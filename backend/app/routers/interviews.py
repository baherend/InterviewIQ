import asyncio
import json
import os
import re
import subprocess
import sys
import uuid
import aiofiles
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models.interview import Interview
from app.models.interview_question import InterviewQuestion
from app.models.answer_segment import AnswerSegment, UploadStatus, ProcessingStatus, AudioFailureCode
from app.models.audio_analysis import AudioAnalysis
from app.models.question import Question
from app.models.result import Result
from app.models.user import User
from app.schemas.interview import InterviewStart, InterviewResponse, InterviewStartResponse
from app.schemas.interview_question import InterviewQuestionOut
from app.schemas.answer_segment import (
    AnswerSegmentResponse, InterviewProcessingStatusResponse, SegmentStatusItem,
    ProcessAudioResponse,
)
from app.schemas.audio_analysis import AudioAnalysisOut, AudioSummaryOut
from app.auth.jwt_handler import get_current_user
from app.ai_modules.vision_module import run_vision
from app.ai_modules.audio_module import run_audio
from app.ai_modules.nlp_module import run_nlp
from app.ai_modules.fusion_engine import fuse_scores
from app.config import settings
from app.fusion_response import clean_fusion_response
from app.services.audio_analysis_service import analyze_answer_segment_audio

router = APIRouter(prefix="/interviews", tags=["interviews"])

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".mkv", ".avi"}
QUESTION_ID_PATTERN = re.compile(r"^[A-Z]{2}-\d{3}$")

# Phase 3A: per-question answer segments.
# Same eligible-question count the product already used before this phase
# (InterviewRoom.jsx used to fetch questions client-side and slice to the
# first 5) — persisted here now, not redesigned.
DEFAULT_QUESTION_COUNT = 5
ANSWER_SEGMENT_ALLOWED_EXTENSIONS = {".webm", ".mp4", ".mov", ".mkv", ".avi", ".ogg", ".wav"}
TERMINAL_PROCESSING_STATUSES = {
    ProcessingStatus.COMPLETED.value,
    ProcessingStatus.PARTIAL.value,
    ProcessingStatus.FAILED.value,
    ProcessingStatus.INSUFFICIENT_EVIDENCE.value,
}


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


