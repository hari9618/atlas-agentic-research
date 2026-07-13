# Atlas — Autonomous Due-Diligence Desk

Atlas takes a company / startup / market question (e.g. *"Should I worry about Company X
as a competitor?"*) and runs a **team of specialist AI agents** that research in parallel,
**debate each other (bull vs. bear)**, ground every claim in retrieved evidence, and produce
an **investor-grade report** with citations, a confidence score, and an explicit
"what we're NOT sure about" section.

This is a portfolio project meant to demonstrate **senior-grade agentic engineering**:
real multi-agent orchestration, agentic hybrid RAG, MCP tools, four memory layers, full
observability, and a self-improving LLM-Ops loop. **Status: complete (M0–M7), runs end-to-end.**

---

## Architecture (one screen)

```
Next.js war-room UI ──SSE──> FastAPI ──> LangGraph graph  (SQLite-checkpointed state)
   recall(memory) → SUPERVISOR → [Fundamentals · News/Sentiment · Risk · Market] (parallel)
                     → BULL ⇄ BEAR debate → SYNTHESIZER + JUDGE → remember(memory) → cited report + confidence

  Memory layers:
    Working (graph state) · Semantic (hybrid RAG corpus) · Episodic (SQLite + vectors: past runs) ·
    Procedural (agent playbooks/files) · Summarizer agent (cheaper model) distills episodes → semantic facts
  Agentic Hybrid RAG:
    BM25Retriever + bge (EnsembleRetriever/RRF) → CrossEncoderReranker → CRAG self-correct → Qdrant/InMemory
  Tools:  web_search (Tavily) · sec_edgar · stock_data (stooq) · company_news
  LLM Ops (self-improving):
    Langfuse trace + auto/Ragas eval → gate → diagnose → rewrite prompt → re-eval → release (prompt registry)
```

## Stack (locked)

| Layer | Choice |
|---|---|
| Orchestration | **LangGraph** (supervisor + specialist subgraphs, SQLite checkpointer for shared state) |
| LLM | **Groq · Llama 3.3 70B** (`llama-3.3-70b-versatile`) via `langchain-groq` |
| RAG | LangChain hybrid: **BM25Retriever + bge-small (EnsembleRetriever/RRF)** → **CrossEncoderReranker** → **CRAG** loop, **Qdrant**/InMemory |
| Embeddings | `BAAI/bge-small-en-v1.5` (free, local via sentence-transformers) |
| Tools | **MCP** server exposing web_search / sec_edgar / stock_data / company_news |
| Memory | **Episodic** (SQLite + embeddings) · **Procedural** (playbook files) · **Summarizer** agent (cheaper model) |
| Backend | **FastAPI** + SSE streaming |
| Observability | **Langfuse** (trace/eval/cost) + **Ragas** + a self-improving **LLM-Ops** loop (prompt registry) |
| Frontend | **Next.js + Tailwind** (hand-rolled war-room components) |
| Infra | **Docker Compose** (qdrant + langfuse + api + web) |

> Constraints: stay on **free / self-hostable** tiers everywhere (Groq free tier, local embeddings,
> SEC EDGAR + Tavily free tier, self-hosted Langfuse + Qdrant).

## Repo layout

```
apps/
  api/                 # FastAPI backend (Python 3.11+)
    atlas/
      config.py        # pydantic-settings, env-driven, graceful degradation
      llm.py           # shared ChatGroq factory (temperature/model overrides)
      observability.py # Langfuse callback handler (None when unconfigured)
      paths.py         # repo-root-anchored data/cache paths
      routers/         # FastAPI routers: health, research (SSE), llmops
      core/
        graph.py       # LangGraph wiring: recall → supervisor → specialists → debate → synthesize → remember
        state.py       # shared "research scratchpad" state
        guardrails.py  # grounding / citation-coverage guardrail
        agents/        # base, specialists (4), debate (bull/bear/judge), synthesizer
        rag/           # chunking, embeddings, index (LangChain hybrid), crag, ingest, loaders
        memory/        # episodic (SQLite+vectors), procedural (playbooks), summarizer
        llmops/        # registry, evaluate, gate, optimizer (self-improvement loop)
        tools/         # web_search (Tavily), sec, market (stock + news)
      eval/            # golden set, retrieval_eval, ragas_eval, langfuse_scores
    tests/             # offline suite (ATLAS_OFFLINE_LLM / ATLAS_OFFLINE_EMBED)
  web/                 # Next.js war-room frontend (M5)
data/corpus/           # sample corpus (*.md tracked); other ingested docs gitignored
data/playbooks/        # procedural-memory agent playbooks
docs/                  # architecture + deployment notes
docker-compose.yml     # local infra (qdrant + langfuse + api + web)
```

## Conventions

- **Python**: 3.11+, type hints everywhere, `from __future__ import annotations`. Format/lint with `ruff`.
  Modules stay small and single-purpose. Docstrings explain *why*, not *what*.
- **Config**: nothing hardcoded — everything flows through `atlas.config.get_settings()`.
  Integrations **degrade gracefully** when keys are missing and report status via `/health/ready`.
- **Observability is not optional**: every agent node and tool call is traced through Langfuse.
  When you add a node, attach `atlas.observability.langchain_callbacks()`.
- **Grounding rule**: no claim in a generated report may exist without a retrieved-evidence citation.
  Guardrails enforce this; don't loosen them.
- **Frontend**: Next.js App Router, server components by default, `"use client"` only where needed.
  Tailwind (hand-rolled war-room components; shadcn optional). Stream agent activity over SSE;
  never block the UI on a full run.
- **Commits**: conventional style (`feat:`, `fix:`, `chore:`), scoped per milestone. Branch off `main`;
  don't commit secrets — only `.env.example` is tracked.

## How to run (local)

```bash
cp apps/api/.env.example apps/api/.env   # then add GROQ_API_KEY (required)
docker compose up -d qdrant langfuse
cd apps/api && pip install -e ".[dev]" && uvicorn atlas.main:app --reload
# frontend (M5): cd apps/web && npm install && npm run dev
```

> Note: Atlas is fully self-contained under `apps/` with its own env at
> `apps/api/.env` — it never depends on files at the repo root beyond
> `docker-compose.yml`.

## Milestones

- **M0** Dev harness — CLAUDE.md, subagents, skills ✅
- **M1** Skeleton & rails — FastAPI, Groq client, Langfuse, config, Docker, CI ✅
- **M2** Hybrid RAG core — LangChain EnsembleRetriever + CrossEncoderReranker + CRAG, Qdrant, Ragas ✅
- **M3** Agents & orchestration — supervisor graph, 4 specialists (parallel), shared checkpointed state, tools ✅
- **M4** Debate & synthesis — Bull/Bear/Judge, cited report + confidence + grounding guardrail ✅
- **M5** War-room frontend — Next.js live agent graph, streaming debate, report view ✅
- **M6** Memory layers — episodic (SQLite + vectors), procedural (playbooks), summarizer agent ✅
- **M7** LLM Ops — auto eval → gate → self-improvement (rewrite prompt) → release (versioned prompt registry) ✅

## Working with this repo (subagents & skills)

This project ships **single-responsibility subagents** under `.claude/agents/`. Delegate work to the
matching specialist instead of doing everything in the main thread:

| Subagent | Owns |
|---|---|
| `backend-engineer` | FastAPI endpoints, services, Python wiring, tests |
| `frontend-engineer` | Next.js war-room UI, shadcn components, SSE streaming |
| `rag-engineer` | ingestion, hybrid retrieval, re-rank, CRAG, Qdrant, Ragas |
| `orchestration-engineer` | LangGraph graph, supervisor, specialists, debate, MCP tools |
| `observability-engineer` | Langfuse tracing, cost tracking, Ragas eval harness, guardrails, LLM-Ops |
| `infra-engineer` | Docker Compose, env, local infra, deployment |
| `debugger` | root-cause diagnosis of failures, flaky tests, version/dependency errors |
| `tester` | full QA passes, coverage, adversarial edge-case + error-path tests |

Reusable procedures live under `.claude/skills/`: `atlas-backend-endpoint`,
`atlas-langgraph-node`, `atlas-rag-component`, `atlas-ui-component`, `atlas-trace-and-eval`,
`atlas-debug`, `atlas-test`. Subagents should invoke the relevant skill so work follows Atlas conventions.
