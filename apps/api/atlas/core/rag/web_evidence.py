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

from .types import Chunk, RetrievedChunk

log = logging.getLogger("atlas.rag.web_evidence")

# Web hits rank below local corpus evidence: the corpus is curated, the web is not.
_WEB_BASE_SCORE = 0.45


def _offline() -> bool:
    return os.getenv("ATLAS_OFFLINE_LLM") == "1" or os.getenv("ATLAS_OFFLINE_EMBED") == "1"


def web_evidence(query: str, *, max_results: int = 4) -> list[RetrievedChunk]:
    """Search the web and return citable chunks (empty when unavailable)."""
    if _offline():
        return []
    try:
        from ..tools.web_search import web_search

        hits = web_search(query, max_results=max_results)
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("web evidence lookup failed: %s", exc)
        return []

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
                ),
                # Decay by rank so the top hit outranks the fourth.
                score=round(_WEB_BASE_SCORE - i * 0.05, 4),
            )
        )
    if chunks:
        log.info("web fallback supplied %d evidence chunks for %r", len(chunks), query[:60])
    return chunks
