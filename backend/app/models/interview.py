from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    interview_type = Column(String(50), nullable=False)
    track = Column(String(100), nullable=True)
    video_path = Column(String(500), nullable=True)
    audio_path = Column(String(500), nullable=True)
    final_score = Column(Float, nullable=True)
    verdict = Column(String(50), nullable=True)
    # Set once, by POST /interviews/{id}/process-audio, when the candidate
    # has finished recording every question. Segment uploads are rejected
    # after this is set, preventing late/duplicate answers once processing
    # has begun. Null for legacy interviews and for interviews still in
    # progress.
    recording_completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="interviews")
    result = relationship("Result", back_populates="interview", uselist=False, cascade="all, delete-orphan")
    interview_questions = relationship(
        "InterviewQuestion",
        back_populates="interview",
        cascade="all, delete-orphan",
        order_by="InterviewQuestion.sequence_index",
    )
    answer_segments = relationship(
        "AnswerSegment", back_populates="interview", cascade="all, delete-orphan"
    )
