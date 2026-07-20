"""Episodic memory — what Atlas has analyzed before.

Every completed research run is stored as an *episode* in SQLite. On a new query
Atlas can recall past episodes two ways (exactly as the architecture prescribes):

* **Recency** — most recent episodes, via a plain SQL `ORDER BY created_at`.
* **Relevance** — most semantically similar past queries, via embeddings + cosine.

Storage is a single SQLite file; relevance uses the same (offline-capable) embedder
as the RAG layer, so it works with no network in tests.

The query embedding is computed **once at save time** and persisted alongside the row.
Recall previously re-embedded every stored query on every call — O(n) embedding work per
run, which is invisible at ten episodes and crippling at ten thousand. Vectors live in
SQLite rather than a second Qdrant collection so episodic memory keeps working when
Qdrant isn't running (Atlas degrades to an in-memory store by design).
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ...paths import cache_dir
from ..rag.embeddings import get_lc_embeddings

log = logging.getLogger("atlas.memory.episodic")


@dataclass
class Episode:
    id: int
    query: str
    target: str
    report: str
    confidence: float | None
    findings: list[dict] = field(default_factory=list)
    created_at: str = ""

    def summary(self, limit: int = 200) -> str:
        head = self.report.strip().replace("\n", " ")[:limit]
        return f"[{self.created_at[:10]}] {self.query} -> {head}"


class EpisodicMemory:
    def __init__(self, db_path: Path | None = None, offline: bool = False) -> None:
        self.db_path = db_path or (cache_dir() / "atlas_episodes.sqlite")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._offline = offline
        self._embedder = None
        self._ensure_table()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _ensure_table(self) -> None:
        with closing(self._conn()) as c, c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    target TEXT,
                    report TEXT,
                    confidence REAL,
                    findings TEXT,
                    created_at TEXT NOT NULL,
                    embedding BLOB
                )"""
            )
            # Migrate databases created before embeddings were persisted.
            cols = {r[1] for r in c.execute("PRAGMA table_info(episodes)")}
            if "embedding" not in cols:
                c.execute("ALTER TABLE episodes ADD COLUMN embedding BLOB")
                log.info("Migrated episodes table: added embedding column")

    def _embed(self):
        if self._embedder is None:
            self._embedder = get_lc_embeddings(offline=self._offline)
        return self._embedder

    @staticmethod
    def _pack(vector) -> bytes:
        return np.asarray(vector, dtype=np.float32).tobytes()

    @staticmethod
    def _unpack(blob: bytes | None):
        if not blob:
            return None
        return np.frombuffer(blob, dtype=np.float32)

    # ---- write ----
    def save(self, query: str, report: str, confidence: float | None,
             findings: list[dict], target: str = "") -> int:
        created_at = datetime.now(timezone.utc).isoformat()
        # Embed once, here — recall then reads the vector instead of recomputing it.
        try:
            blob = self._pack(self._embed().embed_query(query))
        except Exception as exc:  # pragma: no cover - embedder unavailable
            log.warning("Could not embed episode at save time (%s) — will embed on recall", exc)
            blob = None
        with closing(self._conn()) as c, c:
            cur = c.execute(
                "INSERT INTO episodes (query, target, report, confidence, findings, created_at, "
                "embedding) VALUES (?,?,?,?,?,?,?)",
                (query, target, report, confidence, json.dumps(findings), created_at, blob),
            )
            log.info("Saved episode #%s for query %r", cur.lastrowid, query[:60])
            return int(cur.lastrowid)

    # ---- read: recency (SQL) ----
    def recent(self, limit: int = 3) -> list[Episode]:
        with closing(self._conn()) as c, c:
            rows = c.execute(
                "SELECT id,query,target,report,confidence,findings,created_at "
                "FROM episodes ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row(r) for r in rows]

    # ---- read: relevance (vectors) ----
    def relevant(self, query: str, limit: int = 3) -> list[Episode]:
        """Most semantically similar past queries, by cosine over stored vectors.

        Only rows missing a vector (pre-migration, or saved while the embedder was
        down) are embedded here, then backfilled so the cost is paid once.
        """
        rows = self._rows_with_vectors()
        if not rows:
            return []

        missing = [(ep, i) for i, (ep, vec) in enumerate(rows) if vec is None]
        if missing:
            emb = self._embed()
            fresh = emb.embed_documents([ep.query for ep, _ in missing])
            for (ep, idx), vec in zip((m for m in missing), fresh):
                rows[idx] = (ep, np.asarray(vec, dtype=np.float32))
            self._backfill({ep.id: rows[idx][1] for ep, idx in missing})

        episodes = [ep for ep, _ in rows]
        docs = np.vstack([vec for _, vec in rows])
        q = np.asarray(self._embed().embed_query(query), dtype=np.float32)

        # A changed embedding model would leave stale vectors of another width.
        if docs.shape[1] != q.shape[0]:
            log.warning("Stored embedding width %d != model %d — falling back to recency.",
                        docs.shape[1], q.shape[0])
            return self.recent(limit)

        q = q / (np.linalg.norm(q) or 1.0)
        docs = docs / (np.linalg.norm(docs, axis=1, keepdims=True) + 1e-9)
        order = np.argsort(-(docs @ q))[:limit]
        return [episodes[i] for i in order]

    def _rows_with_vectors(self) -> list[tuple[Episode, np.ndarray | None]]:
        with closing(self._conn()) as c, c:
            rows = c.execute(
                "SELECT id,query,target,report,confidence,findings,created_at,embedding "
                "FROM episodes"
            ).fetchall()
        return [(self._row(r), self._unpack(r[7])) for r in rows]

    def _backfill(self, vectors: dict[int, np.ndarray]) -> None:
        with closing(self._conn()) as c, c:
            c.executemany(
                "UPDATE episodes SET embedding=? WHERE id=?",
                [(self._pack(v), eid) for eid, v in vectors.items()],
            )
        log.info("Backfilled %d episode embedding(s)", len(vectors))

    def count(self) -> int:
        with closing(self._conn()) as c, c:
            return int(c.execute("SELECT COUNT(*) FROM episodes").fetchone()[0])

    def all(self) -> list[Episode]:
        with closing(self._conn()) as c, c:
            rows = c.execute(
                "SELECT id,query,target,report,confidence,findings,created_at FROM episodes"
            ).fetchall()
        return [self._row(r) for r in rows]

    @staticmethod
    def _row(r) -> Episode:
        return Episode(
            id=r[0], query=r[1], target=r[2] or "", report=r[3] or "",
            confidence=r[4], findings=json.loads(r[5]) if r[5] else [], created_at=r[6],
        )
