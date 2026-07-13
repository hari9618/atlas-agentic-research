"""sec_filing_excerpt — pull a snippet of a company's latest SEC filing.

Thin wrapper over the EDGAR loader; returns a short excerpt + source url for the
agents to cite. Network-bound; returns {} on failure.
"""

from __future__ import annotations

import logging

from ..rag.loaders.sec_edgar import fetch_latest_filing

log = logging.getLogger("atlas.tools.sec")


def sec_filing_excerpt(ticker: str, *, form: str = "10-K", max_chars: int = 2000) -> dict:
    try:
        doc = fetch_latest_filing(ticker, form=form, max_chars=max_chars)
        if not doc:
            return {}
        return {
            "ticker": ticker.upper(),
            "title": doc.title,
            "url": doc.url,
            "excerpt": doc.text[:max_chars],
        }
    except Exception as exc:  # pragma: no cover - network
        log.warning("sec_filing_excerpt failed for %s: %s", ticker, exc)
        return {}
