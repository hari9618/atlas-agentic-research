"""Structured report (design §1): normalization, markdown render, synthesizer ladder.

All offline: the LLM is replaced by a scripted ``chat`` so each failure path —
bad enums, bad JSON, LLM down — is exercised deterministically.
"""

from __future__ import annotations

import json

import pytest

from atlas.core.agents import synthesizer as syn
from atlas.core.agents.report_render import render_markdown
from atlas.core.agents.report_schema import NOT_ENOUGH, clamp_confidence, normalize_sections

CITE_A = "Acme 10-K (sec_edgar#0)"
CITE_B = "Acme news (company_news#0) [web]"
FINDINGS = [
    {"agent": "fundamentals", "claim": "Revenue grew 20%.", "citation": CITE_A, "confidence": 0.8},
    {"agent": "news_sentiment", "claim": "Launched a robot.", "citation": CITE_B,
     "confidence": 0.7},
]

GOOD = {
    "company": "Acme",
    "headline": f"Acme is growing fast [{CITE_A}].",
    "stance": "BULLISH",
    "confidence": "85%",
    "executive_summary": f"Revenue grew 20% [{CITE_A}].",
    "company_overview": {"what_they_do": "Builds robots.", "products": "Arm X",
                         "business_model": None, "customers": ["Warehouses", "Retail"]},
    "financials": {"summary": "Healthy.", "metrics": [
        {"label": "Revenue growth", "value": "20%", "change": "", "citation": f"[{CITE_A}]"},
        {"label": "no value"}, "junk"]},
    "market_position": {"summary": "Leader.", "strengths": ["Tech"], "weaknesses": "Small"},
    "competitors": [{"name": "Beta Corp", "comparison": "Bigger", "threat": "Severe",
                     "citation": CITE_B}, {"comparison": "nameless"}, "Gamma Inc"],
    "recent_developments": [{"date": "Mar 2026", "title": "Launch", "detail": "New robot",
                             "sentiment": "bullish", "citation": f"[{CITE_B}]"}],
    "sentiment": {"overall": "neutral", "summary": "Mixed mood."},
    "risks": [{"title": "Concentration", "severity": "moderate", "detail": "Top client",
               "citation": CITE_A}],
    "bull_case": ["Growth"], "bear_case": [{"point": "Valuation"}],
    "outlook": {"summary": "Steady.", "watch_items": "Margins"},
    "bottom_line": "Worth watching.",
    "uncertainties": ["Private financials"],
    "unknown_key": "dropped",
}


def test_normalize_coerces_enums_types_and_drops_junk():
    s = normalize_sections(GOOD)
    assert s["stance"] == "positive"
    assert s["confidence"] == 0.85
    assert s["executive_summary"] == [f"Revenue grew 20% [{CITE_A}]."]
    assert s["company_overview"]["products"] == ["Arm X"]
    assert s["company_overview"]["business_model"] == ""
    assert s["company_overview"]["customers"] == "Warehouses; Retail"
    assert [m["label"] for m in s["financials"]["metrics"]] == ["Revenue growth"]
    assert [c["name"] for c in s["competitors"]] == ["Beta Corp", "Gamma Inc"]
    assert s["competitors"][0]["threat"] == "high"
    assert s["competitors"][1]["threat"] == "medium"
    assert s["recent_developments"][0]["sentiment"] == "positive"
    assert s["sentiment"]["overall"] == "mixed"
    assert s["risks"][0]["severity"] == "medium"
    assert s["market_position"]["weaknesses"] == ["Small"]
    assert s["bear_case"] == ["Valuation"]
    assert s["outlook"]["watch_items"] == ["Margins"]
    assert "unknown_key" not in s


def test_normalize_rejects_non_reports():
    assert normalize_sections(None) is None
    assert normalize_sections(["not", "a", "dict"]) is None
    assert normalize_sections({"stance": "positive"}) is None  # nothing substantive


@pytest.mark.parametrize("raw,expected", [
    (0.4, 0.4), ("0.4", 0.4), (72, 0.72), ("72%", 0.72), (-1, 0.0), ("high", 0.5), (None, 0.5),
])
def test_clamp_confidence(raw, expected):
    assert clamp_confidence(raw) == expected


def test_render_markdown_has_sections_and_every_citation():
    s = normalize_sections(GOOD)
    md = render_markdown(s)
    for heading in ("# Acme: Investor Brief", "## Executive Summary", "## Company Overview",
                    "## Financials", "## Market Position", "## Competitors",
                    "## Recent Developments", "## Sentiment", "## Key Risks", "## Bull Case",
                    "## Bear Case", "## Outlook", "## Bottom Line",
                    "## What We're Not Sure About"):
        assert heading in md
    assert "**Beta Corp** (threat: high)" in md
    assert "**Concentration** (severity: medium)" in md
    assert CITE_A in md and CITE_B in md
    assert f"[[{CITE_A}]]" not in md  # pre-bracketed citations are not double-wrapped


