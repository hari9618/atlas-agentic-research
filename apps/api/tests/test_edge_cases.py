"""Adversarial edge-case + error-path tests (offline).

These try to break Atlas: empty inputs, no-match queries, missing keys, duplicate
ingest, unicode, and oversized docs. They assert the *contracts* — graceful
degradation where promised, and the right error where failure is expected.
"""

from __future__ import annotations

import pytest

from atlas.config import get_settings
from atlas.core.rag.chunking import chunk_document
from atlas.core.rag.crag import Grade, corrective_retrieve
from atlas.core.rag.index import build_index
from atlas.core.rag.ingest import ingest_documents
from atlas.core.rag.types import Document


def _index_with(texts: list[str]):
    docs = [Document(doc_id=f"d{i}", text=t, source="t") for i, t in enumerate(texts)]
    return ingest_documents(docs, offline=True)


def test_empty_corpus_returns_no_results():
    index = build_index(offline=True, prefer_qdrant=False)
    result = corrective_retrieve(index, "anything at all", top_k=5)
    assert result.chunks == []
    assert result.grade is Grade.INCORRECT


def test_empty_query_does_not_crash():
    index = _index_with(["helios robotics revenue grew strongly this year"])
    result = corrective_retrieve(index, "   ", top_k=5)
    assert isinstance(result.chunks, list)  # no exception, sensible empty/low result


def test_query_with_no_overlap_is_graceful():
    index = _index_with(["warehouse robots and fleet software"])
    result = corrective_retrieve(index, "zzzz qqqq xxxx nonexistent token", top_k=3)
    assert isinstance(result.chunks, list)
    assert isinstance(result.grade, Grade)


def test_get_llm_without_key_raises():
    if get_settings().llm_configured:
        pytest.skip("GROQ_API_KEY is configured in this environment")
    from atlas.llm import get_llm

    get_llm.cache_clear()  # avoid a cached client from another test
    with pytest.raises(RuntimeError):
        get_llm()


def test_duplicate_ingest_is_idempotent():
    docs = [Document(doc_id="d", text="alpha beta gamma delta epsilon", source="t")]
    index = ingest_documents(docs, offline=True)
    n = len(index.chunks)
    index.add_chunks(chunk_document(docs[0]))  # re-add identical content
    assert len(index.chunks) == n


def test_unicode_document_ingests_and_retrieves():
    index = _index_with(["Société Générale rapport annuel — chiffre d'affaires en hausse 株式会社"])
    result = corrective_retrieve(index, "chiffre d'affaires", top_k=3)
    assert isinstance(result.chunks, list)  # no UnicodeError anywhere in the path


def test_long_document_produces_multiple_chunks():
    doc = Document(doc_id="long", text=" ".join(f"token{i}" for i in range(2000)), source="t")
    chunks = chunk_document(doc, chunk_words=200, overlap_words=40)
    assert len(chunks) > 5


def test_extract_json_prefers_outer_object_over_inner_array():
    # Regression: an object that CONTAINS an array must not be mis-parsed as the array.
    from atlas.core.agents.base import extract_json

    obj = extract_json('{"confidence": 0.7, "uncertainties": ["a", "b"]}', default={})
    assert isinstance(obj, dict) and obj["confidence"] == 0.7
    arr = extract_json('[{"claim": "x", "citation_index": 1}]', default=[])
    assert isinstance(arr, list) and arr[0]["claim"] == "x"
