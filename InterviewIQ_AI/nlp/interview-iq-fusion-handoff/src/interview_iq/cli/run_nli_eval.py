"""
cli/run_nli_eval.py — Phase 5 Gold Set evaluation entrypoint.

Usage:
    python -m interview_iq.cli.run_nli_eval --zero-shot --output-json out/zero_shot.json
    python -m interview_iq.cli.run_nli_eval --adapter-path /path/to/adapter --output-json out/adapter.json

--adapter-path and --zero-shot are mutually exclusive. Omitting both defaults
to zero-shot (per PROJECT_EXECUTION_PLAN.md Phase 5: "--adapter-path optional;
omit for zero-shot"). Run this script twice (once per arm) to produce the
zero-shot vs. adapter comparison — see kaggle/runners/run-nli-eval.ipynb.

Pass --compare-with <other_report.json> on the second (adapter) run to guard
against a silently-inert adapter: if every per-pair prediction matches the
comparison report, this process exits non-zero with
"SILENT ADAPTER FAILURE SUSPECTED" (Phase 5 Task D.3).

This script REPORTS the pre-registered metrics. It does not pick or tune any
threshold, and it does not render a verdict on Subject Blindness — that is a
human judgment made by comparing the two JSON reports side by side.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from interview_iq.config import Config
from interview_iq.evaluation.gold_eval import GoldEvalReport, run_gold_eval

RISK_ACCEPTED_NOTICE = (
    "\n"
    + "!" * 78
    + "\n"
    "RISK ACCEPTED (D33): Gate G1 (Stage-4 per-pair human review of the 150\n"
    "pilot pairs) is CLOSED BY ACCEPTED RISK, not by completed review -- Ahmed's\n"
    "explicit decision under time pressure (decisions.md D33). The 150 pairs\n"
    "underwent automated + qualitative review (Stages 1-3) and the 10 reference\n"
    "documents were manually reviewed, but not per-pair Stage-4 human review.\n"
    "Every result below, including this Gold Set evaluation, is tagged\n"
    "RISK ACCEPTED under that closed gate.\n"
    + "!" * 78
    + "\n"
)

NO_VERDICT_NOTICE = (
    "\n"
    + "-" * 78
    + "\n"
    "NOTE: This script reports numbers (per-class F1, confusion matrix, E<->C\n"
    "cells, macro-F1). It does NOT render a verdict on whether Subject Blindness\n"
    "is fixed -- that is a human judgment, made by comparing the zero-shot and\n"
    "adapter JSON reports side by side.\n"
    + "-" * 78
)


def _guard_against_silent_adapter_failure(report: GoldEvalReport, compare_with: Path) -> None:
    """Fail-loud guard (Phase 5 Task D.3): if this report's per-pair
    predictions are byte-identical to a previously written report (e.g. the
    zero-shot run this adapter run is meant to differ from) on every pair,
    that is strong evidence the adapter never attached / had zero effect.
    Exits the process non-zero rather than silently reporting misleading
    "results" -- the JSON is still written to disk first for investigation."""
    if not compare_with.exists():
        print(f"\n[guard] --compare-with path does not exist, skipping: {compare_with}")
        return

    with compare_with.open("r", encoding="utf-8") as fh:
        other = json.load(fh)
    other_preds = {p["pair_id"]: p["predicted_label"] for p in other.get("predictions", [])}
    this_preds = {p.pair_id: p.predicted_label for p in report.predictions}

    if set(other_preds) != set(this_preds):
        print(f"\n[guard] pair_id sets differ from {compare_with} -- cannot compare, skipping guard.")
        return

    if this_preds and all(other_preds[pid] == this_preds[pid] for pid in this_preds):
        print("\n" + "!" * 78)
        print("SILENT ADAPTER FAILURE SUSPECTED")
        print(
            f"All {len(this_preds)} predictions in this report ({report.mode}) are identical "
            f"to every prediction in {compare_with}."
        )
        print(
            "This means the two runs produced the exact same output on all 48 Gold Set pairs --"
            "\nalmost certainly the adapter never attached / had zero effect on the model's output."
            "\nInvestigate before trusting either report."
        )
        print("!" * 78)
        sys.exit(1)

    print(f"\n[guard] OK -- predictions differ from {compare_with} on at least one pair.")


def _assert_matches_reference(report: GoldEvalReport, reference_path: Path) -> None:
    """Reproducibility gate (mandatory rerun check): this run's 48 per-pair
    predicted_label values must be IDENTICAL to a frozen reference (e.g.
    results/phase5/gold_eval_*.json, the D41 artifacts). Adding V2
    probabilities must not change argmax -- if even one label differs, the
    inference path is nondeterministic, which is a more serious problem than
    anything Q8 raises: it would mean no number in decisions.md D41 is
    reproducible. Exits non-zero and prints every mismatch; never silently
    overwrites the frozen reference."""
    if not reference_path.exists():
        print(f"\n[reproducibility gate] FAILED -- reference path does not exist: {reference_path}")
        sys.exit(1)

    with reference_path.open("r", encoding="utf-8") as fh:
        reference = json.load(fh)
    ref_preds = {p["pair_id"]: p["predicted_label"] for p in reference.get("predictions", [])}
    this_preds = {p.pair_id: p.predicted_label for p in report.predictions}

    if set(ref_preds) != set(this_preds):
        print(f"\n[reproducibility gate] FAILED -- pair_id sets differ from {reference_path}.")
        print(f"  Only in reference: {sorted(set(ref_preds) - set(this_preds))}")
        print(f"  Only in this run:  {sorted(set(this_preds) - set(ref_preds))}")
        sys.exit(1)

    mismatches = [(pid, ref_preds[pid], this_preds[pid]) for pid in sorted(this_preds) if ref_preds[pid] != this_preds[pid]]
    if mismatches:
        print("\n" + "!" * 78)
        print("REPRODUCIBILITY GATE FAILED -- inference is nondeterministic")
        print(f"{len(mismatches)}/{len(this_preds)} pair(s) differ from the frozen reference {reference_path}:")
        for pid, ref_label, this_label in mismatches:
            print(f"  {pid}: reference={ref_label!r}  this_run={this_label!r}")
        print(
            "Adding V2 probabilities must not change argmax classification. A mismatch\n"
            "here means the inference path itself is nondeterministic -- more serious\n"
            "than anything Q8 raises, since it means no number in decisions.md D41 is\n"
            "reproducible. FAILING LOUDLY rather than quietly overwriting D41."
        )
        print("!" * 78)
        sys.exit(1)

    print(f"\n[reproducibility gate] PASSED -- all {len(this_preds)} predictions match {reference_path} exactly.")


def _repo_root() -> Path:
    # src/interview_iq/cli/run_nli_eval.py -> cli -> interview_iq -> src -> repo root
    return Path(__file__).resolve().parents[3]


def _resolve_data_path(repo_root: Path, data_dir_override: Path | None, config_relative_path: str) -> Path:
    """config_relative_path looks like "data/nli/gold_set_48.json" (relative
    to repo_root). When --data-dir overrides the data/ directory, re-anchor
    everything after the leading "data/" there."""
    if data_dir_override is None:
        return repo_root / config_relative_path
    parts = Path(config_relative_path).parts
    if parts and parts[0] == "data":
        parts = parts[1:]
    return data_dir_override.joinpath(*parts)


def _print_report(report: GoldEvalReport) -> None:
    print(f"Mode: {report.mode}")
    print(f"N pairs: {report.n_pairs}")
    print()
    print(f"{'label':<14}{'precision':>10}{'recall':>10}{'f1':>10}{'support':>10}")
    for label in report.label_order:
        m = report.per_class[label]
        print(f"{label:<14}{m['precision']:>10.3f}{m['recall']:>10.3f}{m['f1']:>10.3f}{m['support']:>10.0f}")
    print(f"\nmacro-F1: {report.macro_f1:.3f}")

    print("\nConfusion matrix (rows=gold, cols=predicted):")
    header = " " * 16 + "".join(f"{label:>14}" for label in report.label_order)
    print(header)
    for gold_label in report.label_order:
        row = "".join(f"{report.confusion_matrix[gold_label][pred_label]:>14}" for pred_label in report.label_order)
        print(f"{gold_label:<16}{row}")

    print("\nSubject Blindness signature:")
    print(
        f"  E->C: {report.e_to_c_count} / {int(report.per_class['entailment']['support'])} "
        f"entailment pairs misclassified as contradiction ({report.e_to_c_rate:.1%})"
    )
    print(
        f"  C->E: {report.c_to_e_count} / {int(report.per_class['contradiction']['support'])} "
        f"contradiction pairs misclassified as entailment ({report.c_to_e_rate:.1%})"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 5: Gold Set evaluation for the Interview IQ NLI model.")
    parser.add_argument(
        "--adapter-path", type=Path, default=None, help="Path to a LoRA adapter checkpoint. Omit for zero-shot."
    )
    parser.add_argument(
        "--zero-shot", action="store_true", help="Force zero-shot evaluation (base model only), even over --adapter-path."
    )
    parser.add_argument("--output-json", type=Path, required=True, help="Where to write the structured JSON report.")
    parser.add_argument(
        "--compare-with",
        type=Path,
        default=None,
        help=(
            "Path to a previously written JSON report (e.g. the zero-shot report). "
            "If every per-pair prediction matches, exits non-zero with "
            "SILENT ADAPTER FAILURE SUSPECTED. Written report is saved to --output-json first."
        ),
    )
    parser.add_argument(
        "--assert-matches",
        type=Path,
        default=None,
        help=(
            "Reproducibility gate: path to a frozen reference JSON report (e.g. "
            "results/phase5/gold_eval_zero_shot.json). Exits non-zero and prints every "
            "mismatch if even one of the 48 predicted_label values differs from it."
        ),
    )
    parser.add_argument("--data-dir", type=Path, default=None, help="Override the data/ directory.")
    parser.add_argument("--configs-dir", type=Path, default=None, help="Override the configs/ directory.")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=256)
    args = parser.parse_args(argv)

    if args.adapter_path is not None and args.zero_shot:
        parser.error("--adapter-path and --zero-shot are mutually exclusive.")

    repo_root = _repo_root()
    cfg = Config(configs_dir=args.configs_dir)
    data_cfg = cfg.nli_finetune["data"]
    gold_set_path = _resolve_data_path(repo_root, args.data_dir, data_cfg["gold_set_file"])

    zero_shot = args.zero_shot or args.adapter_path is None

    print(RISK_ACCEPTED_NOTICE)
    print(f"Base model: {cfg.nli_model}")
    print(f"Gold set:   {gold_set_path}")
    print(f"Mode:       {'ZERO-SHOT (base model, no adapter)' if zero_shot else f'ADAPTER ({args.adapter_path})'}")
    print()

    report = run_gold_eval(
        cfg=cfg,
        gold_set_path=gold_set_path,
        adapter_path=args.adapter_path,
        zero_shot=zero_shot,
        batch_size=args.batch_size,
        max_length=args.max_length,
    )

    _print_report(report)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    with args.output_json.open("w", encoding="utf-8") as fh:
        json.dump(report.to_dict(), fh, ensure_ascii=False, indent=2)
    print(f"\nWrote structured report to: {args.output_json}")

    if args.compare_with is not None:
        _guard_against_silent_adapter_failure(report, args.compare_with)  # exits non-zero on match

    if args.assert_matches is not None:
        _assert_matches_reference(report, args.assert_matches)  # exits non-zero on any mismatch

    print(NO_VERDICT_NOTICE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
