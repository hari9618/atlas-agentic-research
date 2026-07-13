"""Corrective RAG (CRAG) — make retrieval self-correcting.

After hybrid retrieval, grade whether the evidence actually supports answering the
query. If it's strong, return it. If it's weak/ambiguous, take corrective action:
rewrite the query and re-retrieve, and (optionally) fall back to a web tool.

Grading uses the LLM when configured; otherwise it falls back to a transparent
heuristic over rerank/fused scores — so CRAG runs even with no API key.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum

from .index import HybridIndex
from .types import RetrievedChunk

_TOKEN = re.compile(r"[a-z0-9]+")

log = logging.getLogger("atlas.rag.crag")


class Grade(str, Enum):
    CORRECT = "correct"  # evidence is sufficient
    AMBIGUOUS = "ambiguous"  # partial — augment / rewrite
    INCORRECT = "incorrect"  # off-topic — corrective retrieval needed


@dataclass
class CragResult:
    query: str
    chunks: list[RetrievedChunk]
    grade: Grade
    rewritten_query: str | None = None
    used_web_fallback: bool = False


# Heuristic grade by query↔top-chunk token overlap — engine-agnostic (works whether
# scores come from a reranker, RRF, or nothing at all), and runs offline with no LLM.
_STRONG = 0.5
_WEAK = 0.2


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


def _heuristic_grade(query: str, chunks: list[RetrievedChunk]) -> Grade:
    if not chunks:
        return Grade.INCORRECT
    q = _tokens(query)
    if not q:
        return Grade.INCORRECT
    overlap = len(q & _tokens(chunks[0].text)) / len(q)
    if overlap >= _STRONG:
        return Grade.CORRECT
    if overlap >= _WEAK:
        return Grade.AMBIGUOUS
    return Grade.INCORRECT


def _llm_active() -> bool:
    """LLM should be called: configured AND not forced offline (tests/CI)."""
    import os

    from ...config import get_settings

    return get_settings().llm_configured and os.getenv("ATLAS_OFFLINE_LLM") != "1"


def _llm_grade(query: str, chunks: list[RetrievedChunk]) -> Grade | None:
    """Ask the LLM to grade context relevance. Returns None if LLM unavailable."""
    if not _llm_active():
        return None
    try:
        from ...llm import get_llm
        from ...observability import langchain_callbacks

        evidence = "\n\n".join(f"[{i}] {c.text[:500]}" for i, c in enumerate(chunks[:4]))
        prompt = (
            "You grade retrieved context for answering a question. Reply with ONE word: "
            "CORRECT (fully sufficient), AMBIGUOUS (partially relevant), or INCORRECT "
            "(off-topic).\n\n"
            f"Question: {query}\n\nContext:\n{evidence}\n\nGrade:"
        )
        llm = get_llm(temperature=0.0)
        resp = llm.invoke(prompt, config={"callbacks": langchain_callbacks()})
        text = (resp.content if hasattr(resp, "content") else str(resp)).strip().upper()
        for g in Grade:
            if g.name in text:
                return g
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("LLM grading failed (%s) — using heuristic.", exc)
    return None


def _rewrite_query(query: str) -> str:
    """Lightweight query expansion for the corrective re-retrieval pass."""
    if not _llm_active():
        return query + " overview key facts details"
    try:
        from ...llm import get_llm
        from ...observability import langchain_callbacks

        llm = get_llm(temperature=0.3)
        resp = llm.invoke(
            f"Rewrite this search query to be more specific and keyword-rich for "
            f"document retrieval. Return only the rewritten query.\n\nQuery: {query}",
            config={"callbacks": langchain_callbacks()},
        )
        return (resp.content if hasattr(resp, "content") else str(resp)).strip() or query
    except Exception:  # pragma: no cover
        return query


def corrective_retrieve(
    index: HybridIndex,
    query: str,
    *,
    top_k: int = 5,
    web_fallback=None,
) -> CragResult:
    """Retrieve with one self-correction round.

    Args:
        web_fallback: optional callable(query) -> list[RetrievedChunk] used when
            local evidence is INCORRECT (wired to the web_search MCP tool in M3).
    """
    chunks = index.retrieve(query, top_k=top_k)
    grade = _llm_grade(query, chunks) or _heuristic_grade(query, chunks)

    if grade is Grade.CORRECT:
        return CragResult(query, chunks, grade)

    # Corrective action: rewrite + re-retrieve, then merge & re-rank.
    rewritten = _rewrite_query(query)
    extra = index.retrieve(rewritten, top_k=top_k)
    merged = {c.chunk.chunk_id: c for c in chunks}
    for c in extra:
        merged.setdefault(c.chunk.chunk_id, c)
    chunks = sorted(merged.values(), key=lambda c: c.score, reverse=True)[:top_k]

    used_web = False
    if grade is Grade.INCORRECT and web_fallback is not None:
        try:
            web_chunks = web_fallback(query)
            if web_chunks:
                chunks = (web_chunks + chunks)[:top_k]
                used_web = True
        except Exception as exc:  # pragma: no cover
            log.warning("web_fallback failed: %s", exc)

    return CragResult(query, chunks, grade, rewritten_query=rewritten, used_web_fallback=used_web)
