"""Phase 3A: app.services.audio_analysis_service unit tests.

Mocks only the heavyweight boundaries — the emotion-model subprocess
(`_run_emotion_classifier`) and ffmpeg extraction (`_extract_mono_wav`) —
so the default suite never loads the real ML model and never depends on
ffmpeg being installed on the test runner. `calculate_audio_confidence`
(pure numpy/wave DSP, no ML dependency) runs for real against a real
synthetic WAV file, exactly like InterviewIQ_AI/fusion/test_confidence.py
already does for the same function.
"""
from pathlib import Path
from unittest.mock import patch

from conftest import make_wav_bytes

from app.models.answer_segment import AudioFailureCode, ProcessingStatus
from app.services.audio_analysis_service import analyze_answer_segment_audio


def _write_wav(tmp_path: Path, name: str, **kwargs) -> Path:
    path = tmp_path / name
    path.write_bytes(make_wav_bytes(**kwargs))
    return path


def _fake_extract_ok(video_path, wav_path, timeout):
    # Simulates ffmpeg by copying the (already-WAV) source media
    # unchanged — the extraction step itself is not under test here.
    wav_path.write_bytes(Path(video_path).read_bytes())
    return True, None, False


def test_missing_media_file_returns_audio_file_empty(tmp_path):
    outcome = analyze_answer_segment_audio(tmp_path / "does_not_exist.webm")
    assert outcome.processing_status == ProcessingStatus.FAILED.value
    assert outcome.failure_code == AudioFailureCode.AUDIO_FILE_EMPTY.value
    assert outcome.emotion_label is None
    assert outcome.vocal_delivery_score is None


def test_empty_media_file_returns_audio_file_empty(tmp_path):
    path = tmp_path / "empty.webm"
    path.write_bytes(b"")
    outcome = analyze_answer_segment_audio(path)
    assert outcome.processing_status == ProcessingStatus.FAILED.value
    assert outcome.failure_code == AudioFailureCode.AUDIO_FILE_EMPTY.value


def test_silent_audio_produces_insufficient_evidence_and_skips_model(tmp_path):
    """Genuinely silent/empty audio must be classified as
    insufficient_evidence, and the (heavyweight, real) emotion subprocess
    must never even be invoked for it.
    """
    media = _write_wav(tmp_path, "silent.webm", duration_seconds=1.0, amplitude=0.0)

    with patch(
        "app.services.audio_analysis_service._extract_mono_wav", side_effect=_fake_extract_ok
    ), patch(
        "app.services.audio_analysis_service._run_emotion_classifier"
    ) as mock_emotion:
        outcome = analyze_answer_segment_audio(media)

    mock_emotion.assert_not_called()
    assert outcome.processing_status == ProcessingStatus.INSUFFICIENT_EVIDENCE.value
    assert outcome.failure_code == AudioFailureCode.AUDIO_INSUFFICIENT_EVIDENCE.value
    assert outcome.vocal_delivery_score is None
    assert outcome.emotion_label is None
    # Never a fabricated numeric placeholder for a metric with no evidence.
    assert outcome.pause_control_score is None


def test_successful_normalized_output_keeps_confidence_and_vocal_score_independent(tmp_path):
    """The two real categories (emotion model confidence, DSP vocal
    delivery) must be reported independently — one is never derived from
    or overwritten by the other.
    """
    media = _write_wav(tmp_path, "voice.webm", duration_seconds=2.0, amplitude=0.6)

    fake_emotion_result = {
        "dominant_emotion": "Neutral Emotion",
        "emotion_scores": {"Low Emotion": 0.10, "Neutral Emotion": 0.85, "High Emotion": 0.05},
        "confidence_score": 0.85,
    }

    with patch(
        "app.services.audio_analysis_service._extract_mono_wav", side_effect=_fake_extract_ok
    ), patch(
        "app.services.audio_analysis_service._run_emotion_classifier",
        return_value=(fake_emotion_result, {"status": "completed", "return_code": 0}),
    ) as mock_emotion:
        outcome = analyze_answer_segment_audio(media)

    mock_emotion.assert_called_once()
    assert outcome.emotion_label == "Neutral Emotion"
    assert outcome.model_confidence == 0.85
    assert outcome.emotion_probabilities == fake_emotion_result["emotion_scores"]

    # Vocal delivery composite is independently computed by the real DSP
    # function against real (synthetic) signal, and is not equal to /
    # derived from model_confidence.
    assert outcome.pause_control_score is not None
    assert outcome.volume_stability_score is not None
    assert outcome.speech_continuity_score is not None
    # No transcript is supplied in this phase, so the transcript-dependent
    # composite legitimately stays unavailable — never a random fallback.
    assert outcome.vocal_delivery_score is None
    assert outcome.speaking_rate_wpm is None
    assert outcome.model_confidence != outcome.vocal_delivery_score

    assert outcome.processing_status == ProcessingStatus.PARTIAL.value
    assert outcome.failure_code is None
    assert "transcript" in (outcome.failure_message or "").lower()
    assert outcome.model_identifier is not None
    assert outcome.sample_rate_hz == 16000


