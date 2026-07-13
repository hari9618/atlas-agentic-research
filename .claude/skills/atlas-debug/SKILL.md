---
name: atlas-debug
description: >
  Systematic debugging procedure for the Atlas codebase — reproduce with offline
  flags, isolate via probes, check the Atlas-specific failure modes (env/version
  drift, config, paths, offline model loads, Windows console), fix the root cause,
  verify with the suite, and add a regression guard. Use when diagnosing any Atlas
  error, failing test, hang, or wrong output. Primarily for the debugger subagent.
---

# Skill: Debugging Atlas

## 0. Reproduce deterministically
```bash
cd apps/api
ATLAS_OFFLINE_EMBED=1 python -m pytest -q            # full suite
ATLAS_OFFLINE_EMBED=1 python -m pytest path::test -x # one test, stop on first fail
ATLAS_OFFLINE_EMBED=1 python -c "from atlas.core.rag import build_index; ..."  # probe
```
Always capture the **exact command** and the **full traceback**.

## 1. Triage by category (cheapest checks first)

**Dependency / version drift** (very common here):
```bash
python - <<'PY'
import importlib.metadata as md
for p in ["httpx","groq","langchain","langchain-core","langchain-groq",
          "langchain-community","langchain-huggingface","langgraph"]:
    try: print(p, md.version(p))
    except Exception: print(p, "(absent)")
PY
```
- `ChatGroq ... 'proxies'` → groq vs httpx mismatch → keep `httpx>=0.27,<0.28`.
- `ImportError EnsembleRetriever` → LangChain v1 moved it; Atlas pins **v0.3**
  (`EnsembleRetriever` in `langchain.retrievers`, `BM25Retriever` in
  `langchain_community.retrievers`, `CrossEncoderReranker` in
  `langchain.retrievers.document_compressors`).

**Config / integration** (expected graceful, not bugs):
- no `GROQ_API_KEY` → `get_llm()` raises by design; tests must not call it.
- Qdrant down → falls back to `InMemoryVectorStore` (log line, not error).
- Langfuse keys absent → handler is `None`; runs continue.

**Paths**: corpus/cache resolve through `atlas.paths` (repo-root anchored). A
"file not found" usually means cwd assumptions — use the helpers, not `"data/..."`.

**Offline**: bge embedder / reranker download on first use. Without network they must
degrade (hashing embedder / fused order). A hang here = a missing offline guard.

**Windows**: `UnicodeEncodeError ... charmap` → replace non-ASCII (≥, →) in `print`.

## 2. Isolate → hypothesize → instrument
Shrink to the smallest failing call. State one hypothesis. Confirm with a `python -c`
probe, a focused log, or an `importlib.import_module` path check — before editing.

## 3. Fix the cause, not the symptom
Minimal change; honor conventions (config via `get_settings()`, type hints,
graceful degradation). Don't loosen a guardrail/assertion to make red go green.

## 4. Verify + prevent
Re-run the repro and the full suite. Add a test that would have caught it. Report:
root cause (one line), fix, verification output, regression guard added.
