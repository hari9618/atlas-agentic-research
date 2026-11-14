// Browser-side session. The refresh token never reaches JS: it lives in the httpOnly
// `atlas_session` cookie that only the /api/auth/* route handlers touch. What JS holds
// is the short-lived access token, in memory only (never localStorage, so an XSS can't
// lift a long-lived credential from storage), sent to the API as a bearer header.
//
// React-free on purpose: lib/api.ts imports this and is itself imported (for types and
// helpers) from server components. The hook lives in lib/use-session.ts.

import type { AuthAction, AuthUser, BrowserSession } from "./auth-common";
import { API, ensureAwake, inMinutes, isOffline, retryAfterSeconds, sleep } from "./http";

type Session = { accessToken: string; expiresAt: number; user: AuthUser };

export type SessionStatus = "loading" | "authenticated" | "anonymous";
export type SessionSnapshot = { status: SessionStatus; user: AuthUser | null };

/** Refresh this long before the access token expires, so a request never races expiry. */
const REFRESH_MARGIN_MS = 60_000;
/** The BFF waits up to 60 s on a cold API; give it a little more. */
const BFF_TIMEOUT_MS = 65_000;

export const LOADING_SNAPSHOT: SessionSnapshot = { status: "loading", user: null };

let session: Session | null = null;
/** Set once we're navigating away (to /login or after sign-out), so nothing else does. */
let redirecting = false;
let snapshot: SessionSnapshot = LOADING_SNAPSHOT;
const listeners = new Set<() => void>();

function emit(next: SessionSnapshot) {
  snapshot = next;
  listeners.forEach((l) => l());
}

function adopt(s: BrowserSession) {
  const ttl = typeof s.expires_in === "number" && s.expires_in > 0 ? s.expires_in : 900;
  session = { accessToken: s.access_token, expiresAt: Date.now() + ttl * 1000, user: s.user };
  emit({ status: "authenticated", user: s.user });
}

function drop() {
  session = null;
  if (snapshot.status !== "anonymous") emit({ status: "anonymous", user: null });
}

const isSession = (v: unknown): v is BrowserSession =>
  !!v && typeof v === "object" && typeof (v as BrowserSession).access_token === "string" && !!(v as BrowserSession).user;

// ---------------------------------------------------------------------------
// Cross-tab: signing out in one tab signs out the others (they hold their own
// in-memory token, which would otherwise keep working until it expires).
// ---------------------------------------------------------------------------

let channel: BroadcastChannel | null | undefined;

function getChannel(): BroadcastChannel | null {
  if (channel !== undefined) return channel;
  channel = typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel("atlas-auth");
  channel?.addEventListener("message", (e: MessageEvent) => {
    if (e.data === "signout") drop();
  });
  return channel;
}

// ---------------------------------------------------------------------------
// Subscriptions (for lib/use-session.ts)
// ---------------------------------------------------------------------------

let bootstrapped = false;

export function getSnapshot(): SessionSnapshot {
  return snapshot;
}

export function getUser(): AuthUser | null {
  return session?.user ?? null;
}

/** Subscribe to session changes. The first subscriber kicks off a silent refresh, which
 *  turns an existing cookie into a session (or settles on "anonymous"). */
export function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  getChannel();
  if (!bootstrapped) {
    bootstrapped = true;
    if (!session) void refreshShared();
  }
  return () => {
    listeners.delete(cb);
  };
}

// ---------------------------------------------------------------------------
// BFF calls
// ---------------------------------------------------------------------------

export type AuthError = {
  status: number;
  code?: string;
  message: string;
  /** Per-field messages keyed by request field name (from FastAPI validation errors,
   *  weak_password, invalid_credentials on a password change). */
  fields?: Partial<Record<string, string>>;
  retryAfter?: number;
};

export type AuthResult = { ok: true; user: AuthUser } | { ok: false; error: AuthError };

type BffResponse = { status: number; data: unknown; headers: Headers };

