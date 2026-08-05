from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.answer_segment import AnswerSegment
from app.models.audio_analysis import AudioAnalysis
from app.models.interview import Interview
from app.models.result import Result
from app.models.user import User
from app.auth.jwt_handler import get_current_user
from app.schemas.audio_analysis import AudioSummaryOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _audio_summary_for_interview(db: Session, interview_id: int) -> dict:
    """Reads persisted AudioAnalysis rows only — never re-runs inference.
    Averages only valid (non-null) Vocal Delivery Scores; missing/invalid
    segments are never counted as zero. Legacy interviews (no segments at
    all) are reported honestly as unavailable, not as a zero score.
    """
    total_segments = (
        db.query(AnswerSegment).filter(AnswerSegment.interview_id == interview_id).count()
    )
    scores = (
        db.query(AudioAnalysis.vocal_delivery_score)
        .join(AnswerSegment, AnswerSegment.id == AudioAnalysis.answer_segment_id)
        .filter(AnswerSegment.interview_id == interview_id)
        .all()
    )
    valid_scores = [row[0] for row in scores if row[0] is not None]

    if valid_scores:
        return AudioSummaryOut(
            available=True,
            average_vocal_delivery_score=round(sum(valid_scores) / len(valid_scores), 2),
            valid_segment_count=len(valid_scores),
            total_segment_count=total_segments,
        ).model_dump(mode="json")
    if total_segments:
        return AudioSummaryOut(
            available=False,
            valid_segment_count=0,
            total_segment_count=total_segments,
            reason="No answer segments have a valid Vocal Delivery Score yet.",
        ).model_dump(mode="json")
    return AudioSummaryOut(
        available=False,
        valid_segment_count=0,
        total_segment_count=0,
        reason="Audio analysis not available for this historical interview.",
    ).model_dump(mode="json")


@router.get("/history")
def get_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    interviews = (
        db.query(Interview)
        .filter(Interview.user_id == current_user.id)
        .order_by(Interview.created_at.desc())
        .all()
    )

    history = []
    for interview in interviews:
        result = db.query(Result).filter(Result.interview_id == interview.id).first()
        history.append({
            "id": interview.id,
            "interview_type": interview.interview_type,
            "track": interview.track,
            "final_score": interview.final_score,
            "verdict": interview.verdict,
            "created_at": interview.created_at.isoformat() if interview.created_at else None,
            "vision_score": result.vision_score if result else None,
            "audio_score": result.audio_score if result else None,
            "nlp_score": result.nlp_score if result else None,
            "weakest_module": result.weakest_module if result else None,
            "audio_summary": _audio_summary_for_interview(db, interview.id),
        })
    return history


@router.get("/statistics")
def get_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    interviews = (
        db.query(Interview)
        .filter(Interview.user_id == current_user.id, Interview.final_score.isnot(None))
        .order_by(Interview.created_at)
        .all()
    )

    if not interviews:
        return {
            "total_interviews": 0,
            "average_score": 0,
            "best_score": 0,
            "verdicts": {},
            "score_trend": [],
            "module_averages": {"vision": 0, "audio": 0, "nlp": 0},
        }

    scores = [i.final_score for i in interviews]
    verdicts: dict = {}
    for i in interviews:
        if i.verdict:
            verdicts[i.verdict] = verdicts.get(i.verdict, 0) + 1

    results = [
        db.query(Result).filter(Result.interview_id == i.id).first()
        for i in interviews
    ]
    results = [r for r in results if r]

    vision_scores = [r.vision_score for r in results if r.vision_score is not None]
    audio_scores = [r.audio_score for r in results if r.audio_score is not None]
    nlp_scores = [r.nlp_score for r in results if r.nlp_score is not None]

    score_trend = [
        {
            "date": i.created_at.strftime("%b %d"),
            "score": round(i.final_score, 1),
            "interview_type": i.interview_type,
        }
        for i in interviews
    ]

    return {
        "total_interviews": len(interviews),
        "average_score": round(sum(scores) / len(scores), 1),
        "best_score": round(max(scores), 1),
        "verdicts": verdicts,
        "score_trend": score_trend,
        "module_averages": {
            "vision": round(sum(vision_scores) / len(vision_scores), 1) if vision_scores else 0,
            "audio": round(sum(audio_scores) / len(audio_scores), 1) if audio_scores else 0,
            "nlp": round(sum(nlp_scores) / len(nlp_scores), 1) if nlp_scores else 0,
        },
    }
