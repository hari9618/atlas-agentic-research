"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { signOut } from "@/lib/auth";
import { type AuthUser, isAdmin, isGuest } from "@/lib/auth-common";
import { useSession } from "@/lib/use-session";
import { Icon } from "@/components/ui/Icon";
import { Spinner } from "@/components/ui/Spinner";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { cx, limeOutline, monoLabel } from "@/components/ui/styles";

function initial(u: AuthUser): string {
  const source = (u.name || u.email || "").trim();
  return source ? source.charAt(0).toUpperCase() : "A";
}

/** Signed-in identity for the ink app header, with sign-out. A disclosure (button +
 *  panel), not an ARIA menu: it holds a couple of plain links and buttons, which Tab
 *  reaches naturally. On phones it also carries the theme switch, which the header
 *  hides there to make room. */
export function UserMenu() {
  const { status, user } = useSession();
  const [open, setOpen] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setOpen(false);
      buttonRef.current?.focus();
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (status !== "authenticated" || !user) {
    return (
      <span aria-label="Loading your account" role="status" className="flex h-9 w-9 items-center justify-center">
        <span aria-hidden className="h-8 w-8 animate-pulse-soft rounded-full bg-white/[0.08]" />
      </span>
    );
  }

  const guest = isGuest(user);
  const label = guest ? "Guest" : user.email || user.name || "Your account";

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={`Account: ${label}`}
        onClick={() => setOpen((v) => !v)}
        className="flex min-h-9 items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] p-0.5 text-sm text-slate-200 transition-colors hover:border-white/25 hover:text-white lg:pr-3 pointer-coarse:min-h-11"
      >
        <span
          aria-hidden
          className={cx(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold",
            guest ? "border border-dashed border-white/30 text-slate-300" : "bg-accent-400 text-ink-950",
          )}
        >
          {guest ? <Icon name="users" className="h-3.5 w-3.5" /> : initial(user)}
        </span>
        <span className="hidden max-w-[11rem] truncate lg:inline">{label}</span>
        <Icon
          name="chevron"
          className={cx("hidden h-3.5 w-3.5 text-slate-400 transition-transform lg:block", open && "rotate-180")}
        />
      </button>

      {open && (
        <div
          id={panelId}
          className="absolute top-full right-0 z-50 mt-2 w-[min(17rem,calc(100vw-2rem))] animate-enter rounded-xl border border-white/10 bg-ink-900 p-2 text-white shadow-lg"
        >
          <div className="px-3 pt-2 pb-3">
            <p className={cx(monoLabel, "text-slate-400")}>{guest ? "Demo session" : "Signed in as"}</p>
            <p className="mt-1 flex items-center gap-2">
              <span className="min-w-0 truncate text-sm font-medium text-white" title={user.email ?? undefined}>
                {guest ? "Guest" : user.email || user.name}
              </span>
              {isAdmin(user) && <span className={limeOutline}>Admin</span>}
            </p>
            {guest && (
              <p className="mt-1 text-xs leading-relaxed text-slate-400">
                Limited runs per hour. An account keeps your reports.
              </p>
            )}
          </div>

          <div className="space-y-0.5 border-t border-white/[0.08] pt-2">
            <Link
              href="/account"
              onClick={() => setOpen(false)}
              className="flex min-h-10 items-center gap-2 rounded-lg px-3 text-sm text-slate-200 transition-colors hover:bg-white/[0.06] hover:text-white"
            >
              <Icon name="user" className="h-4 w-4 text-slate-400" />
              Account
            </Link>
            {isAdmin(user) && (
              <Link
                href="/admin/audit"
                onClick={() => setOpen(false)}
                className="flex min-h-10 items-center gap-2 rounded-lg px-3 text-sm text-slate-200 transition-colors hover:bg-white/[0.06] hover:text-white"
              >
                <Icon name="list" className="h-4 w-4 text-slate-400" />
                Audit log
              </Link>
            )}
            {guest && (
              <Link
                href="/login?mode=signup&next=%2Fresearch"
                onClick={() => setOpen(false)}
                className="flex min-h-10 items-center gap-2 rounded-lg px-3 text-sm text-slate-200 transition-colors hover:bg-white/[0.06] hover:text-white"
              >
                <Icon name="plus" className="h-4 w-4 text-accent-300" />
                Create an account
              </Link>
            )}
            <div className="flex min-h-10 items-center justify-between gap-3 rounded-lg px-3 sm:hidden">
              <span className="text-sm text-slate-300">Theme</span>
              <ThemeToggle />
            </div>
            <button
              type="button"
              disabled={leaving}
              onClick={async () => {
                setLeaving(true);
                await signOut("/");
              }}
              className="flex min-h-10 w-full items-center gap-2 rounded-lg px-3 text-left text-sm text-slate-200 transition-colors hover:bg-white/[0.06] hover:text-white disabled:opacity-60"
            >
              {leaving ? <Spinner className="h-4 w-4" /> : <Icon name="logOut" className="h-4 w-4 text-slate-400" />}
              {leaving ? "Signing out…" : "Sign out"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
