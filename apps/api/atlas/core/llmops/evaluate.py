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


def _judge_context_precision(query: str, findings: list[dict]) -> float:
    """How on-topic is the retrieved/cited evidence for the question? (0..1)

    Uses the evidence the agents actually cited as the "context" and judges its
    relevance — a live proxy for Ragas context_precision (which needs a golden set).
    LLM-judge when available, token-overlap heuristic offline.
    """
    contexts = [f.get("evidence_text", "") for f in findings if f.get("evidence_text")]
    if not contexts:
        return 0.0
    joined = "\n\n".join(contexts)[:2500]
    if not _llm_active():
        qt = set(_TOKEN.findall(query.lower()))
        ct = set(_TOKEN.findall(joined.lower()))
        return round(len(qt & ct) / len(qt), 3) if qt else 0.0
    from ...llm import get_llm
    from ...observability import langchain_callbacks

    resp = get_llm(temperature=0.0, model=get_settings().summarizer_model).invoke(
        "Rate from 0.0 to 1.0 how RELEVANT and on-topic this retrieved context is for "
        f"answering the question. Reply with only the number.\n\nQuestion: {query}\n\n"
        f"Context:\n{joined}",
        config={"callbacks": langchain_callbacks(), "run_name": "ops.judge_context_precision"},
    )
    text = resp.content if hasattr(resp, "content") else str(resp)
    m = re.search(r"[01](?:\.\d+)?", text)
    return round(min(1.0, float(m.group())), 3) if m else 0.0


def _quality_label(faithfulness: float, relevancy: float, context_precision: float) -> str:
    """A plain-English verdict so a human can read the dashboard at a glance."""
    mean = (faithfulness + relevancy + context_precision) / 3
    if mean >= 0.7:
        return "good"
    if mean >= 0.4:
        return "ok"
    return "poor"


def evaluate_run(query: str, result: dict, *, push: bool = True) -> dict:
    """Return {faithfulness, relevancy, overall, agents} and (optionally) push to Langfuse.

    ``agents`` holds the per-specialist scores (see ``agent_eval``), so a weak run can be
    attributed to a specific agent rather than only the final report.
    """
    report = result.get("report", "")
    findings = result.get("findings", [])
    faithfulness = round(citation_coverage(report, findings), 3)
    relevancy = _judge_relevancy(query, report)
    context_precision = _judge_context_precision(query, findings)
    overall = round(0.5 * faithfulness + 0.5 * relevancy, 3)
    quality = _quality_label(faithfulness, relevancy, context_precision)

    from .agent_eval import evaluate_agents
    from .claim_verify import verify_claims

    # Per-agent scores stay internal (used by the self-improvement loop to find the
    # weakest specialist) — we no longer push them to Langfuse, to keep the Scores
    # panel small and readable. push=False.
    agents = evaluate_agents(findings, query=query, push=False)
    # Claim-level citation verification (Phase 3/4): does each cited claim's evidence
    # actually support it? Deterministic-first, so this runs even offline.
    claims = verify_claims(findings)
    scores = {
        "faithfulness": faithfulness,
        "relevancy": relevancy,
        "overall": overall,
        "citation_coverage": claims["citation_coverage"],
        "citation_correctness": claims["citation_correctness"],
        "claim_support": {
            "supported": claims["supported"],
            "partial": claims["partial"],
            "unsupported": claims["unsupported"],
            "total": claims["total_claims"],
        },
        "agents": agents,
    }

    if push:
        try:
            from ...eval.langfuse_scores import flush, push_item_scores

            # A small, readable set — all 0..1, higher is better — plus a plain-English
            # `quality` verdict (good / ok / poor) so the dashboard is legible at a glance:
            #   faithfulness        — is it grounded in the evidence?
            #   answer_relevancy    — does it answer the question?
            #   context_precision   — was the retrieved evidence on-topic?
            #   citation_coverage   — are the claims cited?
            push_item_scores(
                {
                    "ragas_faithfulness": faithfulness,
                    "ragas_answer_relevancy": relevancy,
                    "ragas_context_precision": context_precision,
                    "citation_coverage": claims["citation_coverage"],
                    "quality": quality,  # categorical: good / ok / poor
                },
                question=query,
                answer=report[:500],
                trace_name="atlas_ops_eval",
            )
            flush()
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("Could not push ops scores to Langfuse: %s", exc)
    return scores
