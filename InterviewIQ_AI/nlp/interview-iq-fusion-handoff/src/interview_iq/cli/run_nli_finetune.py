"""
cli/run_nli_finetune.py — Phase 4 LoRA fine-tuning entrypoint.

Usage:
    python -m interview_iq.cli.run_nli_finetune [--data-dir PATH] [--configs-dir PATH] [--output-dir PATH]

This is the single CLI line the Kaggle thin-runner notebook invokes — zero
training logic lives in the notebook itself (see kaggle/runners/run-nli-finetune.ipynb).
All hyperparameters come from configs/nli_finetune.yaml via Config, which
prints/logs the PRE-CALIBRATION tag on load for every unvalidated value.

⚠️ RISK ACCEPTED (D33): see the notice printed below and decisions.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from interview_iq.config import Config
from interview_iq.nli.finetune import run_finetune

RISK_ACCEPTED_NOTICE = (
    "\n"
    + "!" * 78
    + "\n"
    "RISK ACCEPTED (D33): Stage-4 human review of the 150 pilot pairs is not yet\n"
    "closed (>=20% retroactive spot-check recommended, still pending). Any result\n"
    "from this run is methodologically provisional until Gate G1 is closed --\n"
    "see decisions.md D33. D28 (DS-014 exclusion) and D26 (twin integrity) are\n"
    "still re-asserted as hard gates below; only the human pair-review gate is open.\n"
    + "!" * 78
    + "\n"
)


def _repo_root() -> Path:
    # src/interview_iq/cli/run_nli_finetune.py -> cli -> interview_iq -> src -> repo root
    return Path(__file__).resolve().parents[3]


def _resolve_data_path(repo_root: Path, data_dir_override: Path | None, config_relative_path: str) -> Path:
    """config_relative_path looks like "data/refdocs/foo.json" (relative to
    repo_root). When --data-dir overrides the data/ directory (e.g. to point
    at a fixture set), re-anchor everything after the leading "data/" there."""
    if data_dir_override is None:
        return repo_root / config_relative_path
    parts = Path(config_relative_path).parts
    if parts and parts[0] == "data":
        parts = parts[1:]
    return data_dir_override.joinpath(*parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 4: LoRA fine-tuning for the Interview IQ NLI model.")
    parser.add_argument("--data-dir", type=Path, default=None, help="Override the data/ directory.")
    parser.add_argument("--configs-dir", type=Path, default=None, help="Override the configs/ directory.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Override the checkpoint output directory.")
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    cfg = Config(configs_dir=args.configs_dir)
    data_cfg = cfg.nli_finetune["data"]
    output_cfg = cfg.nli_finetune["output"]

    print(RISK_ACCEPTED_NOTICE)

    refdocs_path = _resolve_data_path(repo_root, args.data_dir, data_cfg["refdocs_file"])
    pilot_pair_paths = [
        _resolve_data_path(repo_root, args.data_dir, data_cfg["pilot_file_da001"]),
        _resolve_data_path(repo_root, args.data_dir, data_cfg["pilot_file_remaining"]),
    ]
    output_dir = args.output_dir if args.output_dir is not None else (repo_root / output_cfg["checkpoint_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Base model: {cfg.nli_model}")
    print(f"Refdocs:    {refdocs_path}")
    print(f"Pilot data: {[str(p) for p in pilot_pair_paths]}")
    print(f"Output dir: {output_dir}")
    print()

    result = run_finetune(
        cfg=cfg,
        refdocs_path=refdocs_path,
        pilot_pair_paths=pilot_pair_paths,
        output_dir=output_dir,
    )

    print()
    print(f"Train pairs: {result.n_train_pairs}  |  Val pairs: {result.n_val_pairs}")
    print(f"Eval metrics: {result.eval_metrics}")
    print(f"Checkpoint saved to: {result.output_dir}")
    print(f"Publish this directory as the Kaggle Dataset '{output_cfg['kaggle_dataset']}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
