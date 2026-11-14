"""Repo-root-anchored paths so data/cache resolve no matter the working directory.

The corpus lives at <repo>/data/corpus and the index cache at <repo>/data/cache,
while code runs from apps/api. We locate the repo root by walking up to the
directory that contains both `apps/` and `data/`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache
def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "apps").is_dir() and (parent / "data").is_dir():
            return parent
    # Fallback: three levels up from atlas/ (apps/api/atlas → repo) or cwd.
    return here.parents[3] if len(here.parents) > 3 else Path.cwd()


def data_dir() -> Path:
    return repo_root() / "data"


def corpus_dir() -> Path:
    return data_dir() / "corpus"


def cache_dir() -> Path:
    """Local state (SQLite checkpoints/memory, dev keys). ``ATLAS_CACHE_DIR`` moves it —
    tests point it at a temp dir so they never touch a developer's real data."""
    import os

    override = os.getenv("ATLAS_CACHE_DIR")
    return Path(override) if override else data_dir() / "cache"
