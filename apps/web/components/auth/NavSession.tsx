"use client";

import Link from "next/link";
import { isGuest } from "@/lib/auth-common";
import { useSession } from "@/lib/use-session";
import { Icon } from "@/components/ui/Icon";

const cta =
  "inline-flex min-h-10 items-center gap-2 rounded-lg bg-accent-400 px-4 text-sm font-medium text-ink-950 transition-colors hover:bg-accent-300";

/** The landing nav's call to action, aware of the session. The server render (and the
 *  first client render) is the anonymous CTA, so the static page hydrates cleanly; it
 *  becomes "Open app" once a silent refresh finds a session. */
export function NavSession() {
  const { status, user } = useSession();

  if (status === "authenticated" && user) {
    const who = isGuest(user) ? "G" : (user.name || user.email || "A").trim().charAt(0).toUpperCase();
    return (
      <Link href="/research" className={`${cta} pl-2`} aria-label="Open the Atlas app">
        <span
          aria-hidden
          className="flex h-7 w-7 items-center justify-center rounded-full bg-ink-950 text-xs font-semibold text-accent-300"
        >
          {who}
        </span>
        Open app
        <Icon name="arrowRight" />
      </Link>
    );
  }

  return (
    <>
      {status === "anonymous" && (
        <Link
          href="/login"
          className="link-rule hidden py-1 text-sm font-medium text-slate-800 sm:inline-block"
        >
          Sign in
        </Link>
      )}
      <Link href="/research" className={cta}>
        <span className="hidden sm:inline">Research a company</span>
        <span className="sm:hidden">Start</span>
        <Icon name="arrowRight" />
      </Link>
    </>
  );
}
