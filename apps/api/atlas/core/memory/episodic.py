"""Episodic memory — what Atlas has analyzed before.

Every completed research run is stored as an *episode* in SQLite. On a new query
Atlas can recall past episodes two ways (exactly as the architecture prescribes):

* **Recency** — most recent episodes, via a plain SQL `ORDER BY created_at`.
* **Relevance** — most semantically similar past queries, via embeddings + cosine.

Storage is a single SQLite file; relevance uses the same (offline-capable) embedder
as the RAG layer, so it works with no network in tests.
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
                    created_at TEXT NOT NULL
                )"""
            )

    def _embed(self):
        if self._embedder is None:
            self._embedder = get_lc_embeddings(offline=self._offline)
        return self._embedder

    # ---- write ----
    def save(self, query: str, report: str, confidence: float | None,
             findings: list[dict], target: str = "") -> int:
        created_at = datetime.now(timezone.utc).isoformat()
        with closing(self._conn()) as c, c:
            cur = c.execute(
                "INSERT INTO episodes (query, target, report, confidence, findings, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (query, target, report, confidence, json.dumps(findings), created_at),
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
        episodes = self.all()
        if not episodes:
            return []
        emb = self._embed()
        q = np.array(emb.embed_query(query), dtype=np.float32)
        docs = np.array(emb.embed_documents([e.query for e in episodes]), dtype=np.float32)
        q = q / (np.linalg.norm(q) or 1.0)
        docs = docs / (np.linalg.norm(docs, axis=1, keepdims=True) + 1e-9)
        sims = docs @ q
        order = np.argsort(-sims)[:limit]
        return [episodes[i] for i in order]

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
