"""
scoring/metrics.py — Dual-Channel Scoring metrics: Precision, Coverage,
Harmonic F (Phase 6, D21).

Precision channel:
    Per-claim verdicts come from scoring/aggregation.score_claim (v2
    Entailment-Priority). The channel score is the MEAN of the per-claim
    scores (VERIFIED=+1.0, NEUTRAL=alpha, CONTRADICTED=-max_C) — "what
    fraction of a perfectly-verified answer this answer's claim set adds up
    to," where a single confident contradiction can pull the whole channel
    negative. D21's "قال غلط" (said wrong) penalty is deliberately unbounded
    below, not merely bounded at zero.

Coverage channel — ⚠️ UNMEASURED and OUT-OF-DISTRIBUTION (D34/D42/D44):
    REVERSED NLI direction: key points (a document-level list of chunk_ids —
    refdocs/loader.py's ReferenceDocument.key_points) are hypotheses; claims
    are premises. Aggregation = max P(entailment) over all claims, per key
    point, then the MEAN of that over every key point in the document.
    The fine-tuned model has NEVER seen this direction during training (D34:
    Coverage-direction pairs were excluded from the first fine-tuning batch)
    — D42 predicts this channel is likely to behave *worse* than zero-shot,
    for the same mechanical reason the Precision-direction model got better
    (D26's HARD_POS twins explicitly teach "premise about a different entity
    => neutral", which is the NORMAL case in the reversed direction, not the
    exception). D44 defers the actual Coverage measurement experiment to
    post-Phase-8 (once claims come from the real decomposition module, not
    synthetic/Gold-Set stand-ins — D44 explicitly rejects both). This module
    BUILDS and UNIT-TESTS the channel against fixtures only; nothing in this
    phase runs it against production data.

Harmonic F:
    F = 2*P*C / (P+C) when P >= 0 — the natural harmonic mean. This already
        returns 0.0 whenever either channel is exactly 0 (division touches
        zero in the numerator, not just the denominator) — including the
        D42 fragility case: Coverage=0 forces F=0 even at Precision=1.0,
        because a 0-weight channel makes the harmonic mean 0 by
        construction, not by a special case written for it.
    F = P directly (bypassing Coverage) when P < 0 — an answer containing a
        confident contradiction is "wrong" regardless of how well it covers
        the reference (D21's ranking: correct > silent > wrong must hold no
        matter what Coverage says).
    NOTE: the P<0 branch is a design choice made in this phase to satisfy
    D21's stated ranking intent; it is not itself a literal quote from
    decisions.md and should be reviewed at Gate G4 alongside the other
    pre-calibration defaults.

    Returned UNSCALED (both channels and F live in the same ~[-1, 1] / [0,1]
    range as the per-claim scores) — decisions.md D42's own key_points-
    fragility table reports F this way (0.67, 0.80, ...), and this module
    keeps that convention. `compute_scoring_result`'s `score_scale`
    parameter (configs/scoring.yaml's combination.score_scale, default 100)
    is applied only when producing the final display/report number.

RATIFIED — D45 (10 July 2026), citing D21:
    Two design decisions made in this module during Phase 6 are now
    ratified in decisions.md D45:
      (a) Precision = mean of per-claim scores, may be negative (D45-a /
          D21: penalty for contradiction is deliberately unbounded below).
      (b) when Precision < 0, harmonic_f returns Precision and ignores
          Coverage entirely — preserves D21's strict ranking
          "said-wrong < silent < said-right"; clipping at zero would make
          those two cases equal, which D21 explicitly forbids (D45-b).

MEASURED SCORE RANGE — D47 (10 July 2026), supersedes D21's "0-100":
    Final score range is [-100.0, +100.0] at alpha=0.0.
    Measured on 43dae43: a single claim with max_c=1.0 yields score=-100.0.
    The lower bound is a function of alpha (PRE-CALIBRATION DEFAULT 0.0),
    not a constant; it must be re-measured after calibration (G4).
    D21's ordering is numerically confirmed: -100 < 0 <= 100
    (said-wrong < silent < said-right).
    NOTE: harmonic_f(0.0, 0.0) returns 0.0 (measured). The mechanism by
    which the zero denominator is avoided has NOT been verified; do not
    assert the existence of a guard.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from interview_iq.refdocs.loader import Chunk, ReferenceDocument
from interview_iq.scoring.aggregation import ClaimVerdict, score_claim


class DanglingKeyPointError(ValueError):
    """Raised when a document's key_points reference a chunk_id absent from
    its own chunks. Should be unreachable for real data — refdocs/loader.py's
    load_reference_docs already rejects this at load time (V3/D42) — but
    metrics.py must not silently produce a wrong Coverage number if it is
    ever handed a ReferenceDocument built outside that loader (e.g.
    hand-built in a test)."""


def resolve_key_point_chunks(document: ReferenceDocument) -> list[Chunk]:
    """Resolve `document.key_points` (chunk_id strings) to their Chunk
    objects, in order. Raises DanglingKeyPointError on any chunk_id not
    present in document.chunks."""
    by_id = {c.chunk_id: c for c in document.chunks}
    resolved: list[Chunk] = []
    missing: list[str] = []
    for kp in document.key_points:
        chunk = by_id.get(kp)
        if chunk is None:
            missing.append(kp)
        else:
            resolved.append(chunk)
    if missing:
        raise DanglingKeyPointError(
            f"Document {document.question_id}: key_points reference unknown chunk_id(s): {missing}"
        )
    return resolved


def precision_channel(
    max_e_per_claim: Sequence[float],
    max_c_per_claim: Sequence[float],
    tau: float,
    tau_e: float,
    alpha: float,
) -> tuple[float, list[ClaimVerdict]]:
    """Mean of per-claim scores (see module docstring). Empty claim set ->
    precision = 0.0 (no signal — treated like a fully-silent answer)."""
    verdicts = [
        score_claim(max_e, max_c, tau=tau, tau_e=tau_e, alpha=alpha)
        for max_e, max_c in zip(max_e_per_claim, max_c_per_claim)
    ]
    if not verdicts:
        return 0.0, verdicts
    return sum(v.score for v in verdicts) / len(verdicts), verdicts


def coverage_channel(max_e_per_keypoint: Sequence[float]) -> float:
    """Mean of max P(entailment) per key point (see module docstring). A
    document always has >=1 key point (V3/D42 loader guarantee), but this
    tolerates an empty sequence defensively (returns 0.0) instead of
    dividing by zero."""
    if not max_e_per_keypoint:
        return 0.0
    return sum(max_e_per_keypoint) / len(max_e_per_keypoint)


def harmonic_f(precision: float, coverage: float) -> float:
    """See module docstring for the two branches. Unscaled — caller applies
    configs/scoring.yaml's score_scale for display."""
    if precision < 0:
        return precision
    if precision + coverage <= 0:
        return 0.0
    return 2 * precision * coverage / (precision + coverage)


