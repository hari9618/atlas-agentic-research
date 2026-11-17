"""Run scores must be readable by a non-specialist: named with their range, explained
in words, and banded Good / OK / Weak the same way everywhere."""

from __future__ import annotations

import pytest

from atlas.core.llmops.evaluate import _heuristic_recall, evaluate_run
from atlas.core.llmops.metrics import METRICS, describe, explain, rating


@pytest.mark.parametrize("value,expected", [
    (1.0, "Good"), (0.7, "Good"), (0.69, "OK"), (0.4, "OK"), (0.39, "Weak"), (0.0, "Weak"),
    (None, "No data"),
])
def test_bands_are_the_same_for_every_score(value, expected):
    assert rating(value) == expected


def test_explanation_says_out_of_one_and_what_good_is():
    text = explain("context_precision", 0.48)
    assert text.startswith("0.48 out of 1 · OK.")
    assert "48% of the evidence" in text and "Good is 0.70 or more" in text


def test_exactly_the_seven_readable_scores():
    assert [m.name for m in METRICS] == [
        "Answer relevancy", "Faithfulness", "Context precision", "Context recall",
        "Citation accuracy", "Citation coverage", "Overall"]
    assert {"relevancy", "context_recall", "context_precision", "faithfulness"} <= {
        m.key for m in METRICS}


def test_panel_rows_cover_every_score_even_without_data():
    rows = describe({"relevancy": 0.92})
    assert [r["key"] for r in rows] == [m.key for m in METRICS]
    assert rows[0]["rating"] == "Good" and rows[0]["name"] == "Answer relevancy"
    assert all(r["rating"] == "No data" for r in rows[1:])


def test_context_recall_heuristic_counts_question_terms_found():
    assert _heuristic_recall("gong pricing reps", ["Gong charges per seat for reps"]) == 0.667
    assert _heuristic_recall("gong pricing", []) == 0.0


def test_run_scores_include_context_recall_and_push_readable_names(monkeypatch):
    sent = {}

    def fake_push(values, **kw):
        sent.update(values=values, comments=kw.get("comments"))

    import atlas.eval.langfuse_scores as lf

    monkeypatch.setattr(lf, "push_item_scores", fake_push)
    monkeypatch.setattr(lf, "flush", lambda: None)
    findings = [{"agent": "risk", "claim": "Gong has transcription complaints",
                 "citation": "[Reviews (reviews#1)]",
                 "evidence_text": "Users report Gong transcription errors and pricing opacity."}]
    scores = evaluate_run("Gong pricing and complaints",
                          {"report": "Gong has transcription complaints [Reviews (reviews#1)].",
                           "findings": findings}, push=True)
    assert 0.0 <= scores["context_recall"] <= 1.0
    assert list(sent["values"]) == [m.name for m in METRICS]  # nothing else is sent
    assert sent["comments"]["Context recall"].split(" · ")[0].endswith("out of 1")
