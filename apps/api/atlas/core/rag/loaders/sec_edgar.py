"""Fetch primary 10-K / 10-Q filing text from SEC EDGAR (free, no API key).

EDGAR requires a descriptive User-Agent (set SEC_EDGAR_USER_AGENT in .env). Network
is needed at fetch time; the rest of the pipeline runs offline on cached corpus.
"""

from __future__ import annotations

import html
import logging
import re

import httpx

from ....config import get_settings
from ..types import Document

log = logging.getLogger("atlas.rag.sec_edgar")

_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
_ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/{doc}"

_TAG = re.compile(r"<[^>]+>")
# Inline elements don't separate words when rendered — filings even split a word across
# spans ("<span>It</span><span>em 4.</span>"). Remove them without inserting a space;
# every other (block) tag still becomes a space, exactly like a browser lays it out.
_INLINE = re.compile(
    r"</?(?:span|a|b|i|u|em|strong|font|sup|sub|small|big|ix:[a-z]+)\b[^>]*>", re.IGNORECASE
)
_WS = re.compile(r"\s+")
# Blocks whose *content* is not readable text: CSS, scripts, and the hidden inline-XBRL
# header that modern filings embed (thousands of chars of contexts and facts).
_DROP = re.compile(r"<(script|style|ix:header)\b[^>]*>.*?</\1\s*>", re.IGNORECASE | re.DOTALL)


def _headers() -> dict[str, str]:
    return {"User-Agent": get_settings().sec_edgar_user_agent}


def _strip_html(raw: str) -> str:
    """Filing HTML → readable text.

    Entities must be decoded: filings write headings as ``Item&#160;1.&#160;Business``,
    so without decoding, section detection only ever matches the plain-text table of
    contents, and every ingested chunk carries ``&#160;`` / ``&#8217;`` noise.
    """
    text = _DROP.sub(" ", raw)
    text = _INLINE.sub("", text)  # inline tags join ("It"+"em" → "Item")
    text = _TAG.sub(" ", text)    # block tags separate
    text = html.unescape(text)  # &#160; → NBSP (collapsed below), &#8217; → ’, &amp; → &
    return _WS.sub(" ", text).strip()


def _get(client: httpx.Client, url: str) -> httpx.Response:
    """GET that raises on HTTP errors, so EDGAR throttling (429/5xx) is visible to the
    retry layer instead of surfacing later as a confusing JSON decode error."""
    resp = client.get(url, headers=_headers())
    resp.raise_for_status()
    return resp


def _cik_for_ticker(client: httpx.Client, ticker: str) -> str | None:
    data = _get(client, _TICKERS_URL).json()
    for row in data.values():
        if row["ticker"].upper() == ticker.upper():
            return f"{int(row['cik_str']):010d}"
    return None


def fetch_latest_filing(
    ticker: str, form: str = "10-K", max_chars: int = 200_000
) -> Document | None:
    """Fetch the most recent `form` filing for `ticker` as a Document (plain text)."""
    with httpx.Client(timeout=30.0) as client:
        cik = _cik_for_ticker(client, ticker)
        if not cik:
            log.warning("No CIK found for ticker %s", ticker)
            return None
        subs = _get(client, _SUBMISSIONS.format(cik=cik)).json()
        recent = subs["filings"]["recent"]
        for i, ftype in enumerate(recent["form"]):
            if ftype != form:
                continue
            acc = recent["accessionNumber"][i]
            primary = recent["primaryDocument"][i]
            # Real filing date from EDGAR (never invented) — the document's published_at.
            filing_date = recent.get("filingDate", [None] * (i + 1))[i]
            url = _ARCHIVE.format(
                cik_int=int(cik), acc_nodash=acc.replace("-", ""), doc=primary
            )
            page = _get(client, url).text
            text = _strip_html(page)[:max_chars]
            company = subs.get("name", ticker)
            return Document(
                doc_id=f"{ticker}_{form}_{acc}".replace("-", ""),
                text=text,
                source="sec_edgar",
                title=f"{company} {form} ({acc})",
                url=url,
                metadata={"ticker": ticker.upper(), "form": form, "accession": acc,
                          "published_at": filing_date},
            )
    log.warning("No %s filing found for %s", form, ticker)
    return None
