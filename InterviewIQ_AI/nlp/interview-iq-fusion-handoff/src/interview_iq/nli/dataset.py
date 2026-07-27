"""
nli/dataset.py — NLI pair-file loading + safety checks for the Interview IQ NLP module.

Loads the pilot NLI pairs (150, across two on-disk shapes) and the DS-014
Gold Set (48, evaluation only), normalizes both into flat record lists, and
implements the mandatory Phase 3 safety checks:

  - D28 gate: DS-014 (or any configured excluded question_id) must never
    appear in a training premise pool.
  - D26 twin integrity: HARD_POS claim groups share identical hypothesis
    text, are labeled {entailment, paired_neutral}, and never span more
    than one question_id (a precondition for "never split across
    train/val", which is enforced by the Phase 4 splitter using this
    data's `question_id`/`claim_group` fields).
  - Pilot label distribution (E/C/N).
  - Question-ID-level split readiness.
  - D35 documented exception: 5-consecutive-word lexical overlap diagnostic.
  - Q4 diagnostic: stage2_verdict presence.

On-disk pair-file shapes supported (auto-detected):
  Flat   — {"meta": {"question_id": "DA-001", ...}, "pairs": [...]}
  Nested — {"meta": {...}, "documents": [{"question_id": "...", "pairs": [...]}, ...]}
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from interview_iq.refdocs.loader import ReferenceDocs

PILOT_LABELS = {"entailment", "contradiction", "paired_neutral", "standard_neutral"}
GOLD_LABELS = {"entailment", "contradiction", "neutral"}
PILOT_CATEGORIES = {
    "EASY_POS",
    "HARD_POS",
    "EASY_NEG",
    "SUBJECT_SWAP",
    "HN_OTHER",
    "STANDARD_NEUTRAL",
}
REQUIRED_PAIR_KEYS = {"pair_id", "category", "label", "chunk_id", "hypothesis"}
REQUIRED_GOLD_KEYS = {"pair_id", "chunk_id", "premise", "hypothesis", "label"}


class NLIDataSchemaError(ValueError):
    """Raised when an NLI pair file (pilot or gold) fails schema validation."""


# ── records ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PairRecord:
    pair_id: str
    question_id: str
    category: str
    label: str
    chunk_id: str
    hypothesis: str
    claim_group: str | None = None
    distractor_of: str | None = None
    swapped_from: str | None = None
    stage2_verdict: str | None = None
    stage2_note: str | None = None
    source_file: str = ""


@dataclass(frozen=True)
class GoldPairRecord:
    pair_id: str
    question_id: str
    chunk_id: str
    premise: str
    hypothesis: str
    label: str
    contradiction_method: str | None = None
    stage2_verdict: str | None = None


# ── loaders ──────────────────────────────────────────────────────────────────


def _validate_pair_dict(d: Any, path: Path, index: int) -> None:
    if not isinstance(d, dict):
        raise NLIDataSchemaError(f"{path}: pairs[{index}] is not an object")
    missing = REQUIRED_PAIR_KEYS - d.keys()
    if missing:
        raise NLIDataSchemaError(f"{path}: pairs[{index}] missing keys {sorted(missing)}")
    if d["label"] not in PILOT_LABELS:
        raise NLIDataSchemaError(
            f"{path}: pair {d['pair_id']!r} has invalid label {d['label']!r} "
            f"(expected one of {sorted(PILOT_LABELS)})"
        )
    if d["category"] not in PILOT_CATEGORIES:
        raise NLIDataSchemaError(
            f"{path}: pair {d['pair_id']!r} has invalid category {d['category']!r} "
            f"(expected one of {sorted(PILOT_CATEGORIES)})"
        )


def _pair_from_dict(d: dict[str, Any], question_id: str, source_file: str) -> PairRecord:
    return PairRecord(
        pair_id=d["pair_id"],
        question_id=question_id,
        category=d["category"],
        label=d["label"],
        chunk_id=d["chunk_id"],
        hypothesis=d["hypothesis"],
        claim_group=d.get("claim_group"),
        distractor_of=d.get("distractor_of"),
        swapped_from=d.get("swapped_from"),
        stage2_verdict=d.get("stage2_verdict"),
        stage2_note=d.get("stage2_note"),
        source_file=source_file,
    )


def load_pilot_pairs_file(path: Path | str) -> list[PairRecord]:
    """Load one pilot pairs file, auto-detecting the flat ('pairs') or
    nested ('documents') on-disk shape, and return normalized PairRecords."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"NLI pairs file not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        try:
            raw = json.load(fh)
        except json.JSONDecodeError as exc:
            raise NLIDataSchemaError(f"{path}: invalid JSON — {exc}") from exc

    if not isinstance(raw, dict) or "meta" not in raw:
        raise NLIDataSchemaError(f"{path}: top-level object must contain 'meta'")

    records: list[PairRecord] = []

    if "pairs" in raw:  # flat shape
        question_id = raw["meta"].get("question_id")
        if not question_id:
            raise NLIDataSchemaError(f"{path}: meta.question_id is required for flat pair files")
        pairs_raw = raw["pairs"]
        if not isinstance(pairs_raw, list) or not pairs_raw:
            raise NLIDataSchemaError(f"{path}: 'pairs' must be a non-empty list")
        for i, d in enumerate(pairs_raw):
            _validate_pair_dict(d, path, i)
            records.append(_pair_from_dict(d, question_id, str(path)))

    elif "documents" in raw:  # nested shape
        docs_raw = raw["documents"]
        if not isinstance(docs_raw, list) or not docs_raw:
            raise NLIDataSchemaError(f"{path}: 'documents' must be a non-empty list")
        for di, doc in enumerate(docs_raw):
            if not isinstance(doc, dict) or "question_id" not in doc or "pairs" not in doc:
                raise NLIDataSchemaError(
                    f"{path}: documents[{di}] must contain 'question_id' and 'pairs'"
                )
            question_id = doc["question_id"]
            pairs_raw = doc["pairs"]
            if not isinstance(pairs_raw, list) or not pairs_raw:
                raise NLIDataSchemaError(f"{path}: documents[{di}] ({question_id}) has no pairs")
            for i, d in enumerate(pairs_raw):
                _validate_pair_dict(d, path, i)
                records.append(_pair_from_dict(d, question_id, str(path)))

    else:
        raise NLIDataSchemaError(f"{path}: must contain either 'pairs' or 'documents'")

    ids = [r.pair_id for r in records]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise NLIDataSchemaError(f"{path}: duplicate pair_id(s) within file: {dup}")

    return records


