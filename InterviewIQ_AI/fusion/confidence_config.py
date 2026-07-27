"""Experimental delivery-confidence defaults requiring human validation."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AudioConfidenceConfig:
    frame_ms: float = 25.0
    hop_ms: float = 10.0
    silence_relative_rms: float = 0.12
    silence_absolute_rms: float = 0.008
    minimum_duration_seconds: float = 1.0
    minimum_words: int = 1
    ideal_wpm_low: float = 100.0
    ideal_wpm_high: float = 160.0
    acceptable_wpm_low: float = 70.0
    acceptable_wpm_high: float = 190.0
    ideal_pause_ratio_low: float = 0.08
    ideal_pause_ratio_high: float = 0.35
    maximum_pause_ratio: float = 0.70
    volume_cv_good: float = 0.25
    volume_cv_poor: float = 1.0
    continuity_target_segment_seconds: float = 1.0
    weights: dict = field(default_factory=lambda: {
        "speaking_rate": 0.30, "pause_control": 0.30,
        "volume_stability": 0.25, "speech_continuity": 0.15,
    })


@dataclass(frozen=True)
class FusionConfidenceConfig:
    weights: dict = field(default_factory=lambda: {"vocal": 0.60, "visual": 0.40})


AUDIO_CONFIDENCE_CONFIG = AudioConfidenceConfig()
FUSION_CONFIDENCE_CONFIG = FusionConfidenceConfig()
