"""Versioned prompt/config registry — the "Release" box of the architecture.

Each named prompt keeps a history of versions and one **active** version (what
production uses). A **candidate** slot records the prompt a self-improvement run
is currently evaluating, for visibility only: live traffic always gets the active
version. The optimizer passes the candidate to its own trial runs through the run
config (see ``graph.run_research(prompt_override=...)``), so an unproven prompt never
reaches a real user's report. Releasing promotes the candidate to a new active version.

Persistence: a Postgres table (``atlas_prompt_registry``, one row per prompt) when
``DATABASE_URL`` is set, so a released prompt survives redeploys on ephemeral hosts;
otherwise a single JSON file. An explicit ``path`` always means JSON (tests).
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ...paths import cache_dir
from ..persistence import get_pg_pool, run_ddl

log = logging.getLogger("atlas.llmops.registry")

# Seed prompts (v1). These are the defaults the loop can improve upon.
SEED_PROMPTS = {
    "synthesizer_system": "You are a senior analyst writing a grounded, cited brief.",
}


@dataclass
class PromptVersion:
    version: int
    text: str
    notes: str = ""
    scores: dict = field(default_factory=dict)
    created_at: str = ""


@dataclass
class PromptEntry:
    name: str
    active_version: int
    versions: list[PromptVersion] = field(default_factory=list)
    candidate: str | None = None  # prompt under evaluation (never served live)

    def active_text(self) -> str:
        for v in self.versions:
            if v.version == self.active_version:
                return v.text
        return self.versions[-1].text if self.versions else ""


class PromptRegistry:
    _DDL = (
        """CREATE TABLE IF NOT EXISTS atlas_prompt_registry (
            name TEXT PRIMARY KEY,
            data JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )""",
    )

    def __init__(self, path: Path | None = None, pool: Any = None) -> None:
        """Pick the store: an explicit ``pool`` → Postgres; an explicit ``path`` → JSON;
        neither → Postgres if ``DATABASE_URL`` is reachable, else JSON."""
        self.path = path or (cache_dir() / "prompt_registry.json")
        if pool is None and path is None:
            pool = get_pg_pool()
        self._pool = pool
        if self._pool is not None:
            try:
                run_ddl(self._pool, self._DDL)
            except Exception as exc:
                log.warning("Postgres prompt registry unavailable (%s) — using JSON.", exc)
                self._pool = None
        self.entries: dict[str, PromptEntry] = {}
        self._load()
        self._seed()

    @property
    def backend(self) -> str:
        return "postgres" if self._pool is not None else "json"

    # ---- persistence ----
    @staticmethod
    def _encode(e: PromptEntry) -> dict:
        return {
            "active_version": e.active_version,
            "versions": [asdict(v) for v in e.versions],
            "candidate": e.candidate,
        }

    @staticmethod
    def _decode(name: str, e: dict) -> PromptEntry:
        return PromptEntry(
            name=name,
            active_version=e["active_version"],
            versions=[PromptVersion(**v) for v in e["versions"]],
            candidate=e.get("candidate"),
        )

    def _load(self) -> None:
        if self._pool is not None:
            with self._pool.connection() as conn:
                rows = conn.execute("SELECT name, data FROM atlas_prompt_registry").fetchall()
            raw = {r["name"]: r["data"] for r in rows}
        elif self.path.exists():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            return
        for name, e in raw.items():
            self.entries[name] = self._decode(name, e)

    def _save(self, *names: str) -> None:
        """Persist ``names`` (default: every entry).

        Postgres upserts only the touched rows, so two workers editing different
        prompts don't overwrite each other with a stale in-memory copy.
        """
        if self._pool is not None:
            from psycopg.types.json import Jsonb

            todo = names or tuple(self.entries)
            with self._pool.connection() as conn, conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO atlas_prompt_registry (name, data, updated_at) "
                    "VALUES (%s, %s, now()) ON CONFLICT (name) DO UPDATE "
                    "SET data = EXCLUDED.data, updated_at = now()",
                    [(n, Jsonb(self._encode(self.entries[n]))) for n in todo],
                )
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        out = {name: self._encode(e) for name, e in self.entries.items()}
        self.path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    def _seed(self) -> None:
        added: list[str] = []
        for name, text in SEED_PROMPTS.items():
            if name not in self.entries:
                self.entries[name] = PromptEntry(
                    name=name,
                    active_version=1,
                    versions=[PromptVersion(1, text, "seed", {}, _now())],
                )
                added.append(name)
        if added:
            self._save(*added)

    # ---- read ----
    def effective(self, name: str, default: str = "") -> str:
        """The prompt live traffic uses: always the active version."""
        e = self.entries.get(name)
        return e.active_text() if e else default

    def candidate(self, name: str) -> str | None:
        """The prompt a self-improvement run is evaluating, if any."""
        e = self.entries.get(name)
        return e.candidate if e else None

    def active_version(self, name: str) -> int:
        e = self.entries.get(name)
        return e.active_version if e else 0

    def history(self, name: str) -> list[PromptVersion]:
        e = self.entries.get(name)
        return e.versions if e else []

    # ---- write / canary ----
    def set_candidate(self, name: str, text: str) -> None:
        if name in self.entries:
            self.entries[name].candidate = text
            self._save(name)

    def clear_candidate(self, name: str) -> None:
        if name in self.entries and self.entries[name].candidate is not None:
            self.entries[name].candidate = None
            self._save(name)

    def release_candidate(self, name: str, scores: dict, notes: str = "") -> int:
        """Promote the current candidate to a new active version."""
        e = self.entries[name]
        if e.candidate is None:
            return e.active_version
        new_version = max((v.version for v in e.versions), default=0) + 1
        e.versions.append(PromptVersion(new_version, e.candidate, notes, scores, _now()))
        e.active_version = new_version
        e.candidate = None
        self._save(name)
        log.info("Released %s v%d (%s)", name, new_version, notes[:60])
        return new_version


def _now() -> str:
    return datetime.now(UTC).isoformat()


_registry: PromptRegistry | None = None


def get_registry() -> PromptRegistry:
    global _registry
    if _registry is None:
        _registry = PromptRegistry()
    return _registry
