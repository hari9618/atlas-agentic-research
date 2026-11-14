// Server-side helpers for the auth BFF: the request guard, the backend call, and the
// session cookie. Kept apart from route.ts so the handler reads as the flow it is.

import type { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE } from "@/lib/auth-common";

/** The API as seen from this server. Inside Docker the browser-facing URL
 *  (NEXT_PUBLIC_API_URL, e.g. http://localhost:8000) doesn't resolve, so an internal
 *  URL can override it; on Vercel both are the public Render URL. */
export const BACKEND = (
  process.env.ATLAS_API_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000"
).replace(/\/+$/, "");

/** A cold Render instance needs 30-60 s to boot. The browser wakes it before calling
 *  us (ensureAwake), so this budget is the backstop, kept under maxDuration. */
export const UPSTREAM_TIMEOUT_MS = 50_000;
export const LOGOUT_TIMEOUT_MS = 8_000;
const MAX_BODY_BYTES = 8_192;

export type Upstream =
  | { ok: true; status: number; body: Record<string, unknown> | null; retryAfter: string | null }
  | { ok: false; status: 502 | 504; body: { detail: string; code: string } };

/** CSRF: the cookie is SameSite=Lax, which already keeps it off cross-site POSTs; on
 *  top of that a POST must come from our own origin (when the browser says where it
 *  came from) and carry a JSON content type, which a cross-site form can't send
 *  without a CORS preflight we never answer. */
export function guard(req: NextRequest): Response | null {
  const origin = req.headers.get("origin");
  if (origin !== null) {
    let originHost = "";
    try {
      originHost = new URL(origin).host;
    } catch {
      // "null" (sandboxed iframes, some redirects) or garbage: not our origin.
    }
    const hosts = [req.headers.get("host"), req.headers.get("x-forwarded-host"), req.nextUrl.host].filter(Boolean);
    if (!originHost || !hosts.includes(originHost)) {
      return json({ detail: "Cross-origin request refused.", code: "bad_origin" }, 403);
    }
  }
  if (req.headers.get("sec-fetch-site") === "cross-site") {
    return json({ detail: "Cross-site request refused.", code: "bad_origin" }, 403);
  }
  const type = req.headers.get("content-type") ?? "";
  if (!type.toLowerCase().startsWith("application/json")) {
    return json({ detail: "Expected a JSON body.", code: "unsupported_media_type" }, 415);
  }
  const length = Number(req.headers.get("content-length") ?? 0);
  if (length > MAX_BODY_BYTES) return json({ detail: "Request too large.", code: "too_large" }, 413);
  return null;
}

/** Parse the incoming JSON body, bounded in size. `{}` when empty. */
export async function readBody(req: NextRequest): Promise<Record<string, unknown> | null> {
  const text = await req.text();
  if (text.length > MAX_BODY_BYTES) return null;
  if (!text.trim()) return {};
  try {
    const v = JSON.parse(text);
    return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

/** The caller's IP, so the backend's per-IP limits count the user, not this server.
 *  On Vercel, x-forwarded-for is set by the platform (client-supplied values are
 *  overwritten), and its left-most entry is the client. */
function clientIp(req: NextRequest): string | null {
  const xff = req.headers.get("x-forwarded-for");
  const first = xff?.split(",")[0]?.trim();
  return first || req.headers.get("x-real-ip") || null;
}

export async function callBackend(
  req: NextRequest,
  path: string,
  body: unknown,
  timeoutMs = UPSTREAM_TIMEOUT_MS,
  extraHeaders: Record<string, string> = {},
): Promise<Upstream> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
    ...extraHeaders,
  };
  const ip = clientIp(req);
  if (ip) headers["X-Forwarded-For"] = ip;
  const ua = req.headers.get("user-agent");
  if (ua) headers["User-Agent"] = ua.slice(0, 512);

  try {
    const r = await fetch(`${BACKEND}${path}`, {
      method: "POST",
      headers,
      body: JSON.stringify(body ?? {}),
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(timeoutMs),
    });
    let parsed: Record<string, unknown> | null = null;
    if (r.status !== 204) {
      try {
        const v = await r.json();
        parsed = v && typeof v === "object" ? (v as Record<string, unknown>) : null;
      } catch {
        // A platform error page (HTML) while the instance boots: no JSON to pass on.
      }
    }
    return { ok: true, status: r.status, body: parsed, retryAfter: r.headers.get("retry-after") };
  } catch (e) {
    const timedOut = e instanceof Error && (e.name === "TimeoutError" || e.name === "AbortError");
    return timedOut
      ? { ok: false, status: 504, body: { detail: "The Atlas API took too long to answer.", code: "upstream_timeout" } }
      : { ok: false, status: 502, body: { detail: "The Atlas API couldn't be reached.", code: "upstream_unreachable" } };
  }
}

/** The browser's `Authorization: Bearer <jwt>`, if well-formed. Passed through only for
 *  actions that act on the signed-in account (change password). */
export function bearerOf(req: NextRequest): string | null {
  const h = req.headers.get("authorization");
  return h && /^Bearer [A-Za-z0-9._~+/-]+=*$/.test(h) && h.length <= 4096 ? h : null;
}

export function json(body: unknown, status = 200, extra: Record<string, string> = {}): Response {
  return Response.json(body, { status, headers: { "Cache-Control": "no-store", ...extra } });
}

/** Secure everywhere except plain-http loopback (local `next dev` / `next start`),
 *  where a Secure cookie would be dropped by some browsers. */
function secureFor(req: NextRequest): boolean {
  const proto = req.headers.get("x-forwarded-proto")?.split(",")[0]?.trim() || req.nextUrl.protocol.replace(":", "");
  if (proto === "https") return true;
  const host = req.nextUrl.hostname;
  const loopback = host === "localhost" || host === "127.0.0.1" || host === "[::1]" || host === "::1";
  return process.env.NODE_ENV === "production" && !loopback;
}

export function setSessionCookie(req: NextRequest, res: NextResponse, token: string, maxAge: unknown) {
  res.cookies.set({
    name: SESSION_COOKIE,
    value: token,
    httpOnly: true,
    secure: secureFor(req),
    sameSite: "lax",
    path: "/",
    // Without a lifetime from the backend, fall back to a browser-session cookie.
    ...(typeof maxAge === "number" && Number.isFinite(maxAge) && maxAge > 0 ? { maxAge: Math.floor(maxAge) } : {}),
  });
}

export function clearSessionCookie(req: NextRequest, res: NextResponse) {
  res.cookies.set({
    name: SESSION_COOKIE,
    value: "",
    httpOnly: true,
    secure: secureFor(req),
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
}
