"""Regression guard for Phase 3A requirement 7/9: the normal per-question
audio flow (segments -> process-audio -> report/history) must never call
the legacy random-value mock in app.ai_modules.audio_module, and must
never use random.uniform/random.gauss/random.randint to produce a normal
student audio result.

app/ai_modules/audio_module.py itself is intentionally left in place
(the legacy POST /interviews/analyze/{interview_id} endpoint still
exists for backward compatibility), but nothing in the new Phase 3A code
path may reach it.
"""
import inspect
import io
from unittest.mock import patch

from conftest import register_and_login, seed_questions, make_wav_bytes

import app.ai_modules.audio_module as legacy_audio_module
import app.routers.interviews as interviews_router
from app.services.audio_analysis_service import AudioAnalysisOutcome
from app.models.answer_segment import ProcessingStatus


def test_new_segment_flow_never_calls_legacy_mock_run_audio(client, db_session):
    _, interview_type = seed_questions(db_session, count=1)
    headers, _ = register_and_login(client)

    r = client.post(
        "/api/interviews/start-interview",
        json={"interview_type": interview_type, "track": "Pytest Track"},
        headers=headers,
    )
    interview = r.json()
    q = interview["questions"][0]

    with patch.object(legacy_audio_module, "run_audio") as mock_legacy_run_audio, patch(
        "app.routers.interviews.analyze_answer_segment_audio",
        return_value=AudioAnalysisOutcome(
            processing_status=ProcessingStatus.COMPLETED.value,
            create_audio_analysis=True,
            emotion_label="Neutral Emotion",
            model_confidence=0.7,
            vocal_delivery_score=65.0,
        ),
    ):
        client.post(
            f"/api/interviews/{interview['id']}/segments",
            data={"interview_question_id": str(q["id"])},
            files={"media": ("a.webm", io.BytesIO(make_wav_bytes()), "video/webm")},
            headers=headers,
        )
        client.post(f"/api/interviews/{interview['id']}/process-audio", headers=headers)
        client.get(f"/api/interviews/report/{interview['id']}", headers=headers)
        client.get("/api/dashboard/history", headers=headers)

    mock_legacy_run_audio.assert_not_called()


def test_legacy_mock_is_confined_to_the_old_analyze_endpoint_only():
    """Source-level check: `run_audio` (the app.ai_modules mock) may only
    be referenced by the old, deliberately-untouched legacy endpoint —
    never by any Phase 3A function.
    """
    phase_3a_functions = [
        interviews_router.upload_answer_segment,
        interviews_router.start_audio_processing,
        interviews_router.get_processing_status,
        interviews_router.retry_segment_audio,
        interviews_router._process_segment_audio_task,
        interviews_router.start_interview,
        interviews_router.get_interview_questions,
    ]
    for fn in phase_3a_functions:
        source = inspect.getsource(fn)
        assert "run_audio(" not in source, f"{fn.__name__} must not call the legacy mock run_audio"
        assert "random." not in source, f"{fn.__name__} must not use the `random` module"

    # The legacy endpoint is the one documented, intentional exception.
    legacy_source = inspect.getsource(interviews_router.analyze_interview)
    assert "run_audio(" in legacy_source


def test_no_random_module_usage_anywhere_in_phase_3a_source_files():
    import app.services.audio_analysis_service as audio_service
    import app.models.answer_segment as answer_segment_model
    import app.models.audio_analysis as audio_analysis_model
    import app.models.interview_question as interview_question_model

    for module in (audio_service, answer_segment_model, audio_analysis_model, interview_question_model):
        source = inspect.getsource(module)
        assert "import random" not in source
        # Checked as call syntax (with a paren), not a bare substring —
        # audio_analysis.py's own docstring *names* these functions in
        # prose to explain what it deliberately does not do, which would
        # otherwise be a false positive here.
        assert "random.uniform(" not in source
        assert "random.gauss(" not in source
        assert "random.randint(" not in source
