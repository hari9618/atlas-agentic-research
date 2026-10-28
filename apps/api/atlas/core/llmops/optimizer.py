"""Self-improvement loop — run → eval → gate → (diagnose → rewrite → re-run) → release.

If a run clears the gate on the active prompt, nothing changes. If it fails, the
optimizer diagnoses why, asks the LLM to rewrite the synthesizer's system prompt to
fix it, runs again with that candidate, and re-evaluates. The candidate is **released
as a new version only if it passes the gate AND beats the baseline by a real margin**
— otherwise it is discarded.

Safety properties (each one was a real bug):

* The candidate is trialled through the run config (``prompt_override``), never the
  shared registry slot — so user runs in flight keep the active prompt.
* Trial runs are scored once, here (``score=False`` on the graph run), not twice.
* Every run gets a fresh thread id, so a checkpointer never resumes an old ops run.
* A single LLM run is noisy; ``MIN_GAIN`` keeps a lucky re-roll from being released.
* The candidate slot is always cleared, even if a run raises.
"""

from __future__ import annotations

import logging
import os
import uuid

from ...config import get_settings
from .evaluate import evaluate_run
from .gate import run_gate
from .registry import get_registry

log = logging.getLogger("atlas.llmops.optimizer")

_PROMPT_NAME = "synthesizer_system"
# A candidate must beat the baseline's overall score by at least this much: run-to-run
# variance of one LLM report is a few hundredths, so smaller "gains" are noise.
MIN_GAIN = 0.05
# A system prompt is a short persona + priorities; the detailed rules live in the
# user prompt. A runaway rewrite is rejected rather than shipped.
_MAX_PROMPT_CHARS = 1200


def _llm_active() -> bool:
    return get_settings().llm_configured and os.getenv("ATLAS_OFFLINE_LLM") != "1"


def _thread(tag: str) -> str:
    return f"ops-{tag}-{uuid.uuid4().hex[:8]}"


def _diagnosis(reasons: list[str], scores: dict) -> str:
    """Why the run failed, with the offending sentences, so the rewrite is targeted."""
    parts = list(reasons) or ["low overall score"]
    check = scores.get("report_check") or {}
    if check.get("unsupported"):
        parts.append("statements the evidence does not support: "
                     + " | ".join(s[:160] for s in check["unsupported"][:3]))
    if check.get("miscited"):
        parts.append("statements whose own citation does not back them: "
                     + " | ".join(s[:160] for s in check["miscited"][:3]))
    return "; ".join(parts)


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
        "You improve the SYSTEM prompt of an analyst that writes cited investor briefs as "
        f"JSON. The last run failed evaluation because: {diagnosis}.\n\nWeak output:\n"
        f"{report[:1500]}\n\nRewrite the system prompt to fix exactly these weaknesses. "
        "Keep it to 2-4 sentences. Keep the analyst persona and the rule that every claim "
        "must cite its evidence. Do not mention output formats (the user prompt defines "
        f"them). Return ONLY the new prompt.\n\nCurrent prompt: {current}",
        config={"callbacks": langchain_callbacks(), "run_name": "ops.optimize_prompt"},
    )
    text = (resp.content if hasattr(resp, "content") else str(resp)).strip().strip('"').strip()
    if not text or len(text) > _MAX_PROMPT_CHARS:
        log.warning("optimizer proposal rejected (%d chars)", len(text))
        return current
    return text


def optimize(query: str, *, max_iters: int = 1) -> dict:
    """Run the self-improvement loop for one query. Returns an ops report."""
    from ..graph import research  # lazy import avoids an import cycle

    reg = get_registry()
    reg.clear_candidate(_PROMPT_NAME)
    active = reg.effective(_PROMPT_NAME)

    result = research(query, thread_id=_thread("base"), score=False)
    scores = evaluate_run(query, result)
    g = run_gate(scores)
    iterations = [{
        "iter": 0, "version": f"v{reg.active_version(_PROMPT_NAME)} (active)",
        "scores": scores, "passed": g.passed, "reasons": g.reasons,
    }]

    if g.passed:
        return {"released": False, "reason": "active prompt already passes the gate",
                "iterations": iterations, "final_scores": scores, "final": result,
                "active_version": reg.active_version(_PROMPT_NAME)}

    baseline_overall = scores["overall"]
    best_result, best_overall = result, baseline_overall
    released, new_version = False, None
    current, last_report, last_scores = active, result.get("report", ""), scores

    try:
        for i in range(1, max_iters + 1):
            diagnosis = _diagnosis(g.reasons, last_scores)
            candidate = propose_improved_prompt(current, diagnosis, last_report)
            if candidate.strip() == current.strip():
                iterations.append({"iter": i, "version": "candidate", "diagnosis": diagnosis,
                                   "scores": None, "passed": False,
                                   "skipped": "no usable rewrite proposed"})
                break
            reg.set_candidate(_PROMPT_NAME, candidate)  # visible in /llmops/prompts

            result_i = research(query, thread_id=_thread(str(i)), prompt_override=candidate,
                                score=False)
            scores_i = evaluate_run(query, result_i)
            g_i = run_gate(scores_i)
            gain = round(scores_i["overall"] - baseline_overall, 3)
            iterations.append({
                "iter": i, "version": "candidate", "diagnosis": diagnosis, "prompt": candidate,
                "scores": scores_i, "passed": g_i.passed, "reasons": g_i.reasons, "gain": gain,
            })

            if scores_i["overall"] > best_overall:
                best_result, best_overall = result_i, scores_i["overall"]
            if g_i.passed and gain >= MIN_GAIN:
                release_scores = {k: v for k, v in scores_i.items()
                                  if isinstance(v, (int, float, str))}
                new_version = reg.release_candidate(
                    _PROMPT_NAME, release_scores,
                    notes=f"auto-improve (+{gain:.2f}): {'; '.join(g.reasons)}"[:300],
                )
                released = True
                break
            # Iterate from the latest candidate and diagnose ITS failure next.
            g, current = g_i, candidate
            last_report, last_scores = result_i.get("report", ""), scores_i
    finally:
        if not released:
            reg.clear_candidate(_PROMPT_NAME)  # discard the canary, even on error

    return {
        "released": released,
        "new_version": new_version,
        "active_version": reg.active_version(_PROMPT_NAME),
        "min_gain": MIN_GAIN,
        "iterations": iterations,
        "final": best_result,
    }
