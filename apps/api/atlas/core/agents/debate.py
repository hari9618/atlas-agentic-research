"""Bull ⇄ Bear debate + Judge — the visible agent-to-agent communication.

Two agents argue opposite sides of the findings; a neutral judge weighs the exchange.
Adversarial pressure surfaces failure modes a single pass would confidently miss.
"""

from __future__ import annotations

import logging

from ..state import ResearchState
from .base import chat, llm_ready

log = logging.getLogger("atlas.agents.debate")


def _findings_brief(state: ResearchState) -> str:
    lines = []
    for f in state.get("findings", []):
        lines.append(f"- ({f['agent']}) {f['claim']} [cite: {f.get('citation', 'n/a')}]")
    return "\n".join(lines) or "(no findings)"


def debate_node(state: ResearchState) -> dict:
    query = state["query"]
    brief = _findings_brief(state)

    if not llm_ready():
        return {"debate": [
            {"role": "bull", "text": "[offline stub] optimistic reading of the findings"},
            {"role": "bear", "text": "[offline stub] skeptical reading of the findings"},
            {"role": "judge", "text": "[offline stub] balanced verdict", "leaning": "neutral"},
        ]}

    bull = chat(
        f"You are the BULL. Argue the optimistic case on:\n{query}\n\nFindings:\n{brief}\n\n"
        "Give 3 crisp points grounded in the findings.",
        system="You argue the bullish/positive case, but only from the evidence.",
        temperature=0.6, run_name="debate.bull",
    )
    bear = chat(
        f"You are the BEAR. Rebut the bull and argue the cautious case on:\n{query}\n\n"
        f"Findings:\n{brief}\n\nBull said:\n{bull}\n\nGive 3 crisp counterpoints.",
        system="You argue the bearish/risk case, but only from the evidence.",
        temperature=0.6, run_name="debate.bear",
    )
    judge = chat(
        f"You are a neutral JUDGE. Weigh both sides on:\n{query}\n\n"
        f"BULL:\n{bull}\n\nBEAR:\n{bear}\n\n"
        "Deliver a 2-3 sentence balanced verdict and end with exactly one word on its own "
        "line: BULLISH, BEARISH, or NEUTRAL.",
        system="You are impartial and decide based on argument strength.",
        temperature=0.1, run_name="debate.judge",
    )
    leaning = "neutral"
    for tag in ("BULLISH", "BEARISH", "NEUTRAL"):
        if tag in judge.upper():
            leaning = tag.lower()
            break
    return {"debate": [
        {"role": "bull", "text": bull},
        {"role": "bear", "text": bear},
        {"role": "judge", "text": judge, "leaning": leaning},
    ]}
