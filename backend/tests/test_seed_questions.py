"""Phase 3D: app.utils.seed.seed_questions and Question.code regression
tests.

Exercises the real, unmodified production seeding function (never a
reimplementation) against the shared pytest test database -- nothing here
mocks seed_questions itself, only the DB is the pytest fixture's own
isolated SQLite file (see conftest.py), never the real dev database.
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.question import Question
from app.utils.seed import SEED_QUESTIONS, seed_questions


def test_seed_questions_inserts_all_rows_and_is_idempotent(db_session):
    seed_questions(db_session)
    first_count = db_session.query(Question).count()
    assert first_count >= len(SEED_QUESTIONS)

    seed_questions(db_session)
    second_count = db_session.query(Question).count()
    assert second_count == first_count  # no duplicates on a second call


def test_phase_3d_mappings_present_after_seeding(db_session):
    seed_questions(db_session)

    se_028 = db_session.query(Question).filter(Question.code == "se-028-tdd").first()
    assert se_028 is not None
    assert se_028.nlp_reference_id == "SE-028"

    da_017 = db_session.query(Question).filter(Question.code == "da-017-sql-join-inner-left").first()
    assert da_017 is not None
    assert da_017.nlp_reference_id == "DA-017"
    assert da_017.track == "Data Analysis"

    da_005 = db_session.query(Question).filter(Question.code == "da-005-missing-values").first()
    assert da_005 is not None
    assert da_005.nlp_reference_id == "DA-005"
    assert da_005.track == "Data Analysis"

    # Deliberately unmapped -- the NO_REFERENCE_DOCUMENT gate case.
    inferential_stats = db_session.query(Question).filter(
        Question.question == "What is the difference between descriptive and inferential statistics?"
    ).first()
    assert inferential_stats is not None
    assert inferential_stats.code is None
    assert inferential_stats.nlp_reference_id is None


def test_seed_questions_does_not_duplicate_a_coded_row_even_if_text_later_differs(db_session):
    """The whole point of Question.code: dedup must survive a wording
    edit. Simulates a row that was already provisioned with a code, then
    had its question text edited afterward (the exact scenario that
    silently broke the old exact-text matching) -- seed_questions() must
    still recognize it as already present via its code, not insert a
    second row.

    The pytest database file is session-scoped (see conftest.py) -- data
    written by one test is visible to every test that runs after it in
    the same session. This test mutates a real seeded row, so it must
    restore that row's original text itself (try/finally, not relying on
    any fixture to reset it) rather than leaving the mutation behind for
    later tests to silently inherit.
    """
    seed_questions(db_session)
    existing = db_session.query(Question).filter(Question.code == "da-005-missing-values").first()
    original_text = existing.question
    try:
        existing.question = "How should missing values be handled in a dataset? (edited wording)"
        db_session.commit()

        seed_questions(db_session)

        rows = db_session.query(Question).filter(Question.code == "da-005-missing-values").all()
        assert len(rows) == 1
    finally:
        existing.question = original_text
        db_session.commit()


def test_question_code_uniqueness_enforced_at_db_level(db_session):
    db_session.add(Question(
        question="Duplicate-code probe A", interview_type="Pytest", track=None,
        difficulty="Medium", code="pytest-duplicate-code-probe",
    ))
    db_session.commit()

    db_session.add(Question(
        question="Duplicate-code probe B", interview_type="Pytest", track=None,
        difficulty="Medium", code="pytest-duplicate-code-probe",
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
