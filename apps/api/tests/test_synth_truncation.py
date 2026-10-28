"""A synthesizer reply cut off by the token limit must not throw the report away.

Found live: a rich Reliance Industries run hit max_tokens mid-"bottom_line", both
attempts failed to parse, and the run fell back to the plain-markdown report with no
structured sections at all.
"""

from __future__ import annotations

import json

from atlas.core.agents import synthesizer as S
from atlas.core.agents.base import salvage_json_object

FULL = {
    "company": "Acme", "headline": "Acme is growing fast.", "stance": "neutral",
    "confidence": 0.7, "bottom_line": "Worth watching [news#0].",
    "executive_summary": ["Revenue grew 20% [sec_edgar#0]."],
    "risks": [{"title": "Debt", "severity": "medium", "detail": "Rising leverage [news#1]."}],
}


def _cut(obj: dict, marker: str) -> str:
    text = json.dumps(obj)
    return text[: text.index(marker) + len(marker)]  # truncated mid-value


def test_salvage_keeps_every_complete_field():
    truncated = _cut(FULL, '"detail": "Rising lev')
    out = salvage_json_object("Here you go:\n" + truncated)
    assert out["headline"] == "Acme is growing fast." and out["bottom_line"].startswith("Worth")
    assert out["executive_summary"] == ["Revenue grew 20% [sec_edgar#0]."]
    assert "risks" not in out  # the field that was cut off is dropped, not half-kept


def test_salvage_handles_braces_and_quotes_inside_strings():
    obj = {"headline": 'He said "growth {fast}, [steady]", ok', "stance": "positive",
           "bottom_line": "x"}
    assert salvage_json_object(_cut(obj, '"bottom_line": "')) == {
        "headline": obj["headline"], "stance": "positive"}


def test_salvage_returns_none_when_nothing_is_complete():
    assert salvage_json_object('{"headline": "cut off before any comma') is None
    assert salvage_json_object("no json here") is None


def test_salvage_returns_a_complete_object_unchanged():
    assert salvage_json_object(json.dumps(FULL)) == FULL


def test_synthesizer_uses_salvaged_sections_without_a_second_call(monkeypatch):
    calls = []
    truncated = _cut(FULL, '"detail": "Rising lev')

    def fake_chat(prompt, **kw):
        calls.append(prompt)
        return truncated

    monkeypatch.setattr(S, "chat", fake_chat)
    state = {"query": "Is Acme a good investment?", "target": "Acme", "findings": [],
             "debate": []}
    sections = S._structured_sections(state)
    assert sections and sections["headline"] == "Acme is growing fast."
    assert sections["bottom_line"].startswith("Worth watching")
    assert len(calls) == 1  # salvaged — no wasted retry


def test_retry_asks_for_a_shorter_reply_when_nothing_is_salvageable(monkeypatch):
    calls = []
    replies = iter(['{"headline": "cut', json.dumps(FULL)])

    def fake_chat(prompt, **kw):
        calls.append(prompt)
        return next(replies)

    monkeypatch.setattr(S, "chat", fake_chat)
    sections = S._structured_sections({"query": "q?", "target": "Acme", "findings": [],
                                       "debate": []})
    assert sections and len(calls) == 2
    assert "keep it SHORT" in calls[1]


def test_schema_puts_the_verdict_and_bottom_line_first():
    # If a reply is ever cut off, it should lose the tail, never the verdict.
    order = [k for k in ("headline", "stance", "confidence", "bottom_line",
                         "executive_summary", "uncertainties") if k in S._SCHEMA]
    positions = [S._SCHEMA.index(f'"{k}"') for k in order]
    assert positions == sorted(positions)
    assert S._SCHEMA.index('"bottom_line"') < S._SCHEMA.index('"executive_summary"')
