"""Postgres integration tests — durable checkpoints, memory and registry.

Skipped unless ``ATLAS_TEST_DATABASE_URL`` points at a throwaway database, e.g.::

    docker run -d --name atlas-pg-test -e POSTGRES_PASSWORD=atlas -e POSTGRES_DB=atlas \\
        -p 55432:5432 postgres:16
    ATLAS_TEST_DATABASE_URL=postgresql://postgres:atlas@localhost:55432/atlas pytest \\
        tests/test_persistence_pg.py

The key property under test: a run paused by ``interrupt()`` can be resumed by a
brand-new saver on a brand-new pool — i.e. it survives a server restart. Every test
uses unique ids and deletes only the rows it created, so reruns are idempotent.
"""

from __future__ import annotations

import operator
import os
import uuid
from typing import Annotated, TypedDict

import pytest

PG_URL = os.getenv("ATLAS_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not PG_URL, reason="ATLAS_TEST_DATABASE_URL not set")


@pytest.fixture
def pool():
    from atlas.core.persistence import open_pg_pool

    p = open_pg_pool(PG_URL)
    yield p
    p.close()


class _S(TypedDict, total=False):
    topic: str
    draft: str
    decision: str


class _FanState(TypedDict, total=False):
    topic: str
    findings: Annotated[list[str], operator.add]  # parallel branches append


def _review_graph(saver):
    """write draft → human review (interrupt) → finalize — a miniature of the Atlas HITL flow."""
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import interrupt

    def draft(state: _S) -> _S:
        return {"draft": f"report on {state['topic']}"}

    def review(state: _S) -> _S:
        answer = interrupt({"draft": state["draft"]})
        return {"decision": answer}

    def finalize(state: _S) -> _S:
        return {"draft": state["draft"] + f" [{state['decision']}]"}

    g = StateGraph(_S)
    g.add_node("write", draft)  # node names must not collide with state keys
    g.add_node("review", review)
    g.add_node("finalize", finalize)
    g.add_edge(START, "write")
    g.add_edge("write", "review")
    g.add_edge("review", "finalize")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=saver)


def _delete_thread(pool, thread_id: str) -> None:
    with pool.connection() as conn:
        for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
            conn.execute(f"DELETE FROM {table} WHERE thread_id = %s", (thread_id,))


def test_checkpointer_round_trip(pool):
    from langgraph.graph import END, START, StateGraph

    from atlas.core.persistence import postgres_saver

    def step(state: _S) -> _S:
        return {"draft": state["topic"].upper()}

    g = StateGraph(_S)
    g.add_node("step", step)
    g.add_edge(START, "step")
    g.add_edge("step", END)
    app = g.compile(checkpointer=postgres_saver(pool))

    tid = f"rt-{uuid.uuid4()}"
    cfg = {"configurable": {"thread_id": tid}}
    try:
        out = app.invoke({"topic": "helios"}, cfg)
        assert out["draft"] == "HELIOS"
        assert app.get_state(cfg).values == {"topic": "helios", "draft": "HELIOS"}
    finally:
        _delete_thread(pool, tid)


def test_interrupted_run_resumes_after_restart():
    """Pause on process A's pool; resume on an entirely new pool + saver (process B)."""
    from langgraph.types import Command

    from atlas.core.persistence import open_pg_pool, postgres_saver

    tid = f"hitl-{uuid.uuid4()}"
    cfg = {"configurable": {"thread_id": tid}}

    pool_a = open_pg_pool(PG_URL)
    try:
        app_a = _review_graph(postgres_saver(pool_a))
        app_a.invoke({"topic": "helios"}, cfg)
        snap = app_a.get_state(cfg)
        assert snap.next == ("review",), "run should be paused at human review"
        assert snap.tasks[0].interrupts[0].value == {"draft": "report on helios"}
    finally:
        pool_a.close()  # "server restart": every connection from run A is gone

    pool_b = open_pg_pool(PG_URL)
    try:
        app_b = _review_graph(postgres_saver(pool_b))
        assert app_b.get_state(cfg).next == ("review",), "paused state lost on restart"
        out = app_b.invoke(Command(resume="approve"), cfg)
        assert out["decision"] == "approve"
        assert out["draft"] == "report on helios [approve]"
        assert app_b.get_state(cfg).next == ()
    finally:
        _delete_thread(pool_b, tid)
        pool_b.close()


