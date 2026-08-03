"""A deliberately simple RAG baseline: retrieve → single LLM synthesis.

The point is not to be another agent system — it is the control group. It shares
Atlas's retrieval (so the comparison isolates the *multi-agent + debate + verification*
contribution, not the retriever) but replaces the four specialists, the bull/bear
debate, the judge, and the synthesizer with one LLM call over all evidence.

Its output has the same shape as an Atlas run ({report, findings, confidence}), so the
exact same ``evaluate_run`` scores both — a fair, apples-to-apples comparison.
"""

from __future__ import annotations

import logging

from ..core.agents.base import chat, extract_json, format_evidence, llm_ready

log = logging.getLogger("atlas.eval.baseline")


def baseline_run(query: str, *, top_k: int = 6) -> dict:
    """Answer with a single retrieval + one LLM synthesis. No agents, no debate."""
    from ..core.graph import get_index
    from ..core.rag.crag import corrective_retrieve
    from ..core.rag.web_evidence import web_evidence

    chunks = corrective_retrieve(
        get_index(), query, top_k=top_k, web_fallback=web_evidence
    ).chunks

    def _finding(claim: str, ch, conf: float) -> dict:
        return {
            "agent": "baseline",
            "claim": claim,
            "citation": ch.citation() if ch else "n/a",
            "evidence_text": ch.text[:500] if ch else "",
            "evidence_id": ch.chunk_id if ch else "",
            "confidence": conf,
        }

    if not llm_ready():
        # Offline: synthesize deterministically from the top chunks so the harness
        # still runs hermetically (both systems degrade the same way offline).
        findings = [_finding(c.chunk.text[:160].strip(), c.chunk, 0.5) for c in chunks[:4]]
        report = "## Answer (baseline)\n" + " ".join(f["claim"] for f in findings)
        return {"report": report, "findings": findings, "confidence": 0.4,
                "uncertainties": [], "citations": [], "debate": [], "plan": []}

    evidence = format_evidence(chunks)
    prompt = (
        "Answer the question using ONLY the evidence below, citing the index of each "
        "supporting item. Return ONLY JSON:\n"
        '{"report": "<a short markdown brief>", '
        '"findings": [{"claim": "...", "citation_index": 1, "confidence": 0.0-1.0}]}\n\n'
        f"Question: {query}\n\nEvidence (cite by index):\n{evidence}"
    )
    raw = chat(prompt, system="You are an analyst writing a grounded, cited brief.",
               temperature=0.2, run_name="baseline.synthesize")
    parsed = extract_json(raw, default={})
    items = parsed.get("findings", []) if isinstance(parsed, dict) else []

    findings = []
    for it in items if isinstance(items, list) else []:
        idx = it.get("citation_index", 1)
        ch = chunks[idx - 1].chunk if isinstance(idx, int) and 1 <= idx <= len(chunks) else None
        findings.append(_finding(str(it.get("claim", "")).strip(), ch,
                                 float(it.get("confidence", 0.6) or 0.6)))
    report = parsed.get("report", "") if isinstance(parsed, dict) else str(raw)
    return {"report": report, "findings": findings, "confidence": None,
            "uncertainties": [], "citations": [], "debate": [], "plan": []}
