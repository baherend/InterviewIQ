from sqlalchemy import Column, Integer, Float, Boolean, String, Text, JSON, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class AudioAnalysis(Base):
    """Real local audio analysis output for one AnswerSegment (1:1).

    Every field here is either taken directly from the existing real
    audio implementation (InterviewIQ_AI/audio/audio_confidence.py and
    InterviewIQ_AI/audio/audio_emotion_package/audio_module.py) or is
    plain, honestly-labeled metadata about that run (model identifier,
    sample rate, duration, timestamp). No field is fabricated, and no
    field here is (or should be) fed by app/ai_modules/audio_module.py's
    `random.uniform`/`random.gauss` mock.

    Two independent categories, matching the real implementation exactly:

    Emotion classification (InterviewIQ_AI/audio/audio_emotion_package):
        emotion_label, emotion_probabilities, model_confidence.
        `model_confidence` is `max(softmax(logits))` — diagnostic model
        certainty only, not a candidate-performance metric, and it is not
        calibrated (`model_confidence_calibrated` is always False today —
        there is no temperature scaling, Platt/isotonic scaling, ECE, or
        Brier-score work anywhere in this codebase for this model).

    Vocal delivery (InterviewIQ_AI/audio/audio_confidence.py, a
    deterministic DSP heuristic — "no emotion inference is performed"):
        vocal_delivery_score and its four weighted sub-scores. The
        composite score requires a transcript (for speaking-rate scoring)
        which this phase does not produce (ASR/NLP integration is
        explicitly out of scope for Phase 3A) — so `vocal_delivery_score`
        and `speaking_rate_*` will legitimately be None/"Not available"
        for most segments in this phase, while pause/volume/continuity
        (which do not depend on a transcript) are still real computed
        values. See PHASE_3A_REAL_AUDIO_IMPLEMENTATION_REPORT.md.
    """

    __tablename__ = "audio_analyses"

    id = Column(Integer, primary_key=True, index=True)
    answer_segment_id = Column(
        Integer, ForeignKey("answer_segments.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    # --- Emotion classifier (InterviewIQ_AI/audio/audio_emotion_package) ---
    emotion_label = Column(String(50), nullable=True)
    emotion_probabilities = Column(JSON, nullable=True)
    model_confidence = Column(Float, nullable=True)
    model_confidence_calibrated = Column(Boolean, nullable=False, default=False)

    # --- Vocal delivery DSP (InterviewIQ_AI/audio/audio_confidence.py) ---
    vocal_delivery_score = Column(Float, nullable=True)
    speaking_rate_wpm = Column(Float, nullable=True)
    speaking_rate_score = Column(Float, nullable=True)
    pause_ratio = Column(Float, nullable=True)
    pause_control_score = Column(Float, nullable=True)
    volume_stability_score = Column(Float, nullable=True)
    speech_continuity_score = Column(Float, nullable=True)
    sufficient_evidence = Column(Boolean, nullable=True)
    failure_reason = Column(Text, nullable=True)

    # --- Metadata ---
    model_identifier = Column(String(200), nullable=True)
    model_version = Column(String(100), nullable=True)
    sample_rate_hz = Column(Integer, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    raw_diagnostic = Column(JSON, nullable=True)
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now())

    answer_segment = relationship("AnswerSegment", back_populates="audio_analysis")
