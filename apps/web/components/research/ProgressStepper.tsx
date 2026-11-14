import { Icon } from "@/components/ui/Icon";
import { IndeterminateBar } from "@/components/ui/Spinner";
import { cx, surface } from "@/components/ui/styles";

export type StepStatus = "idle" | "active" | "done" | "error";
export type StepId =
  | "plan"
  | "fundamentals"
  | "news_sentiment"
  | "market"
  | "risk"
  | "debate"
  | "followup"
  | "writing"
  | "review";
export type Steps = Record<StepId, StepStatus>;

/** One line of the live activity feed; `at` is seconds since the run started. */
export type ActivityEntry = { text: string; at: number };

/** waking = the server is cold-starting; live = agents are working; stopped = failed. */
export type RunMode = "waking" | "live" | "stopped" | "settled";

export const IDLE_STEPS: Steps = {
  plan: "idle",
  fundamentals: "idle",
  news_sentiment: "idle",
  market: "idle",
  risk: "idle",
  debate: "idle",
  followup: "idle",
  writing: "idle",
  review: "idle",
};

const ANALYSTS: { id: StepId; label: string; role: string }[] = [
  { id: "fundamentals", label: "Fundamentals", role: "Filings · financials" },
  { id: "news_sentiment", label: "News", role: "Headlines · tone" },
  { id: "market", label: "Market", role: "Quotes · competitors" },
  { id: "risk", label: "Risk", role: "Concentration · supply" },
];

const STATUS_TEXT: Record<StepStatus, string> = {
  idle: "waiting",
  active: "in progress",
  done: "done",
  error: "stopped",
};

type Stage = { id: string; title: string; detail: string; status: StepStatus; analysts?: boolean };

function combine(list: StepStatus[]): StepStatus {
  if (list.some((s) => s === "error")) return "error";
  if (list.every((s) => s === "done")) return "done";
  if (list.some((s) => s === "active" || s === "done")) return "active";
  return "idle";
}

function stagesOf(steps: Steps, showFollowup: boolean, reviewLabel: string): Stage[] {
  const out: Stage[] = [
    { id: "plan", title: "Planning", detail: "Scoping the question", status: steps.plan },
    {
      id: "research",
      title: "Research",
      detail: "Four analysts in parallel",
      status: combine(ANALYSTS.map((a) => steps[a.id])),
      analysts: true,
    },
    { id: "debate", title: "Bull vs bear", detail: "Arguing both sides", status: steps.debate },
  ];
  if (showFollowup) out.push({ id: "followup", title: "Follow-up", detail: "Researching your feedback", status: steps.followup });
  out.push({ id: "writing", title: "Writing the brief", detail: "Citing every claim", status: steps.writing });
  out.push({ id: "review", title: reviewLabel, detail: "Approve, revise or reject", status: steps.review });
  return out;
}

