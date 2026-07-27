"""
asr/engine.py — Phase 7 ASR engine: faster-whisper transcription producing
Format Spec v1.1 exactly (configs/asr.yaml's `output.fields` — the canonical,
authoritative field list and order; this module reads it from Config rather
than duplicating it as a hardcoded constant, so the YAML stays the single
source of truth).

Pipeline order per configs/asr.yaml: VAD runs FIRST (audio.segmentation.run_vad)
and decides status (ok/no_speech/too_short); faster-whisper only actually
transcribes on status="ok". VAD features come from Silero on the raw
waveform, never from Whisper's own word timestamps.

Model loading is lazy and injectable (same convention as
retrieval/chunk_cap.py's BgeM3Embedder and audio/segmentation.py's SileroVad):
FasterWhisperBackend does not import/construct faster_whisper.WhisperModel
until `.transcribe()` is first called, and transcribe_audio() accepts a
`whisper_backend`/`vad_backend` for tests to inject fakes — no test in this
repo downloads a real model or touches the network.

device/compute_type overrides (transcribe_audio's device_override /
compute_type_override params) let a caller run on Kaggle GPU for
experimentation WITHOUT editing configs/asr.yaml — the config file remains
the registered CPU/int8 production baseline (per its own header comment:
"Do NOT change `checkpoint` without closing G3"; device/compute_type are not
`checkpoint` and are explicitly designed to be override-able per call).

NORMALIZATION — honest placeholder, not a real implementation yet: no
normalization rule is registered anywhere in decisions.md or
PROJECT_EXECUTION_PLAN.md beyond the *target* ("formal_arabic" register,
Latin-script technical terms — configs/asr.yaml's `normalization` section,
which is the Claim Decomposition module's job per D74, not this one's).
`_normalize_transcript` therefore does not invent any rule: normalized_transcript
== raw_transcript verbatim, normalization_log == [] always, in this first
version. This must not be read as "normalization is complete" — it is
explicitly not implemented, only structurally wired so the Format Spec field
exists and downstream code (decomposition) has something to consume.

pre_answer_latency_sec — INTERPRETED, not a registered decision: this field
name appears in configs/asr.yaml and PROJECT_EXECUTION_PLAN.md §[1] with no
further definition. Given "Video/Audio (per-question segments via click
timestamps)" (PROJECT_EXECUTION_PLAN.md §2 — each answer is already its own
segment), the most defensible reading is "how long after the segment started
before the candidate began speaking" — i.e. the start time (in seconds) of
the first VAD-detected speech segment within this answer's audio. That is
what is computed below. This interpretation is NOT registered as a D##
decision — flag for explicit confirmation before relying on it downstream.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from interview_iq.audio.segmentation import VadBackend, run_vad
from interview_iq.config import Config


class ASRError(RuntimeError):
    """Raised on unrecoverable ASR failure: missing audio file, faster-whisper
    model load failure, or a transcription crash. Callers must not silently
    swallow this — a failed transcription must not be treated as an empty/ok
    result (same contract as decomposition_llm.client.LLMDecompositionError)."""


class WhisperBackend(Protocol):
    """Anything with a `.transcribe(audio_path, language) -> (segments, info)`
    method matching faster-whisper's own WhisperModel.transcribe() return
    shape (an iterable of segment objects with .text/.avg_logprob/.words, and
    an info object). Tests inject a fake implementation; production uses
    FasterWhisperBackend."""

    def transcribe(self, audio_path: str, language: str) -> tuple[Any, Any]: ...


class FasterWhisperBackend:
    """Lazy, real faster-whisper backend (production path).

    Not constructed until `.transcribe()` is first called, so this class can
    be default-constructed anywhere without ever loading a model unless
    transcription actually runs (see module docstring).
    """

    def __init__(self, checkpoint: str, device: str, compute_type: str) -> None:
        self._checkpoint = checkpoint
        self._device = device
        self._compute_type = compute_type
        self._model: Any = None

    def _ensure_loaded(self) -> None:
        if self._model is None:
            from faster_whisper import WhisperModel  # heavy import deferred to first use

            print(
                f"[asr.engine] Loading faster-whisper {self._checkpoint} "
                f"(device={self._device}, compute_type={self._compute_type}) ..."
            )
            self._model = WhisperModel(self._checkpoint, device=self._device, compute_type=self._compute_type)

    def transcribe(self, audio_path: str, language: str) -> tuple[Any, Any]:
        self._ensure_loaded()
        return self._model.transcribe(audio_path, language=language, word_timestamps=True)


def _normalize_transcript(raw_transcript: str) -> tuple[str, list[str]]:
    """First version: no normalization rule is registered yet — see module
    docstring's NORMALIZATION note. Returns (raw_transcript unchanged, empty
    log) rather than inventing an unregistered rule."""
    return raw_transcript, []


def _format_spec_fields(cfg: Config) -> tuple[str, ...]:
    """The canonical field order comes from configs/asr.yaml itself (the
    authoritative spec — see module docstring), never a hardcoded duplicate."""
    return tuple(cfg.asr["output"]["fields"])


def _empty_stage_result(fields: tuple[str, ...], question_id: str | None, status: str, vad_features: dict[str, Any]) -> dict[str, Any]:
    """Fills every Format Spec field for a status that never reaches Whisper
    (no_speech / too_short): transcript fields are empty strings/lists, not
    None, so downstream consumers (decomposition) always see a valid (if
    empty) string type — only `avg_logprob` and `pre_answer_latency_sec`
    (which genuinely have no measurement in this case) stay None."""
    record = dict.fromkeys(fields)
    record["question_id"] = question_id
    record["status"] = status
    record["raw_transcript"] = ""
    record["normalized_transcript"] = ""
    record["normalization_log"] = []
    record["word_timestamps"] = []
    record["vad_features"] = vad_features
    record["avg_logprob"] = None
    record["pre_answer_latency_sec"] = None
    return record


def transcribe_audio(
    audio_path: str | Path,
    config: Config | None = None,
    device_override: str | None = None,
    compute_type_override: str | None = None,
    question_id: str | None = None,
    whisper_backend: WhisperBackend | None = None,
    vad_backend: VadBackend | None = None,
) -> dict[str, Any]:
    """Transcribe one answer-segment audio file into a Format Spec v1.1 dict.

    Runs VAD first (audio.segmentation.run_vad); if status != "ok", returns
    immediately with empty transcript fields (no faster-whisper call at all —
    this mirrors configs/asr.yaml's own comment: "status ... decided by VAD,
    before the ASR"). Otherwise runs faster-whisper and fills every field.

    Raises ASRError (never returns a partial/fabricated result) if:
      - audio_path does not exist,
      - the whisper backend fails to load or crashes during transcription.

    device_override / compute_type_override let a caller run on GPU (Kaggle)
    without touching configs/asr.yaml — see module docstring.
    """
    cfg = config or Config()
    fields = _format_spec_fields(cfg)

    audio_path = Path(audio_path)
    if not audio_path.is_file():
        raise ASRError(f"Audio file not found: {audio_path}")

    model_cfg = cfg.asr["model"]
    device = device_override or model_cfg["device"]
    compute_type = compute_type_override or model_cfg["compute_type"]
    checkpoint = model_cfg["checkpoint"]
    language = model_cfg["language"]

    vad_result = run_vad(audio_path, config=cfg, backend=vad_backend)

    if vad_result.status != "ok":
        record = _empty_stage_result(fields, question_id, vad_result.status, vad_result.vad_features)
        # "too_short" still has a first detected speech segment (just below
        # the min-duration threshold) -- "no_speech" has none at all, so
        # pre_answer_latency_sec stays None (set by _empty_stage_result).
        segments = vad_result.vad_features["segments"]
        if vad_result.status == "too_short" and segments:
            record["pre_answer_latency_sec"] = round(segments[0]["start_ms"] / 1000, 3)
        return record

    backend = whisper_backend or FasterWhisperBackend(checkpoint=checkpoint, device=device, compute_type=compute_type)
    try:
        segments, _info = backend.transcribe(str(audio_path), language=language)
        segments = list(segments)  # faster-whisper returns a generator
    except Exception as exc:  # noqa: BLE001 -- any whisper-backend failure must surface as ASRError, not crash the caller
        raise ASRError(f"faster-whisper transcription failed for {audio_path}: {type(exc).__name__}: {exc}") from exc

    raw_transcript = "".join(seg.text for seg in segments).strip()
    word_timestamps: list[dict[str, Any]] = []
    logprobs: list[float] = []
    for seg in segments:
        logprobs.append(float(seg.avg_logprob))
        for w in getattr(seg, "words", None) or []:
            word_timestamps.append({"word": w.word, "start": w.start, "end": w.end})
    avg_logprob = sum(logprobs) / len(logprobs) if logprobs else None

    normalized_transcript, normalization_log = _normalize_transcript(raw_transcript)

    # pre_answer_latency_sec — see module docstring: start of the first
    # VAD-detected speech segment, not this function's own wall-clock cost.
    first_segment = vad_result.vad_features["segments"][0]
    pre_answer_latency_sec = round(first_segment["start_ms"] / 1000, 3)

    record = dict.fromkeys(fields)
    record["question_id"] = question_id
    record["status"] = "ok"
    record["raw_transcript"] = raw_transcript
    record["normalized_transcript"] = normalized_transcript
    record["normalization_log"] = normalization_log
    record["word_timestamps"] = word_timestamps
    record["vad_features"] = vad_result.vad_features
    record["avg_logprob"] = avg_logprob
    record["pre_answer_latency_sec"] = pre_answer_latency_sec
    return record
