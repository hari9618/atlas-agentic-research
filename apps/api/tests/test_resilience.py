"""Retry + degradation policy tests (design §5) — offline, zero-wait.

Guards the contract: transient failures are retried then succeed, non-transient
failures are never retried, and exhausted retries degrade to the fallback.
"""

from __future__ import annotations

import importlib

import httpx
import pytest

from atlas.core.resilience import is_transient, retry_call, run_or_degrade

WS_MODULE = importlib.import_module("atlas.core.tools.web_search")
MARKET = importlib.import_module("atlas.core.tools.market")


def _status_error(code: int) -> httpx.HTTPStatusError:
    req = httpx.Request("GET", "https://example.test")
    return httpx.HTTPStatusError("boom", request=req, response=httpx.Response(code, request=req))


class _Flaky:
    """Fails with ``exc`` for the first ``n`` calls, then returns ``value``."""

    def __init__(self, n: int, exc: Exception, value="ok"):
        self.n, self.exc, self.value, self.calls = n, exc, value, 0

    def __call__(self, *a, **k):
        self.calls += 1
        if self.calls <= self.n:
            raise self.exc
        return self.value


@pytest.mark.parametrize("exc", [
    _status_error(429), _status_error(503), httpx.ConnectTimeout("slow"),
    httpx.ConnectError("refused"), TimeoutError(), ConnectionResetError(),
])
def test_transient_errors_are_classified(exc):
    assert is_transient(exc)


@pytest.mark.parametrize("exc", [
    _status_error(400), _status_error(401), _status_error(404), ValueError("bad json"),
    KeyError("x"),
])
def test_non_transient_errors_are_classified(exc):
    assert not is_transient(exc)


def test_groq_rate_limit_is_transient():
    groq = pytest.importorskip("groq")
    req = httpx.Request("POST", "https://api.groq.com")
    exc = groq.RateLimitError("rate limited", response=httpx.Response(429, request=req), body=None)
    assert is_transient(exc)


def test_transient_error_is_retried_then_succeeds():
    fn = _Flaky(2, _status_error(429))
    assert retry_call(fn, attempts=3, base_wait=0, max_wait=0) == "ok"
    assert fn.calls == 3


def test_non_transient_error_is_not_retried():
    fn = _Flaky(5, ValueError("bad request"))
    with pytest.raises(ValueError):
        retry_call(fn, attempts=3, base_wait=0, max_wait=0)
    assert fn.calls == 1


def test_exhausted_retries_reraise_and_degrade_to_fallback():
    fn = _Flaky(10, httpx.ReadTimeout("slow"))
    with pytest.raises(httpx.ReadTimeout):
        retry_call(fn, attempts=3, base_wait=0, max_wait=0)
    assert fn.calls == 3
    out = run_or_degrade(lambda: retry_call(fn, attempts=2), fallback={"degraded": True},
                         label="t")
    assert out == {"degraded": True}


def test_degrade_fallback_can_build_from_the_exception():
    def boom():
        raise RuntimeError("down")

    out = run_or_degrade(boom, fallback=lambda exc: {"why": str(exc)}, label="t")
    assert out == {"why": "down"}


def test_web_search_retries_transient_then_returns_hits(monkeypatch):
    class _S:
        tavily_api_key = "test-key"

    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append(1)
        req = httpx.Request("POST", url)
        if len(calls) == 1:
            return httpx.Response(503, request=req)
        return httpx.Response(200, request=req, json={"results": [
            {"title": "t", "url": "https://x.test", "content": "c"}]})

    monkeypatch.setattr(WS_MODULE, "get_settings", lambda: _S())
    monkeypatch.setattr(WS_MODULE.httpx, "post", fake_post)
    hits = WS_MODULE.web_search("acme")
    assert len(calls) == 2 and hits[0]["url"] == "https://x.test"


def test_web_search_does_not_retry_auth_errors(monkeypatch):
    class _S:
        tavily_api_key = "bad-key"

    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append(1)
        return httpx.Response(401, request=httpx.Request("POST", url))

    monkeypatch.setattr(WS_MODULE, "get_settings", lambda: _S())
    monkeypatch.setattr(WS_MODULE.httpx, "post", fake_post)
    assert WS_MODULE.web_search("acme") == []
    assert len(calls) == 1


def test_stock_quote_degrades_to_empty_after_retries(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        raise httpx.ConnectTimeout("quote source down")

    monkeypatch.setattr(MARKET.httpx, "get", fake_get)
    assert MARKET.stock_quote("ACME") == {}
    # US symbol: Yahoo retried TOOL_ATTEMPTS times, then the Stooq fallback the same.
    assert sum("yahoo" in u for u in calls) == 3
    assert sum("stooq" in u for u in calls) == 3


def test_stock_quote_falls_back_to_stooq_csv_for_us(monkeypatch):
    csv = "Symbol,Date,Time,Open,High,Low,Close,Volume\nACME.US,2026-10-27,22:00,10,12,9,11,1000"

    def fake_get(url, **kwargs):
        if "yahoo" in url:  # Yahoo unavailable (non-transient) → Stooq answers
            return httpx.Response(404, request=httpx.Request("GET", url))
        return httpx.Response(200, request=httpx.Request("GET", url), text=csv)

    monkeypatch.setattr(MARKET.httpx, "get", fake_get)
    q = MARKET.stock_quote("acme")
    assert q["ticker"] == "ACME" and q["close"] == "11" and q["date"] == "2026-10-27"
    assert q["source"] == "Stooq"


def test_chat_retries_transient_llm_errors(monkeypatch):
    from atlas.core.agents import base

    class _Resp:
        content = " hello "

    class _LLM:
        calls = 0

        def invoke(self, msgs, config=None):
            _LLM.calls += 1
            if _LLM.calls == 1:
                raise httpx.ReadTimeout("groq slow")
            return _Resp()

    monkeypatch.setattr(base, "get_llm", lambda **k: _LLM())
    assert base.chat("hi", run_name="t") == "hello"
    assert _LLM.calls == 2
