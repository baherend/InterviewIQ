import enum

from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, DateTime, ForeignKey,
    UniqueConstraint, CheckConstraint,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class UploadStatus(str, enum.Enum):
    """Status of the raw media upload for one answer segment. Persisted as
    a plain lowercase string (same convention as UserRole/MembershipRole),
    validated at the application layer.
    """

    PENDING = "pending"
    UPLOADED = "uploaded"
    FAILED = "failed"


class ProcessingStatus(str, enum.Enum):
    """Status of real audio analysis for one answer segment.

    `insufficient_evidence` is distinct from `failed`: it means the audio
    itself was read successfully but did not contain enough signal (e.g.
    silence, no measurable speech energy) for any score to be produced.
    `partial` means at least one of the two audio categories (emotion
    classification, vocal-delivery DSP) produced a usable result while the
    other did not — see backend/app/services/audio_analysis_service.py.
    """

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class AudioFailureCode(str, enum.Enum):
    """Stable failure codes surfaced to the API and frontend. A human
    readable `failure_message` may accompany the code, but the code is
    the stable value calling code/UI should branch on.
    """

    AUDIO_FILE_EMPTY = "AUDIO_FILE_EMPTY"
    AUDIO_FORMAT_UNSUPPORTED = "AUDIO_FORMAT_UNSUPPORTED"
    AUDIO_EXTRACTION_FAILED = "AUDIO_EXTRACTION_FAILED"
    AUDIO_MODEL_UNAVAILABLE = "AUDIO_MODEL_UNAVAILABLE"
    AUDIO_INFERENCE_FAILED = "AUDIO_INFERENCE_FAILED"
    AUDIO_INSUFFICIENT_EVIDENCE = "AUDIO_INSUFFICIENT_EVIDENCE"
    AUDIO_TIMEOUT = "AUDIO_TIMEOUT"
    # Phase 3B: real ASR (interview_iq.asr.engine.transcribe_audio) failed
    # or crashed — distinct from AUDIO_INFERENCE_FAILED (emotion model) so
    # a failure_code always identifies which real component failed.
    AUDIO_TRANSCRIPTION_FAILED = "AUDIO_TRANSCRIPTION_FAILED"


class AnswerSegment(Base):
    """One recorded answer, bound deterministically to the question that
    was active when it was recorded (`interview_question_id`). Created by
    `POST /interviews/{interview_id}/segments` once the corresponding
    upload has been fully validated and written to disk.

    `question_id`/`sequence_index` are denormalized copies of the parent
    `InterviewQuestion` row, kept only for integrity re-validation and
    querying convenience — `interview_question_id` remains the
    authoritative binding.
    """

    __tablename__ = "answer_segments"
    __table_args__ = (
        UniqueConstraint(
            "interview_id", "interview_question_id",
            name="uq_answer_segments_interview_question",
        ),
        CheckConstraint("sequence_index >= 0", name="ck_answer_segments_sequence_index_non_negative"),
    )

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True)
    interview_question_id = Column(
        Integer, ForeignKey("interview_questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="SET NULL"), nullable=True)
    sequence_index = Column(Integer, nullable=False)

    media_path = Column(String(500), nullable=True)
    media_type = Column(String(100), nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    upload_status = Column(String(20), nullable=False, default=UploadStatus.PENDING.value)
    processing_status = Column(String(30), nullable=False, default=ProcessingStatus.PENDING.value)
    failure_code = Column(String(50), nullable=True)
    failure_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    interview = relationship("Interview", back_populates="answer_segments")
    interview_question = relationship("InterviewQuestion", back_populates="answer_segments")
    audio_analysis = relationship(
        "AudioAnalysis", back_populates="answer_segment", uselist=False, cascade="all, delete-orphan"
    )
