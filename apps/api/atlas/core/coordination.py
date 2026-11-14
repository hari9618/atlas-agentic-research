"""Cross-instance coordination: rate limits and leases.

Behind a load balancer, a limit kept in one process's memory is a limit per instance
— three replicas would quietly triple every quota. Rate-limit counters and "only one
of these at a time" leases therefore live in shared storage, picked in this order:

* **Redis** (``REDIS_URL``): one round-trip per check, via Lua scripts that run
  atomically on the server and read the server's clock (no skew between instances).
* **Postgres** (``DATABASE_URL``): a single atomic ``INSERT … ON CONFLICT DO UPDATE``
  per check, using the database clock; the tables are ``UNLOGGED`` (no WAL cost —
  losing counters in a crash is harmless).
* **Memory**: single-process dev and tests.

Rate limiting uses **GCRA** (the generic cell rate algorithm, a token bucket stored as
a single timestamp): smooth, burst-aware, and one value per key, so it is cheap on
every backend. A rule ``limit`` per ``period`` allows a burst of ``limit`` and then
one request every ``period / limit`` seconds.

Failure policy: if the shared store is unreachable, checks **fail open** (logged) —
an outage of the limiter must not become an outage of the product. The per-instance
admission limit (``limits.RunSlots``) still caps load in that case.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass
from typing import Any, Protocol

from ..config import get_settings
from .persistence import get_pg_pool, run_ddl

log = logging.getLogger("atlas.coordination")


@dataclass(frozen=True)
class Rule:
    name: str
    limit: int        # requests allowed in a burst…
    period_s: float   # …refilling fully over this many seconds

    @property
    def interval(self) -> float:
        return self.period_s / self.limit


@dataclass(frozen=True)
class Decision:
    allowed: bool
    remaining: int
    retry_after: float  # seconds until the next request would be allowed (0 if allowed)
    limit: int


def _gcra(tat: float | None, now: float, rule: Rule) -> tuple[bool, float, Decision]:
    """Pure GCRA step → (allowed, new_tat, decision). Shared by memory + tests."""
    tat = max(tat or now, now)
    new_tat = tat + rule.interval
    allow_at = new_tat - rule.period_s
    if now < allow_at:
        return False, tat, Decision(False, 0, allow_at - now, rule.limit)
    remaining = int((rule.period_s - (new_tat - now)) // rule.interval)
    return True, new_tat, Decision(True, max(0, remaining), 0.0, rule.limit)


class Backend(Protocol):
    """``hit`` keys are namespaced by ``rule.name`` inside each backend, so the same
    subject (a user id, an IP) has an independent bucket per rule."""

    name: str

    def hit(self, key: str, rule: Rule) -> Decision: ...
    def acquire(self, key: str, owner: str, ttl_s: float) -> bool: ...
    def release(self, key: str, owner: str) -> None: ...


# ------------------------------------------------------------------ memory
class MemoryBackend:
    name = "memory"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tat: dict[str, float] = {}
        self._leases: dict[str, tuple[str, float]] = {}

    def hit(self, key: str, rule: Rule) -> Decision:
        now = time.monotonic()
        key = f"{rule.name}:{key}"
        with self._lock:
            allowed, new_tat, decision = _gcra(self._tat.get(key), now, rule)
            if allowed:
                self._tat[key] = new_tat
            if len(self._tat) > 50_000:  # drop keys whose bucket is full again
                self._tat = {k: v for k, v in self._tat.items() if v > now}
            return decision

    def acquire(self, key: str, owner: str, ttl_s: float) -> bool:
        now = time.monotonic()
        with self._lock:
            held = self._leases.get(key)
            if held and held[1] > now and held[0] != owner:
                return False
            self._leases[key] = (owner, now + ttl_s)
            return True

    def release(self, key: str, owner: str) -> None:
        with self._lock:
            if self._leases.get(key, ("",))[0] == owner:
                self._leases.pop(key, None)


# ------------------------------------------------------------------ redis
_GCRA_LUA = """
local t = redis.call('TIME')
local now = tonumber(t[1]) + tonumber(t[2]) / 1000000
local interval = tonumber(ARGV[1])
local period = tonumber(ARGV[2])
local tat = tonumber(redis.call('GET', KEYS[1]) or now)
if tat < now then tat = now end
local new_tat = tat + interval
local allow_at = new_tat - period
if now < allow_at then
  return {0, tostring(allow_at - now), '0'}
end
redis.call('SET', KEYS[1], tostring(new_tat), 'PX', math.ceil((new_tat - now) * 1000))
return {1, '0', tostring(math.floor((period - (new_tat - now)) / interval))}
"""

_RELEASE_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) end
return 0
"""


class RedisBackend:
    name = "redis"

    def __init__(self, client: Any) -> None:
        self.r = client
        self._gcra = client.register_script(_GCRA_LUA)
        self._release = client.register_script(_RELEASE_LUA)

    @classmethod
    def from_url(cls, url: str) -> RedisBackend:
        import redis

        client = redis.Redis.from_url(url, socket_timeout=2, socket_connect_timeout=2,
                                      health_check_interval=30, decode_responses=True)
        client.ping()
        return cls(client)

    def hit(self, key: str, rule: Rule) -> Decision:
        ok, retry, remaining = self._gcra(keys=[f"atlas:rl:{rule.name}:{key}"],
                                          args=[rule.interval, rule.period_s])
        return Decision(bool(int(ok)), int(float(remaining)), float(retry), rule.limit)

    def acquire(self, key: str, owner: str, ttl_s: float) -> bool:
        return bool(self.r.set(f"atlas:lease:{key}", owner, nx=True,
                               px=int(ttl_s * 1000)))

    def release(self, key: str, owner: str) -> None:
        self._release(keys=[f"atlas:lease:{key}"], args=[owner])


