from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from interview_iq.evaluation.checkpoint_control import (
    CheckpointControlError,
    build_metrics,
    compare_checkpoint_results,
    compute_metrics,
    infer_predictions,
    load_and_validate_dataset,
    load_manifest,
    normalize_overlap_text,
    sha256_file,
    sha256_text_file,
    validate_manifest,
    validate_training_separation,
    write_json,
)


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "results" / "nli_checkpoint_control_cp006" / "experiment_manifest_v1.json"
CP005_RESULT = ROOT / "results" / "nli_baseline_cp005" / "current_model_baseline_v1.json"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_frozen_manifest_dataset_and_question_boundary() -> None:
    manifest = load_manifest(MANIFEST)
    dataset, cases, controls = load_and_validate_dataset(ROOT, manifest)

    assert sha256_text_file(ROOT / manifest["dataset"]["path"]) == "5AA1278465B99B4D88AAE94871181D2A768A91AB601AD1B4E2141CF0B2A8DC18"
    assert dataset["do_not_train"] is True
    assert len(cases) == 45
    assert controls["unique_case_ids"] == 45
    assert controls["unique_normalized_pairs"] == 45
    assert {case["source_question_id"] for case in cases} == set(manifest["leakage_controls"]["protected_question_ids"])


def test_manifest_rejects_mutable_revision_and_runtime_drift() -> None:
    manifest = _json(MANIFEST)
    invalid = copy.deepcopy(manifest)
    invalid["models"]["candidate"]["revision"] = "main"
    with pytest.raises(CheckpointControlError, match="mutable/invalid"):
        validate_manifest(invalid)

    invalid = copy.deepcopy(manifest)
    invalid["inference"]["max_length"] = 128
    with pytest.raises(CheckpointControlError, match="max_length"):
        validate_manifest(invalid)

    invalid = copy.deepcopy(manifest)
    invalid["inference"]["device"] = "cuda"
    with pytest.raises(CheckpointControlError, match="device"):
        validate_manifest(invalid)


@pytest.mark.parametrize("defect", ["duplicate_id", "duplicate_pair"])
def test_dataset_duplicate_controls_fail(tmp_path: Path, defect: str) -> None:
    manifest = _json(MANIFEST)
    dataset = _json(ROOT / manifest["dataset"]["path"])
    if defect == "duplicate_id":
        dataset["cases"][1]["case_id"] = dataset["cases"][0]["case_id"]
    else:
        dataset["cases"][1]["premise"] = dataset["cases"][0]["premise"]
        dataset["cases"][1]["hypothesis"] = dataset["cases"][0]["hypothesis"]
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
    test_manifest = copy.deepcopy(manifest)
    test_manifest["dataset"]["path"] = path.name
    test_manifest["dataset"]["sha256"] = sha256_text_file(path)
    with pytest.raises(CheckpointControlError, match="Duplicate"):
        load_and_validate_dataset(tmp_path, test_manifest)


def _eval_case() -> dict:
    return {
        "case_id": "E-1",
        "source_question_id": "Q-EVAL",
        "premise": "النموذج يستخدم LEFT JOIN.",
        "hypothesis": "The model uses left join",
    }


@pytest.mark.parametrize(
    "record, expected",
    [
        ({"pair_id": "T1", "question_id": "Q-EVAL", "premise": "new premise", "hypothesis": "new hypothesis"}, "protected_question_id_hits"),
        ({"pair_id": "T1", "question_id": "Q-NEW", "premise": "النموذج يستخدم left join", "hypothesis": "the model uses LEFT JOIN!"}, "evaluation_pair_overlap_hits"),
        ({"pair_id": "T1", "question_id": "Q-NEW", "premise": "النموذج يستخدم left join", "hypothesis": "different hypothesis"}, "evaluation_premise_overlap_hits"),
        ({"pair_id": "T1", "question_id": "Q-NEW", "premise": "different premise", "hypothesis": "the model uses LEFT JOIN!"}, "evaluation_hypothesis_overlap_hits"),
    ],
)
def test_training_leakage_controls_fail(record: dict, expected: str, tmp_path: Path) -> None:
    with pytest.raises(CheckpointControlError, match=expected):
        validate_training_separation([_eval_case()], {"Q-EVAL"}, [(tmp_path / "train.json", {"records": [record]})])


