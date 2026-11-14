"""GCRA rate limiting and leases on every coordination backend.

Memory always runs. Postgres and Redis run when ``ATLAS_TEST_DATABASE_URL`` /
``ATLAS_TEST_REDIS_URL`` point at a real server (CI provides both as service
containers), because their atomicity lives in SQL / Lua that only a real server runs.
"""

from __future__ import annotations

import os
import threading
import uuid

import pytest

from atlas.core.coordination import (
    Coordinator,
    MemoryBackend,
    PostgresBackend,
    RedisBackend,
    Rule,
    _gcra,
)

PG_URL = os.getenv("ATLAS_TEST_DATABASE_URL", "")
REDIS_URL = os.getenv("ATLAS_TEST_REDIS_URL", "")


def _backends():
    yield pytest.param(lambda: MemoryBackend(), id="memory")
    yield pytest.param(_pg, id="postgres",
                       marks=pytest.mark.skipif(not PG_URL, reason="ATLAS_TEST_DATABASE_URL unset"))
    yield pytest.param(lambda: RedisBackend.from_url(REDIS_URL), id="redis",
                       marks=pytest.mark.skipif(not REDIS_URL, reason="ATLAS_TEST_REDIS_URL unset"))
    # The same Lua script on an emulator, so it is exercised everywhere. Lua's 14-digit
    # number formatting once rounded stored timestamps and refused a burst's last
    # request; only running the script itself catches that class of bug.
    yield pytest.param(_fake_redis, id="fakeredis",
                       marks=pytest.mark.skipif(not _has_fakeredis(),
                                                reason="fakeredis not installed"))


def _has_fakeredis() -> bool:
    try:
        import fakeredis  # noqa: F401
        import lupa  # noqa: F401
    except ImportError:
        return False
    return True


def _fake_redis():
    import fakeredis

    return RedisBackend(fakeredis.FakeRedis(decode_responses=True))


def _pg():
    from atlas.core.persistence import open_pg_pool

    return PostgresBackend(open_pg_pool(PG_URL))


def test_gcra_allows_a_burst_then_spaces_requests():
    rule = Rule("t", 3, 30.0)  # burst of 3, then one per 10 s
    tat, now = None, 1000.0
    results = []
    for _ in range(4):
        allowed, tat_next, d = _gcra(tat, now, rule)
        results.append((allowed, d.remaining))
        if allowed:
            tat = tat_next
    assert results == [(True, 2), (True, 1), (True, 0), (False, 0)]
    _, _, denied = _gcra(tat, now, rule)
    assert denied.retry_after == pytest.approx(10.0)
    allowed, _, _ = _gcra(tat, now + 10.0, rule)  # one interval later: one more
    assert allowed


@pytest.mark.parametrize("make", _backends())
def test_rate_limit_is_enforced(make):
    backend = make()
    rule = Rule(f"t{uuid.uuid4().hex[:6]}", 5, 60.0)
    decisions = [backend.hit("k", rule) for _ in range(6)]
    assert [d.allowed for d in decisions] == [True] * 5 + [False]
    assert decisions[0].remaining == 4
    assert 0 < decisions[-1].retry_after <= 12.5
    assert backend.hit("other-key", rule).allowed  # keys are independent


@pytest.mark.parametrize("make", _backends())
def test_rate_limit_is_atomic_under_concurrency(make):
    """The whole point of the shared backends: N racing requests get exactly
    ``limit`` approvals, never more."""
    backend = make()
    rule = Rule(f"c{uuid.uuid4().hex[:6]}", 10, 3600.0)
    allowed: list[bool] = []
    lock = threading.Lock()

    def worker():
        for _ in range(5):
            d = backend.hit("shared", rule)
            with lock:
                allowed.append(d.allowed)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(allowed) == 10 and len(allowed) == 40


@pytest.mark.parametrize("make", _backends())
def test_leases_are_exclusive_until_released_or_expired(make):
    backend = make()
    key = f"lease-{uuid.uuid4().hex[:6]}"
    assert backend.acquire(key, "a", 30)
    assert not backend.acquire(key, "b", 30)
    backend.release(key, "b")  # not the owner: no effect
    assert not backend.acquire(key, "b", 30)
    backend.release(key, "a")
    assert backend.acquire(key, "b", 30)

    short = f"short-{uuid.uuid4().hex[:6]}"
    assert backend.acquire(short, "a", 0.05)
    import time

    time.sleep(0.2)
    assert backend.acquire(short, "b", 30)  # expired: a crashed holder can't block forever


def test_coordinator_fails_open_when_the_store_is_down():
    class Broken:
        name = "broken"

        def hit(self, *_):
            raise ConnectionError("redis down")

        def acquire(self, *_):
            raise ConnectionError("redis down")

        def release(self, *_):
            raise ConnectionError("redis down")

    c = Coordinator(Broken())
    assert c.hit("k", Rule("r", 1, 60)).allowed
    assert c.acquire("k", "o", 10)
    c.release("k", "o")  # must not raise


@pytest.mark.parametrize("make", _backends())
def test_rate_limit_counts_down_exactly_over_many_buckets(make):
    """Regression: remaining must count 4,3,2,1,0 and the 5th request must pass —
    every time, not just when floating-point rounding happens to fall the right way."""
    backend = make()
    for _ in range(50):
        rule = Rule(f"r{uuid.uuid4().hex[:6]}", 5, 60.0)
        decisions = [backend.hit("k", rule) for _ in range(6)]
        assert [d.remaining for d in decisions[:5]] == [4, 3, 2, 1, 0]
        assert [d.allowed for d in decisions] == [True] * 5 + [False]

