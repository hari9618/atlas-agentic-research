"""Entity guard: keep web/news evidence about the company under analysis, and only that.

Live search matches on words, not on companies. A query about the private "Helios
Robotics" comes back with "Helios Technologies" (a different, listed company) and an
unrelated "Helios" humanoid robot. Those hits are cited correctly, so the grounding
guardrail can't catch them — the report ends up confidently citing facts about the
wrong company. For an investor brief, no evidence is better than that.

The rule is deliberately strict and explainable:

* the target's full name — with only *legal* suffixes removed ("Inc", "Ltd", ...;
  never industry words like "Robotics" or "Industries") — must appear as a
  whole-word phrase in the title or content, **or**
* the ticker must appear as a whole word, written in capitals as tickers are. One- and
  two-letter tickers ("F", "GE") collide with ordinary text, so they only count in a
  ticker context such as "$F" or "NYSE: F".

Pure functions, no I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Legal-form suffixes only. "Holdings", "Group", "Technologies", "Robotics",
# "Industries" etc. are part of the name and are never stripped.
_LEGAL_SUFFIXES = {
    "inc", "incorporated", "corp", "corporation", "ltd", "limited", "llc", "plc", "co",
}
_NON_WORD = re.compile(r"[^a-z0-9]+")
# A "target" longer than this is not a company name (e.g. the supervisor's fallback
# echoed the whole question); guarding on it would discard every hit.
_MAX_NAME_WORDS = 6


@dataclass(frozen=True)
class EntityTerms:
    name: str     # normalized name phrase, e.g. "reliance industries"
    ticker: str   # upper-case ticker or ""


def _normalize(text: str) -> str:
    return " ".join(_NON_WORD.sub(" ", (text or "").lower().replace("&", " and ")).split())


def normalize_name(target: str) -> str:
    """Lower-case, punctuation-free name with trailing legal suffixes removed."""
    words = _normalize(target).split()
    if words and words[0] == "the" and len(words) > 1:
        words = words[1:]
    while len(words) > 1 and words[-1] in _LEGAL_SUFFIXES:
        words = words[:-1]
    return " ".join(words)


def entity_terms(target: str, ticker: str = "") -> EntityTerms | None:
    """Matching terms for the company, or None when there is nothing safe to match on."""
    name = normalize_name(target)
    if len(name.split()) > _MAX_NAME_WORDS:
        name = ""
    tick = (ticker or "").strip().upper().lstrip("$")
    if not (name or tick):
        return None
    return EntityTerms(name=name, ticker=tick)


def _ticker_in(text: str, ticker: str) -> bool:
    t = re.escape(ticker)
    if len(ticker) <= 2:
        pattern = rf"(?:\$|\b(?:NYSE|NASDAQ|Nasdaq|AMEX|ticker)\s*:?\s*){t}(?![A-Za-z0-9])"
    else:
        pattern = rf"(?<![A-Za-z0-9$]){t}(?![A-Za-z0-9])|\${t}(?![A-Za-z0-9])"
    return re.search(pattern, text or "") is not None


def mentions_entity(text: str, terms: EntityTerms | None) -> bool:
    """True if ``text`` is about the company described by ``terms`` (None → True)."""
    if terms is None:
        return True
    if terms.name and f" {terms.name} " in f" {_normalize(text)} ":
        return True
    return bool(terms.ticker) and _ticker_in(text, terms.ticker)