def load_pilot_pairs(paths: Iterable[Path | str]) -> list[PairRecord]:
    """Load and concatenate multiple pilot pairs files, checking global pair_id uniqueness."""
    all_records: list[PairRecord] = []
    for p in paths:
        all_records.extend(load_pilot_pairs_file(p))
    ids = [r.pair_id for r in all_records]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise NLIDataSchemaError(f"Duplicate pair_id(s) across pilot files: {dup}")
    return all_records


def load_gold_set(path: Path | str) -> list[GoldPairRecord]:
    """Load and schema-validate the Gold Set file (evaluation-only pairs)."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Gold set file not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        try:
            raw = json.load(fh)
        except json.JSONDecodeError as exc:
            raise NLIDataSchemaError(f"{path}: invalid JSON — {exc}") from exc

    if not isinstance(raw, dict) or "meta" not in raw or "pairs" not in raw:
        raise NLIDataSchemaError(f"{path}: top-level object must contain 'meta' and 'pairs'")

    question_id = raw["meta"].get("question_id")
    if not question_id:
        raise NLIDataSchemaError(f"{path}: meta.question_id is required")

    pairs_raw = raw["pairs"]
    if not isinstance(pairs_raw, list) or not pairs_raw:
        raise NLIDataSchemaError(f"{path}: 'pairs' must be a non-empty list")

    records: list[GoldPairRecord] = []
    seen_ids: set[str] = set()
    for i, d in enumerate(pairs_raw):
        if not isinstance(d, dict):
            raise NLIDataSchemaError(f"{path}: pairs[{i}] is not an object")
        missing = REQUIRED_GOLD_KEYS - d.keys()
        if missing:
            raise NLIDataSchemaError(f"{path}: pairs[{i}] missing keys {sorted(missing)}")
        if d["label"] not in GOLD_LABELS:
            raise NLIDataSchemaError(
                f"{path}: pair {d['pair_id']!r} has invalid label {d['label']!r} "
                f"(expected one of {sorted(GOLD_LABELS)})"
            )
        if d["pair_id"] in seen_ids:
            raise NLIDataSchemaError(f"{path}: duplicate pair_id {d['pair_id']!r}")
        seen_ids.add(d["pair_id"])
        stage2 = d.get("stage2") or {}
        records.append(
            GoldPairRecord(
                pair_id=d["pair_id"],
                question_id=question_id,
                chunk_id=d["chunk_id"],
                premise=d["premise"],
                hypothesis=d["hypothesis"],
                label=d["label"],
                contradiction_method=d.get("contradiction_method"),
                stage2_verdict=stage2.get("verdict"),
            )
        )
    return records


# ── check result ─────────────────────────────────────────────────────────────


@dataclass
class CheckResult:
    name: str
    passed: bool
    severity: str  # "HARD" | "WARNING" | "INFO"
    message: str
    details: Any = None


# ── safety checks ────────────────────────────────────────────────────────────


def check_chunk_resolution(pairs: list[PairRecord], refdocs: ReferenceDocs) -> CheckResult:
    """Every pair's chunk_id must resolve to an existing chunk in refdocs."""
    valid_ids = refdocs.chunk_ids()
    unresolved = [(p.pair_id, p.chunk_id) for p in pairs if p.chunk_id not in valid_ids]
    if unresolved:
        return CheckResult(
            name="chunk_resolution",
            passed=False,
            severity="HARD",
            message=f"{len(unresolved)} pair(s) reference unknown chunk_id(s): {unresolved[:10]}",
            details=unresolved,
        )
    return CheckResult(
        name="chunk_resolution",
        passed=True,
        severity="HARD",
        message=f"All {len(pairs)} pairs resolve to a valid chunk_id.",
    )


