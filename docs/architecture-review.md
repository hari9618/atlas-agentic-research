# Architecture review — findings and fixes (Nov 2026)

An independent review of the backend (reliability, scalability, retrieval, the learning
loop, agent design, tests), done read-only by a separate reviewer and then fixed. Each
finding lists what was wrong, the concrete failure, and what changed. Open items are
listed honestly at the end.

## Product gap that triggered the work

Users don't need help with NVIDIA — a chat assistant already summarizes it. They ask
about **small, private and mid-sized companies** that have no filings, no stock and no
press. Atlas only knew those public sources, and a question like *"my company is
caughtleads.com — should I worry about revsquad.ai as a competitor?"* produced a brief
**about CaughtLeads** (the asker) with "insufficient public data".

**Fix:** a research brief (`core/agents/brief.py`) that separates *subject*, *asker*,
*persona* (investor / competitor / buyer / partner / job seeker), *goal* and *extra
asks*, with deterministic verification of the model's answer; a safe website reader
(`core/tools/website.py`); company evidence from reviews, LinkedIn (via search),
funding pages, "alternatives" pages and the asker's own site
(`core/rag/company_evidence.py`); and a persona-shaped report (verdict, snapshot,
strengths, weaknesses, pricing, customer praise/complaints, head-to-head, answers to
extra asks). On the original question the live agent now answers: *not a direct
competitor — RevSquad sells AI sales coaching to B2B sales teams, CaughtLeads captures
inbound calls for home-services businesses; low threat, monitor*, with real pricing.

## Findings

| # | Severity | Finding | Status |
|---|---|---|---|
| 1 | critical | CRAG grade parsing read `INCORRECT` as `CORRECT` (substring), so off-topic local evidence was accepted and the web fallback never ran — in production only (tests are offline). | **Fixed** — whole-word, last-match parsing (`crag.parse_grade`), routed through `chat()` on the small model; table test. |
| 2 | critical | Episodic memory was global: any user's question + report summary was injected into every other user's prompts (data leak + prompt-injection channel); recall by query similarity pulled *other companies'* reports. | **Fixed** — episodes carry an `owner`; recall is by owner **and** subject identity, after the brief (graph is now supervisor → recall); prior context is fenced as untrusted data. |
| 3 | high | Consolidated (derived) memory counted as "the corpus covers this company", switching later runs off the web; local retrieval wasn't entity-filtered. | **Fixed** — derived chunks excluded from coverage; local results filtered to the subject; consolidation into the shared index off by default (it would mix tenants). |
| 4 | high | Learning loop not statistically sound: 2 trials, 0.03 bar, failed trials dropped, validated on the runs the lesson came from. Simulated false-release rate ≈ 25%. | **Fixed** — 6-question holdout benchmark, ≥ 4 trials, failures block release, ≥ 75% of questions must improve, bootstrap one-sided 97.5% bound > 0. Simulated: ~4% of no-op changes pass, ~95% of real +0.08 gains do (tested). Records now carry the brief so replay uses production evidence. |
| 5 | high | The loop learned from unvetted input: any reviewer's text could become a lesson in every user's prompts. | **Fixed** — only signed-up (non-guest) reviewers count; degraded runs teach nothing; lessons with links/addresses/hijack phrasing are refused; a validated change waits for **admin approval of the exact lesson text** (`/llmops/experiments/{id}/approve`), unless `LLMOPS_AUTO_RELEASE` is set. |
| 6 | high | No token-aware capacity model; LLM retries can exceed stream timeouts; several LLM calls bypass the bulkhead. | **Partly fixed** — CRAG grading now goes through `chat()` (bulkhead, retries, tracing). A provider-wide token bucket and per-run deadline remain **open**. |
| 7 | high | Retrieval index: cross-encoder rebuilt on every `retrieve()`; Qdrant re-appends the corpus on rebuild; per-process BM25. | **Partly fixed** — one cached cross-encoder per process. Deterministic Qdrant point ids / incremental upsert and shared BM25 remain **open** (production uses the lightweight path, `ATLAS_OFFLINE_EMBED=1`). |
| 8 | high | Citation keys `source#rank` collided across specialists (four pages behind `web_search#0`); ids used per-process `hash()`. | **Fixed** — content-derived stable keys (`types.stable_ordinal`, blake2b) for web-tier evidence: same evidence → same key, different evidence → different key. |
| 9 | high | Statement-level verification runs only after delivery; findings without a citation index silently cited chunk #1. | **Partly fixed** — no default citation index; verifier bug (nested `[web]` markers made every web citation look uncited) fixed. Running `verify_report` before `final` remains **open**. |
| 10 | high | LLM-guessed tickers trusted: a private "Helios Robotics" guessed as HLIO got Helios Technologies' 10-K as authoritative evidence. | **Fixed** — ticker kept only if the listed company's name matches the subject (all significant words); otherwise dropped with a note to the reader and researched as private. |
| 11 | high | Brief extractor misread askers ("I run a bakery" → asker "a bakery") and forced the competitor persona. | **Fixed** — case-sensitive name capture, clause-aware entity detection, no persona forcing, lazy fallback; table test over the reviewer's cases. |
| 12 | medium | Entity guard didn't strip "Private Limited", "Pvt Ltd", "Pte", GmbH, AG… — every hit dropped for Indian/EU/APAC privates; domain match was a raw substring. | **Fixed** — expanded legal suffixes; whole-domain regex match; domain or URL host counts as identity. |
| 13 | medium | Web/site text reached prompts undelimited; hidden page text kept. | **Fixed** — evidence fenced in `<evidence>` tags with an explicit "data, not instructions" rule; `display:none` / `aria-hidden` / `hidden` nodes stripped; the question is quoted as data in the planner. |
| 14 | medium | Evaluation ran on the user's stream after `final`, holding the run slot. | **Fixed** — recorded on a small background pool. A durable job queue remains **open**. |
| 15 | medium | O(N) decrypt-everything recall; no retention. | **Partly fixed** — recall is a bounded owner-scoped query. Retention jobs remain **open**. |
| 16 | medium | DB pool shared by checkpoints and the limiter. | **Open** — documented; Redis recommended for >1 replica. |
| 17 | medium | Silent supervisor degradation; debate verdict parsed the first tag; debate framing ignored persona. | **Fixed** — `degraded` flag surfaced in uncertainties; last-tag parse; debate receives the brief. |
| 18 | medium | Search budget (~14 searches/run) vs the free tier. | **Partly fixed** — search cache 10 min → 1 h; same evidence shared across specialists via the cache. Credit tracking remains **open**. |
| 19 | medium | Token waste (big model for one-word grades). | **Partly fixed** — grader on the small model at low reasoning effort. |
| 20 | low-med | Unknown provenance defaulted to *authoritative*. | **Fixed** — allowlist; unknown sources are web-tier. |

