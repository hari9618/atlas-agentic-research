"""Self-improvement loop — run → eval → gate → (diagnose → rewrite → re-run) → release.

If a run clears the gate on the active prompt, nothing changes. If it fails, the
optimizer diagnoses why, asks the LLM to rewrite the synthesizer's system prompt to
fix it, runs again with that candidate (a canary), and re-evaluates. The improved
prompt is **released as a new version only if it actually scores better and passes** —
otherwise the candidate is discarded. This is the automatic "self-improvement" box.
"""

from __future__ import annotations

import logging
import os

from ...config import get_settings
from .evaluate import evaluate_run
from .gate import run_gate
from .registry import get_registry

log = logging.getLogger("atlas.llmops.optimizer")

_PROMPT_NAME = "synthesizer_system"


def _llm_active() -> bool:
    return get_settings().llm_configured and os.getenv("ATLAS_OFFLINE_LLM") != "1"


def propose_improved_prompt(current: str, diagnosis: str, report: str) -> str:
    """Ask the LLM to rewrite the system prompt to fix the diagnosed weaknesses."""
    if not _llm_active():
        return (
            current
            + " Ground EVERY claim in a bracketed citation, answer the question directly in the "
            "Verdict, and explicitly list what is uncertain."
        ).strip()
    from ...llm import get_llm
    from ...observability import langchain_callbacks

    # The optimizer (a meta-task) runs on the cheaper model. The failing report is
    # included so the rewrite targets what actually went wrong.
    resp = get_llm(temperature=0.3, model=get_settings().summarizer_model).invoke(
        "You improve a system prompt for an analyst that writes cited briefs. The last run "
        f"failed evaluation because: {diagnosis}. Here is the weak output:\n{report[:1500]}\n\n"
        "Rewrite the system prompt to fix this. Keep it one or two sentences. "
        f"Return ONLY the new prompt.\n\nCurrent prompt: {current}",
        config={"callbacks": langchain_callbacks(), "run_name": "ops.optimize_prompt"},
    )
    text = (resp.content if hasattr(resp, "content") else str(resp)).strip().strip('"')
    return text or current


def optimize(query: str, *, max_iters: int = 1) -> dict:
    """Run the self-improvement loop for one query. Returns an ops report."""
    from ..graph import research  # lazy import avoids an import cycle

    reg = get_registry()
    reg.clear_candidate(_PROMPT_NAME)

    result = research(query, thread_id="ops-0")
    scores = evaluate_run(query, result)
    g = run_gate(scores)
    iterations = [{
        "iter": 0, "version": f"v{reg.active_version(_PROMPT_NAME)} (active)",
        "scores": scores, "passed": g.passed, "reasons": g.reasons,
    }]

    if g.passed:
        return {"released": False, "reason": "active prompt already passes the gate",
                "iterations": iterations, "final_scores": scores, "final": result}

    baseline_overall = scores["overall"]
    best_result = result
    released, new_version = False, None

    for i in range(1, max_iters + 1):
        diagnosis = "; ".join(g.reasons) or "low overall score"
        candidate = propose_improved_prompt(reg.effective(_PROMPT_NAME), diagnosis, result.get("report", ""))
        reg.set_candidate(_PROMPT_NAME, candidate)

        result_i = research(query, thread_id=f"ops-{i}")
        scores_i = evaluate_run(query, result_i)
        g_i = run_gate(scores_i)
        iterations.append({
            "iter": i, "version": "candidate", "diagnosis": diagnosis,
            "scores": scores_i, "passed": g_i.passed, "reasons": g_i.reasons,
        })

        if scores_i["overall"] > baseline_overall:
            best_result = result_i
        if g_i.passed and scores_i["overall"] >= baseline_overall:
            new_version = reg.release_candidate(_PROMPT_NAME, scores_i, notes=f"auto-improve: {diagnosis}")
            released = True
            best_result = result_i
            break
        g = g_i  # diagnose the LATEST candidate's failure on the next iteration

    if not released:
        reg.clear_candidate(_PROMPT_NAME)  # discard the canary

    return {
        "released": released,
        "new_version": new_version,
        "active_version": reg.active_version(_PROMPT_NAME),
        "iterations": iterations,
        "final": best_result,
    }
