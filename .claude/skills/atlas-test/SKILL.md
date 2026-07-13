---
name: atlas-test
description: >
  How to test Atlas the Atlas way — offline (ATLAS_OFFLINE_EMBED=1), contract-focused,
  across unit/integration/API/eval layers, with coverage and an adversarial edge-case
  sweep. Includes the concrete commands and a coverage map of what each module needs.
  Use when writing tests or running a full quality pass. Primarily for the tester subagent.
---

# Skill: Testing Atlas

## Run commands
```bash
cd apps/api
ruff check apps/api                                   # lint
ATLAS_OFFLINE_EMBED=1 python -m pytest -q             # all tests, offline
ATLAS_OFFLINE_EMBED=1 python -m pytest --cov=atlas --cov-report=term-missing
```
Everything must pass with **no network and no API keys**. Tests that need a real
model or Groq key are skipped (`pytest.mark.skipif`), never left to flake.

## Test the contracts (what to assert, by module)
| Module | Contract to assert |
|---|---|
| `config` | defaults load; `*_configured` flags reflect env; graceful when keys absent |
| `rag.bm25` | tokenization; relevant doc ranks first; serialization round-trips |
| `rag.chunking` | deterministic ids; overlap; empty input → no chunks |
| `rag.fusion` | RRF combines rankings; weights bias correctly; empty lists safe |
| `rag.embeddings` | offline hashing embedder is deterministic, L2-normalised, right dim |
| `rag.index` | idempotent add (no dup); retrieve returns provenance-carrying chunks |
| `rag.crag` | grade enum returned; weak evidence triggers a rewrite/corrective pass |
| `eval.retrieval_eval` | hit_rate/MRR/precision computed over the golden set |
| `routers/health` | `/health` 200; `/health/ready` reports llm/langfuse/qdrant |
| `main` | app boots; root identifies the service; CORS configured |

## Adversarial edge cases (add these)
- empty corpus → retrieve returns `[]`, no crash.
- empty / whitespace query → no crash, sensible empty/low result.
- query with zero lexical+semantic overlap → graceful (CRAG INCORRECT path).
- `get_llm()` with no key → raises `RuntimeError` (assert it does).
- duplicate ingest → chunk count unchanged (idempotency).
- non-ASCII / unicode document text → ingest + retrieve without encoding errors.
- very long document → chunker produces multiple overlapping chunks.

## Bar for "done"
- 100% of tests green offline; lint clean.
- Coverage reported; weakest modules named with line gaps.
- A verdict table: layer → pass/fail → coverage → top remaining risks
  (ranked by likelihood × impact). Be honest about what is NOT covered.
