"""Automatic per-run evaluation — the "Eval / Observe" box.

Scores every research run without a human, on the brief the reader actually sees:

* **faithfulness**      — share of the brief's statements supported by the retrieved
                          evidence (report_verify; Ragas' definition of faithfulness).
* **citation_accuracy** — share of cited statements supported by their OWN citation.
* **citation_coverage** — share of statements that carry a citation.
* **relevancy**         — does the brief answer the question? (LLM judge with a rubric)
* **context_precision** — share of the cited evidence that is on-topic for the question
                          (one batched relevance call over the distinct evidence chunks).
* **overall**           — mean of faithfulness, relevancy and context precision; the
                          optimizer compares candidates on it.

Earlier versions scored "faithfulness" as the share of findings' citations that
appeared somewhere in the report. That is bookkeeping, not grounding: it read 1.0 on
real reports regardless of whether their statements were true to the evidence. And
one judge call per ambiguous claim could exhaust the free-tier rate limit; the whole
evaluation is now at most three small-model calls.

Each judge degrades to a deterministic heuristic if the LLM is unavailable, so a
transient error lowers precision, never zeroes a score.
"""

from __future__ import annotations

import json
import logging
import os
import re

from ...config import get_settings
from ..resilience import LLM_ATTEMPTS, retry_call
from .report_verify import evidence_map, verify_report

log = logging.getLogger("atlas.llmops.evaluate")

_TOKEN = re.compile(r"[a-z0-9]+")
_SCORE = re.compile(r"(?<![\d.])(1(?:\.0+)?|0?\.\d+|0)(?![\d.])")
_STOP = frozenset({"the", "a", "an", "of", "to", "in", "and", "or", "is", "are", "for", "on",
                   "with", "as", "at", "by", "it", "this", "that", "should", "i", "about",
                   "what", "how", "does", "do", "vs", "my"})
_MAX_CONTEXTS = 12


def _llm_active() -> bool:
    return get_settings().llm_configured and os.getenv("ATLAS_OFFLINE_LLM") != "1"


def _judge(prompt: str, run_name: str) -> str:
    """One small-model judge call, retried on transient errors."""
    from ...llm import get_llm
    from ...observability import langchain_callbacks

    llm = get_llm(temperature=0.0, model=get_settings().summarizer_model)
    resp = retry_call(llm.invoke, prompt, attempts=LLM_ATTEMPTS, label=run_name,
                      config={"callbacks": langchain_callbacks(), "run_name": run_name})
    return (resp.content if hasattr(resp, "content") else str(resp)).strip()


def _query_terms(query: str) -> set[str]:
    return {t for t in _TOKEN.findall(query.lower()) if t not in _STOP and len(t) > 1}


def _heuristic_relevancy(query: str, report: str) -> float:
    qt = _query_terms(query)
    rt = set(_TOKEN.findall(report.lower()))
    return round(len(qt & rt) / len(qt), 3) if qt else 0.0


def parse_score(text: str) -> float | None:
    """First 0..1 number in a judge reply ("0.8", ".75", "1", "Score: 0.6")."""
    m = _SCORE.search(text or "")
    return round(min(1.0, float(m.group(1))), 3) if m else None


def _judge_relevancy(query: str, report: str) -> float:
    if not report:
        return 0.0
    if not _llm_active():
        return _heuristic_relevancy(query, report)
    try:
        reply = _judge(
            "Score how well this brief ANSWERS the user's question.\n"
            "1.0 = answers it directly, with specifics and a clear verdict\n"
            "0.7 = answers it, but partly generic or missing an asked-for aspect\n"
            "0.4 = on the right company/topic but does not really answer the question\n"
            "0.0 = off-topic or about a different company\n"
            "Reply with only the number.\n\n"
            f"Question: {query}\n\nBrief:\n{report[:3000]}",
            "ops.judge_relevancy",
        )
        score = parse_score(reply)
        if score is not None:
            return score
        log.warning("relevancy judge gave no score (%r) — using heuristic", reply[:60])
    except Exception as exc:
        log.warning("relevancy judge failed (%s) — using heuristic", exc)
    return _heuristic_relevancy(query, report)


