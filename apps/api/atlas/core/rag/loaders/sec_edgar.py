"""Fetch primary 10-K / 10-Q filing text from SEC EDGAR (free, no API key).

EDGAR requires a descriptive User-Agent (set SEC_EDGAR_USER_AGENT in .env). Network
is needed at fetch time; the rest of the pipeline runs offline on cached corpus.
"""

from __future__ import annotations

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
_WS = re.compile(r"\s+")


def _headers() -> dict[str, str]:
    return {"User-Agent": get_settings().sec_edgar_user_agent}


def _strip_html(html: str) -> str:
    text = _TAG.sub(" ", html)
    return _WS.sub(" ", text).strip()


def _cik_for_ticker(client: httpx.Client, ticker: str) -> str | None:
    data = client.get(_TICKERS_URL, headers=_headers()).json()
    for row in data.values():
        if row["ticker"].upper() == ticker.upper():
            return f"{int(row['cik_str']):010d}"
    return None


def fetch_latest_filing(ticker: str, form: str = "10-K", max_chars: int = 200_000) -> Document | None:
    """Fetch the most recent `form` filing for `ticker` as a Document (plain text)."""
    with httpx.Client(timeout=30.0) as client:
        cik = _cik_for_ticker(client, ticker)
        if not cik:
            log.warning("No CIK found for ticker %s", ticker)
            return None
        subs = client.get(_SUBMISSIONS.format(cik=cik), headers=_headers()).json()
        recent = subs["filings"]["recent"]
        for i, ftype in enumerate(recent["form"]):
            if ftype != form:
                continue
            acc = recent["accessionNumber"][i]
            primary = recent["primaryDocument"][i]
            url = _ARCHIVE.format(
                cik_int=int(cik), acc_nodash=acc.replace("-", ""), doc=primary
            )
            html = client.get(url, headers=_headers()).text
            text = _strip_html(html)[:max_chars]
            company = subs.get("name", ticker)
            return Document(
                doc_id=f"{ticker}_{form}_{acc}".replace("-", ""),
                text=text,
                source="sec_edgar",
                title=f"{company} {form} ({acc})",
                url=url,
                metadata={"ticker": ticker.upper(), "form": form, "accession": acc},
            )
    log.warning("No %s filing found for %s", form, ticker)
    return None
