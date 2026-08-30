"""Reproducible CP-005 checkpoint-control evaluation.

This module is deliberately isolated from production scoring.  It validates the
frozen CP-005 dataset and an immutable experiment manifest, loads one pinned NLI
checkpoint in CPU/fp32 mode, and emits auditable metrics and resource evidence.
It never trains, attaches an adapter, changes thresholds, or selects a winner.
"""

from __future__ import annotations

import gc
import hashlib
import json
import os
import platform
import random
import re
import threading
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from importlib import metadata
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

import numpy as np
import psutil
import torch
from huggingface_hub import hf_hub_download
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from interview_iq.nli.common import EXPECTED_ID2LABEL


LABEL_ORDER: tuple[str, ...] = ("entailment", "neutral", "contradiction")
IMMUTABLE_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
AUTHORIZED_MODELS = {
    "baseline": "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
    "candidate": "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7",
}
REQUIRED_CASE_KEYS = {
    "case_id",
    "source_question_id",
    "source_reference_id",
    "premise",
    "hypothesis",
    "expected_label",
    "language_style",
    "difficulty_type",
    "regression_anchor",
    "scored",
    "label_review_status",
}


class CheckpointControlError(RuntimeError):
    """A hard experiment-control invariant failed."""


def now_cairo() -> str:
    return datetime.now(ZoneInfo("Africa/Cairo")).isoformat()


