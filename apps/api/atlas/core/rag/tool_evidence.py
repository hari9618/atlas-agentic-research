"""Tool results → retrievable, citable evidence.

Specialists call the research tools (SEC EDGAR, Stooq quotes, company news) for data
the ingested corpus may not have. Raw tool output can't be cited, so — exactly like
``web_evidence`` — this adapter wraps each result in a ``RetrievedChunk`` that carries
provenance (source, title, url, retrieval time). A claim sourced from a tool is then
cited, trust-tiered (see provenance.py) and guardrail-checked like any other.

SEC and stock-quote evidence is fetched by ticker, so it is about the right company
by construction; news hits pass the entity guard (entity.py) first.

Fails soft by design: offline runs, a missing ticker, or a tool failure (the tools
already retry transient errors) all yield ``[]`` — "no tool evidence", never an error.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from .entity import entity_terms
from .types import Chunk, RetrievedChunk
from .web_evidence import filter_hits_for_entity, web_offline

log = logging.getLogger("atlas.rag.tool_evidence")

# Tool evidence is targeted (asked for this exact company), so it starts a touch
# above a generic web hit; there is no query-relevance score to measure here.
_TOOL_SCORE = 0.6
# format_evidence shows ~600 chars per chunk, so long excerpts are split to fit.
_PIECE_CHARS = 600


def _offline() -> bool:
    return web_offline()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _chunk(source: str, key: str, ordinal: int, text: str, title: str, url: str = "",
           **meta) -> RetrievedChunk:
    return RetrievedChunk(
        chunk=Chunk(
            chunk_id=f"tool::{source}::{abs(hash((key, ordinal))) % 10**12}",
            doc_id=f"{source}_{key}",
            text=text,
            source=source,
            title=title,
            url=url,
            ordinal=ordinal,
            metadata={"retrieved_at": _now(), **{k: v for k, v in meta.items() if v}},
        ),
        score=round(_TOOL_SCORE - ordinal * 0.02, 4),
    )


def sec_evidence(ticker: str, *, pieces: int = 3) -> list[RetrievedChunk]:
    """Excerpt of the latest 10-K / 20-F (business section), split into citable pieces.

    Only US-listed symbols have EDGAR filings; for ``RELIANCE.NS`` and the like the
    fundamentals come from web search, company news and uploaded annual reports.
    """
    if _offline() or not ticker:
        return []
    from ..tools import sec as sec_tool  # module ref so tests can patch the tool
    from ..tools.symbols import is_us_listed

    if not is_us_listed(ticker):
        return []

    res = sec_tool.sec_filing_excerpt(ticker, max_chars=_PIECE_CHARS * pieces)
    text = (res.get("excerpt") or "").strip() if res else ""
    if not text:
        return []
    title = res.get("title") or f"{ticker.upper()} SEC filing"
    out = [
        _chunk("sec_edgar", ticker.upper(), i, text[start:start + _PIECE_CHARS], title,
               res.get("url", ""), published_at=res.get("published_at"))
        for i, start in enumerate(range(0, len(text), _PIECE_CHARS))
        if text[start:start + _PIECE_CHARS].strip()
    ]
    log.info("sec_edgar supplied %d evidence chunks for %s", len(out), ticker)
    return out[:pieces]


def quote_evidence(ticker: str) -> list[RetrievedChunk]:
    """The latest daily quote as one citable sentence (no numbers are invented)."""
    if _offline() or not ticker:
        return []
    from ..tools import market as market_tool

    q = market_tool.stock_quote(ticker)
    if not q or not q.get("close"):
        return []
    sym = q.get("ticker", ticker.upper())
    cur = f" {q['currency']}" if q.get("currency") else ""
    labels = {"close": "last price", "previous_close": "previous close", "open": "open",
              "high": "day high", "low": "day low", "volume": "volume"}
    parts = [f"{label} {q[k]}{'' if k == 'volume' else cur}"
             for k, label in labels.items() if q.get(k)]
    if q.get("week52_low") and q.get("week52_high"):
        parts.append(f"52-week range {q['week52_low']}–{q['week52_high']}{cur}")
    who = f"{q['name']} ({sym})" if q.get("name") else sym
    where = f" on {q['exchange']}" if q.get("exchange") else ""
    text = (f"Latest daily stock quote for {who}{where} "
            f"(trading date {q.get('date') or 'unknown'}): " + ", ".join(parts) + ".")
    source = q.get("source") or "market data"
    return [_chunk("stock_data", sym, 0, text, f"{sym} daily quote ({source})",
                   q.get("url", ""), trading_date=q.get("date"))]


def news_evidence(company: str, *, ticker: str = "",
                  max_results: int = 3) -> list[RetrievedChunk]:
    """Recent news hits about the company, one chunk per article.

    News search matches words, so hits that don't mention this company (full name or
    ticker) are dropped — a same-named company must never feed the report.
    """
    if _offline() or not company:
        return []
    from ..tools import market as market_tool

    hits = market_tool.company_news(company, max_results=max_results)
    hits = filter_hits_for_entity(hits or [], entity_terms(company, ticker), label="news")
    out: list[RetrievedChunk] = []
    for hit in hits or []:
        text = (hit.get("content") or "").strip()
        if not text:
            continue
        out.append(_chunk("company_news", hit.get("url", "") or company, len(out),
                          text[:_PIECE_CHARS * 2], (hit.get("title") or "news").strip(),
                          hit.get("url", "")))
    log.info("company_news supplied %d evidence chunks for %r", len(out), company[:60])
    return out


def tool_evidence_for(agent: str, *, target: str, ticker: str) -> list[RetrievedChunk]:
    """The tool evidence each specialist gets (design §3). Never raises."""
    try:
        if agent == "fundamentals":
            return sec_evidence(ticker)
        if agent == "market":
            return quote_evidence(ticker)
        if agent == "news_sentiment":
            return news_evidence(target, ticker=ticker)
    except Exception as exc:  # tools already degrade; this is belt-and-braces
        log.warning("tool evidence for %s failed: %s", agent, exc)
    return []
