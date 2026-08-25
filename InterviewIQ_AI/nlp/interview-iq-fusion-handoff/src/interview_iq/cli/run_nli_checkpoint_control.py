"""CLI for the CP-006 Phase-2A NLI checkpoint-control experiment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from interview_iq.evaluation.checkpoint_control import (
    CheckpointControlError,
    compare_checkpoint_results,
    evaluate_checkpoint,
    load_and_validate_dataset,
    load_manifest,
    render_comparison_markdown,
    sha256_file,
    validate_training_separation,
    validate_completed_artifacts,
    verify_snapshot_files,
    write_json,
)


def _path(value: str) -> Path:
    return Path(value).resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pinned CPU/fp32 checkpoint-control evaluation on frozen CP-005. No training or production change."
    )
    parser.add_argument("--project-root", type=_path, default=Path.cwd(), help="NLP handoff repository root")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Run manifest, snapshot, dataset, and leakage preflight only")
    validate.add_argument("--manifest", type=_path, required=True)
    validate.add_argument("--training-manifest", type=_path, action="append", default=[])
    validate.add_argument("--output", type=_path)

    evaluate = subparsers.add_parser("evaluate", help="Evaluate exactly one manifest model in this fresh process")
    evaluate.add_argument("--manifest", type=_path, required=True)
    evaluate.add_argument("--model-key", choices=("baseline", "candidate"), required=True)
    evaluate.add_argument("--training-manifest", type=_path, action="append", default=[])
    evaluate.add_argument("--output", type=_path, required=True)

    compare = subparsers.add_parser("compare", help="Compare two completed result artifacts without loading a model")
    compare.add_argument("--manifest", type=_path, required=True)
    compare.add_argument("--baseline-result", type=_path, required=True)
    compare.add_argument("--candidate-result", type=_path, required=True)
    compare.add_argument("--output-json", type=_path, required=True)
    compare.add_argument("--output-md", type=_path, required=True)

    audit = subparsers.add_parser("audit", help="Recompute and validate completed artifacts without loading a model")
    audit.add_argument("--manifest", type=_path, required=True)
    audit.add_argument("--baseline-result", type=_path, required=True)
    audit.add_argument("--candidate-result", type=_path, required=True)
    audit.add_argument("--comparison", type=_path, required=True)
    audit.add_argument("--output", type=_path, required=True)

    return parser


def run_validate(args: argparse.Namespace) -> dict:
    manifest = load_manifest(args.manifest)
    _, cases, dataset_controls = load_and_validate_dataset(args.project_root, manifest)
    training_manifests = [(path, json.loads(path.read_text(encoding="utf-8"))) for path in args.training_manifest]
    separation = validate_training_separation(
        cases,
        set(manifest["leakage_controls"]["protected_question_ids"]),
        training_manifests,
        eval_dataset_path=(args.project_root / manifest["dataset"]["path"]).resolve(),
    )
    snapshot_files = {key: verify_snapshot_files(spec) for key, spec in manifest["models"].items()}
    result = {
        "status": "PASS",
        "manifest_sha256": sha256_file(args.manifest),
        "dataset_controls": dataset_controls,
        "training_separation": separation,
        "snapshot_files": snapshot_files,
    }
    if args.output:
        write_json(args.output, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            result = run_validate(args)
            print(f"Phase-2A preflight: {result['status']}")
            return 0
        if args.command == "evaluate":
            result = evaluate_checkpoint(
                project_root=args.project_root,
                manifest_path=args.manifest,
                model_key=args.model_key,
                training_manifest_paths=args.training_manifest,
            )
            write_json(args.output, result)
            overall = result["metrics"]["all_scored_cases"]
            print(
                f"{args.model_key}: accuracy={overall['accuracy']:.6f} "
                f"macro_f1={overall['macro_f1']:.6f} output={args.output}"
            )
            return 0
        if args.command == "compare":
            comparison = compare_checkpoint_results(
                project_root=args.project_root,
                manifest_path=args.manifest,
                baseline_result_path=args.baseline_result,
                candidate_result_path=args.candidate_result,
            )
            write_json(args.output_json, comparison)
            args.output_md.parent.mkdir(parents=True, exist_ok=True)
            args.output_md.write_text(render_comparison_markdown(comparison), encoding="utf-8")
            print(f"Comparison complete; automatic_winner={comparison['automatic_winner']!r}")
            return 0
        if args.command == "audit":
            validation = validate_completed_artifacts(
                project_root=args.project_root,
                manifest_path=args.manifest,
                baseline_result_path=args.baseline_result,
                candidate_result_path=args.candidate_result,
                comparison_path=args.comparison,
            )
            write_json(args.output, validation)
            print(f"Completed-artifact audit: {validation['status']}")
            return 0
    except (CheckpointControlError, OSError, ValueError) as exc:
        print(f"CHECKPOINT CONTROL FAILED: {exc}", file=sys.stderr)
        return 2
    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
