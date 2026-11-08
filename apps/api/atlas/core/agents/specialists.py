"""Supervisor plan + the four specialist analyst agents.

Each specialist works in two steps, kept separate on purpose:

1. ``gather_evidence`` — CRAG hybrid RAG (the live web as the corrective fallback)
   plus the specialist's own research tool (SEC filing, stock quote, company news).
2. ``extract_findings`` — turn that evidence into findings where **every claim cites
   a retrieved chunk**, under the specialist's active *policy* (learned lessons,
   exemplar findings and retrieval depth, see ``llmops.policy``).

The split lets the learning loop replay a candidate policy against the baseline on
the *same* evidence, so a measured difference is the policy's, not retrieval noise.

Provenance flows into shared state so the synthesizer can build a cited report. With
no GROQ key each node returns a deterministic stub so the graph still runs offline;
when retries are exhausted a node degrades instead of failing the run.
"""

from __future__ import annotations

import logging
import re

from ..llmops.policy import Policy, get_policies, prompt_block
from ..memory.procedural import ProceduralMemory
from ..rag.crag import corrective_retrieve
from ..rag.entity import entity_terms
from ..rag.tool_evidence import tool_evidence_for
from ..rag.types import RetrievedChunk
from ..rag.web_evidence import web_evidence_about
from ..resilience import run_or_degrade
from ..resources import get_index
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
SEARCH_FOCUS = {name: focus for name, focus, _ in SPECIALISTS}
ROLES = {name: role for name, _, role in SPECIALISTS}

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


def merge_evidence(tool_chunks: list[RetrievedChunk], crag_chunks: list[RetrievedChunk]
           ) -> list[RetrievedChunk]:
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


def gather_evidence(name: str, state: ResearchState, top_k: int
                    ) -> tuple[list[RetrievedChunk], list[RetrievedChunk]]:
    """``(tool_chunks, crag_chunks)`` for one specialist's angle on the target.

    ``web_fallback`` makes CRAG's corrective step real: when local evidence grades weak
    (e.g. the company was never ingested), live web evidence is pulled instead —
    scoped to this company so same-named firms are dropped.
    """
    target = state.get("target") or ""
    ticker = state.get("ticker") or ""
    result = corrective_retrieve(
        get_index(), f"{target or state['query']} {SEARCH_FOCUS[name]}", top_k=top_k,
        web_fallback=web_evidence_about(target, ticker),
        entity=entity_terms(target, ticker) if target else None,
    )
    if result.used_web_fallback:
        log.info("%s fell back to web evidence", name)
    return tool_evidence_for(name, target=target, ticker=ticker), result.chunks


def extract_findings(name: str, state: ResearchState, chunks: list[RetrievedChunk],
                     policy: Policy) -> list[dict]:
    """Findings for ``name`` from ``chunks``, each citing the chunk it came from."""
    query = state["query"]
    target = state.get("target") or ""
    if not llm_ready():
        cite = chunks[0].chunk.citation() if chunks else "n/a"
        return [{"agent": name, "claim": f"[offline stub] {name} analysis of: {query}",
                 "citation": cite, "confidence": 0.5}]

    # Role + procedural memory (playbook file) + what the learning loop taught it.
    role = ROLES[name]
    playbook = _procedural.get(name)
    learned = prompt_block(policy)
    system = "\n\n".join(p for p in (role, f"Playbook:\n{playbook}" if playbook else "",
                                       learned) if p)
    prior = state.get("prior_context") or []
    prior_block = ("\n\nPrior related analyses (from memory):\n"
                   + "\n".join(f"- {p}" for p in prior)) if prior else ""
    prompt = (
        f"{role}\n\nCompany: {target or 'see question'}\nQuestion: {query}{prior_block}"
        f"\n\nEvidence (cite by index):\n{format_evidence(chunks)}\n\n"
        + entity_rule(target) + findings_instructions("3-5")
    )
    # Extraction, not deliberation: low reasoning effort keeps hidden reasoning from
    # eating the output budget (see llm.get_llm) and saves daily tokens.
    raw = chat(prompt, system=system, temperature=0.2, run_name=f"specialist.{name}",
               reasoning_effort="low")
    findings = parse_findings(name, raw, chunks)
    return findings or [{"agent": name, "claim": "No well-grounded finding extracted.",
                         "citation": "n/a", "confidence": 0.3}]


def _make_specialist(name: str):
    def run(state: ResearchState) -> dict:
        policy = get_policies().active(name)
        tools, crag = gather_evidence(name, state, policy.top_k)
        findings = extract_findings(name, state, merge_evidence(tools, crag), policy)
        log.info("%s produced %d findings (%d tool chunks, top_k=%d)",
                 name, len(findings), len(tools), policy.top_k)
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
SPECIALIST_NODES = {name: _make_specialist(name) for name, _, _ in SPECIALISTS}
fundamentals_node = SPECIALIST_NODES["fundamentals"]
news_sentiment_node = SPECIALIST_NODES["news_sentiment"]
risk_node = SPECIALIST_NODES["risk"]
market_node = SPECIALIST_NODES["market"]
