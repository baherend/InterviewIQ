from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict


class AudioAnalysisOut(BaseModel):
    """Real local audio analysis result for one answer segment.

    `model_confidence` is diagnostic model certainty only (max softmax
    probability of the emotion classifier) — it is not calibrated
    (`model_confidence_calibrated` is always False) and it is not a
    candidate-performance score.

    `vocal_delivery_score` is an experimental, deterministic DSP-based
    delivery indicator, not a scientifically validated psychological
    confidence score. It requires a transcript to score speaking rate;
    since ASR/NLP is out of scope for this phase, it and
    `speaking_rate_*` will commonly be null ("Not available") while the
    transcript-independent sub-scores (pause/volume/continuity) are real
    computed values.
    """

    emotion_label: Optional[str] = None
    emotion_probabilities: Optional[Dict[str, float]] = None
    model_confidence: Optional[float] = None
    model_confidence_calibrated: bool = False

    vocal_delivery_score: Optional[float] = None
    speaking_rate_wpm: Optional[float] = None
    speaking_rate_score: Optional[float] = None
    pause_ratio: Optional[float] = None
    pause_control_score: Optional[float] = None
    volume_stability_score: Optional[float] = None
    speech_continuity_score: Optional[float] = None
    sufficient_evidence: Optional[bool] = None
    failure_reason: Optional[str] = None

    model_identifier: Optional[str] = None
    model_version: Optional[str] = None
    sample_rate_hz: Optional[int] = None
    duration_seconds: Optional[float] = None
    analyzed_at: Optional[datetime] = None

    # `model_*` field names are legitimate domain fields here (the ML
    # model's confidence/identifier/version), not an accidental clash with
    # Pydantic's own reserved `model_` method namespace — silence the
    # cosmetic warning rather than renaming fields away from their real
    # meaning.
    model_config = {"from_attributes": True, "protected_namespaces": ()}


class AudioSummaryOut(BaseModel):
    """Interview-level aggregate. Averages only valid (non-null) vocal
    delivery scores — missing/invalid segments are never counted as zero.
    `available` is False (with `reason` set) when there are no valid
    scores to average yet.
    """

    available: bool
    average_vocal_delivery_score: Optional[float] = None
    valid_segment_count: int = 0
    total_segment_count: int = 0
    reason: Optional[str] = None
