// Typed client for the Atlas backend. Contract: docs/investor-platform-design.md §1 + §4,
// plus the review (reject / section) and LLM-Ops (/llmops/*) additions.

export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  sentiment?: { overall?: OverallSentiment | string; summary?: string };
  risks?: Risk[];
  bull_case?: string[];
  bear_case?: string[];
  outlook?: { summary?: string; watch_items?: string[] };
  bottom_line?: string;
  uncertainties?: string[];
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
// Failures. Every way a request can go wrong is named, so the UI can say what
// happened and offer the right recovery instead of a generic "something broke".
// ---------------------------------------------------------------------------

/** Codes the backend sends in an in-band SSE `error` event. */
export type ServerErrorCode = "bad_request" | "not_configured" | "run_failed" | "not_paused" | "unknown_thread";

export type FailureKind =
  /** The browser reports no network connection. */
  | "offline"
  /** No response at all: the server is down, asleep past our budget, or blocked (CORS/DNS). */
  | "unreachable"
  /** The server answered with an HTTP error (or a non-SSE body the stream can't read). */
  | "server"
  /** A stream that was open closed before its terminal event. */
  | "dropped"
  /** A stream stayed open but went silent far longer than any agent step takes. */
  | "stalled"
  /** The server reported a problem in-band (SSE `error` event, or `{error}` JSON). */
  | "in_band"
  /** A request took longer than its time budget. */
  | "timeout"
  /** Cancelled by the caller. */
  | "aborted";

export type ApiFailure = {
  kind: FailureKind;
  message: string;
  code?: ServerErrorCode | string;
  status?: number;
};

const isOffline = () => typeof navigator !== "undefined" && navigator.onLine === false;

function fail(kind: FailureKind, message: string, extra: Partial<ApiFailure> = {}): ApiFailure {
  return { kind, message, ...extra };
}

// ---------------------------------------------------------------------------
// Cold starts. The API runs on a free tier that sleeps when idle; the first request
// after a nap can take ~50 s while the instance boots. We ping /health first (shared
// between callers, cached while warm) so a run never opens a stream into the void.
// ---------------------------------------------------------------------------

const WARM_FOR_MS = 90_000;
const WAKE_BUDGET_MS = 80_000;
const ATTEMPT_TIMEOUT_MS = 25_000;
const SLOW_AFTER_MS = 1_200;

let healthyAt = 0;
let inflight: Promise<WakeResult> | null = null;

export type WakeResult = { ok: true } | { ok: false; failure: ApiFailure };

/** True if the API answered recently, so a run can start without a health check. */
export function isWarm(): boolean {
  return Date.now() - healthyAt < WARM_FOR_MS;
}

function markHealthy() {
  healthyAt = Date.now();
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function pingUntilAwake(): Promise<WakeResult> {
  const started = Date.now();
  let lastStatus: number | undefined;
  while (Date.now() - started < WAKE_BUDGET_MS) {
    if (isOffline()) return { ok: false, failure: fail("offline", "You're offline.") };
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), ATTEMPT_TIMEOUT_MS);
    try {
      const r = await fetch(`${API}/health`, { cache: "no-store", signal: ctrl.signal });
      // Any non-5xx answer means a live process is serving; 502/503 is the platform's
      // proxy while the instance boots, so keep waiting.
      if (r.status < 500) {
        markHealthy();
        return { ok: true };
      }
      lastStatus = r.status;
    } catch {
      // Network error or attempt timeout: the instance may still be booting.
    } finally {
      clearTimeout(timer);
    }
    await sleep(2_500);
  }
  return {
    ok: false,
    failure: lastStatus
      ? fail("server", "The research engine is responding with errors.", { status: lastStatus })
      : fail("unreachable", "The research engine didn't respond."),
  };
}

/** Resolve once the API is awake. `onSlow` fires if that takes more than a moment
 *  (i.e. a cold start), so the UI can explain the wait instead of looking frozen. */
export function ensureAwake(opts: { onSlow?: () => void; signal?: AbortSignal } = {}): Promise<WakeResult> {
  if (isWarm()) return Promise.resolve({ ok: true });
  if (isOffline()) return Promise.resolve({ ok: false, failure: fail("offline", "You're offline.") });

  const shared = (inflight ??= pingUntilAwake().finally(() => {
    inflight = null;
  }));

  return new Promise<WakeResult>((resolve) => {
    let settled = false;
    const slow = setTimeout(() => !settled && opts.onSlow?.(), SLOW_AFTER_MS);
    const done = (r: WakeResult) => {
      if (settled) return;
      settled = true;
      clearTimeout(slow);
      opts.signal?.removeEventListener("abort", onAbort);
      resolve(r);
    };
    const onAbort = () => done({ ok: false, failure: fail("aborted", "Cancelled.") });
    if (opts.signal?.aborted) return onAbort();
    opts.signal?.addEventListener("abort", onAbort);
    shared.then(done);
  });
}

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

