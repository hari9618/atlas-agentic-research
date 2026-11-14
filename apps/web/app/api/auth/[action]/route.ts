// Auth BFF: POST /api/auth/{login|register|guest|refresh|logout|password}.
//
// The web (Vercel) and the API (Render) are different sites, so a cookie set by the API
// would be third-party and Safari would drop it. These handlers keep the refresh token
// in a first-party httpOnly cookie on the web origin and hand the browser only the
// short-lived access token, which it sends to the API as a bearer header.

import { type NextRequest, NextResponse } from "next/server";
import { AUTH_ACTIONS, type AuthAction, SESSION_COOKIE } from "@/lib/auth-common";
import {
  bearerOf,
  callBackend,
  clearSessionCookie,
  guard,
  json,
  LOGOUT_TIMEOUT_MS,
  readBody,
  setSessionCookie,
  type Upstream,
} from "./bff";

// The Render free instance can take 30-60 s to boot on the first call after a nap.
export const maxDuration = 60;

const isAction = (a: string): a is AuthAction => (AUTH_ACTIONS as readonly string[]).includes(a);

function pick(body: Record<string, unknown>, keys: string[]): Record<string, unknown> {
  return Object.fromEntries(keys.filter((k) => body[k] !== undefined).map((k) => [k, body[k]]));
}

/** Relay a backend failure as-is (status, detail/code/retry_after, Retry-After), so the
 *  browser can show the backend's own message. */
function relay(up: Upstream, fallback = "The Atlas API returned an error."): Response {
  const body = up.body ?? { detail: fallback, code: "upstream_error" };
  const retry = up.ok && up.retryAfter ? { "Retry-After": up.retryAfter } : undefined;
  return json(body, up.status, retry);
}

/** A successful token response: rotate the cookie, strip the refresh token. */
function issue(req: NextRequest, up: Upstream): Response {
  const b = up.ok ? up.body : null;
  if (!up.ok || up.status < 200 || up.status >= 300) return relay(up);
  if (!b || typeof b.access_token !== "string" || typeof b.refresh_token !== "string" || !b.user) {
    return json({ detail: "The Atlas API sent an unexpected answer.", code: "bad_upstream" }, 502);
  }
  const res = NextResponse.json(
    { access_token: b.access_token, token_type: b.token_type ?? "bearer", expires_in: b.expires_in, user: b.user },
    { status: up.status, headers: { "Cache-Control": "no-store" } },
  );
  setSessionCookie(req, res, b.refresh_token, b.refresh_expires_in);
  return res;
}

async function refresh(req: NextRequest): Promise<Response> {
  const token = req.cookies.get(SESSION_COOKIE)?.value;
  if (!token) return json({ detail: "Not signed in.", code: "no_session" }, 401);

  const up = await callBackend(req, "/auth/refresh", { refresh_token: token });
  if (up.ok && up.status >= 200 && up.status < 300) return issue(req, up);

  const code = up.ok && typeof up.body?.code === "string" ? up.body.code : "";
  // refresh_race: another tab rotated the token a moment ago and the browser already
  // holds the newer cookie. Keep it; the client retries once.
  if (code === "refresh_race") return relay(up);
  // Any other definite rejection (expired, revoked, reused, malformed) ends the
  // session. Upstream outages (5xx, timeouts) and 429 keep the cookie for a retry.
  if (up.ok && (up.status === 401 || up.status === 400 || up.status === 403 || up.status === 422)) {
    const res = NextResponse.json(up.body ?? { detail: "Session expired.", code: "invalid_token" }, {
      status: 401,
      headers: { "Cache-Control": "no-store" },
    });
    clearSessionCookie(req, res);
    return res;
  }
  return relay(up);
}

async function logout(req: NextRequest): Promise<Response> {
  const token = req.cookies.get(SESSION_COOKIE)?.value;
  // Best effort: revoking server-side is good hygiene, but signing out locally must
  // never depend on the API being awake.
  if (token) await callBackend(req, "/auth/logout", { refresh_token: token }, LOGOUT_TIMEOUT_MS);
  const res = new NextResponse(null, { status: 204, headers: { "Cache-Control": "no-store" } });
  clearSessionCookie(req, res);
  return res;
}

/** Change password: authenticated with the browser's access token (forwarded as-is).
 *  The backend revokes every other session and issues a new refresh token, so the
 *  cookie must rotate here, exactly like a login. A 401 (wrong current password, or an
 *  expired access token) leaves the cookie alone: the session itself is still valid. */
async function changePassword(req: NextRequest, body: Record<string, unknown>): Promise<Response> {
  const auth = bearerOf(req);
  if (!auth) return json({ detail: "Sign in to continue.", code: "not_authenticated" }, 401);
  const up = await callBackend(req, "/auth/password", pick(body, ["current_password", "new_password"]), undefined, {
    Authorization: auth,
  });
  return issue(req, up);
}

export async function POST(req: NextRequest, ctx: { params: Promise<{ action: string }> }) {
  const { action } = await ctx.params;
  if (!isAction(action)) return json({ detail: "Not found.", code: "not_found" }, 404);

  const blocked = guard(req);
  if (blocked) return blocked;

  const body = await readBody(req);
  if (body === null) return json({ detail: "Invalid JSON body.", code: "bad_request" }, 400);

  switch (action) {
    case "login":
      return issue(req, await callBackend(req, "/auth/login", pick(body, ["email", "password"])));
    case "register":
      return issue(req, await callBackend(req, "/auth/register", pick(body, ["email", "password", "name"])));
    case "guest":
      return issue(req, await callBackend(req, "/auth/guest", {}));
    case "refresh":
      return refresh(req);
    case "logout":
      return logout(req);
    case "password":
      return changePassword(req, body);
  }
}