def sha256_file(path: Path) -> str:
    """Return the SHA-256 of the file's exact bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def sha256_text_file(path: Path) -> str:
    """Hash text bytes after canonicalizing only line endings to LF.

    The frozen CP-005 dataset digest was declared from an LF checkout. This
    explicit helper keeps that text contract portable while ``sha256_file``
    continues to protect model snapshots and generated artifacts byte-for-byte.
    """
    payload = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(payload).hexdigest().upper()


def _matches_historical_text_hash(path: Path, expected_sha: str) -> bool:
    """Accept a historical text digest under LF or CRLF checkout semantics.

    CP-005 recorded two repository JSON digests on different operating systems.
    Integrity remains strict: the only accepted byte transformation is newline
    normalization; all other bytes must be identical.
    """
    payload = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    variants = {
        hashlib.sha256(payload).hexdigest().upper(),
        hashlib.sha256(payload.replace(b"\n", b"\r\n")).hexdigest().upper(),
    }
    return expected_sha in variants


def sha256_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CheckpointControlError(f"Cannot read strict UTF-8 JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CheckpointControlError(f"Expected a JSON object at {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def normalize_overlap_text(text: str) -> str:
    """Conservative exact-overlap normalization for leakage checks.

    NFKC, case folding, Arabic-diacritic/tatweel removal, punctuation removal,
    and whitespace collapse catch cosmetic variants without attempting semantic
    similarity.  Semantic-family review remains a separate human gate.
    """

    normalized = unicodedata.normalize("NFKC", str(text)).casefold().replace("\u0640", "")
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    tokens = re.findall(r"\w+", normalized, flags=re.UNICODE)
    return " ".join(tokens)


def normalized_pair(premise: str, hypothesis: str) -> tuple[str, str]:
    return normalize_overlap_text(premise), normalize_overlap_text(hypothesis)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckpointControlError(message)


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    _require(manifest.get("schema_version") == 1, "Manifest schema_version must be 1")
    _require(
        manifest.get("experiment_id") == "interviewiq-nli-phase2a-checkpoint-control-v1",
        "Unexpected experiment_id",
    )
    _require(
        manifest.get("decision_scope") == "PHASE_2A_EVALUATION_ONLY_NO_TRAINING",
        "Manifest must be Phase-2A evaluation-only",
    )
    _require(manifest.get("training_authorized") is False, "Manifest must explicitly forbid training")
    _require(manifest.get("production_change_authorized") is False, "Manifest must forbid production changes")
    _require(manifest.get("automatic_model_selection") is False, "Manifest must forbid automatic model selection")

    dataset = manifest.get("dataset") or {}
    _require(bool(dataset.get("path")), "Manifest dataset.path is required")
    _require(bool(dataset.get("dataset_id")), "Manifest dataset.dataset_id is required")
    _require(bool(re.fullmatch(r"[0-9A-F]{64}", str(dataset.get("sha256", "")))), "Dataset SHA must be uppercase SHA-256")
    _require(int(dataset.get("scored_cases", 0)) == 45, "CP-005 manifest must freeze 45 scored cases")

    contract = manifest.get("metrics_contract") or {}
    _require(contract.get("path") == "data/nli/evaluation/baseline_metrics_contract_v1.json", "Unexpected metrics-contract path")
    _require(bool(re.fullmatch(r"[0-9A-F]{64}", str(contract.get("sha256", "")))), "Metrics-contract SHA is invalid")
    _require(contract.get("status") == "PREDECLARED_BEFORE_INFERENCE", "Metrics contract was not predeclared")
    baseline_reference = manifest.get("baseline_reference_result") or {}
    _require(
        baseline_reference.get("path") == "results/nli_baseline_cp005/current_model_baseline_v1.json",
        "Unexpected CP-005 baseline-reference path",
    )
    _require(bool(re.fullmatch(r"[0-9A-F]{64}", str(baseline_reference.get("sha256", "")))), "Baseline-reference SHA is invalid")

    inference = manifest.get("inference") or {}
    expected_controls = {
        "device": "cpu",
        "dtype": "float32",
        "max_length": 256,
        "batch_size": 8,
        "seed": 42,
        "deterministic_algorithms": True,
        "adapter": None,
        "thresholds_used": False,
        "local_files_only": True,
    }
    for key, expected in expected_controls.items():
        _require(inference.get(key) == expected, f"Manifest inference.{key} must be {expected!r}")
    _require(int(inference.get("torch_num_threads", 0)) > 0, "torch_num_threads must be positive")
    _require(int(inference.get("torch_num_interop_threads", 0)) > 0, "torch_num_interop_threads must be positive")
    _require(tuple(inference.get("label_order", ())) == LABEL_ORDER, "Label order must be E/N/C")
    _require(inference.get("premise") == "canonical reference evidence text", "Premise direction changed")
    _require(inference.get("hypothesis") == "candidate answer claim", "Hypothesis direction changed")

    models = manifest.get("models") or {}
    _require(set(models) == {"baseline", "candidate"}, "Manifest must contain baseline and candidate models")
    for key, spec in models.items():
        for required in ("model_id", "revision", "tokenizer_id", "tokenizer_revision", "snapshot_files"):
            _require(bool(spec.get(required)), f"models.{key}.{required} is required")
        _require(IMMUTABLE_REVISION_RE.fullmatch(spec["revision"]) is not None, f"models.{key}.revision is mutable/invalid")
        _require(spec["model_id"] == AUTHORIZED_MODELS[key], f"models.{key}.model_id is not the authorized checkpoint")
        _require(spec["tokenizer_id"] == spec["model_id"], f"models.{key}.tokenizer_id must equal model_id")
        _require(
            IMMUTABLE_REVISION_RE.fullmatch(spec["tokenizer_revision"]) is not None,
            f"models.{key}.tokenizer_revision is mutable/invalid",
        )
        _require(spec["tokenizer_revision"] == spec["revision"], f"models.{key} tokenizer/model revisions differ")
        _require(isinstance(spec["snapshot_files"], dict) and spec["snapshot_files"], f"models.{key}.snapshot_files is empty")
        for filename, expected_sha in spec["snapshot_files"].items():
            _require(bool(filename), f"models.{key} has an empty snapshot filename")
            _require(bool(re.fullmatch(r"[0-9A-F]{64}", expected_sha)), f"Invalid SHA for models.{key}.{filename}")
        snapshot_names = set(spec["snapshot_files"])
        _require("config.json" in snapshot_names, f"models.{key} must pin config.json")
        _require(bool(snapshot_names & {"model.safetensors", "pytorch_model.bin"}), f"models.{key} must pin model weights")
        _require("tokenizer_config.json" in snapshot_names, f"models.{key} must pin tokenizer_config.json")
        _require(bool(snapshot_names & {"tokenizer.json", "spm.model"}), f"models.{key} must pin tokenizer material")

    leakage = manifest.get("leakage_controls") or {}
    protected = leakage.get("protected_question_ids") or []
    _require(len(protected) == 10 and len(set(protected)) == 10, "Exactly ten CP-005 question IDs must be protected")
    _require(leakage.get("reject_question_id_overlap") is True, "Question-ID leakage rejection is required")
    _require(leakage.get("reject_pair_overlap") is True, "Pair-overlap rejection is required")
    _require(leakage.get("reject_premise_overlap") is True, "Premise-overlap rejection is required")
    _require(leakage.get("reject_hypothesis_overlap") is True, "Hypothesis-overlap rejection is required")
    _require(leakage.get("reject_duplicate_training_pairs") is True, "Duplicate training-pair rejection is required")
    _require(
        leakage.get("training_manifest_record_format") == "inline premise/hypothesis records required",
        "Future training-manifest record format must be explicit",
    )
    outputs = manifest.get("outputs") or {}
    required_outputs = {"preflight", "baseline", "candidate", "comparison_json", "comparison_markdown", "independent_validation"}
    _require(required_outputs <= set(outputs), f"Manifest outputs missing {sorted(required_outputs - set(outputs))}")
    _require(all(isinstance(outputs[key], str) and outputs[key] for key in required_outputs), "Manifest output paths must be nonempty strings")


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = read_json(path)
    validate_manifest(manifest)
    return manifest


def verify_snapshot_files(model_spec: Mapping[str, Any]) -> dict[str, Any]:
    verified: dict[str, Any] = {}
    for filename, expected_sha in model_spec["snapshot_files"].items():
        try:
            cached = Path(
                hf_hub_download(
                    repo_id=model_spec["model_id"],
                    filename=filename,
                    revision=model_spec["revision"],
                    local_files_only=True,
                )
            )
        except Exception as exc:
            raise CheckpointControlError(
                f"Pinned snapshot file is not available locally: {model_spec['model_id']}@{model_spec['revision']}:{filename}"
            ) from exc
        actual_sha = sha256_file(cached)
        _require(actual_sha == expected_sha, f"Snapshot hash mismatch for {filename}: expected {expected_sha}, got {actual_sha}")
        verified[filename] = {"sha256": actual_sha, "bytes": cached.stat().st_size}
    return verified


def load_and_validate_dataset(project_root: Path, manifest: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    dataset_spec = manifest["dataset"]
    dataset_path = (project_root / dataset_spec["path"]).resolve()
    _require(dataset_path.is_file(), f"Frozen dataset is missing: {dataset_path}")
    actual_sha = sha256_text_file(dataset_path)
    _require(actual_sha == dataset_spec["sha256"], f"Frozen dataset SHA mismatch: expected {dataset_spec['sha256']}, got {actual_sha}")

    raw = read_json(dataset_path)
    _require(raw.get("dataset_id") == dataset_spec["dataset_id"], "Dataset ID does not match manifest")
    _require(raw.get("do_not_train") is True, "Frozen dataset must declare do_not_train=true")
    raw_cases = raw.get("cases")
    _require(isinstance(raw_cases, list), "Frozen dataset cases must be a list")
    cases: list[dict[str, Any]] = []
    for index, case in enumerate(raw_cases):
        _require(isinstance(case, dict), f"cases[{index}] is not an object")
        missing = REQUIRED_CASE_KEYS - case.keys()
        _require(not missing, f"cases[{index}] missing fields {sorted(missing)}")
        if case["scored"] and case["label_review_status"] == "approved_unambiguous":
            _require(case["expected_label"] in LABEL_ORDER, f"Invalid expected label in {case['case_id']}")
            cases.append(dict(case))
    _require(len(cases) == dataset_spec["scored_cases"], "Scored-case count does not match manifest")

    ids = [case["case_id"] for case in cases]
    duplicate_ids = sorted(case_id for case_id, count in Counter(ids).items() if count > 1)
    _require(not duplicate_ids, f"Duplicate evaluation case IDs: {duplicate_ids}")

    pairs = [normalized_pair(case["premise"], case["hypothesis"]) for case in cases]
    duplicate_pairs = sorted(pair for pair, count in Counter(pairs).items() if count > 1)
    _require(not duplicate_pairs, f"Duplicate normalized evaluation pairs: {duplicate_pairs[:5]}")

    hypotheses = [normalize_overlap_text(case["hypothesis"]) for case in cases]
    duplicate_hypotheses = sorted(text for text, count in Counter(hypotheses).items() if count > 1)
    _require(not duplicate_hypotheses, f"Duplicate normalized evaluation hypotheses: {duplicate_hypotheses[:5]}")

    protected = set(manifest["leakage_controls"]["protected_question_ids"])
    actual_question_ids = {case["source_question_id"] for case in cases}
    _require(actual_question_ids == protected, f"Protected question IDs do not exactly match dataset IDs: {sorted(actual_question_ids)}")

    premise_counts = Counter(normalize_overlap_text(case["premise"]) for case in cases)
    repeated_premises = {text: count for text, count in premise_counts.items() if count > 1}
    controls = {
        "dataset_sha256_verified": True,
        "dataset_id_verified": True,
        "do_not_train_verified": True,
        "scored_cases": len(cases),
        "unique_case_ids": len(ids),
        "unique_normalized_pairs": len(pairs),
        "unique_normalized_hypotheses": len(hypotheses),
        "protected_question_ids": sorted(actual_question_ids),
        "intentional_repeated_premise_groups": len(repeated_premises),
        "intentional_repeated_premise_case_count": sum(repeated_premises.values()),
    }
    return raw, cases, controls


def _walk_training_records(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if "premise" in value and "hypothesis" in value:
            yield value
        for child in value.values():
            yield from _walk_training_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_training_records(child)


def validate_training_separation(
    eval_cases: Sequence[Mapping[str, Any]],
    protected_question_ids: set[str],
    training_manifests: Sequence[tuple[Path, Mapping[str, Any]]],
    eval_dataset_path: Path | None = None,
) -> dict[str, Any]:
    """Validate present/future training manifests against the CP-005 boundary."""

    if not training_manifests:
        return {
            "status": "NO_TRAINING_MANIFEST_PRESENT",
            "control_ready": True,
            "manifests_checked": 0,
            "claim_limit": "No future training data was available; policy readiness was tested, not future-data cleanliness.",
        }

    eval_pairs = {normalized_pair(case["premise"], case["hypothesis"]) for case in eval_cases}
    eval_premises = {normalize_overlap_text(case["premise"]) for case in eval_cases}
    eval_hypotheses = {normalize_overlap_text(case["hypothesis"]) for case in eval_cases}
    all_records: list[tuple[str, Mapping[str, Any]]] = []

    for path, manifest in training_manifests:
        if eval_dataset_path is not None:
            _require(path.resolve() != eval_dataset_path.resolve(), "Evaluation dataset cannot be supplied as a training manifest")
        records = list(_walk_training_records(manifest))
        _require(records, f"Training manifest {path} contains no inline premise/hypothesis records")
        all_records.extend((str(path), record) for record in records)

    training_pairs: list[tuple[str, str]] = []
    protected_hits: list[str] = []
    pair_hits: list[str] = []
    premise_hits: list[str] = []
    hypothesis_hits: list[str] = []
    identifiers: list[str] = []
    for index, (source, record) in enumerate(all_records):
        record_id = str(record.get("pair_id") or record.get("case_id") or f"{source}#{index}")
        identifiers.append(record_id)
        question_id = str(record.get("question_id") or record.get("source_question_id") or "")
        if question_id in protected_question_ids:
            protected_hits.append(record_id)
        pair = normalized_pair(str(record["premise"]), str(record["hypothesis"]))
        training_pairs.append(pair)
        if pair in eval_pairs:
            pair_hits.append(record_id)
        if pair[0] in eval_premises:
            premise_hits.append(record_id)
        if pair[1] in eval_hypotheses:
            hypothesis_hits.append(record_id)

    duplicate_training_pairs = sorted(pair for pair, count in Counter(training_pairs).items() if count > 1)
    problems = {
        "protected_question_id_hits": protected_hits,
        "evaluation_pair_overlap_hits": pair_hits,
        "evaluation_premise_overlap_hits": premise_hits,
        "evaluation_hypothesis_overlap_hits": hypothesis_hits,
        "duplicate_training_pair_count": len(duplicate_training_pairs),
    }
    _require(not any(problems.values()), f"Training/evaluation leakage detected: {problems}")
    return {
        "status": "PASS",
        "control_ready": True,
        "manifests_checked": len(training_manifests),
        "records_checked": len(all_records),
        **problems,
    }


def compute_metrics(gold: Sequence[str], predicted: Sequence[str]) -> dict[str, Any]:
    _require(len(gold) == len(predicted) and len(gold) > 0, "Metric inputs must have equal, nonzero lengths")
    for label in [*gold, *predicted]:
        _require(label in LABEL_ORDER, f"Unexpected metric label: {label}")

    cm = {g: {p: 0 for p in LABEL_ORDER} for g in LABEL_ORDER}
    for expected, actual in zip(gold, predicted):
        cm[expected][actual] += 1

    per_class: dict[str, dict[str, float | int]] = {}
    for label in LABEL_ORDER:
        tp = cm[label][label]
        fp = sum(cm[other][label] for other in LABEL_ORDER if other != label)
        fn = sum(cm[label][other] for other in LABEL_ORDER if other != label)
        support = sum(cm[label].values())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1, "support": support}

    accuracy = sum(expected == actual for expected, actual in zip(gold, predicted)) / len(gold)
    e_support = int(per_class["entailment"]["support"])
    c_support = int(per_class["contradiction"]["support"])
    e_to_c = cm["entailment"]["contradiction"]
    c_to_e = cm["contradiction"]["entailment"]
    return {
        "support": len(gold),
        "accuracy": accuracy,
        "per_class": per_class,
        "macro_f1": sum(float(per_class[label]["f1"]) for label in LABEL_ORDER) / len(LABEL_ORDER),
        "confusion_matrix": cm,
        "confusion_matrix_orientation": "rows=expected_label, columns=predicted_label",
        "false_contradiction_count_on_entailments": e_to_c,
        "false_contradiction_rate_on_entailments": e_to_c / e_support if e_support else 0.0,
        "false_entailment_count_on_contradictions": c_to_e,
        "false_entailment_rate_on_contradictions": c_to_e / c_support if c_support else 0.0,
    }


def build_metrics(cases: Sequence[Mapping[str, Any]], predictions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    _require(len(cases) == len(predictions) and len(cases) > 0, "Cases/predictions must have equal, nonzero lengths")
    case_ids = [case["case_id"] for case in cases]
    prediction_ids = [prediction["case_id"] for prediction in predictions]
    _require(case_ids == prediction_ids, "Prediction order/IDs do not match the frozen dataset")

    def subset(indices: Sequence[int]) -> dict[str, Any]:
        return compute_metrics(
            [cases[index]["expected_label"] for index in indices],
            [predictions[index]["predicted_label"] for index in indices],
        )

    all_indices = list(range(len(cases)))
    discovery = [index for index, case in enumerate(cases) if not case["regression_anchor"]]
    anchors = [index for index, case in enumerate(cases) if case["regression_anchor"]]
    result: dict[str, Any] = {
        "all_scored_cases": subset(all_indices),
        "heldout_discovery_only": subset(discovery),
        "DA017_regression_anchors": subset(anchors),
    }
    for field, output_key in (("language_style", "by_language_style"), ("difficulty_type", "by_difficulty_type")):
        groups: dict[str, list[int]] = defaultdict(list)
        for index, case in enumerate(cases):
            groups[str(case[field])].append(index)
        result[output_key] = {name: subset(indices) for name, indices in sorted(groups.items())}
    return result


def evaluate_acceptance(metrics: Mapping[str, Any], contract: Mapping[str, Any]) -> dict[str, Any]:
    target = contract["proposed_remediation_acceptance_target"]
    overall = metrics["all_scored_cases"]
    anchors = metrics["DA017_regression_anchors"]
    checks: dict[str, dict[str, Any]] = {}

    def add(name: str, actual: Any, target_text: str, passed: bool) -> None:
        checks[name] = {"actual": actual, "target": target_text, "passed": bool(passed)}

    add("overall_accuracy", overall["accuracy"], f">={target['overall_accuracy_min']}", overall["accuracy"] >= target["overall_accuracy_min"])
    add("macro_f1", overall["macro_f1"], f">={target['macro_f1_min']}", overall["macro_f1"] >= target["macro_f1_min"])
    minimum_class_f1 = min(float(overall["per_class"][label]["f1"]) for label in LABEL_ORDER)
    add("minimum_per_class_f1", minimum_class_f1, f">={target['per_class_f1_min']}", minimum_class_f1 >= target["per_class_f1_min"])
    add(
        "false_contradiction_rate",
        overall["false_contradiction_rate_on_entailments"],
        f"<={target['false_contradiction_rate_on_entailments_max']}",
        overall["false_contradiction_rate_on_entailments"] <= target["false_contradiction_rate_on_entailments_max"],
    )
    add(
        "false_entailment_rate",
        overall["false_entailment_rate_on_contradictions"],
        f"<={target['false_entailment_rate_on_contradictions_max']}",
        overall["false_entailment_rate_on_contradictions"] <= target["false_entailment_rate_on_contradictions_max"],
    )
    anchor_correct = round(anchors["accuracy"] * anchors["support"])
    add("DA017_anchors", f"{anchor_correct}/{anchors['support']}", target["DA-017_regression_anchors_required_correct"], anchor_correct == anchors["support"])

    eligible_slices: dict[str, float] = {}
    for group_name in ("by_language_style", "by_difficulty_type"):
        for slice_name, slice_metrics in metrics[group_name].items():
            if slice_metrics["support"] >= 5:
                eligible_slices[f"{group_name}.{slice_name}"] = slice_metrics["accuracy"]
    minimum_slice = min(eligible_slices.values()) if eligible_slices else 1.0
    add(
        "minimum_supported_slice_accuracy",
        minimum_slice,
        f">={target['minimum_slice_accuracy_when_support_at_least_5']}",
        minimum_slice >= target["minimum_slice_accuracy_when_support_at_least_5"],
    )
    return {
        "approval_status": target["approval_status"],
        "checks": checks,
        "all_pass": all(check["passed"] for check in checks.values()),
        "decision_limit": "Evaluation evidence only; no automatic model selection or production change.",
    }


class ResourceSampler:
    def __init__(self, interval_seconds: float = 0.01) -> None:
        self.process = psutil.Process(os.getpid())
        self.interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.peak_rss = 0

    def _sample(self) -> None:
        while not self._stop.is_set():
            try:
                self.peak_rss = max(self.peak_rss, int(self.process.memory_info().rss))
            except psutil.Error:
                pass
            self._stop.wait(self.interval_seconds)

    def start(self) -> "ResourceSampler":
        self.peak_rss = int(self.process.memory_info().rss)
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> int:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        try:
            self.peak_rss = max(self.peak_rss, int(self.process.memory_info().rss))
        except psutil.Error:
            pass
        return self.peak_rss


def memory_snapshot(process: psutil.Process) -> dict[str, int | None]:
    basic = process.memory_info()
    try:
        full = process.memory_full_info()
    except (psutil.Error, AttributeError):
        full = basic
    return {
        "rss_bytes": int(basic.rss),
        "uss_bytes": int(getattr(full, "uss", 0)) or None,
        "private_bytes": int(getattr(full, "private", 0)) or None,
        "peak_working_set_bytes": int(getattr(basic, "peak_wset", 0)) or None,
    }


def configure_deterministic_cpu(inference: Mapping[str, Any]) -> None:
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    seed = int(inference["seed"])
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(int(inference["torch_num_threads"]))
    try:
        torch.set_num_interop_threads(int(inference["torch_num_interop_threads"]))
    except RuntimeError as exc:
        raise CheckpointControlError(f"Cannot pin torch inter-op threads in this process: {exc}") from exc
    torch.use_deterministic_algorithms(True)


def tokenizer_identity(tokenizer: Any, model_spec: Mapping[str, Any]) -> dict[str, Any]:
    vocab = tokenizer.get_vocab()
    vocab_digest = hashlib.sha256()
    for token, token_id in sorted(vocab.items(), key=lambda item: (item[1], item[0])):
        vocab_digest.update(str(token_id).encode("ascii"))
        vocab_digest.update(b"\0")
        vocab_digest.update(token.encode("utf-8"))
        vocab_digest.update(b"\n")
    return {
        "requested_id": model_spec["tokenizer_id"],
        "requested_revision": model_spec["tokenizer_revision"],
        "class": type(tokenizer).__name__,
        "is_fast": bool(getattr(tokenizer, "is_fast", False)),
        "vocab_size": int(getattr(tokenizer, "vocab_size", len(vocab))),
        "effective_vocab_entries": len(vocab),
        "vocab_sha256": vocab_digest.hexdigest().upper(),
        "special_tokens_map": tokenizer.special_tokens_map,
        "all_special_ids": list(tokenizer.all_special_ids),
        "model_max_length": int(tokenizer.model_max_length),
    }


def tokenization_diagnostics(tokenizer: Any, cases: Sequence[Mapping[str, Any]], max_length: int) -> dict[str, Any]:
    lengths: list[int] = []
    over_length: list[str] = []
    unk_cases: list[str] = []
    unk_id = tokenizer.unk_token_id
    for case in cases:
        encoded = tokenizer(case["premise"], case["hypothesis"], truncation=False, add_special_tokens=True)
        ids = encoded["input_ids"]
        lengths.append(len(ids))
        if len(ids) > max_length:
            over_length.append(case["case_id"])
        if unk_id is not None and unk_id in ids:
            unk_cases.append(case["case_id"])
    return {
        "max_untruncated_pair_tokens": max(lengths),
        "over_max_length_case_ids": over_length,
        "unknown_token_case_ids": unk_cases,
        "truncation_occurred": bool(over_length),
    }


@torch.inference_mode()
def infer_predictions(
    model: Any,
    tokenizer: Any,
    cases: Sequence[Mapping[str, Any]],
    batch_size: int,
    max_length: int,
) -> list[dict[str, Any]]:
    id2label = {int(key): str(value).strip().lower() for key, value in model.config.id2label.items()}
    _require(id2label == EXPECTED_ID2LABEL, f"Model label mapping mismatch: {id2label}")
    results: list[dict[str, Any]] = []
    for start in range(0, len(cases), batch_size):
        batch = cases[start : start + batch_size]
        inputs = tokenizer(
            [case["premise"] for case in batch],
            [case["hypothesis"] for case in batch],
            truncation=True,
            padding=True,
            max_length=max_length,
            return_tensors="pt",
        )
        _require(all(tensor.device.type == "cpu" for tensor in inputs.values()), "Tokenizer produced non-CPU tensors")
        logits = model(**inputs).logits
        probabilities = torch.softmax(logits, dim=-1).cpu().tolist()
        predicted_ids = logits.argmax(dim=-1).cpu().tolist()
        for case, row, predicted_id in zip(batch, probabilities, predicted_ids):
            predicted_label = id2label[predicted_id]
            results.append(
                {
                    "case_id": case["case_id"],
                    "expected_label": case["expected_label"],
                    "predicted_label": predicted_label,
                    "correct": predicted_label == case["expected_label"],
                    "error_direction": None if predicted_label == case["expected_label"] else f"{case['expected_label']}->{predicted_label}",
                    "probabilities": {LABEL_ORDER[index]: round(float(row[index]), 6) for index in range(3)},
                }
            )
    _require(len(results) == len(cases), "Inference returned the wrong number of predictions")
    return results


def package_versions() -> dict[str, str]:
    names = ("torch", "transformers", "tokenizers", "huggingface-hub", "numpy", "psutil", "safetensors")
    versions: dict[str, str] = {}
    for name in names:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "NOT_INSTALLED"
    return versions


def evaluate_checkpoint(
    project_root: Path,
    manifest_path: Path,
    model_key: str,
    training_manifest_paths: Sequence[Path] = (),
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    _require(model_key in ("baseline", "candidate"), "model_key must be baseline or candidate")
    dataset_raw, cases, dataset_controls = load_and_validate_dataset(project_root, manifest)
    dataset_path = (project_root / manifest["dataset"]["path"]).resolve()
    contract_path = (project_root / manifest["metrics_contract"]["path"]).resolve()
    _require(
        _matches_historical_text_hash(contract_path, manifest["metrics_contract"]["sha256"]),
        "Metrics-contract SHA mismatch",
    )
    contract = read_json(contract_path)
    training_manifests = [(path, read_json(path)) for path in training_manifest_paths]
    separation = validate_training_separation(
        cases,
        set(manifest["leakage_controls"]["protected_question_ids"]),
        training_manifests,
        eval_dataset_path=dataset_path,
    )

    inference = manifest["inference"]
    configure_deterministic_cpu(inference)
    model_spec = manifest["models"][model_key]
    snapshot_files = verify_snapshot_files(model_spec)

    process = psutil.Process(os.getpid())
    memory_before = memory_snapshot(process)
    lifecycle_sampler = ResourceSampler().start()
    load_sampler = ResourceSampler().start()
    tokenizer_start = time.perf_counter_ns()
    tokenizer = AutoTokenizer.from_pretrained(
        model_spec["tokenizer_id"],
        revision=model_spec["tokenizer_revision"],
        local_files_only=True,
        use_fast=True,
    )
    tokenizer_seconds = (time.perf_counter_ns() - tokenizer_start) / 1e9
    model_start = time.perf_counter_ns()
    model = AutoModelForSequenceClassification.from_pretrained(
        model_spec["model_id"],
        revision=model_spec["revision"],
        local_files_only=True,
        torch_dtype=torch.float32,
    )
    model.to(device=torch.device("cpu"), dtype=torch.float32)
    model.eval()
    model_seconds = (time.perf_counter_ns() - model_start) / 1e9
    peak_load_rss = load_sampler.stop()
    memory_after_load = memory_snapshot(process)

    actual_mapping = {int(key): str(value).strip().lower() for key, value in model.config.id2label.items()}
    _require(actual_mapping == EXPECTED_ID2LABEL, f"Model label mapping mismatch: {actual_mapping}")
    _require(not bool(getattr(model, "peft_config", None)), "An adapter is attached; Phase 2A forbids adapters")
    floating_dtypes = {parameter.dtype for parameter in model.parameters() if parameter.is_floating_point()}
    devices = {parameter.device.type for parameter in model.parameters()}
    _require(floating_dtypes == {torch.float32}, f"Model is not uniformly fp32: {floating_dtypes}")
    _require(devices == {"cpu"}, f"Model is not uniformly on CPU: {devices}")
    diagnostics = tokenization_diagnostics(tokenizer, cases, int(inference["max_length"]))

    # Identical fixed warm-up for both fresh worker processes; excluded from timed inference.
    warmup_start = time.perf_counter_ns()
    infer_predictions(model, tokenizer, cases[: int(inference["batch_size"])], int(inference["batch_size"]), int(inference["max_length"]))
    warmup_seconds = (time.perf_counter_ns() - warmup_start) / 1e9

    inference_sampler = ResourceSampler().start()
    cpu_start = time.process_time_ns()
    wall_start = time.perf_counter_ns()
    predictions = infer_predictions(
        model,
        tokenizer,
        cases,
        int(inference["batch_size"]),
        int(inference["max_length"]),
    )
    inference_wall_seconds = (time.perf_counter_ns() - wall_start) / 1e9
    inference_cpu_seconds = (time.process_time_ns() - cpu_start) / 1e9
    peak_inference_rss = inference_sampler.stop()
    memory_after_inference = memory_snapshot(process)
    peak_lifecycle_rss = lifecycle_sampler.stop()

    metrics = build_metrics(cases, predictions)
    acceptance = evaluate_acceptance(metrics, contract)
    enriched_predictions: list[dict[str, Any]] = []
    for case, prediction in zip(cases, predictions):
        enriched_predictions.append(
            {
                **case,
                **prediction,
            }
        )

    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    parameter_bytes = sum(parameter.numel() * parameter.element_size() for parameter in model.parameters())
    model_identity = {
        "role": model_key,
        "requested_model_id": model_spec["model_id"],
        "requested_revision": model_spec["revision"],
        "config_commit_hash": getattr(model.config, "_commit_hash", None),
        "class": type(model).__name__,
        "id2label": {str(key): value for key, value in actual_mapping.items()},
        "parameter_count": parameter_count,
        "parameter_bytes_fp32": parameter_bytes,
        "config_sha256": sha256_json(model.config.to_dict()),
        "snapshot_files": snapshot_files,
    }
    tokenizer_info = tokenizer_identity(tokenizer, model_spec)

    del model
    del tokenizer
    gc.collect()

    return {
        "schema_version": 1,
        "run_id": f"cp006-{model_key}-checkpoint-control-v1",
        "created_at": now_cairo(),
        "decision_scope": "PHASE_2A_EVALUATION_ONLY_NO_TRAINING_NO_AUTOMATIC_WINNER",
        "manifest": {
            "path": str(manifest_path.relative_to(project_root)).replace("\\", "/") if manifest_path.is_relative_to(project_root) else str(manifest_path),
            "sha256": sha256_file(manifest_path),
            "experiment_id": manifest["experiment_id"],
        },
        "dataset": {
            "path": manifest["dataset"]["path"],
            "dataset_id": dataset_raw["dataset_id"],
            "sha256": manifest["dataset"]["sha256"],
            "scored_cases": len(cases),
            "heldout_discovery_cases": sum(not case["regression_anchor"] for case in cases),
            "regression_anchors": sum(bool(case["regression_anchor"]) for case in cases),
        },
        "experiment_controls": {
            "dataset_validation": dataset_controls,
            "training_separation": separation,
            "inference": inference,
            "tokenization": diagnostics,
        },
        "model": model_identity,
        "tokenizer": tokenizer_info,
        "runtime": {
            "device": "cpu",
            "dtype": "torch.float32",
            "eval_mode": True,
            "adapter": None,
            "deterministic_algorithms_enabled": torch.are_deterministic_algorithms_enabled(),
            "seed": inference["seed"],
            "torch_num_threads": torch.get_num_threads(),
            "torch_num_interop_threads": torch.get_num_interop_threads(),
            "batch_size": inference["batch_size"],
            "max_length": inference["max_length"],
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "logical_cpu_count": psutil.cpu_count(logical=True),
            "physical_cpu_count": psutil.cpu_count(logical=False),
            "packages": package_versions(),
        },
        "resources": {
            "method": "Fresh process per model; pinned local snapshot; one fixed-batch warm-up excluded from timed 45-case inference; perf_counter_ns/process_time_ns; psutil RSS sampled every 10ms and Windows cumulative peak working set.",
            "memory_before_load": memory_before,
            "memory_after_load": memory_after_load,
            "memory_after_inference": memory_after_inference,
            "sampled_peak_load_rss_bytes": peak_load_rss,
            "sampled_peak_inference_rss_bytes": peak_inference_rss,
            "sampled_peak_lifecycle_rss_bytes": peak_lifecycle_rss,
            "process_peak_working_set_bytes": memory_after_inference["peak_working_set_bytes"],
            "incremental_peak_load_rss_bytes": max(0, peak_load_rss - int(memory_before["rss_bytes"])),
            "incremental_peak_lifecycle_rss_bytes": max(0, peak_lifecycle_rss - int(memory_before["rss_bytes"])),
            "tokenizer_load_wall_seconds": tokenizer_seconds,
            "model_load_wall_seconds": model_seconds,
            "warmup_wall_seconds": warmup_seconds,
            "inference_wall_seconds": inference_wall_seconds,
            "inference_cpu_seconds": inference_cpu_seconds,
            "milliseconds_per_case": inference_wall_seconds * 1000 / len(cases),
            "cases_per_second": len(cases) / inference_wall_seconds,
        },
        "metrics": metrics,
        "proposed_acceptance": acceptance,
        "predictions": enriched_predictions,
    }


def _metric_delta(candidate: Mapping[str, Any], baseline: Mapping[str, Any], key: str) -> float:
    return float(candidate[key]) - float(baseline[key])


def compare_checkpoint_results(
    project_root: Path,
    manifest_path: Path,
    baseline_result_path: Path,
    candidate_result_path: Path,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    _, frozen_cases, frozen_dataset_controls = load_and_validate_dataset(project_root, manifest)
    frozen_case_ids = [case["case_id"] for case in frozen_cases]
    frozen_expected = {case["case_id"]: case["expected_label"] for case in frozen_cases}
    baseline = read_json(baseline_result_path)
    candidate = read_json(candidate_result_path)
    expected_manifest_sha = sha256_file(manifest_path)
    for name, result in (("baseline", baseline), ("candidate", candidate)):
        model_spec = manifest["models"][name]
        _require(result["manifest"]["sha256"] == expected_manifest_sha, f"{name} result used a different manifest")
        _require(result["dataset"]["sha256"] == manifest["dataset"]["sha256"], f"{name} result used a different dataset")
        _require(result["dataset"]["scored_cases"] == 45, f"{name} result case count changed")
        _require(result["model"]["role"] == name, f"{name} result has the wrong model role")
        _require(result["model"]["requested_model_id"] == model_spec["model_id"], f"{name} model ID mismatch")
        _require(result["model"]["requested_revision"] == model_spec["revision"], f"{name} revision mismatch")
        _require(result["model"]["config_commit_hash"] == model_spec["revision"], f"{name} resolved config commit mismatch")
        _require(result["tokenizer"]["requested_id"] == model_spec["tokenizer_id"], f"{name} tokenizer ID mismatch")
        _require(result["tokenizer"]["requested_revision"] == model_spec["tokenizer_revision"], f"{name} tokenizer revision mismatch")
        _require(result["model"]["id2label"] == {"0": "entailment", "1": "neutral", "2": "contradiction"}, f"{name} label mapping mismatch")
        for filename, expected_sha in model_spec["snapshot_files"].items():
            _require(
                result["model"]["snapshot_files"].get(filename, {}).get("sha256") == expected_sha,
                f"{name} snapshot evidence mismatch for {filename}",
            )
        runtime = result["runtime"]
        _require(runtime["device"] == "cpu" and runtime["dtype"] == "torch.float32", f"{name} device/dtype mismatch")
        _require(runtime["eval_mode"] is True and runtime["adapter"] is None, f"{name} eval/adapter control mismatch")
        _require(runtime["deterministic_algorithms_enabled"] is True, f"{name} deterministic algorithms disabled")
        _require(runtime["max_length"] == 256 and runtime["batch_size"] == 8, f"{name} length/batch control mismatch")
        _require(result["experiment_controls"]["inference"] == manifest["inference"], f"{name} inference controls differ from manifest")
        _require(result["experiment_controls"]["dataset_validation"] == frozen_dataset_controls, f"{name} dataset validation evidence differs")
        _require(result["experiment_controls"]["tokenization"]["truncation_occurred"] is False, f"{name} tokenization truncated cases")

    baseline_rows = baseline["predictions"]
    candidate_rows = candidate["predictions"]
    baseline_ids = [row["case_id"] for row in baseline_rows]
    candidate_ids = [row["case_id"] for row in candidate_rows]
    _require(baseline_ids == candidate_ids == frozen_case_ids, "Result case IDs/order differ from frozen CP-005")
    for role, rows in (("baseline", baseline_rows), ("candidate", candidate_rows)):
        _require(
            all(row["expected_label"] == frozen_expected[row["case_id"]] for row in rows),
            f"{role} expected labels differ from frozen CP-005",
        )

    stored_path = (project_root / manifest["baseline_reference_result"]["path"]).resolve()
    _require(
        _matches_historical_text_hash(stored_path, manifest["baseline_reference_result"]["sha256"]),
        "Stored CP-005 baseline hash mismatch",
    )
    stored = read_json(stored_path)
    stored_rows = stored["predictions"]
    _require([row["case_id"] for row in stored_rows] == baseline_ids, "Stored CP-005 IDs/order differ")
    label_mismatches = [
        row["case_id"]
        for row, old in zip(baseline_rows, stored_rows)
        if row["predicted_label"] != old["predicted_label"]
    ]
    probability_delta = 0.0
    for row, old in zip(baseline_rows, stored_rows):
        for label in LABEL_ORDER:
            old_probability = float(old[f"{label}_probability"])
            probability_delta = max(probability_delta, abs(float(row["probabilities"][label]) - old_probability))
    current_overall = baseline["metrics"]["all_scored_cases"]
    stored_overall = stored["metrics"]["all_scored_cases"]
    metric_parity = {
        key: abs(float(current_overall[key]) - float(stored_overall[key])) <= 1e-12
        for key in ("accuracy", "macro_f1", "false_contradiction_rate_on_entailments", "false_entailment_rate_on_contradictions")
    }
    _require(not label_mismatches and all(metric_parity.values()), f"Baseline rerun did not reproduce CP-005: labels={label_mismatches}, metrics={metric_parity}")

    baseline_by_id = {row["case_id"]: row for row in baseline_rows}
    candidate_by_id = {row["case_id"]: row for row in candidate_rows}
    fixed: list[str] = []
    regressed: list[str] = []
    changed_wrong: list[str] = []
    unchanged: list[str] = []
    for case_id in baseline_ids:
        before = baseline_by_id[case_id]
        after = candidate_by_id[case_id]
        if not before["correct"] and after["correct"]:
            fixed.append(case_id)
        elif before["correct"] and not after["correct"]:
            regressed.append(case_id)
        elif not before["correct"] and not after["correct"] and before["predicted_label"] != after["predicted_label"]:
            changed_wrong.append(case_id)
        else:
            unchanged.append(case_id)

    baseline_overall = baseline["metrics"]["all_scored_cases"]
    candidate_overall = candidate["metrics"]["all_scored_cases"]
    metric_comparison = {
        "accuracy": {"baseline": baseline_overall["accuracy"], "candidate": candidate_overall["accuracy"], "delta": _metric_delta(candidate_overall, baseline_overall, "accuracy")},
        "macro_f1": {"baseline": baseline_overall["macro_f1"], "candidate": candidate_overall["macro_f1"], "delta": _metric_delta(candidate_overall, baseline_overall, "macro_f1")},
        "false_contradiction_rate": {
            "baseline": baseline_overall["false_contradiction_rate_on_entailments"],
            "candidate": candidate_overall["false_contradiction_rate_on_entailments"],
            "delta": _metric_delta(candidate_overall, baseline_overall, "false_contradiction_rate_on_entailments"),
        },
        "false_entailment_rate": {
            "baseline": baseline_overall["false_entailment_rate_on_contradictions"],
            "candidate": candidate_overall["false_entailment_rate_on_contradictions"],
            "delta": _metric_delta(candidate_overall, baseline_overall, "false_entailment_rate_on_contradictions"),
        },
    }
    baseline_resources = baseline["resources"]
    candidate_resources = candidate["resources"]
    resource_comparison = {}
    for key in (
        "model_load_wall_seconds",
        "inference_wall_seconds",
        "milliseconds_per_case",
        "sampled_peak_lifecycle_rss_bytes",
        "process_peak_working_set_bytes",
    ):
        before = float(baseline_resources[key])
        after = float(candidate_resources[key])
        resource_comparison[key] = {
            "baseline": baseline_resources[key],
            "candidate": candidate_resources[key],
            "delta": after - before,
            "ratio": after / before if before else None,
        }

    return {
        "schema_version": 1,
        "comparison_id": "cp006-checkpoint-control-comparison-v1",
        "created_at": now_cairo(),
        "decision_scope": "COMPARISON_ONLY_NO_AUTOMATIC_WINNER_NO_PRODUCTION_CHANGE",
        "manifest": {"path": manifest_path.as_posix(), "sha256": expected_manifest_sha},
        "dataset_sha256": manifest["dataset"]["sha256"],
        "baseline": {
            "model_id": baseline["model"]["requested_model_id"],
            "revision": baseline["model"]["requested_revision"],
            "result_path": baseline_result_path.as_posix(),
            "result_sha256": sha256_file(baseline_result_path),
        },
        "candidate": {
            "model_id": candidate["model"]["requested_model_id"],
            "revision": candidate["model"]["requested_revision"],
            "result_path": candidate_result_path.as_posix(),
            "result_sha256": sha256_file(candidate_result_path),
        },
        "baseline_reproduction": {
            "stored_result_path": manifest["baseline_reference_result"]["path"],
            "stored_result_sha256": manifest["baseline_reference_result"]["sha256"],
            "prediction_labels_exact": not label_mismatches,
            "metric_parity": metric_parity,
            "maximum_rounded_probability_absolute_delta": probability_delta,
            "passed": not label_mismatches and all(metric_parity.values()),
        },
        "metrics": metric_comparison,
        "confusion_matrices": {
            "baseline": baseline_overall["confusion_matrix"],
            "candidate": candidate_overall["confusion_matrix"],
        },
        "per_class": {
            "baseline": baseline_overall["per_class"],
            "candidate": candidate_overall["per_class"],
        },
        "DA017_regression_anchors": {
            "baseline_metrics": baseline["metrics"]["DA017_regression_anchors"],
            "candidate_metrics": candidate["metrics"]["DA017_regression_anchors"],
            "cases": [
                {
                    "case_id": case_id,
                    "expected_label": baseline_by_id[case_id]["expected_label"],
                    "baseline_prediction": baseline_by_id[case_id]["predicted_label"],
                    "baseline_probabilities": baseline_by_id[case_id]["probabilities"],
                    "candidate_prediction": candidate_by_id[case_id]["predicted_label"],
                    "candidate_probabilities": candidate_by_id[case_id]["probabilities"],
                    "baseline_pass": baseline_by_id[case_id]["correct"],
                    "candidate_pass": candidate_by_id[case_id]["correct"],
                }
                for case_id in baseline_ids
                if baseline_by_id[case_id]["regression_anchor"]
            ],
        },
        "language_style": {
            name: {
                "support": baseline["metrics"]["by_language_style"][name]["support"],
                "baseline_accuracy": baseline["metrics"]["by_language_style"][name]["accuracy"],
                "candidate_accuracy": candidate["metrics"]["by_language_style"][name]["accuracy"],
                "delta": candidate["metrics"]["by_language_style"][name]["accuracy"] - baseline["metrics"]["by_language_style"][name]["accuracy"],
            }
            for name in baseline["metrics"]["by_language_style"]
        },
        "difficulty_type": {
            name: {
                "support": baseline["metrics"]["by_difficulty_type"][name]["support"],
                "baseline_accuracy": baseline["metrics"]["by_difficulty_type"][name]["accuracy"],
                "candidate_accuracy": candidate["metrics"]["by_difficulty_type"][name]["accuracy"],
                "delta": candidate["metrics"]["by_difficulty_type"][name]["accuracy"] - baseline["metrics"]["by_difficulty_type"][name]["accuracy"],
            }
            for name in baseline["metrics"]["by_difficulty_type"]
        },
        "case_changes": {
            "fixed_failures": fixed,
            "new_regressions": regressed,
            "changed_but_still_wrong": changed_wrong,
            "unchanged_or_same_outcome": unchanged,
        },
        "resources": resource_comparison,
        "deployment_constraints": {
            "same_model_class": baseline["model"]["class"] == candidate["model"]["class"],
            "same_tokenizer_class": baseline["tokenizer"]["class"] == candidate["tokenizer"]["class"],
            "same_label_mapping": baseline["model"]["id2label"] == candidate["model"]["id2label"],
            "same_parameter_count": baseline["model"]["parameter_count"] == candidate["model"]["parameter_count"],
            "both_cpu_fp32": baseline["runtime"]["device"] == candidate["runtime"]["device"] == "cpu" and baseline["runtime"]["dtype"] == candidate["runtime"]["dtype"] == "torch.float32",
        },
        "proposed_acceptance": {
            "baseline": baseline["proposed_acceptance"],
            "candidate": candidate["proposed_acceptance"],
        },
        "automatic_winner": None,
        "decision_required": "Human engineering review; this artifact does not change production configuration.",
    }


def render_comparison_markdown(comparison: Mapping[str, Any]) -> str:
    metrics = comparison["metrics"]
    lines = [
        "# CP-006 Phase 2A NLI Checkpoint-Control Comparison",
        "",
        "- Scope: evaluation only; no training, adapter, threshold, scoring, retrieval, Fusion, or production change.",
        f"- Dataset SHA-256: `{comparison['dataset_sha256']}`",
        f"- Baseline: `{comparison['baseline']['model_id']}` @ `{comparison['baseline']['revision']}`",
        f"- Candidate: `{comparison['candidate']['model_id']}` @ `{comparison['candidate']['revision']}`",
        f"- Baseline CP-005 reproduction: `{'PASS' if comparison['baseline_reproduction']['passed'] else 'FAIL'}`",
        "- Automatic winner: **none**; engineering review is required.",
        "",
        "## Aggregate comparison",
        "",
        "| Metric | Baseline | Candidate | Delta |",
        "|---|---:|---:|---:|",
    ]
    for label, key in (("Accuracy", "accuracy"), ("Macro F1", "macro_f1"), ("False contradiction rate", "false_contradiction_rate"), ("False entailment rate", "false_entailment_rate")):
        row = metrics[key]
        lines.append(f"| {label} | {row['baseline']:.6f} | {row['candidate']:.6f} | {row['delta']:+.6f} |")

    lines.extend(
        [
            "",
            "## Per-class metrics",
            "",
            "| Class | Model | Precision | Recall | F1 | Support |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for class_name in LABEL_ORDER:
        for role in ("baseline", "candidate"):
            row = comparison["per_class"][role][class_name]
            lines.append(
                f"| {class_name} | {role} | {row['precision']:.6f} | {row['recall']:.6f} | "
                f"{row['f1']:.6f} | {row['support']} |"
            )

    lines.extend(["", "## Confusion matrices", ""])
    for role in ("baseline", "candidate"):
        cm = comparison["confusion_matrices"][role]
        lines.extend(
            [
                f"### {role.title()}",
                "",
                "Rows are expected labels; columns are predicted E/N/C.",
                "",
                "| Expected | E | N | C |",
                "|---|---:|---:|---:|",
                f"| E | {cm['entailment']['entailment']} | {cm['entailment']['neutral']} | {cm['entailment']['contradiction']} |",
                f"| N | {cm['neutral']['entailment']} | {cm['neutral']['neutral']} | {cm['neutral']['contradiction']} |",
                f"| C | {cm['contradiction']['entailment']} | {cm['contradiction']['neutral']} | {cm['contradiction']['contradiction']} |",
                "",
            ]
        )

    lines.extend(
        [
            "## DA-017 anchors",
            "",
            "| Case | Expected | Baseline prediction (E/N/C) | Candidate prediction (E/N/C) | Baseline | Candidate |",
            "|---|---|---|---|---:|---:|",
        ]
    )
    for row in comparison["DA017_regression_anchors"]["cases"]:
        bp = row["baseline_probabilities"]
        cp = row["candidate_probabilities"]
        lines.append(
            f"| {row['case_id']} | {row['expected_label']} | {row['baseline_prediction']} "
            f"({bp['entailment']:.6f}/{bp['neutral']:.6f}/{bp['contradiction']:.6f}) | "
            f"{row['candidate_prediction']} ({cp['entailment']:.6f}/{cp['neutral']:.6f}/{cp['contradiction']:.6f}) | "
            f"{'PASS' if row['baseline_pass'] else 'FAIL'} | {'PASS' if row['candidate_pass'] else 'FAIL'} |"
        )

    for title, key in (("Language-style breakdown", "language_style"), ("Difficulty breakdown", "difficulty_type")):
        lines.extend(["", f"## {title}", "", "| Slice | Support | Baseline accuracy | Candidate accuracy | Delta |", "|---|---:|---:|---:|---:|"])
        for name, row in comparison[key].items():
            lines.append(f"| {name} | {row['support']} | {row['baseline_accuracy']:.6f} | {row['candidate_accuracy']:.6f} | {row['delta']:+.6f} |")

    changes = comparison["case_changes"]
    lines.extend(
        [
            "",
            "## Case-level changes",
            "",
            f"- Fixed baseline failures: `{changes['fixed_failures']}`",
            f"- New regressions: `{changes['new_regressions']}`",
            f"- Changed but still wrong: `{changes['changed_but_still_wrong']}`",
            "",
            "## Resource comparison",
            "",
            "Fresh process per model; pinned local snapshot; identical fixed-batch warm-up excluded from timed 45-case inference.",
            "",
            "| Resource | Baseline | Candidate | Ratio |",
            "|---|---:|---:|---:|",
        ]
    )
    for label, key in (("Model load seconds", "model_load_wall_seconds"), ("Inference seconds", "inference_wall_seconds"), ("Milliseconds/case", "milliseconds_per_case"), ("Lifecycle peak RSS bytes", "sampled_peak_lifecycle_rss_bytes"), ("Process peak working set bytes", "process_peak_working_set_bytes")):
        row = comparison["resources"][key]
        ratio = "n/a" if row["ratio"] is None else f"{row['ratio']:.3f}x"
        lines.append(f"| {label} | {row['baseline']:.6f} | {row['candidate']:.6f} | {ratio} |")

    lines.extend(
        [
            "",
            "## Decision boundary",
            "",
            "This experiment records evidence only. It does not select or deploy a winner, train an adapter, or alter production behavior.",
            "",
        ]
    )
    return "\n".join(lines)


def validate_completed_artifacts(
    project_root: Path,
    manifest_path: Path,
    baseline_result_path: Path,
    candidate_result_path: Path,
    comparison_path: Path,
) -> dict[str, Any]:
    """Recompute persisted outputs without loading either model."""

    manifest = load_manifest(manifest_path)
    _, cases, dataset_controls = load_and_validate_dataset(project_root, manifest)
    comparison = read_json(comparison_path)
    results = {
        "baseline": read_json(baseline_result_path),
        "candidate": read_json(candidate_result_path),
    }
    result_paths = {"baseline": baseline_result_path, "candidate": candidate_result_path}
    per_model: dict[str, Any] = {}

    for role, result in results.items():
        rows = result["predictions"]
        _require(len(rows) == len(cases) == 45, f"{role} prediction count mismatch")
        _require([row["case_id"] for row in rows] == [case["case_id"] for case in cases], f"{role} case order mismatch")
        argmax_mismatches: list[str] = []
        probability_sum_max_error = 0.0
        for row in rows:
            probabilities = row["probabilities"]
            probability_sum_max_error = max(
                probability_sum_max_error,
                abs(sum(float(probabilities[label]) for label in LABEL_ORDER) - 1.0),
            )
            argmax_label = max(LABEL_ORDER, key=lambda label: float(probabilities[label]))
            if argmax_label != row["predicted_label"]:
                argmax_mismatches.append(row["case_id"])
        _require(not argmax_mismatches, f"{role} argmax mismatches: {argmax_mismatches}")
        _require(probability_sum_max_error <= 2e-6, f"{role} probability sums exceed tolerance: {probability_sum_max_error}")

        recomputed = build_metrics(cases, rows)
        stored = result["metrics"]
        metric_checks = {
            "accuracy": abs(recomputed["all_scored_cases"]["accuracy"] - stored["all_scored_cases"]["accuracy"]) <= 1e-12,
            "macro_f1": abs(recomputed["all_scored_cases"]["macro_f1"] - stored["all_scored_cases"]["macro_f1"]) <= 1e-12,
            "confusion_matrix": recomputed["all_scored_cases"]["confusion_matrix"] == stored["all_scored_cases"]["confusion_matrix"],
            "anchor_metrics": recomputed["DA017_regression_anchors"] == stored["DA017_regression_anchors"],
            "language_slices": recomputed["by_language_style"] == stored["by_language_style"],
            "difficulty_slices": recomputed["by_difficulty_type"] == stored["by_difficulty_type"],
        }
        _require(all(metric_checks.values()), f"{role} persisted metrics failed recomputation: {metric_checks}")
        _require(result["runtime"]["device"] == "cpu", f"{role} was not CPU")
        _require(result["runtime"]["dtype"] == "torch.float32", f"{role} was not fp32")
        _require(result["runtime"]["deterministic_algorithms_enabled"] is True, f"{role} determinism flag is false")
        _require(result["runtime"]["max_length"] == 256, f"{role} max_length changed")
        _require(result["model"]["id2label"] == {"0": "entailment", "1": "neutral", "2": "contradiction"}, f"{role} label mapping changed")
        _require(result["experiment_controls"]["training_separation"]["status"] == "NO_TRAINING_MANIFEST_PRESENT", f"{role} unexpected training-manifest state")
        per_model[role] = {
            "result_sha256": sha256_file(result_paths[role]),
            "prediction_count": len(rows),
            "argmax_mismatches": argmax_mismatches,
            "maximum_probability_sum_error": probability_sum_max_error,
            "metric_checks": metric_checks,
            "runtime_controls_passed": True,
        }

    _require(comparison["baseline"]["result_sha256"] == per_model["baseline"]["result_sha256"], "Comparison baseline hash is stale")
    _require(comparison["candidate"]["result_sha256"] == per_model["candidate"]["result_sha256"], "Comparison candidate hash is stale")
    _require(comparison["automatic_winner"] is None, "Comparison selected a winner automatically")
    _require(comparison["baseline_reproduction"]["passed"] is True, "Baseline did not reproduce CP-005")
    recomputed_comparison = compare_checkpoint_results(
        project_root,
        manifest_path,
        baseline_result_path,
        candidate_result_path,
    )
    comparison_sections = (
        "baseline_reproduction",
        "metrics",
        "confusion_matrices",
        "per_class",
        "DA017_regression_anchors",
        "language_style",
        "difficulty_type",
        "case_changes",
        "resources",
        "deployment_constraints",
        "proposed_acceptance",
        "automatic_winner",
    )
    comparison_recompute_checks = {
        section: comparison[section] == recomputed_comparison[section] for section in comparison_sections
    }
    _require(all(comparison_recompute_checks.values()), f"Comparison artifact failed recomputation: {comparison_recompute_checks}")

    return {
        "schema_version": 1,
        "validation_id": "cp006-checkpoint-control-validation-v1",
        "created_at": now_cairo(),
        "status": "PASS",
        "dataset_sha256": manifest["dataset"]["sha256"],
        "dataset_controls": dataset_controls,
        "manifest": {"path": manifest_path.as_posix(), "sha256": sha256_file(manifest_path)},
        "models": per_model,
        "comparison": {"path": comparison_path.as_posix(), "sha256": sha256_file(comparison_path)},
        "comparison_recompute_checks": comparison_recompute_checks,
        "baseline_cp005_reproduction_passed": True,
        "automatic_winner_is_none": True,
        "training_performed": False,
        "production_behavior_changed": False,
    }
