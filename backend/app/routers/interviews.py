import asyncio
import json
import os
import re
import subprocess
import sys
import uuid
import aiofiles
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.interview import Interview
from app.models.result import Result
from app.models.user import User
from app.schemas.interview import InterviewStart, InterviewResponse
from app.auth.jwt_handler import get_current_user
from app.ai_modules.vision_module import run_vision
from app.ai_modules.audio_module import run_audio
from app.ai_modules.nlp_module import run_nlp
from app.ai_modules.fusion_engine import fuse_scores
from app.config import settings
from app.fusion_response import clean_fusion_response

router = APIRouter(prefix="/interviews", tags=["interviews"])

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".mkv", ".avi"}
QUESTION_ID_PATTERN = re.compile(r"^[A-Z]{2}-\d{3}$")


def _load_fusion_questions() -> list[dict[str, str]]:
    try:
        payload = json.loads(settings.fusion_reference_json.read_text(encoding="utf-8"))
        documents = payload["documents"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=503, detail="Fusion question reference data is unavailable."
        ) from exc

    questions = [
        {
            "question_id": item["question_id"],
            "question": item["question"],
            "track": item.get("track", ""),
        }
        for item in documents
        if isinstance(item, dict) and item.get("question_id") and item.get("question")
    ]
    if not questions:
        raise HTTPException(
            status_code=503, detail="Fusion question reference data contains no questions."
        )
    return questions


def _execute_fusion(video_path: Path, question_id: str, output_path: Path) -> dict:
    command = [
        sys.executable,
        str(settings.fusion_runner),
        "--video",
        str(video_path),
        "--question-id",
        question_id,
        "--output",
        str(output_path),
    ]
    process_environment = os.environ.copy()
    process_environment["PYTHONIOENCODING"] = "utf-8"
    try:
        completed = subprocess.run(
            command,
            cwd=str(settings.fusion_dir),
            env=process_environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=settings.FUSION_PROCESS_TIMEOUT_SECONDS,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=504,
            detail="Fusion processing timed out. The uploaded video and any partial output were kept for debugging.",
        ) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=503, detail="The local Fusion process could not be started."
        ) from exc

    log_path = output_path.with_suffix(".log")
    try:
        log_path.write_text(
            "=== stdout ===\n"
            + completed.stdout
            + "\n=== stderr ===\n"
            + completed.stderr,
            encoding="utf-8",
        )
    except OSError:
        # The JSON result remains authoritative. Failure to write the
        # optional diagnostic sidecar must not discard a valid model result.
        pass

    if not output_path.is_file():
        detail = "Fusion did not produce a result file."
        if completed.returncode != 0:
            detail = "Fusion processing failed before producing a result."
        raise HTTPException(status_code=502, detail=detail)

    try:
        result = json.loads(output_path.read_text(encoding="utf-8"))
        if not isinstance(result, dict):
            raise ValueError("Fusion result must be a JSON object.")
        clean = clean_fusion_response(result, question_id)
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Fusion produced an invalid result. The result file was kept for debugging.",
        ) from exc

    if completed.returncode != 0 and clean["status"] == "failed":
        raise HTTPException(
            status_code=502,
            detail="All Fusion components failed. The result file was kept for debugging.",
        )
    return clean


@router.get("/analysis-questions")
def get_fusion_analysis_questions():
    """Questions supported by the existing Fusion reference dataset."""
    return {"questions": _load_fusion_questions()}


@router.post("/analyze")
async def analyze_uploaded_video(
    video: UploadFile = File(...),
    question_id: str = Form(...),
):
    """Run the existing isolated Fusion pipeline against one uploaded answer."""
    normalized_question_id = question_id.strip().upper()
    if not QUESTION_ID_PATTERN.fullmatch(normalized_question_id):
        raise HTTPException(status_code=422, detail="Invalid question ID format.")

    valid_ids = {item["question_id"] for item in _load_fusion_questions()}
    if normalized_question_id not in valid_ids:
        raise HTTPException(status_code=422, detail="Unknown question ID.")

    extension = Path(video.filename or "").suffix.lower()
    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported video type. Allowed extensions: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}.",
        )

    settings.fusion_upload_path.mkdir(parents=True, exist_ok=True)
    settings.fusion_output_path.mkdir(parents=True, exist_ok=True)
    artifact_id = uuid.uuid4().hex
    video_path = (settings.fusion_upload_path / f"{artifact_id}{extension}").resolve()
    output_path = (
        settings.fusion_output_path / f"{artifact_id}_{normalized_question_id}.json"
    ).resolve()
    if video_path.parent != settings.fusion_upload_path:
        raise HTTPException(status_code=400, detail="Unsafe upload path.")

    bytes_written = 0
    try:
        async with aiofiles.open(video_path, "wb") as destination:
            while chunk := await video.read(1024 * 1024):
                bytes_written += len(chunk)
                if bytes_written > settings.FUSION_MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Uploaded video is too large.")
                await destination.write(chunk)
    except HTTPException:
        video_path.unlink(missing_ok=True)
        raise
    except OSError as exc:
        video_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Could not save uploaded video.") from exc
    finally:
        await video.close()

    if bytes_written == 0:
        video_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Uploaded video is empty.")

    return await asyncio.to_thread(
        _execute_fusion, video_path, normalized_question_id, output_path
    )


@router.post("/start-interview", response_model=InterviewResponse, status_code=201)
def start_interview(
    data: InterviewStart,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    interview = Interview(
        user_id=current_user.id,
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
    current_user: User = Depends(get_current_user),
):
    interview = db.query(Interview).filter(
        Interview.id == interview_id, Interview.user_id == current_user.id
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
    current_user: User = Depends(get_current_user),
):
    interview = db.query(Interview).filter(
        Interview.id == interview_id, Interview.user_id == current_user.id
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
    current_user: User = Depends(get_current_user),
):
    interview = db.query(Interview).filter(
        Interview.id == interview_id, Interview.user_id == current_user.id
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