# ------------------------------------------------------------------ postgres
_PG_DDL = [
    "CREATE UNLOGGED TABLE IF NOT EXISTS atlas_rate_limits ("
    "key TEXT PRIMARY KEY, tat DOUBLE PRECISION NOT NULL)",
    "CREATE UNLOGGED TABLE IF NOT EXISTS atlas_leases ("
    "key TEXT PRIMARY KEY, owner TEXT NOT NULL, expires_at DOUBLE PRECISION NOT NULL)",
]
_NOW = "extract(epoch from clock_timestamp())::double precision"

# Insert-or-advance in one statement. The WHERE on the UPDATE branch makes a denied
# request a no-op that returns no row; the database clock is the only clock used.
_PG_HIT = f"""
INSERT INTO atlas_rate_limits AS r (key, tat) VALUES (%(k)s, {_NOW} + %(i)s)
ON CONFLICT (key) DO UPDATE
   SET tat = GREATEST(r.tat, {_NOW}) + %(i)s
 WHERE GREATEST(r.tat, {_NOW}) + %(i)s - %(p)s <= {_NOW}
RETURNING tat, {_NOW} AS now
"""
_PG_PEEK = f"SELECT tat, {_NOW} AS now FROM atlas_rate_limits WHERE key = %(k)s"
_PG_ACQUIRE = f"""
INSERT INTO atlas_leases AS l (key, owner, expires_at) VALUES (%(k)s, %(o)s, {_NOW} + %(t)s)
ON CONFLICT (key) DO UPDATE SET owner = EXCLUDED.owner, expires_at = EXCLUDED.expires_at
 WHERE l.expires_at < {_NOW} OR l.owner = EXCLUDED.owner
RETURNING owner
"""


class PostgresBackend:
    name = "postgres"

    def __init__(self, pool: Any) -> None:
        self.pool = pool
        run_ddl(pool, _PG_DDL)
        self._hits = 0

    def hit(self, key: str, rule: Rule) -> Decision:
        params = {"k": f"{rule.name}:{key}", "i": rule.interval, "p": rule.period_s}
        with self.pool.connection() as conn:
            row = conn.execute(_PG_HIT, params).fetchone()
            if row is not None:
                remaining = (rule.period_s - (row["tat"] - row["now"])) // rule.interval
                decision = Decision(True, max(0, int(remaining)), 0.0, rule.limit)
            else:
                peek = conn.execute(_PG_PEEK, params).fetchone()
                retry = (peek["tat"] + rule.interval - rule.period_s - peek["now"]) if peek else 1
                decision = Decision(False, 0, max(0.0, float(retry)), rule.limit)
            self._hits += 1
            if self._hits % 1000 == 0:  # occasional sweep of buckets that refilled long ago
                conn.execute(f"DELETE FROM atlas_rate_limits WHERE tat < {_NOW} - 86400")
                conn.execute(f"DELETE FROM atlas_leases WHERE expires_at < {_NOW}")
        return decision

    def acquire(self, key: str, owner: str, ttl_s: float) -> bool:
        with self.pool.connection() as conn:
            row = conn.execute(_PG_ACQUIRE, {"k": key, "o": owner, "t": ttl_s}).fetchone()
        return row is not None

    def release(self, key: str, owner: str) -> None:
        with self.pool.connection() as conn:
            conn.execute("DELETE FROM atlas_leases WHERE key = %s AND owner = %s", (key, owner))


# ------------------------------------------------------------------ facade
class Coordinator:
    """Fail-open wrapper around the chosen backend."""

    def __init__(self, backend: Backend) -> None:
        self.backend = backend

    @property
    def name(self) -> str:
        return self.backend.name

    def hit(self, key: str, rule: Rule) -> Decision:
        try:
            return self.backend.hit(key, rule)
        except Exception as exc:
            log.warning("rate limiter (%s) unavailable, failing open: %s", self.name, exc)
            return Decision(True, rule.limit, 0.0, rule.limit)

    def acquire(self, key: str, owner: str, ttl_s: float) -> bool:
        try:
            return self.backend.acquire(key, owner, ttl_s)
        except Exception as exc:
            log.warning("lease store (%s) unavailable, failing open: %s", self.name, exc)
            return True

    def release(self, key: str, owner: str) -> None:
        try:
            self.backend.release(key, owner)
        except Exception as exc:  # the lease's TTL reclaims it anyway
            log.warning("lease release failed (%s): %s", self.name, exc)


def _build() -> Coordinator:
    settings = get_settings()
    if settings.redis_url:
        try:
            backend = RedisBackend.from_url(settings.redis_url)
            log.info("Coordination: Redis")
            return Coordinator(backend)
        except Exception as exc:
            log.warning("REDIS_URL set but Redis unreachable (%s) — trying Postgres.", exc)
    pool = get_pg_pool()
    if pool is not None:
        try:
            backend = PostgresBackend(pool)
            log.info("Coordination: Postgres")
            return Coordinator(backend)
        except Exception as exc:
            log.warning("Postgres coordination setup failed (%s) — using memory.", exc)
    log.info("Coordination: in-process memory (single instance only)")
    return Coordinator(MemoryBackend())


_lock = threading.Lock()
_coordinator: Coordinator | None = None


def get_coordinator() -> Coordinator:
    global _coordinator
    with _lock:
        if _coordinator is None:
            _coordinator = _build()
        return _coordinator


def set_coordinator(c: Coordinator | None) -> None:
    global _coordinator
    with _lock:
        _coordinator = c


def ceil_seconds(x: float) -> int:
    return max(1, math.ceil(x))
