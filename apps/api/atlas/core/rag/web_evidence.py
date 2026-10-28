"""Web results → retrievable, citable evidence.

CRAG can fall back to the live web when local evidence is graded INCORRECT, but it
needs chunks, not raw search hits. This adapter converts `web_search` results into
``RetrievedChunk``s that carry provenance, so a claim sourced from the web is cited
exactly like one sourced from an ingested filing — the grounding guardrail treats
both the same.

Fails soft by design: no Tavily key, a network error, or an offline test run all
yield an empty list, which callers read as "no web evidence" rather than an error.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from .entity import EntityTerms, entity_terms, mentions_entity
from .reranker import rerank_chunks
from .types import Chunk, RetrievedChunk

log = logging.getLogger("atlas.rag.web_evidence")

# Provisional score before re-ranking; the top hit starts a touch below a strong
# local match, then the cross-encoder assigns the real, comparable score.
_WEB_BASE_SCORE = 0.45


def web_offline() -> bool:
    """True when live network research must be skipped.

    Deliberately NOT tied to ``ATLAS_OFFLINE_EMBED``: production (Render, 512MB) sets
    that flag only to swap in the lightweight hashing embedder, and coupling the two
    silently disabled every web/news/market lookup in production. Web research is off
    only for fully-offline runs (``ATLAS_OFFLINE_LLM=1``, i.e. tests/CI) or when
    explicitly disabled with ``ATLAS_OFFLINE_WEB=1``. Under ``ATLAS_OFFLINE_EMBED=1``
    the re-rank below is a no-op, so no neural model is ever loaded on this path.
    """
    return os.getenv("ATLAS_OFFLINE_LLM") == "1" or os.getenv("ATLAS_OFFLINE_WEB") == "1"


def _offline() -> bool:
    return web_offline()


def filter_hits_for_entity(hits: list[dict], entity: EntityTerms | None,
                           *, label: str = "web") -> list[dict]:
    """Drop hits that aren't about the target company (see entity.py). Logs the count."""
    if entity is None:
        return hits
    kept = [h for h in hits
            if mentions_entity(f"{h.get('title', '')}\n{h.get('content', '')}", entity)]
    if len(kept) < len(hits):
        log.info("entity guard (%s): dropped %d of %d hits not about %r", label,
                 len(hits) - len(kept), len(hits), entity.name or entity.ticker)
    return kept


def web_evidence(query: str, *, max_results: int = 4,
                 entity: EntityTerms | None = None) -> list[RetrievedChunk]:
    """Search the web and return citable chunks, re-ranked (empty when unavailable).

    With ``entity`` set, hits that don't mention that company are discarded: better
    no evidence than evidence about a same-named company.
    """
    if _offline():
        return []
    try:
        from ..tools.web_search import web_search

        hits = web_search(query, max_results=max_results)
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("web evidence lookup failed: %s", exc)
        return []

    hits = filter_hits_for_entity(hits, entity)

    # Web evidence has no publication date we can trust, but we know when we fetched
    # it — record that so "is this stale?" is answerable downstream (Phase 6).
    retrieved_at = datetime.now(UTC).isoformat()
    chunks: list[RetrievedChunk] = []
    for i, hit in enumerate(hits):
        text = (hit.get("content") or "").strip()
        if not text:
            continue
        title = (hit.get("title") or "web result").strip()
        url = hit.get("url", "")
        chunks.append(
            RetrievedChunk(
                chunk=Chunk(
                    # Stable id: the same result for the same query won't duplicate.
                    chunk_id=f"web::{abs(hash((url, i))) % 10**12}",
                    doc_id=f"web_{i}",
                    text=text,
                    source="web_search",
                    title=title,
                    url=url,
                    ordinal=i,
                    metadata={"retrieved_at": retrieved_at},
                ),
                # Provisional score by rank; the re-rank below replaces it with a
                # measured relevance so web evidence is comparable to local evidence.
                score=round(_WEB_BASE_SCORE - i * 0.05, 4),
            )
        )

    # Score web chunks with the same cross-encoder the local path uses, so a weak
    # Tavily hit sinks on measured relevance instead of riding a fixed score.
    chunks = rerank_chunks(query, chunks)
    if chunks:
        log.info("web fallback supplied %d evidence chunks for %r", len(chunks), query[:60])
    return chunks


def web_evidence_about(target: str, ticker: str = ""):
    """A CRAG ``web_fallback`` scoped to one company: off-entity hits are dropped."""
    entity = entity_terms(target, ticker)

    def _fallback(query: str) -> list[RetrievedChunk]:
        return web_evidence(query, entity=entity)

    return _fallback
