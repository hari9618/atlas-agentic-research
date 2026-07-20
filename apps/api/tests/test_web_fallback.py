"""CRAG web-fallback tests (offline, no network).

Regression guard for a real gap: the tools existed but were never wired in, so a
question about an un-ingested company produced no evidence at all instead of
falling back to the web.
"""

from __future__ import annotations

import importlib

from atlas.core.rag import web_evidence as we
from atlas.core.rag.crag import Grade, corrective_retrieve
from atlas.core.rag.ingest import ingest_documents
from atlas.core.rag.types import Document

# `core.tools.__init__` re-exports the function under the same name as its module,
# which shadows the submodule — patch the module object itself, not the dotted path.
WS_MODULE = importlib.import_module("atlas.core.tools.web_search")

FAKE_HITS = [
    {"title": "Northwind Q4 results", "url": "https://news.example/nw-q4",
     "content": "Northwind Robotics reported record quarterly revenue growth of 31%."},
    {"title": "Northwind profile", "url": "https://profile.example/nw",
     "content": "Northwind Robotics builds autonomous warehouse systems in Ohio."},
]


def _index_with(texts: list[str]):
    docs = [Document(doc_id=f"d{i}", text=t, source="t") for i, t in enumerate(texts)]
    return ingest_documents(docs, offline=True)


def test_web_evidence_returns_citable_chunks(monkeypatch):
    monkeypatch.setattr(we, "_offline", lambda: False)
    monkeypatch.setattr(WS_MODULE, "web_search", lambda q, **k: FAKE_HITS)

    chunks = we.web_evidence("northwind robotics")
    assert len(chunks) == 2
    top = chunks[0]
    assert top.chunk.source == "web_search"
    assert top.chunk.url.startswith("https://")
    # Provenance must survive so the grounding guardrail can cite it.
    assert "Northwind" in top.chunk.citation() or "web" in top.chunk.citation()
    assert chunks[0].score > chunks[1].score  # rank decay


def test_web_evidence_is_empty_offline(monkeypatch):
    monkeypatch.setattr(we, "_offline", lambda: True)
    assert we.web_evidence("anything") == []


def test_web_evidence_survives_tool_failure(monkeypatch):
    monkeypatch.setattr(we, "_offline", lambda: False)

    def boom(q, **k):
        raise RuntimeError("tavily down")

    monkeypatch.setattr(WS_MODULE, "web_search", boom)
    assert we.web_evidence("anything") == []  # fail soft, never crash the run


def test_web_fallback_fires_for_an_uningested_company(monkeypatch):
    """The real-world case: the company isn't in the corpus, but shares vocabulary
    with it ("robotics"), so the grade is AMBIGUOUS rather than INCORRECT. Per CRAG,
    ambiguous evidence must be *combined* with web results — firing only on INCORRECT
    left these runs with partial evidence about the wrong company."""
    monkeypatch.setattr(we, "_offline", lambda: False)
    monkeypatch.setattr(WS_MODULE, "web_search", lambda q, **k: FAKE_HITS)

    index = _index_with(["helios robotics warehouse revenue and margins"])
    result = corrective_retrieve(
        index, "northwind robotics quarterly results", top_k=4, web_fallback=we.web_evidence
    )
    assert result.grade is not Grade.CORRECT
    assert result.used_web_fallback
    assert any(c.chunk.source == "web_search" for c in result.chunks)


def test_incorrect_grade_lets_web_evidence_lead(monkeypatch):
    monkeypatch.setattr(we, "_offline", lambda: False)
    monkeypatch.setattr(WS_MODULE, "web_search", lambda q, **k: FAKE_HITS)

    index = _index_with(["barometric pressure readings across alpine weather stations"])
    result = corrective_retrieve(
        index, "northwind robotics quarterly results", top_k=4, web_fallback=we.web_evidence
    )
    assert result.grade is Grade.INCORRECT
    assert result.used_web_fallback
    assert result.chunks[0].chunk.source == "web_search"  # off-topic local is displaced


def test_good_local_evidence_does_not_trigger_web(monkeypatch):
    called = []
    monkeypatch.setattr(we, "_offline", lambda: False)
    monkeypatch.setattr(
        WS_MODULE, "web_search", lambda q, **k: called.append(q) or FAKE_HITS
    )

    index = _index_with(["helios robotics revenue grew strongly with healthy margins"])
    result = corrective_retrieve(
        index, "helios robotics revenue", top_k=4, web_fallback=we.web_evidence
    )
    if result.grade is Grade.CORRECT:
        assert not result.used_web_fallback
        assert called == []  # local corpus is preferred; the web is a last resort


def test_specialists_pass_the_web_fallback():
    """The wiring itself — the gap this suite exists to prevent regressing."""
    import inspect

    from atlas.core.agents import specialists

    src = inspect.getsource(specialists)
    assert "web_fallback=web_evidence" in src
