"""Synthesizer — turn findings + debate into an investor-grade, cited report.

One LLM call returns the structured brief (design §1) as JSON — sections, confidence
and uncertainties together, so there is no second "meta" call to pay for. The JSON is
normalized to the contract, rendered to markdown, and the grounding guardrail measures
citation coverage on that markdown to temper the confidence.

On a human revision request the previous draft and the reviewer's feedback are part
of the prompt, so the rewrite addresses the feedback instead of starting over.

Failure ladder (design §5): bad JSON → one strict "JSON only" retry → plain markdown
brief with ``report_sections=None`` → if even that fails, the run errors.
"""

from __future__ import annotations

import json
import logging

from langchain_core.runnables import RunnableConfig

from ...config import get_settings
from ..guardrails import apply_grounding_guardrail
from ..state import ResearchState
from .base import chat, extract_json, llm_ready, salvage_json_object
from .report_render import render_markdown
from .report_schema import NOT_ENOUGH, normalize_brackets, normalize_sections

log = logging.getLogger("atlas.agents.synthesizer")

_SCHEMA = """{
  "company": "company name",
  "headline": "one sentence that answers the user's question",
  "stance": "positive | neutral | cautious",
  "confidence": 0.0,
  "bottom_line": "2-3 sentences a reader can act on",
  "executive_summary": ["3-5 bullets: the findings that matter most, each cited"],
  "company_overview": {"what_they_do": "...", "business_model": "how they make money",
                       "products": ["main products / services"], "customers": "who buys and why"},
  "financials": {"summary": "growth and financial health in plain words",
                 "metrics": [{"label": "Revenue (FY2025)", "value": "...", "change": "...",
                              "citation": "[label]"}]},
  "market_position": {"summary": "...", "strengths": ["..."], "weaknesses": ["..."]},
  "competitors": [{"name": "...", "comparison": "how they compare",
                   "threat": "high | medium | low", "citation": "[label]"}],
  "recent_developments": [{"date": "...", "title": "short headline",
                           "detail": "what happened and why it matters",
                           "sentiment": "positive | neutral | negative", "citation": "[label]"}],
  "sentiment": {"overall": "positive | mixed | negative", "summary": "the overall mood"},
  "risks": [{"title": "...", "severity": "high | medium | low", "detail": "...",
             "citation": "[label]"}],
  "bull_case": ["optimistic points, cited"],
  "bear_case": ["cautious points, cited"],
  "outlook": {"summary": "what to expect", "watch_items": ["what an investor should monitor"]},
  "uncertainties": ["what we are NOT sure about"]
}"""

_RULES = (
    "Rules:\n"
    "- Write in plain English for a busy, non-technical investor. No jargon, no tables.\n"
    "- Be brief — a brief that gets read beats a long one: every text field at most 2 "
    "short sentences; every list at most 4 items (risks and recent_developments at most "
    "5, financial metrics at most 6); every bullet under 25 words. Pick what matters most "
    "to an investor; leave out minor details.\n"
    "- Every factual claim MUST end with its citation: the exact bracketed label shown "
    "after the finding it came from, e.g. [Acme 10-K (sec_edgar#0)]. List items also put "
    "that label in their \"citation\" field.\n"
    "- Only state what the findings support. Never invent numbers, names or dates.\n"
    f"- If there is no evidence for a field, use [] or the string \"{NOT_ENOUGH}\".\n"
    "- Enum fields use exactly the listed lowercase values.\n"
    "- confidence is 0..1: how well the evidence answers the question.\n"
    "- uncertainties lists what the evidence does NOT establish.\n"
    "- Return ONLY the JSON object — no prose, no markdown fences."
)


def _collect_citations(findings: list[dict]) -> list[dict]:
    seen, out = set(), []
    for f in findings:
        c = f.get("citation")
        if c and c != "n/a" and c not in seen:
            seen.add(c)
            out.append({"citation": c, "agent": f.get("agent")})
    return out


def _findings_block(findings: list[dict]) -> str:
    return "\n".join(
        f"- ({f.get('agent', '?')}) {f.get('claim', '')} [{f.get('citation', 'n/a')}]"
        for f in findings
    ) or "(no findings)"


def _debate_block(debate: list[dict]) -> str:
    return "\n".join(f"{d.get('role', '?').upper()}: {str(d.get('text', ''))[:900]}"
                     for d in debate) or "(no debate)"


def _revision_block(state: ResearchState) -> str:
    revision = state.get("revision") or 0
    feedback = (state.get("feedback") or "").strip()
    if revision <= 0 or not feedback:
        return ""
    prev = state.get("report_sections")
    prev_text = (json.dumps(prev, ensure_ascii=False)[:3000] if prev
                 else (state.get("report") or "")[:3000])
    return (
        f"\n\nREVISION {revision}: a human reviewer read the previous draft and asked:\n"
        f'"{feedback}"\n'
        "Address this feedback specifically: expand or correct the sections it concerns "
        "using the findings (follow-up findings gathered for this feedback are tagged "
        "(reviewer_followup)). Keep the parts of the previous draft that were good. If the "
        "evidence cannot satisfy the request, say so in uncertainties.\n"
        f"PREVIOUS DRAFT:\n{prev_text}"
    )