def check_ds014_exclusion(pairs: list[PairRecord], excluded_question_ids: set[str]) -> CheckResult:
    """D28: excluded question_id(s) (DS-014 by default) must never appear in a training pool."""
    contaminated = sorted({p.question_id for p in pairs} & excluded_question_ids)
    if contaminated:
        offending_pairs = [p.pair_id for p in pairs if p.question_id in excluded_question_ids]
        return CheckResult(
            name="premise_pool_contamination",
            passed=False,
            severity="HARD",
            message=(
                f"D28 VIOLATION: training pool contains excluded question_id(s) "
                f"{contaminated}: {len(offending_pairs)} pair(s) — {offending_pairs[:10]}"
            ),
            details=offending_pairs,
        )
    return CheckResult(
        name="premise_pool_contamination",
        passed=True,
        severity="HARD",
        message=f"D28 OK: no training pairs from excluded question_id(s) {sorted(excluded_question_ids)}.",
    )


def check_hard_pos_twin_integrity(
    pairs: list[PairRecord], expected_groups: int | None = None
) -> CheckResult:
    """D26: HARD_POS twins share identical hypothesis text, labels
    {entailment, paired_neutral}, and never span more than one question_id.

    Twins are grouped by (question_id, claim_group) — claim_group labels
    (e.g. "HP1") are only unique *within* a question, not globally.
    """
    groups: dict[tuple[str, str], list[PairRecord]] = {}
    for p in pairs:
        if p.claim_group:
            groups.setdefault((p.question_id, p.claim_group), []).append(p)

    problems: list[str] = []
    for key, members in groups.items():
        if len(members) != 2:
            problems.append(f"{key}: expected 2 twin pairs, found {len(members)}")
            continue
        labels = sorted(m.label for m in members)
        if labels != ["entailment", "paired_neutral"]:
            problems.append(f"{key}: labels {labels} != [entailment, paired_neutral]")
        hyps = {m.hypothesis for m in members}
        if len(hyps) != 1:
            problems.append(f"{key}: hypothesis text differs between twins")

    if expected_groups is not None and len(groups) != expected_groups:
        problems.append(
            f"expected {expected_groups} HARD_POS claim group(s), found {len(groups)}"
        )

    if problems:
        return CheckResult(
            name="hard_pos_twin_integrity",
            passed=False,
            severity="HARD",
            message=f"D26 VIOLATION: {len(problems)} problem(s): {problems[:10]}",
            details=problems,
        )
    return CheckResult(
        name="hard_pos_twin_integrity",
        passed=True,
        severity="HARD",
        message=f"D26 OK: {len(groups)} HARD_POS claim group(s) verified (twins intact).",
        details={"n_groups": len(groups)},
    )


def check_label_distribution(
    pairs: list[PairRecord], expected: dict[str, int] | None = None
) -> CheckResult:
    """Pilot label distribution over entailment / contradiction / neutral,
    where neutral = paired_neutral + standard_neutral."""
    counts = Counter(p.label for p in pairs)
    actual = {
        "entailment": counts.get("entailment", 0),
        "contradiction": counts.get("contradiction", 0),
        "neutral": counts.get("paired_neutral", 0) + counts.get("standard_neutral", 0),
    }
    if expected is not None and actual != expected:
        return CheckResult(
            name="label_distribution",
            passed=False,
            severity="HARD",
            message=f"Label distribution mismatch: expected {expected}, got {actual}",
            details=actual,
        )
    return CheckResult(
        name="label_distribution",
        passed=True,
        severity="HARD",
        message=f"Label distribution OK: {actual}",
        details=actual,
    )


