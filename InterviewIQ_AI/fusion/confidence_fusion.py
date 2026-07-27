"""Fuse candidate delivery scores without technical/model-confidence inputs."""
from __future__ import annotations

from typing import Any

from confidence_config import FUSION_CONFIDENCE_CONFIG, FusionConfidenceConfig


def fuse_confidence(
    vocal_confidence_score: float | None,
    visual_confidence_score: float | None,
    *,
    vocal_sufficient_evidence: bool = True,
    visual_sufficient_evidence: bool = True,
    config: FusionConfidenceConfig = FUSION_CONFIDENCE_CONFIG,
    warnings: list[str] | None = None,
    **_ignored: Any,
) -> dict[str, Any]:
    notes = list(warnings or [])
    available = {
        "vocal": vocal_confidence_score
        if vocal_sufficient_evidence and isinstance(vocal_confidence_score, (int, float))
        else None,
        "visual": visual_confidence_score
        if visual_sufficient_evidence and isinstance(visual_confidence_score, (int, float))
        else None,
    }
    if isinstance(visual_confidence_score, (int, float)) and not visual_sufficient_evidence:
        notes.append("Visual confidence was excluded because visual evidence was insufficient.")
    if isinstance(vocal_confidence_score, (int, float)) and not vocal_sufficient_evidence:
        notes.append("Vocal confidence was excluded because vocal evidence was insufficient.")
    present = [name for name, score in available.items() if score is not None]
    if not present:
        final, status = None, "insufficient"
    else:
        denominator = sum(config.weights[name] for name in present)
        final = sum(config.weights[name] * available[name] for name in present) / denominator
        status = "complete" if len(present) == 2 else "partial"
        if len(present) == 1:
            excluded = "visual" if present[0] == "vocal" else "vocal"
            notes.append(f"Only {present[0]} confidence evidence was available; {excluded} was excluded.")
    effective = {
        name: (config.weights[name] / sum(config.weights[item] for item in present))
        if name in present else 0.0
        for name in config.weights
    } if present else {"vocal": 0.0, "visual": 0.0}
    return {
        "vocal_confidence_score": available["vocal"],
        "visual_confidence_score": available["visual"],
        "final_confidence_score": round(final, 3) if final is not None else None,
        "confidence_evidence_status": status,
        "nominal_weights": dict(config.weights),
        "effective_weights": effective,
        "weights": {
            "nominal": dict(config.weights),
            "effective": effective,
        },
        "warnings": list(dict.fromkeys(notes)),
    }
