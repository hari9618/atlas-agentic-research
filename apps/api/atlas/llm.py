"""Groq LLM client (GPT-OSS-120B by default) shared across all Atlas agents.

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
def get_llm(
    temperature: float | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    reasoning_effort: str | None = None,
) -> ChatGroq:
    """Return a cached ChatGroq client.

    Args:
        temperature: optional override (e.g. 0.7 for the creative debate agents,
            0.0 for the deterministic judge). Defaults to the configured value.
        model: optional model override (e.g. a cheaper model for the summarizer).
            Defaults to the configured GROQ_MODEL.
        max_tokens: optional output budget override (e.g. the synthesizer's larger
            structured-report budget). Part of the cache key, so each budget gets
            its own client.
        reasoning_effort: "low" / "medium" / "high" for reasoning models (gpt-oss).
            Hidden reasoning tokens count against ``max_tokens``: on a long evidence
            prompt, default-effort reasoning used 1023 of a specialist's 1024 tokens,
            and one token more cut the JSON reply off, losing every finding. Extraction
            tasks pass "low". Ignored for non-reasoning models.
    """
    settings = get_settings()
    if not settings.llm_configured:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to apps/api/.env "
            "(get a free key at https://console.groq.com/keys)."
        )

    temp = settings.llm_temperature if temperature is None else temperature
    model_name = model or settings.groq_model
    budget = settings.llm_max_tokens if max_tokens is None else max_tokens
    log.info("Building ChatGroq client model=%s temp=%s max_tokens=%s", model_name, temp, budget)
    return ChatGroq(
        api_key=settings.groq_api_key,
        model=model_name,
        temperature=temp,
        max_tokens=budget,
        # Sent as a raw body field: the pinned groq SDK (0.11) predates a named
        # `reasoning_effort` argument and raises TypeError on it.
        model_kwargs=(
            {"extra_body": {"reasoning_effort": reasoning_effort}}
            if reasoning_effort and "gpt-oss" in model_name else {}
        ),
        # Retry budget, layer 1 of 2. The free tier caps tokens-per-minute (8k on
        # gpt-oss-120b) and the four specialists fire in parallel, so bursts hit a
        # 429. The Groq SDK honours Retry-After on 429/5xx/timeouts: 1 try + 4
        # retries. Layer 2 is ``atlas.core.resilience`` (``LLM_ATTEMPTS`` = 2 outer
        # attempts in ``chat()``), so the worst case is 2 x 5 = 10 requests per
        # logical LLM call before the node degrades — bounded, not unbounded.
        max_retries=4,
        request_timeout=60,
    )
