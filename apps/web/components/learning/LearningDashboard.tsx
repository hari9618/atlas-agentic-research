"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  type ApiFailure,
  approveExperiment,
  ensureAwake,
  type Experiment,
  getExperiments,
  getLlmOpsOverview,
  isPending,
  rejectExperiment,
  type LlmOpsOverview,
  type RecentRun,
  type RunMetric,
  rollbackComponent,
  runImprovementExperiment,
} from "@/lib/api";
import { isAdmin } from "@/lib/auth-common";
import { useSession } from "@/lib/use-session";
import { Badge } from "@/components/ui/Badge";
import { Icon } from "@/components/ui/Icon";
import { IndeterminateBar, Spinner } from "@/components/ui/Spinner";
import { btn, cx, monoLabel, surface, tap, type ToneKey } from "@/components/ui/styles";
import { ComponentCard } from "./ComponentCard";
import { ExperimentCard } from "./ExperimentCard";
import { type Decision, PendingApprovals } from "./PendingApprovals";
import { fmtScore, fullDate, humanize, pct, timeAgo } from "./format";

type Load =
  | { status: "loading"; waking: boolean }
  | { status: "ready"; data: LlmOpsOverview }
  | { status: "error"; failure: ApiFailure };

type Notice = { tone: "good" | "bad" | "info"; title: string; body?: string; experimentId?: string };

/** Typical stages of POST /llmops/improve, by elapsed seconds. The server only answers
 *  at the end, so these are an honest guide to what is happening, not live telemetry. */
const STAGES: { at: number; text: string }[] = [
  { at: 0, text: "Picking the weakest component from open failure patterns" },
  { at: 6, text: "Writing a hypothesis and one targeted change" },
  { at: 15, text: "Running the baseline: current policy on the trial queries" },
  { at: 45, text: "Running the candidate on the same queries" },
  { at: 80, text: "Comparing paired scores and deciding" },
];

function failureCopy(f: ApiFailure): { title: string; body: string } {
  if (f.kind === "offline") return { title: "You're offline", body: "Reconnect, then try again." };
  if (f.kind === "forbidden")
    return { title: "Admins only", body: "Running experiments and rolling back policies is limited to administrators." };
  if (f.kind === "rate_limited") return { title: "Slow down a little", body: f.message };
  if (f.kind === "busy") return { title: "Atlas is at capacity right now", body: f.message };
  if (f.kind === "unauthenticated") return { title: "Your session has ended", body: "Sign in again to continue." };
  if (f.status === 404)
    return {
      title: "The learning loop isn't available on this server yet",
      body: "This API version doesn't expose the /llmops endpoints. Once it's deployed, this page fills in on its own.",
    };
  if (f.kind === "unreachable")
    return {
      title: "Can't reach the research engine",
      body: "The server didn't answer, even after waiting for it to wake up. Try again in a moment.",
    };
  if (f.kind === "timeout") return { title: "That took too long", body: "The server didn't finish in time. Try again." };
  return { title: "Something went wrong", body: f.message };
}

/** The experiments endpoint is the source of truth for status (it knows about changes
 *  awaiting approval); the overview may carry richer fields. Merge by id. */
function mergeExperiments(overview: LlmOpsOverview, live: Experiment[]): LlmOpsOverview {
  const byId = new Map(live.map((e) => [e.id, e]));
  const merged = overview.experiments.map((e) => {
    const l = byId.get(e.id);
    byId.delete(e.id);
    return l ? { ...e, ...l, change: { ...e.change, ...l.change } } : e;
  });
  const extra = [...byId.values()];
  const experiments = [...extra, ...merged].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
  return { ...overview, experiments };
}

const QUALITY_TONE: Record<string, ToneKey> = { good: "good", ok: "mid", poor: "bad" };
const REVIEW_TONE: Record<string, ToneKey> = { approved: "good", rejected: "bad", revised: "info", none: "muted" };
const REVIEW_TEXT: Record<string, string> = {
  approved: "Approved",
  rejected: "Rejected",
  revised: "Revised",
  none: "Not reviewed",
};

