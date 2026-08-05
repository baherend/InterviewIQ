"""Phase 3A: persistence, report/history integration, and aggregation.

Mocks app.routers.interviews.analyze_answer_segment_audio (the real
model/subprocess boundary) so these tests run fast and deterministically,
while exercising the real persistence, report, and history code paths
end-to-end.
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
    with patch("app.routers.interviews.analyze_answer_segment_audio", side_effect=outcomes):
        client.post(f"/api/interviews/{interview['id']}/process-audio", headers=headers)

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
