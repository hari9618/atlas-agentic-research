"""International market support: one symbol convention, routed per market.

US listings (no suffix) get SEC filings (10-K, or 20-F for foreign issuers with a US
listing) plus quotes; exchange-suffixed symbols such as RELIANCE.NS get quotes only —
there is no EDGAR filing to fetch. All HTTP is mocked: no network.
"""

from __future__ import annotations

import httpx
import pytest

from atlas.core.rag import entity
from atlas.core.rag import tool_evidence as TE
from atlas.core.tools import market as MARKET
from atlas.core.tools import sec as SEC
from atlas.core.tools.symbols import clean_ticker, is_us_listed, market_of, split_symbol


# ---------------------------------------------------------------- symbols
@pytest.mark.parametrize("raw, expected", [
    ("AAPL", "AAPL"), ("$aapl", "AAPL"), ("brk-b", "BRK-B"), ("INFY", "INFY"),
    ("RELIANCE.NS", "RELIANCE.NS"), ("hdfcbank.ns", "HDFCBANK.NS"), ("M&M.NS", "M&M.NS"),
    ("BAJAJ-AUTO.NS", "BAJAJ-AUTO.NS"), ("500325.BO", "500325.BO"), ("VOD.L", "VOD.L"),
    ("", ""), (None, ""), ("not a ticker", ""), ("AAPL.TOOLONG", ""),
    ("A" * 16, ""), ("-ABC", ""),
])
def test_clean_ticker(raw, expected):
    assert clean_ticker(raw) == expected


def test_market_routing_helpers():
    assert split_symbol("RELIANCE.NS") == ("RELIANCE", "NS")
    assert is_us_listed("AAPL") and is_us_listed("BRK-B") and is_us_listed("INFY")
    assert not is_us_listed("RELIANCE.NS") and not is_us_listed("500325.BO")
    assert market_of("TCS.NS") == {"exchange": "NSE", "country": "India"}
    assert market_of("500325.BO")["exchange"] == "BSE"
    assert market_of("AAPL")["country"] == "United States"


# ---------------------------------------------------------------- quotes
def _yahoo_json(price=1196.2, currency="INR", name="Reliance Industries Limited"):
    return {"chart": {"result": [{
        "meta": {"regularMarketPrice": price, "currency": currency, "longName": name,
                 "regularMarketTime": 1761696000, "regularMarketDayHigh": 1201.0,
                 "regularMarketDayLow": 1188.5, "regularMarketVolume": 5234567,
                 "chartPreviousClose": 1190.0, "fiftyTwoWeekHigh": 1608.95,
                 "fiftyTwoWeekLow": 1114.85},
        "indicators": {"quote": [{"open": [1180.0, None, 1191.1]}]},
    }]}}


def test_indian_quote_comes_from_yahoo_with_currency(monkeypatch):
    seen = []

    def fake_get(url, **kwargs):
        seen.append(url)
        return httpx.Response(200, request=httpx.Request("GET", url), json=_yahoo_json())

    monkeypatch.setattr(MARKET.httpx, "get", fake_get)
    q = MARKET.stock_quote("reliance.ns")
    assert q["ticker"] == "RELIANCE.NS" and q["currency"] == "INR"
    assert q["close"] == "1196.20" and q["open"] == "1191.10" and q["volume"] == "5234567"
    assert q["exchange"] == "NSE" and q["country"] == "India" and q["source"] == "Yahoo Finance"
    assert q["week52_low"] == "1114.85" and q["week52_high"] == "1608.95"
    assert all("RELIANCE.NS" in u for u in seen)


def test_non_us_symbol_never_falls_back_to_stooq(monkeypatch):
    seen = []

    def fake_get(url, **kwargs):
        seen.append(url)
        return httpx.Response(404, request=httpx.Request("GET", url))

    monkeypatch.setattr(MARKET.httpx, "get", fake_get)
    assert MARKET.stock_quote("TCS.NS") == {}
    assert seen and not any("stooq" in u for u in seen)  # Stooq only covers US listings


def test_invalid_symbol_makes_no_request(monkeypatch):
    monkeypatch.setattr(MARKET.httpx, "get", lambda *a, **k: pytest.fail("no request expected"))
    assert MARKET.stock_quote("not a symbol!") == {}