export function LearningDashboard() {
  const [load, setLoad] = useState<Load>({ status: "loading", waking: false });
  const [refreshing, setRefreshing] = useState(false);
  const [improving, setImproving] = useState(false);
  const [improveStart, setImproveStart] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [highlight, setHighlight] = useState<string | null>(null);
  const [rollingBack, setRollingBack] = useState<string | null>(null);
  const improvingRef = useRef(false);
  const { status, user } = useSession();
  const admin = isAdmin(user);

  const fetchOverview = useCallback(async (signal?: AbortSignal) => {
    const wake = await ensureAwake({
      signal,
      onSlow: () => setLoad((l) => (l.status === "loading" ? { status: "loading", waking: true } : l)),
    });
    if (!wake.ok) return { ok: false as const, failure: wake.failure };
    // The experiments list is optional extra detail: an older API without it (404) or
    // a hiccup there must not blank the dashboard.
    const [overview, live] = await Promise.all([getLlmOpsOverview(signal), getExperiments(signal)]);
    if (!overview.ok) return overview;
    return { ok: true as const, data: live.ok ? mergeExperiments(overview.data, live.data) : overview.data };
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    fetchOverview(ctrl.signal).then((r) => {
      if (ctrl.signal.aborted || (!r.ok && r.failure.kind === "aborted")) return;
      setLoad(r.ok ? { status: "ready", data: r.data } : { status: "error", failure: r.failure });
    });
    return () => ctrl.abort();
  }, [fetchOverview]);

  async function refresh(opts: { quiet?: boolean } = {}) {
    if (!opts.quiet) setRefreshing(true);
    if (load.status === "error") setLoad({ status: "loading", waking: false });
    const r = await fetchOverview();
    setRefreshing(false);
    if (r.ok) setLoad({ status: "ready", data: r.data });
    else if (load.status !== "ready") setLoad({ status: "error", failure: r.failure });
    else if (!opts.quiet) setNotice({ tone: "bad", ...failureCopy(r.failure) });
  }

  useEffect(() => {
    if (!improving) return;
    const t = setInterval(() => setElapsed(Math.floor((Date.now() - improveStart) / 1000)), 1000);
    return () => clearInterval(t);
  }, [improving, improveStart]);

  async function improve() {
    if (improvingRef.current || !admin) return;
    improvingRef.current = true;
    setImproving(true);
    setImproveStart(Date.now());
    setElapsed(0);
    setNotice(null);
    setHighlight(null);
    const wake = await ensureAwake();
    const r = wake.ok ? await runImprovementExperiment() : { ok: false as const, failure: wake.failure };
    improvingRef.current = false;
    setImproving(false);

    if (!r.ok) {
      setNotice({ tone: "bad", ...failureCopy(r.failure) });
      return;
    }
    const exp = r.data.experiment;
    if (exp) {
      setLoad((l) =>
        l.status === "ready"
          ? { status: "ready", data: { ...l.data, experiments: [exp, ...l.data.experiments.filter((e) => e.id !== exp.id)] } }
          : l,
      );
      setHighlight(exp.id);
      setNotice({
        tone: exp.decision === "released" ? "good" : "info",
        title: exp.decision === "released" ? "Improvement released" : "Experiment finished: change not released",
        body: r.data.message,
        experimentId: exp.id,
      });
    } else {
      setNotice({ tone: "info", title: "No experiment was run", body: r.data.message });
    }
    refresh({ quiet: true });
  }

  async function rollback(name: string) {
    setRollingBack(name);
    setNotice(null);
    const r = await rollbackComponent(name);
    setRollingBack(null);
    if (!r.ok) {
      setNotice({ tone: "bad", ...failureCopy(r.failure) });
      return;
    }
    setLoad((l) =>
      l.status === "ready"
        ? {
            status: "ready",
            data: {
              ...l.data,
              components: l.data.components.map((c) => (c.name === r.data.component ? { ...c, version: r.data.version } : c)),
            },
          }
        : l,
    );
    const label = load.status === "ready" ? load.data.components.find((c) => c.name === name)?.label : undefined;
    setNotice({ tone: "good", title: `${label || name} rolled back`, body: `Now serving v${r.data.version}.` });
    refresh({ quiet: true });
  }

  async function decide(exp: Experiment, decision: Decision) {
    setNotice(null);
    const label = labelOf(exp.component);
    if (decision === "approve") {
      const r = await approveExperiment(exp.id);
      if (!r.ok) return setNotice({ tone: "bad", ...failureCopy(r.failure) });
      setNotice({ tone: "good", title: `${label} updated`, body: `The approved change is live as v${r.data.version}.` });
    } else {
      const r = await rejectExperiment(exp.id);
      if (!r.ok) return setNotice({ tone: "bad", ...failureCopy(r.failure) });
      setNotice({ tone: "info", title: "Change rejected", body: `${label} keeps its current policy.` });
    }
    await refresh({ quiet: true });
  }

  useEffect(() => {
    if (!highlight) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    document.getElementById(`exp-${highlight}`)?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" });
  }, [highlight]);

  const data = load.status === "ready" ? load.data : null;
  const labelOf = (name: string) => data?.components.find((c) => c.name === name)?.label || humanize(name);
  const stage = [...STAGES].reverse().find((s) => elapsed >= s.at) ?? STAGES[0];

  return (
    <div className="space-y-8">
      {/* Toolbar */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0" aria-live="polite">
          <p className="text-sm font-medium text-slate-900">Live from the API</p>
          <p className="mt-2 text-sm text-slate-600">
            {load.status === "loading"
              ? load.waking
                ? "Waking up the research engine…"
                : "Loading the learning state…"
              : load.status === "error"
                ? "The learning state couldn't be loaded."
                : `${data!.components.length} components · ${data!.experiments.length} experiment${data!.experiments.length === 1 ? "" : "s"} logged`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => refresh()}
            disabled={refreshing || load.status === "loading"}
            className={cx(btn.secondary, tap)}
          >
            {refreshing ? <Spinner className="h-3.5 w-3.5" /> : <Icon name="refresh" />}
            Refresh
          </button>
          <button
            type="button"
            onClick={improve}
            disabled={improving || load.status !== "ready" || !admin}
            aria-describedby="improve-hint"
            title={status === "authenticated" && !admin ? "Admins only" : undefined}
            className={cx(btn.primary, tap)}
          >
            {improving ? <Spinner className="h-3.5 w-3.5" /> : <Icon name="spark" />}
            {improving ? "Experiment running…" : "Run an improvement experiment"}
          </button>
        </div>
      </div>
      {status === "authenticated" && !admin ? (
        <p
          id="improve-hint"
          className="-mt-4 flex items-start gap-2 text-sm leading-relaxed text-slate-600 sm:justify-end sm:text-right"
        >
          <Icon name="shield" className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
          Experiments and rollbacks change what every user gets, so they&apos;re limited to admins. Everything else here is
          live and yours to explore.
        </p>
      ) : (
        <p id="improve-hint" className="sr-only">
          Runs one paired experiment on the server. It usually takes 30 seconds to 2 minutes.
        </p>
      )}

      {improving && (
        <section
          aria-labelledby="improve-title"
          aria-busy="true"
          className="animate-enter overflow-hidden rounded-xl bg-ink-950 p-5 text-white ring-1 ring-ink-700 sm:p-6"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0" role="status">
              <p className="flex items-center gap-2 font-mono text-2xs font-medium tracking-label text-accent-300 uppercase">
                <Spinner className="h-3 w-3 text-accent-300" />
                Experiment in progress
              </p>
              <h2 id="improve-title" className="mt-2 text-lg font-semibold tracking-tight">
                {stage.text}…
              </h2>
              <p className="mt-1 text-sm text-slate-400">
                Usually 30 seconds to 2 minutes. You can keep reading; the result appears here when the server answers.
              </p>
            </div>
            <span className="flex items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 py-1 font-mono text-xs text-slate-200 tabular-nums">
              <Icon name="clock" className="h-3.5 w-3.5 text-slate-400" />
              {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")}
              <span className="sr-only"> elapsed</span>
            </span>
          </div>
          <IndeterminateBar tone="dark" className="mt-5" />
          <ol className="mt-5 grid gap-2 sm:grid-cols-5">
            {STAGES.map((s, i) => {
              const state = s === stage ? "active" : elapsed >= s.at ? "done" : "idle";
              return (
                <li
                  key={s.at}
                  className={cx(
                    "rounded-md border px-3 py-2 text-xs leading-snug transition-colors duration-500",
                    state === "active" && "border-indigo-300/25 bg-indigo-400/[0.08] text-slate-100",
                    state === "done" && "border-emerald-400/20 bg-emerald-400/[0.05] text-slate-300",
                    state === "idle" && "border-white/[0.08] text-slate-400",
                  )}
                >
                  <span className="mb-1 block font-mono text-2xs text-slate-400">
                    {state === "done" ? "✓" : String(i + 1).padStart(2, "0")}
                  </span>
                  {s.text}
                </li>
              );
            })}
          </ol>
        </section>
      )}

      {notice && (
        <div
          role={notice.tone === "bad" ? "alert" : "status"}
          className={cx(
            "flex animate-enter items-start gap-3 rounded-xl border p-4",
            notice.tone === "good" && "border-emerald-200 bg-emerald-50/70",
            notice.tone === "bad" && "border-rose-200 bg-rose-50/70",
            notice.tone === "info" && "border-indigo-200 bg-indigo-50/60",
          )}
        >
          <span
            aria-hidden
            className={cx(
              "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
              notice.tone === "good" && "bg-emerald-600 text-white",
              notice.tone === "bad" && "bg-rose-100 text-rose-700",
              notice.tone === "info" && "bg-indigo-100 text-indigo-700",
            )}
          >
            <Icon name={notice.tone === "good" ? "check" : notice.tone === "bad" ? "alert" : "spark"} />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-slate-950">{notice.title}</p>
            {notice.body && <p className="mt-0.5 text-sm leading-relaxed text-slate-700">{notice.body}</p>}
            {notice.experimentId && (
              <a href={`#exp-${notice.experimentId}`} className="mt-2 inline-block text-sm font-medium text-indigo-700 hover:underline">
                See the experiment
              </a>
            )}
          </div>
          <button
            type="button"
            onClick={() => setNotice(null)}
            aria-label="Dismiss"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-slate-500 hover:bg-slate-900/5 hover:text-slate-800 pointer-coarse:h-11 pointer-coarse:w-11"
          >
            <Icon name="x" />
          </button>
        </div>
      )}

      {load.status === "loading" && <DashboardSkeleton />}

      {load.status === "error" && (
        <div role="alert" className={cx(surface, "flex flex-col items-start gap-4 p-6 sm:flex-row sm:items-center")}>
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-700">
            <Icon name="alert" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="font-semibold text-slate-950">{failureCopy(load.failure).title}</p>
            <p className="mt-0.5 text-sm leading-relaxed text-slate-600">{failureCopy(load.failure).body}</p>
          </div>
          <button type="button" onClick={() => refresh()} className={cx(btn.secondary, tap)}>
            <Icon name="refresh" />
            Try again
          </button>
        </div>
      )}

      {data && (
        <div className="animate-enter space-y-10">
          <PendingApprovals items={data.experiments.filter(isPending)} admin={admin} labelOf={labelOf} onDecide={decide} />

          <Stats data={data} />

          {data.runs.metrics.some((m) => m.mean != null) && (
            <section aria-labelledby="scores-title">
              <SectionHead
                id="scores-title"
                title="How good are the reports?"
                text="Every run is scored automatically. Each score is out of 1, and higher is better: 0.70 or more is good, below 0.40 is weak. Averages over recent runs."
              />
              <ScorePanel metrics={data.runs.metrics} />
            </section>
          )}

          <section aria-labelledby="components-title">
            <SectionHead
              id="components-title"
              title="Agent components"
              text="Each component's live policy. Experiments change one lever at a time: a written lesson, the worked exemplars it sees, or how deep it retrieves."
            />
            {data.components.length ? (
              <ul className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
                {data.components.map((c) => (
                  <ComponentCard
                    key={c.name}
                    c={c}
                    busy={rollingBack === c.name}
                    onRollback={admin ? rollback : undefined}
                  />
                ))}
              </ul>
            ) : (
              <Empty text="No agent policies are registered yet." />
            )}
          </section>

          <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <section aria-labelledby="issues-title" className="min-w-0">
              <SectionHead
                id="issues-title"
                title="Open failure patterns"
                text="Recurring problems found in scored runs and reviewer feedback. The next experiment targets the biggest one."
              />
              {data.issues.length ? (
                <ul className={cx(surface, "divide-y divide-slate-100 overflow-hidden")}>
                  {[...data.issues]
                    .sort((a, b) => b.count - a.count)
                    .map((it, i) => (
                      <li key={`${it.component}-${it.kind}-${i}`} className="flex gap-3 px-4 py-4 sm:px-5">
                        <span className="flex h-7 min-w-7 shrink-0 items-center justify-center rounded-full bg-rose-50 px-2 font-mono text-xs font-semibold text-rose-700 ring-1 ring-rose-600/15 tabular-nums">
                          {it.count}
                          <span className="sr-only"> occurrences</span>
                        </span>
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-slate-900">{humanize(it.kind)}</p>
                          <p className="text-xs text-slate-500">{labelOf(it.component)}</p>
                          {it.example && (
                            <p className="mt-2 line-clamp-2 border-l-2 border-slate-200 pl-2 text-sm leading-relaxed text-slate-600">
                              {it.example}
                            </p>
                          )}
                        </div>
                      </li>
                    ))}
                </ul>
              ) : (
                <Empty text="No open failure patterns. Recent runs look healthy." good />
              )}
            </section>

            <section aria-labelledby="runs-title" className="min-w-0">
              <SectionHead
                id="runs-title"
                title="Recent runs"
                text="Every finished run is scored automatically; reviewer decisions feed the same record."
              />
              {data.runs.recent.length ? (
                <ul className={cx(surface, "divide-y divide-slate-100 overflow-hidden")}>
                  {data.runs.recent.map((r) => (
                    <RunRow key={r.id} r={r} />
                  ))}
                </ul>
              ) : (
                <Empty text="No runs have been scored yet. Finish a run in the research workspace to start the loop." />
              )}
            </section>
          </div>

          <section aria-labelledby="experiments-title">
            <SectionHead
              id="experiments-title"
              title="Experiment log"
              text="Each experiment tests one change against the current policy on the same queries. Only a change that wins is released."
            />
            {data.experiments.length ? (
              <ol className="space-y-3">
                {data.experiments.map((e: Experiment, i) => (
                  <ExperimentCard
                    key={e.id}
                    exp={e}
                    label={labelOf(e.component)}
                    defaultOpen={i === 0}
                    highlight={highlight === e.id}
                  />
                ))}
              </ol>
            ) : (
              <Empty text="No experiments yet. Run the first one with the button above." />
            )}
          </section>
        </div>
      )}
    </div>
  );
}

function SectionHead({ id, title, text }: { id: string; title: string; text: string }) {
  return (
    <div className="mb-4">
      <h2 id={id} className="text-lg font-semibold tracking-tight text-slate-950">
        {title}
      </h2>
      <p className="mt-1 max-w-[70ch] text-sm leading-relaxed text-slate-600">{text}</p>
    </div>
  );
}

function Empty({ text, good = false }: { text: string; good?: boolean }) {
  return (
    <p
      className={cx(
        "flex items-center gap-2 rounded-xl border border-dashed px-4 py-5 text-sm",
        good ? "border-emerald-300/70 text-emerald-800" : "border-slate-300 text-slate-600",
      )}
    >
      <Icon name={good ? "check" : "help"} className="h-4 w-4 shrink-0" />
      {text}
    </p>
  );
}

function Stats({ data }: { data: LlmOpsOverview }) {
  const r = data.runs;
  // Oldest to newest, scored runs only: the trend line for mean quality.
  const series = [...r.recent]
    .filter((x) => typeof x.overall === "number")
    .sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at))
    .map((x) => x.overall as number);
  const cells: { label: string; value: string; foot: string; chart?: number[] }[] = [
    { label: "Runs recorded", value: String(r.total), foot: `${r.reviewed} reviewed by a person` },
    { label: "Approval rate", value: pct(r.approved, r.reviewed), foot: `${r.approved} of ${r.reviewed} reviewed runs` },
    {
      label: "Mean quality",
      value: fmtScore(r.mean_overall),
      foot: r.mean_overall == null ? "No scores yet" : "Automatic eval, 0 to 1",
      chart: series,
    },
    { label: "Revision requests", value: String(r.revision_requests), foot: "Changes asked for by reviewers" },
    { label: "Rejected", value: String(r.rejected), foot: "Drafts a reviewer turned down" },
  ];
  return (
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-xl bg-slate-200/80 ring-1 ring-slate-200/80 sm:grid-cols-3 lg:grid-cols-5">
      {cells.map((c, i) => (
        <div key={c.label} className={cx("min-w-0 bg-surface p-4 sm:p-5", i === cells.length - 1 && "col-span-2 sm:col-span-1")}>
          <dt className={cx(monoLabel, "text-slate-500")}>{c.label}</dt>
          <dd className="mt-2 flex items-end justify-between gap-3">
            <span className="font-mono text-2xl font-semibold tracking-tight text-slate-950 tabular-nums">{c.value}</span>
            {c.chart && c.chart.length >= 2 && <Sparkline values={c.chart} />}
          </dd>
          <dd className="mt-1 text-xs text-slate-500">{c.foot}</dd>
        </div>
      ))}
    </dl>
  );
}

