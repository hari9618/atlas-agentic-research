"""Shared helpers for agent nodes: the traced LLM call, JSON extraction, evidence fmt.

Every LLM call goes through ``chat()`` so it is uniformly traced in Langfuse with a
readable run name. Nodes call ``llm_ready()`` to degrade gracefully (deterministic
stubs) when no GROQ key is present — which keeps the whole graph runnable offline/CI.
"""

from __future__ import annotations

import json
import logging
import os

from langchain_core.messages import HumanMessage, SystemMessage

from ...config import get_settings
from ...llm import get_llm
from ...observability import langchain_callbacks
from ..rag.types import RetrievedChunk

log = logging.getLogger("atlas.agents")


def llm_ready() -> bool:
    """True when a real LLM call should be made.

    ATLAS_OFFLINE_LLM=1 forces the deterministic stub path (used by tests/CI so the
    whole graph runs without hitting the live key).
    """
    if os.getenv("ATLAS_OFFLINE_LLM") == "1":
        return False
    return get_settings().llm_configured


def chat(prompt: str, *, system: str | None = None, temperature: float = 0.2,
         run_name: str = "agent") -> str:
    """One traced LLM turn. Raises if no key — guard with llm_ready() first."""
    llm = get_llm(temperature=temperature)
    msgs: list = []
    if system:
        msgs.append(SystemMessage(content=system))
    msgs.append(HumanMessage(content=prompt))
    resp = llm.invoke(msgs, config={"callbacks": langchain_callbacks(), "run_name": run_name})
    return (resp.content if hasattr(resp, "content") else str(resp)).strip()


def format_evidence(chunks: list[RetrievedChunk]) -> str:
    """Number evidence so the LLM can cite by index [1], [2], ..."""
    return "\n\n".join(
        f"[{i + 1}] ({c.chunk.citation()}) {c.text[:600]}" for i, c in enumerate(chunks)
    )


def extract_json(text: str, default):
    """Best-effort: pull the first JSON object/array out of an LLM reply.

    Structure-aware: tries whichever of ``{`` / ``[`` appears FIRST, so an object
    that contains an array (e.g. {"confidence":.., "uncertainties":[..]}) isn't
    mis-parsed as the inner array.
    """
    openers = [(text.find(o), o, c) for o, c in (("{", "}"), ("[", "]")) if text.find(o) != -1]
    for _, opener, closer in sorted(openers):  # earliest-appearing structure first
        try:
            start, end = text.index(opener), text.rindex(closer) + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError):
            continue
    return default
