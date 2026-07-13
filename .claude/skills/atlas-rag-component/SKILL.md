---
name: atlas-rag-component
description: >
  Add or change a piece of the Atlas agentic hybrid-RAG pipeline the Atlas way —
  ingestion/chunking, BM25 + bge dense indexing in Qdrant, RRF fusion, bge
  re-ranking, and the CRAG self-correction loop — always returning evidence with
  provenance and re-running the Ragas eval. Use when the rag-engineer touches
  anything under atlas/core/rag. Primarily for the rag-engineer subagent.
---

# Skill: Atlas RAG component

The retrieval contract: **hybrid → fuse → re-rank → CRAG**, returning chunks
**with source metadata** so downstream agents can cite. The engine uses the
**LangChain v0.3** components (pinned) — don't reintroduce hand-rolled BM25/fusion.

## 1. Ingestion (idempotent)
- Chunk docs with `atlas.core.rag.chunking.chunk_document` (deterministic, stable ids
  so re-ingesting never duplicates). Provenance rides in each `Chunk`.
- `HybridIndex.add_chunks()` is idempotent by `chunk_id`.

## 2. Indexes (LangChain)
- **Dense**: `langchain_huggingface.HuggingFaceEmbeddings("BAAI/bge-small-en-v1.5")`
  online / `HashingEmbeddings` offline → `InMemoryVectorStore` (local) or
  `langchain_qdrant.QdrantVectorStore` (prod). Read names/urls from `get_settings()`.
- **Sparse**: `langchain_community.retrievers.BM25Retriever.from_documents(...,
  preprocess_func=lowercasing_tokenizer)`.

## 3. Hybrid fusion (EnsembleRetriever does RRF)
```python
from langchain.retrievers import EnsembleRetriever
ensemble = EnsembleRetriever(retrievers=[bm25, vector_retriever], weights=[0.4, 0.6])
```

## 4. Re-rank (ContextualCompressionRetriever)
```python
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
model = HuggingFaceCrossEncoder(model_name=get_settings().rerank_model)  # bge-reranker-base
reranker = ContextualCompressionRetriever(
    base_compressor=CrossEncoderReranker(model=model, top_n=top_k), base_retriever=ensemble,
)
```
Skip rerank when `ATLAS_OFFLINE_EMBED=1` (no model download in tests/CI).

## 5. CRAG self-correction
- Grade the top context for relevance (LLM or reranker score threshold).
- If **weak/ambiguous**: rewrite the query and re-retrieve, or fall back to the
  `web_search` MCP tool; if **strong**: return as-is.
- Always return `List[RetrievedChunk]` where each chunk carries its provenance.

## 6. Evaluate (don't skip)
- Run the Ragas harness on the golden set. Targets: faithfulness ≥0.9,
  answer relevancy ≥0.85, context precision ≥0.8.
- Report metric deltas vs the previous run; investigate any regression.

## 7. Verify & report
- What changed, current eval numbers vs targets, corpus added/changed.
