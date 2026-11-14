"""Who may do how much: per-plan quotas, abuse limits and run admission control.

Three layers, cheapest first:

1. **Per-IP / per-account rate limits** (shared across instances, see
   ``core.coordination``) — brute-force and quota protection.
2. **A global research budget** — guests can be minted per IP, and IPs can be rotated,
   so the LLM spend is also capped for the whole deployment.
3. **Admission control** — a run streams for minutes and holds a worker thread plus
   parallel LLM calls. Each user gets a bounded number of concurrent runs (a shared
   lease), and each *instance* a bounded number of runs in total (``RunSlots``); a
   full instance answers 503 + ``Retry-After`` instead of degrading every run on it.
"""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass

from fastapi import Request
from starlette.concurrency import run_in_threadpool

from ..config import get_settings
from ..core.coordination import Rule, get_coordinator
from ..errors import ApiError, retry_after_error

HOUR = 3600.0
MINUTE = 60.0
RUN_LEASE_TTL_S = 15 * MINUTE  # longest a run may hold a slot if its process dies


@dataclass(frozen=True)
class Plan:
    research: Rule
    resume: Rule
    concurrent_runs: int


PLANS: dict[str, Plan] = {
    "guest": Plan(Rule("research.guest", 3, HOUR), Rule("resume.guest", 10, HOUR), 1),
    "user": Plan(Rule("research.user", 12, HOUR), Rule("resume.user", 40, HOUR), 1),
    "admin": Plan(Rule("research.admin", 60, HOUR), Rule("resume.admin", 200, HOUR), 3),
}

# Abuse limits that don't depend on who you are.
IP_GLOBAL = Rule("ip", 240, MINUTE)                 # every API request, per IP
LOGIN_IP = Rule("login.ip", 10, MINUTE)
LOGIN_ACCOUNT = Rule("login.account", 8, 15 * MINUTE)
REGISTER_IP = Rule("register.ip", 5, HOUR)
GUEST_IP = Rule("guest.ip", 6, HOUR)
GUEST_GLOBAL = Rule("guest.global", 120, HOUR)
REFRESH_IP = Rule("refresh.ip", 60, MINUTE)
RESEARCH_GLOBAL = Rule("research.global", 300, HOUR)  # caps total LLM spend
IMPROVE = Rule("improve", 6, HOUR)


def plan_for(role: str) -> Plan:
    return PLANS.get(role, PLANS["guest"])


def client_ip_from_scope(scope: dict) -> str:
    """The end user's IP, whatever sits in front of the API.

    Behind Render's (or nginx's) load balancer the TCP peer is the balancer, so every
    user would share one IP and one bucket — the guest limit would be site-wide. The
    *left-most* ``X-Forwarded-For`` entry is the original client: the browser for
    direct API calls, and the address the Next.js BFF forwards for /auth calls (where
    the right-most entries are Vercel and Render). Read here rather than relying on
    uvicorn's ``--proxy-headers`` so it holds however the host's start command is set.

    Trade-off (docs/security.md): a direct caller can forge this header to rotate
    "IPs". Per-IP limits are therefore only the first layer; per-account limits and
    the global guest / research budgets cap what forging can achieve.
    """
    for name, value in scope.get("headers") or []:
        if name == b"x-forwarded-for":
            first = value.decode("latin-1").split(",")[0].strip()
            if first and len(first) <= 45 and all(c in "0123456789abcdefABCDEF.:" for c in first):
                return first
            break
    client = scope.get("client")
    return client[0] if client else "unknown"


def client_ip(request: Request) -> str:
    return client_ip_from_scope(request.scope)


async def enforce(rule: Rule, key: str, *, what: str = "requests") -> None:
    """Count one request against ``rule`` for ``key``; raise 429 when over.

    The check may be a network round-trip (Redis/Postgres), so it runs in the thread
    pool — never block the event loop that is streaming other users' runs."""
    if not get_settings().rate_limits_enabled:
        return
    decision = await run_in_threadpool(get_coordinator().hit, key, rule)
    if not decision.allowed:
        minutes = decision.retry_after / 60
        when = f"{int(minutes + 0.999)} min" if minutes >= 1 else \
            f"{int(decision.retry_after + 0.999)} s"
        raise retry_after_error(429, "rate_limited",
                                f"Too many {what}. Try again in {when}.",
                                decision.retry_after)


class RunSlots:
    """Per-process cap on concurrently streaming runs (thread-safe counter)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.active = 0

    def try_take(self) -> bool:
        with self._lock:
            if self.active >= max(1, get_settings().max_concurrent_runs):
                return False
            self.active += 1
            return True

    def give_back(self) -> None:
        with self._lock:
            self.active = max(0, self.active - 1)


RUN_SLOTS = RunSlots()


class RunTicket:
    """What a streaming run holds: one instance slot and one of the user's run leases.
    ``release`` is idempotent — the stream's ``finally`` and error paths may both call it."""

    def __init__(self, lease_key: str | None, owner: str) -> None:
        self._lease_key = lease_key
        self._owner = owner
        self._released = False
        self._lock = threading.Lock()

    def release(self) -> None:
        with self._lock:
            if self._released:
                return
            self._released = True
        RUN_SLOTS.give_back()
        if self._lease_key:
            get_coordinator().release(self._lease_key, self._owner)


async def admit_run(user_id: str, role: str) -> RunTicket:
    """Reserve capacity for one run or raise 503 ``busy`` / 409 ``run_in_progress``."""
    if not RUN_SLOTS.try_take():
        raise retry_after_error(503, "busy",
                                "Atlas is at capacity right now. Please retry shortly.", 20)
    if not get_settings().rate_limits_enabled:
        return RunTicket(None, "")
    owner = secrets.token_hex(8)
    coordinator = get_coordinator()
    for slot in range(plan_for(role).concurrent_runs):
        key = f"run:{user_id}:{slot}"
        if await run_in_threadpool(coordinator.acquire, key, owner, RUN_LEASE_TTL_S):
            return RunTicket(key, owner)
    RUN_SLOTS.give_back()
    raise ApiError(409, "run_in_progress",
                   "You already have a research run in progress. Let it finish (or close "
                   "its tab) before starting another.")
