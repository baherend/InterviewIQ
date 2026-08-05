"""Phase 3A/3B: persistence, report/history integration, and aggregation.

Mocks app.routers.interviews.analyze_answer_segment_audio (the real
model/subprocess boundary, which now includes ASR — see
app.services.audio_analysis_service) so these tests run fast and
deterministically, while exercising the real persistence, report, and
history code paths end-to-end.
"""
import io
from unittest.mock import patch

from conftest import register_and_login, seed_questions, make_wav_bytes

from app.models.answer_segment import AudioFailureCode, ProcessingStatus
from app.services.audio_analysis_service import AudioAnalysisOutcome


def _start_interview(client, headers, *, interview_type, track="Pytest Track"):
    r = client.post(
        "/api/interviews/start-interview",
        json={"interview_type": interview_type, "track": track},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def _upload_segment(client, headers, interview_id, question):
    r = client.post(
        f"/api/interviews/{interview_id}/segments",
        data={"interview_question_id": str(question["id"])},
        files={"media": ("answer.webm", io.BytesIO(make_wav_bytes()), "video/webm")},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def _successful_outcome(**overrides):
    defaults = dict(
        processing_status=ProcessingStatus.COMPLETED.value,
        failure_code=None,
        failure_message=None,
        create_audio_analysis=True,
        emotion_label="High Emotion",
        emotion_probabilities={"Low Emotion": 0.1, "Neutral Emotion": 0.1, "High Emotion": 0.8},
        model_confidence=0.8,
        transcript="This is the transcribed answer.",
        transcript_status="ok",
        vocal_delivery_score=72.4,
        speaking_rate_wpm=130.0,
        speaking_rate_score=0.9,
        pause_ratio=0.15,
        pause_control_score=0.85,
        volume_stability_score=0.9,
        speech_continuity_score=0.95,
        sufficient_evidence=True,
        audio_failure_reason=None,
        model_identifier="test-model",
        model_version="v1",
        sample_rate_hz=16000,
        duration_seconds=3.0,
        raw_diagnostic={"note": "test"},
    )
    defaults.update(overrides)
    return AudioAnalysisOutcome(**defaults)


def test_audio_analysis_persisted_against_correct_segment(client, db_session):
    _, interview_type = seed_questions(db_session, count=1)
    headers, _ = register_and_login(client)
    interview = _start_interview(client, headers, interview_type=interview_type)
    q = interview["questions"][0]
    segment = _upload_segment(client, headers, interview["id"], q)

    with patch(
        "app.routers.interviews.analyze_answer_segment_audio",
        return_value=_successful_outcome(),
    ) as mock_analyze:
        r = client.post(f"/api/interviews/{interview['id']}/process-audio", headers=headers)
        assert r.status_code == 200

    mock_analyze.assert_called_once()

    from app.models.audio_analysis import AudioAnalysis

    row = db_session.query(AudioAnalysis).filter(
        AudioAnalysis.answer_segment_id == segment["id"]
    ).first()
    assert row is not None
    assert row.emotion_label == "High Emotion"
    assert row.model_confidence == 0.8
    assert row.vocal_delivery_score == 72.4
    assert row.model_confidence_calibrated is False
    # The two categories must never be conflated.
    assert row.model_confidence != row.vocal_delivery_score
    # Phase 3B: transcript persisted against this exact segment's row.
    assert row.transcript == "This is the transcribed answer."
    assert row.transcript_status == "ok"


def test_failed_analysis_persists_failure_code_without_audio_analysis_row(client, db_session):
    _, interview_type = seed_questions(db_session, count=1)
    headers, _ = register_and_login(client)
    interview = _start_interview(client, headers, interview_type=interview_type)
    q = interview["questions"][0]
    segment = _upload_segment(client, headers, interview["id"], q)

    failed_outcome = AudioAnalysisOutcome(
        processing_status=ProcessingStatus.FAILED.value,
        failure_code=AudioFailureCode.AUDIO_EXTRACTION_FAILED.value,
        failure_message="ffmpeg failed",
        create_audio_analysis=False,
    )
    with patch("app.routers.interviews.analyze_answer_segment_audio", return_value=failed_outcome):
        r = client.post(f"/api/interviews/{interview['id']}/process-audio", headers=headers)
        assert r.status_code == 200

    r = client.get(f"/api/interviews/{interview['id']}/processing-status", headers=headers)
    body = r.json()
    assert body["all_terminal"] is True
    assert body["segments"][0]["processing_status"] == "failed"
    assert body["segments"][0]["failure_code"] == "AUDIO_EXTRACTION_FAILED"

    from app.models.audio_analysis import AudioAnalysis

    row = db_session.query(AudioAnalysis).filter(
        AudioAnalysis.answer_segment_id == segment["id"]
    ).first()
    assert row is None


def test_report_reads_persisted_data_and_never_reruns_inference(client, db_session):
    _, interview_type = seed_questions(db_session, count=1)
    headers, _ = register_and_login(client)
    interview = _start_interview(client, headers, interview_type=interview_type)
    q = interview["questions"][0]
    _upload_segment(client, headers, interview["id"], q)

    with patch(
        "app.routers.interviews.analyze_answer_segment_audio",
        return_value=_successful_outcome(),
    ) as mock_analyze:
        client.post(f"/api/interviews/{interview['id']}/process-audio", headers=headers)

        r1 = client.get(f"/api/interviews/report/{interview['id']}", headers=headers)
        r2 = client.get(f"/api/interviews/report/{interview['id']}", headers=headers)

    assert mock_analyze.call_count == 1  # loading the report twice never re-invokes analysis

    report = r2.json()
    assert report["audio_summary"]["available"] is True
    assert report["audio_summary"]["average_vocal_delivery_score"] == 72.4
    q0 = report["questions"][0]
    assert q0["segment"]["audio_analysis"]["model_confidence"] == 0.8
    assert q0["segment"]["audio_analysis"]["vocal_delivery_score"] == 72.4
    assert q0["segment"]["audio_analysis"]["model_confidence_calibrated"] is False
    # Phase 3B: transcript/status reach the Report (and, via the same
    # persisted row, History) API without the frontend recomputing WPM.
    assert q0["segment"]["audio_analysis"]["transcript"] == "This is the transcribed answer."
    assert q0["segment"]["audio_analysis"]["transcript_status"] == "ok"
    assert r1.json() == r2.json()


def test_history_shows_audio_summary_without_rerunning_inference(client, db_session):
    _, interview_type = seed_questions(db_session, count=1)
    headers, _ = register_and_login(client)
    interview = _start_interview(client, headers, interview_type=interview_type)
    q = interview["questions"][0]
    _upload_segment(client, headers, interview["id"], q)

    with patch(
        "app.routers.interviews.analyze_answer_segment_audio",
        return_value=_successful_outcome(),
    ) as mock_analyze:
        client.post(f"/api/interviews/{interview['id']}/process-audio", headers=headers)
        r = client.get("/api/dashboard/history", headers=headers)

    assert mock_analyze.call_count == 1
    item = next(h for h in r.json() if h["id"] == interview["id"])
    assert item["audio_summary"]["available"] is True
    assert item["audio_summary"]["average_vocal_delivery_score"] == 72.4
    assert item["audio_summary"]["valid_segment_count"] == 1
    assert item["audio_summary"]["total_segment_count"] == 1


def test_aggregation_uses_only_valid_scores_and_ignores_missing(client, db_session):
    _, interview_type = seed_questions(db_session, count=3)
    headers, _ = register_and_login(client)
    interview = _start_interview(client, headers, interview_type=interview_type)
    questions = interview["questions"]
    assert len(questions) == 3
    for q in questions:
        _upload_segment(client, headers, interview["id"], q)

    outcomes = [
        _successful_outcome(vocal_delivery_score=60.0),
        _successful_outcome(vocal_delivery_score=80.0),
        _successful_outcome(vocal_delivery_score=None, sufficient_evidence=False,
                             processing_status=ProcessingStatus.PARTIAL.value,
                             audio_failure_reason="no transcript"),
    ]
    with patch(
        "app.routers.interviews.analyze_answer_segment_audio", side_effect=outcomes
    ) as mock_analyze:
        client.post(f"/api/interviews/{interview['id']}/process-audio", headers=headers)

    # One real (ASR-inclusive) analysis call per persisted AnswerSegment —
    # never batched, never skipped, never re-run for a different segment.
    assert mock_analyze.call_count == 3

    r = client.get(f"/api/interviews/report/{interview['id']}", headers=headers)
    summary = r.json()["audio_summary"]
    assert summary["available"] is True
    # Average of 60.0 and 80.0 only — the missing third score must never
    # be treated as 0.
    assert summary["average_vocal_delivery_score"] == 70.0
    assert summary["valid_segment_count"] == 2
    assert summary["total_segment_count"] == 3


def test_no_valid_scores_gives_unavailable_summary(client, db_session):
    _, interview_type = seed_questions(db_session, count=1)
    headers, _ = register_and_login(client)
    interview = _start_interview(client, headers, interview_type=interview_type)
    q = interview["questions"][0]
    _upload_segment(client, headers, interview["id"], q)

    insufficient_outcome = AudioAnalysisOutcome(
        processing_status=ProcessingStatus.INSUFFICIENT_EVIDENCE.value,
        failure_code=AudioFailureCode.AUDIO_INSUFFICIENT_EVIDENCE.value,
        failure_message="Silent audio.",
        create_audio_analysis=True,
        sufficient_evidence=False,
        vocal_delivery_score=None,
    )
    with patch("app.routers.interviews.analyze_answer_segment_audio", return_value=insufficient_outcome):
        client.post(f"/api/interviews/{interview['id']}/process-audio", headers=headers)

    r = client.get(f"/api/interviews/report/{interview['id']}", headers=headers)
    summary = r.json()["audio_summary"]
    assert summary["available"] is False
    assert summary["average_vocal_delivery_score"] is None
    assert summary["reason"]


def test_legacy_interview_with_no_segments_reports_unavailable_honestly(client, db_session):
    """Simulates a pre-Phase-3A interview: an Interview row with no
    InterviewQuestion/AnswerSegment rows at all (as if created before
    this phase existed).
    """
    from app.models.interview import Interview
    from app.models.user import User
    from app.auth.password import hash_password
    from app.auth.jwt_handler import create_access_token

    user = User(name="Legacy User", email="legacy-user@example.com", password_hash=hash_password("x"))
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    legacy_interview = Interview(user_id=user.id, interview_type="Technical", track=None)
    db_session.add(legacy_interview)
    db_session.commit()
    db_session.refresh(legacy_interview)

    # This user was created directly in the DB (not via /register), so we
    # mint its token the same way login would rather than registering a
    # second, unrelated account.
    token = create_access_token({"sub": str(user.id)})
    legacy_headers = {"Authorization": f"Bearer {token}"}

    r = client.get(f"/api/interviews/report/{legacy_interview.id}", headers=legacy_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["questions"] == []
    assert body["audio_summary"]["available"] is False
    assert "historical" in body["audio_summary"]["reason"].lower()

    r2 = client.get("/api/dashboard/history", headers=legacy_headers)
    item = next(h for h in r2.json() if h["id"] == legacy_interview.id)
    assert item["audio_summary"]["available"] is False


def test_two_segments_each_get_their_own_asr_call_bound_to_correct_segment(client, db_session):
    """Two persisted AnswerSegments must cause two independent analysis
    (ASR-inclusive) calls, each result landing on its own segment's row —
    never swapped, merged, or applied to the wrong segment.
    """
    _, interview_type = seed_questions(db_session, count=2)
    headers, _ = register_and_login(client)
    interview = _start_interview(client, headers, interview_type=interview_type)
    q0, q1 = interview["questions"]
    segment0 = _upload_segment(client, headers, interview["id"], q0)
    segment1 = _upload_segment(client, headers, interview["id"], q1)

    outcomes = [
        _successful_outcome(transcript="First answer transcript.", vocal_delivery_score=55.0),
        _successful_outcome(transcript="Second answer transcript.", vocal_delivery_score=90.0),
    ]
    with patch(
        "app.routers.interviews.analyze_answer_segment_audio", side_effect=outcomes
    ) as mock_analyze:
        r = client.post(f"/api/interviews/{interview['id']}/process-audio", headers=headers)
        assert r.status_code == 200

    assert mock_analyze.call_count == 2

    from app.models.audio_analysis import AudioAnalysis

    row0 = db_session.query(AudioAnalysis).filter(
        AudioAnalysis.answer_segment_id == segment0["id"]
    ).first()
    row1 = db_session.query(AudioAnalysis).filter(
        AudioAnalysis.answer_segment_id == segment1["id"]
    ).first()
    assert row0.transcript == "First answer transcript."
    assert row0.vocal_delivery_score == 55.0
    assert row1.transcript == "Second answer transcript."
    assert row1.vocal_delivery_score == 90.0

    # Still exactly one AudioAnalysis row per segment (the FK is
    # unique=True at the model level) — no duplicates from this run.
    assert db_session.query(AudioAnalysis).filter(
        AudioAnalysis.answer_segment_id.in_([segment0["id"], segment1["id"]])
    ).count() == 2


def test_unicode_transcript_round_trips_through_report_api(client, db_session):
    _, interview_type = seed_questions(db_session, count=1)
    headers, _ = register_and_login(client)
    interview = _start_interview(client, headers, interview_type=interview_type)
    q = interview["questions"][0]
    _upload_segment(client, headers, interview["id"], q)

    arabic_transcript = "مرحبا، هذا اختبار للنسخ الصوتي في هذه المقابلة"
    with patch(
        "app.routers.interviews.analyze_answer_segment_audio",
        return_value=_successful_outcome(transcript=arabic_transcript, transcript_status="ok"),
    ):
        client.post(f"/api/interviews/{interview['id']}/process-audio", headers=headers)

    r = client.get(f"/api/interviews/report/{interview['id']}", headers=headers)
    q0 = r.json()["questions"][0]
    assert q0["segment"]["audio_analysis"]["transcript"] == arabic_transcript


def test_legacy_audio_analysis_row_with_null_transcript_serializes_gracefully(client, db_session):
    """Simulates a row written before the Phase 3B migration (transcript
    columns default to NULL for every pre-existing row) — the API must
    treat this as "not available", not an error.
    """
    _, interview_type = seed_questions(db_session, count=1)
    headers, _ = register_and_login(client)
    interview = _start_interview(client, headers, interview_type=interview_type)
    q = interview["questions"][0]
    segment = _upload_segment(client, headers, interview["id"], q)

    from app.models.audio_analysis import AudioAnalysis

    legacy_row = AudioAnalysis(
        answer_segment_id=segment["id"],
        emotion_label="Neutral Emotion",
        model_confidence=0.7,
        model_confidence_calibrated=False,
        vocal_delivery_score=None,
        transcript=None,
        transcript_status=None,
    )
    db_session.add(legacy_row)
    db_session.commit()

    r = client.get(f"/api/interviews/report/{interview['id']}", headers=headers)
    assert r.status_code == 200
    audio_payload = r.json()["questions"][0]["segment"]["audio_analysis"]
    assert audio_payload["transcript"] is None
    assert audio_payload["transcript_status"] is None
    assert audio_payload["emotion_label"] == "Neutral Emotion"


# ============================================================================
# Phase 3C — real Answer Content Score, persistence, report/history
# integration.
#
# Mocks app.routers.interviews.score_answer_segment_content (the real
# Groq/BGE-M3/NLI subprocess boundary — see
# app.services.answer_content_service) so these tests run fast and
# deterministically, while exercising the real persistence, report, and
# history code paths end-to-end. One test below deliberately does NOT
# mock it, to prove the real no-reference-document gate short-circuits
# through the actual router/service wiring without any subprocess call.
# ============================================================================

from app.services.answer_content_service import AnswerContentOutcome


def _set_nlp_reference_id(db_session, question_id: int, nlp_reference_id: str) -> None:
    from app.models.question import Question

    question = db_session.query(Question).filter(Question.id == question_id).first()
    question.nlp_reference_id = nlp_reference_id
    db_session.commit()


def _content_success_outcome(**overrides):
    defaults = dict(
        status="SUCCESS",
        error_message=None,
        question_reference_id="SE-028",
        precision=0.75,
        coverage=0.5,
        harmonic_f=0.6,
        answer_content_score=60.0,
        claims=["claim one"],
        claim_scores=[{"claim_index": 0, "claim_text": "claim one", "verdict": "VERIFIED", "claim_score": 1.0}],
        model_identifiers={"decomposition_model": "openai/gpt-oss-120b"},
        raw_diagnostic={"note": "test"},
    )
    defaults.update(overrides)
    return AnswerContentOutcome(**defaults)


def test_content_analysis_persisted_and_appears_in_report_and_history(client, db_session):
    (question,), interview_type = seed_questions(db_session, count=1)
    _set_nlp_reference_id(db_session, question.id, "SE-028")
    headers, _ = register_and_login(client)
    interview = _start_interview(client, headers, interview_type=interview_type)
    q = interview["questions"][0]
    segment = _upload_segment(client, headers, interview["id"], q)

    with patch(
        "app.routers.interviews.analyze_answer_segment_audio", return_value=_successful_outcome()
    ), patch(
        "app.routers.interviews.score_answer_segment_content",
        return_value=_content_success_outcome(),
    ) as mock_content:
        r = client.post(f"/api/interviews/{interview['id']}/process-audio", headers=headers)
        assert r.status_code == 200

    mock_content.assert_called_once()
    # Reuses the audio task's persisted transcript -- never re-runs ASR.
    call_args = mock_content.call_args[0]
    assert call_args[0] == "This is the transcribed answer."
    assert call_args[1] == "ok"
    assert call_args[2] == "SE-028"

    from app.models.answer_content_analysis import AnswerContentAnalysis

    row = db_session.query(AnswerContentAnalysis).filter(
        AnswerContentAnalysis.answer_segment_id == segment["id"]
    ).first()
    assert row is not None
    assert row.status == "SUCCESS"
    assert row.answer_content_score == 60.0
    assert row.precision == 0.75
    assert row.claim_scores[0]["verdict"] == "VERIFIED"

    report = client.get(f"/api/interviews/report/{interview['id']}", headers=headers).json()
    content_payload = report["questions"][0]["segment"]["content_analysis"]
    assert content_payload["status"] == "SUCCESS"
    assert content_payload["answer_content_score"] == 60.0
    assert content_payload["claims"] == ["claim one"]
    assert report["content_summary"]["available"] is True
    assert report["content_summary"]["average_answer_content_score"] == 60.0

    history = client.get("/api/dashboard/history", headers=headers).json()
    item = next(h for h in history if h["id"] == interview["id"])
    assert item["content_summary"]["available"] is True
    assert item["content_summary"]["average_answer_content_score"] == 60.0


def test_two_segments_content_scores_bound_to_correct_question_not_swapped(client, db_session):
    """Two questions, each mapped to a DIFFERENT reference document.
    score_answer_segment_content's mocked return value is driven purely
    by the nlp_reference_id argument it actually receives -- if binding
    were positional/order-based instead of ID-based, the two segments'
    persisted scores would come out swapped.
    """
    (q1, q2), interview_type = seed_questions(db_session, count=2)
    _set_nlp_reference_id(db_session, q1.id, "SE-028")
    _set_nlp_reference_id(db_session, q2.id, "DA-001")
    headers, _ = register_and_login(client)
    interview = _start_interview(client, headers, interview_type=interview_type)
    iq1, iq2 = interview["questions"]
    segment1 = _upload_segment(client, headers, interview["id"], iq1)
    segment2 = _upload_segment(client, headers, interview["id"], iq2)

    def _content_side_effect(transcript, transcript_status, nlp_reference_id, timeout=None):
        score = 11.0 if nlp_reference_id == "SE-028" else 22.0
        return _content_success_outcome(question_reference_id=nlp_reference_id, answer_content_score=score)

    audio_outcomes = [
        _successful_outcome(transcript="First answer."),
        _successful_outcome(transcript="Second answer."),
    ]
    with patch(
        "app.routers.interviews.analyze_answer_segment_audio", side_effect=audio_outcomes
    ), patch(
        "app.routers.interviews.score_answer_segment_content", side_effect=_content_side_effect
    ) as mock_content:
        r = client.post(f"/api/interviews/{interview['id']}/process-audio", headers=headers)
        assert r.status_code == 200

    assert mock_content.call_count == 2

    from app.models.answer_content_analysis import AnswerContentAnalysis

    row1 = db_session.query(AnswerContentAnalysis).filter(
        AnswerContentAnalysis.answer_segment_id == segment1["id"]
    ).first()
    row2 = db_session.query(AnswerContentAnalysis).filter(
        AnswerContentAnalysis.answer_segment_id == segment2["id"]
    ).first()
    assert row1.question_reference_id == "SE-028"
    assert row1.answer_content_score == 11.0
    assert row2.question_reference_id == "DA-001"
    assert row2.answer_content_score == 22.0


def test_content_scoring_gated_out_for_real_when_question_has_no_reference_mapping(client, db_session):
    """Deliberately does NOT mock score_answer_segment_content -- the
    question has no nlp_reference_id, so the real service's own
    eligibility gate must short-circuit (no subprocess, no Groq call)
    and persist NO_REFERENCE_DOCUMENT.
    """
    _, interview_type = seed_questions(db_session, count=1)
    headers, _ = register_and_login(client)
    interview = _start_interview(client, headers, interview_type=interview_type)
    q = interview["questions"][0]
    segment = _upload_segment(client, headers, interview["id"], q)

    with patch(
        "app.routers.interviews.analyze_answer_segment_audio", return_value=_successful_outcome()
    ):
        r = client.post(f"/api/interviews/{interview['id']}/process-audio", headers=headers)
        assert r.status_code == 200

    from app.models.answer_content_analysis import AnswerContentAnalysis

    row = db_session.query(AnswerContentAnalysis).filter(
        AnswerContentAnalysis.answer_segment_id == segment["id"]
    ).first()
    assert row is not None
    assert row.status == "NO_REFERENCE_DOCUMENT"
    assert row.answer_content_score is None


def test_retry_audio_does_not_duplicate_content_analysis_row(client, db_session):
    (question,), interview_type = seed_questions(db_session, count=1)
    _set_nlp_reference_id(db_session, question.id, "SE-028")
    headers, _ = register_and_login(client)
    interview = _start_interview(client, headers, interview_type=interview_type)
    q = interview["questions"][0]
    segment = _upload_segment(client, headers, interview["id"], q)

    with patch(
        "app.routers.interviews.analyze_answer_segment_audio", return_value=_successful_outcome()
    ), patch(
        "app.routers.interviews.score_answer_segment_content",
        return_value=_content_success_outcome(answer_content_score=60.0),
    ):
        client.post(f"/api/interviews/{interview['id']}/process-audio", headers=headers)

    with patch(
        "app.routers.interviews.analyze_answer_segment_audio", return_value=_successful_outcome()
    ), patch(
        "app.routers.interviews.score_answer_segment_content",
        return_value=_content_success_outcome(answer_content_score=75.0),
    ):
        r = client.post(
            f"/api/interviews/{interview['id']}/segments/{segment['id']}/retry-audio", headers=headers
        )
        assert r.status_code == 200

    from app.models.answer_content_analysis import AnswerContentAnalysis

    rows = db_session.query(AnswerContentAnalysis).filter(
        AnswerContentAnalysis.answer_segment_id == segment["id"]
    ).all()
    assert len(rows) == 1
    assert rows[0].answer_content_score == 75.0


def test_legacy_segment_without_content_analysis_serializes_gracefully(client, db_session):
    """Simulates a row written before the Phase 3C migration/processing
    ever ran for it (no AnswerContentAnalysis row at all) -- the API
    must treat this as "not available", not an error.
    """
    _, interview_type = seed_questions(db_session, count=1)
    headers, _ = register_and_login(client)
    interview = _start_interview(client, headers, interview_type=interview_type)
    q = interview["questions"][0]
    _upload_segment(client, headers, interview["id"], q)

    r = client.get(f"/api/interviews/report/{interview['id']}", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["questions"][0]["segment"]["content_analysis"] is None
    assert body["content_summary"]["available"] is False
