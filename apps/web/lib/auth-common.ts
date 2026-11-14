// Auth pieces shared by the proxy, the BFF route handlers and the browser. Pure: no
// browser or server-only APIs, so any runtime can import it.

/** First-party httpOnly cookie holding the refresh token. Only the /api/auth/* route
 *  handlers read or write it; browser JS never sees its value. */
export const SESSION_COOKIE = "atlas_session";

export type Role = "admin" | "user" | "guest";

export type AuthUser = {
  id: string;
  email: string | null;
  name: string | null;
  role: Role | string;
};

/** What the BFF hands the browser after login / register / guest / refresh: the
 *  backend token response minus the refresh token (that stays in the cookie). */
export type BrowserSession = {
  access_token: string;
  token_type?: string;
  expires_in: number;
  user: AuthUser;
};

export type Plan = { research_per_hour: number; concurrent_runs: number };
export type Me = { user: AuthUser; plan: Plan };

export const AUTH_ACTIONS = ["login", "register", "guest", "refresh", "logout", "password"] as const;
export type AuthAction = (typeof AUTH_ACTIONS)[number];

/** Accept `next` only as a same-site path: it must start with a single "/" (so not
 *  "//evil.com" or "/\evil.com", which browsers treat as protocol-relative) and carry
 *  no scheme or control characters. Anything else falls back. */
export function safeNextPath(next: string | null | undefined, fallback = "/research"): string {
  if (!next || typeof next !== "string" || next.length > 2048) return fallback;
  if (!next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return fallback;
  if (/[\u0000-\u001f\u007f]/.test(next)) return fallback;
  try {
    // Resolving against a dummy origin catches anything that escapes to another host.
    const u = new URL(next, "https://atlas.invalid");
    if (u.origin !== "https://atlas.invalid") return fallback;
    if (u.pathname === "/login") return fallback;
    return `${u.pathname}${u.search}${u.hash}`;
  } catch {
    return fallback;
  }
}

export const isGuest = (u: AuthUser | null | undefined) => u?.role === "guest";
export const isAdmin = (u: AuthUser | null | undefined) => u?.role === "admin";