## Testing

* Offline suite: 405 tests (CI runs them against real Postgres 16 + Redis 7).
* New table tests for the brief, the SSRF guard, hidden-text stripping, company
  evidence slices, citation-key stability, tenant-scoped memory, ticker verification,
  the learning-loop decision rule under simulated noise, and lesson safety.
* **Live agentic evaluation** (`apps/api/evals/agentic`, DeepEval): persona scenarios
  (competitor/private, buyer/pricing, investor/small, public regression, prompt
  injection) run the real agents, then deterministic checks (right subject, asker,
  persona, sections, no citations to unretrieved evidence) and DeepEval metrics judged
  by the Groq model (answers the question, surfaces negatives, persona fit,
  faithfulness). Workflow: `.github/workflows/agent-eval.yml` (manual + weekly).
* Live results so far: the CaughtLeads/RevSquad competitor scenario passed (G-Eval
  0.9 / 0.9 / 0.9, Faithfulness 1.0). Later runs surfaced harness problems, all fixed:
  a judge rubric that graded the *question* for negatives, the neural reranker
  crashing next to the judge on Windows (evals now use production's lightweight
  path), a judge that truncated DeepEval's schema, and a judge sharing the agent's
  Groq daily token budget (it now runs on the small model, which Groq limits
  separately). On the free tier, about 2–3 full scenarios fit in one day's tokens.

## Open items (next)

1. Provider-wide token bucket in Redis + per-run deadline; admit runs by token budget.
2. Run statement verification before `final`; drop/flag unsupported statements.
3. Qdrant deterministic point ids + incremental upsert; shared sparse (BM25) index.
4. Durable job queue for evaluation/recording; retention jobs for checkpoints, episodes,
   records.
5. Search-credit tracking surfaced in the report when web research is degraded.
6. Mark specialist/debate/synthesis fallbacks (e.g. LLM daily quota exhausted) in
   `degraded`, so a starved run says so instead of reading like "little public data".
