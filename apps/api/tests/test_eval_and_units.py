"""Unit tests for the eval harness + small utilities (all offline, deterministic)."""

from __future__ import annotations

import numpy as np

from atlas.core.rag.embeddings import HashingEmbedder
from atlas.core.rag.ingest import ingest_documents
from atlas.core.rag.loaders.files import _parse_frontmatter, load_corpus_dir
from atlas.core.rag.loaders.sec_edgar import _strip_html
from atlas.core.rag.types import Document
from atlas.eval.langfuse_scores import derive_scores
from atlas.eval.retrieval_eval import run as retrieval_run


def test_retrieval_eval_runs_offline_over_golden_set():
    out = retrieval_run(top_k=5, offline=True)
    s = out["summary"]
    assert s["n"] == 5
    assert 0.0 <= s["hit_rate@k"] <= 1.0
    assert s["hit_rate@k"] >= 0.8  # hybrid retrieval should find most relevant docs
    assert len(out["rows"]) == 5


def test_derive_scores_adds_hallucination_and_alerts():
    metrics = {
        "ragas_faithfulness": 0.80,   # below 0.90 -> alert
        "ragas_answer_relevancy": 0.90,  # ok
        "ragas_context_precision": 0.70,  # below 0.80 -> alert
    }
    out = derive_scores(metrics)
    assert out["ragas_hallucination"] == 0.20
    assert out["ragas_alert_count"] == 2.0


def test_hashing_embedder_is_deterministic_and_normalised():
    emb = HashingEmbedder(dim=128)
    a = emb.encode(["helios robotics revenue", "helios robotics revenue"])
    assert a.shape == (2, 128)
    assert np.allclose(a[0], a[1])  # identical text -> identical vector
    assert np.isclose(np.linalg.norm(a[0]), 1.0, atol=1e-5)  # L2 normalised


def test_hybrid_index_save_load_roundtrip(tmp_path):
    from atlas.core.rag.index import HybridIndex

    docs = [Document(doc_id="d1", text="helios robotics fleet software revenue", source="t")]
    index = ingest_documents(docs, offline=True)
    base = tmp_path / "idx"
    index.save(base)

    restored = HybridIndex.load(base, offline=True)
    assert len(restored.chunks) == len(index.chunks)
    res = restored.retrieve("fleet software", top_k=1)
    assert res and res[0].chunk.doc_id == "d1"


def test_strip_html_removes_tags():
    assert _strip_html("<p>Hello <b>World</b></p>") == "Hello World"


def test_parse_frontmatter_extracts_metadata():
    raw = "---\ntitle: Acme 10-K\nsource: sec_edgar\n---\nbody text here"
    meta, body = _parse_frontmatter(raw)
    assert meta["title"] == "Acme 10-K"
    assert meta["source"] == "sec_edgar"
    assert body == "body text here"


def test_load_corpus_dir_reads_sample_corpus():
    docs = load_corpus_dir()  # repo-anchored data/corpus
    ids = {d.doc_id for d in docs}
    assert "helios_10k_fy2025" in ids
    assert all(d.title and d.source for d in docs)  # provenance present
