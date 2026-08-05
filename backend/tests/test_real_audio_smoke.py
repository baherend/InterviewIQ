"""Optional real-audio smoke test — not part of the default suite.

Actually invokes the real emotion-classifier subprocess and the real DSP
vocal-delivery function against a real sample WAV. Skipped by default
(the default suite must never load the large model); opt in with:

    RUN_REAL_AUDIO_TESTS=1 pytest tests/test_real_audio_smoke.py -v

Requires the InterviewIQ_AI/audio/audio_emotion_package dedicated
virtual environment and checkpoint to already be present on disk (as
they are in this repository) and takes roughly a minute to run. Calls no
paid API.
"""
import os
import shutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_REAL_AUDIO_TESTS") != "1",
    reason="Set RUN_REAL_AUDIO_TESTS=1 to run the real (slow) audio model smoke test.",
)

SAMPLE_WAV = (
    Path(__file__).resolve().parents[2]
    / "InterviewIQ_AI" / "audio" / "audio_emotion_package" / "test_sample.wav"
)


def test_real_audio_pipeline_produces_a_genuine_result(tmp_path):
    from app.services.audio_analysis_service import analyze_answer_segment_audio
    from app.models.answer_segment import ProcessingStatus

    assert SAMPLE_WAV.is_file(), f"Expected real sample audio at {SAMPLE_WAV}"
    media_path = tmp_path / "real_smoke_sample.wav"
    shutil.copy(SAMPLE_WAV, media_path)

    outcome = analyze_answer_segment_audio(media_path)

    assert outcome.processing_status in {
        ProcessingStatus.COMPLETED.value,
        ProcessingStatus.PARTIAL.value,
    }
    assert outcome.emotion_label in {"Low Emotion", "Neutral Emotion", "High Emotion"}
    assert outcome.model_confidence is not None
    assert 0.0 <= outcome.model_confidence <= 1.0
    assert outcome.emotion_probabilities
    assert abs(sum(outcome.emotion_probabilities.values()) - 1.0) < 0.01
    # Transcript-independent DSP sub-scores must be real, computed values.
    assert outcome.pause_control_score is not None
    assert outcome.volume_stability_score is not None
    assert outcome.speech_continuity_score is not None
    assert outcome.sample_rate_hz == 16000
