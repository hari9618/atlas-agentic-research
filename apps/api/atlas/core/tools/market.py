"""Market tools — stock_quote (free, no key via Stooq) and company_news (via Tavily).

Both degrade gracefully: transient failures are retried with backoff, and a final
network/lookup failure returns an empty/neutral result rather than raising, so a
specialist agent can note "no market data" and move on.
"""

from __future__ import annotations

import logging

import httpx

from ..resilience import TOOL_ATTEMPTS, retry_call
from .web_search import web_search

log = logging.getLogger("atlas.tools.market")

# Stooq exposes a free CSV quote endpoint, no API key required.
_STOOQ = "https://stooq.com/q/l/?s={symbol}.us&f=sd2t2ohlcv&h&e=csv"


def _fetch_quote_csv(ticker: str) -> str:
    """Raw Stooq request. Raises on HTTP errors so the retry layer can judge them."""
    resp = httpx.get(_STOOQ.format(symbol=ticker.lower()), timeout=15.0)
    resp.raise_for_status()
    return resp.text


def stock_quote(ticker: str) -> dict:
    """Latest daily OHLCV for a US ticker. Returns {} on failure."""
    if not ticker:
        return {}
    try:
        text = retry_call(_fetch_quote_csv, ticker, attempts=TOOL_ATTEMPTS,
                          label="tool.stock_quote")
    except Exception as exc:
        log.warning("stock_quote failed for %s: %s", ticker, exc)
        return {}
    lines = text.strip().splitlines()
    if len(lines) < 2:
        return {}
    headers = [h.strip().lower() for h in lines[0].split(",")]
    values = [v.strip() for v in lines[1].split(",")]
    row = dict(zip(headers, values, strict=False))
    if row.get("close") in (None, "", "N/D"):
        return {}
    return {
        "ticker": ticker.upper(),
        "date": row.get("date"),
        "open": row.get("open"),
        "high": row.get("high"),
        "low": row.get("low"),
        "close": row.get("close"),
        "volume": row.get("volume"),
    }


def company_news(company: str, *, max_results: int = 5) -> list[dict]:
    """Recent news about a company, via the Tavily news topic (retries inside web_search)."""
    if not company:
        return []
    return web_search(f"{company} latest news", max_results=max_results, topic="news")
