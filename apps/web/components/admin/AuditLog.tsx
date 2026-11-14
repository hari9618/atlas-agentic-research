"use client";

import { useEffect, useState } from "react";
import { type ApiFailure, type AuditEvent, getAuditLog } from "@/lib/api";
import { isAdmin } from "@/lib/auth-common";
import { useSession } from "@/lib/use-session";
import { fullDate, timeAgo } from "@/components/learning/format";
import { Icon } from "@/components/ui/Icon";
import { Spinner } from "@/components/ui/Spinner";
import { btn, cx, monoLabel, surface, tap, toggleChip } from "@/components/ui/styles";

const FILTERS = [
  { value: "", label: "All" },
  { value: "auth.", label: "auth." },
  { value: "admin.", label: "admin." },
] as const;
type Filter = (typeof FILTERS)[number]["value"];

type Load = { status: "loading" } | { status: "ready"; events: AuditEvent[] } | { status: "error"; failure: ApiFailure };

/** ISO string for `at`, whether the backend sent ISO or epoch seconds / milliseconds. */
function iso(at: AuditEvent["at"]): string {
  if (typeof at === "number" && Number.isFinite(at)) return new Date(at < 1e12 ? at * 1000 : at).toISOString();
  return typeof at === "string" ? at : "";
}

const short = (v: string | null | undefined, n = 8) => (v ? (v.length > n ? `${v.slice(0, n)}…` : v) : "—");

function detailText(d: unknown): string {
  if (d == null || d === "") return "";
  if (typeof d === "string") return d;
  try {
    const s = JSON.stringify(d);
    return s === "{}" ? "" : s;
  } catch {
    return "";
  }
}

const BAD = /fail|denied|forbidden|invalid|revoked|rate|locked|reuse/i;

function eventTone(e: string): string {
  if (BAD.test(e)) return "text-rose-700";
  if (e.startsWith("admin.")) return "text-indigo-700";
  return "text-slate-900";
}

/** Recent security events (sign-ins, password changes, admin actions). Admin only: the
 *  API enforces that; this view just says so plainly on a 403. */
export function AuditLog() {
  const { status, user } = useSession();
  const [filter, setFilter] = useState<Filter>("");
  const [nonce, setNonce] = useState(0);
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const admin = status === "authenticated" && isAdmin(user);
  const knownNonAdmin = status === "authenticated" && !admin;

  useEffect(() => {
    if (!admin) return;
    const ctrl = new AbortController();
    getAuditLog({ prefix: filter || undefined, signal: ctrl.signal }).then((r) => {
      if (ctrl.signal.aborted || (!r.ok && r.failure.kind === "aborted")) return;
      setLoad(r.ok ? { status: "ready", events: r.data } : { status: "error", failure: r.failure });
    });
    return () => ctrl.abort();
  }, [filter, nonce, admin]);

  function choose(f: Filter) {
    if (f === filter) return;
    setLoad({ status: "loading" });
    setFilter(f);
  }

  function reload() {
    setLoad({ status: "loading" });
    setNonce((n) => n + 1);
  }

  if (knownNonAdmin || (load.status === "error" && load.failure.kind === "forbidden")) return <AdminsOnly />;

  const events = load.status === "ready" ? load.events : [];

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div role="group" aria-label="Filter by event type" className="flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <button
              key={f.label}
              type="button"
              aria-pressed={filter === f.value}
              onClick={() => choose(f.value)}
              className={cx(toggleChip, f.value && "font-mono")}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <p aria-live="polite" className="text-sm text-slate-600">
            {load.status === "loading"
              ? "Loading events…"
              : load.status === "ready"
                ? `${events.length} event${events.length === 1 ? "" : "s"}`
                : ""}
          </p>
          <button type="button" onClick={reload} disabled={load.status === "loading"} className={cx(btn.small, tap)}>
            {load.status === "loading" ? <Spinner className="h-3.5 w-3.5" /> : <Icon name="refresh" className="h-3.5 w-3.5" />}
            Refresh
          </button>
        </div>
      </div>

      {load.status === "error" && (
        <div role="alert" className={cx(surface, "flex flex-col items-start gap-3 p-5 sm:flex-row sm:items-center")}>
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-700">
            <Icon name="alert" />
          </span>
          <p className="min-w-0 flex-1 text-sm text-slate-700">
            <span className="block font-semibold text-slate-950">Couldn&apos;t load the audit log</span>
            {load.failure.message}
          </p>
          <button type="button" onClick={reload} className={cx(btn.secondary, tap)}>
            Try again
          </button>
        </div>
      )}

      {load.status !== "error" && (
        <div className={cx(surface, "overflow-hidden")}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[46rem] text-left text-sm">
              <caption className="sr-only">Recent audit events, newest first</caption>
              <thead className="border-b border-slate-200/80 bg-slate-50/70">
                <tr>
                  {["Time", "Event", "User", "IP", "Request"].map((h) => (
                    <th key={h} scope="col" className={cx(monoLabel, "px-4 py-3 font-medium text-slate-500")}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {load.status === "loading" &&
                  [0, 1, 2, 3, 4].map((i) => (
                    <tr key={i} aria-hidden>
                      {[24, 40, 16, 20, 16].map((w, j) => (
                        <td key={j} className="px-4 py-4">
                          <span className="block h-3 animate-pulse-soft rounded-full bg-slate-200/80" style={{ width: `${w * 4}px` }} />
                        </td>
                      ))}
                    </tr>
                  ))}
                {load.status === "ready" &&
                  events.map((e, i) => {
                    const at = iso(e.at);
                    const detail = detailText(e.detail);
                    return (
                      <tr key={`${e.request_id ?? "r"}-${at}-${i}`} className="align-top hover:bg-slate-50/60">
                        <td className="px-4 py-3 whitespace-nowrap text-slate-700">
                          <time dateTime={at} title={fullDate(at)}>
                            {timeAgo(at) || fullDate(at) || "—"}
                          </time>
                        </td>
                        <td className="max-w-[22rem] px-4 py-3">
                          <span className={cx("font-mono text-sm font-medium", eventTone(e.event))}>{e.event}</span>
                          {detail && (
                            <span className="mt-0.5 block truncate text-xs text-slate-500" title={detail}>
                              {detail}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs whitespace-nowrap text-slate-600" title={e.user_id ?? undefined}>
                          {short(e.user_id)}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs whitespace-nowrap text-slate-600">{e.ip || "—"}</td>
                        <td className="px-4 py-3 font-mono text-xs whitespace-nowrap text-slate-600" title={e.request_id ?? undefined}>
                          {short(e.request_id)}
                        </td>
                      </tr>
                    );
                  })}
                {load.status === "ready" && events.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-10 text-center text-sm text-slate-500">
                      No events{filter ? ` starting with “${filter}”` : ""} yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function AdminsOnly() {
  return (
    <div role="alert" className={cx(surface, "flex flex-col items-start gap-4 p-6 sm:flex-row sm:items-center")}>
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-600">
        <Icon name="shield" />
      </span>
      <div className="min-w-0">
        <p className="font-semibold text-slate-950">Admins only</p>
        <p className="mt-0.5 text-sm leading-relaxed text-slate-600">
          The audit log records every account&apos;s security events, so only administrators can see it.
        </p>
      </div>
    </div>
  );
}
