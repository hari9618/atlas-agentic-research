"""Atlas agentic hybrid-RAG layer.

Public surface:
    build_index / HybridIndex   — build & query the hybrid index
    corrective_retrieve         — CRAG self-correcting retrieval
    RetrievedChunk, Chunk, Document — typed, provenance-carrying data
"""

from .crag import CragResult, Grade, corrective_retrieve
from .index import HybridIndex, build_index
from .ingest import ingest_documents
from .types import Chunk, Document, RetrievedChunk

__all__ = [
    "HybridIndex",
    "build_index",
    "ingest_documents",
    "corrective_retrieve",
    "CragResult",
    "Grade",
    "Chunk",
    "Document",
    "RetrievedChunk",
]