function parse(raw: unknown): Record<string, unknown> {
  if (typeof raw !== "string" || !raw) return {};
  try {
    const v = JSON.parse(raw);
    return v && typeof v === "object" ? (v as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

/** Open an SSE stream and dispatch Atlas events. Returns a cancel fn.
 *
 *  EventSource reconnects on its own after a dropped connection, which here would
 *  re-send the GET and launch a duplicate run (or a duplicate resume). So every
 *  failure closes the source on the spot (close() inside the error handler cancels
 *  the scheduled reconnect) and is reported once, classified. */
function openStream(url: string, h: StreamHandlers): () => void {
  const es = new EventSource(url);
  let done = false;
  let opened = false;
  let stall: ReturnType<typeof setTimeout> | undefined;

  const finish = () => {
    done = true;
    clearTimeout(stall);
    es.close();
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

  alive();
  es.onopen = () => {
    opened = true;
    alive();
  };

  es.addEventListener("start", (e) => {
    if (done) return;
    alive();
    h.onStart?.(parse((e as MessageEvent).data));
  });

  for (const node of NODE_EVENTS) {
    es.addEventListener(node, (e) => {
      if (done) return;
      alive();
      h.onNode?.(node, parse((e as MessageEvent).data));
    });
  }

  es.addEventListener("review_required", (e) => {
    if (done) return;
    finish();
    h.onReviewRequired?.(parse((e as MessageEvent).data) as unknown as ReviewRequired);
  });

  es.addEventListener("final", (e) => {
    if (done) return;
    finish();
    h.onFinal?.(parse((e as MessageEvent).data) as unknown as FinalPayload);
  });

  // `error` is both a server-sent event name (a MessageEvent carrying {error, code})
  // and the connection-failure event (a plain Event). Tell them apart by the data.
  es.addEventListener("error", (e) => {
    if (done) return;
    const raw = (e as MessageEvent).data;
    if (typeof raw === "string" && raw) {
      const d = parse(raw);
      const message = typeof d.error === "string" && d.error ? d.error : "The research run reported an error.";
      const code = typeof d.code === "string" ? d.code : undefined;
      report(fail("in_band", message, { code }));
      return;
    }
    // CLOSED: the browser gave up for good (HTTP error status or a non-SSE response).
    // CONNECTING: it was about to retry, which we refuse (see above).
    const closed = es.readyState === EventSource.CLOSED;
    if (isOffline()) report(fail("offline", "You're offline."));
    else if (opened) report(fail("dropped", "The connection to the research engine dropped."));
    else if (closed) report(fail("server", "The research engine refused the request."));
    else report(fail("unreachable", "The research engine didn't respond."));
  });

  return () => {
    done = true;
    clearTimeout(stall);
    es.close();
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
  return openStream(`${API}/research/stream?${params}`, h);
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
  return openStream(`${API}/research/resume?${params}`, h);
}

// ---------------------------------------------------------------------------
// JSON requests
// ---------------------------------------------------------------------------

export type Result<T> = { ok: true; data: T } | { ok: false; failure: ApiFailure };

/** fetch + JSON with a time budget and classified failures. A body of `{error}` is an
 *  in-band failure even on HTTP 200 (the backend degrades that way when unconfigured). */
export async function requestJson<T>(
  path: string,
  init: RequestInit & { timeoutMs?: number } = {},
): Promise<Result<T>> {
  if (isOffline()) return { ok: false, failure: fail("offline", "You're offline.") };
  const { timeoutMs = 20_000, signal, ...rest } = init;
  const ctrl = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    ctrl.abort();
  }, timeoutMs);
  const onAbort = () => ctrl.abort();
  signal?.addEventListener("abort", onAbort);
  try {
    const r = await fetch(`${API}${path}`, { cache: "no-store", ...rest, signal: ctrl.signal });
    markHealthy();
    let body: unknown = null;
    try {
      body = await r.json();
    } catch {
      body = null;
    }
    const err =
      body && typeof body === "object" && "error" in body && typeof (body as { error: unknown }).error === "string"
        ? (body as { error: string }).error
        : body && typeof body === "object" && "detail" in body && typeof (body as { detail: unknown }).detail === "string"
          ? (body as { detail: string }).detail
          : null;
    if (!r.ok) {
      return {
        ok: false,
        failure: fail(r.status >= 500 ? "server" : "in_band", err ?? `Request failed (HTTP ${r.status}).`, {
          status: r.status,
        }),
      };
    }
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
  recent: RecentRun[];
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
  change: { summary: string; before: unknown; after: unknown };
  trials: Trial[];
  mean_delta: number;
  decision: "released" | "rejected";
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

export function getComponentHistory(name: string, signal?: AbortSignal) {
  return requestJson<ComponentHistory>(`/llmops/components/${encodeURIComponent(name)}`, { signal });
}
