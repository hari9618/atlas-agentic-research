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
from ..resilience import LLM_ATTEMPTS, retry_call

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
         run_name: str = "agent", max_tokens: int | None = None) -> str:
    """One traced LLM turn. Raises if no key — guard with llm_ready() first.

    Transient failures (429 / timeout / 5xx) that survive the SDK's own retries get
    ``LLM_ATTEMPTS`` outer attempts with backoff (see ``atlas.core.resilience``);
    anything else propagates so the calling node can degrade.
    """
    llm = get_llm(temperature=temperature, max_tokens=max_tokens)
    msgs: list = []
    if system:
        msgs.append(SystemMessage(content=system))
    msgs.append(HumanMessage(content=prompt))
    config = {"callbacks": langchain_callbacks(), "run_name": run_name}
    resp = retry_call(llm.invoke, msgs, config=config, attempts=LLM_ATTEMPTS, label=run_name)
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


def salvage_json_object(text: str) -> dict | None:
    """Recover the complete top-level fields of a JSON object that was cut off.

    When a reply hits the token limit mid-object, ``json.loads`` rejects all of it.
    But every top-level field written before the cut is intact: scan from the first
    ``{`` tracking strings and nesting, remember where the last top-level member
    ended (a ``,`` at depth 1), and close the object there. Returns None if not even
    one member is complete.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth, in_str, escaped, last_cut = 0, False, False, None
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
            if depth == 0:  # the object actually closed — nothing to salvage
                try:
                    parsed = json.loads(text[start:i + 1])
                except (ValueError, json.JSONDecodeError):
                    return None
                return parsed if isinstance(parsed, dict) else None
        elif ch == "," and depth == 1:
            last_cut = i
    if last_cut is None:
        return None
    try:
        parsed = json.loads(text[start:last_cut] + "}")
    except (ValueError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None
