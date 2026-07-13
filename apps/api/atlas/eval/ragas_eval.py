"""Ragas evaluation, with scores pushed to Langfuse.

Pipeline per golden item:
    retrieve (CRAG) → generate a grounded answer (Groq) → score with Ragas
    → push ragas_* scores to Langfuse (faithfulness, answer_relevancy,
      context_precision, + derived hallucination & alert_count).

Ragas is configured to use **Groq + local embeddings** (never OpenAI). If the
`ragas` package isn't installed, we fall back to an LLM-as-judge that produces the
same metric names, so Langfuse always gets the ragas_* score schema. Method is
recorded in each trace's metadata so you can tell them apart.

    pip install -e ".[eval]"          # to get the real Ragas path
    python -m atlas.eval.ragas_eval   # requires GROQ_API_KEY
"""

from __future__ import annotations

import argparse
import json
import logging

from ..config import get_settings
from ..core.rag.crag import corrective_retrieve
from ..core.rag.ingest import ingest_documents
from ..core.rag.loaders import load_corpus_dir
from .golden import GOLDEN_SET
from .langfuse_scores import ALERT_THRESHOLDS, flush, push_item_scores

log = logging.getLogger("atlas.eval.ragas")

TARGETS = {
    "ragas_faithfulness": 0.90,
    "ragas_answer_relevancy": 0.85,
    "ragas_context_precision": 0.80,
}


# ---------- generation (grounded answer) ----------
def generate_answer(question: str, contexts: list[str]) -> str:
    from ..llm import get_llm
    from ..observability import langchain_callbacks

    context_block = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(contexts))
    prompt = (
        "Answer the question using ONLY the context below. Be concise and factual. "
        "If the context is insufficient, say so.\n\n"
        f"Context:\n{context_block}\n\nQuestion: {question}\nAnswer:"
    )
    llm = get_llm(temperature=0.0)
    resp = llm.invoke(prompt, config={"callbacks": langchain_callbacks()})
    return (resp.content if hasattr(resp, "content") else str(resp)).strip()


# ---------- metric computation ----------
def _ragas_metrics(samples: list[dict]) -> list[dict[str, float]] | None:
    """Real Ragas path (Groq + local embeddings). Returns per-sample metrics or None."""
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import answer_relevancy, context_precision, faithfulness
    except Exception as exc:
        log.info("Ragas not available (%s) — using LLM-judge fallback.", exc)
        return None

    from langchain_community.embeddings import HuggingFaceEmbeddings

    from ..llm import get_llm

    ragas_llm = LangchainLLMWrapper(get_llm(temperature=0.0))
    ragas_emb = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(model_name=get_settings().embedding_model)
    )
    ds = Dataset.from_list(
        [
            {
                "question": s["question"],
                "answer": s["answer"],
                "contexts": s["contexts"],
                "ground_truth": s["ground_truth"],
            }
            for s in samples
        ]
    )
    metrics = [faithfulness, answer_relevancy, context_precision]
    for m in metrics:
        if hasattr(m, "llm"):
            m.llm = ragas_llm
        if hasattr(m, "embeddings"):
            m.embeddings = ragas_emb
    result = evaluate(ds, metrics=metrics, llm=ragas_llm, embeddings=ragas_emb)
    df = result.to_pandas()
    out = []
    for _, row in df.iterrows():
        out.append(
            {
                "ragas_faithfulness": float(row.get("faithfulness", 0.0) or 0.0),
                "ragas_answer_relevancy": float(row.get("answer_relevancy", 0.0) or 0.0),
                "ragas_context_precision": float(row.get("context_precision", 0.0) or 0.0),
            }
        )
    return out


def _judge_metrics(sample: dict) -> dict[str, float]:
    """LLM-as-judge fallback producing the same metric names as Ragas."""
    from ..llm import get_llm
    from ..observability import langchain_callbacks

    context_block = "\n\n".join(sample["contexts"])
    prompt = (
        "You are a strict RAG evaluator. Given a question, the retrieved context, a "
        "generated answer, and the ground truth, rate each metric from 0.0 to 1.0.\n"
        "- faithfulness: is every claim in the answer supported by the context?\n"
        "- answer_relevancy: does the answer address the question?\n"
        "- context_precision: is the retrieved context on-topic for the question?\n"
        'Return ONLY JSON: {"faithfulness":x,"answer_relevancy":x,"context_precision":x}\n\n'
        f"Question: {sample['question']}\nContext:\n{context_block}\n"
        f"Answer: {sample['answer']}\nGround truth: {sample['ground_truth']}\nJSON:"
    )
    llm = get_llm(temperature=0.0)
    resp = llm.invoke(prompt, config={"callbacks": langchain_callbacks()})
    text = resp.content if hasattr(resp, "content") else str(resp)
    try:
        start, end = text.index("{"), text.rindex("}") + 1
        data = json.loads(text[start:end])
    except Exception:
        data = {}
    return {
        "ragas_faithfulness": float(data.get("faithfulness", 0.0)),
        "ragas_answer_relevancy": float(data.get("answer_relevancy", 0.0)),
        "ragas_context_precision": float(data.get("context_precision", 0.0)),
    }


# ---------- driver ----------
def run(offline_embed: bool = False) -> dict:
    if not get_settings().llm_configured:
        raise RuntimeError("GROQ_API_KEY is required for the Ragas eval (answer generation).")

    docs = load_corpus_dir()
    index = ingest_documents(docs, offline=offline_embed)

    samples: list[dict] = []
    for item in GOLDEN_SET:
        res = corrective_retrieve(index, item.question, top_k=4)
        contexts = [c.text for c in res.chunks]
        answer = generate_answer(item.question, contexts)
        samples.append(
            {
                "question": item.question,
                "answer": answer,
                "contexts": contexts,
                "ground_truth": item.answer,
            }
        )

    per_item = _ragas_metrics(samples)
    method = "ragas"
    if per_item is None:
        per_item = [_judge_metrics(s) for s in samples]
        method = "llm_judge"

    # push to Langfuse + aggregate
    agg: dict[str, list[float]] = {k: [] for k in TARGETS}
    for sample, metrics in zip(samples, per_item):
        push_item_scores(
            metrics,
            question=sample["question"],
            answer=sample["answer"],
            trace_name=f"atlas_rag_eval[{method}]",
        )
        for k in TARGETS:
            agg[k].append(metrics.get(k, 0.0))
    flush()

    summary = {k: (sum(v) / len(v) if v else 0.0) for k, v in agg.items()}
    return {"method": method, "summary": summary, "per_item": per_item}


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser(description="Ragas eval → Langfuse scores.")
    parser.add_argument("--offline-embed", action="store_true", help="hashing embedder")
    args = parser.parse_args()

    out = run(offline_embed=args.offline_embed)
    s = out["summary"]
    print(f"\n=== Atlas Ragas eval (method: {out['method']}) ===")
    for name, target in TARGETS.items():
        val = s[name]
        flag = "OK " if val >= target else "LOW"
        print(f"  {name:24}: {val:.3f}  (target >= {target:.2f})  [{flag}]")
    alerts = sum(1 for n, t in ALERT_THRESHOLDS.items() if s[n] < t)
    print(f"  ragas_hallucination     : {1 - s['ragas_faithfulness']:.3f}  (lower is better)")
    print(f"  ragas_alert_count       : {alerts}")
    print("\n  -> scores pushed to Langfuse under the ragas_* schema (if configured).\n")


if __name__ == "__main__":
    main()
