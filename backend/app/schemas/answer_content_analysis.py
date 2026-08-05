from pydantic import BaseModel
from datetime import datetime
from typing import Any, Dict, List, Optional


class AnswerContentAnalysisOut(BaseModel):
    """Real Answer Content Score result for one answer segment, produced
    by the existing, unmodified real NLP pipeline (claim decomposition
    via Groq, BGE-M3 retrieval, NLI, Precision/Coverage scoring) against
    this exact answer's Phase 3B transcript.

    `status` mirrors interview_iq.pipeline.evaluate_answer's own typed
    contract (SUCCESS/DECOMPOSITION_FAILED/NLI_FAILED/...), plus
    TRANSCRIPT_UNAVAILABLE/NO_REFERENCE_DOCUMENT for the two eligibility
    gates checked before the real pipeline is ever invoked. Only
    `status == "SUCCESS"` has real precision/coverage/answer_content_score
    values — every other status leaves them null ("Not available"), never
    a fabricated or zeroed score. `answer_content_score` is on the real
    pipeline's own [-100, 100] scale (a confident contradiction can push
    it negative), not clipped to 0.
    """

    status: Optional[str] = None
    error_message: Optional[str] = None
    question_reference_id: Optional[str] = None

    precision: Optional[float] = None
    coverage: Optional[float] = None
    harmonic_f: Optional[float] = None
    answer_content_score: Optional[float] = None

    claims: Optional[List[str]] = None
    claim_scores: Optional[List[Dict[str, Any]]] = None

    analyzed_at: Optional[datetime] = None

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class ContentSummaryOut(BaseModel):
    """Interview-level aggregate. Averages only valid (status == SUCCESS)
    Answer Content Scores — missing/ineligible/failed segments are never
    counted as zero. `available` is False (with `reason` set) when there
    are no valid scores to average yet.
    """

    available: bool
    average_answer_content_score: Optional[float] = None
    valid_segment_count: int = 0
    total_segment_count: int = 0
    reason: Optional[str] = None
