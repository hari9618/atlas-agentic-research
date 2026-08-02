"""Provenance & temporal tests (offline).

The core reliability invariant: Atlas-generated *derived* evidence must never rank
as, or be cited as, authoritative source evidence — closing the feedback loop where
a wrong earlier output gets retrieved back as if it were a source.
"""

from __future__ import annotations

from atlas.core.guardrails import authoritative_support
from atlas.core.memory.episodic import EpisodicMemory
from atlas.core.memory.summarizer import consolidate
from atlas.core.rag.index import build_index
from atlas.core.rag.ingest import ingest_documents
from atlas.core.rag.provenance import (
    TrustTier,
    is_derived,
    trust_for_source,
    trust_weight,
)
from atlas.core.rag.types import Chunk, Document

# ---- tier classification ----

def test_sources_map_to_the_right_trust_tier():
    assert trust_for_source("sec_edgar") is TrustTier.AUTHORITATIVE
    assert trust_for_source("upload") is TrustTier.AUTHORITATIVE
    assert trust_for_source("news") is TrustTier.AUTHORITATIVE
    assert trust_for_source("web_search") is TrustTier.WEB
    assert trust_for_source("atlas_derived") is TrustTier.DERIVED
    assert trust_for_source("memory") is TrustTier.DERIVED
    # Unknown ingested source defaults to authoritative, not derived.
    assert trust_for_source("some_new_loader") is TrustTier.AUTHORITATIVE


def test_authoritative_outranks_derived_in_weight():
    assert trust_weight("sec_edgar") > trust_weight("web_search") > trust_weight("atlas_derived")


# ---- citation marking ----

def test_authoritative_citation_is_unmarked_but_derived_is_marked():
    auth = Chunk(chunk_id="a", doc_id="d", text="x", source="sec_edgar", title="Helios 10-K")
    derived = Chunk(chunk_id="b", doc_id="e", text="y", source="atlas_derived",
                    title="Memory facts")
    web = Chunk(chunk_id="c", doc_id="f", text="z", source="web_search", title="News")
    assert auth.citation() == "Helios 10-K (sec_edgar#0)"  # byte-identical to before
    assert "[atlas-derived]" in derived.citation()
    assert "[web]" in web.citation()
    assert auth.trust is TrustTier.AUTHORITATIVE and is_derived(derived.source)


# ---- the invariant: derived never outranks authoritative in retrieval ----

def test_derived_evidence_sinks_below_authoritative_in_retrieval():
    # Both chunks are about the same fact and both relevant to the query; the text
    # differs (real derived facts are paraphrases, not byte-identical copies, and the
    # ensemble retriever dedups identical content). Provenance must rank the real
    # source above Atlas's own derived memory.
    docs = [
        Document(doc_id="auth",
                 text="Helios Robotics reported total revenue of 4.2 billion dollars in 2025.",
                 source="sec_edgar", title="Helios 10-K"),
        Document(doc_id="derived",
                 text="Per prior Atlas analysis, Helios revenue was about 4.2 billion in 2025.",
                 source="atlas_derived", title="Atlas memory"),
    ]
    index = ingest_documents(docs, offline=True)
    hits = index.retrieve("Helios Robotics revenue 2025", top_k=2)
    assert len(hits) == 2, "both chunks should retrieve (different text)"
    assert hits[0].chunk.source == "sec_edgar"  # authoritative first
    assert hits[1].chunk.source == "atlas_derived"  # derived sinks below


# ---- guardrail distinguishes authoritative grounding from derived-only ----

def test_authoritative_support_flags_derived_only_grounding():
    report = "Revenue rose [Atlas memory (atlas_derived#0) [atlas-derived]]."
    findings = [{"agent": "fundamentals", "claim": "revenue rose",
                 "citation": "Atlas memory (atlas_derived#0) [atlas-derived]"}]
    s = authoritative_support(report, findings)
    assert s["derived_evidence_used"] is True
    assert s["authoritative_coverage"] == 0.0  # cited, but not by a real source


def test_authoritative_support_counts_real_sources():
    report = "Revenue was 4.2B [Helios 10-K (sec_edgar#0)]."
    findings = [{"agent": "fundamentals", "claim": "revenue 4.2B",
                 "citation": "Helios 10-K (sec_edgar#0)"}]
    s = authoritative_support(report, findings)
    assert s["authoritative_coverage"] == 1.0 and s["derived_evidence_used"] is False


# ---- summarizer tags its output as derived, not a primary source ----

def test_summarizer_writes_derived_not_authoritative(tmp_path):
    mem = EpisodicMemory(db_path=tmp_path / "ep.sqlite", offline=True)
    mem.save("Analyze Helios", "Helios has strong software revenue", 0.7, [])
    index = build_index(offline=True, prefer_qdrant=False)
    consolidate(mem, index, last_n=5)
    derived_chunks = [c for c in index.chunks.values() if c.source == "atlas_derived"]
    assert derived_chunks, "summarizer output should be tagged atlas_derived"
    assert all(is_derived(c.source) for c in derived_chunks)


# ---- Phase 6: temporal metadata ----

def test_corpus_publication_date_is_preserved(tmp_path):
    from atlas.core.rag.loaders import load_corpus_dir

    docs = load_corpus_dir()  # the real sample corpus, which now carries published_at
    dated = [d for d in docs if d.metadata.get("published_at")]
    assert dated, "at least one sample doc should carry a published_at date"


def test_web_evidence_records_retrieval_time(monkeypatch):
    from atlas.core.rag import web_evidence as we

    monkeypatch.setattr(we, "_offline", lambda: False)
    import importlib
    ws = importlib.import_module("atlas.core.tools.web_search")
    monkeypatch.setattr(ws, "web_search", lambda q, **k: [
        {"title": "T", "url": "https://x.example/a", "content": "some web content about a company"},
    ])
    chunks = we.web_evidence("a company")
    assert chunks and chunks[0].chunk.metadata.get("retrieved_at")
