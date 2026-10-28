import { Icon } from "@/components/ui/Icon";
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
  error: "failed",
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
  out.push({ id: "review", title: reviewLabel, detail: "Approve or request changes", status: steps.review });
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
          dark ? "bg-indigo-500/20" : "bg-indigo-100",
        )}
      >
        <span className="absolute inset-0 animate-ping rounded-full bg-indigo-400/30" />
        <span className={cx("h-2 w-2 rounded-full", dark ? "bg-indigo-300" : "bg-indigo-600")} />
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
        "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border font-mono text-[10px] font-semibold",
        dark ? "border-white/15 text-slate-500" : "border-slate-300 bg-white text-slate-500",
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
};

/** Full live view of a run, shown while the first draft streams in: the pipeline on
 *  the left (analysts with working bars), a timestamped activity feed on the right. */
export function ProgressStepper({
  steps,
  counts,
  headline,
  elapsed,
  activity,
  showFollowup,
  reviewLabel = "Your review",
  question,
}: Props) {
  const stages = stagesOf(steps, showFollowup, reviewLabel);
  const done = stages.filter((s) => s.status === "done").length;
  const failed = stages.some((s) => s.status === "error");
  const pct = Math.round((done / stages.length) * 100);

  return (
    <section
      aria-labelledby="progress-title"
      className="relative isolate overflow-hidden rounded-2xl bg-ink-950 text-white shadow-[0_30px_70px_-40px_rgb(5_7_13/0.7)] ring-1 ring-ink-700/70"
    >
      <div aria-hidden className="absolute inset-0 -z-10 bg-grid" />
      <div
        aria-hidden
        className="absolute -top-40 left-1/3 -z-10 h-[24rem] w-[40rem] bg-[radial-gradient(closest-side,rgb(79_70_229/0.3),transparent)]"
      />

      <div className="flex flex-wrap items-start justify-between gap-4 px-5 pt-5 pb-4 sm:px-6">
        <div className="min-w-0 flex-1" aria-live="polite">
          <p
            className={cx(
              "flex items-center gap-2 font-mono text-[10.5px] font-medium tracking-[0.18em] uppercase",
              failed ? "text-rose-300" : "text-emerald-300",
            )}
          >
            <span
              aria-hidden
              className={cx("h-1.5 w-1.5 rounded-full", failed ? "bg-rose-400" : "animate-blink bg-emerald-400")}
            />
            {failed ? "Run stopped" : "Live run"}
          </p>
          <h2 id="progress-title" className="mt-2 text-lg font-semibold tracking-tight sm:text-xl">
            {headline}
          </h2>
          {question && <p className="mt-1 truncate text-sm text-slate-400">{question}</p>}
        </div>
        <div className="flex items-center gap-3">
          <span className="font-mono text-[11px] text-slate-400 tabular-nums">
            {done}/{stages.length} stages
          </span>
          {elapsed != null && (
            <span className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 font-mono text-xs text-slate-200 tabular-nums">
              <Icon name="clock" className="h-3.5 w-3.5 text-slate-400" />
              {clock(elapsed)}
              <span className="sr-only"> elapsed</span>
            </span>
          )}
        </div>
      </div>

      <div
        role="progressbar"
        aria-label="Run progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        className="h-px bg-white/[0.08]"
      >
        <div
          className="h-full bg-linear-to-r from-indigo-500 via-sky-400 to-emerald-300 transition-[width] duration-700"
          style={{ width: `${Math.max(pct, 4)}%` }}
        />
      </div>

      <div className="grid lg:grid-cols-[minmax(0,1fr)_20rem]">
        <ol className="space-y-1 p-3 sm:p-4">
          {stages.map((st, i) => (
            <li
              key={st.id}
              className={cx(
                "rounded-xl px-3 py-3 transition-colors",
                st.status === "active" && "bg-white/[0.05] ring-1 ring-white/10",
              )}
            >
              <div className="flex items-center gap-3">
                <Dot status={st.status} n={i + 1} dark />
                <div className="min-w-0 flex-1">
                  <p className={cx("text-sm font-medium", st.status === "idle" ? "text-slate-500" : "text-slate-100")}>
                    {st.title}
                    <span className="sr-only">: {STATUS_TEXT[st.status]}</span>
                  </p>
                  <p className="truncate text-xs text-slate-500">{st.detail}</p>
                </div>
              </div>
              {st.analysts && (
                <ul className="mt-3 grid grid-cols-2 gap-2 pl-9 xl:grid-cols-4">
                  {ANALYSTS.map((a) => {
                    const s = steps[a.id];
                    const count = counts[a.id];
                    return (
                      <li
                        key={a.id}
                        className={cx(
                          "min-w-0 rounded-lg border px-2.5 py-2",
                          s === "done" && "border-emerald-400/20 bg-emerald-400/[0.06]",
                          s === "active" && "border-indigo-400/25 bg-indigo-500/[0.08]",
                          s === "idle" && "border-white/[0.07] bg-white/[0.02]",
                          s === "error" && "border-rose-400/25 bg-rose-400/[0.07]",
                        )}
                      >
                        <p className="truncate text-xs font-medium text-slate-200">
                          {a.label}
                          <span className="sr-only">: {STATUS_TEXT[s]}</span>
                        </p>
                        {s === "done" ? (
                          <p className="truncate font-mono text-[10.5px] text-emerald-300 tabular-nums">
                            {count ?? 0} finding{count === 1 ? "" : "s"}
                          </p>
                        ) : s === "error" ? (
                          <p className="font-mono text-[10.5px] text-rose-300">Failed</p>
                        ) : (
                          <p className="truncate text-[11px] text-slate-500">{a.role}</p>
                        )}
                        <div aria-hidden className="mt-2 h-1 overflow-hidden rounded-full bg-white/[0.06]">
                          {s === "active" && (
                            <div className="h-full animate-scan rounded-full bg-linear-to-r from-indigo-500 via-sky-400 to-emerald-300" />
                          )}
                          {s === "done" && <div className="h-full w-full rounded-full bg-emerald-400/70" />}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </li>
          ))}
        </ol>

        <div className="border-t border-white/[0.08] p-5 lg:border-t-0 lg:border-l">
          <p className="font-mono text-[10.5px] font-medium tracking-[0.18em] text-slate-500 uppercase">Activity</p>
          <ol className="mt-3 space-y-2.5" aria-label="Recent activity">
            {activity.map((a, i) => (
              <li
                key={`${a.at}-${a.text}`}
                className={cx("flex gap-3 text-[13px] leading-snug", i === 0 ? "text-slate-100" : "text-slate-400")}
              >
                <span className="w-9 shrink-0 font-mono text-[11px] text-slate-500 tabular-nums">{clock(a.at)}</span>
                <span className="min-w-0">{a.text}</span>
              </li>
            ))}
          </ol>
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
}: Props & { live: boolean }) {
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
          <p className="font-mono text-[10.5px] text-slate-500 tabular-nums">
            {done}/{stages.length} stages complete
          </p>
        </div>
        {live && elapsed != null ? (
          <span className="flex shrink-0 items-center gap-1.5 rounded-full bg-ink-950 px-2.5 py-1 font-mono text-[11px] text-slate-200 tabular-nums">
            <span aria-hidden className="h-1.5 w-1.5 animate-blink rounded-full bg-emerald-400" />
            {clock(elapsed)}
            <span className="sr-only"> elapsed</span>
          </span>
        ) : (
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-emerald-600 ring-1 ring-emerald-600/20">
            <Icon name="check" className="h-3.5 w-3.5" strokeWidth={3} />
          </span>
        )}
      </header>
      <ol className="relative px-4 py-3">
        <span aria-hidden className="absolute top-6 bottom-6 left-[1.625rem] w-px bg-slate-200" />
        {stages.map((st, i) => (
          <li key={st.id} className="relative flex items-center gap-3 py-1.5">
            <span className="relative flex scale-[0.85] rounded-full bg-white">
              <Dot status={st.status} n={i + 1} />
            </span>
            <span className={cx("min-w-0 flex-1 truncate text-[13px]", st.status === "idle" ? "text-slate-400" : "text-slate-800", st.status === "active" && "font-semibold")}>
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
                      "h-1.5 w-3 rounded-full",
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
                {ANALYSTS.map((a) => `${a.label} ${STATUS_TEXT[steps[a.id]]}${counts[a.id] != null ? `, ${counts[a.id]} findings` : ""}`).join("; ")}
              </span>
            )}
          </li>
        ))}
      </ol>
      {latest && (
        <p className="flex gap-2 border-t border-slate-100 bg-slate-50/60 px-4 py-2.5 text-xs text-slate-600">
          <span className="font-mono text-[11px] text-slate-400 tabular-nums">{clock(latest.at)}</span>
          <span className="min-w-0">{latest.text}</span>
        </p>
      )}
    </section>
  );
}
