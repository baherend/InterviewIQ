from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class AnswerSegmentResponse(BaseModel):
    """Returned by POST /interviews/{interview_id}/segments. Never exposes
    the server-side filesystem storage path.
    """

    id: int
    interview_id: int
    interview_question_id: int
    question_id: Optional[int] = None
    sequence_index: int
    upload_status: str
    processing_status: str
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SegmentStatusItem(BaseModel):
    id: int
    interview_question_id: int
    sequence_index: int
    upload_status: str
    processing_status: str
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None


class InterviewProcessingStatusResponse(BaseModel):
    """Polled by Processing.jsx until `all_terminal` is true. Terminal
    processing_status values: completed, partial, failed,
    insufficient_evidence (i.e. anything other than pending/processing).
    """

    interview_id: int
    segments: List[SegmentStatusItem]
    all_terminal: bool


class ProcessAudioResponse(BaseModel):
    interview_id: int
    segments_queued: List[int]
    status: str
