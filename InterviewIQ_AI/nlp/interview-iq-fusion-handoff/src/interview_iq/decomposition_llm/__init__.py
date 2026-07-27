"""
decomposition_llm/ — Claim Decomposition via external LLM API (D74 pivot).

decisions.md D74 replaces the AraT5-base fine-tuning approach (archived under
archive/phase8_arat5_superseded/) with an external LLM API call for this
module only. Zero-LLM-at-runtime remains in force for the rest of the
pipeline (NLI, BGE-M3, ASR) — see D74 scope.

Status: implemented.
  - system_prompt.md   the D74-supplied system prompt (real content, not a
                        placeholder)
  - client.py          full Groq (OpenAI-compatible chat completions) client:
                        decompose_via_llm() calls the Groq API and parses its
                        numbered-claims output. Wired in as the default
                        decompose_fn in pipeline.evaluate_answer().

Not wired into configs/decomposition.yaml (that file still describes the
superseded AraT5 approach). The mandatory D74 sanity gate (verifying the LLM
preserves candidate errors rather than correcting them) has been implemented
and run repeatedly — see scripts/llm_decomposition_sanity_gate.py and
decisions.md D77 onward for gate history and results.
"""

from __future__ import annotations

from interview_iq.decomposition_llm.client import LLMDecompositionError, decompose_via_llm

__all__ = ["decompose_via_llm", "LLMDecompositionError"]
