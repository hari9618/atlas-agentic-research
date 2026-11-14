"""Managed calls to external services: cache → coalesce → breaker → bulkhead → retry.

``retry_call`` alone handles a *blip*. At many concurrent users the failure modes
are different, and each layer here answers one of them:

1. **TTL cache** — ten users researching NVIDIA in the same ten minutes need one
   Tavily search, not ten. Only successful, non-empty results are cached.
2. **Single-flight** — identical calls already in flight share that call's result
   instead of all hitting the provider at the same moment (a cache stampede).
3. **Circuit breaker** — when a provider is down, every run used to spend its whole
   retry budget (attempts × backoff) rediscovering that. After ``failure_threshold``
   consecutive failed calls the circuit *opens* and calls fail instantly for
   ``cooldown_s``; then one probe call is let through (*half-open*) and its outcome
   closes or re-opens the circuit. Runs degrade in milliseconds, not tens of seconds.
4. **Bulkhead** — a cap on concurrent calls per provider, so a burst of runs queues
   briefly instead of tripping the provider's own rate limit for everyone.
5. **Retry** — ``retry_call``: transient errors only, backoff + jitter, honouring
   ``Retry-After``, inside an overall deadline.

State is per process, deliberately: a breaker reacts to what *this* instance sees, and
sharing it would add a network hop to every call. ``stats()`` feeds /health/upstreams.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable
from concurrent.futures import Future
from typing import Any, TypeVar

from .resilience import TOOL_ATTEMPTS, is_transient, retry_call

log = logging.getLogger("atlas.upstreams")

T = TypeVar("T")

CLOSED, OPEN, HALF_OPEN = "closed", "open", "half_open"


class CircuitOpenError(RuntimeError):
    """Raised instantly while a provider's circuit is open. Not transient: callers
    degrade (empty result) instead of retrying."""


class BulkheadFullError(RuntimeError):
    """Too many calls to this provider are already waiting."""


class Upstream:
    def __init__(
        self,
        name: str,
        *,
        max_concurrency: int = 4,
        acquire_timeout_s: float = 30.0,
        failure_threshold: int = 5,
        cooldown_s: float = 30.0,
        cache_ttl_s: float = 0.0,
        cache_size: int = 256,
        attempts: int = TOOL_ATTEMPTS,
        deadline_s: float = 45.0,
    ) -> None:
        self.name = name
        self.attempts = attempts
        self.deadline_s = deadline_s
        self.failure_threshold = failure_threshold
        self.cooldown_s = cooldown_s
        self.cache_ttl_s = cache_ttl_s
        self.cache_size = cache_size
        self.acquire_timeout_s = acquire_timeout_s
        self._sem = threading.BoundedSemaphore(max(1, max_concurrency))
        self.max_concurrency = max(1, max_concurrency)
        self._lock = threading.Lock()
        self._cache: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._inflight: dict[Hashable, Future] = {}
        self._state = CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._probe_out = False
        self.counters = {"calls": 0, "ok": 0, "failed": 0, "retries": 0, "cache_hits": 0,
                         "coalesced": 0, "short_circuited": 0, "rejected": 0}
        self._active = 0

    # ------------------------------------------------------------ breaker
    def _admit(self) -> None:
        with self._lock:
            if self._state == OPEN:
                if time.monotonic() - self._opened_at < self.cooldown_s:
                    self.counters["short_circuited"] += 1
                    raise CircuitOpenError(f"{self.name} circuit open")
                self._state, self._probe_out = HALF_OPEN, False
            if self._state == HALF_OPEN:
                if self._probe_out:  # one probe at a time
                    self.counters["short_circuited"] += 1
                    raise CircuitOpenError(f"{self.name} circuit half-open (probing)")
                self._probe_out = True

    def _record(self, ok: bool) -> None:
        with self._lock:
            if ok:
                if self._state != CLOSED:
                    log.info("upstream %s recovered — circuit closed", self.name)
                self._state, self._failures, self._probe_out = CLOSED, 0, False
                self.counters["ok"] += 1
                return
            self.counters["failed"] += 1
            self._failures += 1
            if self.failure_threshold and (
                    self._state == HALF_OPEN or self._failures >= self.failure_threshold):
                if self._state != OPEN:
                    log.warning("upstream %s failing (%d in a row) — circuit open for %.0fs",
                                self.name, self._failures, self.cooldown_s)
                self._state, self._opened_at, self._probe_out = OPEN, time.monotonic(), False

    # ------------------------------------------------------------ cache
    def _cached(self, key: Hashable) -> tuple[bool, Any]:
        if not self.cache_ttl_s or key is None:
            return False, None
        with self._lock:
            hit = self._cache.get(key)
            if hit and hit[0] > time.monotonic():
                self._cache.move_to_end(key)
                self.counters["cache_hits"] += 1
                return True, hit[1]
            if hit:
                self._cache.pop(key, None)
        return False, None

    def _store(self, key: Hashable, value: Any) -> None:
        if not self.cache_ttl_s or key is None or not value:
            return
        with self._lock:
            self._cache[key] = (time.monotonic() + self.cache_ttl_s, value)
            self._cache.move_to_end(key)
            while len(self._cache) > self.cache_size:
                self._cache.popitem(last=False)

    # ------------------------------------------------------------ call
    def call(self, fn: Callable[..., T], *args: Any, cache_key: Hashable = None,
             label: str | None = None, **kwargs: Any) -> T:
        """Run ``fn`` through every layer. Raises on final failure — the tool decides
        how to degrade (they all return an empty result)."""
        with self._lock:
            self.counters["calls"] += 1
        hit, value = self._cached(cache_key)
        if hit:
            return value

        leader = True
        if cache_key is not None:
            with self._lock:
                fut = self._inflight.get(cache_key)
                if fut is None:
                    fut = Future()
                    self._inflight[cache_key] = fut
                else:
                    leader = False
                    self.counters["coalesced"] += 1
            if not leader:
                return fut.result(timeout=self.deadline_s + self.acquire_timeout_s)
        try:
            result = self._execute(fn, args, kwargs, label)
        except BaseException as exc:
            if cache_key is not None:
                self._finish(cache_key, error=exc)
            raise
        self._store(cache_key, result)
        if cache_key is not None:
            self._finish(cache_key, result=result)
        return result

    def _finish(self, key: Hashable, *, result: Any = None,
                error: BaseException | None = None) -> None:
        with self._lock:
            fut = self._inflight.pop(key, None)
        if fut is not None:
            if error is not None:
                fut.set_exception(error)
            else:
                fut.set_result(result)

    def _execute(self, fn: Callable[..., T], args: tuple, kwargs: dict,
                 label: str | None) -> T:
        self._admit()
        if not self._sem.acquire(timeout=self.acquire_timeout_s):
            with self._lock:
                self.counters["rejected"] += 1
                self._probe_out = False
            raise BulkheadFullError(f"{self.name}: too many concurrent calls")
        with self._lock:
            self._active += 1
        try:
            result = retry_call(fn, *args, attempts=self.attempts,
                                label=label or f"upstream.{self.name}",
                                deadline_s=self.deadline_s, on_retry=self._count_retry,
                                **kwargs)
        except Exception as exc:
            # Only provider trouble trips the breaker; a 404 for an unknown ticker is
            # a correct answer, not an outage.
            if is_transient(exc):
                self._record(False)
            else:
                with self._lock:
                    self._probe_out = False
            raise
        finally:
            with self._lock:
                self._active -= 1
            self._sem.release()
        self._record(True)
        return result

    def _count_retry(self) -> None:
        with self._lock:
            self.counters["retries"] += 1

    # ------------------------------------------------------------ introspection
    @property
    def state(self) -> str:
        with self._lock:
            if self._state == OPEN and time.monotonic() - self._opened_at >= self.cooldown_s:
                return HALF_OPEN
            return self._state

    def stats(self) -> dict:
        state = self.state  # takes the lock itself; read it before re-acquiring
        with self._lock:
            return {"state": state,
                    "consecutive_failures": self._failures, "in_flight": self._active,
                    "max_concurrency": self.max_concurrency,
                    "cached_entries": len(self._cache), **self.counters}

    def reset(self) -> None:
        with self._lock:
            self._cache.clear()
            self._inflight.clear()
            self._state, self._failures, self._probe_out = CLOSED, 0, False
            for k in self.counters:
                self.counters[k] = 0


# One per provider. Cache TTLs follow how fast the data changes: quotes move by the
# minute, news by the hour, filings by the quarter.
# Company research repeats the same subject searches across specialists and users;
# an hour keeps the free search quota for new companies.
TAVILY = Upstream("tavily", max_concurrency=4, cache_ttl_s=3600)
YAHOO = Upstream("yahoo_finance", max_concurrency=4, cache_ttl_s=60)
STOOQ = Upstream("stooq", max_concurrency=2, cache_ttl_s=60)
SEC_EDGAR = Upstream("sec_edgar", max_concurrency=2, cache_ttl_s=6 * 3600,
                     deadline_s=60)  # SEC asks for <= 10 req/s; filings are large

# Company websites: many unrelated hosts behind one name, so no shared breaker (one
# dead startup site must not stop reading the next); the bulkhead and cache still apply.
WEBSITES = Upstream("websites", max_concurrency=6, failure_threshold=0, cache_ttl_s=6 * 3600,
                    attempts=2, deadline_s=60)

REGISTRY: dict[str, Upstream] = {u.name: u for u in (TAVILY, YAHOO, STOOQ, SEC_EDGAR,
                                                     WEBSITES)}


def stats() -> dict[str, dict]:
    return {name: u.stats() for name, u in REGISTRY.items()}


def reset_all() -> None:
    for u in REGISTRY.values():
        u.reset()
