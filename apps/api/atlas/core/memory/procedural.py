"""Procedural memory — "how to act", loaded from files.

Agent playbooks live as text/markdown under data/playbooks/. This is the
file-based procedural memory from the architecture: durable instructions an agent
reads to know *how* to do its job (distinct from semantic facts about the world).
Missing playbooks degrade gracefully to an empty string.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ...paths import data_dir

log = logging.getLogger("atlas.memory.procedural")


class ProceduralMemory:
    def __init__(self, playbook_dir: Path | None = None) -> None:
        self.dir = playbook_dir or (data_dir() / "playbooks")
        self._cache: dict[str, str] = {}

    def get(self, name: str) -> str:
        """Return the playbook text for an agent, or '' if none exists (cached)."""
        if name not in self._cache:
            text = ""
            for ext in (".md", ".txt"):
                p = self.dir / f"{name}{ext}"
                if p.is_file():
                    text = p.read_text(encoding="utf-8").strip()
                    break
            self._cache[name] = text
        return self._cache[name]

    def available(self) -> list[str]:
        if not self.dir.is_dir():
            return []
        return sorted(p.stem for p in self.dir.glob("*") if p.suffix in {".md", ".txt"})
