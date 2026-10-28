"""Per-agent evaluation — score each specialist, not just the final report.

The per-run evaluator (``evaluate.py``) scores the *final report*, which the
self-improvement loop can attribute to one prompt: the synthesizer's. But a bad
report might really be a weak *specialist* — and with four of them writing into a
shared findings list, a single final score can't say which one to blame.

This module closes that gap. It groups the findings by agent and scores each
specialist on its own output, so a weak agent is identified by a number (and its
scores are pushed to Langfuse tagged per agent). That per-agent attribution is the
prerequisite for ever extending automatic prompt-improvement beyond the synthesizer.

Scores (all 0..1, computed offline — no LLM, so the test suite stays hermetic):

* **groundedness** — how well the agent's findings are supported by the evidence they
  cite (deterministic claim verification: supported 1, partial 0.5). A finding with a
  citation but no attached evidence text can't be checked and counts as cited-only.
  (Counting "has a citation" alone read ~1.0 for every agent, so it could never pick
  out a weak one.)
* **richness**     — how many solid, non-stub findings it produced (vs. a target).
* **score**        — the blend the dashboard/gate reads (grounding weighted higher).
"""

from __future__ import annotations

import logging

log = logging.getLogger("atlas.llmops.agent_eval")

# A specialist that returns fewer than this many solid findings is under-delivering.
_RICHNESS_TARGET = 3

# Fallback claims the specialists emit when they find nothing usable — not "solid".
_STUB_MARKERS = ("[offline stub]", "No well-grounded finding")


def _is_solid(finding: dict) -> bool:
    claim = str(finding.get("claim", "")).strip()
    if not claim:
        return False
    return not any(marker in claim for marker in _STUB_MARKERS)


def _has_citation(finding: dict) -> bool:
    cite = finding.get("citation")
    return bool(cite) and cite != "n/a"


def _support(finding: dict) -> float:
    """1 / 0.5 / 0 for a finding its cited evidence supports / partly / not at all."""
    if not _has_citation(finding):
        return 0.0
    evidence = str(finding.get("evidence_text") or "")
    if not evidence.strip():
        return 1.0  # cited, but no evidence attached to check against
    from .claim_verify import PARTIAL, SUPPORTED, verify_claim

    verdict = verify_claim(str(finding.get("claim", "")), evidence, use_llm=False).support
    return 1.0 if verdict == SUPPORTED else 0.5 if verdict == PARTIAL else 0.0


def score_agent(findings: list[dict]) -> dict:
    """Score one agent's findings on groundedness, richness, and the blend."""
    if not findings:
        return {"groundedness": 0.0, "richness": 0.0, "score": 0.0, "n_findings": 0}
    solid = [f for f in findings if _is_solid(f)]
    groundedness = round(sum(_support(f) for f in solid) / len(solid), 3) if solid else 0.0
    richness = round(min(1.0, len(solid) / _RICHNESS_TARGET), 3)
    score = round(0.7 * groundedness + 0.3 * richness, 3)
    return {
        "groundedness": groundedness,
        "richness": richness,
        "score": score,
        "n_findings": len(solid),
    }


def evaluate_agents(findings: list[dict], *, query: str = "", push: bool = True) -> dict[str, dict]:
    """Group findings by agent and score each. Returns {agent: {scores}}.

    When ``push`` is set and Langfuse is configured, each agent's scores are sent as
    their own trace tagged ``atlas_agent_eval:<agent>`` so they chart per specialist.
    """
    by_agent: dict[str, list[dict]] = {}
    for f in findings or []:
        by_agent.setdefault(f.get("agent", "unknown"), []).append(f)

    results = {agent: score_agent(items) for agent, items in by_agent.items()}
    for agent, s in results.items():
        log.info("agent_eval %s -> score=%.3f grounded=%.3f rich=%.3f (n=%d)",
                 agent, s["score"], s["groundedness"], s["richness"], s["n_findings"])

    if push and results:
        try:
            from ...eval.langfuse_scores import flush, push_item_scores

            for agent, s in results.items():
                claims = "; ".join(str(f.get("claim", "")) for f in by_agent[agent])
                push_item_scores(
                    {
                        "agent_score": s["score"],
                        "agent_groundedness": s["groundedness"],
                        "agent_richness": s["richness"],
                    },
                    question=f"[{agent}] {query}",
                    answer=claims[:500],
                    trace_name=f"atlas_agent_eval:{agent}",
                )
            flush()
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("Could not push per-agent scores to Langfuse: %s", exc)

    return results


def weakest_agent(results: dict[str, dict]) -> str | None:
    """Return the agent with the lowest score — the candidate to improve next."""
    if not results:
        return None
    return min(results, key=lambda a: results[a]["score"])
