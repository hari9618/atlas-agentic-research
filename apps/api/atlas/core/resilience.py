"""Retry + degradation policy (design §5).

Two layers keep a run alive on a free-tier stack:

1. ``retry_call`` retries **transient** failures only — rate limits (429), timeouts,
   connection drops, HTTP 5xx — with exponential backoff + jitter and a hard cap on
   attempts and per-wait seconds. A bad request, an auth error or a parse error is
   never retried: repeating it can only waste quota.
2. ``run_or_degrade`` is the per-node safety net: once retries are exhausted the node
   returns a documented fallback (default plan, "agent unavailable" finding, neutral
   debate stub, empty tool result) instead of killing the whole run.

Retry budget (bounded on purpose):

* LLM calls: the Groq SDK already retries 4x honouring Retry-After (``atlas.llm``);
  ``chat()`` wraps that in ``LLM_ATTEMPTS`` = 2 outer attempts → at most 10 requests.
* Tools (Tavily, Stooq, EDGAR): no inner retries, so ``TOOL_ATTEMPTS`` = 3.
* Waits: ``base * 2**n`` + jitter, capped at ``ATLAS_RETRY_MAX_WAIT`` (default 20s).
  Tests set ``ATLAS_RETRY_BASE_WAIT=0`` so the suite never sleeps.

Every retry is logged at WARNING, which lands in the run's logs/trace.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any, TypeVar

from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

log = logging.getLogger("atlas.resilience")

T = TypeVar("T")

LLM_ATTEMPTS = 2   # outer attempts around the SDK's own 4 Retry-After-aware retries
TOOL_ATTEMPTS = 3  # tools have no inner retry layer

_TRANSIENT_STATUS = {408, 425, 429}  # request timeout, too early, rate limited
_TRANSIENT_NAMES = (
    "ratelimit", "timeout", "timedout", "connecterror", "connectionerror",
    "apiconnectionerror", "remoteprotocolerror", "readerror", "writeerror",
    "networkerror", "internalservererror", "serviceunavailable",
)
_TRANSIENT_TEXT = ("rate limit", "rate_limit", "too many requests", "timed out", "timeout",
                   "temporarily unavailable", "connection reset", "connection aborted")


def _status_code(exc: BaseException) -> int | None:
    """HTTP status from the exception itself or its attached response, if any."""
    for holder in (exc, getattr(exc, "response", None)):
        code = getattr(holder, "status_code", None)
        if isinstance(code, int):
            return code
    return None


def is_transient(exc: BaseException) -> bool:
    """True for failures worth retrying: 429, timeouts, connection errors, HTTP 5xx."""
    # Typed checks first — cheapest and most precise.
    try:
        import httpx

        if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError,
                            httpx.RemoteProtocolError)):
            return True
    except ImportError:  # pragma: no cover - httpx is a hard dependency
        pass
    try:
        import groq

        if isinstance(exc, (groq.RateLimitError, groq.APITimeoutError,
                            groq.APIConnectionError, groq.InternalServerError)):
            return True
    except ImportError:  # pragma: no cover - groq ships with langchain-groq
        pass
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True

    code = _status_code(exc)
    if code is not None:
        return code in _TRANSIENT_STATUS or 500 <= code < 600

    # Last resort for wrapped/third-party errors: class name, then message.
    name = type(exc).__name__.lower()
    if any(n in name for n in _TRANSIENT_NAMES):
        return True
    msg = str(exc).lower()
    return any(t in msg for t in _TRANSIENT_TEXT)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _log_retry(label: str) -> Callable[[RetryCallState], None]:
    def _before_sleep(rs: RetryCallState) -> None:
        exc = rs.outcome.exception() if rs.outcome else None
        wait = rs.next_action.sleep if rs.next_action else 0.0
        log.warning("retry %s: attempt %d failed (%s: %s); retrying in %.1fs",
                    label, rs.attempt_number, type(exc).__name__, exc, wait)
    return _before_sleep


def retry_call(
    fn: Callable[..., T],
    *args: Any,
    attempts: int = TOOL_ATTEMPTS,
    label: str | None = None,
    base_wait: float | None = None,
    max_wait: float | None = None,
    **kwargs: Any,
) -> T:
    """Call ``fn(*args, **kwargs)``, retrying transient errors with backoff + jitter.

    Non-transient errors propagate immediately; after the last attempt the final
    transient error is re-raised (callers decide whether to degrade).
    """
    base = _env_float("ATLAS_RETRY_BASE_WAIT", 1.0) if base_wait is None else base_wait
    cap = _env_float("ATLAS_RETRY_MAX_WAIT", 20.0) if max_wait is None else max_wait
    name = label or getattr(fn, "__name__", "call")
    retryer = Retrying(
        stop=stop_after_attempt(max(1, attempts)),
        wait=wait_exponential_jitter(initial=base, max=cap, jitter=base),
        retry=retry_if_exception(is_transient),
        before_sleep=_log_retry(name),
        reraise=True,
    )
    return retryer(fn, *args, **kwargs)


def run_or_degrade(
    fn: Callable[..., T],
    *args: Any,
    fallback: T | Callable[[BaseException], T],
    label: str,
    **kwargs: Any,
) -> T:
    """Run ``fn``; on any failure log it and return ``fallback`` instead of raising.

    ``fallback`` may be a value or a callable taking the exception, so a node can
    build a degraded update that mentions what went wrong.
    """
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        log.warning("%s degraded after failure (%s: %s)", label, type(exc).__name__, exc)
        return fallback(exc) if callable(fallback) else fallback
