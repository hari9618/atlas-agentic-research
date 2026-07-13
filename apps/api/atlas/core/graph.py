"""The Atlas research graph — supervisor → specialists (parallel) → debate → synthesize.

Compiled once with a SQLite checkpointer so runs are durable/resumable. The index is
built once from the corpus and cached. ``run_research`` streams per-node updates for
the war-room UI; ``research`` returns the final state.
"""

from __future__ import annotations

import logging
import os
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from ..config import get_settings
from ..paths import cache_dir
from .agents.debate import debate_node
from .agents.specialists import (
    fundamentals_node,
    market_node,
    news_sentiment_node,
    plan_node,
    risk_node,
)
from .agents.synthesizer import synthesize_node
from .memory.episodic import EpisodicMemory
from .memory.summarizer import consolidate
from .rag.index import HybridIndex
from .rag.ingest import ingest_documents
from .rag.loaders import load_corpus_dir
from .state import ResearchState

log = logging.getLogger("atlas.graph")

_index: HybridIndex | None = None
_graph = None
_episodic: EpisodicMemory | None = None


def get_episodic() -> EpisodicMemory:
    """Build (once) and cache the episodic memory store."""
    global _episodic
    if _episodic is None:
        _episodic = EpisodicMemory(offline=os.getenv("ATLAS_OFFLINE_EMBED") == "1")
    return _episodic


def recall_node(state: ResearchState) -> dict:
    """Read episodic memory: pull relevant + recent past runs into working memory."""
    mem = get_episodic()
    query = state["query"]
    ctx, seen = [], set()
    for e in mem.relevant(query, limit=2) + mem.recent(limit=1):
        if e.id in seen:
            continue
        seen.add(e.id)
        ctx.append(e.summary())
    if ctx:
        log.info("Recalled %d prior episode(s) for this run", len(ctx))
    return {"prior_context": ctx}


def remember_node(state: ResearchState) -> dict:
    """Write to episodic memory; periodically consolidate into semantic facts."""
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


def get_index() -> HybridIndex:
    """Build (once) and cache the hybrid index from the corpus."""
    global _index
    if _index is None:
        offline = os.getenv("ATLAS_OFFLINE_EMBED") == "1"
        docs = load_corpus_dir()
        _index = ingest_documents(docs, offline=offline)
        log.info("Built research index: %d docs, %d chunks", len(docs), len(_index.chunks))
    return _index


def build_graph():
    """Wire and compile the StateGraph with a SQLite checkpointer."""
    # Node names must NOT collide with state keys (LangGraph rule) — hence
    # "supervisor" (state has `plan`) and "debate_round" (state has `debate`).
    g = StateGraph(ResearchState)
    g.add_node("recall", recall_node)          # read episodic memory
    g.add_node("supervisor", plan_node)
    g.add_node("fundamentals", fundamentals_node)
    g.add_node("news_sentiment", news_sentiment_node)
    g.add_node("risk", risk_node)
    g.add_node("market", market_node)
    g.add_node("debate_round", debate_node)
    g.add_node("synthesize", synthesize_node)
    g.add_node("remember", remember_node)      # write episodic memory (+ consolidate)

    g.add_edge(START, "recall")
    g.add_edge("recall", "supervisor")
    for s in ("fundamentals", "news_sentiment", "risk", "market"):
        g.add_edge("supervisor", s)     # fan-out: specialists run in parallel
        g.add_edge(s, "debate_round")   # fan-in: debate waits for all specialists
    g.add_edge("debate_round", "synthesize")
    g.add_edge("synthesize", "remember")
    g.add_edge("remember", END)

    db = cache_dir() / "atlas_checkpoints.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db), check_same_thread=False)
    saver = SqliteSaver(conn)
    try:
        saver.setup()  # create checkpoint tables if missing
    except Exception as exc:  # pragma: no cover
        log.warning("SqliteSaver.setup() failed (%s); continuing.", exc)
    return g.compile(checkpointer=saver)


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def run_research(query: str, *, thread_id: str = "default"):
    """Generator of {event, data} updates per node, ending with a 'final' event."""
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}
    yield {"event": "start", "data": {"query": query}}
    for chunk in graph.stream({"query": query}, config=config, stream_mode="updates"):
        for node, update in chunk.items():
            yield {"event": node, "data": update or {}}
    final = graph.get_state(config).values
    yield {"event": "final", "data": {
        "report": final.get("report", ""),
        "confidence": final.get("confidence"),
        "uncertainties": final.get("uncertainties", []),
        "citations": final.get("citations", []),
        "findings": final.get("findings", []),
        "debate": final.get("debate", []),
        "plan": final.get("plan", []),
    }}


def research(query: str, *, thread_id: str = "default") -> dict:
    """Run to completion and return the final state (non-streaming)."""
    result = None
    for ev in run_research(query, thread_id=thread_id):
        if ev["event"] == "final":
            result = ev["data"]
    return result or {}
