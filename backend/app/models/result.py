from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Result(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, unique=True)
    vision_score = Column(Float, nullable=True)
    audio_score = Column(Float, nullable=True)
    nlp_score = Column(Float, nullable=True)
    emotion = Column(String(50), nullable=True)
    eye_contact = Column(Float, nullable=True)
    wpm = Column(Float, nullable=True)
    pause_count = Column(Integer, nullable=True)
    filler_count = Column(Integer, nullable=True)
    transcript = Column(Text, nullable=True)
    weakest_module = Column(String(50), nullable=True)
    recommendations = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    interview = relationship("Interview", back_populates="result")
