"""The shared LangGraph state — Atlas's working memory ("research scratchpad").

Specialist agents append findings concurrently, so `findings`, `debate` and
`review_history` use an additive reducer. The graph is compiled with a durable
checkpointer (see persistence.py) so a run survives a pause for human review and can
be resumed later — possibly by a different worker.
"""

from __future__ import annotations

from typing import Annotated, TypedDict


def add_or_reset(left: list | None, right: list | None) -> list:
    """``operator.add`` for lists, except an explicit ``None`` update clears the list.

    Why: a thread id can be reused for a brand-new run (``/research/sync`` defaults to
    ``"default"``). With a plain ``operator.add`` the
    checkpointed findings of the *previous* company would leak into the next report.
    ``run_research`` sends ``None`` for these keys at the start of every run.
    """
    if right is None:
        return []
    return (left or []) + list(right)


class ResearchState(TypedDict, total=False):
    query: str                                   # the user's question
    target: str                                  # company/entity under analysis (supervisor)
    ticker: str                                  # stock ticker if public and known, else ""
    # ---- research brief (agents/brief.py): who asks, about whom, and why ----
    subject_domain: str                          # the subject's website domain, if known
    asker: str                                   # the user's own company, if they said
    asker_domain: str
    persona: str                                 # investor | competitor | buyer | ... | general
    goal: str                                    # the decision the report must support
    extra_asks: list[str]                        # specific asks beyond the standard brief
    brief_notes: list[str]                       # caveats from planning (e.g. dropped ticker)
    degraded: list[str]                          # nodes that fell back (surfaced to the reader)
    prior_context: list[str]                     # episodic memory recalled for this run
    plan: list[str]                              # supervisor's focus areas
    findings: Annotated[list[dict], add_or_reset]  # specialists append here
    debate: Annotated[list[dict], add_or_reset]    # bull / bear / judge turns
    report: str                                  # final report rendered as markdown
    report_sections: dict | None                 # structured report (design §1), None on fallback
    confidence: float                            # 0..1 overall confidence (guardrail-tempered)
    uncertainties: list[str]                     # explicit "what we're not sure about"
    citations: list[dict]                        # evidence used, with provenance
    # ---- human-in-the-loop review (design §3) ----
    require_review: bool                         # pause for human review after drafting
    review_status: str  # pending | approved | revision_requested | rejected | auto_approved
    feedback: str                                # latest reviewer feedback
    feedback_section: str                        # report section the feedback targets
    revision: int                                # 0 for the first draft, +1 per requested change
    review_history: Annotated[list[dict], add_or_reset]  # {revision, action, feedback, section}
