"""
scoring/aggregation.py — v2 Entailment-Priority decision rule (Phase 6, D21 ✅ locked).

Turns one claim's (max_E, max_C) — computed by nli/engine.py's
ClaimsChunksMatrix over the full Claims x Chunks matrix — into exactly one
of three verdicts, per the decision rule locked in configs/scoring.yaml
(decision_rule: "v2_entailment_priority") and decisions.md D21:

    if   max_E >= tau_e:  VERIFIED       (C channel ignored entirely —
                                           justified by internal reference
                                           consistency, PROJECT_EXECUTION_PLAN.md §2)
    elif max_C > tau:     CONTRADICTED   (score = -max_C)
    else:                 NEUTRAL        (score = alpha)

All three thresholds (tau, tau_e, alpha) are function parameters supplied by
the caller from Config — see config.py's PRE_CALIBRATION_TAG, printed on
every Config() construction. Nothing in this module hardcodes a threshold
value.

Per-claim scores (VERIFIED=+1.0, NEUTRAL=alpha, CONTRADICTED=-max_C) are the
unit the Precision channel (scoring/metrics.py) averages over claims. +1.0
for VERIFIED is this module's one hardcoded constant: it is not a threshold
subject to calibration, it is the definition of "a claim is fully
confirmed" — the ceiling every per-claim score is measured against.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Verdict(str, Enum):
    VERIFIED = "VERIFIED"
    CONTRADICTED = "CONTRADICTED"
    NEUTRAL = "NEUTRAL"


VERIFIED_SCORE = 1.0  # ceiling for a fully-confirmed claim — see module docstring


@dataclass(frozen=True)
class ClaimVerdict:
    verdict: Verdict
    score: float
    max_e: float
    max_c: float


def score_claim(max_e: float, max_c: float, tau: float, tau_e: float, alpha: float) -> ClaimVerdict:
    """Apply the v2 Entailment-Priority rule to one claim's (max_E, max_C)."""
    if max_e >= tau_e:
        return ClaimVerdict(verdict=Verdict.VERIFIED, score=VERIFIED_SCORE, max_e=max_e, max_c=max_c)
    if max_c > tau:
        return ClaimVerdict(verdict=Verdict.CONTRADICTED, score=-max_c, max_e=max_e, max_c=max_c)
    return ClaimVerdict(verdict=Verdict.NEUTRAL, score=alpha, max_e=max_e, max_c=max_c)
