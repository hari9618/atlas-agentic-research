"""Persistence factory — URL normalization and the SQLite fallback (no Postgres needed)."""

from __future__ import annotations

import pytest

from atlas.config import get_settings
from atlas.core import persistence
from atlas.core.llmops.registry import PromptRegistry
from atlas.core.memory.episodic import EpisodicMemory


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """Fresh settings + persistence singletons, with every default file under tmp_path."""
    import atlas.core.llmops.registry as registry_mod
    import atlas.core.memory.episodic as episodic_mod

    for mod in (persistence, episodic_mod, registry_mod):
        monkeypatch.setattr(mod, "cache_dir", lambda: tmp_path)
    get_settings.cache_clear()
    persistence.reset_persistence()
    yield monkeypatch
    persistence.reset_persistence()
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Render / Heroku spelling
        ("postgres://u:p@host:5432/db", "postgresql://u:p@host:5432/db"),
        # Neon / Supabase spelling, sslmode must survive
        ("postgresql://u:p@ep-x.neon.tech/db?sslmode=require",
         "postgresql://u:p@ep-x.neon.tech/db?sslmode=require"),
        # SQLAlchemy driver suffix
        ("postgresql+psycopg://u:p@h/db?sslmode=require&channel_binding=require",
         "postgresql://u:p@h/db?sslmode=require&channel_binding=require"),
        ("POSTGRES://u:p@h/db", "postgresql://u:p@h/db"),
        ("  postgresql://u@h/db  ", "postgresql://u@h/db"),
        # key/value DSN passes through untouched
        ("host=h dbname=db sslmode=require", "host=h dbname=db sslmode=require"),
        ("", ""),
    ],
)
def test_normalize_database_url(raw, expected):
    assert persistence.normalize_database_url(raw) == expected


def test_redact_hides_password():
    red = persistence.redact_database_url("postgresql://user:s3cret@h:5432/db?sslmode=require")
    assert "s3cret" not in red and red.startswith("postgresql://user:***@h")


def test_no_database_url_means_sqlite(isolated):
    from langgraph.checkpoint.sqlite import SqliteSaver

    assert persistence.get_pg_pool() is None
    assert not persistence.using_postgres()
    saver = persistence.get_checkpointer()
    assert isinstance(saver, SqliteSaver)
    assert persistence.get_checkpointer() is saver  # process singleton
    assert EpisodicMemory(offline=True).backend == "sqlite"
    assert PromptRegistry().backend == "json"


def test_unreachable_postgres_falls_back_to_sqlite(isolated, caplog):
    """Configured-but-down Postgres must degrade, not crash, and say so loudly."""
    from langgraph.checkpoint.sqlite import SqliteSaver

    # Port 1 on loopback refuses immediately, so this stays fast.
    isolated.setenv("DATABASE_URL", "postgres://atlas:pw@127.0.0.1:1/atlas")
    get_settings.cache_clear()

    with caplog.at_level("WARNING", logger="atlas.persistence"):
        assert persistence.get_pg_pool() is None
    assert any("falling back" in r.message for r in caplog.records)
    assert all("pw@" not in r.getMessage() for r in caplog.records)  # no password leak

    assert isinstance(persistence.get_checkpointer(), SqliteSaver)
    mem = EpisodicMemory(offline=True)
    assert mem.backend == "sqlite"
    mem.save("Analyze Helios", "r", 0.7, [])
    assert mem.count() == 1
    assert PromptRegistry().backend == "json"


def test_explicit_paths_always_use_sqlite_and_json(isolated, tmp_path):
    # Even with DATABASE_URL set, an explicit path is a deliberate local store.
    isolated.setenv("DATABASE_URL", "postgresql://atlas:pw@127.0.0.1:1/atlas")
    get_settings.cache_clear()
    assert EpisodicMemory(db_path=tmp_path / "e.sqlite", offline=True).backend == "sqlite"
    assert PromptRegistry(path=tmp_path / "r.json").backend == "json"
