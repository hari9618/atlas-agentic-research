"""HybridIndex — hybrid retrieval built on LangChain v0.3 components.

Pipeline (the LangChain-idiomatic stack):
    BM25Retriever (sparse) + vector retriever (dense)
        → EnsembleRetriever  (Reciprocal Rank Fusion)
        → ContextualCompressionRetriever + CrossEncoderReranker (precision stage)

The dense store is LangChain's ``InMemoryVectorStore`` locally (offline, zero infra)
or ``QdrantVectorStore`` in production. Atlas keeps a stable surface — ``retrieve()``
returns ``RetrievedChunk``s that always carry provenance — so the agents and eval don't
care that the engine underneath is LangChain.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from langchain.retrievers import ContextualCompressionRetriever, EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document as LCDocument
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore

from ...config import get_settings
from ...paths import cache_dir
from .embeddings import get_lc_embeddings
from .types import Chunk, RetrievedChunk

log = logging.getLogger("atlas.rag.index")

DEFAULT_CACHE = cache_dir() / "atlas_index"
_TOKEN = re.compile(r"[a-z0-9]+")


def _preprocess(text: str) -> list[str]:
    """Lowercasing tokenizer for BM25 (the default split() doesn't lowercase)."""
    return _TOKEN.findall(text.lower())


def _chunk_to_lcdoc(c: Chunk) -> LCDocument:
    return LCDocument(
        page_content=c.text,
        metadata={
            "chunk_id": c.chunk_id,
            "doc_id": c.doc_id,
            "source": c.source,
            "title": c.title,
            "url": c.url,
            "ordinal": c.ordinal,
        },
    )


class HybridIndex:
    def __init__(self, embeddings: Embeddings, prefer_qdrant: bool = True) -> None:
        self.embeddings = embeddings
        self.prefer_qdrant = prefer_qdrant
        self.chunks: dict[str, Chunk] = {}
        self._lcdocs: list[LCDocument] = []
        self._vectorstore = None
        self._bm25 = None
        self._dirty = True

    # ---- build ----
    def add_chunks(self, chunks: list[Chunk]) -> None:
        new = [c for c in chunks if c.chunk_id not in self.chunks]  # idempotent
        if not new:
            return
        for c in new:
            self.chunks[c.chunk_id] = c
            self._lcdocs.append(_chunk_to_lcdoc(c))
        self._dirty = True
        log.info("Indexed %d new chunks (total %d).", len(new), len(self.chunks))

    def _build_vectorstore(self):
        if self.prefer_qdrant:
            try:
                import qdrant_client  # noqa: F401
                from langchain_qdrant import QdrantVectorStore

                settings = get_settings()
                vs = QdrantVectorStore.from_documents(
                    self._lcdocs,
                    embedding=self.embeddings,
                    url=settings.qdrant_url,
                    collection_name=settings.qdrant_collection,
                )
                log.info("Using QdrantVectorStore (%s).", settings.qdrant_url)
                return vs
            except Exception as exc:
                log.info("Qdrant unavailable (%s) — using InMemoryVectorStore.", exc)
        return InMemoryVectorStore.from_documents(self._lcdocs, self.embeddings)

    def _ensure_backends(self):
        """Build & cache the vector store + BM25 retriever; rebuild only when docs change."""
        if self._vectorstore is None or self._bm25 is None or self._dirty:
            self._vectorstore = self._build_vectorstore()
            self._bm25 = BM25Retriever.from_documents(self._lcdocs, preprocess_func=_preprocess)
            self._dirty = False
        return self._vectorstore, self._bm25

    def _build_retriever(self, top_k: int, candidate_k: int, rerank: bool):
        vectorstore, bm25 = self._ensure_backends()
        vector_retriever = vectorstore.as_retriever(search_kwargs={"k": candidate_k})
        bm25.k = candidate_k  # cheap per-call tweak; the index itself is cached
        # EnsembleRetriever fuses the two ranked lists via Reciprocal Rank Fusion.
        ensemble = EnsembleRetriever(
            retrievers=[bm25, vector_retriever], weights=[0.4, 0.6]
        )
        if rerank and os.getenv("ATLAS_OFFLINE_EMBED") != "1":
            try:
                from langchain.retrievers.document_compressors import CrossEncoderReranker
                from langchain_community.cross_encoders import HuggingFaceCrossEncoder

                model = HuggingFaceCrossEncoder(model_name=get_settings().rerank_model)
                compressor = CrossEncoderReranker(model=model, top_n=top_k)
                return ContextualCompressionRetriever(
                    base_compressor=compressor, base_retriever=ensemble
                )
            except Exception as exc:
                log.warning("Reranker unavailable (%s) — using fused order.", exc)
        return ensemble

    # ---- retrieve ----
    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        candidate_k: int = 20,
        rerank: bool = True,
    ) -> list[RetrievedChunk]:
        if not self.chunks:
            return []
        # A blank/whitespace query has nothing to match and produces a zero
        # embedding vector — newer langchain-core raises on that in the in-memory
        # store's cosine path, so short-circuit here (contract: return no results).
        if not query or not query.strip():
            return []
        retriever = self._build_retriever(top_k, candidate_k, rerank)
        docs = retriever.invoke(query)

        results: list[RetrievedChunk] = []
        seen: set[str] = set()
        for rank, d in enumerate(docs):
            cid = d.metadata.get("chunk_id", "")
            if cid in seen:
                continue
            seen.add(cid)
            chunk = self.chunks.get(cid) or Chunk(
                chunk_id=cid,
                doc_id=d.metadata.get("doc_id", ""),
                text=d.page_content,
                source=d.metadata.get("source", ""),
                title=d.metadata.get("title", ""),
                url=d.metadata.get("url", ""),
                ordinal=d.metadata.get("ordinal", 0),
            )
            score = float(d.metadata.get("relevance_score", 1.0 / (rank + 1)))
            results.append(RetrievedChunk(chunk=chunk, score=score))
            if len(results) >= top_k:
                break
        return results

    # ---- persistence (store the chunks; retrievers rebuild on load) ----
    def save(self, base: Path = DEFAULT_CACHE) -> None:
        base.parent.mkdir(parents=True, exist_ok=True)
        payload = {"chunks": {cid: c.__dict__ for cid, c in self.chunks.items()}}
        base.with_suffix(".json").write_text(json.dumps(payload), encoding="utf-8")
        log.info("Saved index (%d chunks) → %s.json", len(self.chunks), base)

    @classmethod
    def load(cls, base: Path = DEFAULT_CACHE, offline: bool = False) -> "HybridIndex":
        idx = build_index(offline=offline)
        payload = json.loads(base.with_suffix(".json").read_text(encoding="utf-8"))
        idx.add_chunks([Chunk(**c) for c in payload["chunks"].values()])
        log.info("Loaded index (%d chunks) from %s.json", len(idx.chunks), base)
        return idx


def build_index(offline: bool = False, prefer_qdrant: bool = True) -> HybridIndex:
    """Fresh empty index with the configured LangChain embeddings + vector store."""
    return HybridIndex(get_lc_embeddings(offline=offline), prefer_qdrant=prefer_qdrant)
