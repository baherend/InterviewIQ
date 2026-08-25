"""
nli/probe_verdict.py — D46 pre-registered decision-rule evaluation.

Applies D46's pre-registered A/B/C criteria to the two probe result dicts
produced by scripts/probe_reversed_direction.py (one per arm: zero-shot and
adapter). This module contains only the threshold comparisons D46 specifies
verbatim in decisions.md — it does not run any model or compute probabilities.

  A  self-entailment      criterion: median P(E) >= 0.90   (per arm)
  B  no-relation ceiling  criterion: median P(E) <= 0.10   (per arm)
  C  cross-entity signal  pre-registered prediction: adapter median < zero-shot
                          median; signal criterion: (zero_shot - adapter) >= 0.10

D46's asymmetric-inference note: failure of A or B proves the channel is
broken; passing does not prove it is sound. This module reports pass/fail
against the stated thresholds only — it makes no soundness claim either way.
"""

from __future__ import annotations

from typing import Any

TEST_A_THRESHOLD = 0.90  # median P(E) >= this
TEST_B_THRESHOLD = 0.10  # median P(E) <= this
TEST_C_SIGNAL_THRESHOLD = 0.10  # zero_shot_median - adapter_median >= this


def _arm_verdict(result: dict[str, Any]) -> dict[str, Any]:
    median_a = result["test_A"]["median_p_e"]
    median_b = result["test_B"]["median_p_e"]
    return {
        "test_A": {
            "median_p_e": median_a,
            "threshold": TEST_A_THRESHOLD,
            "pass": median_a >= TEST_A_THRESHOLD,
        },
        "test_B": {
            "median_p_e": median_b,
            "threshold": TEST_B_THRESHOLD,
            "pass": median_b <= TEST_B_THRESHOLD,
        },
    }


def evaluate_verdict(zero_shot_result: dict[str, Any], adapter_result: dict[str, Any]) -> dict[str, Any]:
    """Apply D46's pre-registered thresholds to a pair of arm results.

    Parameters mirror the JSON schema written by
    scripts/probe_reversed_direction.py (results/probe_reversed/probe_zero_shot.json
    and probe_adapter.json): each must contain test_A/test_B/test_C sub-dicts
    with a median_p_e key.
    """
    zero_shot_c = zero_shot_result["test_C"]["median_p_e"]
    adapter_c = adapter_result["test_C"]["median_p_e"]
    diff = zero_shot_c - adapter_c
    direction_matches_prediction = adapter_c < zero_shot_c
    signal_detected = direction_matches_prediction and diff >= TEST_C_SIGNAL_THRESHOLD

    return {
        "zero_shot": _arm_verdict(zero_shot_result),
        "adapter": _arm_verdict(adapter_result),
        "test_C_signal": {
            "zero_shot_median_p_e": zero_shot_c,
            "adapter_median_p_e": adapter_c,
            "diff": diff,
            "direction_matches_prediction": direction_matches_prediction,
            "signal_threshold": TEST_C_SIGNAL_THRESHOLD,
            "signal_detected": signal_detected,
        },
    }
