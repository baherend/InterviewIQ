"""
nli/engine.py — Full Claims x Chunks NLI matrix engine (Phase 6).

Computes the full SummaC-style Claims x Chunks matrix: for every (claim,
chunk) pair, runs the NLI model and returns the RAW SOFTMAX distribution over
all three classes (entailment, neutral, contradiction) — NEVER argmax (D43).
scoring/aggregation.py is the only place a probability becomes a verdict, and
it does so against configured thresholds, not against this module's opinion
of "the" label for a pair.

Reuses the id2label sanity assertion from nli/common.py (refactored out of
evaluation/gold_eval.py during this phase — see nli/common.py's docstring),
so this module and gold_eval.py cannot silently drift apart on what a valid
id2label mapping looks like.

Two directions are supported, matching configs/scoring.yaml's two channels:
  - build_claims_chunks_matrix — Precision channel (D21/D26 convention):
    premise = chunk text, hypothesis = claim text.
  - build_coverage_matrix — Coverage channel, REVERSED direction (D34):
    premise = claim text, hypothesis = key-point chunk text. This direction
    is OOD for the fine-tuned model and its measurement is deferred to
    post-Phase-8 (D42/D44) — this module only computes probabilities for
    whatever direction it is asked for; it does not judge either direction.

Model/tokenizer are always injected by the caller (never constructed here),
so unit tests never download anything. Inference is batched.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import torch
from transformers import PreTrainedModel, PreTrainedTokenizerBase

from interview_iq.nli.common import assert_id2label
from interview_iq.refdocs.loader import Chunk

LABEL_ORDER: tuple[str, ...] = ("entailment", "neutral", "contradiction")


def _normalize_label(raw: str) -> str:
    label = str(raw).strip().lower()
    if label not in LABEL_ORDER:
        raise ValueError(f"Unrecognized model label {raw!r}; expected one of {LABEL_ORDER}")
    return label


@torch.no_grad()
def run_nli_matrix(
    model: PreTrainedModel,
    tokenizer: PreTrainedTokenizerBase,
    premises: Sequence[str],
    hypotheses: Sequence[str],
    batch_size: int = 8,
    max_length: int = 256,
) -> list[list[dict[str, float]]]:
    """Full cross-product matrix: matrix[i][j] = raw softmax
    {entailment, neutral, contradiction} probs for (premises[i],
    hypotheses[j]) — never argmax (D43). Batched over the flattened
    premise x hypothesis pairs regardless of the two lists' individual
    lengths.
    """
    assert_id2label(model, caller="nli.engine")
    model.eval()
    id2label = {int(k): v for k, v in model.config.id2label.items()}
    ordered_indices = sorted(id2label.keys())

    n_premises, n_hypotheses = len(premises), len(hypotheses)
    flat_premises: list[str] = []
    flat_hypotheses: list[str] = []
    for p in premises:
        for h in hypotheses:
            flat_premises.append(p)
            flat_hypotheses.append(h)

    flat_probs: list[dict[str, float]] = []
    for start in range(0, len(flat_premises), batch_size):
        batch_p = flat_premises[start : start + batch_size]
        batch_h = flat_hypotheses[start : start + batch_size]
        inputs = tokenizer(
            batch_p, batch_h, truncation=True, padding=True, max_length=max_length, return_tensors="pt"
        )
        logits = model(**inputs).logits
        batch_softmax = torch.softmax(logits, dim=-1).tolist()
        for row in batch_softmax:
            flat_probs.append({_normalize_label(id2label[i]): round(float(row[i]), 6) for i in ordered_indices})

    return [flat_probs[i * n_hypotheses : (i + 1) * n_hypotheses] for i in range(n_premises)]


# ── Precision channel: Claims x Chunks, premise=chunk / hypothesis=claim ────


@dataclass(frozen=True)
class ClaimsChunksMatrix:
    """Precision-channel matrix (D21/D26 convention): premise = chunk text,
    hypothesis = claim text. `matrix[claim_idx][chunk_idx]` = probs dict."""

    claims: tuple[str, ...]
    chunk_ids: tuple[str, ...]
    matrix: tuple[tuple[dict[str, float], ...], ...]

    def max_entailment(self, claim_idx: int) -> float:
        row = self.matrix[claim_idx]
        return max((cell["entailment"] for cell in row), default=0.0)

    def max_contradiction(self, claim_idx: int) -> float:
        row = self.matrix[claim_idx]
        return max((cell["contradiction"] for cell in row), default=0.0)

    def best_chunk_id(self, claim_idx: int) -> str | None:
        """chunk_id with the highest P(entailment) for this claim — used for
        the per-claim decision log (cli/run_scoring.py)."""
        row = self.matrix[claim_idx]
        if not row:
            return None
        best_j = max(range(len(row)), key=lambda j: row[j]["entailment"])
        return self.chunk_ids[best_j]


def build_claims_chunks_matrix(
    model: PreTrainedModel,
    tokenizer: PreTrainedTokenizerBase,
    claims: Sequence[str],
    chunks: Sequence[Chunk],
    batch_size: int = 8,
    max_length: int = 256,
) -> ClaimsChunksMatrix:
    """Full Claims x Chunks matrix per SummaC (Precision channel, D21):
    premise=chunk.text, hypothesis=claim — matches the training-pair
    convention (D26) and configs/scoring.yaml's
    channels.precision.direction = "claim_as_hypothesis"."""
    chunk_texts = [c.text for c in chunks]
    raw = run_nli_matrix(
        model, tokenizer, premises=chunk_texts, hypotheses=list(claims), batch_size=batch_size, max_length=max_length
    )  # raw[chunk_idx][claim_idx]
    n_chunks, n_claims = len(chunks), len(claims)
    transposed = tuple(
        tuple(raw[chunk_idx][claim_idx] for chunk_idx in range(n_chunks)) for claim_idx in range(n_claims)
    )
    return ClaimsChunksMatrix(claims=tuple(claims), chunk_ids=tuple(c.chunk_id for c in chunks), matrix=transposed)


# ── Coverage channel: reversed direction, premise=claim / hypothesis=keypoint ─


@dataclass(frozen=True)
class CoverageMatrix:
    """Coverage-channel matrix — REVERSED NLI direction (D34; UNMEASURED and
    OOD per D42/D44, see scoring/metrics.py's module docstring): premise =
    claim text, hypothesis = key-point chunk text.
    `matrix[keypoint_idx][claim_idx]` = probs dict."""

    claims: tuple[str, ...]
    key_point_chunk_ids: tuple[str, ...]
    matrix: tuple[tuple[dict[str, float], ...], ...]

    def max_entailment_for_keypoint(self, kp_idx: int) -> float:
        row = self.matrix[kp_idx]
        return max((cell["entailment"] for cell in row), default=0.0)


def build_coverage_matrix(
    model: PreTrainedModel,
    tokenizer: PreTrainedTokenizerBase,
    claims: Sequence[str],
    key_point_chunks: Sequence[Chunk],
    batch_size: int = 8,
    max_length: int = 256,
) -> CoverageMatrix:
    """Coverage channel (reversed NLI direction, D34/D42/D44): premise=claim,
    hypothesis=key-point chunk text. This direction is OOD for the
    fine-tuned model (D34) and its real measurement is deferred to
    post-Phase-8 (D44) — this function only runs whichever direction it is
    asked for; scoring/metrics.py documents what the number means."""
    key_point_texts = [c.text for c in key_point_chunks]
    raw = run_nli_matrix(
        model, tokenizer, premises=list(claims), hypotheses=key_point_texts, batch_size=batch_size, max_length=max_length
    )  # raw[claim_idx][kp_idx]
    n_claims, n_kps = len(claims), len(key_point_chunks)
    transposed = tuple(
        tuple(raw[claim_idx][kp_idx] for claim_idx in range(n_claims)) for kp_idx in range(n_kps)
    )
    return CoverageMatrix(
        claims=tuple(claims), key_point_chunk_ids=tuple(c.chunk_id for c in key_point_chunks), matrix=transposed
    )
