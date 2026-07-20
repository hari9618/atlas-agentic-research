# Atlas — End-to-End Architecture

How a single question flows through the whole system: from the war-room UI, through
the multi-agent research graph and the hybrid-RAG evidence engine, to a cited report —
and back through the self-improving LLM-Ops loop.

---

## Two separate paths (read this first)

Agents **consume** the knowledge base; they never fill it. Documents get in through a
distinct ingestion path that runs *before* any question is asked.

```
━━━ PATH 1 · INGESTION (before the run) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Upload a file  ─┐
  Paste text     ─┼─►  POST /corpus/*        routers/corpus.py
  Ticker (10-K)  ─┘         │                 (or CLI: make ingest)
  Drop in data/corpus/      ▼
                      chunk 220 words         core/rag/chunking.py
                            ▼                 (40-word overlap)
                      bge embeddings          core/rag/embeddings.py
                            ▼
                      Qdrant "atlas_corpus"   ← the searchable index
                      (in-memory fallback when Qdrant is down)

  No agent involved. No LLM. Files → vectors.

━━━ PATH 2 · THE RUN (below) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Agents SEARCH that index. Live web tools are a CRAG fallback, used for the
  current answer only — web results are NOT written back to the index.
```

---

## Full request flow

```
  USER: "Should I worry about Helios Robotics as a competitor?"
                              │
        apps/web/app/page.tsx  ──►  EventSource (SSE)
                              │
        apps/api/atlas/routers/research.py   (FastAPI, streams events)
                              │
                              ▼
╔══════════════════════════ LangGraph ════════════════════════════╗
║                       core/graph.py                              ║
║      every node traced → Langfuse   (atlas/observability.py)     ║
╚══════════════════════════════════════════════════════════════════╝
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  ① RECALL                     core/memory/episodic.py        │
│  • embed ONLY the incoming question                          │
│  • cosine vs. vectors persisted in SQLite at save time        │
│    (recall is flat — it never re-embeds stored episodes)      │
│  • load prior findings as context                            │
└─────────────────────────────────────────────────────────────┘
                              │  prior context
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  ② SUPERVISOR                 core/graph.py                   │
│  • load each agent's playbook   core/memory/procedural.py     │
│  • dispatch 4 specialists → ONE shared state  core/state.py   │
│    (checkpointed in SQLite → resumable)                       │
└─────────────────────────────────────────────────────────────┘
          │            │            │            │
          ▼            ▼            ▼            ▼   (parallel)
   ┌───────────┐┌───────────┐┌───────────┐┌───────────┐
   │FUNDAMENTAL││   NEWS    ││   RISK    ││  MARKET   │  temp 0.3
   └─────┬─────┘└─────┬─────┘└─────┬─────┘└─────┬─────┘
         │            │            │            │   core/agents/specialists.py
         └────────────┴─────┬──────┴────────────┘
                            │  each agent → evidence engine ↓
                            ▼
╔═══════════════════════════════════════════════════════════════╗
║   EVIDENCE ENGINE   (RAG + tools)                             ║
║                                                               ║
║   question                                                    ║
║      ├──▶ BM25 (exact: "Helios","$4.2M")  ┐                   ║
║      └──▶ bge vectors (meaning)           │ core/rag/index.py ║
║                     │  ← both hit Qdrant  ┘                   ║
║                     ▼                                         ║
║              RRF fusion  (merge rankings)                     ║
║                     ▼                                         ║
║              cross-encoder re-rank  (best 5 of 20)            ║
║                     ▼                                         ║
║              rewrite query + re-search (corrective step)      ║
║                     ▼                                         ║
║              CRAG grade — three ways     core/rag/crag.py     ║
║                     │                                         ║
║      ┌──────────────┼──────────────────┐                      ║
║   CORRECT       AMBIGUOUS          INCORRECT                  ║
║  use local    local + web        web leads,                   ║
║               COMBINED           local dropped                ║
║                     │                  │                      ║
║                     └────────┬─────────┘                      ║
║                              ▼                                ║
║              🌐 web_evidence()      core/rag/web_evidence.py  ║
║                 web_search (Tavily) → RetrievedChunk          ║
║                 scored below local; fails soft if no key      ║
║                              ▼                                ║
║   ONE evidence format, whatever the origin — every chunk      ║
║   carries source/title/url, so a web claim is cited exactly   ║
║   like an ingested filing and the guardrail treats both alike ║
╚═══════════════════════════════════════════════════════════════╝
                            │  grounded findings → shared state
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  ④ DEBATE                     core/agents/debate.py          │
│     BULL (temp 0.6)  ⇄  BEAR (temp 0.6)                      │
│     both must cite evidence from the state                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  ⑤ JUDGE + SYNTHESIZE                                        │
│  • JUDGE (temp 0.1)              core/agents/debate.py       │
│  • SYNTHESIZER (temp 0.3)        core/agents/synthesizer.py  │
│      system prompt pulled from → core/llmops/registry.py     │
│  • GUARDRAIL: uncited claim → REJECTED   core/guardrails.py  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
              ┌───────────────────────────────┐
              │   CITED REPORT  (temp 0.0 meta)│
              │   • every claim → source      │
              │   • confidence score          │
              │   • "what we're unsure about" │
              └───────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  ⑥ REMEMBER                   core/memory/episodic.py        │
│  • save run → SQLite: question, report, confidence, findings  │
│    + the question's embedding, computed once here             │
│  • summarizer (Llama 3.1 8B) distills → semantic facts,       │
│    written into the same corpus index                         │
│                                core/memory/summarizer.py      │
│    → next run's step ① recalls this                          │
└─────────────────────────────────────────────────────────────┘
```

