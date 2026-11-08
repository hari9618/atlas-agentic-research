"""Graph nodes that read and write episodic memory."""

from __future__ import annotations

import logging

from ...config import get_settings
from ..resources import get_episodic, get_index
from ..state import ResearchState
from .summarizer import consolidate

log = logging.getLogger("atlas.memory.nodes")


def recall_node(state: ResearchState) -> dict:
    """Pull relevant and recent past runs into this run's working memory."""
    mem = get_episodic()
    ctx, seen = [], set()
    for e in mem.relevant(state["query"], limit=2) + mem.recent(limit=1):
        if e.id not in seen:
            seen.add(e.id)
            ctx.append(e.summary())
    if ctx:
        log.info("Recalled %d prior episode(s) for this run", len(ctx))
    return {"prior_context": ctx}


def remember_node(state: ResearchState) -> dict:
    """Save an accepted run to episodic memory; periodically consolidate into facts.

    Only approved (or auto-approved) reports reach this node: a rejected report is
    routed past it, so a run a human threw out never becomes "memory".
    """
    mem = get_episodic()
    mem.save(
        query=state["query"],
        report=state.get("report", ""),
        confidence=state.get("confidence"),
        findings=state.get("findings", []),
        target=state.get("target", ""),
    )
    every = get_settings().memory_consolidate_every
    if every and mem.count() % every == 0:
        consolidate(mem, get_index())  # summarizer agent → semantic memory
    return {}
