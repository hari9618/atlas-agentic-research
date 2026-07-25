"""Cross-encoder re-ranking as a reusable scorer.

The local retrieval path re-ranks inside a LangChain retriever chain, but web
evidence arrives as a plain list of chunks with no measured relevance — it was
entering the prompt on Tavily's ordering and a hardcoded score. This exposes the
same cross-encoder as a direct function so web (or any) chunks can be scored
against the query the same way local evidence is: the model reads the question
and each passage *together* and returns a genuine relevance score.

The model is loaded once and cached. Offline runs skip it (the caller keeps its
original order), so the test suite never downloads a model.
"""

from __future__ import annotations

import logging
import os

from ...config import get_settings
from .types import RetrievedChunk

log = logging.getLogger("atlas.rag.reranker")

_encoder = None


def _get_encoder():
    global _encoder
    if _encoder is None:
        from langchain_community.cross_encoders import HuggingFaceCrossEncoder

        _encoder = HuggingFaceCrossEncoder(model_name=get_settings().rerank_model)
    return _encoder


def rerank_chunks(
    query: str, chunks: list[RetrievedChunk], *, top_n: int | None = None
) -> list[RetrievedChunk]:
    """Re-order chunks by cross-encoder relevance to the query.

    Sets each chunk's ``rerank_score`` and ``score`` to the measured value, so a
    weak result sinks or drops instead of riding a fixed score. Returns the input
    unchanged (order preserved) when offline or if the model is unavailable.
    """
    if not chunks or os.getenv("ATLAS_OFFLINE_EMBED") == "1":
        return chunks[:top_n] if top_n else chunks
    try:
        encoder = _get_encoder()
        pairs = [(query, c.chunk.text[:1000]) for c in chunks]
        scores = encoder.score(pairs)
    except Exception as exc:  # pragma: no cover - model/network drift
        log.warning("rerank unavailable (%s) — keeping original order", exc)
        return chunks[:top_n] if top_n else chunks

    for c, s in zip(chunks, scores, strict=False):
        c.rerank_score = float(s)
        c.score = float(s)
    ranked = sorted(chunks, key=lambda c: c.rerank_score or 0.0, reverse=True)
    return ranked[:top_n] if top_n else ranked
