"""Summarizer agent — consolidate episodic memory into durable semantic facts.

Runs on a cheaper/faster model (per the architecture: "Summarizer Agent (cheaper
models)"). Triggered after every N episodes, it distills recent research runs into
reusable facts and writes them into semantic memory (the RAG index), so future runs
start smarter. Degrades to a deterministic stub when no LLM is active.
"""

from __future__ import annotations

import logging
import os

from ...config import get_settings
from ..rag.chunking import chunk_document
from ..rag.types import Document
from .episodic import EpisodicMemory

log = logging.getLogger("atlas.memory.summarizer")


def _llm_active() -> bool:
    return get_settings().llm_configured and os.getenv("ATLAS_OFFLINE_LLM") != "1"


def consolidate(episodic: EpisodicMemory, index, *, last_n: int | None = None) -> list[str]:
    """Distill the last N episodes into facts and add them to semantic memory."""
    settings = get_settings()
    last_n = last_n or settings.memory_consolidate_every
    episodes = episodic.recent(last_n)
    if not episodes:
        return []

    if not _llm_active():
        facts = [
            f"Prior analysis of '{e.query}' concluded with confidence {e.confidence}."
            for e in episodes
        ]
    else:
        from ...llm import get_llm
        from ...observability import langchain_callbacks

        transcript = "\n\n".join(e.summary(500) for e in episodes)
        prompt = (
            "You are a memory consolidator. From these past research runs, extract durable, "
            "reusable facts (company facts, key numbers, relationships). One fact per line, "
            "no preamble.\n\n" + transcript
        )
        llm = get_llm(temperature=0.0, model=settings.summarizer_model)
        resp = llm.invoke(
            prompt, config={"callbacks": langchain_callbacks(), "run_name": "memory.summarizer"}
        )
        text = resp.content if hasattr(resp, "content") else str(resp)
        facts = [ln.strip("-• ").strip() for ln in text.splitlines() if len(ln.strip()) > 10]

    if facts:
        doc = Document(
            doc_id=f"memory_facts_{episodic.count()}",
            text="\n".join(f"- {f}" for f in facts),
            source="memory",
            title="Consolidated memory facts",
        )
        index.add_chunks(chunk_document(doc))
        log.info("Consolidated %d facts into semantic memory", len(facts))
    return facts
