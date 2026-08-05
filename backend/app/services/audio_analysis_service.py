"""Real local audio analysis for one answer-segment media file.

Wraps the existing, already-implemented real audio code under
`InterviewIQ_AI/audio/` — it does not reimplement, retune, or otherwise
change any formula or threshold:

  * Emotion classification (Wav2Vec2-XLSR + BiLSTM, trained on BAVED) —
    `InterviewIQ_AI/audio/audio_emotion_package/audio_module.py`, run out
    of process in its own dedicated virtual environment, via the same
    adapter/subprocess pattern already used by the Fusion pipeline
    (`InterviewIQ_AI/fusion/adapters/audio_adapter.py` +
    `InterviewIQ_AI/fusion/runners/run_audio_json.py`).

  * Vocal-delivery DSP heuristic —
    `InterviewIQ_AI/audio/audio_confidence.py::calculate_audio_confidence`,
    imported directly and run in-process (pure numpy/wave code, no heavy
    ML dependency, already available in this backend's own environment).

Deliberately excluded from this module, per Phase 3A scope: NLP/ASR,
Vision, Late Fusion, Groq, BGE-M3, NLI. In particular, no transcript is
produced or supplied here, so `calculate_audio_confidence` is called with
`transcript=None` — its composite `vocal_confidence_score` requires word
count for speaking-rate scoring, so it will legitimately be `None`
("insufficient evidence") for the speaking-rate component and the
composite score in most/all cases in this phase, while the
transcript-independent sub-scores (pause control, volume stability,
speech continuity) are still real, computed values. This is the existing
formula's real, honest behavior given a real, currently-missing input —
not a bug and not something this module works around.

Never returns a random or fabricated value. Every failure path returns a
typed outcome (`AudioAnalysisOutcome`) with a stable `failure_code` (see
`app.models.answer_segment.AudioFailureCode`) and a human-readable
`failure_message`, and never silently substitutes zero or a mock score.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
import wave
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from app.config import settings
from app.models.answer_segment import AudioFailureCode, ProcessingStatus

# --- Make the existing real audio code importable without duplicating it ---
# Only the InterviewIQ_AI root is added to sys.path, which makes `audio`
# and `fusion` resolve as (implicit namespace) packages. We deliberately
# do NOT add InterviewIQ_AI/fusion itself to sys.path, which would make
# generically-named top-level modules there (e.g. `config`, `adapters`)
# shadow anything else in this long-lived process that happens to import
# a bare module of the same name.
_INTERVIEWIQ_AI_DIR = str(settings.interviewiq_ai_dir)
if _INTERVIEWIQ_AI_DIR not in sys.path:
    sys.path.insert(0, _INTERVIEWIQ_AI_DIR)

from audio.audio_confidence import calculate_audio_confidence  # noqa: E402
from fusion.adapters.base import run_json_component  # noqa: E402

AUDIO_MODEL_IDENTIFIER = (
    "InterviewIQ_AI/audio/audio_emotion_package "
    "(Wav2Vec2-XLSR-53 + BiLSTM, BAVED-trained, 3-class: "
    "Low/Neutral/High Emotion)"
)


@lru_cache(maxsize=1)
def _model_version() -> Optional[str]:
    """Best-effort, honest model/checkpoint identity from the package's
    own config.json. Returns None (not a guess) if unavailable — this
    function never fabricates a version string, and it does not surface
    any accuracy/F1 metric (those are not repository-verified — see
    PROJECT_STATUS_AUDIT_2026-08-04.md).
    """
    config_path = settings.audio_emotion_package_dir / "config.json"
    try:
        import json

        payload = json.loads(config_path.read_text(encoding="utf-8"))
        model_id = payload.get("model_id")
        experiment = payload.get("experiment")
        if model_id and experiment:
            return f"{model_id}:{experiment}"
        return str(model_id or experiment) if (model_id or experiment) else None
    except (OSError, ValueError, TypeError):
        return None


@dataclass
class AudioAnalysisOutcome:
    processing_status: str
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    create_audio_analysis: bool = False

    emotion_label: Optional[str] = None
    emotion_probabilities: Optional[dict[str, float]] = None
    model_confidence: Optional[float] = None

    vocal_delivery_score: Optional[float] = None
    speaking_rate_wpm: Optional[float] = None
    speaking_rate_score: Optional[float] = None
    pause_ratio: Optional[float] = None
    pause_control_score: Optional[float] = None
    volume_stability_score: Optional[float] = None
    speech_continuity_score: Optional[float] = None
    sufficient_evidence: Optional[bool] = None
    audio_failure_reason: Optional[str] = None

    model_identifier: Optional[str] = None
    model_version: Optional[str] = None
    sample_rate_hz: Optional[int] = None
    duration_seconds: Optional[float] = None
    raw_diagnostic: Optional[dict[str, Any]] = field(default=None)


def _extract_mono_wav(video_path: Path, wav_path: Path, timeout: int) -> tuple[bool, Optional[str], bool]:
    """Mirrors InterviewIQ_AI/fusion/fusion_pipeline.py::extract_audio —
    same ffmpeg arguments (mono, 16kHz, PCM16), same safety properties
    (no shell=True, explicit timeout, captured output). Not imported
    directly from fusion_pipeline.py to avoid pulling in that module's
    NLP/vision adapter imports for what is otherwise a five-line ffmpeg
    call. Returns (ok, error_message, timed_out).
    """
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    command = [
        ffmpeg, "-y", "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        str(wav_path),
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, check=False, shell=False,
        )
    except subprocess.TimeoutExpired:
        return False, "Audio extraction timed out.", True
    except OSError as exc:
        return False, f"Could not start audio extraction: {exc}", False
    if completed.returncode != 0 or not wav_path.is_file():
        stderr_tail = (completed.stderr or "").strip()[-500:]
        return False, f"ffmpeg exited with code {completed.returncode}. {stderr_tail}".strip(), False
    return True, None, False


def _read_wav_metadata(wav_path: Path) -> tuple[Optional[int], Optional[float]]:
    try:
        with wave.open(str(wav_path), "rb") as wav_file:
            rate = wav_file.getframerate()
            frames = wav_file.getnframes()
            duration = frames / rate if rate else None
            return rate, duration
    except (OSError, wave.Error):
        return None, None


def _run_emotion_classifier(wav_path: Path, timeout: int) -> tuple[Optional[dict], dict]:
    """Runs the real emotion classifier in its dedicated environment,
    reusing the existing subprocess/JSON-validation plumbing
    (`fusion.adapters.base.run_json_component`) rather than
    reimplementing it. Returns (parsed_result_or_None, execution_info).
    """
    audio_python = settings.audio_emotion_python
    audio_runner = settings.audio_emotion_runner
    checkpoint = settings.audio_emotion_checkpoint
    if not (audio_python.is_file() and audio_runner.is_file() and checkpoint.is_file()):
        return None, {
            "status": "failed",
            "error": {
                "type": "PreflightError",
                "message": (
                    "The dedicated audio-model environment or checkpoint is not "
                    "available on this machine (expected a virtual environment at "
                    f"{audio_python} and a checkpoint at {checkpoint})."
                ),
            },
        }

    import os

    env = os.environ.copy()
    env["PYTHONPATH"] = str(settings.audio_emotion_package_dir)
    env["PYTHONIOENCODING"] = "utf-8"
    command = [str(audio_python), str(audio_runner), "--audio", str(wav_path)]
    parsed, execution = run_json_component(
        command, settings.audio_emotion_package_dir, env, timeout
    )
    return parsed, execution


def _validate_emotion_result(parsed: dict) -> bool:
    if not isinstance(parsed, dict):
        return False
    if "dominant_emotion" not in parsed or "emotion_scores" not in parsed:
        return False
    if not isinstance(parsed.get("emotion_scores"), dict) or not parsed["emotion_scores"]:
        return False
    confidence = parsed.get("confidence_score")
    return isinstance(confidence, (int, float)) and not isinstance(confidence, bool)


def analyze_answer_segment_audio(media_path: Path) -> AudioAnalysisOutcome:
    """Single entry point. Takes the path to one uploaded answer-segment
    media file (video, containing audio) and returns a typed outcome.
    Performs no database access — callers persist the result.
    """
    media_path = Path(media_path)
    if not media_path.is_file() or media_path.stat().st_size == 0:
        return AudioAnalysisOutcome(
            processing_status=ProcessingStatus.FAILED.value,
            failure_code=AudioFailureCode.AUDIO_FILE_EMPTY.value,
            failure_message="The stored answer segment media file is missing or empty.",
        )

    # Never derive the extraction target with a plain suffix swap: if the
    # source media happens to already be a .wav file (unlikely in
    # production, where segments are always browser-recorded video, but
    # possible for direct testing/uploads), that would collide with the
    # input path and ffmpeg refuses to edit a file in place.
    wav_path = media_path.with_name(media_path.stem + "_extracted.wav")
    extracted, extraction_error, timed_out = _extract_mono_wav(
        media_path, wav_path, settings.AUDIO_EXTRACTION_TIMEOUT_SECONDS
    )
    if not extracted:
        return AudioAnalysisOutcome(
            processing_status=ProcessingStatus.FAILED.value,
            failure_code=(
                AudioFailureCode.AUDIO_TIMEOUT.value
                if timed_out
                else AudioFailureCode.AUDIO_EXTRACTION_FAILED.value
            ),
            failure_message=extraction_error or "Audio extraction failed for an unknown reason.",
        )

    sample_rate_hz, duration_seconds = _read_wav_metadata(wav_path)

    try:
        vocal_result = calculate_audio_confidence(wav_path, transcript=None)
    except Exception as exc:  # pragma: no cover - calculate_audio_confidence already self-guards
        vocal_result = {
            "vocal_confidence_score": None, "sufficient_evidence": False,
            "warnings": [f"{type(exc).__name__}: {exc}"],
        }

    vocal_warnings = list(vocal_result.get("warnings") or [])
    # calculate_audio_confidence's internal `empty` fallback leaves every
    # transcript-independent sub-score at None too — that combination is
    # how we distinguish "no usable audio signal at all" (zero duration,
    # unreadable, or no measurable energy) from "signal present, only the
    # transcript-dependent parts are unavailable" (the expected, common
    # case in this phase).
    truly_empty = vocal_result.get("pause_control_score") is None

    if truly_empty:
        return AudioAnalysisOutcome(
            processing_status=ProcessingStatus.INSUFFICIENT_EVIDENCE.value,
            failure_code=AudioFailureCode.AUDIO_INSUFFICIENT_EVIDENCE.value,
            failure_message=(
                "; ".join(vocal_warnings)
                or "The recorded audio did not contain enough signal to analyze."
            ),
            create_audio_analysis=True,
            vocal_delivery_score=None,
            sufficient_evidence=False,
            audio_failure_reason="; ".join(vocal_warnings) or None,
            model_identifier=AUDIO_MODEL_IDENTIFIER,
            model_version=_model_version(),
            sample_rate_hz=sample_rate_hz,
            duration_seconds=duration_seconds,
            raw_diagnostic={"vocal": vocal_result},
        )

    emotion_parsed, emotion_execution = _run_emotion_classifier(
        wav_path, settings.AUDIO_MODEL_TIMEOUT_SECONDS
    )
    emotion_ok = emotion_execution.get("status") == "completed" and _validate_emotion_result(
        emotion_parsed or {}
    )

    emotion_failure_message: Optional[str] = None
    emotion_failure_code: Optional[str] = None
    if not emotion_ok:
        error = emotion_execution.get("error") or {}
        error_type = error.get("type", "")
        message = error.get("message") or "Emotion classification failed."
        if error_type == "PreflightError":
            emotion_failure_code = AudioFailureCode.AUDIO_MODEL_UNAVAILABLE.value
        elif error_type in {"TimeoutExpired", "subprocess.TimeoutExpired"}:
            emotion_failure_code = AudioFailureCode.AUDIO_TIMEOUT.value
        else:
            emotion_failure_code = AudioFailureCode.AUDIO_INFERENCE_FAILED.value
        emotion_failure_message = f"Emotion classification unavailable: {message}"

    vocal_composite_missing_reason = None
    if vocal_result.get("vocal_confidence_score") is None:
        vocal_composite_missing_reason = (
            "Vocal Delivery Score requires a transcript (speaking-rate scoring); "
            "ASR/NLP integration is deferred to a later phase, so this composite "
            "score is not available yet. Pause control, volume stability, and "
            "speech continuity do not depend on a transcript and are shown."
        )
        if vocal_warnings:
            vocal_composite_missing_reason += " (" + "; ".join(vocal_warnings) + ")"

    failure_parts = [m for m in (emotion_failure_message, vocal_composite_missing_reason) if m]
    combined_failure_message = " | ".join(failure_parts) if failure_parts else None

    if emotion_ok and vocal_result.get("vocal_confidence_score") is not None:
        processing_status = ProcessingStatus.COMPLETED.value
        failure_code = None
    elif emotion_ok or vocal_result.get("pause_control_score") is not None:
        processing_status = ProcessingStatus.PARTIAL.value
        failure_code = emotion_failure_code
    else:  # pragma: no cover - truly_empty already handled above
        processing_status = ProcessingStatus.FAILED.value
        failure_code = emotion_failure_code or AudioFailureCode.AUDIO_INFERENCE_FAILED.value

    return AudioAnalysisOutcome(
        processing_status=processing_status,
        failure_code=failure_code,
        failure_message=combined_failure_message,
        create_audio_analysis=True,
        emotion_label=(emotion_parsed or {}).get("dominant_emotion") if emotion_ok else None,
        emotion_probabilities=(emotion_parsed or {}).get("emotion_scores") if emotion_ok else None,
        model_confidence=(emotion_parsed or {}).get("confidence_score") if emotion_ok else None,
        vocal_delivery_score=vocal_result.get("vocal_confidence_score"),
        speaking_rate_wpm=vocal_result.get("speaking_rate_wpm"),
        speaking_rate_score=vocal_result.get("speaking_rate_score"),
        pause_ratio=vocal_result.get("pause_ratio"),
        pause_control_score=vocal_result.get("pause_control_score"),
        volume_stability_score=vocal_result.get("volume_stability_score"),
        speech_continuity_score=vocal_result.get("speech_continuity_score"),
        sufficient_evidence=vocal_result.get("sufficient_evidence"),
        audio_failure_reason=combined_failure_message,
        model_identifier=AUDIO_MODEL_IDENTIFIER,
        model_version=_model_version(),
        sample_rate_hz=sample_rate_hz,
        duration_seconds=duration_seconds,
        raw_diagnostic={"vocal": vocal_result, "emotion_execution": emotion_execution},
    )
