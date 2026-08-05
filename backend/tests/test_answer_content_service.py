"""Phase 3C: app.services.answer_content_service unit tests.

Mocks only the heavyweight boundary — the real Answer-Content-Score
subprocess (`_run_content_score`, which runs claim decomposition via
Groq + BGE-M3 retrieval + NLI in the dedicated .venv_nlp environment) —
so the default suite never calls the real Groq API or loads any NLI/
BGE-M3 model. `_run_content_score` mirrors `_run_asr`/
`_run_emotion_classifier`'s own `(parsed, execution)` contract exactly.
"""
from unittest.mock import patch

from app.models.answer_content_analysis import ContentAnalysisStatus
from app.services.answer_content_service import score_answer_segment_content


def _completed(parsed: dict):
    return parsed, {"status": "completed", "return_code": 0}


def _failed(error_type: str, message: str):
    return None, {"status": "failed", "error": {"type": error_type, "message": message}}


def _success_result(**overrides):
    defaults = dict(
        question="ما هو TDD وما دورته؟",
        question_id="SE-028",
        status="SUCCESS",
        error=None,
        precision=0.75,
        coverage=0.50122,
        harmonic_f=0.6008775435175269,
        score=60.087754351752686,
        claims=["claim one", "claim two"],
        claim_scores=[
            {"claim_index": 0, "claim_text": "claim one", "best_chunk_id": "SE028-C01",
             "max_e": 0.99, "max_c": 0.001, "verdict": "VERIFIED", "claim_score": 1.0},
        ],
        models_used={"decomposition_model": "openai/gpt-oss-120b"},
    )
    defaults.update(overrides)
    return defaults


def test_no_reference_document_never_invokes_subprocess():
    with patch("app.services.answer_content_service._run_content_score") as mock_run:
        outcome = score_answer_segment_content("some transcript", "ok", None)

    mock_run.assert_not_called()
    assert outcome.status == ContentAnalysisStatus.NO_REFERENCE_DOCUMENT.value
    assert outcome.answer_content_score is None
    assert outcome.error_message


def test_no_speech_never_invokes_subprocess():
    with patch("app.services.answer_content_service._run_content_score") as mock_run:
        outcome = score_answer_segment_content("", "no_speech", "SE-028")

    mock_run.assert_not_called()
    assert outcome.status == ContentAnalysisStatus.ASR_NO_SPEECH.value


def test_too_short_never_invokes_subprocess():
    with patch("app.services.answer_content_service._run_content_score") as mock_run:
        outcome = score_answer_segment_content("", "too_short", "SE-028")

    mock_run.assert_not_called()
    assert outcome.status == ContentAnalysisStatus.ASR_TOO_SHORT.value


def test_ok_status_but_empty_transcript_never_invokes_subprocess():
    """A defensive case: transcript_status says 'ok' but the transcript
    string is empty/whitespace-only -- must never be sent to the real
    pipeline (which would itself reject it, but this must never even try).
    """
    with patch("app.services.answer_content_service._run_content_score") as mock_run:
        outcome = score_answer_segment_content("   ", "ok", "SE-028")

    mock_run.assert_not_called()
    assert outcome.status == ContentAnalysisStatus.TRANSCRIPT_UNAVAILABLE.value


def test_success_populates_all_fields_from_the_real_pipeline_result():
    with patch(
        "app.services.answer_content_service._run_content_score",
        return_value=_completed(_success_result()),
    ) as mock_run:
        outcome = score_answer_segment_content("transcript text", "ok", "SE-028")

    mock_run.assert_called_once()
    assert outcome.status == "SUCCESS"
    assert outcome.question_reference_id == "SE-028"
    assert outcome.precision == 0.75
    assert outcome.coverage == 0.50122
    assert outcome.harmonic_f == 0.6008775435175269
    assert outcome.answer_content_score == 60.087754351752686
    assert outcome.claims == ["claim one", "claim two"]
    assert len(outcome.claim_scores) == 1
    assert outcome.model_identifiers == {"decomposition_model": "openai/gpt-oss-120b"}
    assert outcome.raw_diagnostic is not None
    assert outcome.error_message is None


