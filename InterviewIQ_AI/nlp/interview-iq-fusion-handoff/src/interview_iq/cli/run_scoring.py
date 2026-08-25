"""
cli/run_scoring.py — Phase 6 scoring entrypoint: retrieval cap + NLI matrix +
Dual-Channel Scoring, run over one question's claims.

Usage:
    python -m interview_iq.cli.run_scoring \
        --refdocs-path tests/fixtures/refdocs_mini.json \
        --claims-json tests/fixtures/claims_mini.json \
        --question-id ZZ-001 \
        --output-json out/scoring_ZZ-001.json

Claims JSON is an INTERIM Phase 6 input format — NOT the real decomposition
output (Phase 8, gated behind O9/G2 per D44; this repo does not build the
decomposition module yet). It exists only so the scoring engine built in
this phase can be exercised end-to-end on fixtures before decomposition
exists:

    {"meta": {...}, "question_id": "...",
     "claims": [{"claim_id": "...", "text": "..."}, ...]}

This script reports a 0-100 score plus a PER-CLAIM DECISION LOG (claim text,
best-matching chunk_id, max_E, max_C, verdict). It does not pick or tune any
threshold — tau/tau_e/alpha/k all come from configs/*.yaml via Config. Per
decisions.md D44, this script is not run against production data
(data/refdocs/reference_docs_250_FINAL_v1.json) before the post-Phase-8
Coverage-measurement gate; Phase 6 only builds and unit-tests the engine.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from transformers import PreTrainedModel, PreTrainedTokenizerBase

from interview_iq.config import Config
from interview_iq.evaluation.gold_eval import build_pretrained_model_and_tokenizer, load_adapter
from interview_iq.nli.engine import build_claims_chunks_matrix, build_coverage_matrix
from interview_iq.refdocs.loader import ReferenceDocument, load_reference_docs
from interview_iq.retrieval.chunk_cap import BgeM3Embedder, ChunkEmbedder, select_top_k_chunks
from interview_iq.scoring.metrics import ScoringResult, compute_scoring_result, resolve_key_point_chunks


@dataclass(frozen=True)
class ClaimInput:
    claim_id: str
    text: str


def load_claims(path: Path) -> tuple[str, list[ClaimInput]]:
    """Load the interim Phase 6 claims-JSON format (see module docstring)."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    question_id = raw.get("question_id") or raw.get("meta", {}).get("question_id")
    if not question_id:
        raise ValueError(f"{path}: question_id is required (top-level or meta.question_id)")

    claims_raw = raw.get("claims")
    if not isinstance(claims_raw, list) or not claims_raw:
        raise ValueError(f"{path}: 'claims' must be a non-empty list")

    claims = [ClaimInput(claim_id=c["claim_id"], text=c["text"]) for c in claims_raw]
    return question_id, claims


def run_scoring(
    cfg: Config,
    document: ReferenceDocument,
    claims: list[ClaimInput],
    model: PreTrainedModel,
    tokenizer: PreTrainedTokenizerBase,
    chunk_embedder: ChunkEmbedder | None = None,
    batch_size: int = 8,
    max_length: int = 256,
) -> ScoringResult:
    """Runs the retrieval cap + full NLI matrix + Dual-Channel Scoring
    pipeline for one document's claims. model/tokenizer are injected by the
    caller; chunk_embedder is injectable for tests and otherwise defaults to
    one shared lazy production BGE-M3 wrapper for the whole claim loop. This
    remains directly usable from CPU smoke tests with tiny injected models.

    Precision channel: the retrieval cap (retrieval/chunk_cap.py) is applied
    PER CLAIM (each claim gets its own top-k most-similar chunk subset, per
    PROJECT_EXECUTION_PLAN.md's [3] Chunk Cap -> [4] NLI pipeline order), so
    each claim's Claims x Chunks matrix is built as its own one-claim,
    k-chunks (or fewer) matrix rather than one matrix shared across all
    claims' potentially-different capped subsets.

    Coverage channel: no retrieval cap applies — key points are always a
    small subset of one document's own chunks (D42: max 6/document), so the
    full claim set is scored against every key-point chunk directly.
    """
    claim_texts = [c.text for c in claims]

    if chunk_embedder is None:
        chunk_embedder = BgeM3Embedder(
            model_name=cfg.embedding_model,
            device=str(cfg.retrieval["model"].get("device", "cpu")),
        )

    max_e_per_claim: list[float] = []
    max_c_per_claim: list[float] = []
    best_chunk_per_claim: list[str | None] = []
    for claim in claims:
        retrieval = select_top_k_chunks(claim.text, document.chunks, k=cfg.k, embedder=chunk_embedder)
        capped = retrieval.chunks
        row_matrix = build_claims_chunks_matrix(
            model, tokenizer, claims=[claim.text], chunks=capped, batch_size=batch_size, max_length=max_length
        )
        if retrieval.relevant_chunk_id is None:
            best_chunk, max_e, max_c = row_matrix.best_evidence(0)
        else:
            evidence = row_matrix.evidence_for_chunk(0, retrieval.relevant_chunk_id)
            best_chunk = evidence.chunk_id
            max_e = evidence.entailment
            max_c = evidence.contradiction
        # BGE-M3 chooses the relevant chunk; NLI entailment/contradiction are
        # read from that SAME evidence cell, preserving D110 alignment.
        max_e_per_claim.append(max_e)
        max_c_per_claim.append(max_c)
        best_chunk_per_claim.append(best_chunk)

    key_point_chunks = resolve_key_point_chunks(document)
    coverage_matrix = build_coverage_matrix(
        model, tokenizer, claims=claim_texts, key_point_chunks=key_point_chunks, batch_size=batch_size, max_length=max_length
    )
    max_e_per_keypoint = [
        coverage_matrix.max_entailment_for_keypoint(i) for i in range(len(key_point_chunks))
    ]

    combination_cfg = cfg.scoring["combination"]
    return compute_scoring_result(
        claim_texts=claim_texts,
        max_e_per_claim=max_e_per_claim,
        max_c_per_claim=max_c_per_claim,
        best_chunk_per_claim=best_chunk_per_claim,
        max_e_per_keypoint=max_e_per_keypoint,
        tau=cfg.tau,
        tau_e=cfg.tau_e,
        alpha=cfg.alpha,
        score_scale=float(combination_cfg["score_scale"]),
    )