def test_render_hides_empty_sections_but_keeps_not_enough_evidence():
    s = normalize_sections({"headline": "H", "financials": {"summary": NOT_ENOUGH}})
    md = render_markdown(s)
    assert "## Competitors" not in md and "## Key Risks" not in md
    assert NOT_ENOUGH in md


def _script(monkeypatch, replies):
    """Make the synthesizer's LLM return/raise ``replies`` in order."""
    calls = []

    def fake_chat(prompt, **kw):
        calls.append({"prompt": prompt, **kw})
        r = replies[len(calls) - 1]
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(syn, "llm_ready", lambda: True)
    monkeypatch.setattr(syn, "chat", fake_chat)
    monkeypatch.setattr(syn, "_system_prompt", lambda: "system")
    return calls


def _state(**extra):
    return {"query": "Should I invest in Acme?", "target": "Acme", "findings": FINDINGS,
            "debate": [{"role": "judge", "text": "Balanced", "leaning": "neutral"}], **extra}


def test_synthesizer_structured_path(monkeypatch):
    calls = _script(monkeypatch, [json.dumps(GOOD)])
    out = syn.synthesize_node(_state())
    assert len(calls) == 1  # one call: no separate confidence/uncertainty "meta" call
    from atlas.config import get_settings

    assert calls[0]["max_tokens"] == get_settings().synth_max_tokens
    assert out["report_sections"]["stance"] == "positive"
    assert out["report"].startswith("# Acme: Investor Brief")
    assert 0.0 <= out["confidence"] <= 0.85  # guardrail never raises confidence
    assert out["report_sections"]["confidence"] == out["confidence"]
    assert {c["citation"] for c in out["citations"]} == {CITE_A, CITE_B}


def test_synthesizer_retries_once_on_bad_json(monkeypatch):
    calls = _script(monkeypatch, ["Sure! Here is the report: not json", json.dumps(GOOD)])
    out = syn.synthesize_node(_state())
    assert len(calls) == 2 and "valid JSON" in calls[1]["prompt"]
    assert out["report_sections"] is not None


def test_synthesizer_falls_back_to_markdown(monkeypatch):
    md = f"## Verdict\nGrowing [{CITE_A}] [{CITE_B}]."
    calls = _script(monkeypatch, ["nope", "still nope", md])
    out = syn.synthesize_node(_state())
    assert len(calls) == 3 and calls[2]["run_name"] == "synthesizer.report_markdown"
    assert out["report_sections"] is None
    assert out["report"] == md
    assert any("structured brief could not be generated" in u for u in out["uncertainties"])


def test_synthesizer_llm_failure_falls_back_then_errors(monkeypatch):
    _script(monkeypatch, [RuntimeError("groq down"), f"## Verdict\nOk [{CITE_A}]."])
    assert syn.synthesize_node(_state())["report_sections"] is None

    _script(monkeypatch, [RuntimeError("down"), RuntimeError("still down")])
    with pytest.raises(RuntimeError):
        syn.synthesize_node(_state())


def test_synthesizer_revision_prompt_includes_feedback_and_previous_draft(monkeypatch):
    calls = _script(monkeypatch, [json.dumps(GOOD)])
    prev = normalize_sections(GOOD)
    syn.synthesize_node(_state(revision=1, feedback="More on competitors please",
                               report_sections=prev))
    prompt = calls[0]["prompt"]
    assert "REVISION 1" in prompt and "More on competitors please" in prompt
    assert "PREVIOUS DRAFT" in prompt and "Beta Corp" in prompt


def test_unavailable_specialist_becomes_an_uncertainty(monkeypatch):
    _script(monkeypatch, [json.dumps(GOOD)])
    findings = [*FINDINGS, {"agent": "risk", "claim": "unavailable", "citation": "n/a",
                            "confidence": 0.0, "unavailable": True}]
    out = syn.synthesize_node(_state(findings=findings))
    assert any("risk analysis was unavailable" in u for u in out["uncertainties"])


def test_offline_stub_is_schema_shaped():
    out = syn.synthesize_node(_state())  # conftest forces ATLAS_OFFLINE_LLM=1
    s = out["report_sections"]
    assert s and s["company"] == "Acme" and s["stance"] in {"positive", "neutral", "cautious"}
    assert isinstance(s["executive_summary"], list) and s["executive_summary"]
    assert set(s) >= {"company_overview", "financials", "market_position", "competitors",
                      "recent_developments", "sentiment", "risks", "bull_case", "bear_case",
                      "outlook", "bottom_line", "uncertainties"}
    assert CITE_A in out["report"]
