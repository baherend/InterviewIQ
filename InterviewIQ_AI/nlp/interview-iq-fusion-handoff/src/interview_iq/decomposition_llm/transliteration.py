"""
D97 (a) -- deterministic transliteration layer.

apply_glossary(claims) runs AFTER decompose_via_llm and BEFORE the
ReferenceDocument construction in pipeline.py. Pure function: no LLM
call, no network, no randomness. Reads the build-time-authored,
human-reviewed glossary at data/glossary/transliteration_glossary.json
(see decisions.md D97) and performs literal substitution of Egyptian-Arabic
phonetic transliterations of English technical terms back to the English
term itself, so downstream NLI scoring is not penalized for the ASR/LLM
having rendered a code-switched English word in Arabic script.

Matching, per D97:
    - normalization: strip Arabic diacritics, unify alef variants
      (أ/إ/آ -> ا), strip one optional leading proclitic
      (ال، و، ب، ك، ل، ف) if it prefixes the whole authored form.
    - longest-match-first: forms are tried longest-first so multi-word
      phrase entries (e.g. "Data Warehouse") are not shadowed by a
      shorter single-word entry contained within them (e.g. "Data").
    - word-boundary aware: matches only whole tokens, never substrings
      of a longer unrelated word.

The audit dict records every substitution performed (claim index, matched
Arabic form, replacement term) plus residual_ambiguous_count: occurrences
of AMBIGUOUS forms (data/glossary/transliteration_glossary.json's
"ambiguous" list) left untouched in the output, non-gating per D97.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GLOSSARY_PATH = _REPO_ROOT / "data" / "glossary" / "transliteration_glossary.json"

_DIACRITICS_RE = re.compile(
    "[ؐ-ًؚ-ٰٟۖ-ۜ۟-۪ۨ-ۭـ]"
)
_ALEF_TRANSLATION = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا"})
_PROCLITICS = ("ال", "و", "ب", "ك", "ل", "ف")  # "ال" checked first (2 chars)


def normalize_arabic(text: str) -> str:
    text = _DIACRITICS_RE.sub("", text)
    text = text.translate(_ALEF_TRANSLATION)
    return text.strip()


def strip_proclitic(word: str) -> str:
    for prefix in _PROCLITICS:
        if word.startswith(prefix) and len(word) - len(prefix) >= 2:
            return word[len(prefix):]
    return word


class _Glossary:
    __slots__ = ("form_to_term", "pattern", "ambiguous_pattern")

    def __init__(self, form_to_term: dict[str, str], pattern: re.Pattern, ambiguous_pattern: re.Pattern | None):
        self.form_to_term = form_to_term
        self.pattern = pattern
        self.ambiguous_pattern = ambiguous_pattern


def _proclitic_prefixed_pattern(forms: list[str]) -> re.Pattern | None:
    """Build a single regex matching any form, optionally proclitic-prefixed,
    longest form first so multi-word phrases win over their sub-words."""
    if not forms:
        return None
    ordered = sorted(set(forms), key=len, reverse=True)
    proclitic_group = "|".join(_PROCLITICS)
    alternatives = [rf"(?:{proclitic_group})?{re.escape(form)}" for form in ordered]
    return re.compile(r"\b(?:" + "|".join(alternatives) + r")\b")


@lru_cache(maxsize=1)
def _load_glossary() -> _Glossary:
    with _GLOSSARY_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    form_to_term: dict[str, str] = {}
    all_forms: list[str] = []
    for entry in data["entries"]:
        for form in entry["forms"]:
            form_to_term[form] = entry["term"]
            all_forms.append(form)

    ambiguous_forms = [item["form"] for item in data.get("ambiguous", [])]

    pattern = _proclitic_prefixed_pattern(all_forms)
    ambiguous_pattern = _proclitic_prefixed_pattern(ambiguous_forms)

    if pattern is None:
        # No usable glossary entries -- match nothing.
        pattern = re.compile(r"(?!x)x")

    return _Glossary(form_to_term=form_to_term, pattern=pattern, ambiguous_pattern=ambiguous_pattern)


def _term_for_match(matched_text: str, form_to_term: dict[str, str]) -> str:
    if matched_text in form_to_term:
        return form_to_term[matched_text]
    for prefix in _PROCLITICS:
        if matched_text.startswith(prefix) and matched_text[len(prefix):] in form_to_term:
            return form_to_term[matched_text[len(prefix):]]
    # Guaranteed not to happen: the pattern is built exclusively from
    # form_to_term's keys plus an optional proclitic prefix.
    raise KeyError(matched_text)


def apply_glossary(claims: list[str]) -> tuple[list[str], dict[str, Any]]:
    """Deterministic, LLM-free substitution of glossary Arabic forms with
    their English term. Returns (claims_out, audit)."""
    glossary = _load_glossary()

    claims_out: list[str] = []
    substitutions: list[dict[str, Any]] = []
    residual_ambiguous_count = 0

    for claim_index, claim in enumerate(claims):
        normalized_claim = normalize_arabic(claim)

        def _replace(match: re.Match) -> str:
            matched_text = match.group(0)
            term = _term_for_match(matched_text, glossary.form_to_term)
            substitutions.append(
                {
                    "claim_index": claim_index,
                    "matched_form": matched_text,
                    "replacement_term": term,
                }
            )
            return term

        new_claim = glossary.pattern.sub(_replace, normalized_claim)

        if glossary.ambiguous_pattern is not None:
            residual_ambiguous_count += len(glossary.ambiguous_pattern.findall(new_claim))

        claims_out.append(new_claim)

    audit = {
        "substitutions": substitutions,
        "residual_ambiguous_count": residual_ambiguous_count,
    }
    return claims_out, audit
