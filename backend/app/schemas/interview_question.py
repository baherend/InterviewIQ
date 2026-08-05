from pydantic import BaseModel
from typing import Optional


class InterviewQuestionOut(BaseModel):
    """One server-persisted, ordered question belonging to an interview.

    Returned once at interview start (POST /interviews/start-interview)
    and again, read-only, whenever the interview's report is loaded. The
    frontend never derives this list independently — it always renders
    exactly what the server persisted.
    """

    id: int
    sequence_index: int
    question_id: Optional[int] = None
    question_text: str
    difficulty: Optional[str] = None

    model_config = {"from_attributes": True}
