"""Regression tests for two grounding bugs found on a live Reliance Industries run.

1. The guardrail scored a fully cited report at 0% coverage because the writer cited
   with the compact key ``[company_news#1]`` instead of the full label — slashing
   confidence (and the Langfuse faithfulness score) for every web-sourced company.
2. CRAG handed a Reliance analyst the demo corpus's Helios chunks: they share
   vocabulary ("revenue", "customers") with the query, so they graded as relevant and
   the web search was skipped or diluted.
"""

from __future__ import annotations

from atlas.core.guardrails import citation_coverage
from atlas.core.rag import crag
from atlas.core.rag.entity import entity_terms
from atlas.core.rag.index import build_index
from atlas.core.rag.types import Chunk, RetrievedChunk


# ---------------------------------------------------------------- guardrail
def test_compact_citation_keys_count_as_cited():
    findings = [
        {"citation": "Reliance Q1 results beat estimates (company_news#1) [web]"},
        {"citation": "RELIANCE.NS daily quote (Yahoo Finance) (stock_data#0) [web]"},
    ]
    report = "Revenue rose 25% [company_news#1]. The stock sits near its lows [stock_data#0]."
    assert citation_coverage(report, findings) == 1.0


def test_citation_key_match_is_exact():
    findings = [{"citation": "Some article (company_news#1) [web]"}]
    assert citation_coverage("as reported [company_news#10]", findings) == 0.0
    assert citation_coverage("as reported [xcompany_news#1]", findings) == 0.0


def test_full_labels_still_count():
    findings = [{"citation": "Helios Robotics Inc. 10-K (FY2025) (sec_edgar#0)"}]
    report = "Revenue was $4.2B [Helios Robotics Inc. 10-K (FY2025) (sec_edgar#0)]."
    assert citation_coverage(report, findings) == 1.0


# ---------------------------------------------------------------- entity-aware CRAG
def _index(*docs):
    idx = build_index(offline=True, prefer_qdrant=False)
    idx.add_chunks([
        Chunk(chunk_id=f"c{i}", doc_id=f"d{i}", text=text, source="research", title=title,
              url="", ordinal=0)
        for i, (title, text) in enumerate(docs)
    ])
    return idx


def _web(text):
    return RetrievedChunk(chunk=Chunk(chunk_id="w0", doc_id="web_0", text=text,
                                      source="web_search", title="web result", url="", ordinal=0),
                          score=0.5)


def test_uncovered_company_goes_straight_to_the_web(monkeypatch):
    idx = _index(("Helios Robotics 10-K", "Helios Robotics revenue grew 28%. Its business "
                  "model, products and customers are described here, with margins and growth."))
    graded = []
    monkeypatch.setattr(crag, "_llm_grade", lambda *a: graded.append(1) or None)
    web = _web("Reliance Industries posted quarterly revenue of Rs 3.4 lakh crore.")
    res = crag.corrective_retrieve(
        idx, "Reliance Industries business model products customers revenue growth margins",
        top_k=4, web_fallback=lambda q: [web], entity=entity_terms("Reliance Industries Limited"))
    assert res.used_web_fallback and res.grade is crag.Grade.INCORRECT
    assert [c.chunk.source for c in res.chunks] == ["web_search"]  # no Helios evidence
    assert graded == []  # no LLM grading call wasted on irrelevant local chunks


def test_uncovered_company_without_web_returns_nothing_not_wrong_company():
    idx = _index(("Helios Robotics 10-K", "Helios Robotics revenue and customers."))
    res = crag.corrective_retrieve(idx, "Reliance Industries revenue customers", top_k=4,
                                   web_fallback=lambda q: [],
                                   entity=entity_terms("Reliance Industries"))
    assert res.chunks == [] and not res.used_web_fallback


def test_covered_company_keeps_its_local_documents():
    # A competitor profile that only says "Helios" must still be usable for Helios
    # research — coverage is decided at corpus level, not per retrieved chunk.
    idx = _index(("Helios Robotics 10-K", "Helios Robotics revenue grew 28% on robot demand."),
                 ("Aster Dynamics profile", "Aster Dynamics competes with Helios on software."))
    res = crag.corrective_retrieve(idx, "Helios Robotics competitors software", top_k=4,
                                   web_fallback=lambda q: [],
                                   entity=entity_terms("Helios Robotics"))
    assert res.chunks and all(c.chunk.source == "research" for c in res.chunks)
    assert {c.chunk.title for c in res.chunks} >= {"Aster Dynamics profile"}


def test_no_entity_keeps_the_original_behaviour():
    idx = _index(("Helios Robotics 10-K", "Helios Robotics revenue grew 28%."))
    res = crag.corrective_retrieve(idx, "Helios Robotics revenue", top_k=4)
    assert res.chunks and res.chunks[0].chunk.source == "research"