def test_duplicate_training_pairs_fail(tmp_path: Path) -> None:
    record = {"question_id": "Q-NEW", "premise": "unique premise", "hypothesis": "unique hypothesis"}
    with pytest.raises(CheckpointControlError, match="duplicate_training_pair_count"):
        validate_training_separation(
            [_eval_case()],
            {"Q-EVAL"},
            [(tmp_path / "train.json", {"records": [{**record, "pair_id": "T1"}, {**record, "pair_id": "T2"}]})],
        )


def test_no_training_manifest_is_reported_without_false_cleanliness_claim() -> None:
    result = validate_training_separation([_eval_case()], {"Q-EVAL"}, [])
    assert result["status"] == "NO_TRAINING_MANIFEST_PRESENT"
    assert "future training data" in result["claim_limit"]


def test_cp005_metrics_slices_and_anchors_recompute_exactly() -> None:
    manifest = load_manifest(MANIFEST)
    _, cases, _ = load_and_validate_dataset(ROOT, manifest)
    stored = _json(CP005_RESULT)
    predictions = [
        {
            "case_id": row["case_id"],
            "predicted_label": row["predicted_label"],
        }
        for row in stored["predictions"]
    ]
    recomputed = build_metrics(cases, predictions)
    expected = stored["metrics"]

    assert recomputed == expected


def test_metrics_reject_length_mismatch() -> None:
    with pytest.raises(CheckpointControlError, match="equal, nonzero"):
        compute_metrics(["entailment"], [])


class FakeTokenizer:
    unk_token_id = None

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def __call__(self, premises, hypotheses, **kwargs):
        self.calls.append((premises, hypotheses, kwargs))
        batch = len(premises)
        return {
            "input_ids": torch.ones((batch, 3), dtype=torch.long),
            "attention_mask": torch.ones((batch, 3), dtype=torch.long),
        }


class FakeModel:
    def __init__(self) -> None:
        self.config = SimpleNamespace(id2label={0: "entailment", 1: "neutral", 2: "contradiction"})
        self.no_grad_seen = False

    def __call__(self, **inputs):
        self.no_grad_seen = not torch.is_grad_enabled()
        batch = inputs["input_ids"].shape[0]
        return SimpleNamespace(logits=torch.tensor([[4.0, 1.0, 0.0]]).repeat(batch, 1))


def test_inference_preserves_direction_batch_and_max_length() -> None:
    cases = [
        {"case_id": "A", "premise": "premise-a", "hypothesis": "hypothesis-a", "expected_label": "entailment"},
        {"case_id": "B", "premise": "premise-b", "hypothesis": "hypothesis-b", "expected_label": "entailment"},
    ]
    model = FakeModel()
    tokenizer = FakeTokenizer()
    predictions = infer_predictions(model, tokenizer, cases, batch_size=2, max_length=256)

    assert [row["predicted_label"] for row in predictions] == ["entailment", "entailment"]
    premises, hypotheses, kwargs = tokenizer.calls[0]
    assert premises == ["premise-a", "premise-b"]
    assert hypotheses == ["hypothesis-a", "hypothesis-b"]
    assert kwargs["max_length"] == 256
    assert kwargs["truncation"] is True
    assert model.no_grad_seen is True


def test_overlap_normalization_catches_cosmetic_variants() -> None:
    assert normalize_overlap_text("  LEFT-JOIN  ") == normalize_overlap_text("left join")