export function clock(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

/** Status glyph: shape and icon carry the state, not just colour. */
function Dot({ status, n, dark = false }: { status: StepStatus; n?: number; dark?: boolean }) {
  if (status === "done")
    return (
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-white">
        <Icon name="check" className="h-3.5 w-3.5" strokeWidth={3} />
      </span>
    );
  if (status === "active")
    return (
      <span
        className={cx(
          "relative flex h-6 w-6 shrink-0 items-center justify-center rounded-full",
          dark ? "bg-accent-400/10 ring-1 ring-accent-400/40" : "bg-indigo-50 ring-1 ring-indigo-500/40",
        )}
      >
        <span aria-hidden className={cx("absolute inset-0 animate-halo rounded-full motion-reduce:hidden", dark ? "bg-accent-400/35" : "bg-indigo-400/40")} />
        <span className={cx("h-2 w-2 rounded-full", dark ? "bg-accent-300" : "bg-indigo-600")} />
      </span>
    );
  if (status === "error")
    return (
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-rose-500/15 text-rose-500">
        <Icon name="x" className="h-3.5 w-3.5" strokeWidth={3} />
      </span>
    );
  return (
    <span
      className={cx(
        "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border font-mono text-2xs font-semibold",
        dark ? "border-white/15 text-slate-400" : "border-slate-300 bg-surface text-slate-500",
      )}
    >
      {n}
    </span>
  );
}

type Props = {
  steps: Steps;
  counts: Partial<Record<StepId, number>>;
  headline: string;
  /** Seconds elapsed while a stream is open; omitted when nothing is running. */
  elapsed?: number;
  activity: ActivityEntry[];
  showFollowup: boolean;
  reviewLabel?: string;
  question?: string;
  mode?: RunMode;
};

const MODE_PILL: Record<RunMode, { text: string; cls: string; dot: string }> = {
  waking: { text: "Starting up", cls: "text-accent-300", dot: "bg-accent-300 animate-blink" },
  live: { text: "Live run", cls: "text-accent-300", dot: "bg-accent-400 animate-blink" },
  stopped: { text: "Run stopped", cls: "text-rose-300", dot: "bg-rose-400" },
  settled: { text: "Run", cls: "text-slate-400", dot: "bg-slate-500" },
};

/** Full live view of a run, shown until the first draft arrives: the pipeline on the
 *  left (analysts with working bars), a timestamped activity feed on the right. While
 *  the server cold-starts it explains the wait instead of showing a frozen pipeline. */
export function ProgressStepper({
  steps,
  counts,
  headline,
  elapsed,
  activity,
  showFollowup,
  reviewLabel = "Your review",
  question,
  mode = "live",
  onCancel,
}: Props & { onCancel?: () => void }) {
  const stages = stagesOf(steps, showFollowup, reviewLabel);
  const done = stages.filter((s) => s.status === "done").length;
  const pct = Math.round((done / stages.length) * 100);
  const pill = MODE_PILL[mode];
  const waking = mode === "waking";

  return (
    <section
      aria-labelledby="progress-title"
      className="animate-enter overflow-hidden rounded-xl bg-ink-950 text-white ring-1 ring-ink-700"
    >

      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3 px-5 pt-5 pb-4 sm:px-6">
        <div className="min-w-0 flex-1" aria-live="polite">
          <p className={cx("flex items-center gap-2 font-mono text-2xs font-medium tracking-label uppercase", pill.cls)}>
            <span aria-hidden className={cx("h-1.5 w-1.5 rounded-full", pill.dot)} />
            {pill.text}
          </p>
          <h2 id="progress-title" className="mt-2 text-lg font-semibold tracking-tight text-balance sm:text-xl">
            {headline}
          </h2>
          {question && <p className="mt-1 line-clamp-2 text-sm text-slate-400">{question}</p>}
        </div>
        <div className="flex items-center gap-2">
          {!waking && (
            <span className="hidden font-mono text-2xs text-slate-400 tabular-nums sm:inline">
              {done}/{stages.length} stages
            </span>
          )}
          {elapsed != null && (
            <span className="flex items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 py-1 font-mono text-xs text-slate-200 tabular-nums">
              <Icon name="clock" className="h-3.5 w-3.5 text-slate-400" />
              {clock(elapsed)}
              <span className="sr-only"> elapsed</span>
            </span>
          )}
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="inline-flex items-center rounded-lg border border-white/15 px-3 py-1 text-xs font-medium text-slate-300 transition-colors hover:border-white/25 hover:bg-white/5 hover:text-white pointer-coarse:min-h-11"
            >
              Cancel
            </button>
          )}
        </div>
      </div>

      {waking ? (
        <IndeterminateBar tone="dark" className="mx-5 h-px rounded-none sm:mx-6" />
      ) : (
        <div
          role="progressbar"
          aria-label="Run progress"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct}
          className="mx-5 h-px bg-white/[0.08] sm:mx-6"
        >
          <div
            className="h-full bg-linear-to-r from-accent-500 to-accent-300 transition-[width] duration-700 ease-out"
            style={{ width: `${Math.max(pct, 3)}%` }}
          />
        </div>
      )}

      <div className="grid lg:grid-cols-[minmax(0,1fr)_20rem]">
        <ol className={cx("space-y-0.5 p-3 transition-opacity duration-500 sm:p-4", waking && "opacity-45")}>
          {stages.map((st, i) => (
            <li
              key={st.id}
              className={cx(
                "rounded-xl px-3 py-2 transition-colors duration-300",
                st.status === "active" && "bg-white/[0.04] ring-1 ring-white/[0.08]",
              )}
            >
              <div className="flex items-center gap-3">
                <Dot status={st.status} n={i + 1} dark />
                <div className="min-w-0 flex-1">
                  <p
                    className={cx(
                      "text-sm font-medium transition-colors",
                      st.status === "idle" ? "text-slate-400" : "text-slate-100",
                    )}
                  >
                    {st.title}
                    <span className="sr-only">: {STATUS_TEXT[st.status]}</span>
                  </p>
                  <p className="truncate text-xs text-slate-400">{st.detail}</p>
                </div>
              </div>
              {st.analysts && (
                <ul className="mt-3 grid grid-cols-2 gap-2 sm:pl-9 xl:grid-cols-4">
                  {ANALYSTS.map((a) => {
                    const s = steps[a.id];
                    const count = counts[a.id];
                    return (
                      <li
                        key={a.id}
                        className={cx(
                          "min-w-0 rounded-lg border px-2 py-2 transition-colors duration-500",
                          s === "done" && "border-emerald-400/20 bg-emerald-400/[0.05]",
                          s === "active" && "border-accent-400/20 bg-accent-400/[0.05]",
                          s === "idle" && "border-white/[0.06] bg-white/[0.015]",
                          s === "error" && "border-rose-400/25 bg-rose-400/[0.06]",
                        )}
                      >
                        <p className="truncate text-xs font-medium text-slate-200">
                          {a.label}
                          <span className="sr-only">: {STATUS_TEXT[s]}</span>
                        </p>
                        {s === "done" ? (
                          <p className="truncate font-mono text-2xs text-emerald-300 tabular-nums">
                            {count ?? 0} finding{count === 1 ? "" : "s"}
                          </p>
                        ) : s === "error" ? (
                          <p className="font-mono text-2xs text-rose-300">Stopped</p>
                        ) : (
                          <p className="truncate text-2xs text-slate-400">{a.role}</p>
                        )}
                        <div aria-hidden className="mt-2 h-0.5 overflow-hidden rounded-full bg-white/[0.06]">
                          {s === "active" && (
                            <div className="h-full animate-scan rounded-full bg-linear-to-r from-accent-500 to-accent-300 motion-reduce:w-1/2" />
                          )}
                          {s === "done" && <div className="h-full w-full rounded-full bg-emerald-400/60" />}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </li>
          ))}
        </ol>

        <div className="border-t border-white/[0.07] p-5 lg:border-t-0 lg:border-l">
          {waking ? (
            <div className="animate-enter">
              <p className="font-mono text-2xs font-medium tracking-label text-slate-400 uppercase">Why the wait</p>
              <p className="mt-3 text-sm leading-relaxed text-slate-300">
                Atlas runs on a free server that naps when nobody is using it. The first run after a break takes up to a
                minute to boot; after that, runs start straight away.
              </p>
              <p className="mt-3 text-sm leading-relaxed text-slate-400">
                Your question is queued. The analysts start the moment the server answers.
              </p>
            </div>
          ) : (
            <>
              <p className="font-mono text-2xs font-medium tracking-label text-slate-400 uppercase">Activity</p>
              <ol className="mt-3 space-y-2" aria-label="Recent activity">
                {activity.map((a, i) => (
                  <li
                    key={`${a.at}-${a.text}`}
                    className={cx(
                      "flex gap-3 text-sm leading-snug transition-colors duration-500",
                      i === 0 ? "animate-enter text-slate-100" : "text-slate-400",
                    )}
                  >
                    <span className="w-9 shrink-0 font-mono text-2xs text-slate-400 tabular-nums">{clock(a.at)}</span>
                    <span className="min-w-0">{a.text}</span>
                  </li>
                ))}
              </ol>
            </>
          )}
        </div>
      </div>
    </section>
  );
}

/** Compact run status for the workspace rail, shown once a draft exists. */
export function RunCard({
  steps,
  counts,
  headline,
  elapsed,
  activity,
  showFollowup,
  reviewLabel = "Your review",
  live,
  outcome,
}: Props & { live: boolean; outcome?: "approved" | "rejected" | "stopped" }) {
  const stages = stagesOf(steps, showFollowup, reviewLabel);
  const done = stages.filter((s) => s.status === "done").length;
  const latest = activity[0];

  return (
    <section aria-labelledby="run-title" className={cx(surface, "overflow-hidden")}>
      <header className="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
        <div className="min-w-0" aria-live="polite">
          <h2 id="run-title" className="truncate text-sm font-semibold text-slate-900">
            {headline}
          </h2>
          <p className="font-mono text-2xs text-slate-500 tabular-nums">
            {done}/{stages.length} stages complete
          </p>
        </div>
        {live && elapsed != null ? (
          <span className="flex shrink-0 items-center gap-2 rounded-md bg-ink-950 px-2 py-1 font-mono text-2xs text-slate-200 tabular-nums">
            <span aria-hidden className="h-1.5 w-1.5 animate-blink rounded-full bg-emerald-400" />
            {clock(elapsed)}
            <span className="sr-only"> elapsed</span>
          </span>
        ) : outcome === "rejected" || outcome === "stopped" ? (
          <span
            className={cx(
              "flex h-6 w-6 shrink-0 items-center justify-center rounded-full ring-1",
              outcome === "rejected" ? "bg-rose-50 text-rose-700 ring-rose-600/20" : "bg-amber-50 text-amber-700 ring-amber-600/25",
            )}
          >
            <Icon name={outcome === "rejected" ? "x" : "alert"} className="h-3.5 w-3.5" strokeWidth={2.5} />
          </span>
        ) : (
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/20">
            <Icon name="check" className="h-3.5 w-3.5" strokeWidth={3} />
          </span>
        )}
      </header>
      <ol className="relative px-4 py-3">
        <span aria-hidden className="absolute top-6 bottom-6 left-[1.625rem] w-px bg-slate-200" />
        {stages.map((st, i) => (
          <li key={st.id} className="relative flex items-center gap-3 py-2">
            <span className="relative flex scale-[0.85] rounded-full bg-surface">
              <Dot status={st.status} n={i + 1} />
            </span>
            <span
              className={cx(
                "min-w-0 flex-1 truncate text-sm transition-colors",
                st.status === "idle" ? "text-slate-500" : "text-slate-800",
                st.status === "active" && "font-semibold",
              )}
            >
              {st.title}
              <span className="sr-only">: {STATUS_TEXT[st.status]}</span>
            </span>
            {st.analysts && st.status !== "idle" && (
              <span className="flex shrink-0 gap-1" aria-hidden>
                {ANALYSTS.map((a) => (
                  <span
                    key={a.id}
                    title={`${a.label}: ${STATUS_TEXT[steps[a.id]]}`}
                    className={cx(
                      "h-1.5 w-3 rounded-full transition-colors duration-500",
                      steps[a.id] === "done" && "bg-emerald-500",
                      steps[a.id] === "active" && "animate-pulse-soft bg-indigo-500",
                      steps[a.id] === "idle" && "bg-slate-200",
                      steps[a.id] === "error" && "bg-rose-500",
                    )}
                  />
                ))}
              </span>
            )}
            {st.analysts && (
              <span className="sr-only">
                {ANALYSTS.map(
                  (a) =>
                    `${a.label} ${STATUS_TEXT[steps[a.id]]}${counts[a.id] != null ? `, ${counts[a.id]} findings` : ""}`,
                ).join("; ")}
              </span>
            )}
          </li>
        ))}
      </ol>
      {latest && (
        <p
          key={`${latest.at}-${latest.text}`}
          className="flex animate-enter gap-2 border-t border-slate-100 bg-slate-50/60 px-4 py-2 text-xs text-slate-600"
        >
          <span className="font-mono text-2xs text-slate-500 tabular-nums">{clock(latest.at)}</span>
          <span className="min-w-0">{latest.text}</span>
        </p>
      )}
    </section>
  );
}
