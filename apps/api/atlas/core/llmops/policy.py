"""Agent policies — the versioned, learnable part of each agent.

Rewording one system prompt barely moves report quality: quality is dominated by
*what evidence an analyst pulls* and *how it turns evidence into findings*. So the
learning loop tunes a small, bounded policy per component instead of free text:

* ``lessons``   — short imperative rules distilled from failures and reviewer
                  feedback ("Give the date of every development"). Procedural memory.
* ``exemplars`` — strong, verified findings from approved runs, shown as few-shot
                  demonstrations of the target quality.
* ``top_k``     — retrieval depth: how many evidence chunks the analyst reads.
* ``system``    — the base instruction (synthesizer only; specialists keep their role).

Every change is a new immutable version; exactly one is active. Releasing and
rolling back only move the ``active`` pointer, so any version can be restored and
every run record names the versions it used.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .store import DocumentStore, now_iso

log = logging.getLogger("atlas.llmops.policy")

SPECIALIST_COMPONENTS = ("fundamentals", "news_sentiment", "risk", "market")
COMPONENTS = (*SPECIALIST_COMPONENTS, "synthesizer")
LABELS = {
    "fundamentals": "Fundamentals analyst",
    "news_sentiment": "News & sentiment analyst",
    "risk": "Risk analyst",
    "market": "Market & competitors analyst",
    "synthesizer": "Report writer",
}

MAX_LESSONS = 6
MAX_EXEMPLARS = 2
TOP_K_RANGE = (3, 8)
DEFAULT_TOP_K = 4
DEFAULT_SYSTEM = "You are a senior analyst writing a grounded, cited brief."


@dataclass
class Policy:
    lessons: list[str] = field(default_factory=list)
    exemplars: list[dict] = field(default_factory=list)  # {claim, evidence}
    top_k: int = DEFAULT_TOP_K
    system: str = ""

    def bounded(self) -> Policy:
        """A copy clamped to the limits, so no proposal can grow a prompt unboundedly."""
        lo, hi = TOP_K_RANGE
        return Policy(
            lessons=[s.strip() for s in self.lessons if s.strip()][-MAX_LESSONS:],
            exemplars=self.exemplars[-MAX_EXEMPLARS:],
            top_k=max(lo, min(hi, int(self.top_k))),
            system=self.system.strip(),
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict | None) -> Policy:
        d = d or {}
        return Policy(
            lessons=list(d.get("lessons") or []),
            exemplars=list(d.get("exemplars") or []),
            top_k=int(d.get("top_k") or DEFAULT_TOP_K),
            system=str(d.get("system") or ""),
        ).bounded()


def default_policy(component: str) -> Policy:
    return Policy(system=DEFAULT_SYSTEM if component == "synthesizer" else "")


def prompt_block(policy: Policy) -> str:
    """The policy rendered for a prompt: lessons, then exemplars. ``""`` when empty."""
    parts: list[str] = []
    if policy.lessons:
        parts.append("Lessons from past reviews (follow these):\n"
                     + "\n".join(f"- {s}" for s in policy.lessons))
    if policy.exemplars:
        parts.append("Examples of strong findings (match this specificity and grounding):\n"
                     + "\n".join(f'- "{e.get("claim", "")}"' for e in policy.exemplars))
    return "\n\n".join(parts)


class PolicyStore:
    """Versioned policies, one document per component:
    ``{component, active, versions: [{version, created_at, notes, policy}]}``."""

    def __init__(self, *, root: Path | None = None, pool: Any = None) -> None:
        self._docs = DocumentStore("policy", root=root, pool=pool)

    @property
    def backend(self) -> str:
        return self._docs.backend

    def _doc(self, component: str) -> dict:
        if component not in COMPONENTS:
            raise KeyError(f"unknown component {component!r}")
        doc = self._docs.get(component)
        if doc is None:
            doc = {"component": component, "active": 1, "versions": [{
                "version": 1, "created_at": now_iso(), "notes": "default",
                "policy": default_policy(component).to_dict(),
            }]}
            self._docs.put(component, doc)
        return doc

    def active(self, component: str) -> Policy:
        doc = self._doc(component)
        for v in doc["versions"]:
            if v["version"] == doc["active"]:
                return Policy.from_dict(v["policy"])
        return default_policy(component)

    def active_version(self, component: str) -> int:
        return int(self._doc(component)["active"])

    def versions(self, component: str) -> list[dict]:
        return copy.deepcopy(self._doc(component)["versions"])

    def snapshot(self) -> dict[str, int]:
        """``{component: active version}`` — stamped on every run record."""
        return {c: self.active_version(c) for c in COMPONENTS}

    def release(self, component: str, policy: Policy, notes: str) -> int:
        """Add ``policy`` as a new version and make it active. Returns the version."""
        doc = self._doc(component)
        version = max(v["version"] for v in doc["versions"]) + 1
        doc["versions"].append({"version": version, "created_at": now_iso(),
                                "notes": notes[:300], "policy": policy.bounded().to_dict(),
                                "previous": doc["active"]})
        doc["active"] = version
        self._docs.put(component, doc)
        log.info("released %s v%d: %s", component, version, notes[:80])
        return version

    def rollback(self, component: str) -> int:
        """Re-activate the version the active one replaced (or the one before it)."""
        doc = self._doc(component)
        current = next((v for v in doc["versions"] if v["version"] == doc["active"]), None)
        target = (current or {}).get("previous")
        if target is None:
            older = [v["version"] for v in doc["versions"] if v["version"] < doc["active"]]
            target = max(older) if older else doc["active"]
        doc["active"] = int(target)
        self._docs.put(component, doc)
        log.info("rolled back %s to v%d", component, target)
        return int(target)


_store: PolicyStore | None = None


def get_policies() -> PolicyStore:
    global _store
    if _store is None:
        _store = PolicyStore()
    return _store


def reset_policies() -> None:
    """Forget the cached store (tests)."""
    global _store
    _store = None
