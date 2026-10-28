"""Tool evidence, new provenance tiers, supervisor plan, specialist merge/degrade.

Also the production regression: web research must stay ON when only
``ATLAS_OFFLINE_EMBED=1`` is set (Render uses it just for the light embedder) — and
must not load a neural model on that path. No network: every tool is mocked.
"""

from __future__ import annotations

import importlib
import json

from atlas.core.agents import debate, specialists
from atlas.core.rag import reranker
from atlas.core.rag import tool_evidence as te
from atlas.core.rag import web_evidence as we
from atlas.core.rag.provenance import TrustTier, trust_for_source
from atlas.core.rag.types import Chunk, RetrievedChunk

WS_MODULE = importlib.import_module("atlas.core.tools.web_search")
MARKET = importlib.import_module("atlas.core.tools.market")
SEC = importlib.import_module("atlas.core.tools.sec")

NEWS = [
    {"title": "Acme lands deal", "url": "https://news.test/a", "content": "Acme signed a deal."},
    {"title": "empty", "url": "https://news.test/b", "content": ""},
]


def test_new_sources_have_the_right_trust_tier():
    assert trust_for_source("sec_edgar") is TrustTier.AUTHORITATIVE
    assert trust_for_source("company_news") is TrustTier.WEB
    assert trust_for_source("stock_data") is TrustTier.WEB


def test_web_evidence_is_enabled_with_only_offline_embed(monkeypatch):
    monkeypatch.delenv("ATLAS_OFFLINE_LLM", raising=False)
    monkeypatch.delenv("ATLAS_OFFLINE_WEB", raising=False)
    monkeypatch.setenv("ATLAS_OFFLINE_EMBED", "1")

    def no_model():  # loading a neural model here would OOM a 512MB host
        raise AssertionError("cross-encoder must not load under ATLAS_OFFLINE_EMBED=1")

    monkeypatch.setattr(reranker, "_get_encoder", no_model)
    monkeypatch.setattr(WS_MODULE, "web_search", lambda q, **k: NEWS[:1])
    assert we.web_offline() is False
    chunks = we.web_evidence("acme robotics")
    assert len(chunks) == 1 and chunks[0].chunk.source == "web_search"


def test_web_evidence_off_when_explicitly_disabled(monkeypatch):
    monkeypatch.delenv("ATLAS_OFFLINE_LLM", raising=False)
    monkeypatch.setenv("ATLAS_OFFLINE_WEB", "1")
    assert we.web_offline() is True


def _online(monkeypatch):
    monkeypatch.setattr(te, "_offline", lambda: False)


def test_news_evidence_is_citable(monkeypatch):
    _online(monkeypatch)
    monkeypatch.setattr(MARKET, "company_news", lambda c, **k: NEWS)
    chunks = te.tool_evidence_for("news_sentiment", target="Acme", ticker="")
    assert len(chunks) == 1  # empty-content hit dropped
    c = chunks[0].chunk
    assert c.source == "company_news" and c.url == "https://news.test/a"
    assert c.citation().endswith("[web]") and "retrieved_at" in c.metadata


def test_quote_evidence_is_one_cited_sentence(monkeypatch):
    _online(monkeypatch)
    monkeypatch.setattr(MARKET, "stock_quote", lambda t: {"ticker": "ACME", "date": "2026-10-27",
                                                          "close": "11", "volume": "1000"})
    chunks = te.tool_evidence_for("market", target="Acme", ticker="ACME")
    assert len(chunks) == 1
    assert chunks[0].chunk.source == "stock_data" and "close 11" in chunks[0].text


def test_sec_evidence_splits_excerpt_into_authoritative_chunks(monkeypatch):
    _online(monkeypatch)
    monkeypatch.setattr(SEC, "sec_filing_excerpt", lambda t, **k: {
        "ticker": "ACME", "title": "Acme 10-K", "url": "https://sec.test/x",
        "excerpt": "Item 1. Business " + "word " * 300})
    chunks = te.tool_evidence_for("fundamentals", target="Acme", ticker="ACME")
    assert 2 <= len(chunks) <= 3
    assert all(c.chunk.source == "sec_edgar" for c in chunks)
    assert chunks[0].chunk.citation() == "Acme 10-K (sec_edgar#0)"  # authoritative: no marker
    assert len({c.chunk.citation() for c in chunks}) == len(chunks)


def test_tools_need_a_ticker_and_are_skipped_offline(monkeypatch):
    called = []
    monkeypatch.setattr(SEC, "sec_filing_excerpt", lambda *a, **k: called.append(1) or {})
    monkeypatch.setattr(MARKET, "stock_quote", lambda *a, **k: called.append(1) or {})
    monkeypatch.setattr(MARKET, "company_news", lambda *a, **k: called.append(1) or [])
    # offline (conftest forces ATLAS_OFFLINE_LLM=1) → no tool calls at all
    for agent in ("fundamentals", "market", "news_sentiment", "risk"):
        assert te.tool_evidence_for(agent, target="Acme", ticker="ACME") == []
    _online(monkeypatch)
    assert te.tool_evidence_for("fundamentals", target="Acme", ticker="") == []
    assert te.tool_evidence_for("risk", target="Acme", ticker="ACME") == []
    assert called == []


