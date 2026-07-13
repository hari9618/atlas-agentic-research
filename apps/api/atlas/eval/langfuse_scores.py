"""Push evaluation metrics into Langfuse as scores.

Mirrors the score schema already used on the Langfuse dashboard so Atlas metrics
land under **Scores** alongside everything else:

    ragas_faithfulness        ragas_answer_relevancy      ragas_context_precision
    ragas_hallucination (= 1 - faithfulness)              ragas_alert_count

Each eval item becomes its own trace so the scores attach to something inspectable.
Everything is best-effort: if Langfuse isn't configured the functions no-op and the
eval still prints its table.
"""

from __future__ import annotations

import logging
from typing import Any

from ..config import get_settings

log = logging.getLogger("atlas.eval.langfuse")

# Metrics below these thresholds count toward ragas_alert_count and are flagged.
ALERT_THRESHOLDS = {
    "ragas_faithfulness": 0.90,
    "ragas_answer_relevancy": 0.85,
    "ragas_context_precision": 0.80,
}


def _client() -> Any | None:
    settings = get_settings()
    if not settings.langfuse_configured:
        log.info("Langfuse not configured — skipping score push.")
        return None
    try:
        from langfuse import Langfuse

        return Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("Could not init Langfuse client: %s", exc)
        return None


def derive_scores(metrics: dict[str, float]) -> dict[str, float]:
    """Add the derived scores (hallucination, alert_count) the dashboard expects."""
    out = dict(metrics)
    if "ragas_faithfulness" in metrics:
        out["ragas_hallucination"] = round(1.0 - metrics["ragas_faithfulness"], 4)
    alerts = sum(
        1 for name, thr in ALERT_THRESHOLDS.items()
        if name in metrics and metrics[name] < thr
    )
    out["ragas_alert_count"] = float(alerts)
    return out


def push_item_scores(
    metrics: dict[str, float],
    *,
    question: str,
    answer: str,
    trace_name: str = "atlas_rag_eval",
) -> str | None:
    """Create a trace for one eval item and attach its scores. Returns trace id or None."""
    client = _client()
    if client is None:
        return None
    scores = derive_scores(metrics)
    try:
        trace = client.trace(name=trace_name, input=question, output=answer)
        for name, value in scores.items():
            trace.score(name=name, value=float(value))
        return getattr(trace, "id", None)
    except Exception as exc:  # pragma: no cover - SDK version drift
        # Fall back to the flat score API (older/newer SDKs).
        try:
            for name, value in scores.items():
                client.score(name=name, value=float(value))
            return None
        except Exception:
            log.warning("Failed to push scores to Langfuse: %s", exc)
            return None


def flush() -> None:
    client = _client()
    if client is not None:
        try:
            client.flush()
        except Exception:  # pragma: no cover
            pass
