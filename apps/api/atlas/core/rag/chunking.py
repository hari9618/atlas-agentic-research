"""Token-ish chunking with overlap.

We approximate tokens with whitespace words (good enough for retrieval chunking
and dependency-free). Chunks overlap so a fact that straddles a boundary still
lands wholly inside at least one chunk.
"""

from __future__ import annotations

import hashlib

from .types import Chunk, Document


def _stable_id(*parts: str) -> str:
    """Deterministic id so re-ingesting the same content never duplicates."""
    h = hashlib.sha1("\x00".join(parts).encode("utf-8")).hexdigest()
    return h[:16]


def chunk_document(
    doc: Document,
    *,
    chunk_words: int = 220,
    overlap_words: int = 40,
) -> list[Chunk]:
    """Split a document into overlapping word-windows."""
    words = doc.text.split()
    if not words:
        return []

    step = max(1, chunk_words - overlap_words)
    chunks: list[Chunk] = []
    ordinal = 0
    for start in range(0, len(words), step):
        window = words[start : start + chunk_words]
        if not window:
            break
        text = " ".join(window)
        chunk_id = _stable_id(doc.doc_id, str(ordinal), text[:64])
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                doc_id=doc.doc_id,
                text=text,
                source=doc.source,
                title=doc.title,
                url=doc.url,
                ordinal=ordinal,
                metadata=dict(doc.metadata),
            )
        )
        ordinal += 1
        if start + chunk_words >= len(words):
            break
    return chunks
