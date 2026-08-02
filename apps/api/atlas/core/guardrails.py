"""Output guardrail — the grounding rule.

Every claim in a report should trace to retrieved evidence. We compute a
**citation-coverage** ratio (how many of the findings' citations actually appear in
the report) and use it to temper the reported confidence. This is intentionally strict:
better to under-claim than to present an ungrounded number.
"""

from __future__ import annotations

from .rag.provenance import is_derived_citation


def _distinct_citations(findings: list[dict]) -> set[str]:
    return {f.get("citation") for f in findings if f.get("citation") and f["citation"] != "n/a"}


def _present(citation: str, report: str) -> bool:
    return citation in report or citation.split(" (")[0] in report


def citation_coverage(report: str, findings: list[dict]) -> float:
    """Fraction of distinct finding-citations that are referenced in the report."""
    cites = _distinct_citations(findings)
    if not cites:
        return 0.0
    return sum(1 for c in cites if _present(c, report)) / len(cites)


def authoritative_support(report: str, findings: list[dict]) -> dict:
    """Distinguish authoritative grounding from Atlas-derived context.

    ``authoritative_coverage`` counts only *non-derived* citations that appear in the
    report, over all distinct citations — so a report grounded only in Atlas's own
    derived memory scores low even if every claim technically carries a citation.
    """
    cites = _distinct_citations(findings)
    if not cites:
        return {"authoritative_coverage": 0.0, "derived_evidence_used": False,
                "authoritative_citations": 0, "total_citations": 0}
    authoritative = {c for c in cites if not is_derived_citation(c)}
    present = sum(1 for c in authoritative if _present(c, report))
    return {
        "authoritative_coverage": round(present / len(cites), 3),
        "derived_evidence_used": any(is_derived_citation(c) for c in cites),
        "authoritative_citations": len(authoritative),
        "total_citations": len(cites),
    }


def apply_grounding_guardrail(report: str, findings: list[dict], raw_confidence: float) -> dict:
    """Adjust confidence by grounding; flag if the report is poorly or derived-only cited."""
    coverage = citation_coverage(report, findings)
    auth = authoritative_support(report, findings)
    # Confidence is capped by grounding, and further by *authoritative* grounding —
    # a report leaning on Atlas's own derived facts cannot claim full confidence.
    grounded_confidence = round(
        min(raw_confidence, 0.3 + 0.7 * coverage, 0.4 + 0.6 * auth["authoritative_coverage"]), 3
    )
    return {
        "citation_coverage": round(coverage, 3),
        "authoritative_coverage": auth["authoritative_coverage"],
        "derived_evidence_used": auth["derived_evidence_used"],
        "confidence": grounded_confidence,
        "grounding_ok": coverage >= 0.5,
    }