@dataclass(frozen=True)
class ClaimScore:
    claim_index: int
    claim_text: str
    best_chunk_id: str | None
    max_e: float
    max_c: float
    verdict: ClaimVerdict


@dataclass(frozen=True)
class ScoringResult:
    precision: float
    coverage: float
    harmonic_f: float  # unscaled ratio
    score: float  # harmonic_f * score_scale (display scale)
    claim_scores: tuple[ClaimScore, ...]


def compute_scoring_result(
    claim_texts: Sequence[str],
    max_e_per_claim: Sequence[float],
    max_c_per_claim: Sequence[float],
    best_chunk_per_claim: Sequence[str | None],
    max_e_per_keypoint: Sequence[float],
    tau: float,
    tau_e: float,
    alpha: float,
    score_scale: float = 100.0,
) -> ScoringResult:
    """Pure aggregation entrypoint: takes already-computed per-claim /
    per-keypoint max-probabilities (however they were produced — real NLI
    matrices in production, hand-typed floats in tests) and returns the full
    ScoringResult. Never touches a model, a matrix object, or a file."""
    precision, verdicts = precision_channel(max_e_per_claim, max_c_per_claim, tau=tau, tau_e=tau_e, alpha=alpha)
    coverage = coverage_channel(max_e_per_keypoint)
    f = harmonic_f(precision, coverage)

    claim_scores = tuple(
        ClaimScore(
            claim_index=i,
            claim_text=claim_texts[i],
            best_chunk_id=best_chunk_per_claim[i],
            max_e=max_e_per_claim[i],
            max_c=max_c_per_claim[i],
            verdict=verdicts[i],
        )
        for i in range(len(claim_texts))
    )

    return ScoringResult(precision=precision, coverage=coverage, harmonic_f=f, score=f * score_scale, claim_scores=claim_scores)
