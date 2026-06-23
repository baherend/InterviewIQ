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
