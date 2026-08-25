"""Focused regressions for BGE-M3 relevance-aware Precision evidence."""

from __future__ import annotations

from pathlib import Path

import pytest

from interview_iq.decomposition.types import DecompositionResult
from interview_iq.nli.engine import ClaimsChunksMatrix
from interview_iq.pipeline import evaluate_answer
from interview_iq.refdocs.loader import Chunk, load_reference_docs
from interview_iq.retrieval.chunk_cap import select_top_k_chunks


class MappingEmbedder:
    """Deterministic injected embedder; no model or network is involved."""

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors
        self.calls: list[list[str]] = []

    def encode(self, texts):
        batch = list(texts)
        self.calls.append(batch)
        return [self.vectors[text] for text in batch]


def _cell(entailment: float, neutral: float, contradiction: float) -> dict[str, float]:
    return {
        "entailment": entailment,
        "neutral": neutral,
        "contradiction": contradiction,
    }


def test_small_document_is_ranked_without_becoming_capped():
    chunks = (
        Chunk("C01", "first"),
        Chunk("C02", "second"),
        Chunk("C03", "third"),
    )
    embedder = MappingEmbedder(
        {
            "claim": [1.0, 0.0],
            "first": [0.0, 1.0],
            "second": [1.0, 0.0],
            "third": [1.0, 1.0],
        }
    )

    result = select_top_k_chunks("claim", chunks, k=10, embedder=embedder)

    assert result.capped is False
    assert result.chunks == chunks  # the compute-cap candidate set is unchanged
    assert [item.chunk_id for item in result.ranking] == ["C02", "C03", "C01"]
    assert result.relevant_chunk_id == "C02"
    assert result.relevant_similarity == pytest.approx(1.0)
    assert embedder.calls == [["claim"], ["first", "second", "third"]]


def test_nonpositive_k_is_rejected_explicitly():
    with pytest.raises(ValueError, match="k must be at least 1"):
        select_top_k_chunks("claim", (Chunk("C01", "text"),), k=0, embedder=MappingEmbedder({}))


def test_ds014_real_document_shape_still_uses_the_existing_greater_than_k_cap():
    refdocs_path = Path(__file__).parent / "data" / "refdocs" / "reference_docs_250_FINAL_v1.json"
    document = load_reference_docs(refdocs_path).get_document("DS-014")
    assert document is not None
    assert len(document.chunks) == 12

    vectors = {"claim": [1.0, 0.0]}
    for index, chunk in enumerate(document.chunks, start=1):
        vectors[chunk.text] = [float(index), 1.0]
    embedder = MappingEmbedder(vectors)

    result = select_top_k_chunks("claim", document.chunks, k=10, embedder=embedder)

    expected_ids = [chunk.chunk_id for chunk in reversed(document.chunks[2:])]
    assert result.capped is True
    assert len(result.chunks) == 10
    assert [chunk.chunk_id for chunk in result.chunks] == expected_ids
    assert [item.chunk_id for item in result.ranking[:10]] == expected_ids


def test_retrieval_selected_evidence_keeps_the_complete_nli_cell_aligned():
    chunks = (
        Chunk("RELEVANT", "semantic match"),
        Chunk("NLI_TRAP", "near neighbor"),
        Chunk("CONTRADICTION_TRAP", "unrelated statement"),
    )
    embedder = MappingEmbedder(
        {
            "claim": [1.0, 0.0],
            "semantic match": [1.0, 0.0],
            "near neighbor": [0.7, 0.7],
            "unrelated statement": [0.0, 1.0],
        }
    )
    retrieval = select_top_k_chunks("claim", chunks, k=10, embedder=embedder)
    matrix = ClaimsChunksMatrix(
        claims=("claim",),
        chunk_ids=tuple(chunk.chunk_id for chunk in chunks),
        matrix=(
            (
                _cell(0.40, 0.55, 0.05),
                _cell(0.99, 0.005, 0.005),
                _cell(0.01, 0.01, 0.98),
            ),
        ),
    )

    evidence = matrix.evidence_for_chunk(0, retrieval.relevant_chunk_id)

    assert evidence.chunk_id == "RELEVANT"
    assert (evidence.entailment, evidence.neutral, evidence.contradiction) == (0.40, 0.55, 0.05)
    assert matrix.best_evidence(0)[0] == "NLI_TRAP"  # old max-entailment winner
    assert matrix.max_contradiction(0) == 0.98  # independent max-C must not leak in


