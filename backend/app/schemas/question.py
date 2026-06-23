from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class QuestionCreate(BaseModel):
    question: str
    interview_type: str
    track: Optional[str] = None
    difficulty: str = "Medium"


class QuestionUpdate(BaseModel):
    question: Optional[str] = None
    interview_type: Optional[str] = None
    track: Optional[str] = None
    difficulty: Optional[str] = None


class QuestionResponse(BaseModel):
    id: int
    question: str
    interview_type: str
    track: Optional[str] = None
    difficulty: str
    created_at: datetime

    model_config = {"from_attributes": True}
