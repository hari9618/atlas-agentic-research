// Typed client for the Atlas backend. Contract: docs/investor-platform-design.md §1 + §4,
// plus the review (reject / section) and LLM-Ops (/llmops/*) additions.

import type { Me } from "./auth-common";
import { authFetch } from "./auth";
import { API, type ApiFailure, fail, failureFromResponse, isOffline, markHealthy } from "./http";
import { createSseParser, type SseMessage } from "./sse";

// The transport basics moved to lib/http.ts; re-exported so callers keep one import.
export { API, ensureAwake, isWarm } from "./http";
export type { ApiFailure, FailureKind, ServerErrorCode, WakeResult } from "./http";

// ---------------------------------------------------------------------------
// Report schema (§1). Every field is optional: the UI renders what is present.
// Enum fields are typed loosely (`| string`) because they come from an LLM; the
// report components normalise unknown values to a neutral style.
// ---------------------------------------------------------------------------

export type Stance = "positive" | "neutral" | "cautious";
export type Level = "high" | "medium" | "low";
export type Tone = "positive" | "neutral" | "negative";
export type OverallSentiment = "positive" | "mixed" | "negative";

export type Metric = { label?: string; value?: string; change?: string; citation?: string };
export type Competitor = {
  name?: string;
  comparison?: string;
  threat?: Level | string;
  citation?: string;
};
export type Development = {
  date?: string;
  title?: string;
  detail?: string;
  sentiment?: Tone | string;
  citation?: string;
};
export type Risk = { title?: string; severity?: Level | string; detail?: string; citation?: string };

/** Who asked, and why. The report adapts its verdict and emphasis to the persona. */
export type Persona = "investor" | "competitor" | "buyer" | "partner" | "job_seeker" | "general";
export type Brief = {
  persona?: Persona | string;
  /** The asker's own company (e.g. "CaughtLeads"), if they named one. */
  asker?: string;
  asker_domain?: string;
  subject_domain?: string;
  goal?: string;
  extra_asks?: string[];
};
/** The direct answer to the question, for this persona. */
export type Verdict = { answer?: string; recommendation?: string };
export type Fact = { label?: string; value?: string; citation?: string };
export type PricingPlan = { name?: string; price?: string; notes?: string; citation?: string };
export type Pricing = { summary?: string; plans?: PricingPlan[] };
export type Edge = "subject" | "asker" | "even";
export type HeadToHeadRow = {
  dimension?: string;
  subject?: string;
  asker?: string;
  edge?: Edge | string;
  citation?: string;
};
export type HeadToHead = {
  asker?: string;
  overlap?: "high" | "medium" | "low" | "none" | string;
  summary?: string;
  rows?: HeadToHeadRow[];
};
export type CustomAnswer = { question?: string; answer?: string; citation?: string };

export type ReportSections = {
  company?: string;
  headline?: string;
  stance?: Stance | string;
  confidence?: number;
  executive_summary?: string[];
  company_overview?: {
    what_they_do?: string;
    business_model?: string;
    products?: string[];
    customers?: string;
  };
  financials?: { summary?: string; metrics?: Metric[] };
  market_position?: { summary?: string; strengths?: string[]; weaknesses?: string[] };
  competitors?: Competitor[];
  recent_developments?: Development[];
  sentiment?: { overall?: OverallSentiment | string; summary?: string; praise?: string[]; complaints?: string[] };
  risks?: Risk[];
  bull_case?: string[];
  bear_case?: string[];
  outlook?: { summary?: string; watch_items?: string[] };
  bottom_line?: string;
  uncertainties?: string[];
  // Persona-aware additions (all optional; older reports simply lack them).
  brief?: Brief;
  verdict?: Verdict;
  snapshot?: Fact[];
  /** Top-level now; market_position.strengths/weaknesses mirror these. */
  strengths?: string[];
  weaknesses?: string[];
  pricing?: Pricing;
  head_to_head?: HeadToHead;
  custom_answers?: CustomAnswer[];
};

export type Finding = { agent: string; claim: string; citation: string; confidence: number };
export type DebateTurn = { role: string; text: string; leaning?: string };
export type Citation = { citation: string; agent?: string };

// ---------------------------------------------------------------------------
// Human review
// ---------------------------------------------------------------------------