@router.post("/start-interview", response_model=InterviewStartResponse, status_code=201)
def start_interview(
    data: InterviewStart,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Creates the interview and immediately persists its ordered question
    sequence (Phase 3A). Eligible-question lookup is unchanged from the
    existing product behavior (questions.py's filter-by-type/track,
    ordered by id) — this endpoint persists that exact selection, it does
    not introduce randomization or a new selection policy. The frontend
    must render questions from the returned `questions` list, not from a
    fresh independent GET /questions call.
    """
    query = db.query(Question).filter(Question.interview_type == data.interview_type)
    if data.track:
        query = query.filter(Question.track == data.track)
    eligible = query.order_by(Question.id).limit(DEFAULT_QUESTION_COUNT).all()
    if not eligible:
        raise HTTPException(
            status_code=422,
            detail="No eligible questions are available for the selected type/track.",
        )

    interview = Interview(
        user_id=current_user.id,
        interview_type=data.interview_type,
        track=data.track,
    )
    db.add(interview)
    db.flush()  # assigns interview.id without ending the transaction

    interview_questions = [
        InterviewQuestion(
            interview_id=interview.id,
            question_id=question.id,
            sequence_index=index,
            question_text=question.question,
            difficulty=question.difficulty,
        )
        for index, question in enumerate(eligible)
    ]
    db.add_all(interview_questions)
    db.commit()
    db.refresh(interview)
    for iq in interview_questions:
        db.refresh(iq)

    return InterviewStartResponse(
        id=interview.id,
        user_id=interview.user_id,
        interview_type=interview.interview_type,
        track=interview.track,
        video_path=interview.video_path,
        audio_path=interview.audio_path,
        final_score=interview.final_score,
        verdict=interview.verdict,
        created_at=interview.created_at,
        questions=[InterviewQuestionOut.model_validate(iq) for iq in interview_questions],
    )


@router.get("/{interview_id}/questions", response_model=list[InterviewQuestionOut])
def get_interview_questions(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-fetches the persisted, ordered question sequence for an
    interview the caller owns — e.g. after a page refresh. Never
    re-derives or re-randomizes the sequence; it only reads what
    start-interview already persisted.
    """
    interview = db.query(Interview).filter(
        Interview.id == interview_id, Interview.user_id == current_user.id
    ).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    questions = (
        db.query(InterviewQuestion)
        .filter(InterviewQuestion.interview_id == interview.id)
        .order_by(InterviewQuestion.sequence_index)
        .all()
    )
    return questions


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


# ============================================================================
# Phase 3A — per-question answer segments and real local audio analysis.
#
# Deliberately does not call app/ai_modules/audio_module.py (the
# random.uniform/random.gauss mock) anywhere below. Real analysis is
# delegated to app.services.audio_analysis_service, which wraps the
# existing real audio implementation under InterviewIQ_AI/audio/ and
# never invokes NLP, Vision, Groq, BGE-M3, NLI, or Late Fusion.
# ============================================================================


def _process_segment_audio_task(segment_id: int) -> None:
    """Runs after the HTTP response for /process-audio or /retry-audio has
    already been sent (FastAPI BackgroundTasks). Opens its own database
    session, since the request-scoped session is closed by then.

    This is a local/development-grade background mechanism, not a durable
    production job queue: if the backend process restarts while a segment
    is 'processing', that segment is left in 'processing' and must be
    retried via POST /interviews/{interview_id}/segments/{segment_id}/retry-audio.
    """
    db = SessionLocal()
    try:
        segment = db.query(AnswerSegment).filter(AnswerSegment.id == segment_id).first()
        if not segment or not segment.media_path:
            return
        try:
            outcome = analyze_answer_segment_audio(Path(segment.media_path))
        except Exception as exc:  # noqa: BLE001 - never leave a segment stuck in "processing"
            segment.processing_status = ProcessingStatus.FAILED.value
            segment.failure_code = AudioFailureCode.AUDIO_INFERENCE_FAILED.value
            segment.failure_message = (
                f"Unexpected error during audio analysis: {type(exc).__name__}: {exc}"
            )
            db.commit()
            return

        segment.processing_status = outcome.processing_status
        segment.failure_code = outcome.failure_code
        segment.failure_message = outcome.failure_message

        if outcome.create_audio_analysis:
            audio_analysis = db.query(AudioAnalysis).filter(
                AudioAnalysis.answer_segment_id == segment.id
            ).first()
            if audio_analysis is None:
                audio_analysis = AudioAnalysis(answer_segment_id=segment.id)
                db.add(audio_analysis)
            audio_analysis.emotion_label = outcome.emotion_label
            audio_analysis.emotion_probabilities = outcome.emotion_probabilities
            audio_analysis.model_confidence = outcome.model_confidence
            audio_analysis.model_confidence_calibrated = False
            audio_analysis.vocal_delivery_score = outcome.vocal_delivery_score
            audio_analysis.speaking_rate_wpm = outcome.speaking_rate_wpm
            audio_analysis.speaking_rate_score = outcome.speaking_rate_score
            audio_analysis.pause_ratio = outcome.pause_ratio
            audio_analysis.pause_control_score = outcome.pause_control_score
            audio_analysis.volume_stability_score = outcome.volume_stability_score
            audio_analysis.speech_continuity_score = outcome.speech_continuity_score
            audio_analysis.sufficient_evidence = outcome.sufficient_evidence
            audio_analysis.failure_reason = outcome.audio_failure_reason
            audio_analysis.model_identifier = outcome.model_identifier
            audio_analysis.model_version = outcome.model_version
            audio_analysis.sample_rate_hz = outcome.sample_rate_hz
            audio_analysis.duration_seconds = outcome.duration_seconds
            audio_analysis.raw_diagnostic = outcome.raw_diagnostic

        db.commit()
    finally:
        db.close()


def _parse_optional_datetime(value: Optional[str], field_name: str) -> Optional[datetime]:
    if value is None or value == "":
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=f"{field_name} must be an ISO-8601 datetime string."
        ) from exc