---

## The self-improving LLM-Ops loop

Runs on top of the pipeline above — it grades each run and rewrites weak prompts.

```
  run output
      ▼
  ① EVALUATE (Ragas)          core/llmops/evaluate.py
     faithfulness · answer relevancy · context precision
      │
      ├─ PER-AGENT EVAL        core/llmops/agent_eval.py
      │    score each specialist: groundedness · richness
      │    → weakest_agent() names the culprit
      │    → attribution needed to auto-improve beyond the synthesizer
      │
      ├──── push scores ───►  LANGFUSE  (ragas_* + atlas_agent_eval:<agent>)
      │                       eval/langfuse_scores.py
      ▼
  ② GATE   score ≥ threshold?     core/llmops/gate.py
      │
   ┌──┴───────────────┐
  PASS               FAIL
   │                  ▼
   │            ③ DIAGNOSE weak prompt   core/llmops/optimizer.py
   │                  ▼
   │            ④ REWRITE prompt (candidate)
   │                  ▼
   │            ⑤ RE-EVAL (Ragas) → better?
   │                  ▼
   ▼            ⑥ PROMOTE → new active version
  RELEASE  ◄──────────┘        core/llmops/registry.py
   │                          (versioned prompt registry)
   ▼
  active prompt feeds back into ⑤ SYNTHESIZE  (next runs)
```

**In one line:** Ragas scores each run → Langfuse stores them → if a score fails the gate,
the optimizer diagnoses and rewrites the prompt, re-evaluates, and promotes it in the
registry → that new prompt is what the synthesizer uses next time. The system grades and
improves itself.

---

## Hybrid evidence: uploaded documents first, web as the safety net

A question about a company nobody has ingested must still get a grounded answer, and a
question about a company that *has* been ingested must prefer those curated documents.
CRAG's three-way grade is what arbitrates between the two.

| Grade | Meaning | Evidence used |
|---|---|---|
| **CORRECT** | local evidence answers the question | uploaded/ingested documents only |
| **AMBIGUOUS** | partially relevant | local **combined** with web, interleaved so neither is crowded out |
| **INCORRECT** | off-topic | web leads; off-topic local evidence is displaced |

The middle row is the one that matters in practice. A question about an un-ingested
company still overlaps corpus vocabulary ("robotics", "revenue"), so it grades
AMBIGUOUS rather than INCORRECT — escalating to the web only on INCORRECT (as an
earlier version did) left those runs answering from partial evidence about the *wrong*
company.