/** What a reviewer can send back to a paused run. */
export type ReviewDecision = "approve" | "revise" | "reject";
/** Decisions as recorded in `review_history` (the backend adds `auto_approve` when the
 *  revision limit is reached). */
export type ReviewAction = ReviewDecision | "auto_approve";

/** The report sections a reviewer can aim feedback at (`section` on /research/resume). */
export type ReviewSectionKey =
  | "verdict"
  | "snapshot"
  | "strengths"
  | "weaknesses"
  | "pricing"
  | "head_to_head"
  | "custom_answers"
  | "company_overview"
  | "financials"
  | "market_position"
  | "competitors"
  | "recent_developments"
  | "risks"
  | "outlook";

export type ReviewHistoryItem = {
  revision: number;
  action: ReviewAction;
  feedback: string;
  section?: ReviewSectionKey | string | null;
};

/** The full result of a run (§4). */
export type ResearchPayload = {
  report: string;
  report_sections: ReportSections | null;
  confidence: number | null;
  uncertainties: string[];
  citations: Citation[];
  findings: Finding[];
  debate: DebateTurn[];
  plan: string[];
  target?: string;
  review_history?: ReviewHistoryItem[];
};

export type ReviewRequired = ResearchPayload & { thread_id: string; revision: number };
export type FinalPayload = ResearchPayload & {
  thread_id: string;
  revision: number;
  /** "approved" | "auto_approved" | "rejected" (typed loosely: it is server state). */
  review_status: string;
};

// Graph node names streamed as SSE event names (must match the backend graph, §3/§4).
export const NODE_EVENTS = [
  "recall",
  "supervisor",
  "fundamentals",
  "news_sentiment",
  "risk",
  "market",
  "debate_round",
  "synthesize",
  "human_review",
  "revise_research",
  "remember",
] as const;
export type NodeName = (typeof NODE_EVENTS)[number];

export const SPECIALISTS = ["fundamentals", "news_sentiment", "market", "risk"] as const;

// ---------------------------------------------------------------------------
// SSE streams
// ---------------------------------------------------------------------------

export type StreamHandlers = {
  onStart?: (data: { query?: string; thread_id?: string }) => void;
  onNode?: (node: NodeName, data: Record<string, unknown>) => void;
  onReviewRequired?: (data: ReviewRequired) => void;
  onFinal?: (data: FinalPayload) => void;
  onError?: (failure: ApiFailure) => void;
};

/** No agent step takes anywhere near this long; silence beyond it means a dead link. */
const STALL_MS = 240_000;

const isNode = (e: string): e is NodeName => (NODE_EVENTS as readonly string[]).includes(e);

