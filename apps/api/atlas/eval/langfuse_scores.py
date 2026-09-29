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

import contextlib
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
        with contextlib.suppress(Exception):  # pragma: no cover
            client.flush()
