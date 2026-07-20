"""Per-agent evaluation tests (offline) — attribute quality to a specific specialist."""

from __future__ import annotations

from atlas.core.llmops.agent_eval import evaluate_agents, score_agent, weakest_agent


def test_score_agent_rewards_grounded_and_rich():
    findings = [
        {"agent": "risk", "claim": "supplier concentration", "citation": "10-K p12"},
        {"agent": "risk", "claim": "regulatory exposure", "citation": "10-K p8"},
        {"agent": "risk", "claim": "customer concentration", "citation": "10-K p9"},
    ]
    s = score_agent(findings)
    assert s["groundedness"] == 1.0
    assert s["richness"] == 1.0
    assert s["score"] == 1.0
    assert s["n_findings"] == 3


def test_score_agent_penalises_missing_citations():
    findings = [
        {"agent": "market", "claim": "big market", "citation": "n/a"},
        {"agent": "market", "claim": "few rivals", "citation": "n/a"},
    ]
    s = score_agent(findings)
    assert s["groundedness"] == 0.0
    assert s["score"] < 0.5  # ungrounded work scores low even if it has claims


def test_stub_and_empty_findings_do_not_count_as_solid():
    findings = [
        {"agent": "news_sentiment", "claim": "[offline stub] news analysis", "citation": "n/a"},
        {"agent": "news_sentiment", "claim": "No well-grounded finding extracted.", "citation": "n/a"},
    ]
    s = score_agent(findings)
    assert s["n_findings"] == 0
    assert s["score"] == 0.0


def test_evaluate_agents_groups_and_ranks(monkeypatch):
    # Don't touch Langfuse in the offline suite.
    findings = [
        {"agent": "fundamentals", "claim": "revenue up 40%", "citation": "10-K p3"},
        {"agent": "fundamentals", "claim": "margin pressure", "citation": "10-K p4"},
        {"agent": "risk", "claim": "vague worry", "citation": "n/a"},
    ]
    results = evaluate_agents(findings, query="analyze co", push=False)
    assert set(results) == {"fundamentals", "risk"}
    assert results["fundamentals"]["score"] > results["risk"]["score"]
    # The risk agent is the weakest → the one to improve next.
    assert weakest_agent(results) == "risk"


def test_evaluate_agents_empty_is_safe():
    assert evaluate_agents([], push=False) == {}
    assert weakest_agent({}) is None
