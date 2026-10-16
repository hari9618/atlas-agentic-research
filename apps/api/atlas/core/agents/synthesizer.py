"""Synthesizer — turn findings + debate into an investor-grade, cited report.

Produces markdown with inline citations, an explicit confidence score, and a
"what we're not sure about" section. The grounding guardrail then tempers the
confidence by how well the report is actually cited.
"""

from __future__ import annotations

import logging

from ..guardrails import apply_grounding_guardrail
from ..state import ResearchState
from .base import chat, extract_json, llm_ready

log = logging.getLogger("atlas.agents.synthesizer")


def _collect_citations(findings: list[dict]) -> list[dict]:
    seen, out = set(), []
    for f in findings:
        c = f.get("citation")
        if c and c != "n/a" and c not in seen:
            seen.add(c)
            out.append({"citation": c, "agent": f.get("agent")})
    return out


def synthesize_node(state: ResearchState) -> dict:
    query = state["query"]
    findings = state.get("findings", [])
    debate = state.get("debate", [])
    citations = _collect_citations(findings)

    if not llm_ready():
        report = f"# Due-Diligence Brief (offline stub)\n\nQuestion: {query}\n\n" \
                 f"{len(findings)} findings, {len(debate)} debate turns."
        guard = apply_grounding_guardrail(report, findings, 0.5)
        return {"report": report, "confidence": guard["confidence"],
                "uncertainties": ["offline stub — no LLM synthesis"], "citations": citations}

    findings_block = "\n".join(
        f"- ({f['agent']}) {f['claim']} [{f.get('citation', 'n/a')}]" for f in findings
    )
    debate_block = "\n".join(f"{d['role'].upper()}: {d['text']}" for d in debate)

    # System prompt comes from the versioned registry (canary candidate or active
    # version) so the LLM-Ops loop can improve and release it. Lazy import avoids a cycle.
    from ..llmops.registry import get_registry

    system_prompt = get_registry().effective(
        "synthesizer_system", default="You are a senior analyst writing a grounded, cited brief."
    )

    report = chat(
        f"Write a clear, plain-English due-diligence briefing answering:\n\"{query}\"\n\n"
        f"FINDINGS (cite these inline using their bracketed labels):\n{findings_block}\n\n"
        f"DEBATE:\n{debate_block}\n\n"
        "Write for a busy, non-technical business reader. Use EXACTLY these markdown H2 "
        "sections, in this order. Keep each to 2-4 short sentences or a few short bullet "
        "points. Do NOT use markdown tables — plain sentences and bullets only.\n\n"
        "## Verdict\n"
        "One sentence: the answer to the question and the overall leaning (positive / "
        "neutral / cautious).\n\n"
        "## Business & Revenue\n"
        "How the company is doing financially — revenue, growth rate, momentum — in plain words.\n\n"
        "## What They Offer\n"
        "The main products or services they provide to their customers.\n\n"
        "## Competitors & Market Position\n"
        "Who they compete with, where they are strong, and where they are lagging.\n\n"
        "## Recent News & Sentiment\n"
        "The latest notable events and the overall mood (positive or negative).\n\n"
        "## Key Risks\n"
        "The main risks, stated plainly.\n\n"
        "## Bull vs Bear\n"
        "One bullet for the optimistic case, one bullet for the cautious case.\n\n"
        "## Bottom Line\n"
        "A 2-3 sentence plain-English summary a reader can act on.\n\n"
        "Rules: cite evidence inline using the bracketed labels; only assert what the "
        "findings support; if a section has no supporting evidence, write 'Not enough "
        "evidence yet.' Keep it concise and jargon-free.",
        system=system_prompt,
        temperature=0.3, run_name="synthesizer.report",
    )

    meta = chat(
        "Given this brief, output ONLY JSON with an overall confidence (0..1) and a list "
        'of uncertainties: {"confidence": 0.0, "uncertainties": ["..."]}\n\n'
        f"Brief:\n{report[:3000]}",
        temperature=0.0, run_name="synthesizer.meta",
    )
    parsed = extract_json(meta, default={})
    raw_conf = float(parsed.get("confidence", 0.6) or 0.6) if isinstance(parsed, dict) else 0.6
    uncertainties = parsed.get("uncertainties", []) if isinstance(parsed, dict) else []

    guard = apply_grounding_guardrail(report, findings, raw_conf)
    if not guard["grounding_ok"]:
        uncertainties = (uncertainties or []) + [
            f"Low citation coverage ({guard['citation_coverage']}) — confidence reduced."
        ]
    log.info("synthesized report, confidence=%.2f coverage=%.2f",
             guard["confidence"], guard["citation_coverage"])
    return {
        "report": report,
        "confidence": guard["confidence"],
        "uncertainties": uncertainties or ["None flagged."],
        "citations": citations,
    }
