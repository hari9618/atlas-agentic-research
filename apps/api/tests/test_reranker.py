"""Cross-encoder re-rank tests (offline-safe).

Offline (ATLAS_OFFLINE_EMBED=1, as in CI) the re-ranker is a no-op that preserves
order — so these assert the contract, not model quality. The point being guarded:
web evidence must flow *through* the re-rank path, not enter the prompt on trust.
"""

from __future__ import annotations

from atlas.core.rag.reranker import rerank_chunks
from atlas.core.rag.types import Chunk, RetrievedChunk


def _chunk(text: str, score: float = 0.1) -> RetrievedChunk:
    return RetrievedChunk(chunk=Chunk(chunk_id=text[:8], doc_id="d", text=text, source="web"),
                          score=score)


def test_rerank_is_a_safe_noop_offline():
    chunks = [_chunk("alpha"), _chunk("beta"), _chunk("gamma")]
    out = rerank_chunks("anything", chunks)
    assert [c.chunk.text for c in out] == ["alpha", "beta", "gamma"]


def test_rerank_respects_top_n_offline():
    chunks = [_chunk("a"), _chunk("b"), _chunk("c"), _chunk("d")]
    out = rerank_chunks("q", chunks, top_n=2)
    assert len(out) == 2


def test_rerank_handles_empty():
    assert rerank_chunks("q", []) == []
