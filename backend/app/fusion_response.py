"""Presentation-safe mapping for existing Fusion pipeline results."""
from typing import Any


def _safe_number(value: Any, *, allow_negative: bool = True) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    numeric = float(value)
    if not allow_negative and numeric < 0:
        return None
    return numeric


def clean_fusion_response(result: dict[str, Any], question_id: str) -> dict[str, Any]:
    required = {
        "status",
        "question_answer_match",
        "technical_evaluation",
        "visual_analysis",
        "vocal_analysis",
        "fusion_summary",
    }
    if not required.issubset(result):
        raise ValueError("Fusion result is missing required fields.")

    technical = result["technical_evaluation"]
    vision = result["visual_analysis"]
    audio = result["vocal_analysis"]
    summary = result["fusion_summary"]
    validity = result["question_answer_match"]
    transcript = ((technical.get("raw") or {}).get("asr") or {}).get(
        "normalized_transcript"
    )

    warnings = list(summary.get("limitations") or [])
    warnings.extend(
        f"{error.get('component', 'Fusion')}: {error.get('message', 'processing failed')}"
        for error in (result.get("errors") or [])
        if isinstance(error, dict)
    )
    warnings = list(dict.fromkeys(str(item) for item in warnings if item))

    return {
        "status": result["status"],
        "question_id": question_id,
        "transcript": transcript,
        "question_answer_validity": {
            "valid": validity.get("valid"),
            "reason": validity.get("reason"),
        },
        "vision": {
            "status": vision.get("status"),
            "predicted_class": vision.get("predicted_emotion"),
            "model_confidence": _safe_number(
                (vision.get("raw") or {}).get("confidence")
            ),
            "sufficient_evidence": vision.get("sufficient_evidence"),
        },
        "audio": {
            "status": audio.get("status"),
            "dominant_emotion": audio.get("dominant_emotion"),
            "model_confidence": _safe_number(audio.get("model_confidence")),
        },
        "nlp": {
            "status": technical.get("status"),
            "technical_score": _safe_number(
                technical.get("score"), allow_negative=False
            ),
            "precision": _safe_number(
                technical.get("precision"), allow_negative=False
            ),
            "coverage": _safe_number(
                technical.get("coverage"), allow_negative=False
            ),
            "raw_values_withheld": any(
                isinstance(technical.get(key), (int, float))
                and technical.get(key) < 0
                for key in ("score", "precision", "coverage")
            ),
        },
        "fusion_summary": {
            "final_technical_score": _safe_number(
                summary.get("final_technical_score"), allow_negative=False
            ),
            "technical_interpretation": summary.get("technical_interpretation"),
        },
        "warnings": warnings,
    }