function parse(raw: unknown): Record<string, unknown> {
  if (typeof raw !== "string" || !raw) return {};
  try {
    const v = JSON.parse(raw);
    return v && typeof v === "object" ? (v as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

async function readJson(res: Response): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

/** Open an authenticated SSE stream and dispatch Atlas events. Returns a cancel fn.
 *
 *  Read with fetch rather than EventSource, which can't send the bearer token. That
 *  also settles reconnects: there are none. A retried GET would launch a duplicate run
 *  (or a duplicate resume), so every failure ends the stream on the spot and is
 *  reported once, classified. */
function openStream(path: string, h: StreamHandlers): () => void {
  const ctrl = new AbortController();
  let done = false;
  let stall: ReturnType<typeof setTimeout> | undefined;

  const finish = () => {
    done = true;
    clearTimeout(stall);
    ctrl.abort();
  };
  const report = (f: ApiFailure) => {
    if (done) return;
    finish();
    h.onError?.(f);
  };
  const alive = () => {
    markHealthy();
    clearTimeout(stall);
    stall = setTimeout(
      () => report(fail("stalled", "The research stream went quiet for too long.")),
      STALL_MS,
    );
  };
  const lost = () =>
    report(
      isOffline() ? fail("offline", "You're offline.") : fail("dropped", "The connection to the research engine dropped."),
    );

  const dispatch = ({ event, data }: SseMessage) => {
    if (done) return;
    if (event === "start") {
      alive();
      h.onStart?.(parse(data));
    } else if (isNode(event)) {
      alive();
      h.onNode?.(event, parse(data));
    } else if (event === "review_required") {
      finish();
      h.onReviewRequired?.(parse(data) as unknown as ReviewRequired);
    } else if (event === "final") {
      finish();
      h.onFinal?.(parse(data) as unknown as FinalPayload);
    } else if (event === "error") {
      // In-band failure, e.g. input validation, which the stream endpoints still
      // answer as HTTP 200 with one `error` event carrying {error, code}.
      const d = parse(data);
      const message = typeof d.error === "string" && d.error ? d.error : "The research run reported an error.";
      report(fail("in_band", message, { code: typeof d.code === "string" ? d.code : undefined }));
    } else {
      alive(); // an event we don't render still proves the link is up
    }
  };

  alive();
  void (async () => {
    let res: Response;
    try {
      res = await authFetch(path, {
        headers: { Accept: "text/event-stream" },
        cache: "no-store",
        signal: ctrl.signal,
      });
    } catch {
      if (!done)
        report(isOffline() ? fail("offline", "You're offline.") : fail("unreachable", "The research engine didn't respond."));
      return;
    }
    if (done) return;

    if (!res.ok) {
      report(failureFromResponse(res.status, await readJson(res), res.headers, "research"));
      return;
    }
    if (!res.body || !(res.headers.get("content-type") ?? "").includes("text/event-stream")) {
      // A 200 that isn't a stream: a degraded backend answering `{error}` JSON, or a
      // proxy page. Say what we can.
      const b = (await readJson(res)) as { error?: unknown; detail?: unknown; code?: unknown } | null;
      const message = typeof b?.error === "string" ? b.error : typeof b?.detail === "string" ? b.detail : null;
      report(
        message
          ? fail("in_band", message, { code: typeof b?.code === "string" ? b.code : undefined })
          : fail("server", "The research engine refused the request.", { status: res.status }),
      );
      return;
    }

    alive();
    const parser = createSseParser(dispatch, () => !done && alive());
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    try {
      for (;;) {
        const { value, done: eof } = await reader.read();
        if (eof || done) break;
        parser.push(decoder.decode(value, { stream: true }));
      }
      if (!done) parser.push(decoder.decode());
    } catch {
      // A terminal event or a cancel aborts the read on purpose; anything else is a cut.
      if (!done) lost();
      return;
    }
    parser.end();
    // The server closed the stream without a terminal event.
    if (!done) lost();
  })();

  return () => {
    done = true;
    clearTimeout(stall);
    ctrl.abort();
  };
}

/** A run id that works outside secure contexts too (randomUUID needs https/localhost). */
export function newThreadId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/** Start a run. With `review: true` the backend pauses with `review_required`. */
export function startResearch(
  query: string,
  opts: { review?: boolean; threadId?: string },
  h: StreamHandlers,
): () => void {
  const params = new URLSearchParams({
    q: query,
    thread_id: opts.threadId ?? newThreadId(),
    review: opts.review === false ? "0" : "1",
  });
  return openStream(`/research/stream?${params}`, h);
}

/** Resume a paused run: approve, request a revision (feedback required), or reject
 *  (feedback optional, used as the reason). `section` aims the feedback at one part
 *  of the report. */
export function resumeResearch(
  threadId: string,
  action: ReviewDecision,
  opts: { feedback?: string; section?: ReviewSectionKey | null },
  h: StreamHandlers,
): () => void {
  const params = new URLSearchParams({ thread_id: threadId, action });
  const feedback = opts.feedback?.trim() ?? "";
  if (action !== "approve" && feedback) params.set("feedback", feedback);
  if (action !== "approve" && opts.section) params.set("section", opts.section);
  return openStream(`/research/resume?${params}`, h);
}

// ---------------------------------------------------------------------------
// JSON requests
// ---------------------------------------------------------------------------

export type Result<T> = { ok: true; data: T } | { ok: false; failure: ApiFailure };

/** fetch + JSON with a time budget and classified failures. Authenticated by default
 *  (bearer token, refresh-and-retry on 401); `auth: false` for public endpoints. A body
 *  of `{error}` is an in-band failure even on HTTP 200 (the backend degrades that way
 *  when unconfigured). */
export async function requestJson<T>(
  path: string,
  init: RequestInit & { timeoutMs?: number; auth?: boolean } = {},
): Promise<Result<T>> {
  if (isOffline()) return { ok: false, failure: fail("offline", "You're offline.") };
  const { timeoutMs = 20_000, signal, auth = true, ...rest } = init;
  const ctrl = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    ctrl.abort();
  }, timeoutMs);
  const onAbort = () => ctrl.abort();
  signal?.addEventListener("abort", onAbort);
  try {
    const req: RequestInit = { cache: "no-store", ...rest, signal: ctrl.signal };
    const r = auth ? await authFetch(path, req) : await fetch(`${API}${path}`, req);
    markHealthy();
    const body = await readJson(r);
    if (!r.ok) return { ok: false, failure: failureFromResponse(r.status, body, r.headers) };
    const err =
      body && typeof body === "object" && "error" in body && typeof (body as { error: unknown }).error === "string"
        ? (body as { error: string }).error
        : null;
    if (err) return { ok: false, failure: fail("in_band", err, { status: r.status }) };
    return { ok: true, data: body as T };
  } catch {
    if (signal?.aborted) return { ok: false, failure: fail("aborted", "Cancelled.") };
    if (timedOut) return { ok: false, failure: fail("timeout", "The request took too long.") };
    if (isOffline()) return { ok: false, failure: fail("offline", "You're offline.") };
    return { ok: false, failure: fail("unreachable", "The research engine didn't respond.") };
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }
}

/** The signed-in user and their plan (quota), for the guest banner. */
export function getMe(signal?: AbortSignal) {
  return requestJson<Me>("/auth/me", { signal });
}

// ---------------------------------------------------------------------------
// LLM Ops: the self-improvement loop (/llmops/*)
// ---------------------------------------------------------------------------

export type PolicyComponent = {
  name: string;
  label: string;
  version: number;
  lessons: string[];
  exemplars: number;
  top_k: number;
  updated_at: string;
};

export type RunQuality = "good" | "ok" | "poor";
export type RunReview = "approved" | "rejected" | "revised" | "none";

export type RecentRun = {
  id: string;
  created_at: string;
  query: string;
  target: string;
  overall: number | null;
  quality: RunQuality | null;
  review: RunReview;
};

export type RunStats = {
  total: number;
  reviewed: number;
  approved: number;
  rejected: number;
  revision_requests: number;
  mean_overall: number | null;
  /** Every run score's average with a plain-English reading (llmops/metrics.py). */
  metrics: RunMetric[];
  recent: RecentRun[];
};

export type RunMetric = {
  key: string;
  name: string;
  question: string;
  mean: number | null;
  rating: "Good" | "OK" | "Weak" | "No data" | string;
  meaning: string;
};

export type FailurePattern = { component: string; kind: string; count: number; example: string };

export type Lever = "lesson" | "exemplars" | "retrieval";

export type Trial = { query: string; baseline: number; candidate: number; delta: number };

export type Experiment = {
  id: string;
  created_at: string;
  component: string;
  lever: Lever;
  hypothesis: string;
  /** The proposal. `lesson` carries the exact text when the lever is a written lesson. */
  change: { summary: string; before: unknown; after: unknown; lesson?: string };
  trials: Trial[];
  mean_delta: number;
  /** "awaiting_approval" when a change passed replay but needs a human sign-off. */
  status?: "awaiting_approval" | "released" | "rejected" | string;
  decision: "released" | "rejected" | "awaiting_approval" | string;
  reason: string;
  version_before: number;
  version_after: number | null;
};

export type LlmOpsOverview = {
  components: PolicyComponent[];
  runs: RunStats;
  issues: FailurePattern[];
  experiments: Experiment[];
};

export type ImproveResponse = { experiment: Experiment | null; message: string };
export type RollbackResponse = { component: string; version: number };

export type PolicyVersion = { version: number; created_at: string; notes: string; policy: unknown };
export type ComponentHistory = { name: string; active_version: number; versions: PolicyVersion[] };

const arr = <T>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);
const num = (v: unknown, d = 0): number => (typeof v === "number" && Number.isFinite(v) ? v : d);

