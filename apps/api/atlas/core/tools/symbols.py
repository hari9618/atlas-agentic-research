"""Ticker symbols across markets — one convention, every tool.

Atlas stores a single ``ticker`` per run using the Yahoo Finance symbol convention,
because it is the one free quote source that covers the US, India and most other
exchanges:

* US listings have no suffix:            ``AAPL``, ``BRK-B``, ``INFY`` (an ADR)
* India uses the exchange suffix:        ``RELIANCE.NS`` (NSE), ``500325.BO`` (BSE)
* other markets work the same way:       ``VOD.L`` (London), ``7203.T`` (Tokyo)

The suffix is what tells the tools which market a company trades in, so they can
route: SEC EDGAR filings only exist for US-listed companies (10-K for domestic
filers, 20-F for foreign issuers with US listings), while quotes work everywhere.
"""

from __future__ import annotations

import re

# Base: letters/digits plus the "&" and "-" real symbols use (M&M, BAJAJ-AUTO, BRK-B),
# up to 15 chars (Indian NSE symbols run long). Optional ".XX" exchange suffix.
_SYMBOL = re.compile(r"^[A-Z0-9][A-Z0-9&\-]{0,14}(?:\.[A-Z]{1,3})?$")

# Suffixes we can name for the reader; anything else is still a valid symbol.
_EXCHANGES = {
    "NS": ("NSE", "India"),
    "BO": ("BSE", "India"),
    "L": ("London Stock Exchange", "United Kingdom"),
    "T": ("Tokyo Stock Exchange", "Japan"),
    "HK": ("Hong Kong Stock Exchange", "Hong Kong"),
    "TO": ("Toronto Stock Exchange", "Canada"),
    "AX": ("ASX", "Australia"),
    "DE": ("XETRA", "Germany"),
    "PA": ("Euronext Paris", "France"),
    "SI": ("Singapore Exchange", "Singapore"),
}


def clean_ticker(value) -> str:
    """Normalize an LLM/user-supplied symbol, or return ``""`` if it isn't one."""
    t = str(value or "").strip().upper().lstrip("$")
    # Internal whitespace means a phrase, not a symbol ("not a ticker" ≠ "NOTATICKER").
    return t if _SYMBOL.match(t) else ""


def split_symbol(symbol: str) -> tuple[str, str]:
    """``"RELIANCE.NS"`` → ``("RELIANCE", "NS")``; ``"AAPL"`` → ``("AAPL", "")``."""
    base, _, suffix = (symbol or "").upper().partition(".")
    return base, suffix


def is_us_listed(symbol: str) -> bool:
    """US listings carry no exchange suffix — and only they have SEC filings."""
    return bool(symbol) and not split_symbol(symbol)[1]


def market_of(symbol: str) -> dict[str, str]:
    """Human-readable exchange and country for a symbol (best effort)."""
    _, suffix = split_symbol(symbol)
    if not suffix:
        return {"exchange": "US", "country": "United States"}
    exchange, country = _EXCHANGES.get(suffix, (suffix, ""))
    return {"exchange": exchange, "country": country}