def _contexts(findings: list[dict]) -> list[str]:
    """The distinct evidence chunks the analysts cited, one per source#n key."""
    return list(evidence_map(findings).values())[:_MAX_CONTEXTS]


def _heuristic_on_topic(query: str, context: str) -> bool:
    qt = _query_terms(query)
    ct = set(_TOKEN.findall(context.lower()))
    return bool(qt) and len(qt & ct) / len(qt) >= 0.5


def _judge_context_precision(query: str, findings: list[dict]) -> float:
    """Share of the cited evidence chunks that are relevant to the question (0..1).

    Ragas' context precision asks, per retrieved chunk, "is this useful for answering
    the question?". Atlas judges every distinct cited chunk in ONE call.
    """
    contexts = _contexts(findings)
    if not contexts:
        return 0.0
    flags: list[bool] | None = None
    if _llm_active():
        blocks = "\n\n".join(f"#{i + 1}: {c[:400]}" for i, c in enumerate(contexts))
        try:
            reply = _judge(
                "For each numbered passage, is it relevant and useful for answering the "
                f"question? Question: {query}\n\nReturn ONLY a JSON array of {len(contexts)} "
                "booleans, in order.\n\n" + blocks,
                "ops.judge_context_precision",
            )
            arr = json.loads(reply[reply.index("["): reply.rindex("]") + 1])
            if isinstance(arr, list) and len(arr) == len(contexts):
                flags = [v is True or str(v).lower() in ("true", "yes", "1") for v in arr]
        except Exception as exc:
            log.warning("context-precision judge failed (%s) — using heuristic", exc)
    if flags is None:
        flags = [_heuristic_on_topic(query, c) for c in contexts]
    return round(sum(flags) / len(flags), 3)


def _quality_label(overall: float, faithfulness: float) -> str:
    """A plain-English verdict so a human can read the dashboard at a glance.

    Faithfulness gates it too: a fluent, relevant brief that is half unsupported must
    not read "good" just because the average looks fine.
    """
    if overall >= 0.7 and faithfulness >= 0.7:
        return "good"
    if overall >= 0.4 and faithfulness >= 0.4:
        return "ok"
    return "poor"


def evaluate_run(query: str, result: dict, *, push: bool = True) -> dict:
    """Score one run. Returns the metrics below and (optionally) pushes them to Langfuse.

    ``agents`` holds per-specialist scores (``agent_eval``) so a weak run can be
    attributed to one analyst; ``report_check`` lists the statements that failed.
    """
    report = result.get("report", "")
    findings = result.get("findings", [])
    use_llm = _llm_active()

    check = verify_report(report, findings, use_llm=use_llm)
    faithfulness = check["faithfulness"]
    relevancy = _judge_relevancy(query, report)
    context_precision = _judge_context_precision(query, findings)
    overall = round((faithfulness + relevancy + context_precision) / 3, 3)
    quality = _quality_label(overall, faithfulness)

    from .agent_eval import evaluate_agents

    # Per-agent scores stay internal (the optimizer uses them to find the weakest
    # specialist); they are not pushed, to keep the Langfuse Scores panel readable.
    agents = evaluate_agents(findings, query=query, push=False)
    scores = {
        "faithfulness": faithfulness,
        "relevancy": relevancy,
        "context_precision": context_precision,
        "citation_accuracy": check["citation_accuracy"],
        "citation_coverage": check["citation_coverage"],
        "overall": overall,
        "quality": quality,
        "report_check": {
            "statements": check["total_statements"],
            "cited": check["cited_statements"],
            "unsupported": check["unsupported"],
            "miscited": check["miscited"],
        },
        "agents": agents,
    }

    if push:
        try:
            from ...eval.langfuse_scores import flush, push_item_scores

            # A small, readable set — all 0..1, higher is better — plus a plain-English
            # `quality` verdict. The names keep the Ragas metric names the dashboard
            # already uses; the values are Atlas's own Ragas-style computations.
            push_item_scores(
                {
                    "ragas_faithfulness": faithfulness,
                    "ragas_answer_relevancy": relevancy,
                    "ragas_context_precision": context_precision,
                    "citation_accuracy": check["citation_accuracy"],
                    "citation_coverage": check["citation_coverage"],
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
