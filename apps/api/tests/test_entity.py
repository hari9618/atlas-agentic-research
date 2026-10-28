"""Entity guard tests — web/news evidence must be about the target company.

Regression for a live finding: a "Helios Robotics" run cited Helios Technologies (a
different listed company) and an unrelated "Helios" humanoid robot.
"""

from __future__ import annotations

import importlib

import pytest

from atlas.core.rag import tool_evidence as te
from atlas.core.rag import web_evidence as we
from atlas.core.rag.entity import entity_terms, mentions_entity, normalize_name

WS_MODULE = importlib.import_module("atlas.core.tools.web_search")
MARKET = importlib.import_module("atlas.core.tools.market")

WRONG_COMPANY = [
    {"title": "Helios Technologies Q3 2025 slides: revenue growth returns",
     "url": "https://x.test/hlio", "content": "Helios Technologies raised its outlook."},
    {"title": "ORBIT Robotics unveils Helios four-armed humanoid robot",
     "url": "https://x.test/orbit", "content": "The Helios humanoid is built for space."},
]
RIGHT_COMPANY = [
    {"title": "Helios Robotics signs largest-ever deal", "url": "https://x.test/deal",
     "content": "Helios Robotics will deploy 12,000 robots."},
]


@pytest.mark.parametrize("raw,expected", [
    ("Apple Inc.", "apple"),
    ("Reliance Industries Limited", "reliance industries"),
    ("Microsoft Corporation", "microsoft"),
    ("Acme Co.", "acme"),
    ("Widget Holdings plc", "widget holdings"),     # "Holdings" is part of the name
    ("Helios Robotics", "helios robotics"),         # industry words are never stripped
    ("Helios Technologies, Inc.", "helios technologies"),
    ("The Home Depot, Inc.", "home depot"),
    ("Inc", "inc"),                                  # never strip the whole name
])
def test_only_legal_suffixes_are_stripped(raw, expected):
    assert normalize_name(raw) == expected


def test_same_name_different_company_is_rejected():
    terms = entity_terms("Helios Robotics", "")
    for hit in WRONG_COMPANY:
        assert not mentions_entity(f"{hit['title']}\n{hit['content']}", terms)
    assert mentions_entity("Helios Robotics' software share grew.", terms)


def test_ticker_or_name_match():
    terms = entity_terms("NVIDIA Corporation", "NVDA")
    assert mentions_entity("NVIDIA beat estimates", terms)
    assert mentions_entity("Shares of NVDA rose 4%", terms)
    assert mentions_entity("(NASDAQ: NVDA) closed higher", terms)
    assert not mentions_entity("nvdab is not a ticker", terms)
    assert not mentions_entity("AMD and Intel results", terms)


def test_legal_suffix_target_matches_plain_mentions():
    terms = entity_terms("Reliance Industries Limited", "")
    assert mentions_entity("Reliance Industries said it would expand retail.", terms)
    assert not mentions_entity("Reliance Power said it would expand.", terms)


def test_short_tickers_need_a_ticker_context():
    terms = entity_terms("", "F")
    assert not mentions_entity("Grade F for effort", terms)
    assert mentions_entity("Ford (NYSE: F) rose", terms)
    assert mentions_entity("$F is up today", terms)


def test_no_safe_terms_means_no_filtering():
    assert entity_terms("", "") is None
    assert mentions_entity("anything", None)
    # a whole question echoed as the target is not a name — don't guard on it
    assert entity_terms("should I worry about this company as a competitor next year", "") is None


def test_web_evidence_drops_off_entity_hits(monkeypatch):
    monkeypatch.setattr(we, "_offline", lambda: False)
    monkeypatch.setattr(WS_MODULE, "web_search", lambda q, **k: WRONG_COMPANY + RIGHT_COMPANY)
    chunks = we.web_evidence_about("Helios Robotics")("Helios Robotics competitors")
    assert [c.chunk.title for c in chunks] == ["Helios Robotics signs largest-ever deal"]
    # unscoped calls (no entity) are unchanged
    assert len(we.web_evidence("Helios Robotics competitors")) == 3


def test_news_evidence_drops_off_entity_hits(monkeypatch):
    monkeypatch.setattr(te, "_offline", lambda: False)
    monkeypatch.setattr(MARKET, "company_news", lambda c, **k: WRONG_COMPANY + RIGHT_COMPANY)
    chunks = te.tool_evidence_for("news_sentiment", target="Helios Robotics", ticker="")
    assert [c.chunk.title for c in chunks] == ["Helios Robotics signs largest-ever deal"]
