"""Market tools — stock_quote (free, no key) and company_news (via Tavily).

``stock_quote`` covers every market Atlas researches: Yahoo Finance's public chart
endpoint takes international symbols (``AAPL``, ``RELIANCE.NS``, ``500325.BO`` — see
``symbols.py``) and returns price, currency, exchange and the 52-week range. Stooq's
CSV endpoint is kept as a fallback for US symbols only.

Both tools degrade gracefully: transient failures are retried with backoff, and a
final network/lookup failure returns an empty/neutral result rather than raising, so
a specialist agent can note "no market data" and move on.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

from ..resilience import TOOL_ATTEMPTS, retry_call
from .symbols import clean_ticker, is_us_listed, market_of
from .web_search import web_search

log = logging.getLogger("atlas.tools.market")

_YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
# Yahoo rejects requests without a browser-like User-Agent.
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; atlas-research/1.0)"}
_STOOQ = "https://stooq.com/q/l/?s={symbol}.us&f=sd2t2ohlcv&h&e=csv"


def _num(value) -> str | None:
    """Render a number the way a reader expects (no float noise); None if missing."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return str(int(f)) if f.is_integer() else f"{f:.2f}"


def _fetch_yahoo(symbol: str) -> dict:
    """Raw Yahoo chart request. Raises on HTTP errors so the retry layer can judge them."""
    resp = httpx.get(_YAHOO.format(symbol=symbol), params={"range": "5d", "interval": "1d"},
                     headers=_HEADERS, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


def _fetch_stooq(symbol: str) -> str:
    resp = httpx.get(_STOOQ.format(symbol=symbol.lower()), headers=_HEADERS, timeout=15.0)
    resp.raise_for_status()
    return resp.text


def _yahoo_quote(symbol: str) -> dict:
    data = retry_call(_fetch_yahoo, symbol, attempts=TOOL_ATTEMPTS, label="tool.stock_quote.yahoo")
    result = ((data or {}).get("chart") or {}).get("result") or []
    if not result:
        return {}
    meta = result[0].get("meta") or {}
    price = meta.get("regularMarketPrice")
    if price is None:
        return {}
    # The latest day's open comes from the OHLC series, not the meta block.
    series = ((result[0].get("indicators") or {}).get("quote") or [{}])[0]
    opens = [o for o in (series.get("open") or []) if o is not None]
    ts = meta.get("regularMarketTime")
    market = market_of(symbol)
    exchange = market["exchange"]
    if exchange == "US":
        exchange = meta.get("fullExchangeName") or "US"
    return {
        "ticker": symbol,
        "name": meta.get("longName") or meta.get("shortName") or "",
        "exchange": exchange,
        "country": market["country"],
        "currency": meta.get("currency") or "",
        "date": datetime.fromtimestamp(ts, UTC).date().isoformat() if ts else None,
        "open": _num(opens[-1]) if opens else None,
        "high": _num(meta.get("regularMarketDayHigh")),
        "low": _num(meta.get("regularMarketDayLow")),
        "close": _num(price),
        "previous_close": _num(meta.get("chartPreviousClose")),
        "volume": _num(meta.get("regularMarketVolume")),
        "week52_high": _num(meta.get("fiftyTwoWeekHigh")),
        "week52_low": _num(meta.get("fiftyTwoWeekLow")),
        "source": "Yahoo Finance",
        "url": f"https://finance.yahoo.com/quote/{symbol}",
    }


def _stooq_quote(symbol: str) -> dict:
    text = retry_call(_fetch_stooq, symbol, attempts=TOOL_ATTEMPTS, label="tool.stock_quote.stooq")
    lines = text.strip().splitlines()
    if len(lines) < 2:
        return {}
    headers = [h.strip().lower() for h in lines[0].split(",")]
    row = dict(zip(headers, [v.strip() for v in lines[1].split(",")], strict=False))
    if row.get("close") in (None, "", "N/D"):
        return {}
    return {
        "ticker": symbol, "date": row.get("date"), "open": row.get("open"),
        "high": row.get("high"), "low": row.get("low"), "close": row.get("close"),
        "volume": row.get("volume"), "currency": "USD", "exchange": "US",
        "country": "United States", "source": "Stooq",
        "url": f"https://stooq.com/q/?s={symbol.lower()}.us",
    }


def stock_quote(ticker: str) -> dict:
    """Latest daily quote for a symbol in any market. Returns {} on failure.

    ``ticker`` uses the Yahoo convention (``AAPL``, ``RELIANCE.NS``, ``500325.BO``).
    """
    symbol = clean_ticker(ticker)
    if not symbol:
        return {}
    try:
        quote = _yahoo_quote(symbol)
        if quote:
            return quote
    except Exception as exc:
        log.warning("Yahoo quote failed for %s: %s", symbol, exc)
    if is_us_listed(symbol):  # Stooq only covers US listings
        try:
            return _stooq_quote(symbol)
        except Exception as exc:
            log.warning("Stooq quote failed for %s: %s", symbol, exc)
    return {}


def company_news(company: str, *, max_results: int = 5) -> list[dict]:
    """Recent news about a company, via the Tavily news topic (retries inside web_search)."""
    if not company:
        return []
    return web_search(f"{company} latest news", max_results=max_results, topic="news")
