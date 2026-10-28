"""Supervisor plan + the four specialist analyst agents.

Each specialist gathers grounded evidence for its angle — CRAG hybrid RAG (with the
live web as the corrective fallback) plus its own research tool (SEC filing, stock
quote, company news) — then emits findings where **every claim cites a retrieved
chunk**. Provenance flows into shared state so the synthesizer can build a cited
report. With no GROQ key each node returns a deterministic stub so the graph still
runs offline; when retries are exhausted a node degrades instead of failing the run.
"""

from __future__ import annotations

import logging
import re

from ..memory.procedural import ProceduralMemory
from ..rag.crag import corrective_retrieve
from ..rag.entity import entity_terms
from ..rag.tool_evidence import tool_evidence_for
from ..rag.types import RetrievedChunk
from ..rag.web_evidence import web_evidence_about
from ..resilience import run_or_degrade
from ..state import ResearchState
from .base import chat, extract_json, format_evidence, llm_ready
from .findings import (
    entity_rule,
    findings_instructions,
    parse_findings,
    unavailable_finding,
)

log = logging.getLogger("atlas.agents.specialists")

# Procedural memory: each specialist may have a file-based playbook ("how to act").
_procedural = ProceduralMemory()

# name, search focus (short keywords: it feeds retrieval + the web query), and the
# role brief. Together the four briefs cover what an investor expects from an analyst.
SPECIALISTS = [
    ("fundamentals",
     "business model products customers revenue growth margins funding",
     "You are a fundamentals analyst. Cover what the company does, its business model "
     "(how it makes money), its main products/services and who its customers are, and "
     "its financials: revenue, growth, margins, profitability, and funding raised."),
    ("news_sentiment",
     "latest news deals partnerships product launches leadership changes sentiment",
     "You are a news & sentiment analyst. Cover the most recent notable developments — "
     "deals, partnerships, product launches, funding rounds, leadership changes — with "
     "dates when the evidence gives them, and the overall market sentiment."),
    ("risk",
     "risks customer concentration suppliers regulation litigation debt",
     "You are a risk analyst. Cover the key risks and how severe each is: customer "
     "concentration, supplier/supply-chain dependence, regulatory exposure, litigation, "
     "debt and liquidity, and execution risk."),
    ("market",
     "competitors market share competitive position strengths weaknesses",
     "You are a market/competitor analyst. Cover the competitive landscape: named "
     "competitors and how the company compares, market share and position, and its "
     "main strengths and weaknesses versus rivals."),
]

DEFAULT_PLAN = [s[0] for s in SPECIALISTS]

# ---------------------------------------------------------------- supervisor

# Words that open a question but are never part of a company name.
_NOT_NAME = {
    "should", "i", "is", "are", "was", "what", "whats", "how", "why", "who", "when",
    "which", "can", "could", "does", "do", "did", "will", "would", "evaluate", "assess",
    "analyze", "analyse", "compare", "tell", "give", "me", "the", "a", "an", "worry",
    "invest", "research", "review", "about", "please", "my", "we", "our", "us", "ceo",
}
_CAP_RUN = re.compile(r"[A-Z][\w&.\-]*(?:\s+[A-Z][\w&.\-]*)*")


def guess_target(query: str) -> str:
    """Best-effort company name from the question (offline / failure fallback).

    Picks the longest run of capitalised words, ignoring question words, so
    "Should I invest in Helios Robotics?" → "Helios Robotics".
    """
    best = ""
    for run in _CAP_RUN.findall(query):
        words = [w for w in run.split() if w.lower().strip(".") not in _NOT_NAME]
        name = " ".join(words).strip(" .?!,")
        if len(name) > len(best):
            best = name
    return best or query.strip().rstrip("?!. ")[:80]


def _clean_ticker(value) -> str:
    from ..tools.symbols import clean_ticker  # one symbol convention for every tool

    return clean_ticker(value)


