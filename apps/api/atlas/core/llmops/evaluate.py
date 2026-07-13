"""Automatic per-run evaluation — the "Eval / Observe" box.

Scores every research run without a human:
* **faithfulness** — is the report grounded? (reuses the citation-coverage guardrail)
* **relevancy** — does it answer the question? (LLM-as-judge, heuristic offline)
* **overall** — the blended score the gate checks.

Scores are pushed to Langfuse under the same ragas_* schema already on the dashboard.
"""

from __future__ import annotations

import logging
import os
import re

from ...config import get_settings
from ..guardrails import citation_coverage

log = logging.getLogger("atlas.llmops.evaluate")

_TOKEN = re.compile(r"[a-z0-9]+")


def _llm_active() -> bool:
    return get_settings().llm_configured and os.getenv("ATLAS_OFFLINE_LLM") != "1"


def _judge_relevancy(query: str, report: str) -> float:
    if not report:
        return 0.0
    if not _llm_active():
        qt = set(_TOKEN.findall(query.lower()))
        rt = set(_TOKEN.findall(report.lower()))
        return round(len(qt & rt) / len(qt), 3) if qt else 0.0
    from ...llm import get_llm
    from ...observability import langchain_callbacks

    # Ops/eval runs on the cheaper model (keeps load off the 70B rate limit).
    resp = get_llm(temperature=0.0, model=get_settings().summarizer_model).invoke(
        "Rate from 0.0 to 1.0 how well this brief ANSWERS the question. Reply with only the "
        f"number.\n\nQuestion: {query}\n\nBrief:\n{report[:2500]}",
        config={"callbacks": langchain_callbacks(), "run_name": "ops.judge_relevancy"},
    )
    text = resp.content if hasattr(resp, "content") else str(resp)
    m = re.search(r"[01](?:\.\d+)?", text)
    return round(min(1.0, float(m.group())), 3) if m else 0.0


def evaluate_run(query: str, result: dict, *, push: bool = True) -> dict:
    """Return {faithfulness, relevancy, overall} and (optionally) push to Langfuse."""
    report = result.get("report", "")
    findings = result.get("findings", [])
    faithfulness = round(citation_coverage(report, findings), 3)
    relevancy = _judge_relevancy(query, report)
    overall = round(0.5 * faithfulness + 0.5 * relevancy, 3)
    scores = {"faithfulness": faithfulness, "relevancy": relevancy, "overall": overall}

    if push:
        try:
            from ...eval.langfuse_scores import flush, push_item_scores

            push_item_scores(
                {"ragas_faithfulness": faithfulness, "ragas_answer_relevancy": relevancy},
                question=query,
                answer=report[:500],
                trace_name="atlas_ops_eval",
            )
            flush()
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("Could not push ops scores to Langfuse: %s", exc)
    return scores
