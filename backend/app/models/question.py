from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.database import Base


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    question = Column(String(1000), nullable=False)
    interview_type = Column(String(50), nullable=False)
    track = Column(String(100), nullable=True)
    difficulty = Column(String(20), nullable=False, default="Medium")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Phase 3C: the NLP module's reference-document ID for this question
    # (InterviewIQ_AI/nlp/interview-iq-fusion-handoff/data/refdocs/
    # reference_docs_250_FINAL_v1.json, e.g. "SE-028") — NULL for every
    # question with no matching reference document, which Answer Content
    # Score treats as "not available", never a guessed/fuzzy match.
    nlp_reference_id = Column(String(20), nullable=True)
