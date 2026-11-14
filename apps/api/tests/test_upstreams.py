"""Managed upstream calls: circuit breaker, bulkhead, cache, coalescing, Retry-After."""

from __future__ import annotations

import threading
import time

import httpx
import pytest

from atlas.core.resilience import retry_after_seconds, retry_call
from atlas.core.upstreams import (
    CLOSED,
    HALF_OPEN,
    OPEN,
    BulkheadFullError,
    CircuitOpenError,
    Upstream,
)


def _http_error(status: int, retry_after: str | None = None) -> httpx.HTTPStatusError:
    req = httpx.Request("GET", "https://provider.test")
    headers = {"retry-after": retry_after} if retry_after else {}
    return httpx.HTTPStatusError("boom", request=req,
                                 response=httpx.Response(status, request=req, headers=headers))


def test_breaker_opens_after_consecutive_failures_and_fails_fast():
    up = Upstream("t", failure_threshold=3, cooldown_s=60, attempts=1)
    calls = {"n": 0}

    def down():
        calls["n"] += 1
        raise _http_error(503)

    for _ in range(3):
        with pytest.raises(httpx.HTTPStatusError):
            up.call(down)
    assert up.state == OPEN
    started = time.perf_counter()
    with pytest.raises(CircuitOpenError):
        up.call(down)
    assert time.perf_counter() - started < 0.05  # no network, no backoff
    assert calls["n"] == 3 and up.counters["short_circuited"] == 1


def test_half_open_probe_closes_the_circuit_on_success():
    up = Upstream("t", failure_threshold=1, cooldown_s=0.05, attempts=1)
    with pytest.raises(httpx.HTTPStatusError):
        up.call(lambda: (_ for _ in ()).throw(_http_error(500)))
    assert up.state == OPEN
    time.sleep(0.08)
    assert up.state == HALF_OPEN
    assert up.call(lambda: "ok") == "ok"
    assert up.state == CLOSED


def test_failed_probe_reopens_the_circuit():
    up = Upstream("t", failure_threshold=1, cooldown_s=0.05, attempts=1)
    fail = lambda: (_ for _ in ()).throw(_http_error(502))  # noqa: E731
    with pytest.raises(httpx.HTTPStatusError):
        up.call(fail)
    time.sleep(0.08)
    with pytest.raises(httpx.HTTPStatusError):
        up.call(fail)
    assert up.state == OPEN


def test_client_errors_do_not_trip_the_breaker():
    up = Upstream("t", failure_threshold=2, attempts=1)
    for _ in range(5):
        with pytest.raises(httpx.HTTPStatusError):
            up.call(lambda: (_ for _ in ()).throw(_http_error(404)))
    assert up.state == CLOSED


def test_successful_results_are_cached_per_key():
    up = Upstream("t", cache_ttl_s=60)
    calls = {"n": 0}

    def fetch(q):
        calls["n"] += 1
        return [q]

    assert up.call(fetch, "nvda", cache_key="nvda") == ["nvda"]
    assert up.call(fetch, "nvda", cache_key="nvda") == ["nvda"]
    assert up.call(fetch, "amd", cache_key="amd") == ["amd"]
    assert calls["n"] == 2 and up.counters["cache_hits"] == 1


def test_empty_results_are_not_cached():
    up = Upstream("t", cache_ttl_s=60)
    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        return []

    up.call(fetch, cache_key="k")
    up.call(fetch, cache_key="k")
    assert calls["n"] == 2


def test_identical_concurrent_calls_are_coalesced():
    up = Upstream("t", cache_ttl_s=0, max_concurrency=8)
    calls = {"n": 0}
    gate = threading.Event()

    def slow():
        calls["n"] += 1
        gate.wait(2)
        return ["result"]

    results: list = []
    threads = [threading.Thread(target=lambda: results.append(up.call(slow, cache_key="same")))
               for _ in range(5)]
    for t in threads:
        t.start()
    time.sleep(0.1)
    gate.set()
    for t in threads:
        t.join()
    assert results == [["result"]] * 5
    assert calls["n"] == 1 and up.counters["coalesced"] == 4


def test_bulkhead_rejects_when_all_slots_stay_busy():
    up = Upstream("t", max_concurrency=1, acquire_timeout_s=0.05)
    gate = threading.Event()
    t = threading.Thread(target=lambda: up.call(lambda: gate.wait(2)))
    t.start()
    time.sleep(0.05)
    with pytest.raises(BulkheadFullError):
        up.call(lambda: "never runs")
    gate.set()
    t.join()
    assert up.counters["rejected"] == 1


def test_retry_after_header_drives_the_wait(monkeypatch):
    assert retry_after_seconds(_http_error(429, "7")) == 7.0
    assert retry_after_seconds(_http_error(429, "Wed, 21 Oct 2015 07:28:00 GMT")) is None
    assert retry_after_seconds(ValueError("x")) is None

    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise _http_error(429, "3")
        return "ok"

    assert retry_call(flaky, attempts=3, base_wait=0.5, max_wait=20) == "ok"
    assert sleeps == [3.0]  # the server's hint, not the backoff formula


def test_deadline_stops_retrying():
    calls = {"n": 0}

    def always_timeout():
        calls["n"] += 1
        time.sleep(0.06)
        raise httpx.ReadTimeout("slow")

    with pytest.raises(httpx.ReadTimeout):
        retry_call(always_timeout, attempts=10, base_wait=0, max_wait=0, deadline_s=0.1)
    assert calls["n"] < 10
