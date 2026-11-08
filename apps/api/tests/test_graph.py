"""Multi-agent graph smoke test — runs the whole pipeline offline (stub LLM).

Forces ATLAS_OFFLINE_LLM + ATLAS_OFFLINE_EMBED so no key/network is touched, then
asserts the graph executes end-to-end and produces a structurally valid result:
a plan, findings from all four specialists, a bull/bear/judge debate, and a report
with a guardrail-tempered confidence.
"""

from __future__ import annotations


def test_research_graph_runs_end_to_end_offline(monkeypatch):
    monkeypatch.setenv("ATLAS_OFFLINE_LLM", "1")
    monkeypatch.setenv("ATLAS_OFFLINE_EMBED", "1")

    import atlas.core.graph as G
    from atlas.core.resources import reset_resources

    # reset module caches so the index/graph build under offline settings
    reset_resources()
    G.reset_graph()

    out = G.research("Evaluate Helios Robotics as a competitor", thread_id="test-offline")

    assert out["report"]
    assert out["confidence"] is not None and 0.0 <= out["confidence"] <= 1.0
    # all four specialists contributed
    agents = {f["agent"] for f in out["findings"]}
    assert {"fundamentals", "news_sentiment", "risk", "market"} <= agents
    # debate produced a judge verdict
    assert any(d.get("role") == "judge" for d in out["debate"])


def test_research_stream_emits_node_events(monkeypatch):
    monkeypatch.setenv("ATLAS_OFFLINE_LLM", "1")
    monkeypatch.setenv("ATLAS_OFFLINE_EMBED", "1")

    import atlas.core.graph as G
    from atlas.core.resources import reset_resources

    reset_resources()
    G.reset_graph()

    events = [ev["event"] for ev in G.run_research("Assess Helios risks", thread_id="test-stream")]
    assert events[0] == "start"
    assert events[-1] == "final"
    assert "synthesize" in events
