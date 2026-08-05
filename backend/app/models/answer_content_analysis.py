import enum

from sqlalchemy import Column, Integer, Float, String, Text, JSON, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class ContentAnalysisStatus(str, enum.Enum):
    """Mirrors interview_iq.pipeline.evaluate_answer's own typed `status`
    contract exactly (SUCCESS/ASR_*/DECOMPOSITION_FAILED/NLI_FAILED), plus
    two statuses for preconditions this table's own eligibility gate
    checks before ever invoking the real pipeline (see
    app/services/answer_content_service.py) — never a fabricated result
    for either case.
    """

    SUCCESS = "SUCCESS"
    ASR_NO_SPEECH = "ASR_NO_SPEECH"
    ASR_TOO_SHORT = "ASR_TOO_SHORT"
    DECOMPOSITION_FAILED = "DECOMPOSITION_FAILED"
    NLI_FAILED = "NLI_FAILED"
    # Gated before the real pipeline is ever invoked (no subprocess spawned):
    TRANSCRIPT_UNAVAILABLE = "TRANSCRIPT_UNAVAILABLE"
    NO_REFERENCE_DOCUMENT = "NO_REFERENCE_DOCUMENT"
    # The wrapper process itself crashed unexpectedly (distinct from a
    # typed pipeline failure above):
    EXECUTION_FAILED = "EXECUTION_FAILED"


class AnswerContentAnalysis(Base):
    """Real Answer Content Score for one AnswerSegment (1:1), produced by
    the existing, unmodified real NLP pipeline
    (interview_iq.pipeline.evaluate_answer: claim decomposition via Groq,
    BGE-M3 retrieval, NLI, Precision/Coverage/Harmonic-F scoring — see
    InterviewIQ_AI/nlp/interview-iq-fusion-handoff/src/interview_iq/
    pipeline.py). Reuses Phase 3B's already-persisted transcript for this
    exact segment — never re-runs ASR.

    `precision`/`coverage`/`harmonic_f`/`answer_content_score` are the
    exact fields the real pipeline returns (score is on
    interview_iq.pipeline's own [-100, 100] scale, not clipped to 0 —
    see scoring/metrics.py). `claims`/`claim_scores` hold the full
    transparency payload (every claim + its verdict), never summarized
    away. `status` is None-safe: a NULL row means content scoring has
    not run yet (segment still pending/processing), not an error.
    """

    __tablename__ = "answer_content_analyses"

    id = Column(Integer, primary_key=True, index=True)
    answer_segment_id = Column(
        Integer, ForeignKey("answer_segments.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    status = Column(String(30), nullable=True)
    error_message = Column(Text, nullable=True)
    question_reference_id = Column(String(20), nullable=True)

    precision = Column(Float, nullable=True)
    coverage = Column(Float, nullable=True)
    harmonic_f = Column(Float, nullable=True)
    answer_content_score = Column(Float, nullable=True)

    claims = Column(JSON, nullable=True)
    claim_scores = Column(JSON, nullable=True)

    model_identifiers = Column(JSON, nullable=True)
    raw_diagnostic = Column(JSON, nullable=True)
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now())

    answer_segment = relationship("AnswerSegment", back_populates="content_analysis")
