"""Claim-level citation verification (Phase 3).

The old guardrail asked *"does the answer contain a citation?"*. This asks the harder,
more honest question: *"does the cited evidence actually support this claim?"*

Each finding is already a claim + a citation + (now) the cited evidence text, so
verification runs per finding:

    claim ─► cited evidence ─► entailment check ─► supported / partial / unsupported

The check is **deterministic first** — figures in the claim must appear in the
evidence, plus a lexical-overlap floor — because that is cheap, reproducible, and not
gameable by an LLM's self-report. The LLM-as-judge is used *only* for the genuinely
ambiguous middle (moderate overlap, no decisive numbers), and only when an LLM is
active. Offline, verification is fully deterministic so the test suite stays hermetic.

Phase 4 metrics fall straight out of the verdicts:

    citation_coverage    = supported claims / total factual claims
    citation_correctness = supported claims / claims that carry a citation
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import asdict, dataclass

from ...config import get_settings

log = logging.getLogger("atlas.llmops.claim_verify")

SUPPORTED = "supported"
PARTIAL = "partial"
UNSUPPORTED = "unsupported"

# Claims that are stub/fallback text, not real factual claims to verify.
_STUB_MARKERS = ("[offline stub]", "No well-grounded finding")

# Numbers with an optional unit/scale, normalized so "4.2 billion", "$4.2B" and
# "4.2 billion dollars" all compare equal.
_NUM = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(%|percent|billion|million|thousand|bn|b|m|k)?", re.I)
_SCALE = {"percent": "%", "%": "%", "bn": "b", "billion": "b", "b": "b",
          "million": "m", "m": "m", "thousand": "k", "k": "k"}
_WORD = re.compile(r"[a-z0-9]+")
_STOP = frozenset({
    "the", "a", "an", "of", "to", "in", "and", "or", "is", "are", "was", "were", "for",
    "on", "with", "as", "at", "by", "its", "it", "this", "that", "these", "those",
    "from", "has", "have", "had", "will", "be", "been",
})


def _llm_active() -> bool:
    return get_settings().llm_configured and os.getenv("ATLAS_OFFLINE_LLM") != "1"


def _key_figures(text: str) -> set[str]:
    """Material figures only — money/percent/scaled numbers, normalized.

    A bare integer like a year ("2025") is deliberately excluded: a claim of "$9.9B
    in 2025" must not count as supported just because the evidence also says "2025".
    """
    out: set[str] = set()
    for num, scale in _NUM.findall(text or ""):
        s = _SCALE.get(scale.lower(), "") if scale else ""
        if s:  # keep only numbers carrying a unit/scale (b, m, k, %)
            out.add(num.replace(",", "") + s)
    return out


def _content_words(text: str) -> set[str]:
    return {w for w in _WORD.findall((text or "").lower()) if w not in _STOP and len(w) > 2}


def _overlap(claim: str, evidence: str) -> float:
    """Fraction of the claim's content words that appear in the evidence."""
    c = _content_words(claim)
    if not c:
        return 0.0
    return len(c & _content_words(evidence)) / len(c)


def is_factual(finding: dict) -> bool:
    claim = str(finding.get("claim", "")).strip()
    return bool(claim) and not any(m in claim for m in _STUB_MARKERS)


@dataclass
class ClaimVerdict:
    claim: str
    citation: str
    evidence_id: str
    support: str
    reason: str
    method: str  # "deterministic" or "llm"


def _deterministic(claim: str, evidence: str) -> tuple[str, str, bool]:
    """Return (verdict, reason, confident). ``confident`` gates the LLM fallback."""
    if not evidence.strip():
        return UNSUPPORTED, "no evidence text attached", True
    cnums, enums = _key_figures(claim), _key_figures(evidence)
    overlap = _overlap(claim, evidence)
    if cnums:
        missing = cnums - enums
        if not missing and overlap >= 0.12:
            return SUPPORTED, f"all {len(cnums)} figure(s) present in evidence", True
        if missing == cnums:
            return UNSUPPORTED, "claim figures absent from the cited evidence", True
        return PARTIAL, "some figures match, some do not", False
    if overlap >= 0.40:
        return SUPPORTED, f"high lexical overlap ({overlap:.2f})", True
    if overlap <= 0.10:
        return UNSUPPORTED, f"low lexical overlap ({overlap:.2f})", True
    return PARTIAL, f"moderate overlap ({overlap:.2f})", False


def _llm_judge(claim: str, evidence: str) -> str | None:
    from ...llm import get_llm
    from ...observability import langchain_callbacks

    try:
        resp = get_llm(temperature=0.0, model=get_settings().summarizer_model).invoke(
            "Does the EVIDENCE support the CLAIM? Reply with exactly one word: "
            f"supported, partial, or unsupported.\n\nCLAIM: {claim}\n\nEVIDENCE: {evidence[:1200]}",
            config={"callbacks": langchain_callbacks(), "run_name": "ops.verify_claim"},
        )
        text = (resp.content if hasattr(resp, "content") else str(resp)).lower()
        for v in (UNSUPPORTED, PARTIAL, SUPPORTED):  # check 'unsupported' before 'supported'
            if v in text:
                return v
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("claim LLM judge failed: %s", exc)
    return None


def verify_claim(claim: str, evidence: str, *, use_llm: bool) -> ClaimVerdict:
    verdict, reason, confident = _deterministic(claim, evidence)
    method = "deterministic"
    if not confident and use_llm and evidence.strip():
        judged = _llm_judge(claim, evidence)
        if judged:
            verdict, reason, method = judged, "LLM entailment judge", "llm"
    return ClaimVerdict(claim, "", "", verdict, reason, method)


def verify_claims(findings: list[dict], *, use_llm: bool | None = None,
                  max_claims: int = 24) -> dict:
    """Verify every factual claim against its cited evidence. Returns verdicts + metrics."""
    if use_llm is None:
        use_llm = _llm_active()

    verdicts: list[ClaimVerdict] = []
    for f in [f for f in findings if is_factual(f)][:max_claims]:
        claim = str(f.get("claim", "")).strip()
        cite = f.get("citation", "n/a")
        has_cite = bool(cite) and cite != "n/a"
        if not has_cite:
            # An uncited factual claim cannot be supported — fail it deterministically.
            verdicts.append(ClaimVerdict(claim, "n/a", "", UNSUPPORTED,
                                         "factual claim carries no citation", "deterministic"))
            continue
        v = verify_claim(claim, f.get("evidence_text", ""), use_llm=use_llm)
        v.citation, v.evidence_id = cite, f.get("evidence_id", "")
        verdicts.append(v)

    total = len(verdicts)
    supported = sum(1 for v in verdicts if v.support == SUPPORTED)
    partial = sum(1 for v in verdicts if v.support == PARTIAL)
    unsupported = sum(1 for v in verdicts if v.support == UNSUPPORTED)
    cited = sum(1 for v in verdicts if v.citation and v.citation != "n/a")
    return {
        "verdicts": [asdict(v) for v in verdicts],
        "total_claims": total,
        "cited_claims": cited,
        "supported": supported,
        "partial": partial,
        "unsupported": unsupported,
        # Phase 4 metrics — claim-level, not a count of citation markers.
        "citation_coverage": round(supported / total, 3) if total else 0.0,
        "citation_correctness": round(supported / cited, 3) if cited else 0.0,
    }
