from typing import Dict, List

VISION_WEIGHT = 0.35
AUDIO_WEIGHT = 0.30
NLP_WEIGHT = 0.35

_RECOMMENDATIONS: Dict[str, List[str]] = {
    "Vision": [
        "Maintain steady eye contact with the camera — look directly at the lens, not the screen.",
        "Sit upright and keep your shoulders relaxed to project confidence.",
        "Practice in front of a mirror or record yourself to become comfortable with your expressions.",
        "Minimise background distractions and ensure good, even lighting on your face.",
        "Smile naturally when appropriate; it conveys warmth and enthusiasm to interviewers.",
    ],
    "Audio": [
        "Target a speaking pace of 120–150 words per minute — slow enough to be clear, fast enough to stay engaging.",
        "Pause deliberately between key points rather than rushing; silence signals confidence.",
        "Practice diaphragmatic breathing before the interview to calm nerves and improve vocal projection.",
        "Record yourself answering sample questions and critique your tone and pace.",
        "Use a quiet environment and a quality microphone to ensure clear audio.",
    ],
    "NLP": [
        "Structure every answer with the STAR method: Situation, Task, Action, Result.",
        "Prepare and rehearse two to three concrete stories that demonstrate key competencies.",
        "Reduce filler words (um, uh, like) by pausing silently instead of filling space.",
        "Focus answers on measurable outcomes — use numbers and percentages wherever possible.",
        "Read the job description carefully and weave relevant keywords naturally into your answers.",
    ],
}


def _get_verdict(score: float) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Pass"
    if score >= 50:
        return "Needs Improvement"
    return "Fail"


def fuse_scores(vision_score: float, audio_score: float, nlp_score: float) -> Dict:
    final_score = round(
        vision_score * VISION_WEIGHT + audio_score * AUDIO_WEIGHT + nlp_score * NLP_WEIGHT,
        2,
    )

    module_scores = {"Vision": vision_score, "Audio": audio_score, "NLP": nlp_score}
    weakest_module = min(module_scores, key=module_scores.get)

    recommendations = _RECOMMENDATIONS[weakest_module][:5]

    return {
        "final_score": final_score,
        "verdict": _get_verdict(final_score),
        "weakest_module": weakest_module,
        "recommendations": recommendations,
    }
