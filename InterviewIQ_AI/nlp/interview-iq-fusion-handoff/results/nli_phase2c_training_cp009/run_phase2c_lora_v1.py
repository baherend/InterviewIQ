"""Fail-closed CP-009 single-LoRA training and frozen CP-005 evaluation.

This experiment utility is isolated from production.  It accepts exactly one
manifest/configuration, loads only the pinned local snapshot, trains one adapter,
evaluates it once on CP-005, and never changes thresholds or production files.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import random
import shutil
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import psutil
import torch
from datasets import Dataset
from peft import LoraConfig, PeftModel, TaskType, get_peft_model
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)

from interview_iq.evaluation.checkpoint_control import (
    LABEL_ORDER,
    ResourceSampler,
    build_metrics,
    infer_predictions,
    memory_snapshot,
    normalize_overlap_text,
    package_versions,
    sha256_file,
    tokenization_diagnostics,
    tokenizer_identity,
    verify_snapshot_files,
)
from interview_iq.nli.common import EXPECTED_ID2LABEL


LABEL_TO_ID = {label: index for index, label in enumerate(LABEL_ORDER)}
REQUIRED_TRAINING_KEYS = {
    "case_id",
    "question_id",
    "premise",
    "hypothesis",
    "label",
    "language_style",
    "difficulty_type",
    "source",
    "rationale",
    "split",
    "pair_group_id",
    "semantic_family_ids",
}


class Phase2CError(RuntimeError):
    """A Phase 2C immutable-control or acceptance invariant failed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Phase2CError(message)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Phase2CError(f"Cannot read strict UTF-8 JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"Expected JSON object: {path}")
    return value


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(json_safe(value), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def relative_path(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")


def load_manifest(project_root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    require(manifest.get("schema_version") == 1, "Manifest schema_version must be 1")
    require(manifest.get("experiment_id") == "interviewiq-nli-phase2c-single-lora-v1", "Unexpected experiment ID")
    require(manifest.get("decision_scope") == "EXACTLY_ONE_LORA_TRAINING_AND_CP005_EVALUATION_NO_PROMOTION", "Scope changed")
    authorization = manifest.get("authorization") or {}
    require(authorization.get("training_authorized") is True, "Training is not authorized")
    require(authorization.get("configuration_count") == 1, "Exactly one configuration is required")
    for key in (
        "production_promotion_authorized",
        "production_pipeline_change_authorized",
        "scoring_change_authorized",
        "threshold_change_authorized",
        "retrieval_change_authorized",
        "fusion_change_authorized",
    ):
        require(authorization.get(key) is False, f"Authorization boundary changed: {key}")
    model = manifest.get("model") or {}
    require(model.get("model_id") == "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli", "Wrong base model")
    require(model.get("revision") == "8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c", "Wrong model revision")
    require(model.get("tokenizer_revision") == model.get("revision"), "Tokenizer/model revisions differ")
    require({int(k): v for k, v in model.get("expected_id2label", {}).items()} == EXPECTED_ID2LABEL, "Label mapping changed")
    lora = manifest.get("lora") or {}
    require(lora == {
        "r": 16,
        "lora_alpha": 32,
        "target_modules": ["query_proj", "value_proj"],
        "lora_dropout": 0.1,
        "bias": "none",
        "task_type": "SEQ_CLS",
    }, "LoRA configuration differs from the authorized single configuration")
    training = manifest.get("training") or {}
    for key, expected in {
        "learning_rate": 0.0002,
        "num_train_epochs": 5,
        "seed": 42,
        "max_length": 256,
        "effective_train_batch_size": 16,
        "device": "cpu",
        "dtype": "float32",
        "cp005_used_for_training_or_selection": False,
    }.items():
        require(training.get(key) == expected, f"training.{key} must be {expected!r}")
    require(int(training["per_device_train_batch_size"]) * int(training["gradient_accumulation_steps"]) == 16, "Effective batch mismatch")
    outputs = manifest.get("outputs") or {}
    require(len(outputs) == len(set(outputs.values())), "Output paths must be unique")
    for path_value in outputs.values():
        require(isinstance(path_value, str) and path_value, "Every output path is required")
        resolved = (project_root / path_value).resolve()
        require(resolved.is_relative_to(project_root.resolve()), f"Output escapes project root: {resolved}")
    return manifest


def normalized_pair(record: Mapping[str, Any]) -> tuple[str, str]:
    return normalize_overlap_text(record["premise"]), normalize_overlap_text(record["hypothesis"])


def validate_inputs(project_root: Path, manifest: Mapping[str, Any], require_outputs_absent: bool) -> dict[str, Any]:
    def frozen_file(spec: Mapping[str, Any], name: str) -> tuple[Path, dict[str, Any]]:
        path = (project_root / spec["path"]).resolve()
        require(path.is_file(), f"Missing {name}: {path}")
        actual = sha256_file(path)
        require(actual == spec["sha256"], f"{name} SHA mismatch: {actual}")
        return path, read_json(path)

    attestation_path, attestation = frozen_file(manifest["human_review_attestation"], "human review attestation")
    require(attestation.get("approved_for_training") is True, "External review did not approve training")
    require(attestation.get("reviewed_records") == 600, "External review record count mismatch")
    require(attestation.get("review_passes_completed") == 2, "Two review passes are required")
    require(attestation.get("label_disagreements_adjudicated") is True, "Adjudication is incomplete")
    require(attestation.get("content_changes_after_cp008") is False, "Attestation reports post-CP008 data changes")

    corpus_path, corpus = frozen_file(manifest["training_dataset"], "training corpus")
    split_path, split_manifest = frozen_file(manifest["split_manifest"], "split manifest")
    cp005_path, cp005 = frozen_file(manifest["cp005_evaluation"], "CP-005 evaluation")
    baseline_path = (project_root / manifest["cp005_evaluation"]["baseline_result_path"]).resolve()
    require(baseline_path.is_file(), "Frozen CP-005 baseline result is missing")
    require(sha256_file(baseline_path) == manifest["cp005_evaluation"]["baseline_result_sha256"], "CP-005 baseline SHA mismatch")
    require(cp005.get("do_not_train") is True, "CP-005 must remain do_not_train=true")

    records = corpus.get("records")
    require(isinstance(records, list) and len(records) == 600, "Corpus must contain exactly 600 records")
    ids: list[str] = []
    pairs: list[tuple[str, str]] = []
    for index, record in enumerate(records):
        require(isinstance(record, dict), f"records[{index}] is not an object")
        missing = REQUIRED_TRAINING_KEYS - record.keys()
        require(not missing, f"{record.get('case_id', index)} missing {sorted(missing)}")
        require(record["label"] in LABEL_ORDER, f"Invalid label in {record['case_id']}")
        require(record["split"] in ("train", "dev"), f"Invalid split in {record['case_id']}")
        source = record["source"]
        require(isinstance(source, dict) and source.get("question_id") == record["question_id"], f"Source mismatch in {record['case_id']}")
        ids.append(record["case_id"])
        pairs.append(normalized_pair(record))
    require(len(ids) == len(set(ids)), "Duplicate training case IDs")
    require(len(pairs) == len(set(pairs)), "Duplicate normalized training pairs")
    require(Counter(record["label"] for record in records) == Counter(manifest["training_dataset"]["label_distribution"]), "Label distribution changed")

    train = [record for record in records if record["split"] == "train"]
    dev = [record for record in records if record["split"] == "dev"]
    require(len(train) == 480 and len(dev) == 120, "Train/dev record counts changed")
    train_qids = {record["question_id"] for record in train}
    dev_qids = {record["question_id"] for record in dev}
    train_families = {family for record in train for family in record["semantic_family_ids"]}
    dev_families = {family for record in dev for family in record["semantic_family_ids"]}
    train_groups = {record["pair_group_id"] for record in train}
    dev_groups = {record["pair_group_id"] for record in dev}
    require(not train_qids & dev_qids, "Train/dev question-ID overlap")
    require(not train_families & dev_families, "Train/dev semantic-family overlap")
    require(not train_groups & dev_groups, "Train/dev pair-group overlap")
    require(train_qids == set(split_manifest["train"]["question_ids"]), "Train question IDs differ from split manifest")
    require(dev_qids == set(split_manifest["dev"]["question_ids"]), "Dev question IDs differ from split manifest")
    require({record["case_id"] for record in train} == set(split_manifest["train"]["case_ids"]), "Train case IDs differ from split manifest")
    require({record["case_id"] for record in dev} == set(split_manifest["dev"]["case_ids"]), "Dev case IDs differ from split manifest")

    eval_cases = cp005.get("cases")
    require(isinstance(eval_cases, list) and len(eval_cases) == 45, "CP-005 case count changed")
    protected_qids = {case["source_question_id"] for case in eval_cases}
    eval_premises = {normalize_overlap_text(case["premise"]) for case in eval_cases}
    eval_hypotheses = {normalize_overlap_text(case["hypothesis"]) for case in eval_cases}
    eval_pairs = {normalized_pair(case) for case in eval_cases}
    require(not ({record["question_id"] for record in records} & protected_qids), "CP-005 question-ID leakage")
    require(not ({normalize_overlap_text(record["premise"]) for record in records} & eval_premises), "CP-005 premise leakage")
    require(not ({normalize_overlap_text(record["hypothesis"]) for record in records} & eval_hypotheses), "CP-005 hypothesis leakage")
    require(not (set(pairs) & eval_pairs), "CP-005 pair leakage")

    snapshot = verify_snapshot_files(manifest["model"])
    tokenizer = AutoTokenizer.from_pretrained(
        manifest["model"]["tokenizer_id"],
        revision=manifest["model"]["tokenizer_revision"],
        local_files_only=True,
        use_fast=True,
    )
    tokenizer_info = tokenizer_identity(tokenizer, manifest["model"])
    require(tokenizer_info["vocab_sha256"] == manifest["model"]["tokenizer_vocab_sha256"], "Tokenizer vocabulary fingerprint mismatch")
    training_tokenization = tokenization_diagnostics(
        tokenizer,
        [{"case_id": r["case_id"], "premise": r["premise"], "hypothesis": r["hypothesis"]} for r in records],
        int(manifest["training"]["max_length"]),
    )
    del tokenizer

    output_dir = (project_root / manifest["outputs"]["adapter_dir"]).resolve()
    trainer_work = (project_root / "results/nli_phase2c_training_cp009/trainer_work_v1").resolve()
    if require_outputs_absent:
        require(not output_dir.exists(), f"Adapter output already exists; refusing a second run: {output_dir}")
        require(not trainer_work.exists(), f"Trainer work directory already exists: {trainer_work}")

    vm = psutil.virtual_memory()
    require(int(vm.available) >= 6_000_000_000, f"Insufficient available memory for controlled CPU training: {vm.available}")
    return {
        "attestation": {"path": relative_path(attestation_path, project_root), "sha256": sha256_file(attestation_path), "approved": True},
        "corpus": {"path": relative_path(corpus_path, project_root), "sha256": sha256_file(corpus_path), "records": len(records)},
        "split": {
            "path": relative_path(split_path, project_root),
            "sha256": sha256_file(split_path),
            "train_records": len(train),
            "dev_records": len(dev),
            "train_questions": len(train_qids),
            "dev_questions": len(dev_qids),
            "question_overlap": [],
            "semantic_family_overlap": [],
            "pair_group_overlap": [],
        },
        "labels": dict(sorted(Counter(record["label"] for record in records).items())),
        "leakage": {
            "cp005_path": relative_path(cp005_path, project_root),
            "cp005_sha256": sha256_file(cp005_path),
            "protected_question_hits": [],
            "premise_hits": [],
            "hypothesis_hits": [],
            "pair_hits": [],
        },
        "duplicates": {"case_id_count": 0, "normalized_pair_count": 0},
        "model_snapshot": snapshot,
        "tokenizer": tokenizer_info,
        "training_tokenization": training_tokenization,
        "environment_capacity": {
            "total_memory_bytes": int(vm.total),
            "available_memory_bytes": int(vm.available),
            "disk_free_bytes": int(shutil.disk_usage(project_root).free),
            "cpu_logical": psutil.cpu_count(logical=True),
            "cpu_physical": psutil.cpu_count(logical=False),
        },
        "adapter_output_absent_before_training": not output_dir.exists(),
    }


def stage_preflight(project_root: Path, manifest_path: Path) -> None:
    manifest = load_manifest(project_root, manifest_path)
    controls = validate_inputs(project_root, manifest, require_outputs_absent=True)
    output = {
        "schema_version": 1,
        "validation_id": "interviewiq-nli-phase2c-preflight-v1",
        "status": "PASS",
        "training_authorized_and_ready": True,
        "manifest": {"path": relative_path(manifest_path, project_root), "sha256": sha256_file(manifest_path)},
        "exactly_one_configuration": True,
        "controls": controls,
        "scope": {
            "production_change": False,
            "scoring_change": False,
            "threshold_change": False,
            "retrieval_change": False,
            "fusion_change": False,
            "promotion": False,
        },
    }
    output_path = project_root / manifest["outputs"]["preflight"]
    write_json(output_path, output)
    print("PHASE2C_PREFLIGHT=PASS")
    print(f"PREFLIGHT_SHA256={sha256_file(output_path)}")


def configure_training_runtime(training: Mapping[str, Any]) -> None:
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    seed = int(training["seed"])
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(int(training["torch_num_threads"]))
    try:
        torch.set_num_interop_threads(int(training["torch_num_interop_threads"]))
    except RuntimeError as exc:
        raise Phase2CError(f"Cannot pin torch inter-op threads: {exc}") from exc
    torch.use_deterministic_algorithms(True)


def scalar_training_metrics(eval_pred: Any) -> dict[str, float]:
    logits, labels = eval_pred
    if isinstance(logits, tuple):
        logits = logits[0]
    predictions = np.argmax(np.asarray(logits), axis=-1)
    labels_array = np.asarray(labels)
    class_f1: list[float] = []
    output: dict[str, float] = {"accuracy": float(np.mean(predictions == labels_array))}
    for class_id, name in enumerate(LABEL_ORDER):
        tp = int(np.sum((predictions == class_id) & (labels_array == class_id)))
        fp = int(np.sum((predictions == class_id) & (labels_array != class_id)))
        fn = int(np.sum((predictions != class_id) & (labels_array == class_id)))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        class_f1.append(f1)
        output[f"f1_{name}"] = f1
    output["f1_macro"] = float(sum(class_f1) / len(class_f1))
    return output


def make_dataset(records: Sequence[Mapping[str, Any]], tokenizer: Any, max_length: int) -> Dataset:
    dataset = Dataset.from_list([
        {
            "premise": record["premise"],
            "hypothesis": record["hypothesis"],
            "labels": LABEL_TO_ID[record["label"]],
        }
        for record in records
    ])

    def tokenize(batch: dict[str, list[Any]]) -> dict[str, Any]:
        return tokenizer(batch["premise"], batch["hypothesis"], truncation=True, max_length=max_length)

    return dataset.map(tokenize, batched=True, remove_columns=["premise", "hypothesis"])


def stage_train(project_root: Path, manifest_path: Path) -> None:
    manifest = load_manifest(project_root, manifest_path)
    preflight_path = project_root / manifest["outputs"]["preflight"]
    require(preflight_path.is_file(), "Preflight artifact is missing")
    preflight = read_json(preflight_path)
    require(preflight.get("status") == "PASS" and preflight.get("training_authorized_and_ready") is True, "Preflight did not pass")
    require(preflight["manifest"]["sha256"] == sha256_file(manifest_path), "Manifest changed after preflight")
    validate_inputs(project_root, manifest, require_outputs_absent=True)

    training = manifest["training"]
    configure_training_runtime(training)
    corpus = read_json(project_root / manifest["training_dataset"]["path"])
    train_records = [record for record in corpus["records"] if record["split"] == "train"]
    dev_records = [record for record in corpus["records"] if record["split"] == "dev"]
    adapter_dir = (project_root / manifest["outputs"]["adapter_dir"]).resolve()
    trainer_work = (project_root / "results/nli_phase2c_training_cp009/trainer_work_v1").resolve()

    process = psutil.Process(os.getpid())
    memory_before = memory_snapshot(process)
    lifecycle_sampler = ResourceSampler(interval_seconds=0.05).start()
    load_start = time.perf_counter_ns()
    tokenizer = AutoTokenizer.from_pretrained(
        manifest["model"]["tokenizer_id"],
        revision=manifest["model"]["tokenizer_revision"],
        local_files_only=True,
        use_fast=True,
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        manifest["model"]["model_id"],
        revision=manifest["model"]["revision"],
        local_files_only=True,
        torch_dtype=torch.float32,
        low_cpu_mem_usage=True,
    )
    model.to(device=torch.device("cpu"), dtype=torch.float32)
    load_seconds = (time.perf_counter_ns() - load_start) / 1e9
    actual_mapping = {int(key): str(value).strip().lower() for key, value in model.config.id2label.items()}
    require(actual_mapping == EXPECTED_ID2LABEL, f"Model label mapping mismatch: {actual_mapping}")
    require(not bool(getattr(model, "peft_config", None)), "Base model unexpectedly has an adapter")

    lora = manifest["lora"]
    peft_config = LoraConfig(
        r=int(lora["r"]),
        lora_alpha=int(lora["lora_alpha"]),
        target_modules=list(lora["target_modules"]),
        lora_dropout=float(lora["lora_dropout"]),
        bias=str(lora["bias"]),
        task_type=TaskType[lora["task_type"]],
    )
    model = get_peft_model(model, peft_config)
    trainable_parameters = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    total_parameters = sum(parameter.numel() for parameter in model.parameters())
    require(trainable_parameters > 0, "LoRA produced zero trainable parameters")
    require(bool(getattr(model, "peft_config", None)), "LoRA adapter did not attach")

    train_dataset = make_dataset(train_records, tokenizer, int(training["max_length"]))
    dev_dataset = make_dataset(dev_records, tokenizer, int(training["max_length"]))
    data_collator = DataCollatorWithPadding(tokenizer=tokenizer, padding=True, return_tensors="pt")
    training_args = TrainingArguments(
        output_dir=str(trainer_work),
        overwrite_output_dir=False,
        learning_rate=float(training["learning_rate"]),
        num_train_epochs=float(training["num_train_epochs"]),
        per_device_train_batch_size=int(training["per_device_train_batch_size"]),
        gradient_accumulation_steps=int(training["gradient_accumulation_steps"]),
        per_device_eval_batch_size=int(training["per_device_eval_batch_size"]),
        warmup_ratio=float(training["warmup_ratio"]),
        weight_decay=float(training["weight_decay"]),
        evaluation_strategy=str(training["evaluation_strategy"]),
        save_strategy=str(training["save_strategy"]),
        save_total_limit=int(training["save_total_limit"]),
        load_best_model_at_end=bool(training["load_best_model_at_end"]),
        metric_for_best_model=str(training["metric_for_best_model"]),
        greater_is_better=bool(training["greater_is_better"]),
        logging_strategy="epoch",
        seed=int(training["seed"]),
        data_seed=int(training["seed"]),
        use_cpu=True,
        fp16=False,
        bf16=False,
        report_to=[],
        dataloader_num_workers=0,
        remove_unused_columns=True,
        optim="adamw_torch",
        full_determinism=True,
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=dev_dataset,
        data_collator=data_collator,
        compute_metrics=scalar_training_metrics,
        tokenizer=tokenizer,
    )

    training_start = time.perf_counter_ns()
    train_result = trainer.train()
    training_seconds = (time.perf_counter_ns() - training_start) / 1e9
    final_dev_metrics = trainer.evaluate()
    adapter_dir.mkdir(parents=True, exist_ok=False)
    trainer.model.save_pretrained(str(adapter_dir), safe_serialization=True)
    tokenizer.save_pretrained(str(adapter_dir))
    trainer.state.save_to_json(str(adapter_dir / "trainer_state.json"))
    peak_rss = lifecycle_sampler.stop()
    memory_after = memory_snapshot(process)

    log_path = project_root / manifest["outputs"]["training_log"]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", newline="\n") as handle:
        for entry in trainer.state.log_history:
            handle.write(json.dumps(json_safe(entry), ensure_ascii=False, sort_keys=True) + "\n")

    environment = {
        "schema_version": 1,
        "run_id": "interviewiq-nli-phase2c-single-lora-v1",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "logical_cpu_count": psutil.cpu_count(logical=True),
        "physical_cpu_count": psutil.cpu_count(logical=False),
        "torch_num_threads": torch.get_num_threads(),
        "torch_num_interop_threads": torch.get_num_interop_threads(),
        "cuda_available": torch.cuda.is_available(),
        "device": "cpu",
        "dtype": "float32",
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "packages": {**package_versions(), "peft": getattr(sys.modules.get("peft"), "__version__", "0.10.0"), "datasets": getattr(sys.modules.get("datasets"), "__version__", "2.18.0")},
        "model_load_wall_seconds": load_seconds,
        "training_wall_seconds": training_seconds,
        "memory_before_load": memory_before,
        "memory_after_training": memory_after,
        "sampled_peak_lifecycle_rss_bytes": peak_rss,
        "process_peak_working_set_bytes": memory_after["peak_working_set_bytes"],
    }
    environment_path = project_root / manifest["outputs"]["environment"]
    write_json(environment_path, environment)

    required_adapter_files = [
        adapter_dir / "adapter_config.json",
        adapter_dir / "adapter_model.safetensors",
        adapter_dir / "tokenizer_config.json",
        adapter_dir / "trainer_state.json",
    ]
    for path in required_adapter_files:
        require(path.is_file(), f"Required training artifact is missing: {path}")
    adapter_hashes = {
        relative_path(path, project_root): {"sha256": sha256_file(path), "bytes": path.stat().st_size}
        for path in sorted(adapter_dir.rglob("*")) if path.is_file()
    }
    metrics = {
        "schema_version": 1,
        "run_id": "interviewiq-nli-phase2c-single-lora-v1",
        "status": "TRAINING_COMPLETE_NOT_PROMOTED",
        "manifest": {"path": relative_path(manifest_path, project_root), "sha256": sha256_file(manifest_path)},
        "preflight": {"path": relative_path(preflight_path, project_root), "sha256": sha256_file(preflight_path), "status": "PASS"},
        "dataset": {"train_records": len(train_records), "dev_records": len(dev_records), "cp005_used": False},
        "configuration": {"lora": lora, "training": training},
        "model": {
            "model_id": manifest["model"]["model_id"],
            "revision": manifest["model"]["revision"],
            "id2label": {str(key): value for key, value in actual_mapping.items()},
            "total_parameters_with_adapter": total_parameters,
            "trainable_parameters": trainable_parameters,
            "trainable_parameter_ratio": trainable_parameters / total_parameters,
        },
        "trainer": {
            "best_model_checkpoint": trainer.state.best_model_checkpoint,
            "best_metric": trainer.state.best_metric,
            "global_step": trainer.state.global_step,
            "epoch": trainer.state.epoch,
            "train_result_metrics": train_result.metrics,
            "final_dev_metrics": final_dev_metrics,
            "log_history": trainer.state.log_history,
        },
        "runtime": environment,
        "adapter": {"path": relative_path(adapter_dir, project_root), "files": adapter_hashes},
        "scope": {"production_changed": False, "promoted": False, "thresholds_tuned": False, "second_adapter_trained": False},
    }
    metrics_path = project_root / manifest["outputs"]["training_metrics"]
    write_json(metrics_path, metrics)
    print("PHASE2C_TRAINING=COMPLETE")
    print(f"TRAINING_METRICS_SHA256={sha256_file(metrics_path)}")
    print(f"ADAPTER_MODEL_SHA256={sha256_file(adapter_dir / 'adapter_model.safetensors')}")
    print(f"BEST_DEV_F1={trainer.state.best_metric}")

    del trainer
    del model
    del tokenizer
    gc.collect()


def acceptance_result(
    metrics: Mapping[str, Any],
    predictions: Sequence[Mapping[str, Any]],
    baseline: Mapping[str, Any],
    resources: Mapping[str, Any],
    manifest: Mapping[str, Any],
    adapter_attached: bool,
) -> dict[str, Any]:
    acceptance = manifest["acceptance"]
    overall = metrics["all_scored_cases"]
    anchors = metrics["DA017_regression_anchors"]
    baseline_predictions = {row["case_id"]: row for row in baseline["predictions"]}
    baseline_correct = {case_id for case_id, row in baseline_predictions.items() if row["correct"]}
    regressions = [row["case_id"] for row in predictions if row["case_id"] in baseline_correct and not row["correct"]]
    supported_slices: dict[str, float] = {}
    for group_name in ("by_language_style", "by_difficulty_type"):
        for slice_name, slice_metrics in metrics[group_name].items():
            if int(slice_metrics["support"]) >= 5:
                supported_slices[f"{group_name}.{slice_name}"] = float(slice_metrics["accuracy"])
    minimum_slice = min(supported_slices.values()) if supported_slices else 1.0
    neutral = overall["per_class"]["neutral"]
    neutral_correct = int(round(float(neutral["recall"]) * int(neutral["support"])))
    checks: dict[str, dict[str, Any]] = {}

    def add(name: str, actual: Any, target: str, passed: bool) -> None:
        checks[name] = {"actual": actual, "target": target, "passed": bool(passed)}

    correct = int(round(float(overall["accuracy"]) * int(overall["support"])))
    add("overall_correct", correct, f">={acceptance['overall_correct_minimum']}/45", correct >= acceptance["overall_correct_minimum"])
    add("accuracy", overall["accuracy"], f">={acceptance['accuracy_minimum']}", overall["accuracy"] >= acceptance["accuracy_minimum"])
    add("macro_f1", overall["macro_f1"], f">={acceptance['macro_f1_minimum']}", overall["macro_f1"] >= acceptance["macro_f1_minimum"])
    min_class_f1 = min(float(overall["per_class"][label]["f1"]) for label in LABEL_ORDER)
    add("minimum_class_f1", min_class_f1, f">={acceptance['each_class_f1_minimum']}", min_class_f1 >= acceptance["each_class_f1_minimum"])
    add("false_contradiction_count", overall["false_contradiction_count_on_entailments"], f"<={acceptance['false_contradiction_maximum_count']}", overall["false_contradiction_count_on_entailments"] <= acceptance["false_contradiction_maximum_count"])
    add("false_entailment_count", overall["false_entailment_count_on_contradictions"], f"<={acceptance['false_entailment_maximum_count']}", overall["false_entailment_count_on_contradictions"] <= acceptance["false_entailment_maximum_count"])
    add("neutral_correct", neutral_correct, f">={acceptance['neutral_correct_minimum']}/15", neutral_correct >= acceptance["neutral_correct_minimum"])
    add("neutral_f1", neutral["f1"], f">={acceptance['neutral_f1_minimum']}", neutral["f1"] >= acceptance["neutral_f1_minimum"])
    anchor_correct = int(round(float(anchors["accuracy"]) * int(anchors["support"])))
    add("DA017_anchors", anchor_correct, f"={acceptance['da017_correct_required']}/5", anchor_correct == acceptance["da017_correct_required"])
    add("baseline_correct_regressions", regressions, f"<={acceptance['baseline_correct_regressions_maximum']}", len(regressions) <= acceptance["baseline_correct_regressions_maximum"])
    add("minimum_supported_slice_accuracy", minimum_slice, f">={acceptance['minimum_supported_slice_accuracy']}", minimum_slice >= acceptance["minimum_supported_slice_accuracy"])
    add("latency_ms_per_case", resources["milliseconds_per_case"], f"<={acceptance['latency_milliseconds_per_case_maximum']}", resources["milliseconds_per_case"] <= acceptance["latency_milliseconds_per_case_maximum"])
    peak = resources["process_peak_working_set_bytes"] or resources["sampled_peak_lifecycle_rss_bytes"]
    add("peak_working_set_bytes", peak, f"<={acceptance['peak_working_set_bytes_maximum']}", peak <= acceptance["peak_working_set_bytes_maximum"])
    add("adapter_attachment", adapter_attached, "true", adapter_attached)
    return {
        "checks": checks,
        "all_pass": all(check["passed"] for check in checks.values()),
        "baseline_correct_case_ids": sorted(baseline_correct),
        "new_regressions_on_baseline_correct_cases": regressions,
        "supported_slice_accuracies": supported_slices,
        "decision_limit": acceptance["decision_limit"],
    }


def render_report(comparison: Mapping[str, Any]) -> str:
    base = comparison["baseline"]["metrics"]
    adapter = comparison["adapter"]["metrics"]
    acceptance = comparison["acceptance"]
    rows = [
        ("Accuracy", base["accuracy"], adapter["accuracy"]),
        ("Macro F1", base["macro_f1"], adapter["macro_f1"]),
        ("Entailment F1", base["per_class"]["entailment"]["f1"], adapter["per_class"]["entailment"]["f1"]),
        ("Neutral F1", base["per_class"]["neutral"]["f1"], adapter["per_class"]["neutral"]["f1"]),
        ("Contradiction F1", base["per_class"]["contradiction"]["f1"], adapter["per_class"]["contradiction"]["f1"]),
        ("False contradictions", base["false_contradiction_count_on_entailments"], adapter["false_contradiction_count_on_entailments"]),
        ("False entailments", base["false_entailment_count_on_contradictions"], adapter["false_entailment_count_on_contradictions"]),
    ]
    lines = [
        "# CP-009 Baseline vs LoRA Evaluation",
        "",
        f"- Acceptance: `{'PASS' if acceptance['all_pass'] else 'FAIL'}`.",
        "- Decision scope: evaluation recommendation only; adapter is not promoted.",
        "",
        "| Metric | CP-005 baseline | LoRA adapter |",
        "|---|---:|---:|",
    ]
    for name, baseline_value, adapter_value in rows:
        lines.append(f"| {name} | {baseline_value} | {adapter_value} |")
    lines.extend(["", "## Acceptance gates", ""])
    for name, check in acceptance["checks"].items():
        lines.append(f"- {'PASS' if check['passed'] else 'FAIL'} `{name}`: `{check['actual']}`; target `{check['target']}`.")
    lines.extend(["", "## Recommendation", "", comparison["recommendation"], ""])
    return "\n".join(lines)


def stage_evaluate(project_root: Path, manifest_path: Path) -> None:
    manifest = load_manifest(project_root, manifest_path)
    metrics_path = project_root / manifest["outputs"]["training_metrics"]
    require(metrics_path.is_file(), "Training metrics are missing")
    training_metrics = read_json(metrics_path)
    require(training_metrics.get("status") == "TRAINING_COMPLETE_NOT_PROMOTED", "Training did not complete")
    adapter_dir = project_root / manifest["outputs"]["adapter_dir"]
    require((adapter_dir / "adapter_model.safetensors").is_file(), "Adapter weights are missing")

    cp005 = read_json(project_root / manifest["cp005_evaluation"]["path"])
    cases = [dict(case) for case in cp005["cases"] if case["scored"] and case["label_review_status"] == "approved_unambiguous"]
    require(len(cases) == 45, "CP-005 scored case count changed")
    baseline = read_json(project_root / manifest["cp005_evaluation"]["baseline_result_path"])
    evaluation = manifest["evaluation"]
    configure_training_runtime(evaluation)

    process = psutil.Process(os.getpid())
    memory_before = memory_snapshot(process)
    sampler = ResourceSampler(interval_seconds=0.01).start()
    tokenizer = AutoTokenizer.from_pretrained(
        manifest["model"]["tokenizer_id"],
        revision=manifest["model"]["tokenizer_revision"],
        local_files_only=True,
        use_fast=True,
    )
    base_model = AutoModelForSequenceClassification.from_pretrained(
        manifest["model"]["model_id"],
        revision=manifest["model"]["revision"],
        local_files_only=True,
        torch_dtype=torch.float32,
        low_cpu_mem_usage=True,
    )
    model = PeftModel.from_pretrained(base_model, str(adapter_dir), is_trainable=False)
    model.to(device=torch.device("cpu"), dtype=torch.float32)
    model.eval()
    adapter_attached = bool(getattr(model, "peft_config", None))
    require(adapter_attached, "Adapter did not attach")
    actual_mapping = {int(key): str(value).strip().lower() for key, value in model.config.id2label.items()}
    require(actual_mapping == EXPECTED_ID2LABEL, f"Adapter model label mapping mismatch: {actual_mapping}")

    diagnostics = tokenization_diagnostics(tokenizer, cases, int(evaluation["max_length"]))
    infer_predictions(model, tokenizer, cases[: int(evaluation["batch_size"])], int(evaluation["batch_size"]), int(evaluation["max_length"]))
    inference_start = time.perf_counter_ns()
    cpu_start = time.process_time_ns()
    predictions = infer_predictions(model, tokenizer, cases, int(evaluation["batch_size"]), int(evaluation["max_length"]))
    inference_seconds = (time.perf_counter_ns() - inference_start) / 1e9
    inference_cpu_seconds = (time.process_time_ns() - cpu_start) / 1e9
    peak_rss = sampler.stop()
    memory_after = memory_snapshot(process)
    resources = {
        "method": "Fresh CPU/fp32 process; pinned local base plus adapter; one fixed first-batch warm-up excluded; batch 8; max_length 256; perf_counter_ns/process_time_ns; RSS sampled every 10ms.",
        "memory_before_load": memory_before,
        "memory_after_inference": memory_after,
        "sampled_peak_lifecycle_rss_bytes": peak_rss,
        "process_peak_working_set_bytes": memory_after["peak_working_set_bytes"],
        "inference_wall_seconds": inference_seconds,
        "inference_cpu_seconds": inference_cpu_seconds,
        "milliseconds_per_case": inference_seconds * 1000 / len(cases),
        "cases_per_second": len(cases) / inference_seconds,
    }
    metrics = build_metrics(cases, predictions)
    enriched = [{**case, **prediction} for case, prediction in zip(cases, predictions)]
    acceptance = acceptance_result(metrics, enriched, baseline, resources, manifest, adapter_attached)
    anchors = [row for row in enriched if row["regression_anchor"]]
    evaluation_result = {
        "schema_version": 1,
        "run_id": "interviewiq-nli-phase2c-cp005-adapter-eval-v1",
        "status": "EVALUATION_COMPLETE_NOT_PROMOTED",
        "manifest": {"path": relative_path(manifest_path, project_root), "sha256": sha256_file(manifest_path)},
        "dataset": {"path": manifest["cp005_evaluation"]["path"], "sha256": sha256_file(project_root / manifest["cp005_evaluation"]["path"]), "cases": len(cases)},
        "model": {"base_model_id": manifest["model"]["model_id"], "base_revision": manifest["model"]["revision"], "adapter_path": relative_path(adapter_dir, project_root), "adapter_attached": adapter_attached, "id2label": {str(k): v for k, v in actual_mapping.items()}},
        "controls": {"tokenization": diagnostics, "evaluation": evaluation, "thresholds_used": False, "production_changed": False, "promoted": False},
        "resources": resources,
        "metrics": metrics,
        "acceptance": acceptance,
        "DA017_anchors": anchors,
        "predictions": enriched,
    }
    evaluation_path = project_root / manifest["outputs"]["adapter_evaluation"]
    write_json(evaluation_path, evaluation_result)

    baseline_metrics = baseline["metrics"]["all_scored_cases"]
    adapter_metrics = metrics["all_scored_cases"]
    comparison = {
        "schema_version": 1,
        "comparison_id": "interviewiq-nli-phase2c-baseline-vs-lora-v1",
        "decision": "ACCEPTANCE_PASS_RECOMMEND_FURTHER_PROMOTION_REVIEW" if acceptance["all_pass"] else "ACCEPTANCE_FAIL_DO_NOT_PROMOTE",
        "baseline": {"source": manifest["cp005_evaluation"]["baseline_result_path"], "sha256": sha256_file(project_root / manifest["cp005_evaluation"]["baseline_result_path"]), "metrics": baseline_metrics, "DA017": baseline["metrics"]["DA017_regression_anchors"]},
        "adapter": {"source": manifest["outputs"]["adapter_evaluation"], "metrics": adapter_metrics, "DA017": metrics["DA017_regression_anchors"], "resources": resources},
        "deltas": {
            "accuracy": adapter_metrics["accuracy"] - baseline_metrics["accuracy"],
            "macro_f1": adapter_metrics["macro_f1"] - baseline_metrics["macro_f1"],
            "false_contradiction_count": adapter_metrics["false_contradiction_count_on_entailments"] - baseline_metrics["false_contradiction_count_on_entailments"],
            "false_entailment_count": adapter_metrics["false_entailment_count_on_contradictions"] - baseline_metrics["false_entailment_count_on_contradictions"],
        },
        "language_slices": metrics["by_language_style"],
        "difficulty_slices": metrics["by_difficulty_type"],
        "DA017_anchors": anchors,
        "acceptance": acceptance,
        "recommendation": "Adapter passed all predeclared gates, but production promotion requires separate authorization." if acceptance["all_pass"] else "Do not promote the adapter because one or more predeclared gates failed. Preserve it as experiment evidence only.",
        "scope": {"production_changed": False, "promoted": False, "second_adapter_trained": False},
    }
    comparison_path = project_root / manifest["outputs"]["comparison"]
    write_json(comparison_path, comparison)
    report_path = project_root / manifest["outputs"]["comparison_report"]
    report_path.write_text(render_report(comparison), encoding="utf-8", newline="\n")

    hash_targets = [
        manifest_path,
        project_root / manifest["human_review_attestation"]["path"],
        project_root / manifest["outputs"]["preflight"],
        metrics_path,
        project_root / manifest["outputs"]["training_log"],
        project_root / manifest["outputs"]["environment"],
        evaluation_path,
        comparison_path,
        report_path,
        Path(__file__).resolve(),
        *[path for path in adapter_dir.rglob("*") if path.is_file()],
    ]
    artifact_hashes = {
        "schema_version": 1,
        "status": "FROZEN_NOT_PROMOTED",
        "files": {
            relative_path(path, project_root): {"sha256": sha256_file(path), "bytes": path.stat().st_size}
            for path in sorted(set(hash_targets))
        },
    }
    hashes_path = project_root / manifest["outputs"]["artifact_hashes"]
    write_json(hashes_path, artifact_hashes)
    print("PHASE2C_EVALUATION=COMPLETE")
    print(f"ACCEPTANCE_ALL_PASS={acceptance['all_pass']}")
    print(f"ACCURACY={adapter_metrics['accuracy']}")
    print(f"MACRO_F1={adapter_metrics['macro_f1']}")
    print(f"FALSE_CONTRADICTIONS={adapter_metrics['false_contradiction_count_on_entailments']}")
    print(f"FALSE_ENTAILMENTS={adapter_metrics['false_entailment_count_on_contradictions']}")
    print(f"DA017_CORRECT={round(metrics['DA017_regression_anchors']['accuracy'] * metrics['DA017_regression_anchors']['support'])}/5")
    print(f"COMPARISON_SHA256={sha256_file(comparison_path)}")

    del model
    del base_model
    del tokenizer
    gc.collect()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CP-009 one-LoRA controlled training/evaluation")
    parser.add_argument("stage", choices=("preflight", "train", "evaluate"))
    parser.add_argument("--manifest", type=Path, default=None)
    args = parser.parse_args(argv)
    project_root = Path(__file__).resolve().parents[2]
    manifest_path = args.manifest or (project_root / "results/nli_phase2c_training_cp009/immutable_training_manifest_v1.json")
    try:
        if args.stage == "preflight":
            stage_preflight(project_root, manifest_path)
        elif args.stage == "train":
            stage_train(project_root, manifest_path)
        else:
            stage_evaluate(project_root, manifest_path)
    except Exception as exc:
        print(f"PHASE2C_{args.stage.upper()}=FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
