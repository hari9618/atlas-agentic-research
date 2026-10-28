"""The Atlas research graph (design §3).

    recall → supervisor → [fundamentals ‖ news_sentiment ‖ risk ‖ market]
           → debate_round → synthesize → human_review
    human_review: approve / auto → remember → END
    human_review: revise → revise_research → synthesize   (capped at max_revisions)

Compiled once with the configured checkpointer (Postgres or SQLite, see
persistence.py) so a run paused for human review survives restarts and can be
resumed. ``run_research`` / ``resume_research`` stream per-node updates for the UI
and end with ``review_required`` (paused) or ``final``; ``research`` runs to
completion with review off.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from ..config import get_settings
from .agents.debate import debate_node
from .agents.review import (
    ACTIONS,
    human_review_node,
    revise_research_node,
    route_after_review,
)
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
from .payload import research_payload
from .persistence import get_checkpointer
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
    """Wire and compile the StateGraph with the configured checkpointer."""
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
    g.add_node("human_review", human_review_node)        # interrupt() for approval
    g.add_node("revise_research", revise_research_node)  # feedback-driven research
    g.add_node("remember", remember_node)      # write episodic memory (+ consolidate)

    g.add_edge(START, "recall")
    g.add_edge("recall", "supervisor")
    for s in ("fundamentals", "news_sentiment", "risk", "market"):
        g.add_edge("supervisor", s)     # fan-out: specialists run in parallel
        g.add_edge(s, "debate_round")   # fan-in: debate waits for all specialists
    g.add_edge("debate_round", "synthesize")
    g.add_edge("synthesize", "human_review")
    g.add_conditional_edges(
        "human_review", route_after_review,
        {"revise_research": "revise_research", "remember": "remember"},
    )
    g.add_edge("revise_research", "synthesize")
    g.add_edge("remember", END)
    return g.compile(checkpointer=get_checkpointer())


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


class RunNotPausedError(LookupError):
    """Resume was requested for a thread that is not waiting for review."""


def _run_config(thread_id: str, query: str, *, resume: bool = False) -> dict:
    """Per-run config.

    The Langfuse handler is attached at the *graph* level so the whole run is ONE
    trace tree (named "atlas_research_run") with every agent/tool call nested
    underneath — token usage, cost and latency roll up per run. The ``langfuse_*``
    metadata keys group the start and every resume of a thread into one session
    (session id = thread id) and tag them so they're easy to find on the dashboard.
    """
    from ..observability import langchain_callbacks  # lazy: keeps import graph clean

    tags = ["atlas", "research_run"] + (["resume"] if resume else [])
    return {
        "configurable": {"thread_id": thread_id},
        "callbacks": langchain_callbacks(),
        "run_name": "atlas_research_run",
        "metadata": {
            "langfuse_session_id": thread_id,
            "langfuse_tags": tags,
            "atlas_query": query,
        },
    }


def _pending_interrupt(snapshot) -> dict | None:
    """The interrupt payload if the graph is paused at human_review, else None.

    In langgraph 0.2.76 a paused run surfaces as an ``__interrupt__`` entry in the
    "updates" stream and, durably, as ``snapshot.next == ("human_review",)`` with
    the ``Interrupt`` objects on ``snapshot.tasks[i].interrupts``. The checkpoint is
    the source of truth (it also works for a resume on another worker).
    """
    if not snapshot.next:
        return None
    for task in snapshot.tasks:
        for intr in getattr(task, "interrupts", ()) or ():
            if isinstance(intr.value, dict):
                return intr.value
    return None


def _drive(graph, inp, config: dict, thread_id: str) -> Iterator[dict]:
    """Stream node updates, then emit ``review_required`` (paused) or ``final``."""
    for chunk in graph.stream(inp, config=config, stream_mode="updates"):
        for node, update in chunk.items():
            if node == "__interrupt__":  # surfaced below from the checkpoint
                continue
            yield {"event": node, "data": update or {}}

    snapshot = graph.get_state(config)
    values = snapshot.values
    pending = _pending_interrupt(snapshot)
    if pending is not None:
        payload = {**research_payload(values), **pending}
        payload.update(thread_id=thread_id, revision=values.get("revision", 0) or 0,
                       review_status="pending")
        yield {"event": "review_required", "data": payload}
        return
    if snapshot.next:  # paused somewhere other than review — should not happen
        raise RuntimeError(f"run stopped unexpectedly before {snapshot.next}")

    result = research_payload(values)
    result.update(thread_id=thread_id, revision=values.get("revision", 0) or 0,
                  review_status=values.get("review_status") or "auto_approved")
    yield {"event": "final", "data": result}
    # After the report has streamed to the user, auto-evaluate the run and push the
    # scores to Langfuse — once, for the approved final report only. Best-effort: a
    # scoring hiccup must never fail the research run.
    _score_run(values.get("query", ""), result)


def run_research(query: str, *, thread_id: str = "default",
                 require_review: bool = False) -> Iterator[dict]:
    """Start a run. Yields ``start``, one event per node update, then
    ``review_required`` (paused for a human) or ``final``."""
    graph = get_graph()
    config = _run_config(thread_id, query)
    # Fresh run inputs. ``None`` clears the additive lists (findings/debate/history)
    # left by an earlier run on a reused thread id, and the review scalars are reset
    # so a new run never inherits a previous run's revision count or feedback.
    inp = {
        "query": query, "require_review": require_review,
        "findings": None, "debate": None, "review_history": None,
        "revision": 0, "feedback": "", "review_status": "pending",
        "report": "", "report_sections": None, "uncertainties": [], "citations": [],
        "target": "", "ticker": "",
    }
    yield {"event": "start", "data": {"query": query, "thread_id": thread_id}}
    yield from _drive(graph, inp, config, thread_id)


def thread_status(thread_id: str) -> str:
    """``paused`` (waiting at human_review), ``finished`` (has state, not waiting) or
    ``unknown`` (no checkpoint for this thread id)."""
    snapshot = get_graph().get_state({"configurable": {"thread_id": thread_id}})
    if _pending_interrupt(snapshot) is not None:
        return "paused"
    return "finished" if snapshot.values else "unknown"


def is_paused(thread_id: str) -> bool:
    """True when ``thread_id`` is waiting at human_review for a decision."""
    return thread_status(thread_id) == "paused"


def resume_research(thread_id: str, decision: dict) -> Iterator[dict]:
    """Resume a paused run with ``{"action": "approve"}`` or
    ``{"action": "revise", "feedback": "..."}``; same events as ``run_research``.

    Raises ``ValueError`` for an invalid decision and ``RunNotPausedError`` if the
    thread isn't waiting for review — both eagerly, before anything is streamed.
    """
    action = str((decision or {}).get("action", "")).strip().lower()
    feedback = str((decision or {}).get("feedback") or "").strip()
    if action not in ACTIONS:
        raise ValueError(f"action must be one of {ACTIONS}")
    if action == "revise" and not feedback:
        raise ValueError("feedback is required to request a revision")

    graph = get_graph()
    snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
    if _pending_interrupt(snapshot) is None:
        raise RunNotPausedError(f"thread {thread_id!r} is not waiting for review")
    query = snapshot.values.get("query", "")
    config = _run_config(thread_id, query, resume=True)
    command = Command(resume={"action": action, "feedback": feedback})

    def _events() -> Iterator[dict]:
        yield {"event": "start", "data": {"query": query, "thread_id": thread_id,
                                          "resume": action}}
        yield from _drive(graph, command, config, thread_id)

    return _events()


def _score_run(query: str, result: dict) -> None:
    """Per-run automatic eval → push scores to Langfuse. Never raises."""
    if not (result.get("report") and get_settings().llm_configured):
        return
    if os.getenv("ATLAS_OFFLINE_LLM") == "1":
        return  # offline/test runs produce stub reports; never score or push them
    try:
        from .llmops.evaluate import evaluate_run

        scores = evaluate_run(query, result, push=True)
        log.info(
            "Run scored → faithfulness=%.3f relevancy=%.3f (pushed to Langfuse)",
            scores.get("faithfulness", 0.0),
            scores.get("relevancy", 0.0),
        )
    except Exception as exc:  # pragma: no cover - scoring is best-effort
        log.warning("Per-run scoring/push failed (non-fatal): %s", exc)


def research(query: str, *, thread_id: str = "default") -> dict:
    """Run to completion with review off and return the final payload (non-streaming).

    Used by ``/research/sync``, the LLM-Ops optimizer and the eval harness.
    """
    result = None
    for ev in run_research(query, thread_id=thread_id, require_review=False):
        if ev["event"] == "final":
            result = ev["data"]
    return result or {}
