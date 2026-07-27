"""
retrieval/chunk_cap.py — BGE-M3 Top-k chunk cap for the Interview IQ NLP module.

Phase 6 (see PROJECT_EXECUTION_PLAN.md §6). Selects, per claim, the top-k
most similar reference chunks (by BGE-M3 cosine similarity) out of one
document's full chunk set, before the Claims x Chunks NLI matrix
(nli/engine.py) is run against them.

*** This is a COMPUTE CAP, not a filtering/relevance GATE. ***
Its only job is to bound the O(claims x chunks) NLI workload per document.
configs/retrieval.yaml calls k a "generous cap" by design (PRE-CALIBRATION
DEFAULT): k is meant to be large enough that no chunk relevant to a claim is
ever excluded. If a future calibration run (Gate G4) shows k excludes chunks
the NLI engine would otherwise have scored, k must be raised — the cap is
never meant to pick winners, only to bound the irrelevant long tail.

n_chunks <= k behaviour (this is the common case measured against the real
corpus — decisions.md D42: chunks/doc min=6, max=12, mean=6.06, median=6; the
current k=10 PRE-CALIBRATION DEFAULT means the cap only binds on documents
with 11-12 chunks): when a document's chunk count is already <= k, this
module SHORT-CIRCUITS and returns every chunk, in its original order, WITHOUT
constructing an embedder or computing a single embedding. Ranking chunks that
already all fit under the cap would only reorder them for no purpose the cap
exists to serve, and would burn embedding compute for nothing.

Model loading is lazy and injectable: BgeM3Embedder does not import
FlagEmbedding or construct the BGE-M3 model until `.encode()` is first
called — and `.encode()` is only ever reached when the cap actually binds
(n_chunks > k). Unit tests either stay entirely on the n_chunks <= k
short-circuit path, or inject a fake embedder — neither ever triggers a
model download.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol, Sequence

from interview_iq.refdocs.loader import Chunk


class ChunkEmbedder(Protocol):
    """Anything with an `.encode(texts) -> list[list[float]]` method. Tests
    inject a fake implementation; production uses BgeM3Embedder."""

    def encode(self, texts: Sequence[str]) -> list[list[float]]: ...


class BgeM3Embedder:
    """Lazy, real BGE-M3 embedder (production path).

    The FlagEmbedding model is NOT constructed in __init__ — only on the
    first `.encode()` call. Since `select_top_k_chunks` only calls
    `.encode()` when the cap actually binds (n_chunks > k), this class can be
    safely default-constructed anywhere (e.g. as `chunk_embedder` in a CLI's
    argument default) without ever downloading anything unless a document
    with more than k chunks is actually scored.
    """

    def __init__(self, model_name: str = "BAAI/bge-m3", device: str = "cpu") -> None:
        self._model_name = model_name
        self._device = device
        self._model = None

    def _ensure_loaded(self) -> None:
        if self._model is None:
            from FlagEmbedding import BGEM3FlagModel  # heavy import deferred to first use

            print(f"[chunk_cap] Loading BGE-M3 ({self._model_name}) on {self._device} ...")
            self._model = BGEM3FlagModel(self._model_name, device=self._device)

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        self._ensure_loaded()
        out = self._model.encode(list(texts))
        return [list(vec) for vec in out["dense_vecs"]]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass(frozen=True)
class ChunkCapResult:
    chunks: tuple[Chunk, ...]
    capped: bool  # True iff n_chunks > k and ranking/truncation actually ran


def select_top_k_chunks(
    claim_text: str,
    chunks: Sequence[Chunk],
    k: int,
    embedder: ChunkEmbedder | None = None,
) -> ChunkCapResult:
    """Select the top-k chunks (by BGE-M3 cosine similarity to claim_text)
    out of `chunks`. COMPUTE CAP, not a filtering gate — see module
    docstring.

    n_chunks <= k: returns every chunk, in original order, `capped=False`,
    and never constructs or calls an embedder.
    n_chunks > k: ranks all chunks by cosine similarity to claim_text and
    returns the top k, `capped=True`.
    """
    if len(chunks) <= k:
        return ChunkCapResult(chunks=tuple(chunks), capped=False)

    embedder = embedder or BgeM3Embedder()
    claim_vec = embedder.encode([claim_text])[0]
    chunk_vecs = embedder.encode([c.text for c in chunks])
    scored = sorted(
        zip(chunks, chunk_vecs),
        key=lambda pair: _cosine(claim_vec, pair[1]),
        reverse=True,
    )
    top = tuple(chunk for chunk, _ in scored[:k])
    return ChunkCapResult(chunks=top, capped=True)
