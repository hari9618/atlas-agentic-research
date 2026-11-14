"""Replay — paired evaluation of a candidate policy against the active one.

The old loop compared two *independent* full runs. Most of the difference between
two runs is noise (different web results, different sampling), so a "gain" was often
luck. Replay removes the noise by holding the inputs fixed:

* **specialist** — retrieve the evidence ONCE, then extract findings twice (baseline
  policy, candidate policy) from that same evidence. A retrieval-depth candidate sees
  the same ranked list, just more of it.
* **synthesizer** — rewrite the report twice from a recorded run's exact findings and
  debate.

Each pair is scored with the same judge, on several recent questions (distinct
companies), and only the per-question *difference* is used. It is also cheap: a
specialist trial costs two extraction calls instead of a whole research run.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass

from ...config import get_settings
from .policy import Policy

log = logging.getLogger("atlas.llmops.replay")

_STUBS = ("[offline stub]", "No well-grounded finding", "analysis is unavailable")
_RICHNESS_TARGET = 3


@dataclass
class Trial:
    query: str
    target: str
    baseline: float
    candidate: float

    @property
    def delta(self) -> float:
        return round(self.candidate - self.baseline, 3)

    def to_dict(self) -> dict:
        return {**asdict(self), "delta": self.delta}


def _llm_active() -> bool:
    return get_settings().llm_configured and os.getenv("ATLAS_OFFLINE_LLM") != "1"


def benchmark(records: list[dict], k: int, *, avoid: list[str] | None = None) -> list[dict]:
    """Up to ``k`` recent runs on distinct companies; runs in ``avoid`` (the ones the
    change was derived from) come last, so validation is on held-out runs first."""
    avoid = avoid or []
    usable = [r for r in records if r.get("findings") and r.get("query")]
    usable.sort(key=lambda r: (r.get("thread_id") in avoid,))  # stable: keeps recency
    picked, targets = [], set()
    for r in usable:
        key = (r.get("target") or r["query"]).lower()
        if key not in targets:
            targets.add(key)
            picked.append(r)
        if len(picked) == k:
            break
    return picked


def score_findings(findings: list[dict]) -> float:
    """0..1: how grounded (claim-verified against the cited evidence) and how rich."""
    from .agent_eval import score_agent
    from .claim_verify import PARTIAL, SUPPORTED, verify_claims

    solid = [f for f in findings if not any(m in str(f.get("claim", "")) for m in _STUBS)]
    if not solid:
        return 0.0
    check = verify_claims(solid, use_llm=_llm_active())
    verdicts = check["verdicts"]
    if verdicts:
        grounded = sum(1.0 if v["support"] == SUPPORTED else 0.5 if v["support"] == PARTIAL
                       else 0.0 for v in verdicts) / len(verdicts)
    else:  # no checkable factual claims: fall back to the deterministic agent score
        grounded = score_agent(solid)["groundedness"]
    richness = min(1.0, len(solid) / _RICHNESS_TARGET)
    return round(0.7 * grounded + 0.3 * richness, 3)


def score_report(report: str, findings: list[dict]) -> float:
    """0..1: share of the brief's statements the evidence supports, and correctly cited."""
    from .report_verify import verify_report

    if not report:
        return 0.0
    check = verify_report(report, findings, use_llm=_llm_active())
    return round((check["faithfulness"] + check["citation_accuracy"]) / 2, 3)


def _specialist_pair(component: str, record: dict, base: Policy, cand: Policy
                     ) -> tuple[float, float]:
    from ..agents.specialists import extract_findings, gather_evidence, merge_evidence

    # Replay with the production brief, so private-company changes are tested on the
    # same website / review / competitor evidence a real run gets.
    state = {"query": record["query"], "target": record.get("target", ""),
             "ticker": record.get("ticker", ""), "prior_context": [],
             **(record.get("brief") or {})}
    tools, crag = gather_evidence(component, state, max(base.top_k, cand.top_k))
    b = extract_findings(component, state, merge_evidence(tools, crag[:base.top_k]), base)
    c = extract_findings(component, state, merge_evidence(tools, crag[:cand.top_k]), cand)
    return score_findings(b), score_findings(c)


def _synthesizer_pair(record: dict, base: Policy, cand: Policy) -> tuple[float, float]:
    from ..agents.synthesizer import synthesize_with

    findings = record.get("findings") or []
    state = {"query": record["query"], "target": record.get("target", ""),
             "findings": findings, "debate": record.get("debate") or [], "revision": 0,
             **(record.get("brief") or {})}
    b = synthesize_with(state, base)["report"]
    c = synthesize_with(state, cand)["report"]
    return score_report(b, findings), score_report(c, findings)


PairRunner = Callable[[str, dict, Policy, Policy], tuple[float, float]]


def run_pair(component: str, record: dict, base: Policy, cand: Policy) -> tuple[float, float]:
    if component == "synthesizer":
        return _synthesizer_pair(record, base, cand)
    return _specialist_pair(component, record, base, cand)


def paired_trials(component: str, base: Policy, cand: Policy, records: list[dict], *,
                  runner: PairRunner = run_pair) -> tuple[list[Trial], int]:
    """``(trials, failed)``: one baseline-vs-candidate trial per benchmark record.
    Failures are counted, not hidden — ``decide`` refuses to conclude when any failed."""
    trials: list[Trial] = []
    failed = 0
    for r in records:
        try:
            b, c = runner(component, r, base, cand)
        except Exception as exc:
            failed += 1
            log.warning("replay trial on %r failed (%s)", r.get("query"), exc)
            continue
        trials.append(Trial(r["query"], r.get("target", ""), b, c))
        log.info("replay %s on %r: baseline=%.3f candidate=%.3f", component, r["query"], b, c)
    return trials, failed
