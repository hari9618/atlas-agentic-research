"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getMe } from "@/lib/api";
import { isGuest, type Plan } from "@/lib/auth-common";
import { useSession } from "@/lib/use-session";
import { Icon } from "@/components/ui/Icon";
import { cx, tap } from "@/components/ui/styles";

// The plan doesn't change within a session; fetch it once per page load.
let planCache: Plan | null = null;

/** A quiet note for demo (guest) sessions: what the limit is, and that an account keeps
 *  their work. Renders nothing for real accounts. */
export function GuestBanner() {
  const { user } = useSession();
  const guest = isGuest(user);
  const [plan, setPlan] = useState<Plan | null>(planCache);

  useEffect(() => {
    if (!guest || planCache) return;
    const ctrl = new AbortController();
    getMe(ctrl.signal).then((r) => {
      if (!r.ok || !r.data?.plan) return;
      planCache = r.data.plan;
      setPlan(r.data.plan);
    });
    return () => ctrl.abort();
  }, [guest]);

  if (!guest) return null;
  const n = plan?.research_per_hour;

  return (
    <div
      role="note"
      className="flex animate-enter flex-col gap-3 rounded-xl border border-indigo-200/70 bg-indigo-50/50 px-4 py-3 sm:flex-row sm:items-center"
    >
      <p className="flex min-w-0 flex-1 items-start gap-2 text-sm leading-relaxed text-slate-700">
        <Icon name="spark" className="mt-0.5 h-4 w-4 shrink-0 text-indigo-600" />
        <span>
          <span className="font-semibold text-slate-900">Demo session.</span>{" "}
          {typeof n === "number"
            ? `Limited to ${n} run${n === 1 ? "" : "s"} per hour.`
            : "Runs per hour are limited."}{" "}
          Create an account to keep your reports.
        </span>
      </p>
      <Link
        href="/login?mode=signup&next=%2Fresearch"
        className={cx(
          "inline-flex shrink-0 items-center justify-center gap-2 self-start rounded-lg px-4 py-2 text-xs font-semibold text-indigo-800 ring-1 ring-indigo-600/25 transition-colors ring-inset hover:bg-indigo-100 sm:self-auto",
          tap,
        )}
      >
        Create account
        <Icon name="arrowRight" className="h-3.5 w-3.5" />
      </Link>
    </div>
  );
}
