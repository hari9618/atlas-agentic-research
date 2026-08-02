"""Core data types for the Atlas RAG layer.

The contract every retriever honours: chunks always travel **with their
provenance** (source, title, locator) so downstream agents can cite. A bare
string is never returned from retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .provenance import TrustTier, citation_marker, trust_for_source


@dataclass
class Document:
    """A source document before chunking."""

    doc_id: str
    text: str
    source: str  # e.g. "sec_edgar", "news", "upload"
    title: str = ""
    url: str = ""  # or file path
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    """A retrievable unit, carrying enough provenance to cite it."""

    chunk_id: str
    doc_id: str
    text: str
    source: str
    title: str = ""
    url: str = ""
    ordinal: int = 0  # position within the document
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def trust(self) -> TrustTier:
        """Trust tier derived from the source (authoritative / web / derived)."""
        return trust_for_source(self.source)

    def citation(self) -> str:
        """A short human-readable citation label.

        Authoritative citations are unmarked; web and Atlas-derived citations carry a
        visible suffix so they can never be mistaken for primary source evidence.
        """
        label = self.title or self.doc_id
        base = f"{label} ({self.source}#{self.ordinal})"
        marker = citation_marker(self.source)
        return f"{base} {marker}" if marker else base


@dataclass
class RetrievedChunk:
    """A chunk plus the scores that surfaced it. Provenance rides along in `chunk`."""

    chunk: Chunk
    score: float  # final (post-rerank or fused) score
    dense_rank: int | None = None
    sparse_rank: int | None = None
    rerank_score: float | None = None

    @property
    def text(self) -> str:
        return self.chunk.text

    def as_evidence(self) -> dict[str, Any]:
        """Compact, citation-ready view for agents / report grounding."""
        return {
            "chunk_id": self.chunk.chunk_id,
            "doc_id": self.chunk.doc_id,
            "source": self.chunk.source,
            "title": self.chunk.title,
            "url": self.chunk.url,
            "citation": self.chunk.citation(),
            "score": round(self.score, 4),
            "text": self.chunk.text,
        }
