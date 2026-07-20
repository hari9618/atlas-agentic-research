"""LLM-Ops tests — registry versioning, gate, automatic eval, self-improvement loop (offline)."""

from __future__ import annotations

from atlas.core.llmops.evaluate import evaluate_run
from atlas.core.llmops.gate import run_gate
from atlas.core.llmops.optimizer import optimize
from atlas.core.llmops.registry import PromptRegistry


def test_registry_seed_candidate_and_release(tmp_path):
    reg = PromptRegistry(path=tmp_path / "reg.json")
    assert reg.active_version("synthesizer_system") == 1
    assert reg.effective("synthesizer_system")  # seed text present

    reg.set_candidate("synthesizer_system", "A BETTER PROMPT")
    assert reg.effective("synthesizer_system") == "A BETTER PROMPT"  # canary wins

    v = reg.release_candidate("synthesizer_system", {"overall": 0.9}, notes="test")
    assert v == 2
    assert reg.active_version("synthesizer_system") == 2

    # persisted across reloads
    reg2 = PromptRegistry(path=tmp_path / "reg.json")
    assert reg2.active_version("synthesizer_system") == 2
    assert reg2.effective("synthesizer_system") == "A BETTER PROMPT"


def test_gate_passes_and_fails():
    assert run_gate({"faithfulness": 0.9, "relevancy": 0.8}).passed
    failed = run_gate({"faithfulness": 0.1, "relevancy": 0.8})
    assert not failed.passed and failed.reasons


def test_evaluate_run_scores_a_grounded_report():
    result = {
        "report": "## Verdict\nHelios is strong [Helios 10-K (sec_edgar#0)].",
        "findings": [{"agent": "risk", "claim": "x", "citation": "Helios 10-K (sec_edgar#0)"}],
    }
    s = evaluate_run("Evaluate Helios", result, push=False)
    assert set(s) == {"faithfulness", "relevancy", "overall", "agents"}
    assert 0.0 <= s["overall"] <= 1.0
    assert s["faithfulness"] == 1.0  # the citation appears in the report
    # Per-agent scores are attributed to the specialist that produced the finding.
    assert "risk" in s["agents"]


def test_optimize_loop_runs_offline():
    out = optimize("Evaluate Helios Robotics as a competitor", max_iters=1)
    assert "iterations" in out and len(out["iterations"]) >= 1
    assert isinstance(out["released"], bool)
    # every iteration records its scores + gate decision
    assert all("scores" in it and "passed" in it for it in out["iterations"])