def _synthetic_result(role: str, manifest: dict, cases: list[dict], rows: list[dict], controls: dict) -> dict:
    spec = manifest["models"][role]
    return {
        "manifest": {"sha256": sha256_file(MANIFEST)},
        "dataset": {"sha256": manifest["dataset"]["sha256"], "scored_cases": 45},
        "experiment_controls": {
            "dataset_validation": controls,
            "training_separation": {"status": "NO_TRAINING_MANIFEST_PRESENT"},
            "inference": manifest["inference"],
            "tokenization": {"truncation_occurred": False},
        },
        "model": {
            "role": role,
            "requested_model_id": spec["model_id"],
            "requested_revision": spec["revision"],
            "config_commit_hash": spec["revision"],
            "class": "DebertaV2ForSequenceClassification",
            "id2label": {"0": "entailment", "1": "neutral", "2": "contradiction"},
            "parameter_count": 100,
            "snapshot_files": {name: {"sha256": digest, "bytes": 1} for name, digest in spec["snapshot_files"].items()},
        },
        "tokenizer": {
            "requested_id": spec["tokenizer_id"],
            "requested_revision": spec["tokenizer_revision"],
            "class": "DebertaV2TokenizerFast",
        },
        "runtime": {
            "device": "cpu",
            "dtype": "torch.float32",
            "eval_mode": True,
            "adapter": None,
            "deterministic_algorithms_enabled": True,
            "max_length": 256,
            "batch_size": 8,
        },
        "resources": {
            "model_load_wall_seconds": 1.0,
            "inference_wall_seconds": 2.0,
            "milliseconds_per_case": 2000 / 45,
            "sampled_peak_lifecycle_rss_bytes": 1000,
            "process_peak_working_set_bytes": 1100,
        },
        "metrics": build_metrics(cases, rows),
        "proposed_acceptance": {"all_pass": False},
        "predictions": rows,
    }


def _stored_rows(cases: list[dict]) -> list[dict]:
    stored = _json(CP005_RESULT)
    rows: list[dict] = []
    for case, old in zip(cases, stored["predictions"]):
        rows.append(
            {
                **case,
                "predicted_label": old["predicted_label"],
                "correct": old["correct"],
                "error_direction": old["error_direction"],
                "probabilities": {
                    "entailment": old["entailment_probability"],
                    "neutral": old["neutral_probability"],
                    "contradiction": old["contradiction_probability"],
                },
            }
        )
    return rows


def test_comparison_classifies_case_changes_and_never_selects_winner(tmp_path: Path) -> None:
    manifest = load_manifest(MANIFEST)
    _, cases, controls = load_and_validate_dataset(ROOT, manifest)
    baseline_rows = _stored_rows(cases)
    candidate_rows = copy.deepcopy(baseline_rows)
    by_id = {row["case_id"]: row for row in candidate_rows}
    by_id["NLI-EVAL-009"].update(
        {"predicted_label": "contradiction", "correct": True, "error_direction": None, "probabilities": {"entailment": 0.01, "neutral": 0.01, "contradiction": 0.98}}
    )
    by_id["NLI-EVAL-001"].update(
        {"predicted_label": "neutral", "correct": False, "error_direction": "entailment->neutral", "probabilities": {"entailment": 0.01, "neutral": 0.98, "contradiction": 0.01}}
    )
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    write_json(baseline_path, _synthetic_result("baseline", manifest, cases, baseline_rows, controls))
    write_json(candidate_path, _synthetic_result("candidate", manifest, cases, candidate_rows, controls))

    comparison = compare_checkpoint_results(ROOT, MANIFEST, baseline_path, candidate_path)
    assert comparison["automatic_winner"] is None
    assert "NLI-EVAL-009" in comparison["case_changes"]["fixed_failures"]
    assert "NLI-EVAL-001" in comparison["case_changes"]["new_regressions"]


def test_comparison_rejects_wrong_candidate_identity(tmp_path: Path) -> None:
    manifest = load_manifest(MANIFEST)
    _, cases, controls = load_and_validate_dataset(ROOT, manifest)
    rows = _stored_rows(cases)
    baseline_path = tmp_path / "baseline.json"
    candidate_path = tmp_path / "candidate.json"
    write_json(baseline_path, _synthetic_result("baseline", manifest, cases, rows, controls))
    candidate = _synthetic_result("candidate", manifest, cases, rows, controls)
    candidate["model"]["requested_model_id"] = "wrong/model"
    write_json(candidate_path, candidate)
    with pytest.raises(CheckpointControlError, match="model ID mismatch"):
        compare_checkpoint_results(ROOT, MANIFEST, baseline_path, candidate_path)
