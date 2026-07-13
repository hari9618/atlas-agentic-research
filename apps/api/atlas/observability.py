"""Langfuse observability wiring.

Atlas traces every agent hop, tool call, and token/cost figure. This module
exposes a single ``get_langfuse_handler()`` that returns a LangChain callback
handler when Langfuse is configured, or ``None`` otherwise — so the rest of the
app can stay oblivious to whether tracing is on.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from .config import get_settings

log = logging.getLogger("atlas.observability")


@lru_cache
def get_langfuse_handler() -> Any | None:
    """Return a Langfuse CallbackHandler, or None if tracing is disabled.

    Cached so we reuse one client. Import is done lazily so the package stays
    importable even if langfuse is not installed in a minimal environment.
    """
    settings = get_settings()
    if not settings.langfuse_configured:
        log.info("Langfuse not configured — tracing disabled (set keys in .env to enable).")
        return None

    try:
        from langfuse.callback import CallbackHandler

        handler = CallbackHandler(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        log.info("Langfuse tracing enabled → %s", settings.langfuse_host)
        return handler
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("Failed to initialise Langfuse handler: %s", exc)
        return None


def langchain_callbacks() -> list[Any]:
    """Convenience: a callbacks list to pass into LangChain/LangGraph .invoke()."""
    handler = get_langfuse_handler()
    return [handler] if handler else []
