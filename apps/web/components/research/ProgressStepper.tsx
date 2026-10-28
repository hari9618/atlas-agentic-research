import { Icon } from "@/components/ui/Icon";
import { card, cx } from "@/components/ui/styles";

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

const PARALLEL: { id: StepId; label: string }[] = [
  { id: "fundamentals", label: "Fundamentals" },
  { id: "news_sentiment", label: "News" },
  { id: "market", label: "Market" },
  { id: "risk", label: "Risk" },
];

function Dot({ status, n }: { status: StepStatus; n?: number }) {
  if (status === "done")
    return (
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-white">
        <Icon name="check" className="h-3.5 w-3.5" strokeWidth={3} />
      </span>
    );
  if (status === "active")
    return (
      <span className="relative flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-100">
        <span className="absolute inset-0 animate-ping rounded-full bg-indigo-400/40" />
        <span className="h-2.5 w-2.5 rounded-full bg-indigo-600" />
      </span>
    );
  if (status === "error")
    return (
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-rose-100 text-rose-700">
        <Icon name="x" className="h-3.5 w-3.5" strokeWidth={3} />
      </span>
    );
  return (
    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-slate-300 bg-white text-[11px] font-semibold text-slate-500">
      {n}
    </span>
  );
}

const STATUS_TEXT: Record<StepStatus, string> = {
  idle: "waiting",
  active: "in progress",
  done: "done",
  error: "failed",
};

function Stage({
  n,
  title,
  status,
  detail,
  children,
}: {
  n: number;
  title: string;
  status: StepStatus;
  detail?: string;
  children?: React.ReactNode;
}) {
  return (
    <li
      className={cx(
        "rounded-xl border p-3 transition-colors",
        status === "active" && "border-indigo-300 bg-indigo-50/60",
        status === "done" && "border-emerald-200 bg-white",
        status === "idle" && "border-slate-200 bg-white",
        status === "error" && "border-rose-200 bg-rose-50/50",
      )}
    >
      <div className="flex items-center gap-2.5">
        <Dot status={status} n={n} />
        <div className="min-w-0">
          <p className={cx("text-sm font-semibold", status === "idle" ? "text-slate-500" : "text-slate-900")}>
            {title}
            <span className="sr-only">: {STATUS_TEXT[status]}</span>
          </p>
          {detail && <p className="truncate text-xs text-slate-500">{detail}</p>}
        </div>
      </div>
      {children}
    </li>
  );
}

function combine(list: StepStatus[]): StepStatus {
  if (list.some((s) => s === "error")) return "error";
  if (list.every((s) => s === "done")) return "done";
  if (list.some((s) => s === "active" || s === "done")) return "active";
  return "idle";
}

/** Compact live view of the agent pipeline, driven by SSE node events. */
export function ProgressStepper({
  steps,
  counts,
  headline,
  elapsed,
  activity,
  showFollowup,
  reviewLabel = "Your review",
}: {
  steps: Steps;
  counts: Partial<Record<StepId, number>>;
  headline: string;
  elapsed?: number;
  activity: string[];
  showFollowup: boolean;
  reviewLabel?: string;
}) {
  const research = combine(PARALLEL.map((p) => steps[p.id]));
  const mm = elapsed != null ? `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}` : null;
  let n = 0;

  return (
    <section aria-labelledby="progress-title" className={cx(card, "p-4 sm:p-5")}>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0" aria-live="polite">
          <h2 id="progress-title" className="text-base font-semibold tracking-tight text-slate-950">
            {headline}
          </h2>
          {activity[0] && <p className="mt-0.5 truncate text-xs text-slate-500">{activity[0]}</p>}
        </div>
        {mm && (
          <span className="flex items-center gap-2 rounded-full bg-ink-950 px-3 py-1 font-mono text-xs text-slate-200 tabular-nums">
            <span aria-hidden className="h-1.5 w-1.5 animate-blink rounded-full bg-emerald-400" />
            {mm}
            <span className="sr-only"> elapsed</span>
          </span>
        )}
      </div>

      <ol className={cx("grid gap-2.5", showFollowup ? "lg:grid-cols-6" : "lg:grid-cols-5")}>
        <Stage n={++n} title="Planning" status={steps.plan} detail="Scoping the question" />
        <Stage n={++n} title="Research" status={research} detail="Four analysts in parallel" >
          <ul className="mt-2.5 grid grid-cols-2 gap-1.5">
            {PARALLEL.map((p) => {
              const st = steps[p.id];
              const count = counts[p.id];
              return (
                <li
                  key={p.id}
                  className={cx(
                    "flex items-center gap-1.5 rounded-md px-2 py-1 text-xs",
                    st === "done" && "bg-emerald-50 text-emerald-800",
                    st === "active" && "bg-indigo-100/70 text-indigo-800",
                    st === "idle" && "bg-slate-50 text-slate-500",
                    st === "error" && "bg-rose-50 text-rose-800",
                  )}
                >
                  <span
                    aria-hidden
                    className={cx(
                      "h-1.5 w-1.5 shrink-0 rounded-full",
                      st === "done" && "bg-emerald-500",
                      st === "active" && "animate-pulse-soft bg-indigo-500",
                      st === "idle" && "bg-slate-300",
                      st === "error" && "bg-rose-500",
                    )}
                  />
                  <span className="truncate">{p.label}</span>
                  {count != null && st === "done" && (
                    <span className="ml-auto tabular-nums" aria-label={`${count} findings`}>
                      {count}
                    </span>
                  )}
                  <span className="sr-only">: {STATUS_TEXT[st]}</span>
                </li>
              );
            })}
          </ul>
        </Stage>
        <Stage n={++n} title="Bull vs bear" status={steps.debate} detail="Arguing both sides" />
        {showFollowup && (
          <Stage n={++n} title="Follow-up" status={steps.followup} detail="Researching your feedback" />
        )}
        <Stage n={++n} title="Writing report" status={steps.writing} detail="Citing every claim" />
        <Stage n={++n} title={reviewLabel} status={steps.review} detail="Approve or request changes" />
      </ol>
    </section>
  );
}