Web hits are converted to the same `RetrievedChunk` type as ingested content, carrying
`source`, `title`, and `url`. One evidence format means the agents, the citation
system, and the grounding guardrail need no special case for provenance. Web chunks
are scored below local ones (0.45, decaying by rank) because the corpus is curated and
the open web is not. No Tavily key, a network failure, or an offline test run all yield
an empty list — "no web evidence", never an error.

## Storage design

Two stores, each chosen for what it is good at.

| Store | Holds | Why this one |
|---|---|---|
| **Qdrant** — one collection, `atlas_corpus` | document chunks + their bge vectors, and the summarizer's distilled facts | built for "find the nearest meaning" across many vectors; falls back to an in-memory store when Qdrant isn't running |
| **SQLite** — `episodes` table | one row per past run: question, report, confidence, findings, timestamp, **and the question's embedding as a BLOB** | needs `ORDER BY created_at` / filtering, which a vector store handles poorly — and keeping the vector here means recall works without Qdrant |
| **SQLite** — LangGraph checkpointer | the shared working state of an in-flight run | makes a run durable and resumable after a crash |

Episode vectors live in SQLite rather than a second Qdrant collection deliberately:
Atlas is meant to run without Docker, so memory must not depend on infrastructure that
may be absent. The trade-off is that recall is a linear numpy scan rather than an
indexed ANN search — fine at this scale, and the point where a dedicated memory
collection would start to pay off.

## Code map

| Part | File |
|---|---|
| Frontend (war-room UI) | `apps/web/app/page.tsx`, `layout.tsx`, `globals.css` |
| Frontend components | `components/AgentGraph.tsx` · `DebatePanel.tsx` · `FindingsList.tsx` · `ConfidenceDial.tsx` · `ReportView.tsx` · `CorpusPanel.tsx` |
| PDF export | `components/PrintableReport.tsx` · `ExportButton.tsx` · print rules in `app/globals.css` |
| Backend API (SSE stream) | `apps/api/atlas/routers/research.py` · `health.py` · `corpus.py` · `llmops.py` |
| Ingestion | `core/rag/ingest.py` (CLI) · `routers/corpus.py` (live) · `core/rag/loaders/` |
| Graph orchestration | `apps/api/atlas/core/graph.py` |
| Shared state | `apps/api/atlas/core/state.py` |
| Agents | `core/agents/specialists.py` · `debate.py` · `synthesizer.py` · `base.py` |
| Prompts | playbooks → `data/playbooks/*.md` · versioned → `core/llmops/registry.py` |
| RAG engine | `core/rag/index.py` · `crag.py` · `chunking.py` · `embeddings.py` · `ingest.py` |
| MCP tools | `core/tools/web_search.py` · `sec.py` · `market.py` |
| Web→evidence adapter | `core/rag/web_evidence.py` (turns search hits into citable chunks) |
| Memory | `core/memory/episodic.py` · `procedural.py` · `summarizer.py` |
| Guardrail | `core/guardrails.py` |
| LLM-Ops loop | `core/llmops/evaluate.py` · `agent_eval.py` · `gate.py` · `optimizer.py` · `registry.py` |
| Ragas / eval | `eval/ragas_eval.py` · `langfuse_scores.py` · `golden.py` |
| LLM factory / tracing | `atlas/llm.py` · `atlas/observability.py` |

---

## Temperature per agent (task-tuned)

| Agent | Temp | Why |
|---|---|---|
| Specialists | 0.3 | Mostly factual, slight flexibility |
| Bull / Bear | 0.6 | Creative, persuasive arguments |
| Judge | 0.1 | Fair, consistent, low randomness |
| Synthesizer (report) | 0.3 | Clear writing, still grounded |
| Synthesizer (scores) | 0.0 | Deterministic — a score must not change on re-run |

**Model:** Groq · Llama 3.3 70B (main) · Llama 3.1 8B (cheap summarizer)
