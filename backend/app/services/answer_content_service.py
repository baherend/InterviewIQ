"""Real Answer Content Score for one answer segment's persisted transcript.

Wraps the existing, already-implemented real NLP pipeline — it does not
reimplement, retune, or otherwise change any formula, threshold, or
weight:

  * Claim decomposition (Groq LLM) + BGE-M3 retrieval + NLI + Precision/
    Coverage/Harmonic-F scoring —
    `InterviewIQ_AI/nlp/interview-iq-fusion-handoff/src/interview_iq/
    pipeline.py::evaluate_answer`, run out of process in the NLP module's
    own dedicated `.venv_nlp` environment via a thin sibling wrapper
    (`InterviewIQ_AI/fusion/runners/run_content_score_json.py`).

Deliberately does NOT let evaluate_answer run its own ASR: Phase 3B
already transcribed this exact answer segment once
(app.services.audio_analysis_service) and persisted the result — this
module reuses that persisted transcript via an injected `transcribe_fn`
(see the runner), so ASR never runs a second time for the same segment.

Never returns a random or fabricated value. Every non-SUCCESS outcome is
a typed status (see app.models.answer_content_analysis.
ContentAnalysisStatus) with a human-readable `error_message`, never a
silently substituted score. Two eligibility gates are checked before the
real (Groq-calling) pipeline is ever invoked — no usable transcript, or
no reference document mapped to this question — exactly mirroring
app.services.audio_analysis_service's "never even invoke the model
subprocess for genuinely ineligible input" discipline.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from app.config import settings
from app.models.answer_content_analysis import ContentAnalysisStatus

# Only the InterviewIQ_AI root is added to sys.path (matches
# app.services.audio_analysis_service's own convention exactly) — gives
# `fusion.*` as a namespace package without adding InterviewIQ_AI/fusion
# itself to sys.path.
_INTERVIEWIQ_AI_DIR = str(settings.interviewiq_ai_dir)
if _INTERVIEWIQ_AI_DIR not in sys.path:
    sys.path.insert(0, _INTERVIEWIQ_AI_DIR)

from fusion.adapters.base import run_json_component  # noqa: E402

CONTENT_SCORE_MODEL_IDENTIFIER = (
    "interview_iq.pipeline.evaluate_answer (decomposition: Groq LLM; "
    "retrieval: BGE-M3 top-k; NLI: MoritzLaurer/mDeBERTa-v3-base-mnli-xnli, "
    "zero-shot — configs unchanged)"
)


@dataclass
class AnswerContentOutcome:
    status: str
    error_message: Optional[str] = None
    question_reference_id: Optional[str] = None
    precision: Optional[float] = None
    coverage: Optional[float] = None
    harmonic_f: Optional[float] = None
    answer_content_score: Optional[float] = None
    claims: Optional[list[str]] = None
    claim_scores: Optional[list[dict[str, Any]]] = None
    model_identifiers: Optional[dict[str, Any]] = None
    raw_diagnostic: Optional[dict[str, Any]] = None


def _validate_content_score_result(parsed: dict) -> bool:
    if not isinstance(parsed, dict):
        return False
    status = parsed.get("status")
    return isinstance(status, str) and status != ""


def _run_content_score(
    transcript: str, transcript_status: str, question_reference_id: str, timeout: int
) -> tuple[Optional[dict], dict]:
    """Runs the real Answer Content Score pipeline
    (interview_iq.pipeline.evaluate_answer) in its dedicated .venv_nlp
    environment via the same reused subprocess/JSON adapter plumbing as
    the ASR/emotion boundaries. Returns (parsed_result_or_None,
    execution_info).
    """
    nlp_python = settings.nlp_handoff_python
    runner = settings.content_score_runner
    reference_json = settings.fusion_reference_json
    if not (nlp_python.is_file() and runner.is_file() and reference_json.is_file()):
        return None, {
            "status": "failed",
            "error": {
                "type": "PreflightError",
                "message": (
                    "The dedicated NLP/content-scoring environment or reference data is "
                    f"not available on this machine (expected a virtual environment at {nlp_python})."
                ),
            },
        }

    fd, input_path_str = tempfile.mkstemp(prefix="content_score_input_", suffix=".json")
    input_path = Path(input_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "transcript": transcript,
                    "transcript_status": transcript_status,
                    "question_id": question_reference_id,
                },
                fh,
                ensure_ascii=False,
            )

        env = os.environ.copy()
        env["PYTHONPATH"] = str(settings.nlp_handoff_src_dir)
        env["PYTHONIOENCODING"] = "utf-8"
        command = [
            str(nlp_python), str(runner),
            "--input-file", str(input_path),
            "--reference-json", str(reference_json),
        ]
        return run_json_component(command, settings.nlp_handoff_dir, env, timeout)
    finally:
        input_path.unlink(missing_ok=True)


def score_answer_segment_content(
    transcript: Optional[str],
    transcript_status: Optional[str],
    nlp_reference_id: Optional[str],
    timeout: Optional[int] = None,
) -> AnswerContentOutcome:
    """Single entry point. Takes this exact answer segment's already-
    persisted Phase 3B transcript/status and its question's mapped NLP
    reference-document ID, and returns a typed outcome. Performs no
    database access — callers persist the result.
    """
    if timeout is None:
        timeout = settings.CONTENT_SCORE_TIMEOUT_SECONDS

    if nlp_reference_id is None:
        return AnswerContentOutcome(
            status=ContentAnalysisStatus.NO_REFERENCE_DOCUMENT.value,
            error_message=(
                "This question has no reference document configured for Answer Content "
                "Score — content scoring is only available for questions with a mapped "
                "reference document."
            ),
        )

    if transcript_status != "ok" or not transcript or not transcript.strip():
        if transcript_status == "no_speech":
            mapped_status = ContentAnalysisStatus.ASR_NO_SPEECH.value
        elif transcript_status == "too_short":
            mapped_status = ContentAnalysisStatus.ASR_TOO_SHORT.value
        else:
            mapped_status = ContentAnalysisStatus.TRANSCRIPT_UNAVAILABLE.value
        return AnswerContentOutcome(
            status=mapped_status,
            question_reference_id=nlp_reference_id,
            error_message=(
                "No usable transcript is available for this answer "
                f"(transcript_status={transcript_status!r}), so Answer Content Score "
                "could not be computed."
            ),
        )

    parsed, execution = _run_content_score(transcript, transcript_status, nlp_reference_id, timeout)
    ok = execution.get("status") == "completed" and _validate_content_score_result(parsed or {})

    if not ok:
        error = execution.get("error") or {}
        message = error.get("message") or "Answer Content Score processing failed."
        return AnswerContentOutcome(
            status=ContentAnalysisStatus.EXECUTION_FAILED.value,
            error_message=f"Answer Content Score unavailable: {message}",
            question_reference_id=nlp_reference_id,
            raw_diagnostic={"execution": execution},
        )

    return AnswerContentOutcome(
        status=parsed["status"],
        error_message=parsed.get("error"),
        question_reference_id=parsed.get("question_id") or nlp_reference_id,
        precision=parsed.get("precision"),
        coverage=parsed.get("coverage"),
        harmonic_f=parsed.get("harmonic_f"),
        answer_content_score=parsed.get("score"),
        claims=parsed.get("claims"),
        claim_scores=parsed.get("claim_scores"),
        model_identifiers=parsed.get("models_used"),
        raw_diagnostic=parsed,
    )
