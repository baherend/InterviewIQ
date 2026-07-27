"""Result mapping and semantic safeguards. Raw dictionaries are never altered."""
from __future__ import annotations

import re
from typing import Any

_STOP = {"the", "a", "an", "is", "are", "what", "how", "why", "and", "or", "to", "of",
         "في", "من", "ما", "هو", "هي", "على", "عن", "و", "أو", "كيف", "ماهو", "ماهي"}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[\w+#.-]+", text.lower(), re.UNICODE)
            if len(t) > 1 and t not in _STOP}


def assess_question_answer_match(question: str, transcript: str | None) -> dict[str, Any]:
    if not transcript or not transcript.strip():
        return {"valid": None, "reason": "No usable NLP transcript was produced."}
    q, t = _tokens(question), _tokens(transcript)
    if not q:
        return {"valid": None, "reason": "Question text has no comparable terms."}
    overlap = sorted(q & t)
    ratio = len(overlap) / len(q)
    if ratio >= 0.18 and overlap:
        return {"valid": True, "reason": f"Transcript overlaps the selected question on: {', '.join(overlap[:8])}."}
    if ratio < 0.08:
        return {"valid": False, "reason": "Transcript has no meaningful lexical overlap with the selected question; technical score is withheld."}
    return {"valid": None, "reason": "Automated comparison is inconclusive; human review is required before using the technical score."}


def mapped_vision(raw: dict[str, Any] | None, error: dict | None) -> dict[str, Any]:
    raw = raw or {}
    ok = raw.get("status") in {"ok", "insufficient_evidence"}
    return {"status": "success" if ok else "failed", "sufficient_evidence": raw.get("sufficient_evidence"),
            "predicted_emotion": raw.get("predicted_emotion"),
            "behavioral_confidence_score": raw.get("visual_behavioral_confidence_score"),
            "raw": raw, **({"error": error} if error else {})}


def mapped_audio(raw: dict[str, Any] | None, error: dict | None) -> dict[str, Any]:
    raw = raw or {}
    return {"status": "success" if raw and not error else "failed",
            "dominant_emotion": raw.get("dominant_emotion"),
            "model_confidence": raw.get("confidence_score"),
            "probabilities": raw.get("emotion_scores", {}), "raw": raw,
            **({"error": error} if error else {})}


def mapped_nlp(raw: dict[str, Any] | None, error: dict | None) -> dict[str, Any]:
    raw = raw or {}
    ok = raw.get("status") == "SUCCESS"
    return {"status": "success" if ok else "failed", "score": raw.get("score"),
            "precision": raw.get("precision"), "coverage": raw.get("coverage"),
            "harmonic_f": raw.get("harmonic_f"), "claims": raw.get("claims") or [],
            "claim_scores": raw.get("claim_scores") or [], "raw": raw,
            **({"error": error} if error else {})}

