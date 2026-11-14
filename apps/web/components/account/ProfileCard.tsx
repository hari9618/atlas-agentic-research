"use client";

import { useEffect, useState } from "react";
import { getMe } from "@/lib/api";
import { type AuthUser, isAdmin, isGuest, type Plan } from "@/lib/auth-common";
import { Badge } from "@/components/ui/Badge";
import { cx, limeOutline, monoLabel, surface } from "@/components/ui/styles";

type PlanState = { status: "loading" } | { status: "ready"; plan: Plan } | { status: "error"; message: string };

function RoleBadge({ user }: { user: AuthUser }) {
  if (isAdmin(user)) return <span className={limeOutline}>Admin</span>;
  if (isGuest(user)) return <Badge tone="muted">Guest</Badge>;
  return <Badge tone="muted">Member</Badge>;
}

/** Who you are and what your plan allows (from /auth/me, the server's view). */
export function ProfileCard({ user }: { user: AuthUser }) {
  const [plan, setPlan] = useState<PlanState>({ status: "loading" });
  const guest = isGuest(user);

  useEffect(() => {
    const ctrl = new AbortController();
    getMe(ctrl.signal).then((r) => {
      if (ctrl.signal.aborted || (!r.ok && r.failure.kind === "aborted")) return;
      if (r.ok && r.data?.plan) setPlan({ status: "ready", plan: r.data.plan });
      else setPlan({ status: "error", message: r.ok ? "No plan information." : r.failure.message });
    });
    return () => ctrl.abort();
  }, []);

  const initial = guest ? "G" : (user.name || user.email || "A").trim().charAt(0).toUpperCase();
  const limits: [string, (p: Plan) => number][] = [
    ["Research runs per hour", (p) => p.research_per_hour],
    ["Runs at the same time", (p) => p.concurrent_runs],
  ];

  return (
    <section aria-labelledby="profile-title" className={cx(surface, "overflow-hidden")}>
      <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:p-6">
        <span
          aria-hidden
          className={cx(
            "flex h-12 w-12 shrink-0 items-center justify-center rounded-lg text-xl font-semibold",
            guest ? "border border-dashed border-slate-300 text-slate-500" : "bg-accent-400 text-ink-950",
          )}
        >
          {initial}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 id="profile-title" className="min-w-0 truncate text-lg font-semibold text-slate-950">
              {guest ? "Guest session" : user.name || user.email}
            </h2>
            <RoleBadge user={user} />
          </div>
          {!guest && user.name && user.email && <p className="mt-0.5 truncate text-sm text-slate-600">{user.email}</p>}
          {guest && (
            <p className="mt-0.5 text-sm text-slate-600">A temporary demo account. It ends when the session expires.</p>
          )}
          <p className="mt-1 truncate font-mono text-2xs text-slate-500" title={user.id}>
            ID {user.id}
          </p>
        </div>
      </div>

      <dl className="grid grid-cols-2 divide-x divide-slate-200/80 border-t border-slate-200/80 bg-slate-50/60">
        {limits.map(([label, pick]) => (
          <div key={label} className="min-w-0 px-5 py-4 sm:px-6">
            <dt className={cx(monoLabel, "text-slate-500")}>{label}</dt>
            <dd className="mt-1 font-mono text-2xl font-semibold text-slate-950 tabular-nums">
              {plan.status === "ready" ? (
                pick(plan.plan)
              ) : plan.status === "loading" ? (
                <span aria-label="Loading" className="inline-block h-6 w-10 animate-pulse-soft rounded-md bg-slate-200/80" />
              ) : (
                <span className="text-base font-normal text-slate-500" title={plan.message}>
                  —
                </span>
              )}
            </dd>
          </div>
        ))}
      </dl>
      {plan.status === "error" && (
        <p role="status" className="border-t border-slate-200/80 px-5 py-3 text-xs text-slate-500 sm:px-6">
          Couldn&apos;t load your plan: {plan.message}
        </p>
      )}
    </section>
  );
}
