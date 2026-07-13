"""Supervisor plan + the four specialist analyst agents.

Each specialist retrieves grounded evidence (CRAG hybrid RAG) for its angle, then
emits findings where **every claim cites a retrieved chunk** — provenance flows into
shared state so the synthesizer can build a cited report. With no GROQ key, each node
returns a deterministic stub so the graph still runs offline.
"""

from __future__ import annotations

import logging

from ..memory.procedural import ProceduralMemory
from ..rag.crag import corrective_retrieve
from ..state import ResearchState
from .base import chat, extract_json, format_evidence, llm_ready

log = logging.getLogger("atlas.agents.specialists")

# Procedural memory: each specialist may have a file-based playbook ("how to act").
_procedural = ProceduralMemory()

# name, focus query, system role
SPECIALISTS = [
    ("fundamentals", "financials revenue margins growth segments",
     "You are a fundamentals analyst. Focus on revenue, margins, growth, and segments."),
    ("news_sentiment", "recent news events sentiment deals announcements",
     "You are a news & sentiment analyst. Focus on recent events and their implications."),
    ("risk", "risks supply chain customer concentration regulatory competition",
     "You are a risk analyst. Focus on the key risks and their severity."),
    ("market", "competitors market position share competitive landscape",
     "You are a market/competitor analyst. Focus on competitive position and rivals."),
]


def plan_node(state: ResearchState) -> dict:
    """Supervisor: turn the question into a short list of focus areas."""
    query = state["query"]
    if not llm_ready():
        return {"plan": [s[0] for s in SPECIALISTS]}
    raw = chat(
        f"You are a research supervisor. The analyst desk will investigate this question:\n"
        f'"{query}"\n\nList 3-5 concise focus areas (one per line, no numbering).',
        temperature=0.3,
        run_name="supervisor.plan",
    )
    areas = [ln.strip("-• ").strip() for ln in raw.splitlines() if ln.strip()]
    return {"plan": areas[:5] or [s[0] for s in SPECIALISTS]}


def _make_specialist(name: str, focus: str, role: str):
    def node(state: ResearchState) -> dict:
        from ..graph import get_index  # late import avoids a cycle

        query = state["query"]
        chunks = corrective_retrieve(get_index(), f"{focus} {query}", top_k=4).chunks

        if not llm_ready():
            cite = chunks[0].chunk.citation() if chunks else "n/a"
            return {"findings": [{
                "agent": name, "claim": f"[offline stub] {name} analysis of: {query}",
                "citation": cite, "confidence": 0.5,
            }]}

        # Procedural memory (playbook) + episodic memory (prior related analyses).
        playbook = _procedural.get(name)
        system = role + (f"\n\nPlaybook:\n{playbook}" if playbook else "")
        prior = state.get("prior_context") or []
        prior_block = (
            "\n\nPrior related analyses (from memory):\n" + "\n".join(f"- {p}" for p in prior)
            if prior else ""
        )
        evidence = format_evidence(chunks)
        prompt = (
            f"{role}\n\nQuestion: {query}{prior_block}\n\nEvidence (cite by index):\n{evidence}\n\n"
            "Extract 2-4 findings. Each finding MUST be grounded in the evidence and cite "
            'the index it came from. Return ONLY JSON: '
            '[{"claim": "...", "citation_index": 1, "confidence": 0.0-1.0}]'
        )
        raw = chat(prompt, system=system, temperature=0.2, run_name=f"specialist.{name}")
        items = extract_json(raw, default=[])
        findings = []
        for it in items if isinstance(items, list) else []:
            idx = it.get("citation_index", 1)
            cite = "n/a"
            if isinstance(idx, int) and 1 <= idx <= len(chunks):
                cite = chunks[idx - 1].chunk.citation()
            findings.append({
                "agent": name,
                "claim": str(it.get("claim", "")).strip(),
                "citation": cite,
                "confidence": float(it.get("confidence", 0.6) or 0.6),
            })
        if not findings:  # model returned nothing parseable — keep the run honest
            findings = [{"agent": name, "claim": "No well-grounded finding extracted.",
                         "citation": "n/a", "confidence": 0.3}]
        log.info("%s produced %d findings", name, len(findings))
        return {"findings": findings}

    node.__name__ = f"{name}_node"
    return node


# Concrete specialist nodes
fundamentals_node = _make_specialist(*SPECIALISTS[0])
news_sentiment_node = _make_specialist(*SPECIALISTS[1])
risk_node = _make_specialist(*SPECIALISTS[2])
market_node = _make_specialist(*SPECIALISTS[3])

SPECIALIST_NODES = {
    "fundamentals": fundamentals_node,
    "news_sentiment": news_sentiment_node,
    "risk": risk_node,
    "market": market_node,
}
