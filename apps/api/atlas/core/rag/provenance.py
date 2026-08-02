"""Provenance & trust tiers for retrieved evidence.

Every chunk carries a ``source``. This module classifies that source into a small
trust hierarchy so the pipeline can hold one hard invariant:

    Atlas-generated (derived) facts must never rank as, or be counted as,
    authoritative source evidence.

Without this, the summarizer creates a feedback loop —
``source -> Atlas finding -> Atlas summary -> corpus -> future retrieval`` — where a
wrong earlier output can be retrieved back as if it were evidence.

Tiers, most to least trusted for grounding a final claim:

* **AUTHORITATIVE** - ingested primary sources (SEC filings, uploads, curated corpus,
  news/market docs). Citable as primary support.
* **WEB** - live web search hits: external, unvetted. Citable, but ranked below
  authoritative and visibly marked.
* **DERIVED** - Atlas's own consolidated memory (``atlas_derived``). Useful as
  context, never primary support; always visibly marked.

Reuses the existing ``source`` field rather than adding a new schema column.
"""

from __future__ import annotations

from enum import Enum


class TrustTier(str, Enum):
    AUTHORITATIVE = "authoritative"
    WEB = "web"
    DERIVED = "derived"


# Sources that are Atlas's own output or external/unvetted. Everything else is an
# ingested primary source and defaults to AUTHORITATIVE.
_DERIVED_SOURCES = {"atlas_derived", "memory"}
_WEB_SOURCES = {"web_search", "web"}

# Visible markers appended to a citation so a reader (and the guardrail) can tell a
# derived or web citation from an authoritative one at a glance.
DERIVED_MARKER = "[atlas-derived]"
WEB_MARKER = "[web]"

# Retrieval weight per tier: authoritative evidence is preferred; derived sinks
# below it so it can inform but never outrank a real source of equal relevance.
_TRUST_WEIGHT = {
    TrustTier.AUTHORITATIVE: 1.0,
    TrustTier.WEB: 0.9,
    TrustTier.DERIVED: 0.55,
}


def trust_for_source(source: str | None) -> TrustTier:
    s = (source or "").lower()
    if s in _DERIVED_SOURCES:
        return TrustTier.DERIVED
    if s in _WEB_SOURCES:
        return TrustTier.WEB
    return TrustTier.AUTHORITATIVE


def trust_weight(source: str | None) -> float:
    return _TRUST_WEIGHT[trust_for_source(source)]


# Sort priority (lower = preferred). Used as the primary retrieval sort key so an
# authoritative chunk always outranks a derived one of comparable relevance — a
# multiplicative weight alone can't guarantee that when the derived chunk happens
# to retrieve at a better rank.
_TIER_PRIORITY = {
    TrustTier.AUTHORITATIVE: 0,
    TrustTier.WEB: 1,
    TrustTier.DERIVED: 2,
}


def trust_priority(source: str | None) -> int:
    return _TIER_PRIORITY[trust_for_source(source)]


def is_authoritative(source: str | None) -> bool:
    return trust_for_source(source) is TrustTier.AUTHORITATIVE


def is_derived(source: str | None) -> bool:
    return trust_for_source(source) is TrustTier.DERIVED


def citation_marker(source: str | None) -> str:
    """The suffix a citation from this source carries (empty for authoritative)."""
    tier = trust_for_source(source)
    if tier is TrustTier.DERIVED:
        return DERIVED_MARKER
    if tier is TrustTier.WEB:
        return WEB_MARKER
    return ""


def is_derived_citation(citation: str | None) -> bool:
    return DERIVED_MARKER in (citation or "")