# ---------------------------------------------------------------- supervisor


def test_guess_target_extracts_the_company():
    assert specialists.guess_target("Should I invest in Helios Robotics?") == "Helios Robotics"
    assert specialists.guess_target("Evaluate Helios Robotics as a competitor") == \
        "Helios Robotics"
    assert specialists.guess_target("is this any good") == "is this any good"


def test_plan_offline_fallback():
    out = specialists.plan_node({"query": "Should I invest in Helios Robotics?"})
    assert out == {"target": "Helios Robotics", "ticker": "", "plan": specialists.DEFAULT_PLAN}


def test_plan_parses_target_ticker_and_focus(monkeypatch):
    monkeypatch.setattr(specialists, "llm_ready", lambda: True)
    monkeypatch.setattr(specialists, "chat", lambda *a, **k: json.dumps(
        {"target": "Apple Inc.", "ticker": "aapl", "focus_areas": ["iPhone demand", "Services"]}))
    out = specialists.plan_node({"query": "Should I buy Apple?"})
    assert out == {"target": "Apple Inc.", "ticker": "AAPL", "plan": ["iPhone demand", "Services"]}

    monkeypatch.setattr(specialists, "chat", lambda *a, **k: json.dumps(
        {"target": "Helios Robotics", "ticker": "not public", "focus_areas": []}))
    out = specialists.plan_node({"query": "Helios?"})
    assert out["ticker"] == "" and out["plan"] == specialists.DEFAULT_PLAN


def test_plan_degrades_to_default_plan_on_llm_failure(monkeypatch):
    monkeypatch.setattr(specialists, "llm_ready", lambda: True)

    def boom(*a, **k):
        raise RuntimeError("groq down")

    monkeypatch.setattr(specialists, "chat", boom)
    out = specialists.plan_node({"query": "Should I invest in Helios Robotics?"})
    assert out["plan"] == specialists.DEFAULT_PLAN and out["target"] == "Helios Robotics"


# ---------------------------------------------------------------- specialists


def _tool_chunk() -> RetrievedChunk:
    return RetrievedChunk(chunk=Chunk(chunk_id="tool::sec::1", doc_id="sec_ACME",
                                      text="Acme revenue was $10M.", source="sec_edgar",
                                      title="Acme 10-K", ordinal=0), score=0.6)


def test_specialist_cites_merged_tool_evidence_by_index(monkeypatch):
    monkeypatch.setattr(specialists, "llm_ready", lambda: True)
    monkeypatch.setattr(specialists, "tool_evidence_for", lambda *a, **k: [_tool_chunk()])
    seen = {}

    def fake_chat(prompt, **k):
        seen["prompt"] = prompt
        return json.dumps([{"claim": "Revenue was $10M.", "citation_index": 1, "confidence": 0.9},
                           {"claim": "Out of range", "citation_index": 99}])

    monkeypatch.setattr(specialists, "chat", fake_chat)
    out = specialists.fundamentals_node({"query": "Acme?", "target": "Acme", "ticker": "ACME"})
    f0, f1 = out["findings"]
    assert "[1] (Acme 10-K (sec_edgar#0))" in seen["prompt"]  # tool evidence listed first
    assert f0["citation"] == "Acme 10-K (sec_edgar#0)" and f0["evidence_id"] == "tool::sec::1"
    assert f1["citation"] == "n/a"  # an invented index never becomes a citation


def test_specialist_degrades_to_unavailable_finding(monkeypatch):
    monkeypatch.setattr(specialists, "llm_ready", lambda: True)

    def boom(*a, **k):
        raise RuntimeError("groq down")

    monkeypatch.setattr(specialists, "chat", boom)
    out = specialists.risk_node({"query": "Acme?", "target": "Acme"})
    (f,) = out["findings"]
    assert f["agent"] == "risk" and f["confidence"] == 0.0 and f["citation"] == "n/a"
    assert f["unavailable"] is True


def test_debate_degrades_to_neutral_stub(monkeypatch):
    monkeypatch.setattr(debate, "llm_ready", lambda: True)

    def boom(*a, **k):
        raise RuntimeError("groq down")

    monkeypatch.setattr(debate, "chat", boom)
    out = debate.debate_node({"query": "Acme?", "findings": []})
    roles = [d["role"] for d in out["debate"]]
    assert roles == ["bull", "bear", "judge"] and out["debate"][-1]["leaning"] == "neutral"
