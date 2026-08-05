"""Phase 3A: ordered, server-persisted interview question sequence."""
import pytest
from sqlalchemy.exc import IntegrityError

from conftest import register_and_login, seed_questions, unique_interview_type


def test_start_interview_requires_auth(client):
    r = client.post("/api/interviews/start-interview", json={"interview_type": "Technical", "track": "Pytest Track"})
    assert r.status_code == 401


def test_start_interview_persists_ordered_sequence(client, db_session):
    _, interview_type = seed_questions(db_session, track="Pytest Track", count=3)
    headers, _ = register_and_login(client)

    r = client.post(
        "/api/interviews/start-interview",
        json={"interview_type": interview_type, "track": "Pytest Track"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    questions = body["questions"]
    assert len(questions) == 3
    # Server-persisted order, ascending by sequence_index, with no gaps.
    assert [q["sequence_index"] for q in questions] == [0, 1, 2]
    for q in questions:
        assert q["question_text"].startswith("Pytest question")

    # Re-fetching must return exactly the same persisted rows/order, not a
    # freshly re-derived list.
    r2 = client.get(f"/api/interviews/{body['id']}/questions", headers=headers)
    assert r2.status_code == 200
    refetched = r2.json()
    assert [q["id"] for q in refetched] == [q["id"] for q in questions]
    assert [q["sequence_index"] for q in refetched] == [0, 1, 2]


def test_start_interview_no_eligible_questions_returns_422(client):
    headers, _ = register_and_login(client)
    r = client.post(
        "/api/interviews/start-interview",
        json={"interview_type": "Nonexistent Type", "track": "Nonexistent Track"},
        headers=headers,
    )
    assert r.status_code == 422


def test_interview_questions_ownership_enforced(client, db_session):
    _, interview_type = seed_questions(db_session, interview_type=unique_interview_type("HR"), track=None, count=1)
    headers_a, _ = register_and_login(client)
    headers_b, _ = register_and_login(client)

    r = client.post(
        "/api/interviews/start-interview", json={"interview_type": interview_type, "track": None}, headers=headers_a
    )
    interview_id = r.json()["id"]

    r = client.get(f"/api/interviews/{interview_id}/questions", headers=headers_b)
    assert r.status_code == 404


def test_duplicate_sequence_index_rejected_at_db_level(db_session):
    """The unique(interview_id, sequence_index) constraint is the actual
    integrity backstop — verified directly against the ORM/DB layer.
    """
    from app.models.interview import Interview
    from app.models.interview_question import InterviewQuestion
    from app.models.user import User
    from app.auth.password import hash_password

    user = User(name="Constraint Test", email="constraint-test@example.com", password_hash=hash_password("x"))
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    interview = Interview(user_id=user.id, interview_type="Technical", track=None)
    db_session.add(interview)
    db_session.commit()
    db_session.refresh(interview)

    db_session.add(InterviewQuestion(
        interview_id=interview.id, question_id=None, sequence_index=0, question_text="Q1",
    ))
    db_session.commit()

    db_session.add(InterviewQuestion(
        interview_id=interview.id, question_id=None, sequence_index=0, question_text="Q2 (duplicate index)",
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
