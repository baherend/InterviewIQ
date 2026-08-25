"""
nli/finetune.py — LoRA fine-tuning for MoritzLaurer/mDeBERTa-v3-base-mnli-xnli.

Phase 4 (see PROJECT_EXECUTION_PLAN.md). Treats the Subject Blindness
diagnosis from Phase 0 zero-shot testing as confirmed and fine-tunes a LoRA
adapter on top of the frozen base model using the 150-pair pilot set.

All hyperparameters (r, lora_alpha, target_modules, learning_rate, batch
sizes, ...) come from `configs/nli_finetune.yaml` via `interview_iq.config.
Config` — nothing is hardcoded here. Data loading and schema/safety checks
are reused unmodified from `interview_iq.nli.dataset` and
`interview_iq.refdocs.loader` (Phase 3); this module only adds the
Phase-4-specific orchestration: question-ID-level splitting, a held-out
document (GN-008) for validation, twin-split assertion, tokenization, and
the LoRA training loop itself.

⚠️ RISK ACCEPTED (D33): Stage-4 human review of the 150 pilot pairs is not
yet closed. Any result produced by this module is methodologically tagged
RISK ACCEPTED until Gate G1 (>=20% retroactive spot-check) is closed —
see decisions.md D33. This module does not enforce that gate; it only
reasserts the D28 (DS-014 exclusion) and D26 (twin integrity) gates, which
*are* hard requirements independent of G1.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from datasets import Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    PreTrainedModel,
    PreTrainedTokenizerBase,
    Trainer,
    TrainingArguments,
    default_data_collator,
)
from peft import LoraConfig, TaskType, get_peft_model

from interview_iq.config import Config
from interview_iq.nli.dataset import (
    PairRecord,
    check_chunk_resolution,
    check_ds014_exclusion,
    check_hard_pos_twin_integrity,
    load_pilot_pairs,
)
from interview_iq.refdocs.loader import ReferenceDocs, load_reference_docs

NEUTRAL_PILOT_LABELS = {"neutral", "paired_neutral", "standard_neutral"}


class D28ContaminationError(ValueError):
    """Raised when the training pool contains a pair from an excluded question_id (D28)."""


class TwinIntegrityError(ValueError):
    """Raised when HARD_POS twins (D26) fail integrity checks before training."""


class TwinSplitError(ValueError):
    """Raised when a HARD_POS claim group ends up split across train/val (D26)."""


# ── example construction ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class NLIExample:
    pair_id: str
    question_id: str
    premise: str
    hypothesis: str
    label: int


def _label_to_id(label: str, labels_map: dict[str, int]) -> int:
    if label == "entailment":
        return int(labels_map["entailment"])
    if label == "contradiction":
        return int(labels_map["contradiction"])
    if label in NEUTRAL_PILOT_LABELS:
        return int(labels_map["neutral"])
    raise ValueError(f"Unrecognized pilot label {label!r} (expected entailment/contradiction/{NEUTRAL_PILOT_LABELS})")


def build_examples(
    pairs: Sequence[PairRecord], refdocs: ReferenceDocs, labels_map: dict[str, int]
) -> list[NLIExample]:
    """Resolve each pair's chunk_id to premise text and map its label to the
    3-way integer scheme (paired_neutral / standard_neutral -> neutral)."""
    examples: list[NLIExample] = []
    for p in pairs:
        premise = refdocs.get_chunk_text(p.chunk_id)
        if premise is None:
            raise ValueError(f"Pair {p.pair_id!r} references unresolved chunk_id {p.chunk_id!r}")
        examples.append(
            NLIExample(
                pair_id=p.pair_id,
                question_id=p.question_id,
                premise=premise,
                hypothesis=p.hypothesis,
                label=_label_to_id(p.label, labels_map),
            )
        )
    return examples


# ── question-ID-level split (D26 / rule 5 in PROJECT_EXECUTION_PLAN.md §5) ──


def split_train_val(
    pairs: Sequence[PairRecord], val_question_ids: set[str]
) -> tuple[list[PairRecord], list[PairRecord]]:
    """Split at Question-ID level only. `val_question_ids` are held out
    entirely (document-level holdout); every other question_id trains."""
    train = [p for p in pairs if p.question_id not in val_question_ids]
    val = [p for p in pairs if p.question_id in val_question_ids]
    if not val:
        raise ValueError(f"val_question_ids {sorted(val_question_ids)} matched no pairs in the pilot set")
    if not train:
        raise ValueError("Train split is empty after holding out val_question_ids")
    return train, val


def assert_twins_not_split(train_pairs: Sequence[PairRecord], val_pairs: Sequence[PairRecord]) -> None:
    """D26: HARD_POS claim groups (question_id, claim_group) must never have
    members on both sides of the split. A question-ID-level split makes this
    structurally impossible, but we assert it explicitly rather than assume it."""
    train_groups = {(p.question_id, p.claim_group) for p in train_pairs if p.claim_group}
    val_groups = {(p.question_id, p.claim_group) for p in val_pairs if p.claim_group}
    overlap = train_groups & val_groups
    if overlap:
        raise TwinSplitError(f"HARD_POS claim group(s) split across train/val: {sorted(overlap)}")


# ── tokenization ──────────────────────────────────────────────────────────────


def examples_to_dataset(
    examples: Sequence[NLIExample], tokenizer: PreTrainedTokenizerBase, max_length: int = 128
) -> Dataset:
    ds = Dataset.from_list(
        [
            {"premise": e.premise, "hypothesis": e.hypothesis, "labels": e.label, "pair_id": e.pair_id}
            for e in examples
        ]
    )

    def _tokenize(batch: dict[str, list[Any]]) -> dict[str, Any]:
        return tokenizer(
            batch["premise"], batch["hypothesis"], truncation=True, padding="max_length", max_length=max_length
        )

    ds = ds.map(_tokenize, batched=True)
    ds = ds.remove_columns(["premise", "hypothesis", "pair_id"])
    return ds


# ── metrics ───────────────────────────────────────────────────────────────────


def _macro_f1(preds: np.ndarray, labels: np.ndarray, num_labels: int = 3) -> float:
    """Manual macro-F1 (no sklearn dependency — see requirements.txt)."""
    per_class_f1 = []
    for c in range(num_labels):
        tp = int(np.sum((preds == c) & (labels == c)))
        fp = int(np.sum((preds == c) & (labels != c)))
        fn = int(np.sum((preds != c) & (labels == c)))
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        per_class_f1.append(f1)
    return float(np.mean(per_class_f1))


def compute_metrics(eval_pred: Any) -> dict[str, float]:
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {"f1_macro": _macro_f1(np.asarray(preds), np.asarray(labels))}


# ── model construction ───────────────────────────────────────────────────────


def build_pretrained_model_and_tokenizer(model_name: str) -> tuple[PreTrainedModel, PreTrainedTokenizerBase]:
    """Production path: downloads the real base model + tokenizer from the
    Hugging Face Hub. Never called by the CPU smoke test (which injects a
    tiny synthetic model instead) — network access is a Kaggle-runner concern."""
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    return model, tokenizer


def wrap_with_lora(model: PreTrainedModel, lora_cfg: dict[str, Any]) -> PreTrainedModel:
    peft_config = LoraConfig(
        r=int(lora_cfg["r"]),
        lora_alpha=int(lora_cfg["lora_alpha"]),
        target_modules=list(lora_cfg["target_modules"]),
        lora_dropout=float(lora_cfg["lora_dropout"]),
        bias=lora_cfg["bias"],
        task_type=TaskType[lora_cfg["task_type"]],
    )
    return get_peft_model(model, peft_config)


# ── orchestration ─────────────────────────────────────────────────────────────


@dataclass
class FinetuneResult:
    n_train_pairs: int
    n_val_pairs: int
    train_result: Any
    eval_metrics: dict[str, float]
    output_dir: Path


def run_finetune(
    cfg: Config,
    refdocs_path: Path,
    pilot_pair_paths: Sequence[Path],
    output_dir: Path,
    model: PreTrainedModel | None = None,
    tokenizer: PreTrainedTokenizerBase | None = None,
    val_question_ids: set[str] | None = None,
    excluded_question_ids: set[str] | None = None,
    training_arg_overrides: dict[str, Any] | None = None,
) -> FinetuneResult:
    """Run one LoRA fine-tuning job end to end.

    If `model`/`tokenizer` are omitted, the real base model from config is
    downloaded via `build_pretrained_model_and_tokenizer` (production path).
    Tests inject a tiny synthetic model/tokenizer instead so the training
    loop can be smoke-tested offline in seconds.
    """
    data_cfg = cfg.nli_finetune["data"]
    lora_cfg = cfg.nli_finetune["lora"]
    labels_map = cfg.nli_finetune["labels"]

    if excluded_question_ids is None:
        excluded_question_ids = set(data_cfg["excluded_question_ids"])
    if val_question_ids is None:
        val_question_ids = set(data_cfg["val_question_ids"])

    refdocs = load_reference_docs(refdocs_path)
    all_pairs = load_pilot_pairs(pilot_pair_paths)

    # ── re-assert the hard gates at training time (Phase 3 already checked
    #    the files on disk; this guards against a stale/edited pool) ────────
    contamination = check_ds014_exclusion(all_pairs, excluded_question_ids)
    if not contamination.passed:
        raise D28ContaminationError(contamination.message)

    twin_check = check_hard_pos_twin_integrity(all_pairs)
    if not twin_check.passed:
        raise TwinIntegrityError(twin_check.message)

    resolution_check = check_chunk_resolution(all_pairs, refdocs)
    if not resolution_check.passed:
        raise ValueError(resolution_check.message)

    train_pairs, val_pairs = split_train_val(all_pairs, val_question_ids)
    assert_twins_not_split(train_pairs, val_pairs)

    if model is None or tokenizer is None:
        model, tokenizer = build_pretrained_model_and_tokenizer(cfg.nli_model)
    peft_model = wrap_with_lora(model, lora_cfg)

    train_examples = build_examples(train_pairs, refdocs, labels_map)
    val_examples = build_examples(val_pairs, refdocs, labels_map)
    train_ds = examples_to_dataset(train_examples, tokenizer)
    val_ds = examples_to_dataset(val_examples, tokenizer)

    train_cfg = cfg.nli_finetune["training"]
    device = cfg.nli_finetune["model"]["device"]
    args_kwargs: dict[str, Any] = dict(
        output_dir=str(output_dir),
        learning_rate=float(train_cfg["learning_rate"]),
        num_train_epochs=float(train_cfg["num_train_epochs"]),
        per_device_train_batch_size=int(train_cfg["per_device_train_batch_size"]),
        per_device_eval_batch_size=int(train_cfg["per_device_eval_batch_size"]),
        warmup_ratio=float(train_cfg["warmup_ratio"]),
        weight_decay=float(train_cfg["weight_decay"]),
        evaluation_strategy=train_cfg["evaluation_strategy"],
        save_strategy=train_cfg["save_strategy"],
        load_best_model_at_end=bool(train_cfg["load_best_model_at_end"]),
        metric_for_best_model=train_cfg["metric_for_best_model"],
        seed=int(train_cfg["seed"]),
        use_cpu=(device == "cpu"),
        report_to=[],
    )
    if training_arg_overrides:
        args_kwargs.update(training_arg_overrides)
    training_args = TrainingArguments(**args_kwargs)

    trainer = Trainer(
        model=peft_model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=default_data_collator,
        compute_metrics=compute_metrics,
    )

    train_result = trainer.train()
    eval_metrics = trainer.evaluate() if len(val_ds) > 0 else {}
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    return FinetuneResult(
        n_train_pairs=len(train_pairs),
        n_val_pairs=len(val_pairs),
        train_result=train_result,
        eval_metrics=eval_metrics,
        output_dir=output_dir,
    )
