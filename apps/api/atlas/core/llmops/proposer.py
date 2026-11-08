"""Proposer — turn a diagnosed issue into ONE bounded, reviewable policy change.

One change per experiment, so a measured gain is attributable to it. The levers:

* ``lesson``    — distil a single imperative rule from the failure examples (the
                  reviewer's words, the unsupported statements). A small model writes
                  it; a deterministic template per issue kind is the fallback.
* ``retrieval`` — read more evidence: ``top_k + 2`` (bounded). Thin output usually
                  means the analyst never saw enough material. At the ceiling, the
                  proposal falls back to a lesson.
* ``exemplars`` — few-shot demonstrations: verified-strong findings from approved runs.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

from ...config import get_settings
from .diagnose import exemplar_candidates
from .policy import LABELS, MAX_EXEMPLARS, MAX_LESSONS, TOP_K_RANGE, Policy

log = logging.getLogger("atlas.llmops.proposer")

_MAX_LESSON_CHARS = 220

# Used when no LLM is available (tests/offline) or its reply is unusable.
_TEMPLATE_LESSONS = {
    "ungrounded_findings": "Only state a figure, name or date if the cited passage contains "
                           "it word for word; otherwise leave it out.",
    "thin_findings": "Extract at least three distinct findings, each from a different "
                     "passage, before concluding the evidence is thin.",
    "unsupported_statements": "Every sentence must be backed by a finding; drop any "
                              "statement you cannot tie to a cited finding.",
    "miscited_statements": "Attach to each sentence the citation of the finding it "
                           "actually came from, never a nearby one.",
    "off_question": "Open with a direct answer to the user's exact question before any "
                    "background.",
    "reviewer_feedback": "Address the specific aspect reviewers asked for, with concrete, "
                         "cited detail.",
}


@dataclass
class Proposal:
    component: str
    lever: str
    policy: Policy
    summary: str
    before: str
    after: str


def _llm_active() -> bool:
    return get_settings().llm_configured and os.getenv("ATLAS_OFFLINE_LLM") != "1"


def _norm(s: str) -> set[str]:
    return set(re.findall(r"[a-z]{4,}", s.lower()))


def _is_duplicate(lesson: str, existing: list[str]) -> bool:
    words = _norm(lesson)
    for e in existing:
        other = _norm(e)
        if words and other and len(words & other) / len(words | other) > 0.6:
            return True
    return False


def distil_lesson(component: str, kind: str, examples: list[str]) -> str:
    """One short imperative rule that would have prevented these failures."""
    fallback = _TEMPLATE_LESSONS.get(kind, _TEMPLATE_LESSONS["reviewer_feedback"])
    if not _llm_active() or not examples:
        return fallback
    from ...llm import get_llm
    from ...observability import langchain_callbacks

    shown = "\n".join(f"- {e}" for e in examples[:4])
    try:
        resp = get_llm(temperature=0.2, model=get_settings().summarizer_model).invoke(
            f"You coach the {LABELS.get(component, component)} of an AI due-diligence desk. "
            f"Recent runs failed like this ({kind.replace('_', ' ')}):\n{shown}\n\n"
            "Write ONE imperative rule (max 25 words) that would prevent these failures in "
            "future reports about ANY company. It must be general (no company names, no "
            "specific numbers) and must not ask for anything the evidence cannot provide. "
            "Return only the rule.",
            config={"callbacks": langchain_callbacks(), "run_name": "ops.distil_lesson"},
        )
        text = (resp.content if hasattr(resp, "content") else str(resp)).strip()
        text = text.strip("\"'` -•").splitlines()[0].strip() if text else ""
        if 15 <= len(text) <= _MAX_LESSON_CHARS:
            return text
        log.warning("lesson proposal rejected (%d chars)", len(text))
    except Exception as exc:
        log.warning("lesson distillation failed (%s) — using template", exc)
    return fallback


def propose(issue: dict, policy: Policy, records: list[dict]) -> Proposal | None:
    """A candidate policy for ``issue`` (a ranked pattern from ``diagnose.open_issues``),
    or ``None`` when no lever can do anything new."""
    comp, kind, lever = issue["component"], issue["kind"], issue["lever"]
    lo, hi = TOP_K_RANGE

    if lever == "retrieval" and comp != "synthesizer":
        if policy.top_k < hi:
            new_k = min(hi, policy.top_k + 2)
            return Proposal(comp, "retrieval",
                            Policy(policy.lessons, policy.exemplars, new_k, policy.system),
                            f"Read more evidence: top_k {policy.top_k} → {new_k}",
                            str(policy.top_k), str(new_k))
        lever = "lesson"  # already at the ceiling: teach instead of fetching more

    if lever == "exemplars":
        have = {e.get("claim") for e in policy.exemplars}
        fresh = [e for e in exemplar_candidates(records, comp) if e["claim"] not in have]
        if not fresh:
            return None
        exemplars = (policy.exemplars + fresh)[-MAX_EXEMPLARS:]
        return Proposal(comp, "exemplars",
                        Policy(policy.lessons, exemplars, policy.top_k, policy.system),
                        f"Show {len(exemplars)} verified strong finding(s) from approved runs",
                        f"{len(policy.exemplars)} exemplar(s)", f"{len(exemplars)} exemplar(s)")

    lesson = distil_lesson(comp, kind, issue.get("examples") or [issue.get("example", "")])
    if _is_duplicate(lesson, policy.lessons):
        return None
    lessons = [*policy.lessons, lesson][-MAX_LESSONS:]
    return Proposal(comp, "lesson",
                    Policy(lessons, policy.exemplars, max(lo, policy.top_k), policy.system),
                    f"New lesson: {lesson}", f"{len(policy.lessons)} lesson(s)", lesson)
