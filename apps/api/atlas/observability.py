"""Langfuse observability wiring (Langfuse Python SDK v5, OpenTelemetry-based).

Atlas traces every agent hop, tool call, and token/cost figure. This module owns the
one Langfuse client and exposes ``get_langfuse_handler()``, a LangChain callback
handler when Langfuse is configured or ``None`` otherwise, so the rest of the app
can stay oblivious to whether tracing is on.

Why v5: Langfuse Cloud retired the legacy ingestion API used by SDK v2 (sunset
2026-11-16, removed 2026-11-19). v5 sends traces over OpenTelemetry; scores use the
same client (``create_score``), see ``atlas.eval.langfuse_scores``.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from .config import get_settings

log = logging.getLogger("atlas.observability")


@lru_cache
def get_langfuse_client() -> Any | None:
    """The process-wide Langfuse client, or None when tracing is off.

    Import is lazy so the package stays importable without langfuse installed.
    """
    settings = get_settings()
    if not settings.langfuse_configured:
        log.info("Langfuse not configured — tracing disabled (set keys in .env to enable).")
        return None
    try:
        from langfuse import Langfuse

        client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            base_url=settings.langfuse_host,
        )
        log.info("Langfuse tracing enabled → %s", settings.langfuse_host)
        return client
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("Failed to initialise Langfuse: %s", exc)
        return None


@lru_cache
def get_langfuse_handler() -> Any | None:
    """A LangChain CallbackHandler bound to the client above, or None."""
    if get_langfuse_client() is None:
        return None
    try:
        from langfuse.langchain import CallbackHandler

        # v5 finds the client registered for this public key (created above).
        return CallbackHandler(public_key=get_settings().langfuse_public_key)
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("Failed to initialise the Langfuse LangChain handler: %s", exc)
        return None


def langchain_callbacks() -> list[Any]:
    """Convenience: a callbacks list to pass into LangChain/LangGraph .invoke()."""
    handler = get_langfuse_handler()
    return [handler] if handler else []
