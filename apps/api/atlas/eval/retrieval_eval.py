"""Dependency-free retrieval evaluation.

Measures whether the *right documents* are retrieved — independent of any LLM, so it
runs anywhere (CI included). Reports hit-rate@k, MRR, and context precision over the
golden set. This is the fast gate; the Ragas harness (ragas_eval.py) adds the
generation-quality metrics that flow to Langfuse.

    python -m atlas.eval.retrieval_eval            # uses cached index, offline embedder
"""

from __future__ import annotations

import argparse
import logging

from ..core.rag.crag import corrective_retrieve
from ..core.rag.index import HybridIndex
from ..core.rag.ingest import ingest_documents
from ..core.rag.loaders import load_corpus_dir
from .golden import GOLDEN_SET, GoldenItem

log = logging.getLogger("atlas.eval.retrieval")


def _doc_ids(chunks) -> list[str]:
    """Doc ids in retrieved order, de-duplicated (first occurrence wins)."""
    seen: list[str] = []
    for c in chunks:
        if c.chunk.doc_id not in seen:
            seen.append(c.chunk.doc_id)
    return seen


def evaluate_item(index: HybridIndex, item: GoldenItem, top_k: int = 5) -> dict:
    result = corrective_retrieve(index, item.question, top_k=top_k)
    retrieved = _doc_ids(result.chunks)
    relevant = set(item.relevant_doc_ids)

    hit = any(d in relevant for d in retrieved)
    # reciprocal rank of the first relevant doc
    rr = 0.0
    for rank, d in enumerate(retrieved, start=1):
        if d in relevant:
            rr = 1.0 / rank
            break
    # context precision: fraction of retrieved docs that are relevant
    precision = (sum(1 for d in retrieved if d in relevant) / len(retrieved)) if retrieved else 0.0
    return {"hit": hit, "rr": rr, "precision": precision, "grade": result.grade.value}


def run(top_k: int = 5, offline: bool = True) -> dict:
    docs = load_corpus_dir()
    index = ingest_documents(docs, offline=offline)

    rows = [evaluate_item(index, item, top_k=top_k) for item in GOLDEN_SET]
    n = len(rows)
    summary = {
        "hit_rate@k": sum(r["hit"] for r in rows) / n,
        "mrr": sum(r["rr"] for r in rows) / n,
        "context_precision": sum(r["precision"] for r in rows) / n,
        "n": n,
    }
    return {"summary": summary, "rows": rows}


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser(description="Retrieval-quality eval over the golden set.")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--online-embed", action="store_true", help="use bge (downloads model)")
    args = parser.parse_args()

    out = run(top_k=args.top_k, offline=not args.online_embed)
    s = out["summary"]
    print("\n=== Atlas retrieval eval ===")
    print(f"  items              : {s['n']}")
    print(f"  hit_rate@{args.top_k:<9}: {s['hit_rate@k']:.2f}   (target >= 0.90)")
    print(f"  MRR                : {s['mrr']:.2f}")
    print(f"  context_precision  : {s['context_precision']:.2f}   (target >= 0.80)")
    print()


if __name__ == "__main__":
    main()