@router.post("/{interview_id}/segments", response_model=AnswerSegmentResponse, status_code=201)
async def upload_answer_segment(
    interview_id: int,
    media: UploadFile = File(...),
    interview_question_id: int = Form(...),
    question_id: Optional[int] = Form(None),
    sequence_index: Optional[int] = Form(None),
    started_at: Optional[str] = Form(None),
    ended_at: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Uploads one recorded answer and deterministically binds it to the
    question that was active when it was recorded. `question_id` and
    `sequence_index` are optional client-echoed values used only as a
    defense-in-depth integrity check — they are always re-validated
    against the persisted InterviewQuestion row, never trusted blindly.
    """
    interview = db.query(Interview).filter(
        Interview.id == interview_id, Interview.user_id == current_user.id
    ).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    if interview.recording_completed_at is not None:
        raise HTTPException(
            status_code=409,
            detail="This interview's recording has already been marked complete.",
        )

    interview_question = db.query(InterviewQuestion).filter(
        InterviewQuestion.id == interview_question_id,
        InterviewQuestion.interview_id == interview.id,
    ).first()
    if not interview_question:
        raise HTTPException(
            status_code=404, detail="Interview question not found for this interview."
        )

    if question_id is not None and question_id != interview_question.question_id:
        raise HTTPException(
            status_code=422, detail="question_id does not match the persisted interview question."
        )
    if sequence_index is not None and sequence_index != interview_question.sequence_index:
        raise HTTPException(
            status_code=422, detail="sequence_index does not match the persisted interview question."
        )

    parsed_started_at = _parse_optional_datetime(started_at, "started_at")
    parsed_ended_at = _parse_optional_datetime(ended_at, "ended_at")

    segment = db.query(AnswerSegment).filter(
        AnswerSegment.interview_question_id == interview_question.id
    ).first()
    if segment and segment.upload_status == UploadStatus.UPLOADED.value:
        raise HTTPException(
            status_code=409, detail="An answer has already been submitted for this question."
        )

    extension = Path(media.filename or "").suffix.lower()
    if extension not in ANSWER_SEGMENT_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported media type. Allowed extensions: "
                f"{', '.join(sorted(ANSWER_SEGMENT_ALLOWED_EXTENSIONS))}."
            ),
        )

    segment_dir = (settings.answer_segment_upload_path / str(interview.id)).resolve()
    segment_dir.mkdir(parents=True, exist_ok=True)
    artifact_id = uuid.uuid4().hex
    media_path = (segment_dir / f"{artifact_id}{extension}").resolve()
    if media_path.parent != segment_dir:
        raise HTTPException(status_code=400, detail="Unsafe upload path.")

    if segment is None:
        segment = AnswerSegment(
            interview_id=interview.id,
            interview_question_id=interview_question.id,
            question_id=interview_question.question_id,
            sequence_index=interview_question.sequence_index,
            upload_status=UploadStatus.PENDING.value,
            processing_status=ProcessingStatus.PENDING.value,
        )
        db.add(segment)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=409, detail="An answer has already been submitted for this question."
            )

    bytes_written = 0
    try:
        async with aiofiles.open(media_path, "wb") as destination:
            while chunk := await media.read(1024 * 1024):
                bytes_written += len(chunk)
                if bytes_written > settings.ANSWER_SEGMENT_MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Uploaded media is too large.")
                await destination.write(chunk)
    except HTTPException as exc:
        media_path.unlink(missing_ok=True)
        segment.upload_status = UploadStatus.FAILED.value
        segment.failure_message = str(exc.detail)
        db.commit()
        raise
    except OSError as exc:
        media_path.unlink(missing_ok=True)
        segment.upload_status = UploadStatus.FAILED.value
        segment.failure_message = f"Could not save uploaded media: {exc}"
        db.commit()
        raise HTTPException(status_code=500, detail="Could not save uploaded media.") from exc
    finally:
        await media.close()

    if bytes_written == 0:
        media_path.unlink(missing_ok=True)
        segment.upload_status = UploadStatus.FAILED.value
        segment.failure_code = AudioFailureCode.AUDIO_FILE_EMPTY.value
        segment.failure_message = "Uploaded media is empty."
        db.commit()
        raise HTTPException(status_code=422, detail="Uploaded media is empty.")

    segment.media_path = str(media_path)
    segment.media_type = media.content_type
    segment.file_size_bytes = bytes_written
    segment.started_at = parsed_started_at
    segment.ended_at = parsed_ended_at
    segment.upload_status = UploadStatus.UPLOADED.value
    segment.processing_status = ProcessingStatus.PENDING.value
    segment.failure_code = None
    segment.failure_message = None
    db.commit()
    db.refresh(segment)
    return segment


@router.post("/{interview_id}/process-audio", response_model=ProcessAudioResponse)
def start_audio_processing(
    interview_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Marks the recording stage complete (idempotent) and queues real
    audio analysis for every uploaded segment still pending. Processing
    itself runs in a background task (see module docstring above for its
    local/development-grade caveats).
    """
    interview = db.query(Interview).filter(
        Interview.id == interview_id, Interview.user_id == current_user.id
    ).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    if interview.recording_completed_at is None:
        interview.recording_completed_at = datetime.now(timezone.utc)
        db.commit()

    pending_segments = db.query(AnswerSegment).filter(
        AnswerSegment.interview_id == interview.id,
        AnswerSegment.upload_status == UploadStatus.UPLOADED.value,
        AnswerSegment.processing_status == ProcessingStatus.PENDING.value,
    ).all()

    queued_ids: list[int] = []
    for segment in pending_segments:
        segment.processing_status = ProcessingStatus.PROCESSING.value
        queued_ids.append(segment.id)
    db.commit()

    for segment_id in queued_ids:
        background_tasks.add_task(_process_segment_audio_task, segment_id)

    return ProcessAudioResponse(
        interview_id=interview.id, segments_queued=queued_ids, status="processing_started"
    )


@router.get("/{interview_id}/processing-status", response_model=InterviewProcessingStatusResponse)
def get_processing_status(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    interview = db.query(Interview).filter(
        Interview.id == interview_id, Interview.user_id == current_user.id
    ).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    segments = (
        db.query(AnswerSegment)
        .filter(AnswerSegment.interview_id == interview.id)
        .order_by(AnswerSegment.sequence_index)
        .all()
    )
    all_terminal = bool(segments) and all(
        s.processing_status in TERMINAL_PROCESSING_STATUSES for s in segments
    )

    return InterviewProcessingStatusResponse(
        interview_id=interview.id,
        segments=[
            SegmentStatusItem(
                id=s.id,
                interview_question_id=s.interview_question_id,
                sequence_index=s.sequence_index,
                upload_status=s.upload_status,
                processing_status=s.processing_status,
                failure_code=s.failure_code,
                failure_message=s.failure_message,
            )
            for s in segments
        ],
        all_terminal=all_terminal,
    )


@router.post(
    "/{interview_id}/segments/{segment_id}/retry-audio", response_model=AnswerSegmentResponse
)
def retry_segment_audio(
    interview_id: int,
    segment_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    interview = db.query(Interview).filter(
        Interview.id == interview_id, Interview.user_id == current_user.id
    ).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    segment = db.query(AnswerSegment).filter(
        AnswerSegment.id == segment_id, AnswerSegment.interview_id == interview.id
    ).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Answer segment not found")

    if segment.upload_status != UploadStatus.UPLOADED.value:
        raise HTTPException(
            status_code=409, detail="This segment has no uploaded media to analyze."
        )

    segment.processing_status = ProcessingStatus.PROCESSING.value
    segment.failure_code = None
    segment.failure_message = None
    db.commit()
    db.refresh(segment)

    background_tasks.add_task(_process_segment_audio_task, segment.id)
    return segment


@router.get("/report/{interview_id}")
def get_report(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Loads persisted results only — never re-runs any analysis. `result`
    (legacy) is populated only for interviews that went through the old
    mocked /analyze/{interview_id} path; `questions`/`audio_summary`
    (Phase 3A) are populated from persisted InterviewQuestion/
    AnswerSegment/AudioAnalysis rows and are simply empty/unavailable for
    interviews that predate this phase (handled gracefully as legacy
    records, not an error).
    """
    interview = db.query(Interview).filter(
        Interview.id == interview_id, Interview.user_id == current_user.id
    ).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    result = db.query(Result).filter(Result.interview_id == interview_id).first()

    interview_questions = (
        db.query(InterviewQuestion)
        .filter(InterviewQuestion.interview_id == interview.id)
        .order_by(InterviewQuestion.sequence_index)
        .all()
    )

    questions_payload = []
    valid_vocal_scores: list[float] = []
    total_segments = 0
    for interview_question in interview_questions:
        segment = db.query(AnswerSegment).filter(
            AnswerSegment.interview_question_id == interview_question.id
        ).first()
        segment_payload = None
        if segment:
            total_segments += 1
            audio_payload = None
            if segment.audio_analysis:
                audio_payload = AudioAnalysisOut.model_validate(
                    segment.audio_analysis
                ).model_dump(mode="json")
                if segment.audio_analysis.vocal_delivery_score is not None:
                    valid_vocal_scores.append(segment.audio_analysis.vocal_delivery_score)
            segment_payload = {
                "id": segment.id,
                "upload_status": segment.upload_status,
                "processing_status": segment.processing_status,
                "failure_code": segment.failure_code,
                "failure_message": segment.failure_message,
                "started_at": segment.started_at.isoformat() if segment.started_at else None,
                "ended_at": segment.ended_at.isoformat() if segment.ended_at else None,
                "audio_analysis": audio_payload,
            }
        questions_payload.append({
            "sequence_index": interview_question.sequence_index,
            "question_id": interview_question.question_id,
            "question_text": interview_question.question_text,
            "difficulty": interview_question.difficulty,
            "segment": segment_payload,
        })

    if valid_vocal_scores:
        audio_summary = AudioSummaryOut(
            available=True,
            average_vocal_delivery_score=round(
                sum(valid_vocal_scores) / len(valid_vocal_scores), 2
            ),
            valid_segment_count=len(valid_vocal_scores),
            total_segment_count=total_segments,
        )
    elif total_segments:
        audio_summary = AudioSummaryOut(
            available=False,
            valid_segment_count=0,
            total_segment_count=total_segments,
            reason="No answer segments have a valid Vocal Delivery Score yet.",
        )
    else:
        audio_summary = AudioSummaryOut(
            available=False,
            valid_segment_count=0,
            total_segment_count=0,
            reason="Audio analysis not available for this historical interview.",
        )

    return {
        "interview": {
            "id": interview.id,
            "interview_type": interview.interview_type,
            "track": interview.track,
            "final_score": interview.final_score,
            "verdict": interview.verdict,
            "recording_completed_at": (
                interview.recording_completed_at.isoformat()
                if interview.recording_completed_at
                else None
            ),
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
        "questions": questions_payload,
        "audio_summary": audio_summary.model_dump(mode="json"),
    }
