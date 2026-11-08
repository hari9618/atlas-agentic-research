"""Durable JSON documents for the learning loop: policies, run records, experiments.

One small abstraction instead of three bespoke stores. Each document has a ``kind``
(e.g. ``"run"``), an ``id`` and a JSON body. Postgres (one table, JSONB) when
``DATABASE_URL`` is reachable, so learned policies and the run history survive
redeploys on ephemeral hosts; otherwise one JSON file per kind under
``data/cache/llmops`` (or ``$ATLAS_LLMOPS_DIR``). An explicit ``root`` always means
JSON (tests).
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ...paths import cache_dir
from ..persistence import get_pg_pool, run_ddl

log = logging.getLogger("atlas.llmops.store")

_DDL = (
    """CREATE TABLE IF NOT EXISTS atlas_llmops_documents (
        kind TEXT NOT NULL,
        id TEXT NOT NULL,
        data JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (kind, id)
    )""",
    "CREATE INDEX IF NOT EXISTS atlas_llmops_documents_recent "
    "ON atlas_llmops_documents (kind, created_at DESC)",
)


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class DocumentStore:
    """Upsert / get / list-newest-first for one ``kind`` of document."""

    def __init__(self, kind: str, *, root: Path | None = None, pool: Any = None,
                 keep: int | None = None) -> None:
        self.kind = kind
        self.keep = keep  # JSON backend: retain only the newest ``keep`` documents
        default_root = Path(os.getenv("ATLAS_LLMOPS_DIR") or cache_dir() / "llmops")
        self._path = (root or default_root) / f"{kind}.json"
        self._lock = threading.Lock()
        if pool is None and root is None:
            pool = get_pg_pool()
        self._pool = pool
        if self._pool is not None:
            try:
                run_ddl(self._pool, _DDL)
            except Exception as exc:
                log.warning("Postgres %s store unavailable (%s) — using JSON.", kind, exc)
                self._pool = None

    @property
    def backend(self) -> str:
        return "postgres" if self._pool is not None else "json"

    # ---- JSON backend helpers
    def _read(self) -> list[dict]:
        if not self._path.exists():
            return []
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Unreadable %s store (%s) — starting empty.", self._path, exc)
            return []

    def _write(self, docs: list[dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(docs, indent=1, default=str), encoding="utf-8")
        tmp.replace(self._path)

    # ---- API
    def put(self, doc_id: str, data: dict) -> None:
        """Insert or replace a document. ``data["created_at"]`` is set if missing."""
        data = {**data, "id": doc_id}
        data.setdefault("created_at", now_iso())
        if self._pool is not None:
            from psycopg.types.json import Jsonb

            with self._pool.connection() as conn:
                conn.execute(
                    "INSERT INTO atlas_llmops_documents (kind, id, data, created_at) "
                    "VALUES (%s, %s, %s, %s) ON CONFLICT (kind, id) "
                    "DO UPDATE SET data = EXCLUDED.data",
                    (self.kind, doc_id, Jsonb(data), data["created_at"]),
                )
            return
        with self._lock:
            docs = [d for d in self._read() if d.get("id") != doc_id] + [data]
            docs.sort(key=lambda d: d.get("created_at", ""))
            if self.keep:
                docs = docs[-self.keep:]
            self._write(docs)

    def get(self, doc_id: str) -> dict | None:
        if self._pool is not None:
            with self._pool.connection() as conn:
                row = conn.execute(
                    "SELECT data FROM atlas_llmops_documents WHERE kind = %s AND id = %s",
                    (self.kind, doc_id),
                ).fetchone()
            return row["data"] if row else None
        return next((d for d in self._read() if d.get("id") == doc_id), None)

    def list(self, limit: int = 50) -> list[dict]:
        """Newest first."""
        if self._pool is not None:
            with self._pool.connection() as conn:
                rows = conn.execute(
                    "SELECT data FROM atlas_llmops_documents WHERE kind = %s "
                    "ORDER BY created_at DESC LIMIT %s",
                    (self.kind, limit),
                ).fetchall()
            return [r["data"] for r in rows]
        return list(reversed(self._read()))[:limit]
