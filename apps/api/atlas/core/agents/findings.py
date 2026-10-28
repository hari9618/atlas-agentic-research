"""Turn an LLM's cited-findings reply into grounded finding dicts.

Shared by the four specialists and the reviewer-driven ``revise_research`` node so
the grounding contract is enforced in one place: a finding's citation is resolved
from the evidence index the model pointed at — never from text the model wrote —
and the cited evidence text rides along for claim-level verification.
"""

from __future__ import annotations

from ..rag.types import RetrievedChunk
from .base import extract_json

# How much of the cited chunk rides on the finding for claim verification. The WHOLE
# chunk (corpus chunks are ~1.1-1.5k chars): an earlier 500-char cut dropped figures
# the model had been shown (Helios' "$4.2 billion" sits at char 516 of its 10-K chunk),
# so true claims were scored "unsupported". Capped only to bound checkpoint size.
_EVIDENCE_CHARS = 2000


def findings_instructions(count: str = "2-4") -> str:
    """The extraction contract appended to every findings prompt."""
    return (
        f"Extract {count} findings. Each finding MUST be grounded in the evidence and cite "
        "the index it came from. Include concrete figures, names and dates only when the "
        "evidence states them — never invent numbers. Return ONLY JSON: "
        '[{"claim": "...", "citation_index": 1, "confidence": 0.0-1.0}]'
    )


def entity_rule(target: str) -> str:
    """Prompt line keeping the model on the right company (same-name collisions)."""
    if not target:
        return ""
    return (f"Only use evidence about {target}; ignore anything about other companies with "
            "similar names, and do not use evidence that is ambiguous about which company "
            "it describes. ")


def _as_float(value, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _as_index(value) -> int | None:
    try:
        return int(str(value).strip().strip("[]"))
    except (TypeError, ValueError):
        return None


def parse_findings(agent: str, raw: str, chunks: list[RetrievedChunk]) -> list[dict]:
    """Parse the model reply; each claim's citation comes from ``chunks[index-1]``."""
    items = extract_json(raw, default=[])
    if isinstance(items, dict):  # tolerate {"findings": [...]}
        items = items.get("findings", [])
    findings: list[dict] = []
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        claim = str(it.get("claim", "")).strip()
        if not claim:
            continue
        idx = _as_index(it.get("citation_index", 1))
        cite, ev_text, ev_id = "n/a", "", ""
        if idx is not None and 1 <= idx <= len(chunks):
            ch = chunks[idx - 1].chunk
            # Carry the cited evidence text on the finding so claim-level citation
            # verification can check entailment deterministically (no re-retrieval).
            cite, ev_text, ev_id = ch.citation(), ch.text[:_EVIDENCE_CHARS], ch.chunk_id
        findings.append({
            "agent": agent,
            "claim": claim,
            "citation": cite,
            "evidence_text": ev_text,
            "evidence_id": ev_id,
            "confidence": _as_float(it.get("confidence", 0.6), 0.6),
        })
    return findings


def unavailable_finding(agent: str, reason: str = "temporary error") -> dict:
    """The degraded output of a specialist whose retries were exhausted (design §5)."""
    return {
        "agent": agent,
        "claim": f"The {agent.replace('_', ' ')} analysis is unavailable for this run ({reason}).",
        "citation": "n/a",
        "evidence_text": "",
        "evidence_id": "",
        "confidence": 0.0,
        "unavailable": True,
    }
