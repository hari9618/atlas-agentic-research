# Atlas Investor Platform — Design & Contracts

Branch: `feat/investor-platform`. This doc is the single source of truth shared by the
backend (agents/graph), persistence, and frontend workstreams. If you need to change a
contract here, change it in this file in the same commit.

## Goals

1. **Investor-grade report**: a structured brief that covers what an investor or
   business person expects from a research analyst, readable at a glance.
2. **Research any company**: live web, news, market and SEC data, not only uploaded docs.
3. **Proper retries**: transient failures are retried with backoff; one failing agent
   degrades its section instead of killing the run.
4. **Durable state**: Postgres when `DATABASE_URL` is set (checkpoints, episodic memory,
   prompt registry), SQLite fallback for dev/tests.
5. **Human-in-the-loop**: after the report is drafted, a human approves it or requests
   changes; feedback triggers targeted extra research and a regenerated report.
6. **Product UI**: a real website (landing page) plus a clean research workspace.

## Non-goals and decisions

- **No A2A protocol.** All agents run in one process and coordinate through LangGraph's
  typed shared state with reducers. A2A is for independent agent services owned by
  different teams; it would add network hops and failure modes without solving any
  problem here. The real state problem was durability, which Postgres solves.
- The shared state is small and per-run. SQLite was never a memory problem (it is on
  disk). The real problems were: (a) Render's filesystem is ephemeral, so checkpoints
  and memory are wiped on deploy, which breaks paused human-review runs; (b) SQLite is
  single-writer, so it cannot back multiple workers.
- Agents call tools in-process for latency. The same tools are exposed over MCP
  (`atlas/core/tools/mcp_server.py`) for interoperability.

## 1. Report schema (`report_sections`)

The synthesizer returns this JSON object. The backend also renders it to markdown and
keeps that in `report` (used by guardrails, eval, episodic memory, PDF fallback).

```json
{
  "company": "Helios Robotics",
  "headline": "One sentence that answers the user's question.",
  "stance": "positive | neutral | cautious",
  "confidence": 0.0,
  "executive_summary": ["3-5 bullets: the findings that matter most, each cited"],
  "company_overview": {
    "what_they_do": "plain-English description",
    "business_model": "how they make money",
    "products": ["main products / services"],
    "customers": "who buys and why"
  },
  "financials": {
    "summary": "growth and financial health in plain words",
    "metrics": [
      {"label": "Revenue (FY2025)", "value": "$4.2B", "change": "+28% YoY", "citation": "[sec_edgar#0]"}
    ]
  },
  "market_position": {
    "summary": "where they stand in the market",
    "strengths": ["..."],
    "weaknesses": ["..."]
  },
  "competitors": [
    {"name": "Aster Dynamics", "comparison": "how they compare", "threat": "high | medium | low", "citation": "[research#0]"}
  ],
  "recent_developments": [
    {"date": "Mar 2026", "title": "short headline", "detail": "what happened and why it matters",
     "sentiment": "positive | neutral | negative", "citation": "[news#0]"}
  ],
  "sentiment": {"overall": "positive | mixed | negative", "summary": "the overall mood"},
  "risks": [
    {"title": "Customer concentration", "severity": "high | medium | low", "detail": "...", "citation": "[sec_edgar#1]"}
  ],
  "bull_case": ["optimistic points"],
  "bear_case": ["cautious points"],
  "outlook": {"summary": "what to expect", "watch_items": ["what an investor should monitor"]},
  "bottom_line": "2-3 sentences a reader can act on.",
  "uncertainties": ["what we are NOT sure about"]
}
```

Rules:
- Every factual claim carries an inline citation using the evidence's bracketed label.
- Never invent numbers. If there's no evidence for a field, use `[]` or the string
  `"Not enough evidence yet."`.
- Enum fields use exactly the listed lowercase values.
- All fields are optional to the frontend: render what is present, hide what is empty.
- `confidence` from the LLM is tempered by the grounding guardrail before it is returned.

## 2. Shared state additions (`ResearchState`)

| field | type | meaning |
|---|---|---|
| `target` | str | company under analysis (supervisor extracts it) |
| `ticker` | str | stock ticker if public and known, else `""` |
| `report_sections` | dict | the schema above |
| `require_review` | bool | pause for human review after drafting |
| `review_status` | str | `pending`, `approved`, `revision_requested`, `auto_approved` |
| `feedback` | str | latest reviewer feedback |
| `revision` | int | 0 for the first draft, +1 per requested change |
| `review_history` | list[dict] (reducer `operator.add`) | `{revision, action, feedback}` |