def _llm_plan(query: str) -> dict:
    raw = chat(
        "You are a research supervisor for an investment due-diligence desk. The analyst "
        f'desk will investigate this question:\n"{query}"\n\n'
        "Return ONLY a JSON object:\n"
        '{"target": "the company or entity being analysed (official name)", '
        '"ticker": "its Yahoo Finance symbol ONLY if it is a publicly traded company and '
        'you are confident of it, otherwise an empty string", '
        '"focus_areas": ["3-5 concise focus areas"]}\n\n'
        "Ticker format (Yahoo Finance): US listings have no suffix (AAPL, BRK-B, and US "
        "ADRs such as INFY or HDB); Indian companies use the exchange suffix, preferring "
        "NSE (RELIANCE.NS, TCS.NS, HDFCBANK.NS) or BSE (500325.BO); other markets use "
        "their suffix (VOD.L, 7203.T). Private companies and startups get an empty string.",
        temperature=0.0,
        run_name="supervisor.plan",
    )
    parsed = extract_json(raw, default={})
    if not isinstance(parsed, dict):
        parsed = {}
    target = str(parsed.get("target") or "").strip() or guess_target(query)
    areas = parsed.get("focus_areas") or []
    if isinstance(areas, str):
        areas = [areas]
    areas = [str(a).strip("-• ").strip() for a in areas if str(a).strip()]
    return {
        "target": target[:120],
        "ticker": _clean_ticker(parsed.get("ticker")),
        "plan": areas[:5] or DEFAULT_PLAN,
    }


def plan_node(state: ResearchState) -> dict:
    """Supervisor: identify the company (+ ticker) and plan the focus areas."""
    query = state["query"]
    fallback = {"target": guess_target(query), "ticker": "", "plan": DEFAULT_PLAN}
    if not llm_ready():
        return fallback
    return run_or_degrade(_llm_plan, query, fallback=fallback, label="supervisor")

# ---------------------------------------------------------------- specialists


def _merge(tool_chunks: list[RetrievedChunk], crag_chunks: list[RetrievedChunk]):
    """Tool evidence first (targeted at this company), then CRAG — no duplicates.

    The merged list IS the numbered evidence the model cites by index, so citation
    resolution always uses this exact order.
    """
    seen, out = set(), []
    for c in tool_chunks + crag_chunks:
        if c.chunk.chunk_id not in seen:
            seen.add(c.chunk.chunk_id)
            out.append(c)
    return out


def _make_specialist(name: str, focus: str, role: str):
    def run(state: ResearchState) -> dict:
        from ..graph import get_index  # late import avoids a cycle

        query = state["query"]
        target = state.get("target") or ""
        ticker = state.get("ticker") or ""
        # web_fallback makes CRAG's corrective step real: when local evidence grades
        # weak (e.g. the company was never ingested), pull live web evidence instead of
        # returning nothing — scoped to this company so same-named firms are dropped.
        result = corrective_retrieve(
            get_index(), f"{target or query} {focus}", top_k=4,
            web_fallback=web_evidence_about(target, ticker),
            entity=entity_terms(target, ticker) if target else None,
        )
        if result.used_web_fallback:
            log.info("%s fell back to web evidence", name)
        tools = tool_evidence_for(name, target=target, ticker=ticker)
        chunks = _merge(tools, result.chunks)

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
        prompt = (
            f"{role}\n\nCompany: {target or 'see question'}\nQuestion: {query}{prior_block}"
            f"\n\nEvidence (cite by index):\n{format_evidence(chunks)}\n\n"
            + entity_rule(target) + findings_instructions("3-5")
        )
        # Extraction, not deliberation: low reasoning effort keeps the hidden reasoning
        # from eating the output budget (see llm.get_llm) and saves daily tokens.
        raw = chat(prompt, system=system, temperature=0.2, run_name=f"specialist.{name}",
                   reasoning_effort="low")
        findings = parse_findings(name, raw, chunks)
        if not findings:  # model returned nothing parseable — keep the run honest
            findings = [{"agent": name, "claim": "No well-grounded finding extracted.",
                         "citation": "n/a", "confidence": 0.3}]
        log.info("%s produced %d findings (%d tool chunks)", name, len(findings), len(tools))
        return {"findings": findings}

    def node(state: ResearchState) -> dict:
        # One failing specialist degrades its own section, never the whole run.
        return run_or_degrade(
            run, state,
            fallback=lambda exc: {"findings": [unavailable_finding(name)]},
            label=f"specialist.{name}",
        )

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
