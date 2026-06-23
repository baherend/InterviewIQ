from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class InterviewStart(BaseModel):
    interview_type: str
    track: Optional[str] = None


class InterviewResponse(BaseModel):
    id: int
    user_id: int
    interview_type: str
    track: Optional[str] = None
    video_path: Optional[str] = None
    audio_path: Optional[str] = None
    final_score: Optional[float] = None
    verdict: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
