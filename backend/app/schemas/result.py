from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class ResultResponse(BaseModel):
    id: int
    interview_id: int
    vision_score: Optional[float] = None
    audio_score: Optional[float] = None
    nlp_score: Optional[float] = None
    emotion: Optional[str] = None
    eye_contact: Optional[float] = None
    wpm: Optional[float] = None
    pause_count: Optional[int] = None
    filler_count: Optional[int] = None
    transcript: Optional[str] = None
    weakest_module: Optional[str] = None
    recommendations: Optional[List[str]] = None

    model_config = {"from_attributes": True}
