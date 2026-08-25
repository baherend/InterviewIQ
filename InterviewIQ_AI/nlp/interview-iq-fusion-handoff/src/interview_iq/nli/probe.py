"""
nli/probe.py — D46 pre-registered reversed-direction diagnostic probe (core).

Tests the NLI model in the REVERSED direction (premise = chunk, hypothesis =
key-point chunk text) to diagnose Coverage-channel behaviour WITHOUT claims
(D46). Source: DS-014 exclusively — the only document the model has never
seen as a premise during training (D28 Gold Set leakage exclusion). Both arms
(zero-shot and adapter) use the same code path via nli/engine.run_nli_matrix.
Never argmax (D43).

Three tests (D46):
  A  self-entailment — premise == hypothesis (identical text), all chunks.
     D46 criterion: median P(E) >= 0.90. Failure => channel broken structurally.
  B  no-relation ceiling — DS-014 chunks × SE-001 key-point chunk texts.
     D46 criterion: median P(E) <= 0.10. Failure => channel non-discriminating.
  C  cross-entity within probe document — premise = chunk about entity X,
     hypothesis = key-point chunk about entity Y, same document; self-pairs
     excluded. Pre-registered prediction (D42-b / D26): median P(E) for the
     adapter arm < median P(E) for zero-shot arm (signal threshold >= 0.10).

No verdict logic lives here. D46's pre-registered criteria decide; the script
runs on Kaggle. The model is always injected by the caller (never loaded here),
so CPU smoke tests work without any network access.
"""

from __future__ import annotations

import statistics
from typing import Any

from transformers import PreTrainedModel, PreTrainedTokenizerBase

from interview_iq.nli.engine import run_nli_matrix
from interview_iq.refdocs.loader import ReferenceDocument


def run_probe(
    model: PreTrainedModel,
    tokenizer: PreTrainedTokenizerBase,
    probe_doc: ReferenceDocument,
    distant_doc: ReferenceDocument,
    batch_size: int = 8,
    max_length: int = 256,
) -> dict[str, Any]:
    """Run the three D46 tests on the given model/tokenizer pair.

    Parameters
    ----------
    probe_doc:
        The document to probe — DS-014 in production (held out from training
        per D28). All chunks serve as premises; its own key-point chunks serve
        as hypotheses for Test C.
    distant_doc:
        A semantically unrelated document — SE-001 in production. Its
        key-point chunks serve as hypotheses for Test B (ceiling test).

    Returns a dict with ``test_A``, ``test_B``, ``test_C`` sub-dicts, each
    containing ``n_pairs``, ``median_p_e`` (float), and ``pairs`` (full raw
    P(E) + softmax probs per pair). Never argmax.
    """
    chunk_texts = [c.text for c in probe_doc.chunks]
    chunk_ids = [c.chunk_id for c in probe_doc.chunks]

    # ── Test A: self-entailment (diagonal of full chunk × chunk matrix) ─────
    matrix_a = run_nli_matrix(
        model, tokenizer,
        premises=chunk_texts, hypotheses=chunk_texts,
        batch_size=batch_size, max_length=max_length,
    )
    pairs_a = [
        {
            "premise_id": chunk_ids[i],
            "hypothesis_id": chunk_ids[i],
            "p_e": matrix_a[i][i]["entailment"],
            "probs": matrix_a[i][i],
        }
        for i in range(len(chunk_ids))
    ]
    median_a = statistics.median(p["p_e"] for p in pairs_a)

    # ── Test B: no-relation ceiling (probe_doc chunks × distant_doc kp texts) ─
    distant_by_id = {c.chunk_id: c for c in distant_doc.chunks}
    kp_b = [distant_by_id[kp] for kp in distant_doc.key_points]
    kp_texts_b = [c.text for c in kp_b]
    kp_ids_b = [c.chunk_id for c in kp_b]
    matrix_b = run_nli_matrix(
        model, tokenizer,
        premises=chunk_texts, hypotheses=kp_texts_b,
        batch_size=batch_size, max_length=max_length,
    )
    pairs_b = [
        {
            "premise_id": chunk_ids[i],
            "hypothesis_id": kp_ids_b[j],
            "p_e": matrix_b[i][j]["entailment"],
            "probs": matrix_b[i][j],
        }
        for i in range(len(chunk_ids))
        for j in range(len(kp_ids_b))
    ]
    median_b = statistics.median(p["p_e"] for p in pairs_b)

    # ── Test C: cross-entity within probe_doc (self-pairs excluded, D46-C) ──
    probe_by_id = {c.chunk_id: c for c in probe_doc.chunks}
    kp_c = [probe_by_id[kp] for kp in probe_doc.key_points]
    kp_texts_c = [c.text for c in kp_c]
    kp_ids_c = [c.chunk_id for c in kp_c]
    matrix_c = run_nli_matrix(
        model, tokenizer,
        premises=chunk_texts, hypotheses=kp_texts_c,
        batch_size=batch_size, max_length=max_length,
    )
    pairs_c = [
        {
            "premise_id": chunk_ids[i],
            "hypothesis_id": kp_ids_c[j],
            "p_e": matrix_c[i][j]["entailment"],
            "probs": matrix_c[i][j],
        }
        for i in range(len(chunk_ids))
        for j in range(len(kp_ids_c))
        if chunk_ids[i] != kp_ids_c[j]
    ]
    median_c = statistics.median(p["p_e"] for p in pairs_c) if pairs_c else float("nan")

    return {
        "probe_doc_id": probe_doc.question_id,
        "distant_doc_id": distant_doc.question_id,
        "test_A": {
            "label": "self_entailment",
            "n_pairs": len(pairs_a),
            "median_p_e": median_a,
            "pairs": pairs_a,
        },
        "test_B": {
            "label": "no_relation_ceiling",
            "n_pairs": len(pairs_b),
            "median_p_e": median_b,
            "pairs": pairs_b,
        },
        "test_C": {
            "label": "cross_entity_within_doc",
            "n_pairs": len(pairs_c),
            "median_p_e": median_c,
            "pairs": pairs_c,
        },
    }
