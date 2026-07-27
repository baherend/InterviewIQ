"""
nli/common.py — Shared NLI model-sanity helpers for the Interview IQ NLP module.

Refactored out of evaluation/gold_eval.py during Phase 6 (see
PROJECT_EXECUTION_PLAN.md §6): nli/engine.py needs the exact same id2label
sanity assertion gold_eval.py already had before this phase. Duplicating the
check in engine.py would have let the two modules' definitions of "a valid
label mapping" silently drift apart (the failure mode Rule 13 / D31 §5.13
exists to prevent) — so gold_eval.py now imports EXPECTED_ID2LABEL and
assert_id2label from here instead of defining its own copy.
"""

from __future__ import annotations

from transformers import PreTrainedModel

EXPECTED_ID2LABEL: dict[int, str] = {0: "entailment", 1: "neutral", 2: "contradiction"}


def assert_id2label(model: PreTrainedModel, caller: str = "") -> None:
    """Print the model's actual id2label and raise immediately if it doesn't
    match the canonical mapping this whole pipeline assumes (configs/
    nli_finetune.yaml's labels: section) — a mismatch here would silently
    corrupt every downstream prediction."""
    tag = f"[{caller}] " if caller else ""
    print(f"{tag}model.config.id2label = {model.config.id2label}")
    actual = {int(k): str(v).strip().lower() for k, v in model.config.id2label.items()}
    if actual != EXPECTED_ID2LABEL:
        raise ValueError(f"model.config.id2label mismatch: expected {EXPECTED_ID2LABEL}, got {model.config.id2label}")
