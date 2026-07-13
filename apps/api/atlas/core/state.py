"""The shared LangGraph state — Atlas's working memory ("research scratchpad").

Specialist agents append findings concurrently, so `findings` and `debate` use the
additive reducer (``operator.add``). The graph is compiled with a SQLite checkpointer
so a run is durable and resumable (see graph.py).
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class ResearchState(TypedDict, total=False):
    query: str                                   # the user's question
    target: str                                  # company/entity under analysis
    prior_context: list[str]                     # episodic memory recalled for this run
    plan: list[str]                              # supervisor's focus areas
    findings: Annotated[list[dict], operator.add]  # specialists append here
    debate: Annotated[list[dict], operator.add]    # bull / bear / judge turns
    report: str                                  # final synthesized report (markdown)
    confidence: float                            # 0..1 overall confidence
    uncertainties: list[str]                     # explicit "what we're not sure about"
    citations: list[dict]                        # evidence used, with provenance