const RATING_TONE: Record<string, { bar: string; badge: string }> = {
  Good: { bar: "bg-emerald-500", badge: "border-emerald-300/70 text-emerald-800" },
  OK: { bar: "bg-amber-500", badge: "border-amber-300/70 text-amber-800" },
  Weak: { bar: "bg-rose-500", badge: "border-rose-300/70 text-rose-800" },
};

/** Each score as "0.82 / 1", a bar, a Good/OK/Weak badge and one plain sentence. */
function ScorePanel({ metrics }: { metrics: RunMetric[] }) {
  return (
    <ul className="grid gap-px overflow-hidden rounded-xl bg-slate-200/80 ring-1 ring-slate-200/80 md:grid-cols-2">
      {metrics.map((m) => {
        const tone = RATING_TONE[m.rating];
        const pctWidth = m.mean == null ? 0 : Math.round(Math.max(0, Math.min(1, m.mean)) * 100);
        return (
          <li key={m.key} className="min-w-0 bg-surface p-4 sm:p-5">
            <div className="flex items-baseline justify-between gap-3">
              <p className="text-sm font-semibold text-slate-950">{m.name}</p>
              <span className={cx("shrink-0 rounded-md border px-2 py-0.5 text-xs font-medium", tone?.badge ?? "border-slate-300 text-slate-600")}>
                {m.rating}
              </span>
            </div>
            <p className="mt-0.5 text-xs text-slate-500">{m.question}</p>
            <div className="mt-3 flex items-center gap-3">
              <span className="font-mono text-xl font-semibold tracking-tight text-slate-950 tabular-nums">
                {m.mean == null ? "–" : m.mean.toFixed(2)}
                <span className="text-sm font-normal text-slate-500"> / 1</span>
              </span>
              <span className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-slate-200" aria-hidden>
                <span className={cx("block h-full rounded-full", tone?.bar ?? "bg-slate-400")} style={{ width: `${pctWidth}%` }} />
              </span>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-slate-600">{m.meaning}</p>
          </li>
        );
      })}
    </ul>
  );
}

