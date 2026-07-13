"""The release gate — did the run pass? If not, why?

A run must clear every threshold to pass. The failing reasons become the diagnosis
the optimizer uses to rewrite the prompt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

THRESHOLDS = {
    "faithfulness": 0.50,  # grounding / citation coverage
    "relevancy": 0.60,     # answers the question
}


@dataclass
class GateResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)
    scores: dict = field(default_factory=dict)


def run_gate(scores: dict) -> GateResult:
    """Check scores against thresholds; a run must clear all of them to pass."""
    reasons = [
        f"{k} {scores.get(k, 0.0):.2f} < {thr:.2f}"
        for k, thr in THRESHOLDS.items()
        if scores.get(k, 0.0) < thr
    ]
    return GateResult(passed=not reasons, reasons=reasons, scores=scores)