def check_question_id_split_readiness(pairs: list[PairRecord]) -> CheckResult:
    """Splitting logic must operate at Question-ID level only — every pair
    must carry a resolvable question_id for this to be possible."""
    missing = [p.pair_id for p in pairs if not p.question_id]
    if missing:
        return CheckResult(
            name="question_id_split_readiness",
            passed=False,
            severity="HARD",
            message=f"{len(missing)} pair(s) missing question_id: {missing[:10]}",
            details=missing,
        )
    n_questions = len({p.question_id for p in pairs})
    return CheckResult(
        name="question_id_split_readiness",
        passed=True,
        severity="HARD",
        message=(
            f"All {len(pairs)} pairs carry a resolvable question_id across "
            f"{n_questions} question(s); ready for Question-ID-level splitting."
        ),
        details={"n_questions": n_questions},
    )


# ── D35 documented exception: 5-consecutive-word overlap ────────────────────


def _strip_diacritics(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFC", text) if unicodedata.category(ch) != "Mn")


def _tokenize(text: str) -> list[str]:
    text = _strip_diacritics(text)
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return text.split()


def _longest_common_run(a: list[str], b: list[str]) -> int:
    """Length of the longest contiguous token run shared by `a` and `b`."""
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return 0
    prev = [0] * (m + 1)
    best = 0
    for i in range(1, n + 1):
        curr = [0] * (m + 1)
        for j in range(1, m + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1] + 1
                best = max(best, curr[j])
        prev = curr
    return best


def check_five_word_overlap(
    pairs: list[PairRecord],
    refdocs: ReferenceDocs,
    overlap_threshold: int = 5,
    escalate_ratio: float = 0.75,
) -> CheckResult:
    """D35 documented exception: count pairs whose hypothesis shares a run of
    >= overlap_threshold consecutive words with its premise chunk. Not a hard
    failure — escalates to WARNING only if the violators' label distribution
    becomes one-sided (a single label > escalate_ratio of violators), which
    would indicate a lexical shortcut risk (cf. HANS, McCoy et al. 2019)."""
    violations: list[tuple[str, str]] = []
    for p in pairs:
        premise = refdocs.get_chunk_text(p.chunk_id)
        if premise is None:
            continue  # unresolved chunk_id already reported by check_chunk_resolution
        overlap = _longest_common_run(_tokenize(premise), _tokenize(p.hypothesis))
        if overlap >= overlap_threshold:
            violations.append((p.pair_id, p.label))

    label_counts = Counter(label for _, label in violations)
    total = len(violations)
    severity = "INFO"
    message = (
        f"DOCUMENTED EXCEPTION (D35): {total}/{len(pairs)} pair(s) have a "
        f">={overlap_threshold}-consecutive-word overlap with their premise chunk. "
        f"Label distribution of violators: {dict(label_counts)}."
    )
    if total > 0:
        dominant_share = max(label_counts.values()) / total
        if dominant_share > escalate_ratio:
            severity = "WARNING"
            message += (
                f" ESCALATED: dominant label share {dominant_share:.1%} exceeds the "
                f"{escalate_ratio:.0%} one-sidedness threshold — the D35 acceptance "
                f"rationale (balanced overlap, no lexical shortcut) may no longer hold."
            )

    return CheckResult(
        name="five_word_overlap_d35",
        passed=True,
        severity=severity,
        message=message,
        details={"n_violations": total, "label_counts": dict(label_counts)},
    )


def check_stage2_verdict_presence(pairs: list[PairRecord], label: str = "") -> CheckResult:
    """Q4 diagnostic: report stage2_verdict present/missing counts (informational only)."""
    present = [p.pair_id for p in pairs if p.stage2_verdict]
    missing = [p.pair_id for p in pairs if not p.stage2_verdict]
    tag = f" ({label})" if label else ""
    return CheckResult(
        name=f"stage2_verdict_presence{('_' + label) if label else ''}",
        passed=True,
        severity="INFO",
        message=(
            f"Q4 diagnostic{tag}: stage2_verdict present on {len(present)}/{len(pairs)} "
            f"pair(s), missing on {len(missing)}."
        ),
        details={"present": present, "missing": missing},
    )
