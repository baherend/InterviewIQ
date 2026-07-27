"""
refdocs/loader.py — Reference-documents loader for the Interview IQ NLP module.

Loads `data/refdocs/reference_docs_250_FINAL_v1.json` (or any file following
the same schema, e.g. a `tests/fixtures/` sample), validates its structure,
and exposes chunk/document lookups used by the NLI dataset layer and the
retrieval/scoring stages downstream.

Schema (per D-locked convention, see PROJECT_EXECUTION_PLAN.md §4):
    {
      "meta": {...},
      "documents": [
        {
          "question_id": "DA-001",
          "track": "DA",
          "question": "...",
          "chunks": [{"chunk_id": "DA001-C01", "text": "..."}, ...],
          "key_points": ["DA001-C01", "DA001-C04", ...]   # subset of chunk_ids
        },
        ...
      ]
    }

This module performs generic schema + uniqueness validation only. Dataset-
specific size expectations (e.g. "250 documents", "1,515 unique chunks") are
production-data invariants, not schema properties, and are asserted by
`cli/validate_data.py` — keeping this loader reusable against small CPU
fixtures of any size.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REQUIRED_DOC_KEYS = {"question_id", "track", "question", "chunks", "key_points"}
REQUIRED_CHUNK_KEYS = {"chunk_id", "text"}


class RefDocsSchemaError(ValueError):
    """Raised when the reference-docs JSON file fails schema validation."""


class ChunkUniquenessError(ValueError):
    """Raised when chunk IDs are not globally unique across all documents."""


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    text: str


@dataclass(frozen=True)
class ReferenceDocument:
    question_id: str
    track: str
    question: str
    chunks: tuple[Chunk, ...]
    key_points: tuple[str, ...]


class ReferenceDocs:
    """In-memory index over a loaded reference-docs file."""

    def __init__(self, meta: dict[str, Any], documents: tuple[ReferenceDocument, ...]) -> None:
        self.meta = meta
        self.documents = documents
        self._doc_by_qid: dict[str, ReferenceDocument] = {}
        self._chunk_text: dict[str, str] = {}
        for doc in documents:
            self._doc_by_qid[doc.question_id] = doc
            for chunk in doc.chunks:
                self._chunk_text[chunk.chunk_id] = chunk.text

    def get_document(self, question_id: str) -> ReferenceDocument | None:
        return self._doc_by_qid.get(question_id)

    def get_chunk_text(self, chunk_id: str) -> str | None:
        return self._chunk_text.get(chunk_id)

    def chunk_ids(self) -> set[str]:
        return set(self._chunk_text.keys())

    def question_ids(self) -> set[str]:
        return set(self._doc_by_qid.keys())

    def __len__(self) -> int:
        return len(self.documents)


def load_reference_docs(path: Path | str) -> ReferenceDocs:
    """Load and schema-validate a reference-docs JSON file.

    Raises
    ------
    FileNotFoundError
        If `path` does not exist.
    RefDocsSchemaError
        On any structural/schema violation (missing keys, wrong types,
        malformed JSON) or key_points integrity violation (V3): empty list,
        duplicate chunk_id within a document's key_points, or a dangling
        chunk_id reference (a key point that can never be covered).
    ChunkUniquenessError
        If any chunk_id appears more than once across the whole file.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Reference docs file not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        try:
            raw = json.load(fh)
        except json.JSONDecodeError as exc:
            raise RefDocsSchemaError(f"{path}: invalid JSON — {exc}") from exc

    if not isinstance(raw, dict) or "meta" not in raw or "documents" not in raw:
        raise RefDocsSchemaError(f"{path}: top-level object must contain 'meta' and 'documents'")

    documents_raw = raw["documents"]
    if not isinstance(documents_raw, list) or not documents_raw:
        raise RefDocsSchemaError(f"{path}: 'documents' must be a non-empty list")

    documents: list[ReferenceDocument] = []
    seen_question_ids: set[str] = set()
    seen_chunk_ids: set[str] = set()
    duplicate_chunk_ids: set[str] = set()

    for i, doc in enumerate(documents_raw):
        if not isinstance(doc, dict):
            raise RefDocsSchemaError(f"{path}: documents[{i}] is not an object")
        missing = REQUIRED_DOC_KEYS - doc.keys()
        if missing:
            raise RefDocsSchemaError(f"{path}: documents[{i}] missing keys {sorted(missing)}")

        question_id = doc["question_id"]
        if question_id in seen_question_ids:
            raise RefDocsSchemaError(f"{path}: duplicate question_id {question_id!r}")
        seen_question_ids.add(question_id)

        chunks_raw = doc["chunks"]
        if not isinstance(chunks_raw, list) or not chunks_raw:
            raise RefDocsSchemaError(f"{path}: document {question_id} has no chunks")

        chunks: list[Chunk] = []
        local_chunk_ids: set[str] = set()
        for j, chunk_raw in enumerate(chunks_raw):
            if not isinstance(chunk_raw, dict):
                raise RefDocsSchemaError(f"{path}: {question_id}.chunks[{j}] is not an object")
            missing_chunk_keys = REQUIRED_CHUNK_KEYS - chunk_raw.keys()
            if missing_chunk_keys:
                raise RefDocsSchemaError(
                    f"{path}: {question_id}.chunks[{j}] missing keys {sorted(missing_chunk_keys)}"
                )
            chunk_id = chunk_raw["chunk_id"]
            if chunk_id in seen_chunk_ids:
                duplicate_chunk_ids.add(chunk_id)
            seen_chunk_ids.add(chunk_id)
            local_chunk_ids.add(chunk_id)
            chunks.append(Chunk(chunk_id=chunk_id, text=chunk_raw["text"]))

        key_points = doc["key_points"]
        if not isinstance(key_points, list):
            raise RefDocsSchemaError(f"{path}: {question_id}.key_points must be a list")
        if not key_points:
            raise RefDocsSchemaError(
                f"{path}: {question_id}.key_points is empty — every document must have at "
                f"least one mandatory-coverage chunk_id (V3)"
            )
        duplicate_kp = sorted({kp for kp in key_points if key_points.count(kp) > 1})
        if duplicate_kp:
            raise RefDocsSchemaError(
                f"{path}: {question_id}.key_points contains duplicate chunk_id(s): {duplicate_kp} (V3)"
            )
        unresolved = [kp for kp in key_points if kp not in local_chunk_ids]
        if unresolved:
            raise RefDocsSchemaError(
                f"{path}: {question_id}.key_points reference unknown chunk_id(s): {unresolved} "
                f"(V3 — dangling key_point reference; this permanently caps Coverage for {question_id})"
            )

        documents.append(
            ReferenceDocument(
                question_id=question_id,
                track=doc["track"],
                question=doc["question"],
                chunks=tuple(chunks),
                key_points=tuple(key_points),
            )
        )

    if duplicate_chunk_ids:
        raise ChunkUniquenessError(
            f"{path}: {len(duplicate_chunk_ids)} duplicate chunk_id(s) found: "
            f"{sorted(duplicate_chunk_ids)[:10]}"
            + ("..." if len(duplicate_chunk_ids) > 10 else "")
        )

    return ReferenceDocs(meta=raw["meta"], documents=tuple(documents))
