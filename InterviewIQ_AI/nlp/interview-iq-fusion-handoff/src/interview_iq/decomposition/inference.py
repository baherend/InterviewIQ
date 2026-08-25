"""
decomposition/inference.py — Decomposition inference (interface only).

⛔ Phase 8 — Gate G2 is closed (decisions.md D51/D52) and Q6 (AraT5 vs
mT5-base) is now resolved: AraT5-base was selected on
linguistic-specialization grounds (decisions.md D54). No tokenizer or
model checkpoint is loaded here yet — that belongs to the actual
Phase 8 implementation, not this scaffold. Q6 is reopenable if evidence
during actual Phase 8 fine-tuning contradicts this decision.
"""

from __future__ import annotations

from interview_iq.decomposition.types import DecompositionResult


def decompose(source_text: str) -> DecompositionResult:
    """Decompose a source answer into atomic, self-contained claims,
    enforcing the four locked annotation rules.

    Not implemented: blocked on Q6 (see module docstring).
    """
    raise NotImplementedError(
        "decomposition.inference.decompose: blocked on Q6 "
        "(AraT5 vs mT5-base — decisions.md) — Phase 8 skeleton only, no "
        "model-dependent logic implemented yet."
    )
