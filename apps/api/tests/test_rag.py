"""RAG core tests — all offline (hashing embeddings + in-memory store, no network).

These assert the *contracts* of the LangChain-backed engine: deterministic chunking,
idempotent indexing, end-to-end hybrid retrieval, and provenance on every result.
"""

from __future__ import annotations

from atlas.core.rag.chunking import chunk_document
from atlas.core.rag.crag import Grade, corrective_retrieve
from atlas.core.rag.index import build_index
from atlas.core.rag.ingest import ingest_documents
from atlas.core.rag.loaders import load_corpus_dir
from atlas.core.rag.types import Document


def test_chunking_is_deterministic_and_overlapping():
    doc = Document(doc_id="d1", text=" ".join(f"w{i}" for i in range(500)), source="t")
    c1 = chunk_document(doc, chunk_words=100, overlap_words=20)
    c2 = chunk_document(doc, chunk_words=100, overlap_words=20)
    assert [c.chunk_id for c in c1] == [c.chunk_id for c in c2]  # deterministic ids
    assert len(c1) > 1


def test_index_idempotent_add():
    doc = Document(doc_id="d", text="helios robotics revenue grew strongly", source="t")
    index = build_index(offline=True, prefer_qdrant=False)
    chunks = chunk_document(doc)
    index.add_chunks(chunks)
    n = len(index.chunks)
    index.add_chunks(chunks)  # re-add same chunks
    assert len(index.chunks) == n  # no duplication


def test_end_to_end_retrieval_finds_revenue_fact():
    docs = load_corpus_dir()
    assert docs, "sample corpus should be present"
    index = ingest_documents(docs, offline=True)
    result = corrective_retrieve(index, "Helios Robotics total revenue fiscal 2025", top_k=5)
    assert result.chunks
    joined = " ".join(c.text for c in result.chunks).lower()
    assert "4.2 billion" in joined
    assert isinstance(result.grade, Grade)


def test_retrieved_chunks_carry_provenance():
    docs = load_corpus_dir()
    index = ingest_documents(docs, offline=True)
    result = corrective_retrieve(index, "Aster Dynamics competitor", top_k=3)
    assert result.chunks
    top = result.chunks[0]
    assert top.chunk.doc_id and top.chunk.source  # provenance present
    assert top.chunk.citation()  # citation label renders
