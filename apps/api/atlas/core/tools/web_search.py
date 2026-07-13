"""web_search — Tavily web search (built for agents).

Returns a short list of {title, url, content}. Requires TAVILY_API_KEY; without it
the tool returns an empty list (callers treat that as "no web evidence"), so the
pipeline never crashes when the key is absent.
"""

from __future__ import annotations

import logging

import httpx

from ...config import get_settings

log = logging.getLogger("atlas.tools.web_search")

_ENDPOINT = "https://api.tavily.com/search"


def web_search(query: str, *, max_results: int = 5, topic: str = "general") -> list[dict]:
    settings = get_settings()
    if not settings.tavily_api_key:
        log.info("TAVILY_API_KEY not set — web_search returns no results.")
        return []
    try:
        resp = httpx.post(
            _ENDPOINT,
            json={
                "api_key": settings.tavily_api_key,
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
    except Exception as exc:  # pragma: no cover - network
        log.warning("web_search failed: %s", exc)
        return []
