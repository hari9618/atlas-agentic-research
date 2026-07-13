"""Market tools — stock_quote (free, no key via Stooq) and company_news (via Tavily).

Both degrade gracefully: a network/lookup failure returns an empty/neutral result
rather than raising, so a specialist agent can note "no market data" and move on.
"""

from __future__ import annotations

import logging

import httpx

from .web_search import web_search

log = logging.getLogger("atlas.tools.market")

# Stooq exposes a free CSV quote endpoint, no API key required.
_STOOQ = "https://stooq.com/q/l/?s={symbol}.us&f=sd2t2ohlcv&h&e=csv"


def stock_quote(ticker: str) -> dict:
    """Latest daily OHLCV for a US ticker. Returns {} on failure."""
    try:
        resp = httpx.get(_STOOQ.format(symbol=ticker.lower()), timeout=15.0)
        resp.raise_for_status()
        lines = resp.text.strip().splitlines()
        if len(lines) < 2:
            return {}
        headers = [h.strip().lower() for h in lines[0].split(",")]
        values = [v.strip() for v in lines[1].split(",")]
        row = dict(zip(headers, values))
        if row.get("close") in (None, "", "N/D"):
            return {}
        return {
            "ticker": ticker.upper(),
            "date": row.get("date"),
            "close": row.get("close"),
            "volume": row.get("volume"),
        }
    except Exception as exc:  # pragma: no cover - network
        log.warning("stock_quote failed for %s: %s", ticker, exc)
        return {}


def company_news(company: str, *, max_results: int = 5) -> list[dict]:
    """Recent news about a company, via the Tavily news topic."""
    return web_search(f"{company} latest news", max_results=max_results, topic="news")
