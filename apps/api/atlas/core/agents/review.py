"""Human-in-the-loop review (design §3).

``human_review`` pauses the run with LangGraph's ``interrupt()`` so a person can
approve the drafted report or request changes. The checkpointer persists the paused
run, so the decision can arrive minutes later — on another worker — via
``resume_research``. A revision request routes to ``revise_research``, which gathers
evidence aimed at the feedback and appends follow-up findings; ``synthesize`` then
rewrites the report addressing it. The loop is capped at ``max_revisions``.

Important LangGraph detail: on resume the node re-executes from the top and
``interrupt()`` returns the resume value instead of pausing. So everything before
``interrupt()`` must be side-effect free (it is: it only reads state).
"""

from __future__ import annotations

import logging

from langgraph.types import interrupt

from ...config import get_settings
from ..payload import research_payload
from ..rag.crag import corrective_retrieve
from ..rag.entity import entity_terms
from ..rag.web_evidence import web_evidence_about
from ..resilience import run_or_degrade
from ..state import ResearchState
from .base import chat, format_evidence, llm_ready
from .findings import (
    entity_rule,
    findings_instructions,
    parse_findings,
    unavailable_finding,
)
from .synthesizer import with_uncertainty

log = logging.getLogger("atlas.agents.review")

FOLLOWUP_AGENT = "reviewer_followup"
ACTIONS = ("approve", "revise")


def parse_decision(decision) -> tuple[str, str]:
    """Normalize a resume value → (action, feedback). Unknown actions approve."""
    if isinstance(decision, str):
        decision = {"action": decision}
    if not isinstance(decision, dict):
        decision = {}
    action = str(decision.get("action", "approve")).strip().lower()
    feedback = str(decision.get("feedback") or "").strip()
    if action == "revise" and feedback:
        return "revise", feedback
    return "approve", ""


def human_review_node(state: ResearchState) -> dict:
    """Pause for a human decision on the draft (or auto-approve when review is off)."""
    if not state.get("require_review"):
        return {"review_status": "auto_approved"}

    revision = state.get("revision") or 0
    cap = get_settings().max_revisions
    if revision >= cap:
        note = (f"Revision limit reached ({cap} rounds of reviewer feedback); this draft "
                "was approved automatically without a further human review.")
        return {
            "review_status": "auto_approved",
            "review_history": [{"revision": revision, "action": "auto_approve", "feedback": ""}],
            **with_uncertainty(state, note),
        }

    # Pure up to here — this line pauses the run; on resume it returns the decision.
    decision = interrupt({**research_payload(state), "revision": revision,
                          "review_status": "pending"})
    action, feedback = parse_decision(decision)
    log.info("human review of revision %d: %s", revision, action)
    if action == "revise":
        return {"review_status": "revision_requested", "feedback": feedback}
    return {
        "review_status": "approved",
        "review_history": [{"revision": revision, "action": "approve", "feedback": ""}],
    }


def route_after_review(state: ResearchState) -> str:
    return "revise_research" if state.get("review_status") == "revision_requested" else "remember"


def _followup_findings(state: ResearchState, target: str, feedback: str) -> list[dict]:
    from ..graph import get_index  # late import avoids a cycle

    ticker = state.get("ticker") or ""
    web = web_evidence_about(target, ticker)
    result = corrective_retrieve(get_index(), f"{target} {feedback}", top_k=4,
                                 web_fallback=web,
                                 entity=entity_terms(target, ticker) if target else None)
    chunks = result.chunks
    if not llm_ready():
        cite = chunks[0].chunk.citation() if chunks else "n/a"
        return [{"agent": FOLLOWUP_AGENT, "claim": f"[offline stub] follow-up research on: "
                 f"{feedback}", "citation": cite, "confidence": 0.5}]
    raw = chat(
        f"You are a research analyst following up on a reviewer's request about {target}.\n"
        f'Reviewer feedback: "{feedback}"\nOriginal question: {state["query"]}\n\n'
        f"Evidence (cite by index):\n{format_evidence(chunks)}\n\n"
        "Focus only on what the reviewer asked for. " + entity_rule(target)
        + findings_instructions("2-4"),
        system="You extract evidence-grounded findings; you never assert unsupported facts.",
        temperature=0.2, run_name="review.revise_research", reasoning_effort="low",
    )
    findings = parse_findings(FOLLOWUP_AGENT, raw, chunks)
    return findings or [{"agent": FOLLOWUP_AGENT, "claim": "No additional grounded evidence "
                         f"was found for the reviewer's request: {feedback}",
                         "citation": "n/a", "confidence": 0.3}]


def revise_research_node(state: ResearchState) -> dict:
    """Targeted extra research for the reviewer's feedback, then hand back to synthesize."""
    feedback = (state.get("feedback") or "").strip()
    reviewed = state.get("revision") or 0
    target = state.get("target") or state["query"]
    findings = run_or_degrade(
        _followup_findings, state, target, feedback,
        fallback=lambda exc: [unavailable_finding(FOLLOWUP_AGENT)],
        label="revise_research",
    )
    log.info("revise_research: %d follow-up findings for revision %d", len(findings), reviewed + 1)
    return {
        "revision": reviewed + 1,
        "feedback": feedback,
        "review_history": [{"revision": reviewed, "action": "revise", "feedback": feedback}],
        "findings": findings,
    }
