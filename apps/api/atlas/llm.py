"""Groq LLM client (Llama 3.3 70B) shared across all Atlas agents.

A single factory builds a ``ChatGroq`` instance so every agent uses the same
configured model, temperature, and token budget. Langfuse callbacks are attached
at call time (see ``atlas.observability``), not baked into the client, so a
single client can be traced under different runs/sessions.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from langchain_groq import ChatGroq

from .config import get_settings

log = logging.getLogger("atlas.llm")


@lru_cache
def get_llm(temperature: float | None = None, model: str | None = None) -> ChatGroq:
    """Return a cached ChatGroq client.

    Args:
        temperature: optional override (e.g. 0.7 for the creative debate agents,
            0.0 for the deterministic judge). Defaults to the configured value.
        model: optional model override (e.g. a cheaper model for the summarizer).
            Defaults to the configured GROQ_MODEL.
    """
    settings = get_settings()
    if not settings.llm_configured:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to apps/api/.env "
            "(get a free key at https://console.groq.com/keys)."
        )

    temp = settings.llm_temperature if temperature is None else temperature
    model_name = model or settings.groq_model
    log.info("Building ChatGroq client model=%s temp=%s", model_name, temp)
    return ChatGroq(
        api_key=settings.groq_api_key,
        model=model_name,
        temperature=temp,
        max_tokens=settings.llm_max_tokens,
    )
