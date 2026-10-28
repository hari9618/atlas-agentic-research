"""Persistence factory — where Atlas keeps durable state.

One place decides the storage backend so the graph, memory and registry never
hard-code it:

* ``DATABASE_URL`` set  → Postgres (durable across deploys, safe for many workers).
* otherwise             → local SQLite files under ``cache_dir()`` (zero-setup dev/tests).

Why this matters: the LangGraph checkpointer is what lets a run pause for human
review and resume later. On hosts with an ephemeral filesystem (Render's free tier),
SQLite files are wiped on every deploy/restart, so a paused run — and episodic
memory — would silently vanish. Postgres keeps them.

Why a connection *pool*: the graph is compiled once and then driven from a thread
pool (parallel specialists, concurrent requests). A single psycopg connection is not
safe to share across threads; ``psycopg_pool.ConnectionPool`` hands each caller its
own connection, and ``PostgresSaver`` accepts a pool natively.

Why fall back instead of crash: Atlas degrades gracefully everywhere. If Postgres is
configured but unreachable at startup we log a loud warning and keep serving on
SQLite — the app works, it just isn't durable until the database is back and the
process restarts.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import threading
from collections.abc import Iterable, Iterator
from contextlib import contextmanager, suppress
from typing import TYPE_CHECKING, Any

from ..config import get_settings
from ..paths import cache_dir

if TYPE_CHECKING:  # psycopg is only imported when Postgres is actually used
    from psycopg_pool import ConnectionPool

log = logging.getLogger("atlas.persistence")

# Small on purpose: free-tier Postgres (Neon / Supabase / Render) caps connections,
# and one run needs at most ~4 concurrent specialists plus the request thread.
_POOL_MAX_SIZE = 6
# Fail fast on an unreachable host instead of hanging app startup.
_CONNECT_TIMEOUT_S = 10
# Arbitrary constant key for pg_advisory_lock: serializes schema setup across workers.
_SCHEMA_LOCK_KEY = 0x41544C4153  # "ATLAS"

_lock = threading.RLock()
_pool: ConnectionPool | None = None
_pool_attempted = False
_checkpointer: Any = None


# ---------------------------------------------------------------- URL handling
def normalize_database_url(url: str) -> str:
    """Return a libpq-compatible URL.

    Hosts hand out different spellings: Render/Heroku use ``postgres://``, Neon and
    Supabase use ``postgresql://``, and SQLAlchemy-style configs add a driver suffix
    (``postgresql+psycopg://``). Only the scheme is rewritten — host, credentials and
    query params such as ``sslmode=require`` pass through untouched. Key/value DSNs
    (``host=... dbname=...``) have no scheme and are returned as-is.
    """
    url = (url or "").strip()
    scheme, sep, rest = url.partition("://")
    if not sep:
        return url
    base = scheme.lower().split("+", 1)[0]
    if base in {"postgres", "postgresql"}:
        return f"postgresql://{rest}"
    return url


def redact_database_url(url: str) -> str:
    """Hide the password so the URL is safe to log."""
    return re.sub(r"(://[^:/@]+):[^@]*@", r"\1:***@", url or "")


# ---------------------------------------------------------------- Postgres pool
def open_pg_pool(url: str, *, max_size: int = _POOL_MAX_SIZE) -> ConnectionPool:
    """Open a new connection pool and wait until it can actually connect.

    The connection kwargs are what ``PostgresSaver`` requires: ``autocommit`` (its
    setup migrations and writes manage their own transactions), ``prepare_threshold=0``
    and ``dict_row`` (it reads rows by column name). Public so tests can open an
    independent pool to simulate a fresh process.
    """
    import psycopg
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    conninfo = normalize_database_url(url)
    # Probe with one plain connection first: a refused/misspelled host fails in
    # milliseconds with libpq's real error, whereas the pool would keep retrying in the
    # background until its timeout and then raise a vague PoolTimeout.
    psycopg.connect(conninfo, connect_timeout=_CONNECT_TIMEOUT_S).close()

    pool = ConnectionPool(
        conninfo=conninfo,
        min_size=1,
        max_size=max_size,
        open=False,
        name="atlas",
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
            "connect_timeout": _CONNECT_TIMEOUT_S,
        },
        # Serverless Postgres (Neon) drops idle connections when it scales to zero;
        # checking on checkout replaces a dead connection instead of failing a run.
        check=ConnectionPool.check_connection,
    )
    try:
        pool.open(wait=True, timeout=_CONNECT_TIMEOUT_S + 5)
    except Exception:
        pool.close()  # stop the pool's background reconnect workers
        raise
    return pool


@contextmanager
def schema_lock(pool: ConnectionPool) -> Iterator[Any]:
    """Serialize DDL across processes.

    ``CREATE TABLE IF NOT EXISTS`` and the checkpointer's migrations are not safe to
    run concurrently — two workers booting together can collide on the catalog. A
    session-level advisory lock on a dedicated connection makes setup one-at-a-time.
    """
    with pool.connection() as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (_SCHEMA_LOCK_KEY,))
        try:
            yield conn
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (_SCHEMA_LOCK_KEY,))


def run_ddl(pool: ConnectionPool, statements: Iterable[str]) -> None:
    """Create a store's tables/indexes (idempotent) under the schema lock."""
    with schema_lock(pool) as conn:
        for stmt in statements:
            conn.execute(stmt)


def get_pg_pool() -> ConnectionPool | None:
    """The process-wide pool, or ``None`` when Postgres is unconfigured/unreachable.

    Connection is attempted once per process: a dead database should cost one
    timeout at startup, not one per request.
    """
    global _pool, _pool_attempted
    url = get_settings().database_url
    if not url.strip():
        return None
    with _lock:
        if _pool_attempted:
            return _pool
        _pool_attempted = True
        try:
            _pool = open_pg_pool(url)
            log.info("Persistence: Postgres (%s)", redact_database_url(normalize_database_url(url)))
        except Exception as exc:
            _pool = None
            log.warning(
                "DATABASE_URL is set but Postgres is unreachable (%s: %s) — falling back to "
                "local SQLite/JSON. Paused runs and memory will NOT survive a restart.",
                type(exc).__name__, exc,
            )
        return _pool


def using_postgres() -> bool:
    """True when durable state is going to Postgres (useful for /health/ready)."""
    return get_pg_pool() is not None


# ---------------------------------------------------------------- checkpointer
def postgres_saver(pool: ConnectionPool):
    """Build a ``PostgresSaver`` on ``pool`` and run its (idempotent) migrations."""
    from langgraph.checkpoint.postgres import PostgresSaver

    saver = PostgresSaver(pool)
    with schema_lock(pool):
        saver.setup()
    return saver


def _sqlite_saver():
    db = cache_dir() / "atlas_checkpoints.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    from langgraph.checkpoint.sqlite import SqliteSaver

    # check_same_thread=False: the compiled graph is used from worker threads;
    # SqliteSaver serializes access with its own lock.
    conn = sqlite3.connect(str(db), check_same_thread=False)
    saver = SqliteSaver(conn)
    try:
        saver.setup()  # create checkpoint tables if missing
    except Exception as exc:  # pragma: no cover
        log.warning("SqliteSaver.setup() failed (%s); continuing.", exc)
    log.info("Checkpointer: SQLite (%s)", db)
    return saver


def get_checkpointer():
    """Return the process-wide LangGraph checkpointer for the configured backend."""
    global _checkpointer
    with _lock:
        if _checkpointer is not None:
            return _checkpointer
        pool = get_pg_pool()
        if pool is not None:
            try:
                _checkpointer = postgres_saver(pool)
                log.info("Checkpointer: Postgres")
                return _checkpointer
            except Exception as exc:
                log.warning("PostgresSaver setup failed (%s) — falling back to SQLite.", exc)
        _checkpointer = _sqlite_saver()
        return _checkpointer


def reset_persistence() -> None:
    """Close the pool and forget cached backends (tests, and clean shutdown)."""
    global _pool, _pool_attempted, _checkpointer
    with _lock:
        if _pool is not None:
            with suppress(Exception):
                _pool.close()
        _pool, _pool_attempted, _checkpointer = None, False, None
