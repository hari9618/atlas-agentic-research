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

log = logging.getLogger("atlas.tools.sec")

# A 10-K opens with cover-page boilerplate; the useful text starts at "Item 1.
# Business". Its first match is usually the table of contents, so prefer the second.
_BUSINESS = re.compile(r"item\s*1\s*[.:]?\s*business", re.IGNORECASE)
_SCAN_CHARS = 150_000  # how much of the filing to scan for the business section


def _business_excerpt(text: str, max_chars: int) -> str:
    hits = [m.start() for m in _BUSINESS.finditer(text)]
    start = hits[1] if len(hits) > 1 else (hits[0] if hits else 0)
    return text[start:start + max_chars]


def sec_filing_excerpt(ticker: str, *, form: str = "10-K", max_chars: int = 2000) -> dict:
    if not ticker:
        return {}
    try:
        doc = retry_call(fetch_latest_filing, ticker, form=form,
                         max_chars=max(max_chars, _SCAN_CHARS),
                         attempts=TOOL_ATTEMPTS, label="tool.sec_filing_excerpt")
    except Exception as exc:
        log.warning("sec_filing_excerpt failed for %s: %s", ticker, exc)
        return {}
    if not doc:
        return {}
    return {
        "ticker": ticker.upper(),
        "title": doc.title,
        "url": doc.url,
        "excerpt": _business_excerpt(doc.text, max_chars),
        "published_at": (doc.metadata or {}).get("published_at"),
    }
