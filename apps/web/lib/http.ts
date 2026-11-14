// Transport basics shared by the API client (lib/api.ts) and the auth client
// (lib/auth.ts): the base URL, the named failure model, and cold-start wake-up.
// Split out so the two clients can depend on it without depending on each other.

export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  | "aborted"
  /** The session is gone and couldn't be refreshed (the client is sent to /login). */
  | "unauthenticated"
  /** Signed in, but this action needs an admin. */
  | "forbidden"
  /** Over a per-user / per-IP quota; `retryAfter` says when it frees up. */
  | "rate_limited"
  /** The server is at capacity for concurrent runs; retrying later is safe. */
  | "busy"
  /** This user already has a run streaming (possibly in another tab). */
  | "run_in_progress";

export type ApiFailure = {
  kind: FailureKind;
  message: string;
  code?: ServerErrorCode | string;
  status?: number;
  /** Seconds until a retry makes sense (rate limits, capacity). */
  retryAfter?: number;
};

export const isOffline = () => typeof navigator !== "undefined" && navigator.onLine === false;

export function fail(kind: FailureKind, message: string, extra: Partial<ApiFailure> = {}): ApiFailure {
  return { kind, message, ...extra };
}

export const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

const str = (v: unknown): string | undefined => (typeof v === "string" && v ? v : undefined);

/** Seconds to wait, from `retry_after` in the body or the Retry-After header (which
 *  may be delta-seconds or an HTTP date). */
export function retryAfterSeconds(body: unknown, headers?: Headers): number | undefined {
  const b = body && typeof body === "object" ? (body as { retry_after?: unknown }).retry_after : undefined;
  if (typeof b === "number" && Number.isFinite(b) && b >= 0) return Math.ceil(b);
  const h = headers?.get("retry-after");
  if (!h) return undefined;
  const n = Number(h);
  if (Number.isFinite(n) && n >= 0) return Math.ceil(n);
  const at = Date.parse(h);
  return Number.isFinite(at) ? Math.max(0, Math.ceil((at - Date.now()) / 1000)) : undefined;
}

/** "3 min" (never "0 min"); vague when the server didn't say. */
export function inMinutes(s: number | undefined): string {
  return s === undefined ? "a few minutes" : `${Math.max(1, Math.ceil(s / 60))} min`;
}

/** "20 s", switching to minutes for long waits. */
export function inSeconds(s: number | undefined): string {
  if (s === undefined) return "a few seconds";
  return s >= 90 ? inMinutes(s) : `${Math.max(1, Math.ceil(s))} s`;
}

/** Classify a non-2xx API response. `research` picks the copy for the run endpoints,
 *  where a 429 means the hourly research quota. */
export function failureFromResponse(
  status: number,
  body: unknown,
  headers?: Headers,
  context: "research" | "request" = "request",
): ApiFailure {
  const b = body && typeof body === "object" ? (body as Record<string, unknown>) : {};
  const detail = str(b.detail) ?? str(b.error);
  const code = str(b.code);
  const retryAfter = retryAfterSeconds(body, headers);
  const extra = { status, code, retryAfter };

  if (status === 401) return fail("unauthenticated", "Your session has ended. Sign in again to continue.", extra);
  if (status === 403) return fail("forbidden", "Admins only. This action is limited to Atlas administrators.", extra);
  if (status === 429)
    return fail(
      "rate_limited",
      context === "research"
        ? `You've hit the hourly research limit. Try again in ${inMinutes(retryAfter)}.`
        : `Too many requests. Try again in ${inMinutes(retryAfter)}.`,
      extra,
    );
  if (status === 503 && code === "busy")
    return fail("busy", `Atlas is at capacity right now. Retrying is safe in ${inSeconds(retryAfter)}.`, extra);
  if (status === 409 && code === "run_in_progress")
    return fail("run_in_progress", "You already have a run in progress.", extra);
  if (status >= 500) return fail("server", detail ?? "The research engine returned an error.", extra);
  return fail("in_band", detail ?? `Request failed (HTTP ${status}).`, extra);
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

export function markHealthy() {
  healthyAt = Date.now();
}

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