/** Fill in anything a partial or older backend leaves out, so the page never crashes
 *  on a missing list. */
function normalizeOverview(raw: Partial<LlmOpsOverview> | null): LlmOpsOverview {
  const runs: Partial<RunStats> = raw?.runs ?? {};
  return {
    components: arr<PolicyComponent>(raw?.components).map((c) => ({
      ...c,
      lessons: arr<string>(c?.lessons),
      version: num(c?.version, 1),
      exemplars: num(c?.exemplars),
      top_k: num(c?.top_k),
    })),
    runs: {
      total: num(runs.total),
      reviewed: num(runs.reviewed),
      approved: num(runs.approved),
      rejected: num(runs.rejected),
      revision_requests: num(runs.revision_requests),
      mean_overall: typeof runs.mean_overall === "number" ? runs.mean_overall : null,
      metrics: arr<RunMetric>(runs.metrics),
      recent: arr<RecentRun>(runs.recent),
    },
    issues: arr<FailurePattern>(raw?.issues),
    experiments: arr<Experiment>(raw?.experiments).map(normalizeExperiment),
  };
}

function normalizeExperiment(e: Experiment): Experiment {
  return {
    ...e,
    change: e?.change ?? { summary: "", before: null, after: null },
    trials: arr<Trial>(e?.trials),
    mean_delta: num(e?.mean_delta),
  };
}

