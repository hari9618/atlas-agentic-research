"""Dependency-free retrieval evaluation.

Measures whether the *right documents* are retrieved — independent of any LLM, so it
runs anywhere (CI included). Reports hit-rate@k, MRR, and context precision over the
golden set. This is the fast gate; the Ragas harness (ragas_eval.py) adds the
generation-quality metrics that flow to Langfuse.

Context precision is the rank-aware definition Ragas uses — the mean of precision@k
over the ranks where a relevant chunk appears — computed over retrieved *chunks*. (An
earlier version divided by distinct *documents* retrieved; with a three-document
corpus and one relevant document per question that capped the score near
0.33-0.5 no matter how good the ranking was.)

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


def average_precision(relevant_flags: list[bool]) -> float:
    """Mean of precision@k at each rank k holding a relevant item (0 if none)."""
    hits, total = 0, 0.0
    for k, rel in enumerate(relevant_flags, start=1):
        if rel:
            hits += 1
            total += hits / k
    return total / hits if hits else 0.0


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
    flags = [c.chunk.doc_id in relevant for c in result.chunks]
    return {
        "hit": hit,
        "rr": rr,
        "precision": average_precision(flags),  # rank-aware, chunk level (Ragas definition)
        "chunk_precision": (sum(flags) / len(flags)) if flags else 0.0,  # plain precision@k
        "grade": result.grade.value,
    }


def run(top_k: int = 5, offline: bool = True) -> dict:
    docs = load_corpus_dir()
    index = ingest_documents(docs, offline=offline)

    # Only cases with labelled supporting docs can be scored for retrieval.
    rows = [evaluate_item(index, item, top_k=top_k) for item in GOLDEN_SET if item.relevant_doc_ids]
    n = len(rows)
    summary = {
        "hit_rate@k": sum(r["hit"] for r in rows) / n,
        "mrr": sum(r["rr"] for r in rows) / n,
        "context_precision": sum(r["precision"] for r in rows) / n,
        "chunk_precision@k": sum(r["chunk_precision"] for r in rows) / n,
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
    print(f"  context_precision  : {s['context_precision']:.2f}   (target >= 0.80, rank-aware)")
    print(f"  chunk precision@{args.top_k:<2}: {s['chunk_precision@k']:.2f}")
    print()


if __name__ == "__main__":
    main()
