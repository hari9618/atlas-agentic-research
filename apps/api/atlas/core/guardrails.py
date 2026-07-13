"""Output guardrail — the grounding rule.

Every claim in a report should trace to retrieved evidence. We compute a
**citation-coverage** ratio (how many of the findings' citations actually appear in
the report) and use it to temper the reported confidence. This is intentionally strict:
better to under-claim than to present an ungrounded number.
"""

from __future__ import annotations


def citation_coverage(report: str, findings: list[dict]) -> float:
    """Fraction of distinct finding-citations that are referenced in the report."""
    cites = {f.get("citation") for f in findings if f.get("citation") and f["citation"] != "n/a"}
    if not cites:
        return 0.0
    present = sum(1 for c in cites if c and (c in report or c.split(" (")[0] in report))
    return present / len(cites)


def apply_grounding_guardrail(report: str, findings: list[dict], raw_confidence: float) -> dict:
    """Adjust confidence by grounding; flag if the report is poorly cited."""
    coverage = citation_coverage(report, findings)
    # Confidence cannot exceed how well the report is grounded.
    grounded_confidence = round(min(raw_confidence, 0.3 + 0.7 * coverage), 3)
    return {
        "citation_coverage": round(coverage, 3),
        "confidence": grounded_confidence,
        "grounding_ok": coverage >= 0.5,
    }
