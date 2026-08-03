"""Claim-level citation verification tests (offline, deterministic).

Moves grounding from "is there a citation?" to "does the cited evidence actually
support this claim?" — supported / partial / unsupported, plus the coverage metric.
"""

from __future__ import annotations

from atlas.core.llmops.claim_verify import (
    PARTIAL,
    SUPPORTED,
    UNSUPPORTED,
    verify_claim,
    verify_claims,
)

EVIDENCE = (
    "Helios Robotics reported total revenue of 4.2 billion dollars in fiscal 2025, up 28% "
    "year over year. Its three largest customers accounted for 39% of revenue."
)


# ---- single-claim entailment (deterministic, no LLM) ----

def test_supported_claim_with_matching_figures():
    v = verify_claim("Helios revenue was 4.2 billion in 2025", EVIDENCE, use_llm=False)
    assert v.support == SUPPORTED and v.method == "deterministic"


def test_unsupported_claim_with_wrong_figure():
    v = verify_claim("Helios revenue was 9.9 billion in 2025", EVIDENCE, use_llm=False)
    assert v.support == UNSUPPORTED  # the number simply isn't in the evidence


def test_unsupported_claim_off_topic():
    v = verify_claim("The weather in Paris was sunny", EVIDENCE, use_llm=False)
    assert v.support == UNSUPPORTED


def test_partial_claim_some_figures_match():
    # 28% is in the evidence; 55% is not — a mix is a partial, not a pass.
    v = verify_claim("Revenue grew 28% and margins were 55%", EVIDENCE, use_llm=False)
    assert v.support == PARTIAL


def test_missing_evidence_text_is_unsupported():
    v = verify_claim("anything at all", "", use_llm=False)
    assert v.support == UNSUPPORTED


# ---- claim set + coverage metric ----

def test_uncited_factual_claim_fails():
    findings = [{"agent": "risk", "claim": "Revenue was 4.2 billion", "citation": "n/a"}]
    out = verify_claims(findings, use_llm=False)
    assert out["supported"] == 0 and out["verdicts"][0]["support"] == UNSUPPORTED


def test_citation_coverage_is_claim_level():
    findings = [
        {"agent": "a", "claim": "Revenue was 4.2 billion in 2025",
         "citation": "Helios 10-K (sec_edgar#0)", "evidence_text": EVIDENCE},
        {"agent": "b", "claim": "Top three customers were 39% of revenue",
         "citation": "Helios 10-K (sec_edgar#1)", "evidence_text": EVIDENCE},
        {"agent": "c", "claim": "Revenue was 9.9 billion",  # wrong number → unsupported
         "citation": "Helios 10-K (sec_edgar#2)", "evidence_text": EVIDENCE},
    ]
    out = verify_claims(findings, use_llm=False)
    assert out["total_claims"] == 3
    assert out["supported"] == 2
    assert out["citation_coverage"] == round(2 / 3, 3)  # supported / total, claim-level
    # citation_correctness: of the 3 that cite, 2 actually check out.
    assert out["citation_correctness"] == round(2 / 3, 3)


def test_stub_findings_are_not_counted_as_claims():
    findings = [
        {"agent": "x", "claim": "[offline stub] risk analysis", "citation": "n/a"},
        {"agent": "y", "claim": "No well-grounded finding extracted.", "citation": "n/a"},
    ]
    out = verify_claims(findings, use_llm=False)
    assert out["total_claims"] == 0 and out["citation_coverage"] == 0.0
