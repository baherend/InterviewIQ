"""Focused regression test for interview_iq.retrieval.chunk_cap.BgeM3Embedder's
CPU fp16 fix (Phase 3C completion fix).

BGEM3FlagModel defaults to use_fp16=True, which has no LayerNorm CPU kernel
in this torch build (RuntimeError: "LayerNormKernelImpl" not implemented
for 'Half') -- production must always pass use_fp16=False explicitly. This
mirrors the same fix test_real_nlp_pipeline.py's _MatchingEmbedder already
applies in test-only code, now verified for the actual production class.

Mocks FlagEmbedding.BGEM3FlagModel itself (the heavyweight boundary) so
this test never downloads or loads the real BGE-M3 checkpoint -- it
exercises the real, unmodified BgeM3Embedder._ensure_loaded/.encode() code
path, not a reimplementation of it.
"""
from unittest.mock import MagicMock, patch

from interview_iq.retrieval.chunk_cap import BgeM3Embedder


def test_bge_m3_embedder_disables_fp16_on_construction():
    fake_model = MagicMock()
    fake_model.encode.return_value = {"dense_vecs": [[0.1, 0.2, 0.3]]}

    with patch("FlagEmbedding.BGEM3FlagModel", return_value=fake_model) as mock_ctor:
        embedder = BgeM3Embedder(model_name="BAAI/bge-m3", device="cpu")
        result = embedder.encode(["some text"])

    mock_ctor.assert_called_once_with("BAAI/bge-m3", use_fp16=False, device="cpu")
    assert result == [[0.1, 0.2, 0.3]]


def test_bge_m3_embedder_lazy_loads_only_on_first_encode():
    """Constructing BgeM3Embedder must never itself construct the real
    model -- only the first .encode() call may (existing, unmodified
    behavior, re-verified alongside the fp16 fix above).
    """
    with patch("FlagEmbedding.BGEM3FlagModel") as mock_ctor:
        BgeM3Embedder(model_name="BAAI/bge-m3", device="cpu")
        mock_ctor.assert_not_called()
