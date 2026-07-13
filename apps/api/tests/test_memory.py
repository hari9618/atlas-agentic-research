"""Memory-layer tests — episodic (SQL + relevance), procedural, summarizer (offline)."""

from __future__ import annotations

from atlas.core.memory.episodic import EpisodicMemory
from atlas.core.memory.procedural import ProceduralMemory
from atlas.core.memory.summarizer import consolidate
from atlas.core.rag.index import build_index


def test_episodic_save_and_recency(tmp_path):
    mem = EpisodicMemory(db_path=tmp_path / "ep.sqlite", offline=True)
    mem.save("Analyze Helios", "report A", 0.7, [{"agent": "risk", "claim": "x"}])
    mem.save("Analyze Aster", "report B", 0.6, [])
    assert mem.count() == 2
    recent = mem.recent(1)
    assert len(recent) == 1
    assert recent[0].findings == [] or isinstance(recent[0].findings, list)


def test_episodic_many_ops_do_not_leak_or_error(tmp_path):
    # Regression: connections are closed each call (was leaking); many ops must be safe.
    mem = EpisodicMemory(db_path=tmp_path / "ep.sqlite", offline=True)
    for i in range(30):
        mem.save(f"query {i}", "report", 0.5, [])
        mem.recent(2)
        mem.count()
    assert mem.count() == 30


def test_episodic_relevance_ranks_similar_query_first(tmp_path):
    mem = EpisodicMemory(db_path=tmp_path / "ep.sqlite", offline=True)
    mem.save("Helios Robotics revenue and growth", "r", 0.7, [])
    mem.save("Weather in Paris tomorrow", "r", 0.5, [])
    rel = mem.relevant("Helios Robotics financials", limit=1)
    assert rel and "Helios" in rel[0].query


def test_procedural_loads_playbook_and_missing_is_empty():
    proc = ProceduralMemory()
    assert "Risk analyst" in proc.get("risk")
    assert proc.get("does_not_exist") == ""


def test_summarizer_offline_writes_facts_into_semantic_memory(tmp_path):
    mem = EpisodicMemory(db_path=tmp_path / "ep.sqlite", offline=True)
    mem.save("Analyze Helios", "Helios has strong software revenue", 0.7, [])
    index = build_index(offline=True, prefer_qdrant=False)
    before = len(index.chunks)
    facts = consolidate(mem, index, last_n=5)
    assert facts
    assert len(index.chunks) > before
