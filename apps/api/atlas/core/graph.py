"""The Atlas research graph (design §3) and the run driver.

    supervisor → recall → [fundamentals ‖ news_sentiment ‖ risk ‖ market]
           → debate_round → synthesize → human_review
    human_review: approve / auto → remember → END
    human_review: revise         → revise_research → synthesize   (capped at max_revisions)
    human_review: reject         → END   (a rejected report never becomes memory)

Compiled once with the configured checkpointer (Postgres or SQLite, see
persistence.py), so a run paused for human review survives restarts and can be
resumed on any worker. ``run_research`` / ``resume_research`` stream per-node
updates for the UI and end with ``review_required`` (paused) or ``final``.

Every finished run is evaluated and recorded (``llmops.records``) together with the
reviewer's decisions — the raw material of the learning loop (``llmops.improver``).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

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
from .agents.specialists import SPECIALIST_NODES, plan_node
from .agents.synthesizer import synthesize_node
from .memory.nodes import recall_node, remember_node
from .payload import research_payload
from .persistence import get_checkpointer
from .state import ResearchState

log = logging.getLogger("atlas.graph")

_graph = None


def build_graph():
    """Wire and compile the StateGraph with the configured checkpointer."""
    # Node names must NOT collide with state keys (LangGraph rule) — hence
    # "supervisor" (state has `plan`) and "debate_round" (state has `debate`).
    g = StateGraph(ResearchState)
    g.add_node("recall", recall_node)
    g.add_node("supervisor", plan_node)
    for name, node in SPECIALIST_NODES.items():
        g.add_node(name, node)
    g.add_node("debate_round", debate_node)
    g.add_node("synthesize", synthesize_node)
    g.add_node("human_review", human_review_node)        # interrupt() for a decision
    g.add_node("revise_research", revise_research_node)  # feedback-driven research
    g.add_node("remember", remember_node)

    # The brief comes first: memory is recalled for THIS subject and THIS user, which
    # needs the subject identified (it used to be recalled by raw-question similarity,
    # pulling other companies' — and other users' — reports into the prompt).
    g.add_edge(START, "supervisor")
    g.add_edge("supervisor", "recall")
    for name in SPECIALIST_NODES:
        g.add_edge("recall", name)          # fan-out: specialists run in parallel
        g.add_edge(name, "debate_round")    # fan-in: debate waits for all of them
    g.add_edge("debate_round", "synthesize")
    g.add_edge("synthesize", "human_review")
    g.add_conditional_edges(
        "human_review", route_after_review,
        {"revise_research": "revise_research", "remember": "remember", "end": END},
    )
    g.add_edge("revise_research", "synthesize")
    g.add_edge("remember", END)
    return g.compile(checkpointer=get_checkpointer())


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def reset_graph() -> None:
    """Recompile on next use (tests, or after the checkpointer changes)."""
    global _graph
    _graph = None


class RunNotPausedError(LookupError):
    """Resume was requested for a thread that is not waiting for review."""


def _run_config(thread_id: str, query: str, *, resume: bool = False) -> dict:
    """Per-run config: one Langfuse trace tree per run, grouped by thread (session)."""
    from ..observability import langchain_callbacks  # lazy: keeps import graph clean

    return {
        "configurable": {"thread_id": thread_id},
        "callbacks": langchain_callbacks(),
        "run_name": "atlas_research_run",
        "metadata": {
            "langfuse_session_id": thread_id,
            "langfuse_tags": ["atlas", "research_run"] + (["resume"] if resume else []),
            "atlas_query": query,
        },
    }


def _pending_interrupt(snapshot) -> dict | None:
    """The interrupt payload if the graph is paused at human_review, else None.

    The checkpoint is the source of truth (it also works for a resume on another
    worker): a paused run has ``snapshot.next`` set and the ``Interrupt`` objects on
    its tasks.
    """
    if not snapshot.next:
        return None
    for task in snapshot.tasks:
        for intr in getattr(task, "interrupts", ()) or ():
            if isinstance(intr.value, dict):
                return intr.value
    return None


def _drive(graph, inp, config: dict, thread_id: str, *, record: bool = True) -> Iterator[dict]:
    """Stream node updates, then emit ``review_required`` (paused) or ``final``."""
    for chunk in graph.stream(inp, config=config, stream_mode="updates"):
        for node, update in chunk.items():
            if node != "__interrupt__":  # surfaced below from the checkpoint
                yield {"event": node, "data": update or {}}

    snapshot = graph.get_state(config)
    values = snapshot.values
    revision = values.get("revision", 0) or 0
    pending = _pending_interrupt(snapshot)
    if pending is not None:
        payload = {**research_payload(values), **pending,
                   "thread_id": thread_id, "revision": revision, "review_status": "pending"}
        yield {"event": "review_required", "data": payload}
        return
    if snapshot.next:  # paused somewhere other than review — should not happen
        raise RuntimeError(f"run stopped unexpectedly before {snapshot.next}")

    result = {**research_payload(values), "thread_id": thread_id, "revision": revision,
              "review_status": values.get("review_status") or "auto_approved"}
    yield {"event": "final", "data": result}
    # After the report reached the user: evaluate and record the run. Best-effort —
    # learning bookkeeping must never fail a research run.
    if record:
        # Off the stream: scoring makes several judge calls. Run inline, it held the
        # user's run slot (capacity) and was cancelled when the client closed on
        # `final`. A small bounded pool keeps the learning bookkeeping best-effort.
        _RECORDER.submit(_record_run, values, thread_id, result)


_RECORDER = ThreadPoolExecutor(max_workers=2, thread_name_prefix="atlas-record")


def drain_recorder(timeout: float = 30.0) -> None:
    """Wait for queued run records (tests, graceful shutdown)."""
    global _RECORDER
    _RECORDER.shutdown(wait=True, cancel_futures=False)
    _RECORDER = ThreadPoolExecutor(max_workers=2, thread_name_prefix="atlas-record")


def _record_run(values: dict, thread_id: str, result: dict) -> None:
    from .llmops.improver import check_regressions
    from .llmops.policy import get_policies
    from .llmops.records import build_record, get_records

    try:
        scores = None
        live = get_settings().llm_configured and os.getenv("ATLAS_OFFLINE_LLM") != "1"
        if live and result.get("report"):
            from .llmops.evaluate import evaluate_run

            scores = evaluate_run(values.get("query", ""), result, push=True)
            log.info("run %s scored: overall=%.3f (%s)", thread_id, scores["overall"],
                     scores["quality"])
        get_records().save(build_record(values, thread_id=thread_id, scores=scores,
                                        policy_versions=get_policies().snapshot()))
        check_regressions()
    except Exception as exc:  # pragma: no cover - bookkeeping is best-effort
        log.warning("recording run %s failed (non-fatal): %s", thread_id, exc)


def run_research(query: str, *, thread_id: str = "default", require_review: bool = False,
                 record: bool = True) -> Iterator[dict]:
    """Start a run. Yields ``start``, one event per node update, then
    ``review_required`` (paused for a human) or ``final``."""
    graph = get_graph()
    config = _run_config(thread_id, query)
    # Fresh inputs. ``None`` clears the additive lists (findings/debate/history) a
    # previous run on a reused thread id left behind; review scalars are reset too.
    inp = {
        "query": query, "require_review": require_review,
        "findings": None, "debate": None, "review_history": None,
        "revision": 0, "feedback": "", "feedback_section": "", "review_status": "pending",
        "report": "", "report_sections": None, "uncertainties": [], "citations": [],
        "target": "", "ticker": "",
    }
    yield {"event": "start", "data": {"query": query, "thread_id": thread_id}}
    yield from _drive(graph, inp, config, thread_id, record=record)


def thread_status(thread_id: str) -> str:
    """``paused`` (waiting at human_review), ``finished`` or ``unknown`` (no checkpoint)."""
    snapshot = get_graph().get_state({"configurable": {"thread_id": thread_id}})
    if _pending_interrupt(snapshot) is not None:
        return "paused"
    return "finished" if snapshot.values else "unknown"


def is_paused(thread_id: str) -> bool:
    return thread_status(thread_id) == "paused"


def resume_research(thread_id: str, decision: dict) -> Iterator[dict]:
    """Resume a paused run with ``{"action": "approve" | "revise" | "reject",
    "feedback": str, "section": str}``; same events as ``run_research``.

    Raises ``ValueError`` for an invalid decision and ``RunNotPausedError`` if the
    thread isn't waiting for review — both eagerly, before anything is streamed.
    """
    action = str((decision or {}).get("action", "")).strip().lower()
    feedback = str((decision or {}).get("feedback") or "").strip()
    section = str((decision or {}).get("section") or "").strip()
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
    command = Command(resume={"action": action, "feedback": feedback, "section": section})

    def _events() -> Iterator[dict]:
        yield {"event": "start", "data": {"query": query, "thread_id": thread_id,
                                          "resume": action}}
        yield from _drive(graph, command, config, thread_id)

    return _events()


def research(query: str, *, thread_id: str = "default", record: bool = True) -> dict:
    """Run to completion with review off and return the final payload (non-streaming).

    Used by ``/research/sync`` and the eval harness.
    """
    result = None
    for ev in run_research(query, thread_id=thread_id, require_review=False, record=record):
        if ev["event"] == "final":
            result = ev["data"]
    return result or {}