## 3. Graph

```
START → recall → supervisor → [fundamentals ‖ news_sentiment ‖ risk ‖ market]
      → debate_round → synthesize → human_review
human_review: approve / auto ──────────────→ remember → END
human_review: revise ─→ revise_research ─→ synthesize  (loop, max 3 revisions)
```

- `supervisor` returns JSON `{target, ticker, focus_areas}`.
- Specialists add tool evidence as citable chunks: `fundamentals` → `sec_filing_excerpt(ticker)`,
  `market` → `stock_quote(ticker)`, `news_sentiment` → `company_news(target)`. Web search
  stays as the CRAG fallback.
- `human_review` uses LangGraph `interrupt()`. Payload = the draft. Resume value is
  `{"action": "approve"}` or `{"action": "revise", "feedback": "..."}`. When
  `require_review` is false it auto-approves without interrupting.
- `revise_research` retrieves extra evidence for the feedback (CRAG + web) and appends
  findings, then `synthesize` rewrites the report addressing the feedback.
- Scores are pushed to Langfuse once, after the final approval.

## 4. HTTP / SSE protocol

`EventSource` only supports GET, so both stream endpoints are GET.

### `GET /research/stream?q=<query>&thread_id=<id>&review=1`
Starts a run. `review=1` pauses for review (default for the web UI). Events:

| event | data |
|---|---|
| `start` | `{query, thread_id}` |
| `<node>` | that node's state update (`recall`, `supervisor`, `fundamentals`, `news_sentiment`, `risk`, `market`, `debate_round`, `synthesize`, `revise_research`, `remember`) |
| `review_required` | `ResearchPayload` + `{thread_id, revision}` — the run is paused |
| `final` | `ResearchPayload` + `{thread_id, revision, review_status}` — the run is complete |
| `error` | `{error}` — friendly message |

### `GET /research/resume?thread_id=<id>&action=approve|revise&feedback=<text>`
Resumes a paused run. Emits the same events and ends with another `review_required`
(new draft) or `final`.

### `POST /research/sync`  (unchanged contract)
Runs to completion with review off. Response is `ResearchPayload`.

### `ResearchPayload`
```ts
{
  report: string;                 // markdown rendering
  report_sections: ReportSections | null;
  confidence: number | null;
  uncertainties: string[];
  citations: {citation: string; agent?: string}[];
  findings: {agent: string; claim: string; citation: string; confidence: number}[];
  debate: {role: string; text: string; leaning?: string}[];
  plan: string[];
  target?: string;
}
```

## 5. Retry policy (`atlas/core/resilience.py`)

- Transient = rate limit (HTTP 429), timeouts, connection errors, HTTP 5xx.
- Retry transient errors with exponential backoff + jitter, bounded attempts and a
  max wait. Never retry non-transient errors (bad request, auth, parse errors).
- Every retry is logged (and therefore visible in traces).
- Degrade per node after retries are exhausted:
  - specialist → one finding marking the agent unavailable (confidence 0) + an uncertainty
  - debate → neutral stub
  - supervisor → default plan
  - synthesizer → fall back to the markdown prompt; if that fails, the run errors
  - tools → empty result (`[]` / `{}`)
- The Groq client keeps its own Retry-After aware retries; the outer layer covers
  everything else (tools, parsing-independent transient failures) and degradation.

## 6. Persistence

`atlas/core/persistence.py` owns backend selection.
- `get_checkpointer()` → `PostgresSaver` when `DATABASE_URL` is set, else `SqliteSaver`.
- Episodic memory and the prompt registry use Postgres tables when `DATABASE_URL` is
  set, SQLite/JSON otherwise.
- Tests stay on SQLite.

## 7. Frontend

- `/` — marketing site: nav, hero with a sample-report mock, who-it's-for strip, how it
  works, features, sample report preview, comparison table (Atlas vs chatbot vs manual
  analyst), FAQ, final CTA, footer.
- `/research` — workspace: query box, knowledge base panel, compact live agent progress,
  the structured report, the review panel (Approve / Request changes), PDF export.
- Clean light, professional theme (slate text, indigo accent; emerald/amber/rose for
  positive/neutral/negative and severity).
- Falls back to markdown `report` if `report_sections` is missing.
