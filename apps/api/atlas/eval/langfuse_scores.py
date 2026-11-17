"""Push evaluation metrics into Langfuse as scores (Langfuse SDK v5).

Each eval item becomes its own small trace (one "evaluator" observation holding the
question and answer) and its scores attach to that trace, so every score links to
something inspectable. Run scores use the plain names in ``core/llmops/metrics.py``
("Faithfulness", "Context recall", ...) with a one-line comment explaining the value.

Everything is best-effort: if Langfuse isn't configured the functions no-op and the
eval still prints its table.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any

log = logging.getLogger("atlas.eval.langfuse")

# Metrics below these thresholds count toward ragas_alert_count and are flagged.
ALERT_THRESHOLDS = {
    "ragas_faithfulness": 0.90,
    "ragas_answer_relevancy": 0.85,
    "ragas_context_precision": 0.80,
}


def _client() -> Any | None:
    """The shared Langfuse client (``atlas.observability``), or None."""
    from ..observability import get_langfuse_client

    client = get_langfuse_client()
    if client is None:
        log.info("Langfuse not configured — skipping score push.")
    return client


def derive_scores(metrics: dict[str, float]) -> dict[str, float]:
    """Return the metrics as-is.

    Previously this also emitted ``ragas_hallucination`` (= 1 - faithfulness) and
    ``ragas_alert_count`` — but those cluttered the dashboard with numbers that
    duplicate faithfulness or read as cryptic. We push only the metrics we're given,
    so the Scores panel stays small and human-readable.
    """
    return dict(metrics)


def push_item_scores(
    metrics: dict[str, float],
    *,
    question: str,
    answer: str,
    trace_name: str = "atlas_rag_eval",
    comments: dict[str, str] | None = None,
) -> str | None:
    """Create a trace for one eval item and attach its scores. Returns trace id or None.

    ``comments`` (score name → text) shows next to each score in Langfuse, so a reader
    sees what a value means without knowing the metric.
    """
    client = _client()
    if client is None:
        return None
    scores = derive_scores(metrics)
    notes = comments or {}
    try:
        trace_id = client.create_trace_id()
        # A one-observation trace carries the question/answer the scores refer to.
        with client.start_as_current_observation(
                trace_context={"trace_id": trace_id}, name=trace_name, as_type="evaluator",
                input=question, output=answer):
            pass
        for name, value in scores.items():
            categorical = isinstance(value, str)  # e.g. a good/ok/poor label
            client.create_score(
                trace_id=trace_id, name=name,
                value=value if categorical else float(value),
                data_type="CATEGORICAL" if categorical else "NUMERIC",
                comment=notes.get(name))
        return trace_id
    except Exception as exc:  # never let observability break an evaluation
        log.warning("Failed to push scores to Langfuse: %s", exc)
        return None


def flush() -> None:
    client = _client()
    if client is not None:
        with contextlib.suppress(Exception):  # pragma: no cover
            client.flush()
