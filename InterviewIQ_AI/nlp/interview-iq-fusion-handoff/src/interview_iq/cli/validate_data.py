"""
cli/validate_data.py — Phase 3 Data Layer validation gate.

Usage:
    python -m interview_iq.cli.validate_data [--data-dir PATH] [--configs-dir PATH]

Runs every mandatory validation from PROJECT_EXECUTION_PLAN.md Phase 3 against
the real data files in `data/` (or a fixture directory passed via
--data-dir), prints a full report, and exits non-zero on any HARD failure —
this is the gate before Phase 4 (fine-tuning) may proceed.

Hard failures (non-zero exit):
    1. JSON schema validity for every data file.
    2. Chunk-ID uniqueness across all reference docs (expect 1,515).
    3. Every pair's chunk_id resolves to an existing chunk.
    4. D28 gate — excluded question_id(s) never in a training premise pool.
    5. D26 twin integrity — HARD_POS twins (expect 30 claim groups).
    6. Pilot label distribution E=50 / C=60 / N=40 over 150 pairs.
    7. Splitting logic is Question-ID-level ready.
    V3. key_points integrity per document (D42): non-empty, no duplicate
        chunk_id within a document's key_points, every chunk_id resolves
        (enforced inside refdocs.loader.load_reference_docs itself — a
        dangling key_point permanently caps that document's Coverage).

Documented exceptions / diagnostics (reported, never fail the gate):
    8. D35 — 5-consecutive-word overlap count + violators' label distribution.
    9. Q4  — stage2_verdict presence on pairs_DA001_pilot_v1.json.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from interview_iq.config import Config
from interview_iq.nli.dataset import (
    CheckResult,
    NLIDataSchemaError,
    check_chunk_resolution,
    check_ds014_exclusion,
    check_five_word_overlap,
    check_hard_pos_twin_integrity,
    check_label_distribution,
    check_question_id_split_readiness,
    check_stage2_verdict_presence,
    load_gold_set,
    load_pilot_pairs,
)
from interview_iq.refdocs.loader import (
    ChunkUniquenessError,
    RefDocsSchemaError,
    load_reference_docs,
)

# Production-data invariants (not schema properties — see refdocs/loader.py docstring).
EXPECTED_DOC_COUNT = 250
EXPECTED_CHUNK_COUNT = 1_515
EXPECTED_HARD_POS_GROUPS = 30
EXPECTED_LABEL_DISTRIBUTION = {"entailment": 50, "contradiction": 60, "neutral": 40}

REQUIRED_QUESTION_KEYS = {"question_id", "track", "text"}

_ICONS = {"HARD": {True: "✅", False: "❌"}, "WARNING": "⚠️", "INFO": "ℹ️"}


def _repo_root() -> Path:
    # src/interview_iq/cli/validate_data.py -> cli -> interview_iq -> src -> repo root
    return Path(__file__).resolve().parents[3]


def _print_result(r: CheckResult) -> None:
    icon = _ICONS["HARD"][r.passed] if r.severity == "HARD" else _ICONS[r.severity]
    print(f"{icon} [{r.severity}] {r.name}: {r.message}")


def _validate_questions_schema(path: Path) -> tuple[bool, str, int]:
    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, dict) or "meta" not in raw or "questions" not in raw:
        raise NLIDataSchemaError(f"{path}: top-level object must contain 'meta' and 'questions'")
    questions = raw["questions"]
    if not isinstance(questions, list) or not questions:
        raise NLIDataSchemaError(f"{path}: 'questions' must be a non-empty list")
    seen: set[str] = set()
    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            raise NLIDataSchemaError(f"{path}: questions[{i}] is not an object")
        missing = REQUIRED_QUESTION_KEYS - q.keys()
        if missing:
            raise NLIDataSchemaError(f"{path}: questions[{i}] missing keys {sorted(missing)}")
        if q["question_id"] in seen:
            raise NLIDataSchemaError(f"{path}: duplicate question_id {q['question_id']!r}")
        seen.add(q["question_id"])
    return True, f"{len(questions)} questions schema-valid.", len(questions)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the Interview IQ data layer (Phase 3).")
    parser.add_argument(
        "--data-dir", type=Path, default=None, help="Override the data/ directory (e.g. for fixtures)."
    )
    parser.add_argument(
        "--configs-dir", type=Path, default=None, help="Override the configs/ directory."
    )
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    data_dir = args.data_dir if args.data_dir is not None else (repo_root / "data")

    print("=" * 78)
    print("Interview IQ -- Data Layer Validation Report (Phase 3)")
    print("=" * 78)

    cfg = Config(configs_dir=args.configs_dir)
    excluded_question_ids = set(cfg.nli_finetune["data"]["excluded_question_ids"])

    refdocs_path = data_dir / "refdocs" / "reference_docs_250_FINAL_v1.json"
    questions_path = data_dir / "questions" / "questions_250.json"
    gold_path = data_dir / "nli" / "gold_set_48.json"
    da001_path = data_dir / "nli" / "pairs_pilot_150_v2" / "pairs_DA001_pilot_v1.json"
    rem9_path = data_dir / "nli" / "pairs_pilot_150_v2" / "pairs_pilot_remaining9_v2.json"

    hard_failures: list[str] = []

    # ---- [1] Reference documents ----------------------------------------------
    print("\n[1] Reference documents")
    try:
        refdocs = load_reference_docs(refdocs_path)
    except (FileNotFoundError, RefDocsSchemaError, ChunkUniquenessError) as exc:
        print(f"{_ICONS['HARD'][False]} [HARD] refdocs_schema: {exc}")
        print("\nHARD FAILURE on required input -- aborting validation.")
        print("=" * 78)
        return 1
    print(
        f"{_ICONS['HARD'][True]} [HARD] refdocs_schema: {len(refdocs.documents)} documents, "
        f"{len(refdocs.chunk_ids())} unique chunks, schema-valid."
    )

    if len(refdocs.documents) == EXPECTED_DOC_COUNT:
        print(f"{_ICONS['HARD'][True]} [HARD] refdocs_doc_count: {len(refdocs.documents)} == {EXPECTED_DOC_COUNT}")
    else:
        print(
            f"{_ICONS['HARD'][False]} [HARD] refdocs_doc_count: expected {EXPECTED_DOC_COUNT}, "
            f"found {len(refdocs.documents)}"
        )
        hard_failures.append("refdocs_doc_count")

    if len(refdocs.chunk_ids()) == EXPECTED_CHUNK_COUNT:
        print(
            f"{_ICONS['HARD'][True]} [HARD] refdocs_chunk_count: "
            f"{len(refdocs.chunk_ids())} == {EXPECTED_CHUNK_COUNT}"
        )
    else:
        print(
            f"{_ICONS['HARD'][False]} [HARD] refdocs_chunk_count: expected {EXPECTED_CHUNK_COUNT}, "
            f"found {len(refdocs.chunk_ids())}"
        )
        hard_failures.append("refdocs_chunk_count")

    # key_points integrity is enforced as a HARD FAILURE inside
    # load_reference_docs() itself (V3, D42) -- reaching this line means
    # every document's key_points is non-empty, duplicate-free, and fully
    # resolvable. This is a descriptive summary, not an additional check.
    kp_counts = [len(doc.key_points) for doc in refdocs.documents]
    print(
        f"{_ICONS['INFO']} [INFO] key_points_integrity (V3): all {len(refdocs.documents)} documents passed "
        f"(non-empty, no duplicates, no dangling references)."
    )
    print(
        f"{_ICONS['INFO']} [INFO] key_points_summary: per-document key_points count -- "
        f"min={min(kp_counts)}, max={max(kp_counts)}, mean={statistics.mean(kp_counts):.3f}, "
        f"median={statistics.median(kp_counts)}"
    )

    # ---- [2] Question bank ------------------------------------------------------
    print("\n[2] Question bank")
    try:
        _validate_questions_schema(questions_path)
    except (FileNotFoundError, NLIDataSchemaError, json.JSONDecodeError) as exc:
        print(f"{_ICONS['HARD'][False]} [HARD] questions_schema: {exc}")
        hard_failures.append("questions_schema")
    else:
        with questions_path.open("r", encoding="utf-8") as fh:
            n_questions = len(json.load(fh)["questions"])
        print(f"{_ICONS['HARD'][True]} [HARD] questions_schema: {n_questions} questions schema-valid.")

    # ---- [3] Gold set (evaluation only) -----------------------------------------
    print("\n[3] Gold set (evaluation only)")
    gold_pairs = []
    try:
        gold_pairs = load_gold_set(gold_path)
    except (FileNotFoundError, NLIDataSchemaError) as exc:
        print(f"{_ICONS['HARD'][False]} [HARD] gold_schema: {exc}")
        hard_failures.append("gold_schema")
    else:
        print(f"{_ICONS['HARD'][True]} [HARD] gold_schema: {len(gold_pairs)} gold pairs schema-valid.")
        gold_qids = {p.question_id for p in gold_pairs}
        if gold_qids == excluded_question_ids:
            print(f"{_ICONS['INFO']} [INFO] gold_scope: gold set confirmed single-question {sorted(gold_qids)}.")
        else:
            print(
                f"{_ICONS['WARNING']} [WARNING] gold_scope: gold set spans {sorted(gold_qids)}, "
                f"expected exactly {sorted(excluded_question_ids)}."
            )

    # ---- [4] Pilot NLI pairs (150) ----------------------------------------------
    print("\n[4] Pilot NLI pairs")
    pilot_pairs: list = []
    da001_pairs: list = []
    try:
        da001_pairs = load_pilot_pairs([da001_path])
        rem9_pairs = load_pilot_pairs([rem9_path])
        pilot_pairs = load_pilot_pairs([da001_path, rem9_path])
    except (FileNotFoundError, NLIDataSchemaError) as exc:
        print(f"{_ICONS['HARD'][False]} [HARD] pilot_schema: {exc}")
        hard_failures.append("pilot_schema")
    else:
        print(
            f"{_ICONS['HARD'][True]} [HARD] pilot_schema: {len(pilot_pairs)} pilot pairs schema-valid "
            f"({len(da001_pairs)} DA001 + {len(rem9_pairs)} remaining9)."
        )

    if pilot_pairs and refdocs is not None:
        checks = [
            check_chunk_resolution(pilot_pairs, refdocs),
            check_ds014_exclusion(pilot_pairs, excluded_question_ids),
            check_hard_pos_twin_integrity(pilot_pairs, expected_groups=EXPECTED_HARD_POS_GROUPS),
            check_label_distribution(pilot_pairs, expected=EXPECTED_LABEL_DISTRIBUTION),
            check_question_id_split_readiness(pilot_pairs),
        ]
        print()
        for r in checks:
            _print_result(r)
            if r.severity == "HARD" and not r.passed:
                hard_failures.append(r.name)

        print("\n[5] Documented exceptions & diagnostics (informational -- never fail the gate)")
        _print_result(check_five_word_overlap(pilot_pairs, refdocs))
        if da001_pairs:
            _print_result(check_stage2_verdict_presence(da001_pairs, label="DA001"))

    print("\n" + "=" * 78)
    if hard_failures:
        print(f"RESULT: FAILED -- {len(hard_failures)} hard failure(s): {hard_failures}")
        print("=" * 78)
        return 1

    print("RESULT: PASSED -- all mandatory validations green.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