def test_timeout_produces_typed_failure_but_keeps_vocal_subscores(tmp_path):
    media = _write_wav(tmp_path, "voice.webm", duration_seconds=2.0, amplitude=0.6)

    with patch(
        "app.services.audio_analysis_service._extract_mono_wav", side_effect=_fake_extract_ok
    ), patch(
        "app.services.audio_analysis_service._run_emotion_classifier",
        return_value=(None, {
            "status": "failed",
            "error": {"type": "TimeoutExpired", "message": "Command timed out"},
        }),
    ):
        outcome = analyze_answer_segment_audio(media)

    assert outcome.failure_code == AudioFailureCode.AUDIO_TIMEOUT.value
    assert outcome.processing_status == ProcessingStatus.PARTIAL.value
    assert outcome.emotion_label is None
    assert outcome.pause_control_score is not None  # DSP portion still real and present


def test_model_unavailable_produces_typed_failure(tmp_path):
    media = _write_wav(tmp_path, "voice.webm", duration_seconds=2.0, amplitude=0.6)

    with patch(
        "app.services.audio_analysis_service._extract_mono_wav", side_effect=_fake_extract_ok
    ), patch(
        "app.services.audio_analysis_service._run_emotion_classifier",
        return_value=(None, {
            "status": "failed",
            "error": {"type": "PreflightError", "message": "venv or checkpoint missing"},
        }),
    ):
        outcome = analyze_answer_segment_audio(media)

    assert outcome.failure_code == AudioFailureCode.AUDIO_MODEL_UNAVAILABLE.value
    assert outcome.processing_status == ProcessingStatus.PARTIAL.value


def test_malformed_adapter_json_rejected(tmp_path):
    media = _write_wav(tmp_path, "voice.webm", duration_seconds=2.0, amplitude=0.6)

    with patch(
        "app.services.audio_analysis_service._extract_mono_wav", side_effect=_fake_extract_ok
    ), patch(
        "app.services.audio_analysis_service._run_emotion_classifier",
        return_value=(None, {
            "status": "failed",
            "error": {"type": "InvalidComponentJSON", "message": "stdout was not JSON"},
        }),
    ):
        outcome = analyze_answer_segment_audio(media)

    assert outcome.failure_code == AudioFailureCode.AUDIO_INFERENCE_FAILED.value
    assert outcome.processing_status == ProcessingStatus.PARTIAL.value


def test_incomplete_emotion_schema_is_treated_as_inference_failure(tmp_path):
    """A syntactically valid JSON object missing required keys must not
    be accepted as a real result.
    """
    media = _write_wav(tmp_path, "voice.webm", duration_seconds=2.0, amplitude=0.6)

    with patch(
        "app.services.audio_analysis_service._extract_mono_wav", side_effect=_fake_extract_ok
    ), patch(
        "app.services.audio_analysis_service._run_emotion_classifier",
        return_value=({"dominant_emotion": "Neutral Emotion"}, {"status": "completed", "return_code": 0}),
    ):
        outcome = analyze_answer_segment_audio(media)

    assert outcome.emotion_label is None
    assert outcome.failure_code == AudioFailureCode.AUDIO_INFERENCE_FAILED.value


def test_extraction_failure_produces_typed_failure_and_no_vocal_attempt(tmp_path):
    media = _write_wav(tmp_path, "voice.webm", duration_seconds=1.0, amplitude=0.6)

    with patch(
        "app.services.audio_analysis_service._extract_mono_wav",
        return_value=(False, "ffmpeg exited with code 1", False),
    ), patch("app.services.audio_analysis_service._run_emotion_classifier") as mock_emotion:
        outcome = analyze_answer_segment_audio(media)

    mock_emotion.assert_not_called()
    assert outcome.processing_status == ProcessingStatus.FAILED.value
    assert outcome.failure_code == AudioFailureCode.AUDIO_EXTRACTION_FAILED.value
    assert outcome.create_audio_analysis is False


def test_extraction_timeout_produces_audio_timeout_code(tmp_path):
    media = _write_wav(tmp_path, "voice.webm", duration_seconds=1.0, amplitude=0.6)

    with patch(
        "app.services.audio_analysis_service._extract_mono_wav",
        return_value=(False, "Audio extraction timed out.", True),
    ):
        outcome = analyze_answer_segment_audio(media)

    assert outcome.failure_code == AudioFailureCode.AUDIO_TIMEOUT.value


def test_no_result_ever_contains_random_placeholder_values(tmp_path):
    """Regression guard: every numeric field on every outcome above is
    either a real computed value or None — nothing in this module ever
    calls random.uniform/random.gauss/random.randint.
    """
    import inspect
    import app.services.audio_analysis_service as service_module

    source = inspect.getsource(service_module)
    assert "random.uniform" not in source
    assert "random.gauss" not in source
    assert "random.randint" not in source
    assert "import random" not in source
