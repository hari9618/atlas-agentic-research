"""Process-level HTTP middleware, written as pure ASGI.

Pure ASGI rather than ``BaseHTTPMiddleware`` because research runs are long SSE
streams: wrapping them in a ``BaseHTTPMiddleware`` buffers them through an extra task
and interferes with client-disconnect cancellation.

* **Request ID** — honours an incoming ``X-Request-ID`` (from the load balancer) or
  mints one, returns it, and puts it on the access-log line, so one request can be
  followed across nginx → API instance → logs.
* **Per-IP rate limit** — a coarse shield on every route except health probes.
* **Security headers** — nosniff, no framing, no referrer leakage, HSTS in prod.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid

from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .config import get_settings
from .core.coordination import get_coordinator
from .errors import retry_after_error
from .security import limits

log = logging.getLogger("atlas.access")

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_UNLIMITED = ("/health", "/docs", "/openapi.json", "/redoc")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        settings = get_settings()
        headers = dict(scope.get("headers") or [])
        incoming = headers.get(b"x-request-id", b"").decode("latin-1")
        request_id = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        path: str = scope.get("path", "")
        method: str = scope.get("method", "")
        client = limits.client_ip_from_scope(scope)
        started = time.perf_counter()
        status_holder = {"status": 500}

        extra = [
            (b"x-request-id", request_id.encode()),
            (b"x-content-type-options", b"nosniff"),
            (b"x-frame-options", b"DENY"),
            (b"referrer-policy", b"no-referrer"),
        ]
        if settings.is_production:
            extra.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))

        async def send_wrapped(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                message["headers"] = list(message.get("headers", [])) + extra
            await send(message)

        if (settings.rate_limits_enabled and method != "OPTIONS"
                and not path.startswith(_UNLIMITED)):
            decision = await run_in_threadpool(get_coordinator().hit, client,
                                               limits.IP_GLOBAL)
            if not decision.allowed:
                err = retry_after_error(429, "rate_limited",
                                        "Too many requests from your network. Slow down.",
                                        decision.retry_after)
                body = json.dumps(err.body()).encode()
                await send_wrapped({"type": "http.response.start", "status": 429, "headers": [
                    (b"content-type", b"application/json"),
                    (b"retry-after", err.headers["Retry-After"].encode()),
                ]})
                await send({"type": "http.response.body", "body": body})
                log.info("%s %s 429 ip-limit client=%s rid=%s", method, path, client,
                         request_id)
                return

        try:
            await self.app(scope, receive, send_wrapped)
        finally:
            if not path.startswith("/health"):
                log.info("%s %s %d %.0fms client=%s rid=%s", method, path,
                         status_holder["status"], (time.perf_counter() - started) * 1000,
                         client, request_id)
