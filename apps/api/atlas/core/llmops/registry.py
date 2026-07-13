"""Versioned prompt/config registry — the "Release" box of the architecture.

Each named prompt keeps a history of versions and one **active** version (what
production uses). A **candidate** slot holds a proposed prompt during a
self-improvement run (a canary): the synthesizer uses the candidate if present,
otherwise the active version. Releasing promotes the candidate to a new active
version. Persisted to a single JSON file.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ...paths import cache_dir

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
    candidate: str | None = None  # canary text during optimization

    def active_text(self) -> str:
        for v in self.versions:
            if v.version == self.active_version:
                return v.text
        return self.versions[-1].text if self.versions else ""

    def effective_text(self) -> str:
        return self.candidate if self.candidate is not None else self.active_text()


class PromptRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (cache_dir() / "prompt_registry.json")
        self.entries: dict[str, PromptEntry] = {}
        self._load()
        self._seed()

    # ---- persistence ----
    def _load(self) -> None:
        if not self.path.exists():
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        for name, e in raw.items():
            self.entries[name] = PromptEntry(
                name=name,
                active_version=e["active_version"],
                versions=[PromptVersion(**v) for v in e["versions"]],
                candidate=e.get("candidate"),
            )

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        out = {
            name: {
                "active_version": e.active_version,
                "versions": [asdict(v) for v in e.versions],
                "candidate": e.candidate,
            }
            for name, e in self.entries.items()
        }
        self.path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    def _seed(self) -> None:
        changed = False
        for name, text in SEED_PROMPTS.items():
            if name not in self.entries:
                self.entries[name] = PromptEntry(
                    name=name,
                    active_version=1,
                    versions=[PromptVersion(1, text, "seed", {}, _now())],
                )
                changed = True
        if changed:
            self._save()

    # ---- read ----
    def effective(self, name: str, default: str = "") -> str:
        e = self.entries.get(name)
        return e.effective_text() if e else default

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
            self._save()

    def clear_candidate(self, name: str) -> None:
        if name in self.entries and self.entries[name].candidate is not None:
            self.entries[name].candidate = None
            self._save()

    def release_candidate(self, name: str, scores: dict, notes: str = "") -> int:
        """Promote the current candidate to a new active version."""
        e = self.entries[name]
        if e.candidate is None:
            return e.active_version
        new_version = max((v.version for v in e.versions), default=0) + 1
        e.versions.append(PromptVersion(new_version, e.candidate, notes, scores, _now()))
        e.active_version = new_version
        e.candidate = None
        self._save()
        log.info("Released %s v%d (%s)", name, new_version, notes[:60])
        return new_version


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_registry: PromptRegistry | None = None


def get_registry() -> PromptRegistry:
    global _registry
    if _registry is None:
        _registry = PromptRegistry()
    return _registry
