"use client";

import { useState } from "react";
import type { Experiment } from "@/lib/api";
import { Icon } from "@/components/ui/Icon";
import { Spinner } from "@/components/ui/Spinner";
import { btn, cx, monoLabel, surface, tap } from "@/components/ui/styles";
import { Delta, LEVER, PolicyValue, TrialResults } from "./ExperimentCard";
import { fullDate, timeAgo } from "./format";

export type Decision = "approve" | "reject";

/** Candidate policy changes that won their replay but wait for a person to approve the
 *  exact change before it reaches users. Admins decide; everyone else can read. */
export function PendingApprovals({
  items,
  admin,
  labelOf,
  onDecide,
}: {
  items: Experiment[];
  admin: boolean;
  labelOf: (component: string) => string;
  /** Resolves when the server has answered (the dashboard shows the outcome). */
  onDecide: (exp: Experiment, decision: Decision) => Promise<void>;
}) {
  if (!items.length) return null;
  return (
    <section aria-labelledby="pending-title" className="space-y-3">
      <div>
        <h2 id="pending-title" className="text-lg font-semibold text-slate-950">
          Waiting for approval <span className="font-normal text-slate-500 tabular-nums">({items.length})</span>
        </h2>
        <p className="mt-1 max-w-[70ch] text-sm leading-relaxed text-slate-600">
          These changes beat the live policy in a paired replay. Nothing goes live until an admin approves the exact
          change below.
        </p>
      </div>
      <ul className="space-y-3">
        {items.map((e) => (
          <PendingItem key={e.id} exp={e} admin={admin} label={labelOf(e.component)} onDecide={onDecide} />
        ))}
      </ul>
    </section>
  );
}

function PendingItem({
  exp,
  admin,
  label,
  onDecide,
}: {
  exp: Experiment;
  admin: boolean;
  label: string;
  onDecide: (exp: Experiment, decision: Decision) => Promise<void>;
}) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState<Decision | null>(null);
  const lever = LEVER[exp.lever];
  const lesson = typeof exp.change?.lesson === "string" && exp.change.lesson.trim() ? exp.change.lesson : null;
  const trials = exp.trials ?? [];

  async function decide(d: Decision) {
    setBusy(d);
    await onDecide(exp, d);
    setBusy(null);
    setConfirming(false);
  }

  return (
    <li className={cx(surface, "overflow-hidden border-l-2 border-l-amber-500")}>
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 px-4 pt-4 sm:px-6">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-950">
            {label}
            {lever && <span className="font-normal text-slate-500"> · {lever.label}</span>}
          </p>
          <p className="mt-1 text-xs text-slate-500" title={fullDate(exp.created_at)}>
            Proposed {timeAgo(exp.created_at) || fullDate(exp.created_at)}
          </p>
        </div>
        <p className="flex items-center gap-2 text-sm text-slate-600">
          Replay
          <Delta value={exp.mean_delta} className="font-semibold" />
          <span className="text-xs text-slate-500">
            over {trials.length} quer{trials.length === 1 ? "y" : "ies"}
          </span>
        </p>
      </div>

      <div className="space-y-4 px-4 py-4 sm:px-6">
        {exp.hypothesis && <p className="max-w-[72ch] text-sm leading-relaxed text-slate-700">{exp.hypothesis}</p>}

        <div>
          <p className={cx(monoLabel, "mb-2 text-slate-500")}>{lesson ? "Proposed lesson (exact text)" : "Proposed change"}</p>
          {exp.change?.summary && !lesson && <p className="mb-2 text-sm font-medium text-slate-900">{exp.change.summary}</p>}
          <blockquote className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm leading-relaxed text-slate-900">
            {lesson ? <p className="whitespace-pre-wrap">{lesson}</p> : <PolicyValue value={exp.change?.after} />}
          </blockquote>
        </div>

        {trials.length > 0 && (
          <details className="group">
            <summary className="inline-flex items-center gap-2 text-sm font-medium text-indigo-700">
              <Icon name="chevron" className="chevron h-4 w-4 transition-transform" />
              Replay results by query
            </summary>
            <div className="mt-3">
              <TrialResults exp={exp} />
            </div>
          </details>
        )}
      </div>

      <div className="border-t border-slate-200/80 bg-slate-50/60 px-4 py-3 sm:px-6">
        {!admin ? (
          <p className="flex items-center gap-2 text-sm text-slate-600">
            <Icon name="shield" className="h-4 w-4 shrink-0 text-slate-500" />
            An admin reviews this change before it goes live.
          </p>
        ) : confirming ? (
          <div role="group" aria-label="Confirm release" className="flex flex-wrap items-center gap-2">
            <p className="mr-auto text-sm text-slate-800">
              Release this to every run as a new version of <span className="font-semibold">{label}</span>?
            </p>
            <button type="button" onClick={() => decide("approve")} disabled={!!busy} className={cx(btn.primary, tap)}>
              {busy === "approve" ? <Spinner /> : <Icon name="check" />}
              {busy === "approve" ? "Releasing…" : "Release"}
            </button>
            <button type="button" onClick={() => setConfirming(false)} disabled={!!busy} className={cx(btn.secondary, tap)}>
              Cancel
            </button>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={() => setConfirming(true)} disabled={!!busy} className={cx(btn.primary, tap)}>
              <Icon name="check" />
              Approve
            </button>
            <button type="button" onClick={() => decide("reject")} disabled={!!busy} className={cx(btn.secondary, tap)}>
              {busy === "reject" ? <Spinner /> : <Icon name="x" />}
              {busy === "reject" ? "Rejecting…" : "Reject"}
            </button>
            <p className="text-xs text-slate-500">Approving releases it as a new, rollback-able version.</p>
          </div>
        )}
      </div>
    </li>
  );
}
