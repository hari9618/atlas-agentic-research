"""Human-in-the-loop review (design §3).

``human_review`` pauses the run with LangGraph's ``interrupt()`` so a person can act
on the drafted report:

* **approve** — accept it; the run is remembered (episodic memory) and finishes.
* **revise**  — feedback, optionally aimed at one report section. ``revise_research``
  gathers evidence aimed at that feedback (using the responsible specialist's search
  focus when a section is given) and ``synthesize`` rewrites the draft.
* **reject**  — throw it out (optional reason). The run ends without being
  remembered, so a report a human rejected never becomes memory.

Every decision lands in ``review_history`` and, through the run record, becomes a
labelled training signal for the learning loop. The checkpointer persists the paused
run, so the decision can arrive minutes later on another worker. Revisions are
capped at ``max_revisions``.

LangGraph detail: on resume the node re-executes from the top and ``interrupt()``
returns the resume value instead of pausing, so everything before it must be free of
side effects (it is: it only reads state).
"""

from __future__ import annotations

import logging

from langgraph.types import interrupt

from ...config import get_settings
from ..llmops.diagnose import SECTION_COMPONENT
from ..payload import research_payload
from ..rag.crag import corrective_retrieve
from ..rag.entity import entity_terms
from ..rag.web_evidence import web_evidence_about
from ..resilience import run_or_degrade
from ..resources import get_index
from ..state import ResearchState
from .base import chat, format_evidence, llm_ready
from .findings import (
    entity_rule,
    findings_instructions,
    parse_findings,
    unavailable_finding,
)
from .specialists import SEARCH_FOCUS
from .synthesizer import with_uncertainty

log = logging.getLogger("atlas.agents.review")

FOLLOWUP_AGENT = "reviewer_followup"
ACTIONS = ("approve", "revise", "reject")


def parse_decision(decision) -> tuple[str, str, str]:
    """Normalize a resume value → ``(action, feedback, section)``.

    Unknown actions, and a revise without feedback, approve.
    """
    if isinstance(decision, str):
        decision = {"action": decision}
    if not isinstance(decision, dict):
        decision = {}
    action = str(decision.get("action", "approve")).strip().lower()
    feedback = str(decision.get("feedback") or "").strip()
    section = str(decision.get("section") or "").strip()
    if action == "revise" and feedback:
        return "revise", feedback, section
    if action == "reject":
        return "reject", feedback, section
    return "approve", "", ""


def _history(revision: int, action: str, feedback: str = "", section: str = "") -> list[dict]:
    entry = {"revision": revision, "action": action, "feedback": feedback}
    if section:
        entry["section"] = section
    return [entry]


def human_review_node(state: ResearchState) -> dict:
    """Pause for a human decision on the draft (or auto-approve when review is off)."""
    if not state.get("require_review"):
        return {"review_status": "auto_approved"}

    revision = state.get("revision") or 0
    cap = get_settings().max_revisions
    if revision >= cap:
        note = (f"Revision limit reached ({cap} rounds of reviewer feedback); this draft "
                "was approved automatically without a further human review.")
        return {"review_status": "auto_approved",
                "review_history": _history(revision, "auto_approve"),
                **with_uncertainty(state, note)}

    # Pure up to here — this line pauses the run; on resume it returns the decision.
    decision = interrupt({**research_payload(state), "revision": revision,
                          "review_status": "pending"})
    action, feedback, section = parse_decision(decision)
    log.info("human review of revision %d: %s%s", revision, action,
             f" ({section})" if section else "")
    if action == "revise":
        return {"review_status": "revision_requested", "feedback": feedback,
                "feedback_section": section}
    if action == "reject":
        return {"review_status": "rejected",
                "review_history": _history(revision, "reject", feedback, section)}
    return {"review_status": "approved", "review_history": _history(revision, "approve")}


def route_after_review(state: ResearchState) -> str:
    status = state.get("review_status")
    if status == "revision_requested":
        return "revise_research"
    return "end" if status == "rejected" else "remember"


def _followup_findings(state: ResearchState, target: str, feedback: str,
                       section: str) -> list[dict]:
    ticker = state.get("ticker") or ""
    # A section-targeted request searches with the responsible analyst's focus terms.
    focus = SEARCH_FOCUS.get(SECTION_COMPONENT.get(section, ""), "")
    result = corrective_retrieve(get_index(), f"{target} {feedback} {focus}".strip(), top_k=4,
                                 web_fallback=web_evidence_about(target, ticker),
                                 entity=entity_terms(target, ticker) if target else None)
    chunks = result.chunks
    if not llm_ready():
        cite = chunks[0].chunk.citation() if chunks else "n/a"
        return [{"agent": FOLLOWUP_AGENT, "claim": f"[offline stub] follow-up research on: "
                 f"{feedback}", "citation": cite, "confidence": 0.5}]
    about = f" about the {section.replace('_', ' ')} section" if section else ""
    raw = chat(
        f"You are a research analyst following up on a reviewer's request{about} "
        f'regarding {target}.\nReviewer feedback: "{feedback}"\n'
        f"Original question: {state['query']}\n\n"
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
    section = (state.get("feedback_section") or "").strip()
    reviewed = state.get("revision") or 0
    target = state.get("target") or state["query"]
    findings = run_or_degrade(
        _followup_findings, state, target, feedback, section,
        fallback=lambda exc: [unavailable_finding(FOLLOWUP_AGENT)],
        label="revise_research",
    )
    log.info("revise_research: %d follow-up findings for revision %d", len(findings), reviewed + 1)
    return {
        "revision": reviewed + 1,
        "feedback": feedback,
        "review_history": _history(reviewed, "revise", feedback, section),
        "findings": findings,
    }