def _print_result(result: ScoringResult) -> None:
    print(
        f"\nScore: {result.score:.2f}  "
        f"(Precision={result.precision:.3f}, Coverage={result.coverage:.3f}, Harmonic F={result.harmonic_f:.3f})"
    )
    print("\nPer-claim decision log:")
    print(f"{'claim':<50}{'chunk_id':<14}{'max_E':>8}{'max_C':>8}{'verdict':>14}{'claim_score':>12}")
    for cs in result.claim_scores:
        text = (cs.claim_text[:47] + "...") if len(cs.claim_text) > 50 else cs.claim_text
        print(
            f"{text:<50}{(cs.best_chunk_id or '-'):<14}{cs.max_e:>8.3f}{cs.max_c:>8.3f}"
            f"{cs.verdict.verdict.value:>14}{cs.verdict.score:>12.3f}"
        )


def _repo_root() -> Path:
    # src/interview_iq/cli/run_scoring.py -> cli -> interview_iq -> src -> repo root
    return Path(__file__).resolve().parents[3]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 6: retrieval cap + NLI matrix + Dual-Channel Scoring for one question's claims."
    )
    parser.add_argument("--refdocs-path", type=Path, required=True, help="Reference-docs JSON (schema: refdocs/loader.py).")
    parser.add_argument("--claims-json", type=Path, required=True, help="Interim Phase 6 claims JSON (see module docstring).")
    parser.add_argument("--question-id", type=str, required=True)
    parser.add_argument("--adapter-path", type=Path, default=None, help="Optional LoRA adapter. Omit for zero-shot base model.")
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--configs-dir", type=Path, default=None)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=256)
    args = parser.parse_args(argv)

    cfg = Config(configs_dir=args.configs_dir)

    refdocs = load_reference_docs(args.refdocs_path)
    document = refdocs.get_document(args.question_id)
    if document is None:
        parser.error(f"question_id {args.question_id!r} not found in {args.refdocs_path}")
        return 2  # unreachable; parser.error exits, this satisfies type-checkers

    claims_question_id, claims = load_claims(args.claims_json)
    if claims_question_id != args.question_id:
        parser.error(
            f"claims JSON question_id {claims_question_id!r} does not match --question-id {args.question_id!r}"
        )
        return 2

    print(f"[run_scoring] Base model: {cfg.nli_model}")
    model, tokenizer = build_pretrained_model_and_tokenizer(cfg.nli_model)
    if args.adapter_path is not None:
        model = load_adapter(model, args.adapter_path)
        print(f"[run_scoring] Loaded adapter: {args.adapter_path}")

    result = run_scoring(cfg, document, claims, model, tokenizer, batch_size=args.batch_size, max_length=args.max_length)
    _print_result(result)

    if args.output_json is not None:
        payload = {
            "question_id": args.question_id,
            "score": result.score,
            "precision": result.precision,
            "coverage": result.coverage,
            "harmonic_f": result.harmonic_f,
            "claims": [
                {
                    "claim_id": claims[cs.claim_index].claim_id,
                    "claim_text": cs.claim_text,
                    "best_chunk_id": cs.best_chunk_id,
                    "max_e": cs.max_e,
                    "max_c": cs.max_c,
                    "verdict": cs.verdict.verdict.value,
                    "claim_score": cs.verdict.score,
                }
                for cs in result.claim_scores
            ],
        }
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        with args.output_json.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        print(f"\nWrote structured report to: {args.output_json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