def test_negative_score_is_not_clamped():
    """The real pipeline's score is on a [-100, 100] scale (a confident
    contradiction can push it negative) -- this must never be clipped to
    zero or treated as a failure.
    """
    with patch(
        "app.services.answer_content_service._run_content_score",
        return_value=_completed(_success_result(score=-42.5, precision=-0.85)),
    ):
        outcome = score_answer_segment_content("transcript text", "ok", "SE-028")

    assert outcome.status == "SUCCESS"
    assert outcome.answer_content_score == -42.5
    assert outcome.precision == -0.85


def test_decomposition_failed_persists_typed_status_no_scores():
    with patch(
        "app.services.answer_content_service._run_content_score",
        return_value=_completed({
            "question_id": "SE-028",
            "status": "DECOMPOSITION_FAILED",
            "error": "LLMDecompositionError: Groq call failed after 5 attempts",
            "precision": None, "coverage": None, "score": None,
        }),
    ):
        outcome = score_answer_segment_content("transcript text", "ok", "SE-028")

    assert outcome.status == "DECOMPOSITION_FAILED"
    assert outcome.answer_content_score is None
    assert outcome.precision is None
    assert "Groq" in outcome.error_message


def test_nli_failed_persists_typed_status_no_scores():
    with patch(
        "app.services.answer_content_service._run_content_score",
        return_value=_completed({
            "question_id": "SE-028",
            "status": "NLI_FAILED",
            "error": "RuntimeError: adapter load failed",
            "precision": None, "coverage": None, "score": None,
        }),
    ):
        outcome = score_answer_segment_content("transcript text", "ok", "SE-028")

    assert outcome.status == "NLI_FAILED"
    assert outcome.answer_content_score is None


def test_preflight_missing_produces_execution_failed():
    with patch(
        "app.services.answer_content_service._run_content_score",
        return_value=_failed("PreflightError", "venv or reference data missing"),
    ):
        outcome = score_answer_segment_content("transcript text", "ok", "SE-028")

    assert outcome.status == ContentAnalysisStatus.EXECUTION_FAILED.value
    assert outcome.answer_content_score is None
    assert "venv or reference data missing" in outcome.error_message


def test_malformed_json_produces_execution_failed():
    """Execution reports 'completed' (return code 0) but the parsed body
    has no usable `status` field -- must never be silently treated as a
    real result.
    """
    with patch(
        "app.services.answer_content_service._run_content_score",
        return_value=({"unexpected": "shape"}, {"status": "completed", "return_code": 0}),
    ):
        outcome = score_answer_segment_content("transcript text", "ok", "SE-028")

    assert outcome.status == ContentAnalysisStatus.EXECUTION_FAILED.value


def test_unicode_arabic_transcript_passed_through_unchanged():
    arabic_transcript = "مرحبا، هذا اختبار للنسخ الصوتي في هذه المقابلة"
    with patch(
        "app.services.answer_content_service._run_content_score",
        return_value=_completed(_success_result()),
    ) as mock_run:
        score_answer_segment_content(arabic_transcript, "ok", "SE-028")

    called_args = mock_run.call_args[0]
    assert called_args[0] == arabic_transcript


def test_no_result_ever_contains_random_placeholder_values():
    """Regression guard: every numeric field on every outcome above is
    either a real value from the real pipeline or None -- nothing in
    this module ever calls random.uniform/random.gauss/random.randint,
    and Groq is reachable only via decomposition_llm.client, never
    imported directly here.
    """
    import inspect
    import app.services.answer_content_service as service_module

    source = inspect.getsource(service_module)
    assert "random.uniform" not in source
    assert "random.gauss" not in source
    assert "random.randint" not in source
    assert "import random" not in source
    assert "GROQ_API_KEY" not in source
    assert "requests.post" not in source