def _entity_line(state: ResearchState) -> str:
    target = state.get("target") or ""
    if not target:
        return ""
    return (f"Only use evidence about {target}; ignore anything about other companies with "
            "similar names, and say so in uncertainties if evidence looked ambiguous.\n\n")


def _structured_prompt(state: ResearchState) -> str:
    target = state.get("target") or "the company"
    findings = _findings_block(state.get("findings", []))
    return (
        f"Write an investor-grade due-diligence brief on {target}, answering:\n"
        f"\"{state['query']}\"\n\n"
        f"FINDINGS (each ends with its citation label):\n{findings}"
        f"\n\nBULL vs BEAR DEBATE:\n{_debate_block(state.get('debate', []))}"
        f"{_revision_block(state)}\n\n"
        f"{_entity_line(state)}"
        f"Return a JSON object with exactly this shape:\n{_SCHEMA}\n\n{_RULES}"
    )


def _system_prompt() -> str:
    # System prompt comes from the versioned registry (canary candidate or active
    # version) so the LLM-Ops loop can improve and release it. Lazy import avoids a cycle.
    from ..llmops.registry import get_registry

    return get_registry().effective(
        "synthesizer_system", default="You are a senior analyst writing a grounded, cited brief."
    )


_RETRY_NUDGE = (
    "\n\nIMPORTANT: your previous reply was cut off before the JSON was complete, or was "
    "not valid JSON. Return ONE valid JSON object and keep it SHORT: one sentence per "
    "text field and at most 3 items per list."
)


def _structured_sections(state: ResearchState, system: str | None = None) -> dict | None:
    """One JSON call; salvage a cut-off reply; else one shorter retry. None if both fail.

    The usual failure is the reply hitting the token limit mid-object (rich evidence →
    long sections). Retrying the same prompt just gets cut off again, so: keep every
    section that was fully written (bottom line and verdict come first in the schema
    for exactly this reason), and if nothing is salvageable, retry asking for less.
    """
    prompt = _structured_prompt(state)
    budget = get_settings().synth_max_tokens
    system = system or _system_prompt()
    company = state.get("target") or ""
    for attempt, nudge in enumerate(("", _RETRY_NUDGE)):
        raw = chat(prompt + nudge, system=system, temperature=0.2, max_tokens=budget,
                   run_name="synthesizer.report" if attempt == 0 else "synthesizer.report_retry")
        parsed = extract_json(raw, default=None)
        if not isinstance(parsed, dict):
            salvaged = salvage_json_object(raw)
            if salvaged:
                log.warning("synthesizer reply was cut off — salvaged %d complete fields",
                            len(salvaged))
                parsed = salvaged
        sections = normalize_sections(parsed, company=company)
        if sections:
            return sections
        log.warning("synthesizer JSON unusable (attempt %d)", attempt + 1)
    return None


def _markdown_fallback(state: ResearchState, system: str | None = None) -> str:
    """The pre-structured plain markdown brief — used when JSON generation fails."""
    feedback = (state.get("feedback") or "").strip() if (state.get("revision") or 0) > 0 else ""
    fb = f"\n\nA human reviewer asked: \"{feedback}\" — address it.\n" if feedback else ""
    return chat(
        f"Write a clear, plain-English due-diligence briefing answering:\n\"{state['query']}\"\n\n"
        f"FINDINGS (cite these inline using their bracketed labels):\n"
        f"{_findings_block(state.get('findings', []))}\n\n"
        f"DEBATE:\n{_debate_block(state.get('debate', []))}{fb}\n\n"
        f"{_entity_line(state)}"
        "Use these markdown H2 sections: Verdict, Business & Revenue, What They Offer, "
        "Competitors & Market Position, Recent News & Sentiment, Key Risks, Bull vs Bear, "
        "Bottom Line. 2-4 short sentences or bullets each, no tables. Cite evidence inline "
        "using the bracketed labels; only assert what the findings support; if a section "
        f"has no supporting evidence, write '{NOT_ENOUGH}'",
        system=system or _system_prompt(), temperature=0.3,
        run_name="synthesizer.report_markdown",
    )


def _degradation_notes(findings: list[dict]) -> list[str]:
    return [
        f"The {f.get('agent', 'an').replace('_', ' ')} analysis was unavailable this run, "
        "so that angle may be incomplete."
        for f in findings if f.get("unavailable")
    ]


def _finalize(sections: dict, findings: list[dict], citations: list[dict]) -> dict:
    """Guardrail on the rendered markdown, then re-render with the tempered values."""
    guard = apply_grounding_guardrail(render_markdown(sections), findings,
                                      sections.get("confidence", 0.5))
    uncertainties = list(sections.get("uncertainties") or []) + _degradation_notes(findings)
    if not guard["grounding_ok"]:
        uncertainties.append(
            f"Low citation coverage ({guard['citation_coverage']}) — confidence reduced.")
    sections = {**sections, "confidence": guard["confidence"],
                "uncertainties": uncertainties or ["None flagged."]}
    log.info("synthesized structured report, confidence=%.2f coverage=%.2f",
             guard["confidence"], guard["citation_coverage"])
    return {
        "report": render_markdown(sections),
        "report_sections": sections,
        "confidence": guard["confidence"],
        "uncertainties": sections["uncertainties"],
        "citations": citations,
    }


