"""Independently validate the CP-010 diagnosis and checkpoint boundaries."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


EXPECTED_DEPENDENCIES = {
    "data/nli/evaluation/heldout_ar_codeswitch_v1.json": "5AA1278465B99B4D88AAE94871181D2A768A91AB601AD1B4E2141CF0B2A8DC18",
    "data/nli/training/phase2b_lora_corpus_v1.json": "3FB523040C9B2482A0FCF0AAC8FDCC13D54E32AC2D9CB75DF5CE970E2E341F33",
    "data/nli/training/phase2b_lora_split_manifest_v1.json": "157BE9BD9261411A89BA60F46D86DEF56664051AA0B3A2C7F29E18257B85D3F4",
    "results/nli_baseline_cp005/current_model_baseline_v1.json": "7FAFA2F8EF8B1C5BA70AD2AAED371A7780557F7D05E6690C7E8468234495BFC6",
    "results/nli_checkpoint_control_cp006/checkpoint_comparison_v1.json": "908A1F72D426BCA7B54F867C823B1AFB9FAD59BC1480C7A9C9770961DF48BB55",
    "results/nli_phase2c_training_cp009/training_metrics_v1.json": "7F751A8CEC937D303FE2B64DFC34720461DD9F9E1FDB894580179BA0E3C3C240",
    "results/nli_phase2c_training_cp009/cp005_adapter_evaluation_v1.json": "C05B1FEFDC3160C6D3D2695125B1A3E71A2C6D7462E7844C659D38C9B7C5005F",
    "results/nli_phase2c_training_cp009/baseline_vs_lora_comparison_v1.json": "207B9AD75416F9B0A77680352D7A96C9D2D8685271C4F6333BCA050D19AC26D1",
}

MARKERS = {
    "entailment": (
        "خلاصة المعنى أن ", "المعنى ببساطة إن ", "In other words، ",
        "Technically speaking، ", "بصياغة المصطلحات المنطوقة، ",
    ),
    "contradiction": (
        "ليس صحيحًا أن ", "مش صحيح إن ", "It is not true that، ",
        "It is false that ", "The claim says، ", "الادعاء هنا بيقول إن ",
    ),
    "neutral": (
        "معلومة تقنية مستقلة: ", "معلومة تانية مستقلة بتقول إن ",
        "A separate technical fact is، ", "معلومة تقنية منفصلة: ",
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(path)
    return value


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold().replace("ـ", "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return " ".join(re.findall(r"\w+", text, flags=re.UNICODE))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> int:
    result_dir = Path(__file__).resolve().parent
    nlp_root = result_dir.parents[1]
    repo_root = nlp_root.parents[2]
    diagnosis_path = result_dir / "lora_failure_diagnosis_v1.json"
    report_path = result_dir / "lora_failure_diagnosis_v1.md"
    diagnosis = load(diagnosis_path)

    for relative, expected in EXPECTED_DEPENDENCIES.items():
        require(sha256_file(nlp_root / relative) == expected, f"Dependency hash changed: {relative}")
        require(diagnosis["dependencies"][relative]["sha256"] == expected, f"Diagnosis dependency mismatch: {relative}")

    scope = diagnosis["scope"]
    require(scope["analysis_only"] is True, "Analysis-only scope missing")
    require(not any(value for key, value in scope.items() if key != "analysis_only"), "Prohibited action recorded")
    require(diagnosis["status"] == "VERIFIED_DIAGNOSIS_COMPLETE_NO_REMEDIATION", "Diagnosis status mismatch")
    require(diagnosis["checkpoint"] == "CP-010", "Checkpoint mismatch")

    corpus = load(nlp_root / "data/nli/training/phase2b_lora_corpus_v1.json")["records"]
    baseline = load(nlp_root / "results/nli_baseline_cp005/current_model_baseline_v1.json")["predictions"]
    adapter = load(nlp_root / "results/nli_phase2c_training_cp009/cp005_adapter_evaluation_v1.json")["predictions"]
    require(len(corpus) == 600 and len(baseline) == len(adapter) == 45, "Artifact counts changed")
    require(Counter(row["label"] for row in corpus) == Counter({"entailment": 200, "neutral": 200, "contradiction": 200}), "Corpus labels changed")

    marker_counts = {
        label: sum(row["label"] == label and row["hypothesis"].startswith(markers) for row in corpus)
        for label, markers in MARKERS.items()
    }
    require(marker_counts == {"entailment": 170, "contradiction": 150, "neutral": 180}, "Marker evidence mismatch")
    paraphrases = [row for row in corpus if row["difficulty_type"] == "paraphrase_entailment"]
    contained = sum(normalize(row["premise"]) in normalize(row["hypothesis"]) for row in paraphrases)
    require(len(paraphrases) == 180 and contained == 153, "Paraphrase containment evidence mismatch")
    require(not any(re.search(r"\b(?:left|inner|right|full|outer)?\s*join\b", row["premise"] + " " + row["hypothesis"], re.IGNORECASE) for row in corpus), "JOIN coverage claim changed")

    base = {row["case_id"]: row for row in baseline}
    adapted = {row["case_id"]: row for row in adapter}
    require(set(base) == set(adapted) and len(base) == 45, "Evaluation case identity mismatch")
    fixed, regressed, unchanged_fail, unchanged_correct = [], [], [], []
    for case_id in sorted(base):
        b, a = base[case_id], adapted[case_id]
        if not b["correct"] and a["correct"]:
            fixed.append(case_id)
        elif b["correct"] and not a["correct"]:
            regressed.append(case_id)
        elif not b["correct"] and not a["correct"]:
            unchanged_fail.append(case_id)
        else:
            unchanged_correct.append(case_id)
    require(fixed == ["NLI-EVAL-007", "NLI-EVAL-035"], "Fixed transition mismatch")
    require(regressed == ["NLI-EVAL-037", "NLI-EVAL-041"], "Regression transition mismatch")
    require(unchanged_fail == ["NLI-EVAL-009", "NLI-EVAL-018", "NLI-EVAL-023", "NLI-EVAL-042", "NLI-EVAL-043", "NLI-EVAL-045"], "Unchanged failure mismatch")
    require(len(unchanged_correct) == 35, "Unchanged-correct count mismatch")
    require(Counter(row["predicted_label"] for row in baseline) == Counter({"entailment": 15, "neutral": 18, "contradiction": 12}), "Baseline class counts mismatch")
    require(Counter(row["predicted_label"] for row in adapter) == Counter({"entailment": 11, "neutral": 20, "contradiction": 14}), "LoRA class counts mismatch")

    require(report_path.read_text(encoding="utf-8").startswith("# CP-010 — Phase 2D LoRA Failure Diagnosis"), "Markdown report missing")
    for marker in ("Every-case prediction transition", "DA-017 deep analysis", "Root-cause hypothesis ranking", "Exact next step"):
        require(marker in report_path.read_text(encoding="utf-8"), f"Report section missing: {marker}")

    memory_markers = {
        "EXECUTION_STATE.json": '"last_verified_checkpoint": "CP-010"',
        "CURRENT_TASK.md": "CP-010 — LoRA Failure Diagnosis Complete",
        "EVIDENCE_LEDGER.md": "EV-022 — CP-010 LoRA failure diagnosis",
        "PROJECT_MEMORY.md": "CP-010 — LoRA Failure Diagnosis Complete",
        "KNOWN_ISSUES.md": "LORA_FAILURE_DIAGNOSED_REMEDIATION_DESIGN_PENDING",
    }
    for relative, marker in memory_markers.items():
        require(marker in (repo_root / relative).read_text(encoding="utf-8"), f"Checkpoint memory marker missing: {relative}")

    validation = {
        "schema_version": 1,
        "validation_id": "interviewiq-nli-phase2d-diagnosis-validation-v1",
        "checkpoint": "CP-010",
        "status": "PASS",
        "checks": {
            "frozen_dependency_hashes": "PASS",
            "strict_json_and_utf8": "PASS",
            "scope_boundary": "PASS_NO_MODEL_INFERENCE_TRAINING_DATA_OR_PRODUCTION_ACTION",
            "corpus_counts_and_labels": "PASS_600_BALANCED",
            "surface_marker_recomputation": {"status": "PASS", "counts": marker_counts},
            "paraphrase_containment_recomputation": {"status": "PASS", "contained": contained, "support": len(paraphrases)},
            "join_term_coverage": "PASS_ZERO_RECORDS",
            "all_case_transition_recomputation": {
                "status": "PASS",
                "fixed": fixed,
                "regressed_new_failures": regressed,
                "unchanged_failures": unchanged_fail,
                "unchanged_correct": len(unchanged_correct),
            },
            "predicted_class_shift": "PASS_E_15_TO_11_N_18_TO_20_C_12_TO_14",
            "report_sections": "PASS",
            "external_memory_cp010_markers": "PASS",
        },
        "artifacts": {
            "diagnosis_json": {"path": str(diagnosis_path.relative_to(nlp_root)).replace("\\", "/"), "sha256": sha256_file(diagnosis_path)},
            "diagnosis_report": {"path": str(report_path.relative_to(nlp_root)).replace("\\", "/"), "sha256": sha256_file(report_path)},
            "analysis_utility": {"path": str((result_dir / "analyze_lora_failure_v1.py").relative_to(nlp_root)).replace("\\", "/"), "sha256": sha256_file(result_dir / "analyze_lora_failure_v1.py")},
        },
        "decision": "CP010_VERIFIED_DIAGNOSIS_COMPLETE_NO_REMEDIATION",
    }
    output = result_dir / "diagnosis_validation_v1.json"
    output.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("CP010_VALIDATION=PASS")
    print(f"VALIDATION_SHA256={sha256_file(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
