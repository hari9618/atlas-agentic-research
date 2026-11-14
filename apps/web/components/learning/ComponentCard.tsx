"use client";

import { useEffect, useId, useRef, useState } from "react";
import { type ComponentHistory, getComponentHistory, type PolicyComponent } from "@/lib/api";
import { Icon } from "@/components/ui/Icon";
import { Spinner } from "@/components/ui/Spinner";
import { btn, cx, limeOutline, limePill, monoLabel, surface, tap } from "@/components/ui/styles";
import { fullDate, timeAgo } from "./format";

const SHOWN_LESSONS = 3;

type HistoryState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; data: ComponentHistory }
  | { status: "error"; message: string };

/** One agent component's live policy: version, learned lessons, exemplar count and
 *  retrieval depth, with its version history and a guarded rollback. */
export function ComponentCard({
  c,
  busy,
  onRollback,
}: {
  c: PolicyComponent;
  /** A rollback of this component is in flight. */
  busy: boolean;
  /** Absent for non-admins: rollback is admin-only, so the control isn't offered. */
  onRollback?: (name: string) => void;
}) {
  const uid = useId();
  const [allLessons, setAllLessons] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [history, setHistory] = useState<HistoryState>({ status: "idle" });
  const confirmRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const lessons = c.lessons ?? [];
  const shown = allLessons ? lessons : lessons.slice(0, SHOWN_LESSONS);
  const canRollback = c.version > 1;

  useEffect(() => {
    if (confirming) confirmRef.current?.focus();
  }, [confirming]);

  // A new active version invalidates the loaded history.
  const [seenVersion, setSeenVersion] = useState(c.version);
  if (seenVersion !== c.version) {
    setSeenVersion(c.version);
    setHistory({ status: "idle" });
    setHistoryOpen(false);
  }

  async function toggleHistory() {
    const next = !historyOpen;
    setHistoryOpen(next);
    if (!next || history.status === "ready" || history.status === "loading") return;
    setHistory({ status: "loading" });
    const r = await getComponentHistory(c.name);
    setHistory(r.ok ? { status: "ready", data: r.data } : { status: "error", message: r.failure.message });
  }

  const cancel = () => {
    setConfirming(false);
    requestAnimationFrame(() => triggerRef.current?.focus());
  };

  return (
    <li className={cx(surface, "flex min-w-0 flex-col")}>
      <div className="flex items-start justify-between gap-3 px-4 pt-4 sm:px-5">
        <div className="min-w-0">
          <h3 className="text-base font-semibold text-slate-950">{c.label || c.name}</h3>
          <p className="truncate font-mono text-2xs text-slate-500">{c.name}</p>
        </div>
        <span className={cx(limeOutline, "font-mono tabular-nums")}>v{c.version}</span>
      </div>

      <dl className="mx-4 mt-4 grid grid-cols-3 divide-x divide-slate-200/80 rounded-xl border border-slate-200/80 bg-slate-50/60 sm:mx-5">
        {[
          ["Lessons", lessons.length],
          ["Exemplars", c.exemplars],
          ["Top-k", c.top_k],
        ].map(([k, v]) => (
          <div key={k} className="min-w-0 px-3 py-2">
            <dt className={cx(monoLabel, "truncate text-slate-500")}>{k}</dt>
            <dd className="mt-0.5 font-mono text-lg font-semibold text-slate-950 tabular-nums">{v ?? "—"}</dd>
          </div>
        ))}
      </dl>

      <div className="flex-1 px-4 pt-4 sm:px-5">
        <p className={cx(monoLabel, "text-slate-500")}>Learned lessons</p>
        {lessons.length ? (
          <>
            <ul className="mt-2 space-y-2">
              {shown.map((l, i) => (
                <li key={i} className="flex gap-2 text-sm leading-relaxed text-slate-700">
                  <Icon name="spark" className="mt-1 h-3.5 w-3.5 shrink-0 text-indigo-600" />
                  <span className="min-w-0">{l}</span>
                </li>
              ))}
            </ul>
            {lessons.length > SHOWN_LESSONS && (
              <button
                type="button"
                onClick={() => setAllLessons((v) => !v)}
                aria-expanded={allLessons}
                className={cx("mt-2 text-xs font-medium text-indigo-700 hover:underline", tap)}
              >
                {allLessons ? "Show fewer" : `Show all ${lessons.length}`}
              </button>
            )}
          </>
        ) : (
          <p className="mt-2 text-sm text-slate-500 italic">No lessons yet. It runs on its base prompt.</p>
        )}
      </div>

      {historyOpen && (
        <div id={`${uid}-history`} className="mx-4 mt-4 animate-enter rounded-xl border border-slate-200/80 sm:mx-5">
          {history.status === "loading" && (
            <p className="flex items-center gap-2 px-3 py-3 text-sm text-slate-500">
              <Spinner className="h-3.5 w-3.5" /> Loading versions…
            </p>
          )}
          {history.status === "error" && (
            <p className="px-3 py-3 text-sm text-rose-700">Couldn&apos;t load the history. {history.message}</p>
          )}
          {history.status === "ready" &&
            (history.data.versions?.length ? (
              <ol className="divide-y divide-slate-100">
                {[...history.data.versions]
                  .sort((a, b) => b.version - a.version)
                  .map((v) => (
                    <li key={v.version} className="px-3 py-2 text-sm">
                      <p className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs font-semibold text-slate-900 tabular-nums">v{v.version}</span>
                        {v.version === history.data.active_version && (
                          <span className={limePill}>Active</span>
                        )}
                        <span className="ml-auto font-mono text-2xs text-slate-500" title={fullDate(v.created_at)}>
                          {timeAgo(v.created_at)}
                        </span>
                      </p>
                      {v.notes && <p className="mt-1 leading-relaxed text-slate-600">{v.notes}</p>}
                    </li>
                  ))}
              </ol>
            ) : (
              <p className="px-3 py-3 text-sm text-slate-500">Only the base version exists.</p>
            ))}
        </div>
      )}

      <div className="mt-4 border-t border-slate-100 px-4 py-3 sm:px-5">
        {confirming ? (
          <div
            role="group"
            aria-labelledby={`${uid}-confirm`}
            className="animate-enter space-y-2"
            onKeyDown={(e) => e.key === "Escape" && cancel()}
          >
            <p id={`${uid}-confirm`} className="text-sm text-slate-800">
              Restore the previous policy of <span className="font-semibold">{c.label || c.name}</span>?
              <span className="block text-xs text-slate-500">v{c.version} stops serving but stays in the history.</span>
            </p>
            <div className="flex gap-2">
              <button
                ref={confirmRef}
                type="button"
                onClick={() => {
                  setConfirming(false);
                  onRollback?.(c.name);
                }}
                className={cx(
                  "inline-flex items-center justify-center gap-2 rounded-lg bg-rose-600 px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-rose-700",
                  tap,
                )}
              >
                Roll back
              </button>
              <button type="button" onClick={cancel} className={cx(btn.small, tap)}>
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <span className="mr-auto font-mono text-2xs text-slate-500" title={fullDate(c.updated_at)}>
              {c.updated_at ? `Updated ${timeAgo(c.updated_at)}` : "Never updated"}
            </span>
            <button
              type="button"
              onClick={toggleHistory}
              aria-expanded={historyOpen}
              aria-controls={`${uid}-history`}
              className={cx(btn.small, tap)}
            >
              <Icon name="clock" className="h-3.5 w-3.5" />
              History
            </button>
            {onRollback && (
              <button
                ref={triggerRef}
                type="button"
                onClick={() => setConfirming(true)}
                disabled={!canRollback || busy}
                title={canRollback ? "Restore the previous version" : "Already on the first version"}
                className={cx(btn.small, tap)}
              >
                {busy ? <Spinner className="h-3.5 w-3.5" /> : <Icon name="refresh" className="h-3.5 w-3.5" />}
                {busy ? "Rolling back…" : "Roll back"}
              </button>
            )}
          </div>
        )}
      </div>
    </li>
  );
}
