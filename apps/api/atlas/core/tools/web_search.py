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


# ---- diagnostics -------------------------------------------------------------------
# Failures above only reach the server log, so a bad production key looks exactly like
# "no web results". ``probe()`` runs one minimal search and names the failure class
# (never the key), cached so a public health URL can't be used to drain credits.

_PROBE_TTL = 600.0
_probe_cache: tuple[float, dict] | None = None

_STATUS_HINTS = {
    401: "rejected: the API key is invalid",
    403: "rejected: the API key is not allowed",
    429: "rate limited: too many requests right now",
    432: "plan limit reached: the account is out of search credits",
    433: "plan limit reached: pay-as-you-go limit exceeded",
}


def probe() -> dict:
    """One tiny live search → ``{"ok": bool, "detail": str, "results": int}``."""
    import time

    global _probe_cache
    now = time.monotonic()
    if _probe_cache and now - _probe_cache[0] < _PROBE_TTL:
        return {**_probe_cache[1], "cached": True}
    key = get_settings().tavily_api_key
    if not key:
        out = {"ok": False, "detail": "TAVILY_API_KEY is not set", "results": 0}
    else:
        try:
            hits = _tavily_search(key, "Reliance Industries", 1, "general")
            out = {"ok": bool(hits), "detail": "working" if hits else "no results returned",
                   "results": len(hits)}
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            out = {"ok": False, "results": 0,
                   "detail": f"HTTP {code} — {_STATUS_HINTS.get(code, 'unexpected error')}"}
        except Exception as exc:  # network / DNS / timeout
            out = {"ok": False, "results": 0, "detail": f"{type(exc).__name__}: request failed"}
    _probe_cache = (now, out)
    return {**out, "cached": False}