export async function getLlmOpsOverview(signal?: AbortSignal): Promise<Result<LlmOpsOverview>> {
  const r = await requestJson<Partial<LlmOpsOverview>>("/llmops/overview", { signal, timeoutMs: 30_000 });
  return r.ok ? { ok: true, data: normalizeOverview(r.data) } : r;
}

/** Runs a full paired experiment server-side: 30-120 s is normal. */
export async function runImprovementExperiment(signal?: AbortSignal): Promise<Result<ImproveResponse>> {
  const r = await requestJson<ImproveResponse>("/llmops/improve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
    signal,
    timeoutMs: 240_000,
  });
  if (!r.ok) return r;
  const exp = r.data?.experiment;
  return {
    ok: true,
    data: { message: r.data?.message ?? "", experiment: exp && typeof exp === "object" ? normalizeExperiment(exp) : null },
  };
}

export function rollbackComponent(component: string) {
  return requestJson<RollbackResponse>("/llmops/rollback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ component }),
    timeoutMs: 30_000,
  });
}

export const isPending = (e: Pick<Experiment, "status" | "decision">) =>
  e.status === "awaiting_approval" || e.decision === "awaiting_approval";

/** The experiment log with live status (incl. changes awaiting approval). */
export async function getExperiments(signal?: AbortSignal): Promise<Result<Experiment[]>> {
  const r = await requestJson<unknown>("/llmops/experiments", { signal, timeoutMs: 30_000 });
  if (!r.ok) return r;
  const raw = Array.isArray(r.data) ? r.data : (r.data as { experiments?: unknown } | null)?.experiments;
  return { ok: true, data: arr<Experiment>(raw).map(normalizeExperiment) };
}

export type ApproveResponse = { component: string; version: number };

/** Admin: put an approved candidate live (as a new policy version). */
export function approveExperiment(id: string) {
  return requestJson<ApproveResponse>(`/llmops/experiments/${encodeURIComponent(id)}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
    timeoutMs: 30_000,
  });
}

/** Admin: discard a candidate; the active policy stays. */
export function rejectExperiment(id: string) {
  return requestJson<{ status: string }>(`/llmops/experiments/${encodeURIComponent(id)}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
    timeoutMs: 30_000,
  });
}

export function getComponentHistory(name: string, signal?: AbortSignal) {
  return requestJson<ComponentHistory>(`/llmops/components/${encodeURIComponent(name)}`, { signal });
}

// ---------------------------------------------------------------------------
// Admin: audit log (/admin/audit, admin only)
// ---------------------------------------------------------------------------

export type AuditEvent = {
  /** ISO timestamp (or epoch seconds/ms from an older backend). */
  at: string | number;
  event: string;
  user_id: string | null;
  ip: string | null;
  request_id: string | null;
  detail: unknown;
};

export async function getAuditLog(
  opts: { prefix?: string; limit?: number; signal?: AbortSignal } = {},
): Promise<Result<AuditEvent[]>> {
  const params = new URLSearchParams({ limit: String(opts.limit ?? 200) });
  if (opts.prefix) params.set("event", opts.prefix);
  const r = await requestJson<{ events?: unknown }>(`/admin/audit?${params}`, { signal: opts.signal });
  return r.ok ? { ok: true, data: arr<AuditEvent>(r.data?.events) } : r;
}