/** Tiny lime line chart of recent scores (decorative; the number beside it is the data). */
function Sparkline({ values }: { values: number[] }) {
  const w = 84;
  const h = 28;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) => [(i / (values.length - 1)) * w, h - 3 - ((v - min) / span) * (h - 6)] as const);
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const [lx, ly] = pts[pts.length - 1];
  return (
    <svg aria-hidden viewBox={`0 0 ${w} ${h}`} className="h-7 w-[5.25rem] shrink-0 overflow-visible">
      <path d={`${line} L${w} ${h} L0 ${h} Z`} className="fill-accent-400/15" />
      <path d={line} fill="none" strokeWidth="1.75" strokeLinejoin="round" strokeLinecap="round" className="stroke-accent-500" />
      <circle cx={lx} cy={ly} r="2.5" className="fill-accent-400" />
    </svg>
  );
}

function RunRow({ r }: { r: RecentRun }) {
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-4 gap-y-2 px-4 py-4 sm:px-5">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-slate-900" title={r.query}>
          {r.query || r.target || "Untitled run"}
        </p>
        <p className="mt-0.5 truncate font-mono text-2xs text-slate-500" title={fullDate(r.created_at)}>
          {[r.target, timeAgo(r.created_at)].filter(Boolean).join(" · ")}
        </p>
      </div>
      <div className="flex flex-col items-end gap-2">
        <span className="font-mono text-sm font-semibold text-slate-900 tabular-nums">
          {fmtScore(r.overall)}
          <span className="sr-only"> quality score</span>
        </span>
        <span className="flex flex-wrap justify-end gap-1">
          {r.quality && <Badge tone={QUALITY_TONE[r.quality] ?? "muted"}>{humanize(r.quality)}</Badge>}
          <Badge tone={REVIEW_TONE[r.review] ?? "muted"}>{REVIEW_TEXT[r.review] ?? humanize(r.review)}</Badge>
        </span>
      </div>
    </li>
  );
}

function DashboardSkeleton() {
  const bar = "rounded-full bg-slate-200/80 animate-pulse-soft";
  return (
    <div aria-hidden className="space-y-10">
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl bg-slate-200/80 sm:grid-cols-3 lg:grid-cols-5">
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className={cx("bg-surface p-5", i === 4 && "col-span-2 sm:col-span-1")}>
            <div className={cx(bar, "h-2.5 w-20")} />
            <div className={cx(bar, "mt-3 h-7 w-16")} />
            <div className={cx(bar, "mt-3 h-2.5 w-28")} />
          </div>
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className={cx(surface, "space-y-4 p-5")}>
            <div className={cx(bar, "h-4 w-32")} />
            <div className={cx(bar, "h-14 w-full rounded-xl")} />
            <div className={cx(bar, "h-3 w-full")} />
            <div className={cx(bar, "h-3 w-4/5")} />
          </div>
        ))}
      </div>
      <div className={cx(surface, "space-y-3 p-5")}>
        <div className={cx(bar, "h-4 w-48")} />
        <div className={cx(bar, "h-3 w-full")} />
        <div className={cx(bar, "h-3 w-2/3")} />
      </div>
    </div>
  );
}
