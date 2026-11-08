"""Process-wide resources shared by graph nodes, routers and the eval harness.

Built lazily (the index embeds the whole corpus) and cached. Kept out of graph.py so
agents and routers can depend on them without importing the graph — which removes
the circular imports that previously needed late ``from ..graph import`` calls.
"""

from __future__ import annotations

import logging
import os

from .memory.episodic import EpisodicMemory
from .rag.index import HybridIndex
from .rag.ingest import ingest_documents
from .rag.loaders import load_corpus_dir

log = logging.getLogger("atlas.resources")

_index: HybridIndex | None = None
_episodic: EpisodicMemory | None = None


def _offline_embed() -> bool:
    return os.getenv("ATLAS_OFFLINE_EMBED") == "1"


def get_index() -> HybridIndex:
    """The hybrid (BM25 + dense) research index over the corpus."""
    global _index
    if _index is None:
        docs = load_corpus_dir()
        _index = ingest_documents(docs, offline=_offline_embed())
        log.info("Built research index: %d docs, %d chunks", len(docs), len(_index.chunks))
    return _index


def get_episodic() -> EpisodicMemory:
    """Episodic memory: past runs, recalled into new ones."""
    global _episodic
    if _episodic is None:
        _episodic = EpisodicMemory(offline=_offline_embed())
    return _episodic


def reset_resources() -> None:
    """Forget cached resources so they rebuild under the current settings (tests)."""
    global _index, _episodic
    _index, _episodic = None, None
