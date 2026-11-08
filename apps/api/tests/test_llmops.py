"""LLM-Ops tests — the release gate and the automatic per-run evaluation (offline).

The learning loop itself is covered in test_learning_loop.py.
"""

from __future__ import annotations

from atlas.core.llmops.evaluate import evaluate_run
from atlas.core.llmops.gate import run_gate


def test_gate_passes_and_fails():
    good = {"faithfulness": 0.9, "relevancy": 0.8, "citation_accuracy": 0.8}
    assert run_gate(good).passed
    failed = run_gate({**good, "faithfulness": 0.1})
    assert not failed.passed and failed.reasons == ["faithfulness 0.10 < 0.70"]
    # A metric that was never computed fails rather than silently passing.
    assert not run_gate({"faithfulness": 0.9, "relevancy": 0.8}).passed


_EVIDENCE = ("Helios Robotics reported total revenue of $4.2 billion in fiscal 2025, up 28% "
             "from $3.28 billion. The three largest customers were 39% of revenue.")


def test_evaluate_run_scores_the_brief_against_its_evidence():
    result = {
        "report": (
            "## Executive Summary\n"
            "- Helios revenue reached $4.2 billion in fiscal 2025, up 28% "
            "[Helios 10-K (sec_edgar#0)].\n"
            "- Helios plans to triple revenue to $12.6 billion by 2027 "
            "[Helios 10-K (sec_edgar#0)].\n"
        ),
        "findings": [{"agent": "risk", "claim": "Revenue was $4.2 billion, up 28%.",
                      "citation": "Helios 10-K (sec_edgar#0)", "evidence_text": _EVIDENCE}],
    }
    s = evaluate_run("Evaluate Helios Robotics revenue", result, push=False)
    assert {"faithfulness", "relevancy", "context_precision", "citation_accuracy",
            "citation_coverage", "overall", "quality", "report_check", "agents"} <= set(s)
    # One true statement, one invented figure: faithfulness is 0.5, not the old 1.0
    # that only checked the citation label appeared somewhere in the report.
    assert s["faithfulness"] == 0.5
    assert s["citation_accuracy"] == 0.5 and s["citation_coverage"] == 1.0
    assert s["report_check"]["unsupported"] == [
        "Helios plans to triple revenue to $12.6 billion by 2027"]
    assert 0.0 <= s["overall"] <= 1.0 and s["quality"] in {"good", "ok", "poor"}
    assert "risk" in s["agents"]  # attributed to the specialist
