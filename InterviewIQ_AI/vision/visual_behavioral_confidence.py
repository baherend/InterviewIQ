"""Production Visual Behavioral Confidence extracted from the reference notebook.

The defaults and formulas are an experimental baseline requiring later human
validation. This module contains no notebook, plotting, CSV, or Kaggle runtime
behavior. Inputs are temporal-window probability records produced by the
existing Vision model runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

EMOTION_CLASSES = (
    "neutral", "calm", "happy", "sad",
    "angry", "fearful", "disgust", "surprised",
)


@dataclass(frozen=True)
class VisualConfidenceConfig:
    """Experimental baseline defaults requiring later human validation."""

    window_seconds: float = 4.0
    stride_seconds: float = 4.0
    minimum_last_window_seconds: float = 1.5
    negative_affect_threshold: float = 0.25
    sad_weight: float = 1.0
    disgust_weight: float = 1.0
    fearful_weight: float = 1.0
    angry_weight: float = 1.0
    recovery_horizon_windows: int = 2
    recovery_minimum_signal: float = 0.40
    recovery_minimum_gain: float = 0.10
    minimum_windows_for_decision: int = 3
    minimum_face_detection_ratio: float = 0.60
    calm_weight: float = 1.0
    neutral_weight: float = 1.0
    happy_weight: float = 1.0
    comfort_weight: float = 0.35
    stability_weight: float = 0.25
    recovery_weight: float = 0.20
    negative_affect_weight: float = 0.20
    confidence_interval_max_margin: float = 15.0

    def validate(self) -> None:
        if self.window_seconds <= 0:
            raise ValueError("window_seconds must be positive.")
        if self.stride_seconds <= 0:
            raise ValueError("stride_seconds must be positive.")
        if any(weight < 0 for weight in (
            self.sad_weight, self.disgust_weight,
            self.fearful_weight, self.angry_weight,
        )):
            raise ValueError("Emotion severity weights must be non-negative.")
        if any(weight < 0 for weight in (
            self.calm_weight, self.neutral_weight, self.happy_weight,
        )):
            raise ValueError("Comfort emotion weights must be non-negative.")
        if abs(sum((
            self.comfort_weight, self.stability_weight,
            self.recovery_weight, self.negative_affect_weight,
        )) - 1.0) > 1e-6:
            raise ValueError("Base-score weights must sum to 1.0.")
        if self.confidence_interval_max_margin < 0:
            raise ValueError("confidence_interval_max_margin must be non-negative.")
        if self.minimum_windows_for_decision <= 0:
            raise ValueError("minimum_windows_for_decision must be positive.")
        if not 0 <= self.minimum_face_detection_ratio <= 1:
            raise ValueError("minimum_face_detection_ratio must be between 0 and 1.")


VISUAL_CONFIDENCE_CONFIG = VisualConfidenceConfig()
VISUAL_CONFIDENCE_CONFIG.validate()


def _records(windows: Any) -> list[dict[str, Any]]:
    if hasattr(windows, "to_dict"):
        return list(windows.to_dict(orient="records"))
    return [dict(window) for window in windows]


def _values(windows: Sequence[Mapping[str, Any]], key: str) -> np.ndarray:
    return np.asarray([float(window[key]) for window in windows], dtype=np.float64)


def calculate_comfort_signal(
    windows: Sequence[Mapping[str, Any]],
    config: VisualConfidenceConfig = VISUAL_CONFIDENCE_CONFIG,
) -> dict[str, float]:
    rows = _records(windows)
    mean_calm = float(_values(rows, "prob_calm").mean())
    mean_neutral = float(_values(rows, "prob_neutral").mean())
    mean_happy = float(_values(rows, "prob_happy").mean())
    comfort = float(np.clip(
        config.calm_weight * mean_calm
        + config.neutral_weight * mean_neutral
        + config.happy_weight * mean_happy, 0.0, 1.0,
    ))
    return {
        "comfort_signal": comfort,
        "mean_calm_probability": mean_calm,
        "mean_neutral_probability": mean_neutral,
        "mean_happy_probability": mean_happy,
    }


def calculate_emotion_stability(
    windows: Sequence[Mapping[str, Any]],
    classes: Sequence[str] = EMOTION_CLASSES,
) -> dict[str, float]:
    rows = _records(windows)
    if len(rows) <= 1:
        return {"emotion_stability": 1.0, "mean_transition_distance": 0.0}
    matrix = np.asarray(
        [[float(row[f"prob_{emotion}"]) for emotion in classes] for row in rows],
        dtype=np.float64,
    )
    distances = 0.5 * np.abs(matrix[1:] - matrix[:-1]).sum(axis=1)
    mean_distance = float(distances.mean())
    return {
        "emotion_stability": float(np.clip(1.0 - mean_distance, 0.0, 1.0)),
        "mean_transition_distance": mean_distance,
    }


def calculate_negative_affect(
    windows: Sequence[Mapping[str, Any]],
    config: VisualConfidenceConfig = VISUAL_CONFIDENCE_CONFIG,
) -> np.ndarray:
    rows = _records(windows)
    return np.clip(
        config.sad_weight * _values(rows, "prob_sad")
        + config.disgust_weight * _values(rows, "prob_disgust")
        + config.fearful_weight * _values(rows, "prob_fearful")
        + config.angry_weight * _values(rows, "prob_angry"),
        0.0, 1.0,
    )


def _longest_true_streak(values: Sequence[bool]) -> int:
    longest = current = 0
    for value in values:
        current = current + 1 if bool(value) else 0
        longest = max(longest, current)
    return longest


def calculate_negative_affect_persistence(
    windows: Sequence[Mapping[str, Any]],
    config: VisualConfidenceConfig = VISUAL_CONFIDENCE_CONFIG,
) -> dict[str, float | int]:
    rows = _records(windows)
    negative = calculate_negative_affect(rows, config)
    high = negative >= config.negative_affect_threshold
    mean_negative = float(negative.mean())
    high_ratio = float(high.mean())
    streak = _longest_true_streak(high)
    streak_ratio = float(streak / max(len(rows), 1))
    persistence = float(np.clip(
        0.50 * mean_negative + 0.25 * high_ratio + 0.25 * streak_ratio,
        0.0, 1.0,
    ))
    return {
        "negative_affect_persistence": persistence,
        "mean_negative_affect_probability": mean_negative,
        "high_negative_affect_window_ratio": high_ratio,
        "longest_negative_affect_streak_windows": streak,
        "longest_negative_affect_streak_ratio": streak_ratio,
    }


def calculate_calm_recovery(
    windows: Sequence[Mapping[str, Any]],
    config: VisualConfidenceConfig = VISUAL_CONFIDENCE_CONFIG,
) -> dict[str, Any]:
    rows = _records(windows)
    negative = calculate_negative_affect(rows, config)
    calm_signal = _values(rows, "prob_calm") + 0.5 * _values(rows, "prob_neutral")
    high = negative >= config.negative_affect_threshold
    starts = [
        index for index, value in enumerate(high)
        if bool(value) and (index == 0 or not bool(high[index - 1]))
    ]
    if not starts:
        return {
            "calm_recovery": 1.0, "negative_affect_episode_count": 0,
            "recovered_episode_count": 0, "recovery_events": [],
            "recovery_note": "No negative-affect episode required recovery.",
        }
    events: list[dict[str, Any]] = []
    recovered_count = 0
    for start in starts:
        recovered_at = None
        end = min(len(rows), start + 1 + config.recovery_horizon_windows)
        for candidate in range(start + 1, end):
            if (
                calm_signal[candidate] >= config.recovery_minimum_signal
                and calm_signal[candidate] - calm_signal[start]
                >= config.recovery_minimum_gain
                and negative[candidate] < negative[start]
            ):
                recovered_at = candidate
                recovered_count += 1
                break
        events.append({
            "negative_affect_start_window": int(start),
            "recovered": recovered_at is not None,
            "recovery_window": int(recovered_at) if recovered_at is not None else None,
        })
    return {
        "calm_recovery": float(recovered_count / len(starts)),
        "negative_affect_episode_count": len(starts),
        "recovered_episode_count": recovered_count,
        "recovery_events": events,
        "recovery_note": None,
    }


def calculate_visual_reliability(
    windows: Sequence[Mapping[str, Any]],
    config: VisualConfidenceConfig = VISUAL_CONFIDENCE_CONFIG,
) -> dict[str, float]:
    rows = _records(windows)
    face_ratio = float(_values(rows, "face_detection_ratio").mean())
    coverage = float(min(len(rows) / config.minimum_windows_for_decision, 1.0))
    return {
        "visual_reliability": float(np.clip(0.80 * face_ratio + 0.20 * coverage, 0.0, 1.0)),
        "mean_face_detection_ratio": face_ratio,
        "window_coverage": coverage,
    }


def visual_confidence_level(score: float, sufficient_evidence: bool) -> str:
    if not sufficient_evidence:
        return "insufficient_evidence"
    if score >= 75.0:
        return "high"
    if score >= 50.0:
        return "moderate"
    return "low"


def calculate_visual_confidence_summary(
    windows: Sequence[Mapping[str, Any]],
    *,
    config: VisualConfidenceConfig = VISUAL_CONFIDENCE_CONFIG,
    classes: Sequence[str] = EMOTION_CLASSES,
) -> dict[str, Any]:
    config.validate()
    rows = _records(windows)
    if not rows:
        raise ValueError("At least one temporal window is required.")
    comfort = calculate_comfort_signal(rows, config)
    stability = calculate_emotion_stability(rows, classes)
    negative = calculate_negative_affect_persistence(rows, config)
    recovery = calculate_calm_recovery(rows, config)
    reliability = calculate_visual_reliability(rows, config)
    base = (
        config.comfort_weight * comfort["comfort_signal"]
        + config.stability_weight * stability["emotion_stability"]
        + config.recovery_weight * recovery["calm_recovery"]
        + config.negative_affect_weight
        * (1.0 - negative["negative_affect_persistence"])
    )
    score = float(np.clip(base * 100.0, 0.0, 100.0))
    margin = float(
        (1.0 - reliability["visual_reliability"])
        * config.confidence_interval_max_margin
    )
    enough_windows = len(rows) >= config.minimum_windows_for_decision
    enough_faces = (
        reliability["mean_face_detection_ratio"]
        >= config.minimum_face_detection_ratio
    )
    sufficient = bool(enough_windows and enough_faces)
    warnings: list[str] = []
    if not enough_windows:
        warnings.append(
            f"Visual evidence has {len(rows)} temporal window(s); "
            f"at least {config.minimum_windows_for_decision} are required."
        )
    if not enough_faces:
        warnings.append(
            "Mean face detection ratio is below the visual evidence threshold."
        )
    return {
        "visual_behavioral_confidence_score": score,
        "visual_confidence_score": score,
        "visual_confidence_level": visual_confidence_level(score, sufficient),
        "sufficient_evidence": sufficient,
        "number_of_windows": len(rows),
        "confidence_margin": margin,
        "score_range": {
            "low": float(np.clip(score - margin, 0.0, 100.0)),
            "high": float(np.clip(score + margin, 0.0, 100.0)),
        },
        "evidence_checks": {
            "enough_windows": bool(enough_windows),
            "enough_faces": bool(enough_faces),
        },
        "metrics": {**comfort, **stability, **negative, **recovery, **reliability},
        "formula_weights": {
            "comfort_signal": config.comfort_weight,
            "emotion_stability": config.stability_weight,
            "calm_recovery": config.recovery_weight,
            "low_negative_affect": config.negative_affect_weight,
        },
        "interpretation": (
            "Observable temporal behavioral indicators; not a personality "
            "judgment and not validated for hiring decisions."
        ),
        "warnings": warnings,
    }


def analyze_visual_behavioral_confidence(
    video_path: str,
    *,
    config: VisualConfidenceConfig | None = None,
    vision_runtime: object | None = None,
) -> dict[str, Any]:
    """Run existing Vision inference once, then analyze its temporal outputs."""
    cfg = config or VISUAL_CONFIDENCE_CONFIG
    cfg.validate()
    if vision_runtime is None:
        import vision_module as vision_runtime  # type: ignore[no-redef]
    path = Path(video_path)
    if not path.is_file():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    warnings: list[str] = []
    device = vision_runtime._select_device(warnings)
    model, classes, checkpoint_metadata, device = vision_runtime.get_model(
        checkpoint_path=vision_runtime.DEFAULT_CHECKPOINT_PATH,
        device=device,
        warnings_out=warnings,
    )
    windows = vision_runtime.analyze_emotion_windows(
        video_path=str(path), model=model, classes=classes, device=device,
        analysis_config=cfg,
    )
    summary = calculate_visual_confidence_summary(
        windows, config=cfg, classes=classes,
    )
    summary["windows"] = _records(windows)
    summary["warnings"] = list(dict.fromkeys(warnings + summary["warnings"]))
    summary["checkpoint_metadata"] = checkpoint_metadata
    return summary
