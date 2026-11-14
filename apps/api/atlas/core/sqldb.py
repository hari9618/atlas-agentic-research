"""A tiny SQL adapter: the same statements on Postgres (prod) or SQLite (dev/tests).

The auth tables need real constraints — a unique email, an atomic "claim this refresh
token only if nobody else has" — which a JSON document store can't give. Statements
are written once with ``%s`` placeholders and portable SQL (``ON CONFLICT``,
``RETURNING``); SQLite gets ``?`` placeholders. Rows come back as plain dicts on both.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from .persistence import get_pg_pool, run_ddl


class SqlDb:
    def __init__(self, *, pool: Any = None, path: Path | None = None) -> None:
        if pool is None and path is None:
            raise ValueError("SqlDb needs a Postgres pool or a SQLite path")
        self._pool = pool
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        if pool is None:
            path.parent.mkdir(parents=True, exist_ok=True)
            # One shared connection guarded by a lock: SQLite allows one writer anyway.
            self._conn = sqlite3.connect(str(path), check_same_thread=False,
                                         isolation_level=None)  # autocommit, like the pool
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")

    @property
    def dialect(self) -> str:
        return "postgres" if self._pool is not None else "sqlite"

    @classmethod
    def default(cls, sqlite_path: Path) -> SqlDb:
        """Postgres when ``DATABASE_URL`` is configured and reachable, else SQLite."""
        pool = get_pg_pool()
        return cls(pool=pool) if pool is not None else cls(path=sqlite_path)

    def ddl(self, statements: Iterable[str]) -> None:
        if self._pool is not None:
            run_ddl(self._pool, statements)  # under the cross-process schema lock
            return
        with self._lock:
            for stmt in statements:
                self._conn.execute(stmt)

    def _run(self, sql: str, params: Sequence[Any], fetch: str) -> Any:
        if self._pool is not None:
            with self._pool.connection() as conn:
                cur = conn.execute(sql, params)
                if fetch == "one":
                    return cur.fetchone()
                if fetch == "all":
                    return cur.fetchall()
                return cur.rowcount
        with self._lock:
            cur = self._conn.execute(sql.replace("%s", "?"), tuple(params))
            if fetch == "one":
                row = cur.fetchone()
                return dict(row) if row is not None else None
            if fetch == "all":
                return [dict(r) for r in cur.fetchall()]
            return cur.rowcount

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        """Run a statement; returns the affected row count."""
        return self._run(sql, params, "none")

    def one(self, sql: str, params: Sequence[Any] = ()) -> dict | None:
        row = self._run(sql, params, "one")
        return dict(row) if row is not None else None

    def all(self, sql: str, params: Sequence[Any] = ()) -> list[dict]:
        return [dict(r) for r in self._run(sql, params, "all")]

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
