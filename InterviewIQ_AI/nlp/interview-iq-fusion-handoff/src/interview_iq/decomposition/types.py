"""
decomposition/types.py — Data structures for the Claim Decomposition module.

⛔ Phase 8 — Gate G2 is closed (decisions.md D51/D52) and Q6 (AraT5 vs
mT5-base) is now resolved: AraT5-base was selected on
linguistic-specialization grounds (decisions.md D54). These remain
plain, model-agnostic data containers — no field here assumes a specific
tokenizer, checkpoint, or model architecture; that belongs to the actual
Phase 8 implementation, not this scaffold.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class AnnotationRules:
    """The four locked KD annotation rules (configs/decomposition.yaml
    `annotation_rules`; see D50 annotation guide)."""

    preserve_hedging: bool
    generalise_personal_framing: bool
    no_unverifiable_causal_bridge: bool
    enforce_self_containment: bool


@dataclass(frozen=True)
class KDExample:
    """One source-text → decomposed-claims training pair for the KD corpus."""

    question_id: str
    example_id: str
    variant: Literal["original", "asr_aligned"]
    source_file: str
    source_text: str
    claims: list[str]


@dataclass(frozen=True)
class DecompositionResult:
    """Output of a single decomposition call."""

    source_text: str
    claims: list[str]


# The v2 pilot records below are deliberately separate from KDExample. A
# pilot answer case keeps the original and simulated-ASR text together and is
# not a train/validation example (D73 remains open).
PilotCaseType = Literal[
    "complete_correct",
    "short_partial",
    "mixed_correctness",
    "plausible_misconception",
    "natural_egyptian_spoken",
]
CorpusV2CaseType = Literal[
    "complete_correct",
    "concise_correct",
    "partial_correct",
    "mixed_correctness",
    "plausible_misconception",
    "natural_egyptian_spoken",
    "long_noisy_multi_claim",
]


@dataclass(frozen=True)
class GenerationSource:
    provider: str
    model: str
    prompt_version: str
    generated_at: str


@dataclass
class HumanReview:
    reviewer: str | None = None
    supported: bool | None = None
    atomic: bool | None = None
    self_contained: bool | None = None
    missing_claims: list[str] | None = None
    unsupported_claims: list[str] | None = None
    term_corruption: list[str] | None = None
    notes: str | None = None


@dataclass
class PilotAnswerCase:
    question_id: str
    track: str
    question_text: str
    reference_source: str
    answer_case_id: str
    case_type: PilotCaseType
    generation_source: GenerationSource
    answer_original: str
    answer_asr_simulated: str
    asr_simulation_events: list[str]
    claims: list[str]
    latin_terms_in_answer: list[str]
    latin_terms_in_claims: list[str]
    intended_errors: list[str]
    review_status: str = "DRAFT_UNREVIEWED"
    human_review: HumanReview = field(default_factory=HumanReview)

    def to_dict(self) -> dict[str, Any]:
        """Return the authoritative JSON representation without rendering claims."""
        return asdict(self)


@dataclass
class CorpusV2AnswerCase:
    """One canonical synthetic authoring case; ASR remains a paired diagnostic field."""

    question_id: str
    track: str
    split: Literal["train", "validation"]
    question_text: str
    reference_source: str
    answer_case_id: str
    case_type: CorpusV2CaseType
    generation_source: GenerationSource
    answer_original: str
    answer_asr_simulated: str
    asr_simulation_events: list[str]
    claims: list[str]
    latin_terms_in_answer: list[str]
    latin_terms_in_claims: list[str]
    intended_errors: list[str]
    automated_audit: dict[str, Any]
    review_status: str = "DRAFT_UNREVIEWED"
    human_review: HumanReview = field(default_factory=HumanReview)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)