class _PipelineConfig:
    asr_model = "test-asr"
    asr = {"model": {"device": "cpu", "compute_type": "int8"}}
    retrieval = {"model": {"name": "test-bge", "device": "cpu"}}
    embedding_model = "test-bge"
    nli_model = "test-nli"
    k = 10
    tau = 0.5
    tau_e = 0.9
    alpha = 0.0
    scoring = {"combination": {"score_scale": 100}}


class _CoverageMatrix:
    def max_entailment_for_keypoint(self, _index: int) -> float:
        return 0.5


def test_pipeline_uses_bge_evidence_even_when_other_chunks_have_larger_nli_values(monkeypatch):
    chunks = (
        Chunk("RELEVANT", "semantic match"),
        Chunk("NLI_TRAP", "near neighbor"),
        Chunk("CONTRADICTION_TRAP", "unrelated statement"),
    )
    embedder = MappingEmbedder(
        {
            "claim": [1.0, 0.0],
            "semantic match": [1.0, 0.0],
            "near neighbor": [0.7, 0.7],
            "unrelated statement": [0.0, 1.0],
        }
    )

    def fake_precision_matrix(_model, _tokenizer, claims, chunks, **_kwargs):
        cells = {
            "RELEVANT": _cell(0.40, 0.55, 0.05),
            "NLI_TRAP": _cell(0.99, 0.005, 0.005),
            "CONTRADICTION_TRAP": _cell(0.01, 0.01, 0.98),
        }
        return ClaimsChunksMatrix(
            claims=tuple(claims),
            chunk_ids=tuple(chunk.chunk_id for chunk in chunks),
            matrix=(tuple(cells[chunk.chunk_id] for chunk in chunks),),
        )

    monkeypatch.setattr("interview_iq.pipeline.build_claims_chunks_matrix", fake_precision_matrix)
    monkeypatch.setattr("interview_iq.pipeline.build_coverage_matrix", lambda *_args, **_kwargs: _CoverageMatrix())

    result = evaluate_answer(
        "unused.wav",
        "generic question",
        chunks,
        key_points=("RELEVANT",),
        config=_PipelineConfig(),
        question_id="GENERIC-001",
        nli_model=object(),
        nli_tokenizer=object(),
        chunk_embedder=embedder,
        transcribe_fn=lambda *_args, **_kwargs: {"status": "ok", "normalized_transcript": "answer"},
        decompose_fn=lambda _text: DecompositionResult(source_text="answer", claims=["claim"]),
    )

    assert result["status"] == "SUCCESS"
    assert result["retrieval"][0]["selected_chunk_id"] == "RELEVANT"
    assert result["claim_scores"][0]["best_chunk_id"] == "RELEVANT"
    assert result["claim_scores"][0]["nli_entailment"] == 0.40
    assert result["claim_scores"][0]["nli_neutral"] == 0.55
    assert result["claim_scores"][0]["nli_contradiction"] == 0.05
    assert result["claim_scores"][0]["verdict"] == "NEUTRAL"


def test_realistic_da017_claims_rank_inner_and_left_join_evidence_correctly():
    refdocs_path = Path(__file__).parent / "data" / "refdocs" / "reference_docs_250_FINAL_v1.json"
    document = load_reference_docs(refdocs_path).get_document("DA-017")
    assert document is not None

    inner_claim = "ال inner join يعيد الصفوف المتطابقة بين الجدولين."
    left_claim = "ال left join يعيد كل الصفوف من الجدول الايسر حتى اذا لم يكن هناك تطابق."
    by_id = {chunk.chunk_id: chunk for chunk in document.chunks}
    vectors = {
        inner_claim: [1.0, 0.0],
        left_claim: [0.0, 1.0],
        by_id["DA017-C01"].text: [1.0, 0.0],
        by_id["DA017-C02"].text: [0.0, 1.0],
        by_id["DA017-C03"].text: [0.8, 0.4],
        by_id["DA017-C04"].text: [0.4, 0.8],
        by_id["DA017-C05"].text: [-1.0, 0.0],
        by_id["DA017-C06"].text: [0.0, -1.0],
    }
    embedder = MappingEmbedder(vectors)

    inner = select_top_k_chunks(inner_claim, document.chunks, k=10, embedder=embedder)
    left = select_top_k_chunks(left_claim, document.chunks, k=10, embedder=embedder)

    assert inner.capped is False and left.capped is False
    assert inner.relevant_chunk_id == "DA017-C01"
    assert left.relevant_chunk_id == "DA017-C02"
    assert len(inner.chunks) == len(left.chunks) == 6