def test_quote_evidence_cites_source_currency_and_exchange(monkeypatch):
    monkeypatch.setattr(TE, "_offline", lambda: False)
    monkeypatch.setattr(MARKET, "stock_quote", lambda t: {
        "ticker": "RELIANCE.NS", "name": "Reliance Industries Limited", "exchange": "NSE",
        "currency": "INR", "date": "2026-10-28", "close": "1196.20",
        "week52_low": "1114.85", "week52_high": "1608.95", "source": "Yahoo Finance",
        "url": "https://finance.yahoo.com/quote/RELIANCE.NS"})
    [chunk] = TE.quote_evidence("RELIANCE.NS")
    text = chunk.chunk.text
    assert "Reliance Industries Limited (RELIANCE.NS) on NSE" in text
    assert "last price 1196.20 INR" in text and "52-week range 1114.85–1608.95 INR" in text
    assert chunk.chunk.source == "stock_data" and "Yahoo Finance" in chunk.chunk.title
    assert chunk.chunk.url.endswith("RELIANCE.NS")


# ---------------------------------------------------------------- SEC routing
def test_sec_is_skipped_for_non_us_symbols(monkeypatch):
    monkeypatch.setattr(TE, "_offline", lambda: False)
    monkeypatch.setattr(SEC, "fetch_latest_filing", lambda *a, **k: pytest.fail("no EDGAR call"))
    assert SEC.sec_filing_excerpt("RELIANCE.NS") == {}
    assert TE.sec_evidence("RELIANCE.NS") == []


class _Doc:
    def __init__(self, form):
        self.title = f"Infosys Ltd {form} (0001)"
        self.url = "https://www.sec.gov/Archives/x"
        self.text = ("cover page ... Item 4. Information on the Company (toc) ... "
                     "Item 4. Information on the Company Infosys is a global leader in "
                     "next-generation digital services and consulting.")
        self.metadata = {"form": form, "published_at": "2026-06-20"}


def test_missing_10k_falls_back_to_20f_for_foreign_issuers(monkeypatch):
    asked = []

    def fake_fetch(ticker, form="10-K", max_chars=0):
        asked.append(form)
        return _Doc(form) if form == "20-F" else None  # foreign issuer: no 10-K

    monkeypatch.setattr(SEC, "fetch_latest_filing", fake_fetch)
    res = SEC.sec_filing_excerpt("INFY", max_chars=200)
    assert asked == ["10-K", "20-F"]
    assert res["form"] == "20-F"
    # The excerpt starts at the real section (second match), not the table of contents.
    assert res["excerpt"].startswith("Item 4. Information on the Company Infosys")


def test_10k_is_used_when_present(monkeypatch):
    asked = []
    monkeypatch.setattr(SEC, "fetch_latest_filing",
                        lambda t, form="10-K", max_chars=0: asked.append(form) or _Doc(form))
    assert SEC.sec_filing_excerpt("AAPL")["form"] == "10-K"
    assert asked == ["10-K"]


# ---------------------------------------------------------------- entity guard
def test_suffixed_symbols_match_by_name_only():
    terms = entity.entity_terms("Reliance Industries Limited", "RELIANCE.NS")
    assert terms.ticker == ""  # "RELIANCE" is an ordinary word — don't match on it
    assert entity.mentions_entity("Reliance Industries said quarterly profit rose", terms)
    assert not entity.mentions_entity("RELIANCE POWER SHARES SURGE", terms)
    us = entity.entity_terms("NVIDIA Corporation", "NVDA")
    assert us.ticker == "NVDA" and entity.mentions_entity("NVDA rallied on earnings", us)


# ---------------------------------------------------------------- filing text quality
def test_strip_html_decodes_entities_and_joins_inline_tags():
    from atlas.core.rag.loaders.sec_edgar import _strip_html

    raw = ("<html><head><style>.x{color:red}</style></head><body>"
           "<ix:header><ix:hidden>0000320193 2025-09-27 us-gaap:Revenue</ix:hidden></ix:header>"
           "<div><span>It</span><span>em&#160;1.&#160;Business</span></div>"
           "<p>The Company&#8217;s products &amp; services.</p><td>A</td><td>B</td></body></html>")
    text = _strip_html(raw)
    assert "Item 1. Business" in text            # split word re-joined, NBSP decoded
    assert "Company’s products & services." in text
    assert "A B" in text                          # block tags still separate words
    assert "us-gaap" not in text and "color:red" not in text  # hidden XBRL/CSS dropped


def test_business_excerpt_never_returns_a_table_of_contents():
    from atlas.core.tools.sec import _COMPANY_20F, _business_excerpt

    index_only = ("Item 4 Information on the Company Business 4 Selected Statistical "
                  "Information 103 Management’s Discussion and Analysis 112 Supervision "
                  "and Regulation 194 Additional Information 261")
    assert _business_excerpt(index_only, 200, _COMPANY_20F) == ""
    assert _business_excerpt("no headings here at all", 200) == ""
