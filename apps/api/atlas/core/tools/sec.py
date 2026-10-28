"""sec_filing_excerpt — pull a snippet of a company's latest SEC filing.

Thin wrapper over the EDGAR loader; returns a short excerpt + source url for the
agents to cite. Network-bound: transient EDGAR failures (429 throttling, 5xx,
timeouts) are retried with backoff, then it degrades to ``{}``.
"""

from __future__ import annotations

import logging
import re

from ..rag.loaders.sec_edgar import fetch_latest_filing
from ..resilience import TOOL_ATTEMPTS, retry_call
from .symbols import is_us_listed

log = logging.getLogger("atlas.tools.sec")

# A 10-K opens with cover-page boilerplate; the useful text starts at "Item 1.
# Business". A 20-F's equivalent section is "Item 4. Information on the Company".
_BUSINESS = re.compile(r"item\s*1\s*[.:]?\s*business", re.IGNORECASE)
_COMPANY_20F = re.compile(r"item\s*4\s*[.:]?\s*information\s+on\s+the\s+company", re.IGNORECASE)
# Any "Item 1A." / "Item 5:" style heading — used to recognise a table of contents.
_ANY_ITEM = re.compile(r"\bitem\s*\d+[a-z]?\s*[.:]", re.IGNORECASE)
# How much of the filing text to scan for the business section. In a 10-K, Item 1
# comes early. In a 20-F, Item 3 (Key Information, incl. the long Risk Factors)
# precedes Item 4, so the company description sits much deeper.
_SCAN_CHARS = {"10-K": 150_000, "20-F": 600_000}
_PROSE_WINDOW = 400    # chars after a heading that must be prose, not more headings


# "Business 4 Selected Statistical Information 103": a section name and a page number.
_PAGE_REF = re.compile(r"[A-Za-z]\s\d{1,3}\s[A-Z][a-z]")


def _looks_like_toc(window: str) -> bool:
    """A table of contents lists more "Item N." headings or page numbers, not prose."""
    return bool(_ANY_ITEM.search(window)) or len(_PAGE_REF.findall(window)) >= 3


def _business_excerpt(text: str, max_chars: int, pattern: re.Pattern = _BUSINESS) -> str:
    """The real business section, or ``""`` — never a table of contents.

    Filings list their items in a table of contents (sometimes twice — a 20-F often
    has a cross-reference index too), so "the second match" isn't reliable. Take the
    first match followed by prose. If there is none, return nothing: a contents page
    or cover boilerplate is worse than no evidence, because an analyst would cite it.
    """
    for m in pattern.finditer(text):
        if not _looks_like_toc(text[m.end():m.end() + _PROSE_WINDOW]):
            return text[m.start():m.start() + max_chars]
    return ""


def _fetch(ticker: str, form: str, max_chars: int):
    return retry_call(fetch_latest_filing, ticker, form=form,
                      max_chars=max(max_chars, _SCAN_CHARS.get(form, 150_000)),
                      attempts=TOOL_ATTEMPTS, label=f"tool.sec_filing_excerpt.{form}")


def sec_filing_excerpt(ticker: str, *, form: str = "10-K", max_chars: int = 2000) -> dict:
    """Business-section excerpt of the latest annual filing, or {}.

    Only US-listed symbols have EDGAR filings (``RELIANCE.NS`` never will). Foreign
    companies with a US listing — Infosys, Wipro, HDFC Bank, ICICI Bank — file a
    20-F instead of a 10-K, so a missing 10-K falls back to the 20-F.
    """
    if not ticker or not is_us_listed(ticker):
        return {}
    forms = [form, "20-F"] if form == "10-K" else [form]
    doc = None
    for f in forms:
        try:
            doc = _fetch(ticker, f, max_chars)
        except Exception as exc:
            log.warning("sec_filing_excerpt failed for %s (%s): %s", ticker, f, exc)
            return {}
        if doc:
            break
    if not doc:
        return {}
    pattern = _COMPANY_20F if (doc.metadata or {}).get("form") == "20-F" else _BUSINESS
    return {
        "ticker": ticker.upper(),
        "title": doc.title,
        "url": doc.url,
        "form": (doc.metadata or {}).get("form", form),
        "excerpt": _business_excerpt(doc.text, max_chars, pattern),
        "published_at": (doc.metadata or {}).get("published_at"),
    }
