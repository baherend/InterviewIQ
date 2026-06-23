import os
import uuid
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.interview import Interview
from app.models.result import Result
from app.schemas.interview import InterviewStart, InterviewResponse
from app.auth.jwt_handler import get_current_user
from app.ai_modules.vision_module import run_vision
from app.ai_modules.audio_module import run_audio
from app.ai_modules.nlp_module import run_nlp
from app.ai_modules.fusion_engine import fuse_scores
from app.config import settings

router = APIRouter(prefix="/interviews", tags=["interviews"])


@router.post("/start-interview", response_model=InterviewResponse, status_code=201)
def start_interview(
    data: InterviewStart,
    db: Session = Depends(get_db),
    current_user: int = Depends(get_current_user),
):
    interview = Interview(
        user_id=current_user,
        interview_type=data.interview_type,
        track=data.track,
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return interview


@router.post("/upload-video/{interview_id}")
async def upload_video(
    interview_id: int,
    video: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: int = Depends(get_current_user),
):
    interview = db.query(Interview).filter(
        Interview.id == interview_id, Interview.user_id == current_user
    ).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(video.filename or "interview.webm")[1] or ".webm"
    filename = f"{uuid.uuid4()}{ext}"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)

    async with aiofiles.open(filepath, "wb") as f:
        await f.write(await video.read())

    interview.video_path = filepath
    interview.audio_path = filepath
    db.commit()

    return {"message": "Video uploaded successfully", "interview_id": interview_id}


@router.post("/analyze/{interview_id}")
def analyze_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: int = Depends(get_current_user),
):
    interview = db.query(Interview).filter(
        Interview.id == interview_id, Interview.user_id == current_user
    ).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    existing = db.query(Result).filter(Result.interview_id == interview_id).first()
    if existing:
        return {"interview_id": interview_id, "status": "already_analyzed"}

    video_path = interview.video_path or ""
    audio_path = interview.audio_path or video_path

    vision_result = run_vision(video_path)
    audio_result = run_audio(audio_path)
    nlp_result = run_nlp(audio_path)

    fusion = fuse_scores(
        vision_result["vision_score"],
        audio_result["audio_score"],
        nlp_result["nlp_score"],
    )

    interview.final_score = fusion["final_score"]
    interview.verdict = fusion["verdict"]

    result = Result(
        interview_id=interview_id,
        vision_score=vision_result["vision_score"],
        audio_score=audio_result["audio_score"],
        nlp_score=nlp_result["nlp_score"],
        emotion=vision_result.get("emotion", "Neutral"),
        eye_contact=vision_result.get("eye_contact", 0.0),
        wpm=audio_result.get("wpm", 0.0),
        pause_count=audio_result.get("pause_count", 0),
        filler_count=nlp_result.get("filler_count", 0),
        transcript=nlp_result.get("transcript", ""),
        weakest_module=fusion["weakest_module"],
        recommendations=fusion["recommendations"],
    )
    db.add(result)
    db.commit()

    return {"interview_id": interview_id, "status": "analyzed"}


@router.get("/report/{interview_id}")
def get_report(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: int = Depends(get_current_user),
):
    interview = db.query(Interview).filter(
        Interview.id == interview_id, Interview.user_id == current_user
    ).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    result = db.query(Result).filter(Result.interview_id == interview_id).first()

    return {
        "interview": {
            "id": interview.id,
            "interview_type": interview.interview_type,
            "track": interview.track,
            "final_score": interview.final_score,
            "verdict": interview.verdict,
            "created_at": interview.created_at.isoformat() if interview.created_at else None,
        },
        "result": {
            "vision_score": result.vision_score if result else None,
            "audio_score": result.audio_score if result else None,
            "nlp_score": result.nlp_score if result else None,
            "emotion": result.emotion if result else None,
            "eye_contact": result.eye_contact if result else None,
            "wpm": result.wpm if result else None,
            "pause_count": result.pause_count if result else None,
            "filler_count": result.filler_count if result else None,
            "transcript": result.transcript if result else None,
            "weakest_module": result.weakest_module if result else None,
            "recommendations": result.recommendations if result else [],
        },
    }
