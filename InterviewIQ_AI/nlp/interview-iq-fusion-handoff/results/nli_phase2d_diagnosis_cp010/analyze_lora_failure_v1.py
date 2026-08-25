"""Build the CP-010 LoRA failure diagnosis from frozen JSON artifacts only.

This utility is deliberately model-free and read-only with respect to datasets,
adapters, and production code.  It recomputes corpus composition, surface-form
signals, all 45 baseline-to-adapter transitions, confidence shifts, and the
DA-017 evidence used by the accompanying engineering report.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


CREATED_AT = "2026-08-23T20:50:48+03:00"
EXPECTED_HASHES = {
    "data/nli/evaluation/heldout_ar_codeswitch_v1.json": "5AA1278465B99B4D88AAE94871181D2A768A91AB601AD1B4E2141CF0B2A8DC18",
    "data/nli/training/phase2b_lora_corpus_v1.json": "3FB523040C9B2482A0FCF0AAC8FDCC13D54E32AC2D9CB75DF5CE970E2E341F33",
    "data/nli/training/phase2b_lora_split_manifest_v1.json": "157BE9BD9261411A89BA60F46D86DEF56664051AA0B3A2C7F29E18257B85D3F4",
    "results/nli_baseline_cp005/current_model_baseline_v1.json": "7FAFA2F8EF8B1C5BA70AD2AAED371A7780557F7D05E6690C7E8468234495BFC6",
    "results/nli_checkpoint_control_cp006/checkpoint_comparison_v1.json": "908A1F72D426BCA7B54F867C823B1AFB9FAD59BC1480C7A9C9770961DF48BB55",
    "results/nli_phase2c_training_cp009/training_metrics_v1.json": "7F751A8CEC937D303FE2B64DFC34720461DD9F9E1FDB894580179BA0E3C3C240",
    "results/nli_phase2c_training_cp009/cp005_adapter_evaluation_v1.json": "C05B1FEFDC3160C6D3D2695125B1A3E71A2C6D7462E7844C659D38C9B7C5005F",
    "results/nli_phase2c_training_cp009/baseline_vs_lora_comparison_v1.json": "207B9AD75416F9B0A77680352D7A96C9D2D8685271C4F6333BCA050D19AC26D1",
}

LABELS = ("entailment", "neutral", "contradiction")

LABEL_MARKERS = {
    "entailment": (
        "خلاصة المعنى أن ",
        "المعنى ببساطة إن ",
        "In other words، ",
        "Technically speaking، ",
        "بصياغة المصطلحات المنطوقة، ",
    ),
    "contradiction": (
        "ليس صحيحًا أن ",
        "مش صحيح إن ",
        "It is not true that، ",
        "It is false that ",
        "The claim says، ",
        "الادعاء هنا بيقول إن ",
    ),
    "neutral": (
        "معلومة تقنية مستقلة: ",
        "معلومة تانية مستقلة بتقول إن ",
        "A separate technical fact is، ",
        "معلومة تقنية منفصلة: ",
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text)).casefold().replace("ـ", "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return " ".join(re.findall(r"\w+", text, flags=re.UNICODE))


def jaccard(left: str, right: str) -> float:
    left_tokens = set(normalize(left).split())
    right_tokens = set(normalize(right).split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def rounded_stats(values: Iterable[float]) -> dict[str, float]:
    items = list(values)
    return {
        "minimum": round(min(items), 6),
        "median": round(statistics.median(items), 6),
        "mean": round(statistics.fmean(items), 6),
        "maximum": round(max(items), 6),
    }


def distribution(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(record[key]) for record in records).items()))


def baseline_probabilities(row: dict[str, Any]) -> dict[str, float]:
    return {label: float(row[f"{label}_probability"]) for label in LABELS}


def entropy(probabilities: dict[str, float]) -> float:
    return -sum(value * math.log(value) for value in probabilities.values() if value > 0)


def marker_label(hypothesis: str) -> str | None:
    matches = [label for label, markers in LABEL_MARKERS.items() if hypothesis.startswith(markers)]
    if len(matches) > 1:
        raise ValueError(f"Multiple label markers matched: {hypothesis!r}")
    return matches[0] if matches else None


def corpus_analysis(records: list[dict[str, Any]]) -> dict[str, Any]:
    if len(records) != 600:
        raise ValueError(f"Expected 600 corpus records, got {len(records)}")

    by_split = {split: [row for row in records if row["split"] == split] for split in ("train", "dev")}
    qid_counts = Counter(row["question_id"] for row in records)
    marker_rows = [
        {"case_id": row["case_id"], "actual_label": row["label"], "marker_label": marker_label(row["hypothesis"])}
        for row in records
    ]
    marker_summary: dict[str, Any] = {}
    for label in LABELS:
        label_rows = [row for row in marker_rows if row["actual_label"] == label]
        detected = [row for row in label_rows if row["marker_label"] is not None]
        marker_summary[label] = {
            "records": len(label_rows),
            "exclusive_label_marker_detected": len(detected),
            "coverage": round(len(detected) / len(label_rows), 6),
            "wrong_label_marker_count": sum(row["marker_label"] != label for row in detected),
        }

    containment: dict[str, Any] = {}
    for label in LABELS:
        label_records = [row for row in records if row["label"] == label]
        contains = [row for row in label_records if normalize(row["premise"]) in normalize(row["hypothesis"])]
        identical = [row for row in label_records if normalize(row["premise"]) == normalize(row["hypothesis"])]
        containment[label] = {
            "records": len(label_records),
            "hypothesis_contains_full_normalized_premise": len(contains),
            "normalized_pair_identical": len(identical),
            "containment_rate": round(len(contains) / len(label_records), 6),
        }

    overlap_by_label = {
        label: rounded_stats(jaccard(row["premise"], row["hypothesis"]) for row in records if row["label"] == label)
        for label in LABELS
    }
    overlap_by_difficulty = {
        difficulty: rounded_stats(
            jaccard(row["premise"], row["hypothesis"])
            for row in records
            if row["difficulty_type"] == difficulty
        )
        for difficulty in sorted({row["difficulty_type"] for row in records})
    }

    marker_by_split: dict[str, Any] = {}
    for split, split_records in by_split.items():
        marker_by_split[split] = {}
        for label in LABELS:
            label_records = [row for row in split_records if row["label"] == label]
            detected = sum(marker_label(row["hypothesis"]) == label for row in label_records)
            marker_by_split[split][label] = {
                "records": len(label_records),
                "exclusive_label_marker_detected": detected,
                "coverage": round(detected / len(label_records), 6),
            }

    semantic_ids = {family for row in records for family in row["semantic_family_ids"]}
    all_question_only = all(re.fullmatch(r"question:[A-Z]{2}-\d{3}", family) for family in semantic_ids)
    authoring_methods = sorted({row["source"]["authoring_method"] for row in records})
    join_records = [
        row["case_id"]
        for row in records
        if re.search(r"\b(?:left|inner|right|full|outer)?\s*join\b", row["premise"] + " " + row["hypothesis"], re.IGNORECASE)
    ]
    sql_qids = sorted({row["question_id"] for row in records if re.search(r"\bSQL\b", row["premise"] + " " + row["hypothesis"], re.IGNORECASE)})

    return {
        "records": len(records),
        "questions": len(qid_counts),
        "records_per_question": dict(sorted(Counter(qid_counts.values()).items())),
        "question_ids": sorted(qid_counts),
        "distributions": {
            "label": distribution(records, "label"),
            "language_style": distribution(records, "language_style"),
            "difficulty_type": distribution(records, "difficulty_type"),
            "technical_domain": distribution(records, "technical_domain"),
        },
        "split_distributions": {
            split: {
                "records": len(split_records),
                "questions": len({row["question_id"] for row in split_records}),
                "label": distribution(split_records, "label"),
                "language_style": distribution(split_records, "language_style"),
                "difficulty_type": distribution(split_records, "difficulty_type"),
            }
            for split, split_records in by_split.items()
        },
        "surface_form_evidence": {
            "exclusive_label_marker_coverage": marker_summary,
            "exclusive_label_marker_coverage_by_split": marker_by_split,
            "premise_hypothesis_containment": containment,
            "token_jaccard_by_label": overlap_by_label,
            "token_jaccard_by_difficulty": overlap_by_difficulty,
            "entailment_paraphrase_records": sum(row["difficulty_type"] == "paraphrase_entailment" for row in records),
            "paraphrase_entailments_containing_full_premise": sum(
                row["difficulty_type"] == "paraphrase_entailment"
                and normalize(row["premise"]) in normalize(row["hypothesis"])
                for row in records
            ),
            "direct_contradictions_with_explicit_negation_marker": sum(
                row["difficulty_type"] == "direct_contradiction" and marker_label(row["hypothesis"]) == "contradiction"
                for row in records
            ),
            "neutral_cases_with_explicit_independence_marker": sum(
                row["label"] == "neutral" and marker_label(row["hypothesis"]) == "neutral" for row in records
            ),
            "shared_authoring_methods": authoring_methods,
            "semantic_family_ids_are_question_only": all_question_only,
            "template_or_generator_family_ids_recorded": not all_question_only,
            "interpretation": "Question-level splitting prevents source-question overlap but leaves the same label-specific wrappers, mutation operators, and 12-slot generation schedule in train and dev.",
        },
        "concept_coverage": {
            "join_term_record_count": len(join_records),
            "join_term_case_ids": join_records,
            "sql_term_source_question_ids": sql_qids,
            "interpretation": "DA-017 is correctly excluded, but the corpus contains no JOIN relation example; SQL mentions come from other concepts and do not teach JOIN cardinality or unmatched-row semantics.",
        },
    }


def transition_analysis(baseline_rows: list[dict[str, Any]], adapter_rows: list[dict[str, Any]]) -> dict[str, Any]:
    base = {row["case_id"]: row for row in baseline_rows}
    adapter = {row["case_id"]: row for row in adapter_rows}
    if set(base) != set(adapter) or len(base) != 45:
        raise ValueError("Baseline/adapter case sets do not match the frozen 45-case evaluation")

    cases: list[dict[str, Any]] = []
    for case_id in sorted(base):
        b = base[case_id]
        a = adapter[case_id]
        if b["expected_label"] != a["expected_label"]:
            raise ValueError(f"Expected label changed for {case_id}")
        b_probs = baseline_probabilities(b)
        a_probs = {label: float(a["probabilities"][label]) for label in LABELS}
        if not b["correct"] and a["correct"]:
            category = "fixed"
        elif b["correct"] and not a["correct"]:
            category = "regressed_new_failure"
        elif not b["correct"] and not a["correct"]:
            category = "unchanged_failure"
        else:
            category = "unchanged_correct"
        expected = b["expected_label"]
        cases.append({
            "case_id": case_id,
            "source_question_id": b["source_question_id"],
            "expected_label": expected,
            "language_style": b["language_style"],
            "difficulty_type": b["difficulty_type"],
            "regression_anchor": bool(b["regression_anchor"]),
            "baseline": {
                "predicted_label": b["predicted_label"],
                "correct": bool(b["correct"]),
                "probabilities": b_probs,
                "max_confidence": round(max(b_probs.values()), 6),
                "gold_probability": round(b_probs[expected], 6),
            },
            "lora": {
                "predicted_label": a["predicted_label"],
                "correct": bool(a["correct"]),
                "probabilities": a_probs,
                "max_confidence": round(max(a_probs.values()), 6),
                "gold_probability": round(a_probs[expected], 6),
            },
            "category": category,
            "prediction_changed": b["predicted_label"] != a["predicted_label"],
            "gold_probability_delta": round(a_probs[expected] - b_probs[expected], 6),
            "max_confidence_delta": round(max(a_probs.values()) - max(b_probs.values()), 6),
        })

    counts = Counter(row["category"] for row in cases)
    error_confidence = {}
    for name in ("baseline", "lora"):
        failed = [row[name] for row in cases if not row[name]["correct"]]
        error_confidence[name] = {
            "errors": len(failed),
            "mean_max_confidence": round(statistics.fmean(row["max_confidence"] for row in failed), 6),
            "high_confidence_errors_ge_0_90": sum(row["max_confidence"] >= 0.90 for row in failed),
            "high_confidence_error_case_ids": [
                row["case_id"] for row in cases if not row[name]["correct"] and row[name]["max_confidence"] >= 0.90
            ],
        }

    probability_shift = {
        label: round(
            statistics.fmean(row["lora"]["probabilities"][label] - row["baseline"]["probabilities"][label] for row in cases),
            6,
        )
        for label in LABELS
    }
    average_entropy = {
        "baseline": round(statistics.fmean(entropy(row["baseline"]["probabilities"]) for row in cases), 6),
        "lora": round(statistics.fmean(entropy(row["lora"]["probabilities"]) for row in cases), 6),
    }

    return {
        "counts": dict(sorted(counts.items())),
        "fixed_case_ids": [row["case_id"] for row in cases if row["category"] == "fixed"],
        "regressed_new_failure_case_ids": [row["case_id"] for row in cases if row["category"] == "regressed_new_failure"],
        "unchanged_failure_case_ids": [row["case_id"] for row in cases if row["category"] == "unchanged_failure"],
        "unchanged_failure_prediction_changed": [
            row["case_id"] for row in cases if row["category"] == "unchanged_failure" and row["prediction_changed"]
        ],
        "unchanged_correct_count": counts["unchanged_correct"],
        "predicted_label_counts": {
            "baseline": dict(sorted(Counter(row["baseline"]["predicted_label"] for row in cases).items())),
            "lora": dict(sorted(Counter(row["lora"]["predicted_label"] for row in cases).items())),
        },
        "mean_output_probability_shift_lora_minus_baseline": probability_shift,
        "average_predictive_entropy": average_entropy,
        "error_confidence": error_confidence,
        "cases": cases,
    }


def da017_analysis(cases: list[dict[str, Any]], baseline_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    explanations = {
        "NLI-EVAL-041": {
            "diagnosis": "New severe regression: the adapter turns a previously correct INNER JOIN paraphrase into a 0.988097 contradiction.",
            "most_supported_cause": "The synthetic near-neighbor contradiction regime broadens the contradiction boundary around technical term/relation changes, while training contains no JOIN semantics and most entailments preserve the premise wording.",
            "coverage_assessment": "Missing genuine relation-preserving paraphrases plus over-specialization to mutation templates; not label ambiguity.",
        },
        "NLI-EVAL-042": {
            "diagnosis": "The original LEFT JOIN false contradiction remains, at 0.965071 contradiction after adaptation.",
            "most_supported_cause": "No training example teaches the equivalence between the canonical LEFT JOIN definition and this natural Arabic/code-switched unmatched-left-row paraphrase.",
            "coverage_assessment": "Insufficient semantic paraphrase and concept coverage; no evidence that the expected entailment label is ambiguous.",
        },
        "NLI-EVAL-043": {
            "diagnosis": "The prediction moves from false entailment to neutral, but still misses the required contradiction.",
            "most_supported_cause": "The adapter learns to avoid entailment for some technical mismatches, but its simple lexical-replacement/explicit-negation contradictions do not teach the relational consequence that LEFT JOIN preserves unmatched left rows.",
            "coverage_assessment": "Partial boundary movement, insufficient relational hard-negative reasoning; not a fixed case.",
        },
        "NLI-EVAL-044": {
            "diagnosis": "The unrelated Python statement remains a high-confidence neutral and is the only passing post-LoRA anchor.",
            "most_supported_cause": "This is structurally similar to donor-based neutral training and does not exercise JOIN reasoning.",
            "coverage_assessment": "Easy neutral/template match; it does not offset the four semantic JOIN failures.",
        },
        "NLI-EVAL-045": {
            "diagnosis": "The Egyptian Arabic LEFT JOIN entailment remains a very high-confidence contradiction (0.983605).",
            "most_supported_cause": "Egyptian training coverage is numeric but mostly a fixed wrapper around copied canonical text, not independently worded dialectal paraphrase of relational semantics.",
            "coverage_assessment": "Surface-style quota met, semantic/dialect realization missing; expected label remains unambiguous.",
        },
    }
    output = []
    for row in cases:
        if row["case_id"] not in explanations:
            continue
        source = baseline_by_id[row["case_id"]]
        output.append({
            "case_id": row["case_id"],
            "premise": source["premise"],
            "hypothesis": source["hypothesis"],
            "expected_label": row["expected_label"],
            "baseline_prediction": row["baseline"]["predicted_label"],
            "lora_prediction": row["lora"]["predicted_label"],
            "baseline_probabilities": row["baseline"]["probabilities"],
            "lora_probabilities": row["lora"]["probabilities"],
            "category": row["category"],
            **explanations[row["case_id"]],
        })
    return output


def short_label(label: str) -> str:
    return {"entailment": "E", "neutral": "N", "contradiction": "C"}[label]


def format_probs(probabilities: dict[str, float]) -> str:
    return "/".join(f"{probabilities[label]:.6f}" for label in LABELS)


def md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(report: dict[str, Any]) -> str:
    corpus = report["training_corpus_analysis"]
    surface = corpus["surface_form_evidence"]
    transitions = report["error_transition_analysis"]
    markers = surface["exclusive_label_marker_coverage"]
    overlap = surface["token_jaccard_by_label"]

    lines = [
        "# CP-010 — Phase 2D LoRA Failure Diagnosis",
        "",
        "- Status: `VERIFIED_DIAGNOSIS_COMPLETE_NO_REMEDIATION`.",
        "- Decision: **DIAGNOSIS COMPLETE**.",
        "- Scope: artifact-only forensic analysis. No model was loaded, no inference/training ran, no dataset or adapter changed, and production/scoring/thresholds/retrieval/Fusion remain untouched.",
        "- CP-009 adapter remains evaluation-only and must not be promoted.",
        "",
        "## Executive conclusion",
        "",
        "The `1.0` internal-dev Macro F1 is not evidence that the adapter learned general InterviewIQ NLI reasoning. The train/dev split separated source question IDs but retained the same deterministic 12-case authoring grammar, label-specific wrappers, lexical mutation operators, and donor-neutral construction on both sides. The adapter learned that generated distribution extremely well, then failed to transfer to the natural, unmarked, relational paraphrases in frozen CP-005.",
        "",
        "The adapter did not simply stay neutral. It shifted the decision boundary away from entailment: predicted E/N/C counts changed `15/18/12 -> 11/20/14`; entailment recall fell `13/15 -> 11/15`; false contradictions rose `2/15 -> 3/15`. It fixed two cases and regressed two previously correct cases, leaving accuracy `37/45` unchanged. This is a data/validation-design generalization failure with a localized high-confidence contradiction problem, not a failed optimizer run.",
        "",
        "## 1. Generalization-gap evidence",
        "",
        "| Dimension | Training corpus | Frozen CP-005 | Diagnosis |",
        "|---|---|---|---|",
        "| Label balance | 200 E / 200 N / 200 C | 15 E / 15 N / 15 C | No count mismatch; imbalance is rejected as a cause. |",
        "| Language style | MSA 150; Egyptian 150; code-switch 180; transliteration 60; English 60 | MSA 10; Egyptian 9; code-switch 12; transliteration 5; English 9 | Categories overlap, but English is 10% vs 20%, and the training dialect/code-switch forms are mostly fixed wrappers rather than independently worded language. |",
        "| Difficulty | 180 paraphrase E; 20 preservation E; 110 near-neighbor C; 90 direct C; 120 technical N; 80 adjacent N | Ten natural evaluation categories | Names imply coverage, but mechanics do not: copy-plus-prefix entailments, explicit negations, and donor facts differ from CP-005's unmarked semantic decisions. |",
        f"| Concepts | 50 non-protected questions; JOIN term records: {corpus['concept_coverage']['join_term_record_count']} | 10 held-out questions; five DA-017 JOIN anchors | Exact exclusion is correct, but no independent relational/JOIN reasoning coverage exists. |",
        "| Split logic | 40 train questions / 10 dev questions | Fully frozen external evaluation | Question IDs are independent; authoring grammar and transformation families are not. |",
        "",
        "There is zero training/evaluation question overlap and the CP-005 leakage controls remain valid. The failure is therefore not record leakage. It is distribution leakage between train and internal dev: both were produced by the same generator.",
        "",
        "## 2. Training-corpus forensic analysis",
        "",
        f"- Exactly 50 questions contribute exactly 12 cases each: four per label. The same helper functions and slot schedule generate every train and dev question.",
        f"- Exclusive label-correlated opening markers occur in `{markers['entailment']['exclusive_label_marker_detected']}/200` entailments, `{markers['contradiction']['exclusive_label_marker_detected']}/200` contradictions, and `{markers['neutral']['exclusive_label_marker_detected']}/200` neutrals. Wrong-label marker count is zero.",
        f"- The train/dev marker rates are nearly identical: E `{surface['exclusive_label_marker_coverage_by_split']['train']['entailment']['coverage']:.1%}/{surface['exclusive_label_marker_coverage_by_split']['dev']['entailment']['coverage']:.1%}`, C `{surface['exclusive_label_marker_coverage_by_split']['train']['contradiction']['coverage']:.1%}/{surface['exclusive_label_marker_coverage_by_split']['dev']['contradiction']['coverage']:.1%}`, N `{surface['exclusive_label_marker_coverage_by_split']['train']['neutral']['coverage']:.1%}/{surface['exclusive_label_marker_coverage_by_split']['dev']['neutral']['coverage']:.1%}`.",
        f"- `{surface['paraphrase_entailments_containing_full_premise']}/{surface['entailment_paraphrase_records']}` records labelled `paraphrase_entailment` contain the entire normalized premise inside the hypothesis. Across all entailments, this is `{surface['premise_hypothesis_containment']['entailment']['hypothesis_contains_full_normalized_premise']}/200`.",
        f"- All `{surface['direct_contradictions_with_explicit_negation_marker']}` direct contradictions carry an explicit negation marker; `{surface['neutral_cases_with_explicit_independence_marker']}/200` neutrals explicitly announce that the claim is separate/independent.",
        f"- Mean premise/hypothesis token-Jaccard is E `{overlap['entailment']['mean']:.3f}`, C `{overlap['contradiction']['mean']:.3f}`, N `{overlap['neutral']['mean']:.3f}`. This makes lexical overlap and wrapper vocabulary strong class shortcuts.",
        "- `semantic_family_ids` encode only question IDs (and neutral donor question IDs). They do not encode generator, transformation, prefix, or mutation family, so the split validator cannot detect cross-split template reuse.",
        "- Training consumed only premise, hypothesis, and label. Rationales/review metadata were not model inputs, so the problem is visible surface construction, not rationale leakage.",
        "",
        "Assessment: the corpus is structurally valid, balanced, hash-frozen, externally reviewed, and leakage-controlled, but it is too easy and too template-like for the intended generalization claim. Human review can validate labels without making the generation distribution natural or independent.",
        "",
        "## 3. Every-case prediction transition",
        "",
        f"- Fixed: `{', '.join(transitions['fixed_case_ids'])}`.",
        f"- Regressed/new failures: `{', '.join(transitions['regressed_new_failure_case_ids'])}`.",
        f"- Unchanged failures: `{', '.join(transitions['unchanged_failure_case_ids'])}`. `NLI-EVAL-043` changes wrong class E->N but remains wrong.",
        f"- Unchanged correct: `{transitions['unchanged_correct_count']}` cases.",
        "",
        "| Case | Expected | Baseline | LoRA | Category | Δ gold probability |",
        "|---|---:|---:|---:|---|---:|",
    ]
    for row in transitions["cases"]:
        lines.append(
            f"| {row['case_id']} | {short_label(row['expected_label'])} | "
            f"{short_label(row['baseline']['predicted_label'])} | {short_label(row['lora']['predicted_label'])} | "
            f"{row['category']} | {row['gold_probability_delta']:+.6f} |"
        )

    lines.extend([
        "",
        "## 4. LoRA behavior",
        "",
        "| Boundary | Baseline | LoRA | Interpretation |",
        "|---|---|---|---|",
        "| Entailment | precision/recall/F1 0.8667/0.8667/0.8667 | 1.0000/0.7333/0.8462 | More conservative E boundary; four fewer E predictions and two true-E regressions. |",
        "| Neutral | 0.7778/0.9333/0.8485 | 0.7500/1.0000/0.8571 | Full recall, but broader N boundary and lower precision. |",
        "| Contradiction | 0.8333/0.6667/0.7407 | 0.7857/0.7333/0.7586 | Better recall but worse precision; boundary expands into true entailments. |",
        "",
        f"Mean output-probability shift is E `{transitions['mean_output_probability_shift_lora_minus_baseline']['entailment']:+.6f}`, N `{transitions['mean_output_probability_shift_lora_minus_baseline']['neutral']:+.6f}`, C `{transitions['mean_output_probability_shift_lora_minus_baseline']['contradiction']:+.6f}`. Average entropy rises `{transitions['average_predictive_entropy']['baseline']:.6f} -> {transitions['average_predictive_entropy']['lora']:.6f}`, so there is no evidence of uniform global overconfidence. However, error confidence is localized and severe: mean max-confidence on the eight errors rises `{transitions['error_confidence']['baseline']['mean_max_confidence']:.6f} -> {transitions['error_confidence']['lora']['mean_max_confidence']:.6f}`, with high-confidence LoRA errors on `{', '.join(transitions['error_confidence']['lora']['high_confidence_error_case_ids'])}`.",
        "",
        "Conclusion: the contradiction boundary is broader, not reliably better. The adapter learned useful signals for `007` and `035`, but it suppresses entailment and remains confidently wrong on the core relation-preserving paraphrases.",
        "",
        "## 5. DA-017 deep analysis",
        "",
        "Probabilities are shown E/N/C.",
        "",
        "| Case | Expected | Baseline | LoRA | Transition | Diagnosis |",
        "|---|---:|---|---|---|---|",
    ])
    for row in report["da017_deep_analysis"]:
        base_probs = format_probs(row["baseline_probabilities"])
        lora_probs = format_probs(row["lora_probabilities"])
        lines.append(
            f"| {row['case_id']} | {short_label(row['expected_label'])} | "
            f"{short_label(row['baseline_prediction'])} ({base_probs}) | "
            f"{short_label(row['lora_prediction'])} ({lora_probs}) | {row['category']} | {md_cell(row['diagnosis'])} |"
        )

    for row in report["da017_deep_analysis"]:
        lines.extend([
            "",
            f"### {row['case_id']}",
            "",
            f"- Premise: {row['premise']}",
            f"- Hypothesis: {row['hypothesis']}",
            f"- Most supported cause: {row['most_supported_cause']}",
            f"- Coverage assessment: {row['coverage_assessment']}",
        ])

    lines.extend([
        "",
        "DA-017 falls from `2/5` to `1/5` solely because `041` becomes a new failure; `042`, `043`, and `045` remain failures, while only the easy unrelated neutral `044` passes. The adapter does not learn JOIN semantics from the training set because no training record contains a JOIN relation.",
        "",
        "## 6. Root-cause hypothesis ranking",
        "",
        "| Rank | Hypothesis | Confidence | Evidence |",
        "|---:|---|---|---|",
    ])
    for item in report["ranked_root_cause_hypotheses"]:
        lines.append(
            f"| {item['rank']} | {md_cell(item['hypothesis'])} | {item['confidence']} | {md_cell(item['evidence'])} |"
        )

    lines.extend([
        "",
        "The CP-006 control strengthens this conclusion: the alternative checkpoint improved overall accuracy to `39/45` and macro F1 to `0.866270`, yet false contradictions stayed `2/15` and DA-017 stayed `2/5`. Changing weights can improve broad contradiction recognition, but neither checkpoint replacement nor the current templated LoRA resolves the critical relation-preserving paraphrase defect.",
        "",
        "## 7. Failed assumptions",
        "",
    ])
    lines.extend(f"- {item}" for item in report["failed_assumptions"])
    lines.extend([
        "",
        "## 8. What must change before any future training",
        "",
    ])
    lines.extend(f"- {item}" for item in report["required_before_any_future_training"])
    lines.extend([
        "",
        "These are prerequisites, not authorization to author a new dataset or train.",
        "",
        "## 9. LoRA versus another architecture",
        "",
        "- Current adapter: **reject for promotion; preserve as evaluation evidence only**.",
        "- LoRA approach: **pause, conditional—not abandoned**. A second run on the same corpus would repeat a falsified experiment. LoRA remains plausible only after a template-independent corpus and model-selection dev set exist.",
        "- Alternative: a semantic-verifier/cascade deserves a controlled comparison if independent data cannot make a revised LoRA generalize. It has higher latency/calibration complexity, but the CP-006 and CP-009 controls show that weight changes alone have not repaired the critical false-contradiction/DA-017 objective.",
        "- No architecture is selected for production by this diagnosis.",
        "",
        "## 10. Exact next step",
        "",
        report["exact_next_step"],
        "",
        "Stop. No data authoring, retraining, adapter modification, threshold/scoring change, or production promotion is authorized.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    result_dir = Path(__file__).resolve().parent
    root = result_dir.parents[1]

    paths = {relative: root / relative for relative in EXPECTED_HASHES}
    actual_hashes = {relative: sha256_file(path) for relative, path in paths.items()}
    mismatches = {
        relative: {"expected": EXPECTED_HASHES[relative], "actual": actual}
        for relative, actual in actual_hashes.items()
        if actual != EXPECTED_HASHES[relative]
    }
    if mismatches:
        raise ValueError(f"Frozen dependency hash mismatch: {mismatches}")

    cp005_dataset = read_json(paths["data/nli/evaluation/heldout_ar_codeswitch_v1.json"])
    corpus = read_json(paths["data/nli/training/phase2b_lora_corpus_v1.json"])
    split = read_json(paths["data/nli/training/phase2b_lora_split_manifest_v1.json"])
    baseline = read_json(paths["results/nli_baseline_cp005/current_model_baseline_v1.json"])
    cp006 = read_json(paths["results/nli_checkpoint_control_cp006/checkpoint_comparison_v1.json"])
    training = read_json(paths["results/nli_phase2c_training_cp009/training_metrics_v1.json"])
    adapter = read_json(paths["results/nli_phase2c_training_cp009/cp005_adapter_evaluation_v1.json"])

    records = list(corpus["records"])
    eval_rows = list(baseline["predictions"])
    adapter_rows = list(adapter["predictions"])
    corpus_result = corpus_analysis(records)
    transitions = transition_analysis(eval_rows, adapter_rows)
    base_by_id = {row["case_id"]: row for row in eval_rows}
    da017 = da017_analysis(transitions["cases"], base_by_id)

    corpus_qids = {row["question_id"] for row in records}
    eval_qids = {row["source_question_id"] for row in eval_rows}
    if corpus_qids & eval_qids:
        raise ValueError("Unexpected CP-005/training question overlap")
    if cp005_dataset.get("do_not_train") is not True:
        raise ValueError("CP-005 do_not_train control changed")
    if split["train"]["record_count"] != 480 or split["dev"]["record_count"] != 120:
        raise ValueError("Frozen split count changed")

    report = {
        "schema_version": 1,
        "diagnosis_id": "interviewiq-nli-phase2d-lora-failure-diagnosis-v1",
        "checkpoint": "CP-010",
        "created_at": CREATED_AT,
        "status": "VERIFIED_DIAGNOSIS_COMPLETE_NO_REMEDIATION",
        "scope": {
            "analysis_only": True,
            "model_loaded": False,
            "inference_run": False,
            "dataset_modified": False,
            "training_data_created": False,
            "adapter_trained_or_modified": False,
            "production_changed": False,
            "threshold_or_scoring_changed": False,
            "retrieval_or_fusion_changed": False,
        },
        "dependencies": {
            relative: {"sha256": actual_hashes[relative], "verified": True}
            for relative in sorted(actual_hashes)
        },
        "verified_inputs": {
            "cp005_cases": len(eval_rows),
            "cp005_do_not_train": cp005_dataset["do_not_train"],
            "training_records": len(records),
            "train_records": split["train"]["record_count"],
            "dev_records": split["dev"]["record_count"],
            "training_eval_question_overlap": sorted(corpus_qids & eval_qids),
            "training_best_internal_dev_macro_f1": training["trainer"]["best_metric"],
            "cp005_baseline_accuracy": baseline["metrics"]["all_scored_cases"]["accuracy"],
            "cp005_lora_accuracy": adapter["metrics"]["all_scored_cases"]["accuracy"],
            "cp005_baseline_macro_f1": baseline["metrics"]["all_scored_cases"]["macro_f1"],
            "cp005_lora_macro_f1": adapter["metrics"]["all_scored_cases"]["macro_f1"],
        },
        "generalization_gap": {
            "label_distribution_mismatch": {
                "training": corpus_result["distributions"]["label"],
                "cp005": distribution(eval_rows, "expected_label"),
                "assessment": "NONE: both are exactly balanced by label; label-count imbalance does not explain the gap.",
            },
            "language_distribution": {
                "training": corpus_result["distributions"]["language_style"],
                "cp005": distribution(eval_rows, "language_style"),
                "assessment": "Broad categories overlap, but English diagnostics are 10% of training versus 20% of CP-005, and the Arabic/Egyptian/code-switch training realizations are mostly deterministic wrappers rather than natural independent formulations.",
            },
            "difficulty_distribution": {
                "training": corpus_result["distributions"]["difficulty_type"],
                "cp005": distribution(eval_rows, "difficulty_type"),
                "assessment": "Names and counts suggest coverage, but their operational meanings differ: training paraphrases are predominantly copy-plus-prefix, direct contradictions are explicit negations, and neutrals are donor facts with independence markers; CP-005 requires unmarked semantic and relational decisions.",
            },
            "concept_and_reasoning_mismatch": {
                "training_question_count": len(corpus_qids),
                "cp005_question_count": len(eval_qids),
                "question_overlap": sorted(corpus_qids & eval_qids),
                "join_term_record_count": corpus_result["concept_coverage"]["join_term_record_count"],
                "assessment": "Exact exclusion works, but the independent training concepts include no JOIN examples and do not cover LEFT/INNER cardinality, matched/unmatched-row preservation, or equivalent bilingual relational statements.",
            },
            "reasoning_pattern_mismatch": {
                "assessment": "The generator teaches label-correlated surface operations (copy/prefix, explicit negation or one phrase replacement, donor-plus-independent marker). CP-005 failures require compositional paraphrase, scope, cardinality, and near-neighbor relational reasoning without those markers.",
            },
        },
        "training_corpus_analysis": corpus_result,
        "error_transition_analysis": transitions,
        "da017_deep_analysis": da017,
        "lora_behavior": {
            "entailment_boundary": "WORSE_AND_MORE_CONSERVATIVE: predicted entailments fall 15->11; entailment recall falls 13/15->11/15; two baseline-correct entailments become non-entailments.",
            "contradiction_boundary": "BROADER_NOT_RELIABLY_BETTER: true-contradiction recall improves 10/15->11/15, but contradiction precision falls 10/12->11/14 and false contradictions rise 2/15->3/15.",
            "neutral_boundary": "MORE_COMPLETE_BUT_BROADER: neutral recall improves 14/15->15/15 while predicted neutrals rise 18->20 and precision falls 14/18->15/20.",
            "class_bias_shift": "The adapter moves four predictions away from entailment: entailment 15->11, neutral 18->20, contradiction 12->14.",
            "overconfidence": transitions["error_confidence"],
            "memorization_assessment": "Strong evidence of generator/template shortcut learning and distribution memorization; no evidence of CP-005 record memorization because exact question/premise/hypothesis/pair overlap is zero. Perfect question-held-out dev is not independent of the shared authoring grammar.",
            "optimization_assessment": "Optimization completed normally (rapid loss convergence and perfect internal dev). The frozen-held-out failure therefore points to representation/data-distribution mismatch, not an incomplete training run.",
        },
        "cp006_control_context": {
            "candidate_accuracy": cp006["metrics"]["accuracy"]["candidate"],
            "candidate_macro_f1": cp006["metrics"]["macro_f1"]["candidate"],
            "candidate_false_contradiction_rate": cp006["metrics"]["false_contradiction_rate"]["candidate"],
            "candidate_da017_correct": sum(
                bool(row["candidate_pass"]) for row in cp006["DA017_regression_anchors"]["cases"]
            ),
            "assessment": "A stronger checkpoint improved broad CP-005 classification but did not reduce false contradictions or improve DA-017, so checkpoint swapping alone also fails the critical relational-paraphrase defect.",
        },
        "ranked_root_cause_hypotheses": [
            {
                "rank": 1,
                "hypothesis": "Cross-split authoring-template shortcut makes internal dev non-independent.",
                "confidence": "HIGH",
                "evidence": "All questions use the same 12-slot generator; label-exclusive wrappers cover 170/200 entailments, 150/200 contradictions, and 180/200 neutrals, with nearly identical train/dev rates; semantic_family_ids encode questions only, not generator/template families; dev reaches 1.0 while CP-005 does not improve.",
            },
            {
                "rank": 2,
                "hypothesis": "Synthetic examples do not match natural semantic reasoning difficulty.",
                "confidence": "HIGH",
                "evidence": "Most purported paraphrase entailments retain the full premise; all direct contradictions have explicit negation markers; most neutrals announce independence; CP-005 errors are unmarked paraphrase, scope, and relational near-neighbor decisions.",
            },
            {
                "rank": 3,
                "hypothesis": "Contradiction-focused mutations over-broaden the non-entailment boundary and suppress entailment.",
                "confidence": "HIGH",
                "evidence": "Predicted entailments drop 15->11; true-entailment recall drops 13/15->11/15; false contradictions rise 2->3; NLI-EVAL-041 flips from correct entailment to 0.988097 contradiction.",
            },
            {
                "rank": 4,
                "hypothesis": "DA-017 relational concept and natural dialectal paraphrase coverage is absent.",
                "confidence": "HIGH",
                "evidence": "Zero training records contain a JOIN term; Egyptian/code-switch quotas are satisfied largely with wrappers around canonical text; DA-017 falls 2/5->1/5.",
            },
            {
                "rank": 5,
                "hypothesis": "Base-family capacity/calibration remains a contributing limitation.",
                "confidence": "MEDIUM",
                "evidence": "Both the CP-006 checkpoint control and CP-009 adapter fail the critical false-contradiction/DA-017 gates, although they move other contradiction cases in useful directions.",
            },
            {
                "rank": 6,
                "hypothesis": "Label imbalance, CP-005 leakage, or failed optimizer execution caused the gap.",
                "confidence": "REJECTED_BY_EVIDENCE",
                "evidence": "Labels are exactly balanced, frozen leakage checks are zero, hashes are unchanged, and training converged with validated artifacts.",
            },
        ],
        "failed_assumptions": [
            "A complete-question train/dev split was assumed to be sufficient; it did not isolate the shared generator and label wrappers.",
            "Difficulty labels such as paraphrase_entailment and near_neighbor_contradiction were assumed to imply natural reasoning diversity; generation mechanics show otherwise.",
            "Matching language/style counts was assumed to imply representative dialect/code-switch coverage; many examples are canonical text plus a fixed wrapper.",
            "Perfect internal dev was assumed to predict held-out gain; the dev set measured generalization to new questions under the same authoring grammar.",
            "Simple lexical mutations were assumed to teach technical relation boundaries; DA-017 requires compositional row-preservation/cardinality reasoning.",
        ],
        "required_before_any_future_training": [
            "Define and audit generator/template family IDs, then split them so no authoring template or transformation operator is shared between train and model-selection dev.",
            "Require independently worded natural Arabic, Egyptian, code-switched, and English pairs; reject copy-plus-prefix paraphrases and label-revealing wrappers.",
            "Add unmarked hard entailment/contradiction/neutral contrasts that vary one semantic relation, scope, direction, cardinality, or exception while preserving surface similarity.",
            "Cover relational technical reasoning through independent non-CP-005 concepts and examples; keep every CP-005 case/question/premise/hypothesis/pair excluded.",
            "Create a separate template-independent diagnostic/dev set for training selection; keep CP-005 frozen as the final acceptance set and do not tune to its 45 labels.",
            "Pre-register a one-variable comparison that can distinguish revised-data LoRA from a semantic-verifier/cascade alternative before authoring or training begins.",
        ],
        "approach_decision": {
            "current_adapter": "REJECTED_FOR_PROMOTION_EVALUATION_ONLY",
            "lora": "PAUSE_CONDITIONAL_NOT_ABANDONED",
            "recommendation": "Do not run a second LoRA on the current corpus. The immediate problem is the experiment's data/validation design. LoRA remains viable only after template-independent evidence exists; otherwise prioritize a controlled semantic-verifier/cascade experiment because checkpoint replacement and the current adapter both miss the critical false-contradiction/DA-017 objective.",
        },
        "exact_next_step": "Await explicit Phase 2E design-only authorization to specify a template-independent corpus/diagnostic protocol and a pre-registered one-variable comparison between revised-data LoRA and a semantic-verifier/cascade. Do not author data, train, tune on CP-005, modify the adapter, or change production.",
        "decision": "DIAGNOSIS_COMPLETE",
    }

    output_path = result_dir / "lora_failure_diagnosis_v1.json"
    write_json(output_path, report)
    markdown_path = result_dir / "lora_failure_diagnosis_v1.md"
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    print("CP010_DIAGNOSIS=PASS")
    print(f"OUTPUT={output_path}")
    print(f"OUTPUT_SHA256={sha256_file(output_path)}")
    print(f"REPORT={markdown_path}")
    print(f"REPORT_SHA256={sha256_file(markdown_path)}")
    print(f"TRANSITIONS={json.dumps(report['error_transition_analysis']['counts'], sort_keys=True)}")
    print(f"MARKER_COVERAGE={json.dumps(report['training_corpus_analysis']['surface_form_evidence']['exclusive_label_marker_coverage'], sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
