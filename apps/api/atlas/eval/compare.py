"""Baseline vs Atlas — does the multi-agent / evidence architecture measurably help?

Runs the same golden questions through both the simple RAG baseline and the full Atlas
graph, scores both with the *same* ``evaluate_run``, and reports side-by-side averages
plus per-metric win counts. The honest question this answers:

    Does Atlas actually improve quality over retrieve-then-synthesize,
    or is the extra machinery just complexity?

Metrics compared (all from the shared evaluator): faithfulness, answer relevancy,
overall, claim-level citation coverage, citation correctness, and latency.

Run it:  python -m atlas.eval.compare [--limit N]
Numbers come from real runs — nothing here fabricates a result.
"""

from __future__ import annotations

import argparse
import logging
import time
from functools import partial

from .baseline import baseline_run
from .golden import ALL_GOLDEN

log = logging.getLogger("atlas.eval.compare")

_METRICS = ["faithfulness", "relevancy", "overall", "citation_coverage", "citation_correctness"]


def _score(query: str, result: dict) -> dict:
    from ..core.llmops.evaluate import evaluate_run

    scores = evaluate_run(query, result, push=False)
    return {m: float(scores.get(m, 0.0)) for m in _METRICS}


def _timed(fn, *args) -> tuple[dict, float]:
    t0 = time.perf_counter()
    out = fn(*args)
    return out, round(time.perf_counter() - t0, 3)


def run_comparison(items=None, *, limit: int | None = None) -> dict:
    """Run baseline and Atlas over the golden items; return rows + aggregate."""
    from ..core.graph import research

    items = list(items if items is not None else ALL_GOLDEN)
    if limit:
        items = items[:limit]

    rows = []
    for it in items:
        b_out, b_lat = _timed(baseline_run, it.question)
        thread_id = f"cmp-{it.id or abs(hash(it.question))}"
        a_out, a_lat = _timed(partial(research, thread_id=thread_id), it.question)
        rows.append({
            "id": it.id,
            "category": it.category,
            "verifiable": it.verifiable,
            "baseline": {**_score(it.question, b_out), "latency": b_lat},
            "atlas": {**_score(it.question, a_out), "latency": a_lat},
        })

    return {"rows": rows, "aggregate": _aggregate(rows), "n": len(rows)}


def _aggregate(rows: list[dict]) -> dict:
    if not rows:
        return {}
    agg = {"baseline": {}, "atlas": {}, "atlas_wins": {}, "n": len(rows)}
    for m in [*_METRICS, "latency"]:
        b = [r["baseline"][m] for r in rows]
        a = [r["atlas"][m] for r in rows]
        agg["baseline"][m] = round(sum(b) / len(b), 3)
        agg["atlas"][m] = round(sum(a) / len(a), 3)
        # For latency lower is better; for quality metrics higher is better.
        better = (lambda x, y: x < y) if m == "latency" else (lambda x, y: x > y)
        agg["atlas_wins"][m] = sum(1 for r in rows if better(r["atlas"][m], r["baseline"][m]))
    return agg


def _format(result: dict) -> str:
    agg = result["aggregate"]
    if not agg:
        return "No results."
    n = agg["n"]
    lines = [
        f"Baseline vs Atlas over {result['n']} golden questions",
        "=" * 58,
        f"{'metric':<22}{'baseline':>10}{'atlas':>10}{'atlas wins':>14}",
    ]
    for m in [*_METRICS, "latency"]:
        wins = f"{agg['atlas_wins'][m]}/{n}"
        lines.append(
            f"{m:<22}{agg['baseline'][m]:>10.3f}{agg['atlas'][m]:>10.3f}{wins:>14}"
        )
    return "\n".join(lines)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s :: %(message)s")
    ap = argparse.ArgumentParser(description="Compare the RAG baseline against Atlas.")
    ap.add_argument("--limit", type=int, default=None, help="only the first N golden items")
    args = ap.parse_args()
    result = run_comparison(limit=args.limit)
    print(_format(result))


if __name__ == "__main__":
    main()
