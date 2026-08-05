from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class InterviewQuestion(Base):
    """The server-persisted, ordered question sequence for one interview.

    Created once, at interview start, from the same eligible-question
    lookup the product already used (see `questions.py`). The server is
    the source of truth for `question_id` and `sequence_index` from this
    point on — the frontend only ever renders what is persisted here, it
    never re-derives or re-requests the sequence independently.

    `question_text`/`difficulty` are snapshotted at creation time (not
    re-read from `Question` on every access) so that a later edit or hard
    delete of the underlying `Question` row cannot retroactively change
    what this interview actually asked.
    """

    __tablename__ = "interview_questions"
    __table_args__ = (
        UniqueConstraint("interview_id", "sequence_index", name="uq_interview_questions_interview_sequence"),
        UniqueConstraint("interview_id", "question_id", name="uq_interview_questions_interview_question"),
        CheckConstraint("sequence_index >= 0", name="ck_interview_questions_sequence_index_non_negative"),
    )

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True)
    # SET NULL (not CASCADE/RESTRICT): the question bank allows hard
    # delete (see questions.py). A later delete of the source Question
    # must not retroactively delete interview history — the snapshotted
    # `question_text` below keeps the record meaningful either way.
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="SET NULL"), nullable=True, index=True)
    sequence_index = Column(Integer, nullable=False)
    question_text = Column(String(1000), nullable=False)
    difficulty = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    interview = relationship("Interview", back_populates="interview_questions")
    question = relationship("Question")
    answer_segments = relationship(
        "AnswerSegment", back_populates="interview_question", cascade="all, delete-orphan"
    )
