import { type NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE } from "@/lib/auth-common";

/** Optimistic gate for the app pages: no session cookie, no workspace. This only checks
 *  that the cookie exists (cheap, runs on prefetches too); the API verifies the token
 *  on every call and is the real gate. A stale cookie gets through here, then the
 *  client's refresh fails, the BFF clears it and the page sends the user to /login. */
export function proxy(request: NextRequest) {
  if (request.cookies.has(SESSION_COOKIE)) return NextResponse.next();
  const { pathname, search } = request.nextUrl;
  const login = new URL("/login", request.url);
  login.searchParams.set("next", `${pathname}${search}`);
  return NextResponse.redirect(login);
}

// Must be a literal so it can be analysed at build time. The app pages that render
// AppHeader (with its SessionGate) are exactly the ones listed here.
// `:path*` matches the bare path too, so "/research" and "/research/x" are both gated.
export const config = {
  matcher: ["/research/:path*", "/learning/:path*", "/account/:path*", "/admin/:path*"],
};