async function postBff(
  action: AuthAction,
  body: unknown = {},
  timeoutMs = BFF_TIMEOUT_MS,
  bearer?: string,
): Promise<BffResponse> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (bearer) headers.Authorization = `Bearer ${bearer}`;
  const r = await fetch(`/api/auth/${action}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    credentials: "same-origin",
    cache: "no-store",
    signal: AbortSignal.timeout(timeoutMs),
  });
  let data: unknown = null;
  try {
    data = await r.json();
  } catch {
    data = null;
  }
  return { status: r.status, data, headers: r.headers };
}

const FIELD_NAMES = new Set(["email", "password", "name", "current_password", "new_password"]);

function networkError(): AuthError {
  return isOffline()
    ? { status: 0, code: "offline", message: "You're offline. Reconnect and try again." }
    : { status: 0, code: "network", message: "Couldn't reach Atlas. Check your connection and try again." };
}

/** Turn a BFF/backend error body into something a form can show. */
function toAuthError({ status, data, headers }: BffResponse): AuthError {
  const b = data && typeof data === "object" ? (data as Record<string, unknown>) : {};
  const code = typeof b.code === "string" ? b.code : undefined;
  const detail = typeof b.detail === "string" && b.detail ? b.detail : undefined;
  const retryAfter = retryAfterSeconds(data, headers);
  const base = { status, code, retryAfter };

  // FastAPI validation: {detail: [{loc: ["body", "email"], msg}]}.
  if (Array.isArray(b.detail)) {
    const fields: AuthError["fields"] = {};
    for (const item of b.detail as { loc?: unknown[]; msg?: unknown }[]) {
      const field = Array.isArray(item?.loc) ? item.loc[item.loc.length - 1] : undefined;
      if (typeof field === "string" && FIELD_NAMES.has(field) && typeof item.msg === "string") {
        fields[field] ??= item.msg.replace(/^Value error, /, "");
      }
    }
    return { ...base, fields, message: "Check the highlighted fields." };
  }
  if (code === "weak_password")
    return { ...base, fields: { password: detail ?? "Choose a stronger password." }, message: detail ?? "Choose a stronger password." };
  if (code === "invalid_credentials") return { ...base, message: detail ?? "That email and password don't match." };
  if (code === "email_taken") return { ...base, message: detail ?? "An account with this email already exists." };
  if (status === 429) return { ...base, message: `Too many attempts. Try again in ${inMinutes(retryAfter)}.` };
  if (status === 502 || status === 504)
    return { ...base, message: "Atlas's server didn't answer in time. It may still be waking up; try again in a moment." };
  if (code === "bad_origin") return { ...base, message: "This request was blocked for your security. Reload the page and try again." };
  return { ...base, message: detail ?? `Something went wrong (HTTP ${status}). Try again.` };
}

/** Wake a sleeping API from the browser first (cheap polling, with a "slow" signal for
 *  the UI), then let the BFF exchange credentials for a session. */
async function establish(action: AuthAction, body: unknown, onSlow?: () => void): Promise<AuthResult> {
  const wake = await ensureAwake({ onSlow });
  if (!wake.ok && wake.failure.kind === "offline") return { ok: false, error: networkError() };
  // Let a silent refresh that's still in flight land first: if it carried a stale
  // cookie, its "clear the cookie" response must not arrive after (and wipe) the fresh
  // one this sign-in is about to set.
  if (refreshing) await refreshing;
  // A failed wake-up still tries the BFF: its own error is more specific.
  try {
    const r = await postBff(action, body);
    if (r.status >= 200 && r.status < 300 && isSession(r.data)) {
      adopt(r.data);
      bootstrapped = true;
      return { ok: true, user: r.data.user };
    }
    return { ok: false, error: toAuthError(r) };
  } catch {
    return { ok: false, error: networkError() };
  }
}

export const signIn = (email: string, password: string, onSlow?: () => void) =>
  establish("login", { email, password }, onSlow);

export const signUp = (email: string, password: string, name: string | undefined, onSlow?: () => void) =>
  establish("register", name ? { email, password, name } : { email, password }, onSlow);

export const continueAsGuest = (onSlow?: () => void) => establish("guest", {}, onSlow);

/** Revoke server-side (best effort), clear everywhere, and leave the app. */
export async function signOut(to = "/"): Promise<void> {
  try {
    // The BFF clears the cookie even when the API is down, or has already revoked the
    // token (as after logout-all or account deletion).
    await postBff("logout", {}, 10_000);
  } catch {
    // The BFF itself is unreachable: nothing more to do from here.
  }
  // We're navigating away ourselves: don't let a session gate bounce to /login first.
  redirecting = true;
  drop();
  getChannel()?.postMessage("signout");
  window.location.assign(to);
}

// ---------------------------------------------------------------------------
// Access tokens
// ---------------------------------------------------------------------------

export type TokenResult =
  | { ok: true; token: string }
  | { ok: false; reason: "signed_out" }
  | { ok: false; reason: "unavailable"; error: AuthError };

let refreshing: Promise<TokenResult> | null = null;

/** Single flight: every caller during a refresh shares it. Rotation makes this matter:
 *  two parallel refreshes would race each other's one-time refresh token. */
function refreshShared(): Promise<TokenResult> {
  return (refreshing ??= runRefresh().finally(() => {
    refreshing = null;
  }));
}

async function runRefresh(): Promise<TokenResult> {
  let raced = false;
  let woke = false;
  for (;;) {
    let r: BffResponse;
    try {
      r = await postBff("refresh");
    } catch {
      return { ok: false, reason: "unavailable", error: networkError() };
    }
    if (r.status >= 200 && r.status < 300 && isSession(r.data)) {
      adopt(r.data);
      return { ok: true, token: r.data.access_token };
    }
    const code = r.data && typeof r.data === "object" ? (r.data as { code?: unknown }).code : undefined;
    // Another tab rotated the token a moment ago; by now the browser holds the newer
    // cookie, so one more try (after a beat) goes through.
    if (r.status === 401 && code === "refresh_race" && !raced) {
      raced = true;
      await sleep(300 + Math.random() * 300);
      continue;
    }
    if (r.status === 401 && code !== "refresh_race") {
      drop();
      return { ok: false, reason: "signed_out" };
    }
    // The API was too slow (cold start): wake it from here, then try once more.
    if ((r.status === 502 || r.status === 504) && !woke) {
      woke = true;
      if ((await ensureAwake()).ok) continue;
    }
    return { ok: false, reason: "unavailable", error: toAuthError(r) };
  }
}

/** A usable access token, refreshing when missing or about to expire. `rejected` is a
 *  token the API just refused: skip it even if it looks fresh (unless another call has
 *  already replaced it). */
export async function getAccessToken(opts: { rejected?: string } = {}): Promise<TokenResult> {
  if (session && session.accessToken !== opts.rejected && session.expiresAt - Date.now() > REFRESH_MARGIN_MS) {
    return { ok: true, token: session.accessToken };
  }
  return refreshShared();
}

/** Send the user to sign in, remembering where they were. */
export function redirectToLogin() {
  if (typeof window === "undefined" || redirecting) return;
  const here = `${window.location.pathname}${window.location.search}`;
  if (window.location.pathname === "/login") return;
  redirecting = true;
  window.location.assign(`/login?next=${encodeURIComponent(here)}`);
}

/** Thrown when no token could be obtained for a reason other than being signed out
 *  (BFF unreachable, API cold). Shaped like fetch's own network failure, so callers'
 *  existing catch blocks classify it as "unreachable". */
export class AuthUnavailableError extends TypeError {
  constructor(message: string) {
    super(message);
    this.name = "AuthUnavailableError";
  }
}

function withBearer(init: RequestInit, token: string): RequestInit {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  // Direct calls to the API never carry cookies: the session cookie is first-party to
  // the web origin and the API doesn't use cookies at all.
  return { ...init, headers, credentials: "omit" };
}

const TOKEN_CODES = new Set(["token_expired", "invalid_token", "not_authenticated"]);

/** A 401 about the token itself, as opposed to one about a credential in the body
 *  (`invalid_credentials` for a wrong password on delete-account), which must reach the
 *  caller instead of ending the session. */
async function isTokenRejection(res: Response): Promise<boolean> {
  if (res.status !== 401) return false;
  try {
    const code = ((await res.clone().json()) as { code?: unknown })?.code;
    return typeof code !== "string" || TOKEN_CODES.has(code);
  } catch {
    return true;
  }
}

const unauthenticated = () =>
  new Response(JSON.stringify({ detail: "Sign in to continue.", code: "not_authenticated" }), {
    status: 401,
    headers: { "Content-Type": "application/json" },
  });

/** fetch() against the API with the bearer token. A 401 (typically token_expired)
 *  triggers one refresh and one retry; if that still fails the session is over and the
 *  user is sent to /login. Request bodies must be replayable (string / FormData). */
export async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const url = /^https?:\/\//.test(path) ? path : `${API}${path}`;
  const first = await getAccessToken();
  if (!first.ok) {
    if (first.reason === "signed_out") {
      redirectToLogin();
      return unauthenticated();
    }
    throw new AuthUnavailableError(first.error.message);
  }

  const res = await fetch(url, withBearer(init, first.token));
  if (!(await isTokenRejection(res))) return res;

  const again = await getAccessToken({ rejected: first.token });
  if (again.ok) {
    const retried = await fetch(url, withBearer(init, again.token));
    if (!(await isTokenRejection(retried))) return retried;
    drop();
    redirectToLogin();
    return retried;
  }
  if (again.reason === "signed_out") {
    redirectToLogin();
    return res;
  }
  throw new AuthUnavailableError(again.error.message);
}

// ---------------------------------------------------------------------------
// Account management
// ---------------------------------------------------------------------------

const SIGN_IN_AGAIN: AuthError = { status: 401, code: "not_authenticated", message: "Sign in to continue." };

/** Change the password. Goes through the BFF (with the access token) because the
 *  backend answers with a new refresh token, which only the BFF may put in the cookie.
 *  Every other session of the account is revoked server-side. */
export async function changePassword(currentPassword: string, newPassword: string): Promise<AuthResult> {
  const body = { current_password: currentPassword, new_password: newPassword };
  let rejected: string | undefined;
  for (let attempt = 0; attempt < 2; attempt++) {
    const t = await getAccessToken({ rejected });
    if (!t.ok) {
      if (t.reason === "signed_out") {
        redirectToLogin();
        return { ok: false, error: SIGN_IN_AGAIN };
      }
      return { ok: false, error: t.error };
    }
    let r: BffResponse;
    try {
      r = await postBff("password", body, BFF_TIMEOUT_MS, t.token);
    } catch {
      return { ok: false, error: networkError() };
    }
    if (r.status >= 200 && r.status < 300 && isSession(r.data)) {
      adopt(r.data);
      return { ok: true, user: r.data.user };
    }
    const code = r.data && typeof r.data === "object" ? (r.data as { code?: unknown }).code : undefined;
    // An expired access token: refresh once and retry. A wrong current password is
    // also a 401, but that's the form's business, not the session's.
    if (r.status === 401 && typeof code === "string" && TOKEN_CODES.has(code) && attempt === 0) {
      rejected = t.token;
      continue;
    }
    const error = toAuthError(r);
    if (code === "invalid_credentials") {
      error.message = "That isn't your current password.";
      error.fields = { current_password: error.message };
    }
    if (code === "weak_password") error.fields = { new_password: error.message };
    return { ok: false, error };
  }
  redirectToLogin();
  return { ok: false, error: SIGN_IN_AGAIN };
}

export type AccountResult = { ok: true } | { ok: false; error: AuthError };

async function accountCall(path: string, init: RequestInit): Promise<AccountResult> {
  let res: Response;
  try {
    res = await authFetch(path, { ...init, cache: "no-store" });
  } catch {
    return { ok: false, error: networkError() };
  }
  if (res.ok) return { ok: true };
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  const error = toAuthError({ status: res.status, data, headers: res.headers });
  if (error.code === "invalid_credentials") error.message = "That password isn't right.";
  if (res.status === 403) error.message = "You don't have permission to do that.";
  return { ok: false, error };
}

/** Revoke every refresh token of the account (all devices), then sign this browser out
 *  too: clear memory, have the BFF clear the cookie, and go to /login. */
export async function signOutEverywhere(): Promise<AccountResult> {
  const r = await accountCall("/auth/logout-all", { method: "POST" });
  if (r.ok) await signOut("/login");
  return r;
}

/** Delete the account. Password accounts confirm with their password; guests send {}. */
export async function deleteAccount(password?: string): Promise<AccountResult> {
  const r = await accountCall("/auth/me", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(password ? { password } : {}),
  });
  if (r.ok) await signOut("/");
  return r;
}