def _offline_sections(state: ResearchState) -> dict:
    """Deterministic, schema-shaped stub built only from the (cited) findings."""
    findings = state.get("findings", [])
    debate = state.get("debate", [])
    target = state.get("target") or state["query"]
    revision = state.get("revision") or 0

    def cited(f: dict) -> str:
        c = f.get("citation") or "n/a"
        return f"{f.get('claim', '')} [{c}]" if c != "n/a" else f.get("claim", "")

    def of(agent: str) -> list[dict]:
        return [f for f in findings if f.get("agent") == agent]

    summary = [cited(f) for f in findings[:4]] or [NOT_ENOUGH]
    if revision and state.get("feedback"):
        summary.append(f"[offline stub] Revision {revision} addresses: {state['feedback']}")
    raw = {
        "company": target,
        "headline": f"[offline stub] Draft brief on {target} (revision {revision}).",
        "stance": "neutral",
        "confidence": 0.5,
        "executive_summary": summary,
        "company_overview": {
            "what_they_do": " ".join(cited(f) for f in of("fundamentals")) or NOT_ENOUGH,
            "business_model": NOT_ENOUGH, "products": [], "customers": NOT_ENOUGH,
        },
        "financials": {"summary": NOT_ENOUGH, "metrics": []},
        "market_position": {
            "summary": " ".join(cited(f) for f in of("market")) or NOT_ENOUGH,
            "strengths": [], "weaknesses": [],
        },
        "competitors": [],
        "recent_developments": [
            {"title": "News finding", "detail": f.get("claim", ""), "sentiment": "neutral",
             "citation": f.get("citation", "")} for f in of("news_sentiment")
        ],
        "sentiment": {"overall": "mixed", "summary": NOT_ENOUGH},
        "risks": [
            {"title": "Risk finding", "severity": "medium", "detail": f.get("claim", ""),
             "citation": f.get("citation", "")} for f in of("risk")
        ],
        "bull_case": [d["text"] for d in debate if d.get("role") == "bull"][-1:],
        "bear_case": [d["text"] for d in debate if d.get("role") == "bear"][-1:],
        "outlook": {"summary": NOT_ENOUGH, "watch_items": []},
        "bottom_line": f"[offline stub] {len(findings)} findings, {len(debate)} debate turns.",
        "uncertainties": ["offline stub — no LLM synthesis"],
    }
    return normalize_sections(raw, company=target) or {}


def _prompt_override(config: RunnableConfig | None) -> str | None:
    """A candidate system prompt the LLM-Ops optimizer is trialling on THIS run only.

    Carried in the run config rather than the shared registry, so concurrent user
    runs keep the active prompt while a candidate is being evaluated.
    """
    return ((config or {}).get("configurable") or {}).get("synthesizer_system_override")


def synthesize_node(state: ResearchState, config: RunnableConfig | None = None) -> dict:
    findings = state.get("findings", [])
    system = _prompt_override(config)
    citations = _collect_citations(findings)

    if not llm_ready():
        return _finalize(_offline_sections(state), findings, citations)

    try:
        sections = _structured_sections(state, system)
    except Exception as exc:  # LLM failure after retries → simpler prompt below
        log.warning("structured synthesis failed (%s: %s); falling back to markdown",
                    type(exc).__name__, exc)
        sections = None
    if sections:
        return _finalize(sections, findings, citations)

    # Last resort: plain markdown. If this raises too, the run errors (by design).
    report = normalize_brackets(_markdown_fallback(state, system))
    guard = apply_grounding_guardrail(report, findings, 0.6)
    uncertainties = ["The structured brief could not be generated this run; "
                     "this is a plain-text summary.", *_degradation_notes(findings)]
    if not guard["grounding_ok"]:
        uncertainties.append(
            f"Low citation coverage ({guard['citation_coverage']}) — confidence reduced.")
    return {
        "report": report,
        "report_sections": None,
        "confidence": guard["confidence"],
        "uncertainties": uncertainties,
        "citations": citations,
    }


def with_uncertainty(state: ResearchState, note: str) -> dict:
    """State update that appends ``note`` to the uncertainties of the current draft.

    Keeps ``report`` / ``report_sections`` / ``uncertainties`` consistent, e.g. when the
    review loop auto-approves at the revision cap.
    """
    uncertainties = [u for u in (state.get("uncertainties") or []) if u != "None flagged."]
    uncertainties.append(note)
    sections = state.get("report_sections")
    if sections:
        sections = {**sections, "uncertainties": uncertainties}
        return {"uncertainties": uncertainties, "report_sections": sections,
                "report": render_markdown(sections)}
    report = (state.get("report") or "").rstrip() + f"\n\n- {note}\n"
    return {"uncertainties": uncertainties, "report": report}
