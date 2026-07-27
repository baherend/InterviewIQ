"""
pipeline.py — Phase 9 end-to-end Answer Correctness Evaluation orchestrator.

Wires together, in this order (PROJECT_EXECUTION_PLAN.md §9: "one thread: ASR
output -> claims -> chunk cap -> NLI matrix -> score"):

    asr.engine.transcribe_audio
        -> decomposition_llm.client.decompose_via_llm
        -> retrieval.chunk_cap.select_top_k_chunks (Precision side, per claim)
        -> nli.engine.build_claims_chunks_matrix (Precision channel)
        -> nli.engine.build_coverage_matrix (Coverage channel)
        -> scoring.metrics.compute_scoring_result (Precision + Coverage -> Harmonic F -> score)

This module reuses every one of the above unmodified. The NLI/chunk-cap/
scoring wiring is copied in spirit from cli/run_scoring.py's run_scoring()
(same per-claim retrieval-cap-then-Precision-matrix loop, same
resolve_key_point_chunks + build_coverage_matrix + compute_scoring_result
call for Coverage) — not reimplemented differently. Model construction
follows scripts/coverage_channel_real_claims_experiment.py's convention:
model/tokenizer/decompose_fn/transcribe_fn are always injectable, defaulting
to the real production path (build_pretrained_model_and_tokenizer + optional
load_adapter, decompose_via_llm, transcribe_audio) only when not supplied —
so this module is directly testable offline (tiny injected NLI model, mocked
ASR/decomposition) without downloading or calling anything real.

Full transparency: evaluate_answer's returned dict always includes every
intermediate artifact (the full ASR Format Spec record, the claims list, the
exact model identifiers used, per-claim Precision verdicts, per-key-point
Coverage entailment, both channel scores, and the final score) — nothing is
computed and then discarded before reaching the caller.

Failure handling: every stage that can fail (ASR, decomposition, NLI/scoring)
is wrapped so its failure surfaces as one of `status`'s typed values below,
never a bare exception escaping to the caller and never a partial result
silently presented as SUCCESS:

    "SUCCESS"               — full pipeline completed; precision/coverage/score are set.
    "ASR_FAILED"            — asr.engine.ASRError or audio.segmentation.AudioSegmentationError.
    "ASR_NO_SPEECH"         — ASR's own status field was "no_speech" (VAD gate).
    "ASR_TOO_SHORT"         — ASR's own status field was "too_short" (VAD gate).
    "DECOMPOSITION_FAILED"  — decomposition_llm.client.LLMDecompositionError.
    "NLI_FAILED"            — any failure while building the NLI matrices, loading
                              the adapter, or resolving key_points (covers
                              scoring.metrics.DanglingKeyPointError too — a data-
                              integrity error surfaced here rather than adding a
                              fourth, narrower status this first version does not
                              need).

No hardcoded paths anywhere. GROQ_API_KEY is read from `.env` only, via
decomposition_llm.client's existing contract (this module never touches it
directly).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Sequence

from transformers import PreTrainedModel, PreTrainedTokenizerBase

from interview_iq.asr.engine import ASRError, transcribe_audio
from interview_iq.audio.segmentation import AudioSegmentationError
from interview_iq.config import Config
from interview_iq.decomposition.types import DecompositionResult
from interview_iq.decomposition_llm.client import (
    GROQ_MODEL,
    LLMDecompositionError,
    decompose_via_llm,
)
from interview_iq.decomposition_llm.transliteration import apply_glossary
from interview_iq.evaluation.gold_eval import build_pretrained_model_and_tokenizer, load_adapter
from interview_iq.nli.engine import build_claims_chunks_matrix, build_coverage_matrix
from interview_iq.refdocs.loader import Chunk, ReferenceDocument
from interview_iq.retrieval.chunk_cap import ChunkEmbedder, select_top_k_chunks
from interview_iq.scoring.metrics import compute_scoring_result, resolve_key_point_chunks


def _empty_result(question: str, question_id: str | None, models_used: dict[str, Any]) -> dict[str, Any]:
    return {
        "question": question,
        "question_id": question_id,
        "status": None,
        "error": None,
        "asr": None,
        "claims_raw": None,
        "claims": None,
        "transliteration_audit": None,
        "decomposition_error": None,
        "models_used": models_used,
        "key_point_chunk_ids": None,
        "max_e_per_keypoint": None,
        "precision": None,
        "coverage": None,
        "harmonic_f": None,
        "score": None,
        "claim_scores": None,
    }


def evaluate_answer(
    audio_path: str,
    question: str,
    reference_chunks: Sequence[Chunk],
    key_points: Sequence[str],
    config: Config | None = None,
    device_override: str | None = None,
    compute_type_override: str | None = None,
    question_id: str | None = None,
    nli_model: PreTrainedModel | None = None,
    nli_tokenizer: PreTrainedTokenizerBase | None = None,
    adapter_path: Path | None = None,
    chunk_embedder: ChunkEmbedder | None = None,
    transcribe_fn: Callable[..., dict[str, Any]] = transcribe_audio,
    decompose_fn: Callable[[str], DecompositionResult] = decompose_via_llm,
    batch_size: int = 8,
    max_length: int = 256,
) -> dict[str, Any]:
    """Run the full Answer Correctness Evaluation pipeline for one answer.

    Parameters
    ----------
    audio_path:
        Path to an already-extracted answer-segment audio file (mono 16kHz
        WAV, per configs/asr.yaml). Video extraction is a CLI-level concern
        (cli/run_asr.py --video-path), not this function's job.
    question:
        The question text (carried through to the returned dict for
        traceability; not used for scoring — scoring uses reference_chunks/
        key_points, exactly as the rest of the pipeline does).
    reference_chunks:
        All of this question's reference chunks (refdocs.loader.Chunk),
        i.e. one ReferenceDocument.chunks — same type every other module in
        this pipeline (chunk_cap, nli.engine, scoring.metrics) already
        consumes.
    key_points:
        The subset of reference_chunks' chunk_ids marking mandatory-coverage
        points — same shape and meaning as ReferenceDocument.key_points.
    nli_model/nli_tokenizer/adapter_path/chunk_embedder/transcribe_fn/decompose_fn:
        Injection points for tests (offline, zero network/real models) and
        for callers who already hold a loaded model/tokenizer across many
        calls. Left as None/default, this function builds the real
        production objects itself (build_pretrained_model_and_tokenizer +
        optional load_adapter, transcribe_audio, decompose_via_llm) — see
        module docstring.

    Returns
    -------
    A dict — see module docstring for the full `status` contract and the
    complete field list. Always fully populated up to the point of failure;
    fields for stages never reached stay None, never fabricated.
    """
    cfg = config or Config()

    models_used: dict[str, Any] = {
        "asr_checkpoint": cfg.asr_model,
        "asr_device": device_override or cfg.asr["model"]["device"],
        "asr_compute_type": compute_type_override or cfg.asr["model"]["compute_type"],
        "decomposition_model": GROQ_MODEL,
        "nli_base_model": cfg.nli_model,
        "nli_adapter_path": str(adapter_path) if adapter_path is not None else None,
    }
    result = _empty_result(question, question_id, models_used)

    # ── Stage 1: ASR ──────────────────────────────────────────────────────
    try:
        asr_record = transcribe_fn(
            audio_path,
            config=cfg,
            device_override=device_override,
            compute_type_override=compute_type_override,
            question_id=question_id,
        )
    except (ASRError, AudioSegmentationError) as exc:
        result["status"] = "ASR_FAILED"
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    result["asr"] = asr_record

    if asr_record["status"] == "no_speech":
        result["status"] = "ASR_NO_SPEECH"
        return result
    if asr_record["status"] == "too_short":
        result["status"] = "ASR_TOO_SHORT"
        return result

    # ── Stage 2: Claim Decomposition ─────────────────────────────────────
    try:
        decomposition: DecompositionResult = decompose_fn(asr_record["normalized_transcript"])
    except LLMDecompositionError as exc:
        result["status"] = "DECOMPOSITION_FAILED"
        result["decomposition_error"] = str(exc)
        result["error"] = f"LLMDecompositionError: {exc}"
        return result

    claims = decomposition.claims
    claims, transliteration_audit = apply_glossary(claims)
    result["claims_raw"] = decomposition.claims
    result["claims"] = claims
    result["transliteration_audit"] = transliteration_audit
    # An empty claims list (NO_EXTRACTABLE_CLAIMS) is a genuine decomposition
    # result, not a pipeline error (same convention as
    # coverage_channel_real_claims_experiment.py) -- it flows through the
    # exact same scoring path below and naturally yields precision=coverage=0.0
    # (scoring/metrics.py's own documented empty-input behaviour).

    document = ReferenceDocument(
        question_id=question_id or "UNSPECIFIED",
        track="",
        question=question,
        chunks=tuple(reference_chunks),
        key_points=tuple(key_points),
    )

    # ── Stage 3/4: chunk cap (Precision side) + NLI Precision + Coverage ──
    try:
        if nli_model is None or nli_tokenizer is None:
            nli_model, nli_tokenizer = build_pretrained_model_and_tokenizer(cfg.nli_model)
        if adapter_path is not None:
            nli_model = load_adapter(nli_model, adapter_path)

        max_e_per_claim: list[float] = []
        max_c_per_claim: list[float] = []
        best_chunk_per_claim: list[str | None] = []
        for claim_text in claims:
            capped = select_top_k_chunks(claim_text, document.chunks, k=cfg.k, embedder=chunk_embedder).chunks
            row_matrix = build_claims_chunks_matrix(
                nli_model, nli_tokenizer, claims=[claim_text], chunks=capped, batch_size=batch_size, max_length=max_length
            )
            max_e_per_claim.append(row_matrix.max_entailment(0))
            max_c_per_claim.append(row_matrix.max_contradiction(0))
            best_chunk_per_claim.append(row_matrix.best_chunk_id(0))

        key_point_chunks = resolve_key_point_chunks(document)
        coverage_matrix = build_coverage_matrix(
            nli_model, nli_tokenizer, claims=claims, key_point_chunks=key_point_chunks,
            batch_size=batch_size, max_length=max_length,
        )
        max_e_per_keypoint = [
            coverage_matrix.max_entailment_for_keypoint(i) for i in range(len(key_point_chunks))
        ]
    except Exception as exc:  # noqa: BLE001 -- any NLI-stage failure must surface as a typed status, never crash the caller
        result["status"] = "NLI_FAILED"
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    result["key_point_chunk_ids"] = [c.chunk_id for c in key_point_chunks]
    result["max_e_per_keypoint"] = max_e_per_keypoint

    # ── Stage 5: Dual-Channel Scoring ────────────────────────────────────
    combination_cfg = cfg.scoring["combination"]
    scoring_result = compute_scoring_result(
        claim_texts=claims,
        max_e_per_claim=max_e_per_claim,
        max_c_per_claim=max_c_per_claim,
        best_chunk_per_claim=best_chunk_per_claim,
        max_e_per_keypoint=max_e_per_keypoint,
        tau=cfg.tau,
        tau_e=cfg.tau_e,
        alpha=cfg.alpha,
        score_scale=float(combination_cfg["score_scale"]),
    )

    result["status"] = "SUCCESS"
    result["precision"] = scoring_result.precision
    result["coverage"] = scoring_result.coverage
    result["harmonic_f"] = scoring_result.harmonic_f
    result["score"] = scoring_result.score
    result["claim_scores"] = [
        {
            "claim_index": cs.claim_index,
            "claim_text": cs.claim_text,
            "best_chunk_id": cs.best_chunk_id,
            "max_e": cs.max_e,
            "max_c": cs.max_c,
            "verdict": cs.verdict.verdict.value,
            "claim_score": cs.verdict.score,
        }
        for cs in scoring_result.claim_scores
    ]
    return result
