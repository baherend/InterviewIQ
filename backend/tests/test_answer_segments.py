"""Phase 3A: answer-segment upload, structural binding, and validation."""
import io

from conftest import register_and_login, seed_questions, make_wav_bytes


def _start_interview(client, headers, *, interview_type, track="Pytest Track"):
    r = client.post(
        "/api/interviews/start-interview",
        json={"interview_type": interview_type, "track": track},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_segment_endpoints_require_auth(client, db_session):
    _, interview_type = seed_questions(db_session, count=1)
    headers, _ = register_and_login(client)
    interview = _start_interview(client, headers, interview_type=interview_type)
    q = interview["questions"][0]

    r = client.post(
        f"/api/interviews/{interview['id']}/segments",
        data={"interview_question_id": str(q["id"])},
        files={"media": ("a.webm", io.BytesIO(make_wav_bytes()), "video/webm")},
    )
    assert r.status_code == 401

    r = client.post(f"/api/interviews/{interview['id']}/process-audio")
    assert r.status_code == 401

    r = client.get(f"/api/interviews/{interview['id']}/processing-status")
    assert r.status_code == 401


def test_valid_segment_upload_succeeds_and_hides_filesystem_path(client, db_session):
    _, interview_type = seed_questions(db_session, count=1)
    headers, _ = register_and_login(client)
    interview = _start_interview(client, headers, interview_type=interview_type)
    q = interview["questions"][0]

    r = client.post(
        f"/api/interviews/{interview['id']}/segments",
        data={
            "interview_question_id": str(q["id"]),
            "question_id": str(q["question_id"]),
            "sequence_index": str(q["sequence_index"]),
            "started_at": "2026-08-05T10:00:00+00:00",
            "ended_at": "2026-08-05T10:00:03+00:00",
        },
        files={"media": ("answer.webm", io.BytesIO(make_wav_bytes()), "video/webm")},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["upload_status"] == "uploaded"
    assert body["processing_status"] == "pending"
    assert "media_path" not in body


def test_wrong_interview_id_rejected(client, db_session):
    _, interview_type = seed_questions(db_session, count=1)
    headers_a, _ = register_and_login(client)
    headers_b, _ = register_and_login(client)
    interview_a = _start_interview(client, headers_a, interview_type=interview_type)
    q = interview_a["questions"][0]

    # user B has no interview at all with this id -> 404 (ownership)
    r = client.post(
        f"/api/interviews/{interview_a['id']}/segments",
        data={"interview_question_id": str(q["id"])},
        files={"media": ("a.webm", io.BytesIO(make_wav_bytes()), "video/webm")},
        headers=headers_b,
    )
    assert r.status_code == 404


def test_question_not_belonging_to_interview_rejected(client, db_session):
    _, interview_type = seed_questions(db_session, count=1)
    headers, _ = register_and_login(client)
    interview_1 = _start_interview(client, headers, interview_type=interview_type)
    interview_2 = _start_interview(client, headers, interview_type=interview_type)
    q_from_interview_2 = interview_2["questions"][0]

    r = client.post(
        f"/api/interviews/{interview_1['id']}/segments",
        data={"interview_question_id": str(q_from_interview_2["id"])},
        files={"media": ("a.webm", io.BytesIO(make_wav_bytes()), "video/webm")},
        headers=headers,
    )
    assert r.status_code == 404


def test_nonexistent_interview_question_rejected(client, db_session):
    _, interview_type = seed_questions(db_session, count=1)
    headers, _ = register_and_login(client)
    interview = _start_interview(client, headers, interview_type=interview_type)

    r = client.post(
        f"/api/interviews/{interview['id']}/segments",
        data={"interview_question_id": "999999"},
        files={"media": ("a.webm", io.BytesIO(make_wav_bytes()), "video/webm")},
        headers=headers,
    )
    assert r.status_code == 404


def test_question_id_mismatch_rejected(client, db_session):
    _, interview_type = seed_questions(db_session, count=1)
    headers, _ = register_and_login(client)
    interview = _start_interview(client, headers, interview_type=interview_type)
    q = interview["questions"][0]

    r = client.post(
        f"/api/interviews/{interview['id']}/segments",
        data={"interview_question_id": str(q["id"]), "question_id": "999999"},
        files={"media": ("a.webm", io.BytesIO(make_wav_bytes()), "video/webm")},
        headers=headers,
    )
    assert r.status_code == 422


def test_sequence_index_mismatch_rejected(client, db_session):
    _, interview_type = seed_questions(db_session, count=1)
    headers, _ = register_and_login(client)
    interview = _start_interview(client, headers, interview_type=interview_type)
    q = interview["questions"][0]

    r = client.post(
        f"/api/interviews/{interview['id']}/segments",
        data={"interview_question_id": str(q["id"]), "sequence_index": "42"},
        files={"media": ("a.webm", io.BytesIO(make_wav_bytes()), "video/webm")},
        headers=headers,
    )
    assert r.status_code == 422


def test_unsupported_extension_rejected(client, db_session):
    _, interview_type = seed_questions(db_session, count=1)
    headers, _ = register_and_login(client)
    interview = _start_interview(client, headers, interview_type=interview_type)
    q = interview["questions"][0]

    r = client.post(
        f"/api/interviews/{interview['id']}/segments",
        data={"interview_question_id": str(q["id"])},
        files={"media": ("a.txt", io.BytesIO(b"not media"), "text/plain")},
        headers=headers,
    )
    assert r.status_code == 415


def test_empty_upload_rejected(client, db_session):
    _, interview_type = seed_questions(db_session, count=1)
    headers, _ = register_and_login(client)
    interview = _start_interview(client, headers, interview_type=interview_type)
    q = interview["questions"][0]

    r = client.post(
        f"/api/interviews/{interview['id']}/segments",
        data={"interview_question_id": str(q["id"])},
        files={"media": ("a.webm", io.BytesIO(b""), "video/webm")},
        headers=headers,
    )
    assert r.status_code == 422


def test_duplicate_finalized_segment_rejected(client, db_session):
    _, interview_type = seed_questions(db_session, count=1)
    headers, _ = register_and_login(client)
    interview = _start_interview(client, headers, interview_type=interview_type)
    q = interview["questions"][0]

    r = client.post(
        f"/api/interviews/{interview['id']}/segments",
        data={"interview_question_id": str(q["id"])},
        files={"media": ("a.webm", io.BytesIO(make_wav_bytes()), "video/webm")},
        headers=headers,
    )
    assert r.status_code == 201

    r2 = client.post(
        f"/api/interviews/{interview['id']}/segments",
        data={"interview_question_id": str(q["id"])},
        files={"media": ("a.webm", io.BytesIO(make_wav_bytes()), "video/webm")},
        headers=headers,
    )
    assert r2.status_code == 409


def test_segment_upload_rejected_after_recording_marked_complete(client, db_session):
    _, interview_type = seed_questions(db_session, count=1)
    headers, _ = register_and_login(client)
    interview = _start_interview(client, headers, interview_type=interview_type)
    q = interview["questions"][0]

    r = client.post(f"/api/interviews/{interview['id']}/process-audio", headers=headers)
    assert r.status_code == 200

    r2 = client.post(
        f"/api/interviews/{interview['id']}/segments",
        data={"interview_question_id": str(q["id"])},
        files={"media": ("a.webm", io.BytesIO(make_wav_bytes()), "video/webm")},
        headers=headers,
    )
    assert r2.status_code == 409
