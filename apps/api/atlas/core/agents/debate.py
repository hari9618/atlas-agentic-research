"""Bull ⇄ Bear debate + Judge — the visible agent-to-agent communication.

Two agents argue opposite sides of the findings; a neutral judge weighs the exchange.
Adversarial pressure surfaces failure modes a single pass would confidently miss.
If the LLM stays unavailable after retries, the debate degrades to a neutral stub so
the report can still be written from the findings (design §5).
"""

from __future__ import annotations

import logging
import re

from ..resilience import run_or_degrade
from ..state import ResearchState
from .base import chat, llm_ready

log = logging.getLogger("atlas.agents.debate")


def _findings_brief(state: ResearchState) -> str:
    lines = []
    for f in state.get("findings", []):
        lines.append(f"- ({f['agent']}) {f['claim']} [cite: {f.get('citation', 'n/a')}]")
    return "\n".join(lines) or "(no findings)"


def _neutral_stub(_exc: BaseException | None = None) -> dict:
    return {"debate": [
        {"role": "bull", "text": "The bull case could not be argued this run (agent unavailable)."},
        {"role": "bear", "text": "The bear case could not be argued this run (agent unavailable)."},
        {"role": "judge", "text": "No debate verdict this run; the report relies on the "
                                  "specialist findings alone.", "leaning": "neutral"},
    ]}


def debate_node(state: ResearchState) -> dict:
    if not llm_ready():
        return {"debate": [
            {"role": "bull", "text": "[offline stub] optimistic reading of the findings"},
            {"role": "bear", "text": "[offline stub] skeptical reading of the findings"},
            {"role": "judge", "text": "[offline stub] balanced verdict", "leaning": "neutral"},
        ]}
    return run_or_degrade(_debate, state, fallback=_neutral_stub, label="debate")


def _debate(state: ResearchState) -> dict:
    from .brief import describe

    query = f"{state['query']}\n\n{describe(state)}"
    brief = _findings_brief(state)
    bull = chat(
        f"You are the BULL. Argue the optimistic case on:\n{query}\n\nFindings:\n{brief}\n\n"
        "Argue from the reader's side (for a competitor check, 'optimistic' means the "
        "subject is a strong company the reader must take seriously). "
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
    # The verdict word is asked for on the LAST line; a first-match scan read
    # "...the bullish case is weaker... BEARISH" as bullish.
    tags = re.findall(r"\b(BULLISH|BEARISH|NEUTRAL)\b", judge.upper())
    leaning = tags[-1].lower() if tags else "neutral"
    return {"debate": [
        {"role": "bull", "text": bull},
        {"role": "bear", "text": bear},
        {"role": "judge", "text": judge, "leaning": leaning},
    ]}
