"""Graph nodes that read and write episodic memory."""

from __future__ import annotations

import logging

from langchain_core.runnables import RunnableConfig

from ...config import get_settings
from ..resources import get_episodic, get_index
from ..state import ResearchState
from .summarizer import consolidate

log = logging.getLogger("atlas.memory.nodes")


def owner_of(config: RunnableConfig | None) -> str:
    """The user a run belongs to: the prefix of its user-scoped thread id
    (``routers/research.scoped_thread``). Unscoped (CLI/test) runs have no owner."""
    thread = str(((config or {}).get("configurable") or {}).get("thread_id") or "")
    return thread.split(":", 1)[0] if ":" in thread else ""


def recall_node(state: ResearchState, config: RunnableConfig | None = None) -> dict:
    """This user's earlier runs on this same company, as working memory."""
    episodes = get_episodic().for_subject(owner_of(config), state.get("target") or "")
    ctx = [e.summary() for e in episodes]
    if ctx:
        log.info("Recalled %d prior episode(s) on this subject", len(ctx))
    return {"prior_context": ctx}


def remember_node(state: ResearchState, config: RunnableConfig | None = None) -> dict:
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
        owner=owner_of(config),
    )
    every = get_settings().memory_consolidate_every
    if every and mem.count() % every == 0:
        consolidate(mem, get_index())  # summarizer agent → semantic memory
    return {}