def test_episodic_memory_on_postgres(pool):
    from atlas.core.memory.episodic import EpisodicMemory

    tag = uuid.uuid4().hex[:8]
    mem = EpisodicMemory(offline=True, pool=pool)
    assert mem.backend == "postgres"
    try:
        before = mem.count()
        mem.save(f"Helios Robotics revenue {tag}", "report A", 0.7,
                 [{"agent": "risk", "claim": "x"}], target="Helios")
        mem.save(f"Weather in Paris tomorrow {tag}", "report B", 0.5, [])
        assert mem.count() == before + 2

        latest = mem.recent(1)[0]
        assert latest.query == f"Weather in Paris tomorrow {tag}"
        assert latest.created_at[:4].isdigit() and latest.findings == []

        # A fresh instance (new process) sees the same rows, with stored vectors.
        mem2 = EpisodicMemory(offline=True, pool=pool)
        top = mem2.relevant(f"Helios Robotics revenue {tag}", limit=1)[0]
        assert top.query == f"Helios Robotics revenue {tag}"
        assert top.target == "Helios" and top.confidence == 0.7
        assert top.findings == [{"agent": "risk", "claim": "x"}]

        # Rows saved without a vector are embedded on recall and backfilled.
        with pool.connection() as conn:
            conn.execute("UPDATE atlas_episodes SET embedding = NULL WHERE query LIKE %s",
                         (f"%{tag}",))
        assert mem2.relevant(f"Helios Robotics revenue {tag}", limit=1)[0].query.startswith(
            "Helios")
        with pool.connection() as conn:
            n_null = conn.execute(
                "SELECT COUNT(*) AS n FROM atlas_episodes "
                "WHERE query LIKE %s AND embedding IS NULL", (f"%{tag}",),
            ).fetchone()["n"]
        assert n_null == 0
    finally:
        with pool.connection() as conn:
            conn.execute("DELETE FROM atlas_episodes WHERE query LIKE %s", (f"%{tag}",))


def test_registry_release_survives_reinstantiation(pool, monkeypatch):
    import atlas.core.llmops.registry as registry_mod
    from atlas.core.llmops.registry import PromptRegistry

    name = f"test_prompt_{uuid.uuid4().hex[:8]}"
    # Seed only this test's prompt so the test never writes rows it doesn't clean up.
    monkeypatch.setattr(registry_mod, "SEED_PROMPTS", {name: "seed text"})
    try:
        reg = PromptRegistry(pool=pool)
        assert reg.backend == "postgres"
        assert reg.active_version(name) == 1

        reg.set_candidate(name, "A BETTER PROMPT")
        assert PromptRegistry(pool=pool).effective(name) == "A BETTER PROMPT"  # canary durable

        assert reg.release_candidate(name, {"faithfulness": 0.9}, notes="pg test") == 2

        reg2 = PromptRegistry(pool=pool)
        assert reg2.active_version(name) == 2
        assert reg2.effective(name) == "A BETTER PROMPT"
        assert [v.version for v in reg2.history(name)] == [1, 2]
        assert reg2.history(name)[-1].scores == {"faithfulness": 0.9}
    finally:
        with pool.connection() as conn:
            conn.execute("DELETE FROM atlas_prompt_registry WHERE name = %s", (name,))


def test_get_checkpointer_uses_postgres_when_configured(monkeypatch):
    from langgraph.checkpoint.postgres import PostgresSaver

    from atlas.config import get_settings
    from atlas.core import persistence

    monkeypatch.setenv("DATABASE_URL", PG_URL.replace("postgresql://", "postgres://", 1))
    get_settings.cache_clear()
    persistence.reset_persistence()
    try:
        assert persistence.using_postgres()
        assert isinstance(persistence.get_checkpointer(), PostgresSaver)
        assert persistence.get_checkpointer() is persistence.get_checkpointer()
    finally:
        persistence.reset_persistence()
        get_settings.cache_clear()


def test_shared_saver_is_thread_safe_under_parallel_fan_out(pool):
    """Atlas compiles one graph and runs parallel specialists from many request threads."""
    from concurrent.futures import ThreadPoolExecutor

    from langgraph.graph import END, START, StateGraph

    from atlas.core.persistence import postgres_saver

    g = StateGraph(_FanState)
    for agent in ("fundamentals", "news", "risk", "market"):
        g.add_node(agent, lambda s, a=agent: {"findings": [f"{a}:{s['topic']}"]})
        g.add_edge(START, agent)
        g.add_edge(agent, END)
    app = g.compile(checkpointer=postgres_saver(pool))

    tids = [f"fan-{uuid.uuid4()}" for _ in range(8)]

    def run(tid: str) -> list[str]:
        return app.invoke({"topic": tid}, {"configurable": {"thread_id": tid}})["findings"]

    try:
        with ThreadPoolExecutor(max_workers=8) as ex:
            results = list(ex.map(run, tids))
        for tid, findings in zip(tids, results, strict=True):
            assert sorted(findings) == sorted(
                f"{a}:{tid}" for a in ("fundamentals", "news", "risk", "market"))
    finally:
        for tid in tids:
            _delete_thread(pool, tid)
