"""Embeddings for the semantic half of hybrid search — as LangChain ``Embeddings``.

Default (online): ``HuggingFaceEmbeddings`` (BAAI/bge-small-en-v1.5) — the model the
LangChain docs use. Offline fallback: ``HashingEmbeddings``, a deterministic embedder
so ingestion, tests, and CI run with no model download and no network. Both implement
the LangChain ``Embeddings`` interface, so the vector store never cares which is active.
"""

from __future__ import annotations

import hashlib
import logging
import os

import numpy as np
from langchain_core.embeddings import Embeddings

from ...config import get_settings

log = logging.getLogger("atlas.rag.embeddings")


def _l2_normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


class HashingEmbedder:
    """Deterministic hashing embeddings (offline). Decent for tests, not for prod.

    Uses the hashing trick (token hash → fixed bucket) and L2-normalises, so cosine
    similarity is meaningful and identical inputs always embed identically.
    """

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for tok in text.lower().split():
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                out[i, h % self.dim] += 1.0
        return _l2_normalize(out)


class HashingEmbeddings(Embeddings):
    """LangChain ``Embeddings`` adapter around ``HashingEmbedder`` (offline path)."""

    def __init__(self, dim: int = 384) -> None:
        self._e = HashingEmbedder(dim)
        self.dim = dim

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._e.encode(texts).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self._e.encode([text])[0].tolist()


def get_lc_embeddings(offline: bool = False) -> Embeddings:
    """Return a LangChain Embeddings object.

    ``offline=True`` (or env ATLAS_OFFLINE_EMBED=1) forces the hashing embedder, so
    tests/CI never download the bge model.
    """
    if offline or os.getenv("ATLAS_OFFLINE_EMBED") == "1":
        log.info("Using HashingEmbeddings (offline mode).")
        return HashingEmbeddings()
    try:
        from langchain_huggingface import HuggingFaceEmbeddings

        model = get_settings().embedding_model
        log.info("Loading HuggingFaceEmbeddings %s", model)
        return HuggingFaceEmbeddings(model_name=model)
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("Falling back to HashingEmbeddings (bge unavailable): %s", exc)
        return HashingEmbeddings()
