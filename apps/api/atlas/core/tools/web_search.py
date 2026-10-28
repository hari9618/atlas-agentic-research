"""web_search — Tavily web search (built for agents).

Returns a short list of {title, url, content}. Requires TAVILY_API_KEY; without it
the tool returns an empty list (callers treat that as "no web evidence"), so the
pipeline never crashes when the key is absent. Transient HTTP failures (429, 5xx,
timeouts) are retried with backoff before degrading to ``[]``.
"""

from __future__ import annotations

import logging

import httpx

from ...config import get_settings
from ..resilience import TOOL_ATTEMPTS, retry_call

log = logging.getLogger("atlas.tools.web_search")

_ENDPOINT = "https://api.tavily.com/search"


def _tavily_search(api_key: str, query: str, max_results: int, topic: str) -> list[dict]:
    """One raw Tavily request. Raises on HTTP errors so the retry layer can judge them."""
    resp = httpx.post(
        _ENDPOINT,
        json={
            "api_key": api_key,
            "query": query,
            "max_results": max_results,
            "topic": topic,
            "search_depth": "basic",
        },
        timeout=20.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return [
        {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")}
        for r in data.get("results", [])
    ]


def web_search(query: str, *, max_results: int = 5, topic: str = "general") -> list[dict]:
    settings = get_settings()
    if not settings.tavily_api_key:
        log.warning("TAVILY_API_KEY not set — web_search returns no results.")
        return []
    try:
        return retry_call(
            _tavily_search, settings.tavily_api_key, query, max_results, topic,
            attempts=TOOL_ATTEMPTS, label="tool.web_search",
        )
    except Exception as exc:
        log.warning("web_search failed after retries: %s", exc)
        return []
