import { type Experiment, isPending, type Lever } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Icon, type IconName } from "@/components/ui/Icon";
import { cx, limePill, monoLabel, surface } from "@/components/ui/styles";
import { direction, fmtDelta, fmtScore, fullDate, timeAgo } from "./format";

export const LEVER: Record<Lever, { label: string; icon: IconName; hint: string }> = {
  lesson: { label: "Learned lesson", icon: "spark", hint: "A written rule added to the agent's playbook" },
  exemplars: { label: "Exemplars", icon: "layers", hint: "Worked examples shown to the agent" },
  retrieval: { label: "Retrieval depth", icon: "database", hint: "How many evidence passages the agent reads" },
};

const DELTA_TEXT = { up: "text-emerald-700", down: "text-rose-700", flat: "text-slate-500" } as const;

/** Delta with an arrow: shape and sign carry the direction, not colour alone. */
export function Delta({ value, className }: { value: number; className?: string }) {
  const d = direction(value);
  return (
    <span className={cx("inline-flex items-center justify-end gap-1 font-mono tabular-nums", DELTA_TEXT[d], className)}>
      {d !== "flat" && (
        <Icon name={d === "up" ? "trending" : "trendingDown"} className="h-3.5 w-3.5 shrink-0" strokeWidth={2.25} />
      )}
      {fmtDelta(value)}
    </span>
  );
}

/** Render a policy value of unknown shape: text, a number, a list, or JSON. */
export function PolicyValue({ value }: { value: unknown }) {
  if (value == null || value === "") return <span className="text-slate-500 italic">none</span>;
  if (typeof value === "string") return <span className="whitespace-pre-wrap">{value}</span>;
  if (typeof value === "number" || typeof value === "boolean")
    return <span className="font-mono tabular-nums">{String(value)}</span>;
  if (Array.isArray(value) && value.every((v) => typeof v === "string" || typeof v === "number")) {
    if (!value.length) return <span className="text-slate-500 italic">none</span>;
    return (
      <ul className="space-y-2">
        {value.map((v, i) => (
          <li key={i} className="flex gap-2">
            <span aria-hidden className="mt-2 h-1 w-1 shrink-0 rounded-full bg-current opacity-50" />
            <span className="min-w-0">{String(v)}</span>
          </li>
        ))}
      </ul>
    );
  }
  return (
    <pre className="max-h-48 overflow-auto font-mono text-2xs leading-relaxed whitespace-pre-wrap [overflow-wrap:anywhere]">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <li className="relative grid grid-cols-[1.75rem_minmax(0,1fr)] gap-x-3 pb-6 last:pb-0">
      <span aria-hidden className="absolute top-7 bottom-0 left-[0.8125rem] w-px bg-slate-200" />
      <span
        aria-hidden
        className="relative flex h-7 w-7 items-center justify-center rounded-full bg-surface font-mono text-2xs font-semibold text-indigo-700 ring-1 ring-slate-200"
      >
        {n}
      </span>
      <div className="min-w-0 pt-1">
        <p className={cx(monoLabel, "text-slate-500")}>{title}</p>
        <div className="mt-2">{children}</div>
      </div>
    </li>
  );
}

/** Baseline vs candidate per query, with the mean change. Stacked rows on phones, a
 *  table from `sm` up. */
export function TrialResults({ exp }: { exp: Experiment }) {
  const trials = exp.trials ?? [];
  const wins = trials.filter((t) => direction(t.delta) === "up").length;
  const losses = trials.filter((t) => direction(t.delta) === "down").length;
  return (
    trials.length ? (
      <>
      {/* Narrow screens: one stacked row per query, so the question can breathe. */}
      <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200/80 sm:hidden">
        {trials.map((t, i) => (
          <li key={i} className="px-3 py-2">
            <p className="text-sm leading-snug text-slate-700 [overflow-wrap:anywhere]">{t.query}</p>
            <p className="mt-2 flex items-center gap-3 font-mono text-xs text-slate-500 tabular-nums">
              <span>
                base <span className="text-slate-700">{fmtScore(t.baseline)}</span>
              </span>
              <span>
                new <span className="font-medium text-slate-900">{fmtScore(t.candidate)}</span>
              </span>
              <Delta value={t.delta} className="ml-auto" />
            </p>
          </li>
        ))}
        <li className="flex items-center justify-between gap-3 bg-slate-50/70 px-3 py-2 text-xs font-medium text-slate-600">
          <span>
            Mean change · {wins} better, {losses} worse
          </span>
          <Delta value={exp.mean_delta} className="font-semibold" />
        </li>
      </ul>
      <div className="hidden overflow-x-auto rounded-xl border border-slate-200/80 sm:block">
        <table className="w-full min-w-[22rem] text-sm">
          <caption className="sr-only">
            Baseline versus candidate score for each query. Higher is better.
          </caption>
          <thead>
            <tr className={cx(monoLabel, "border-b border-slate-200/80 bg-slate-50/70 text-slate-500")}>
              <th scope="col" className="px-3 py-2 text-left font-medium">
                Query
              </th>
              <th scope="col" className="w-20 px-3 py-2 text-right font-medium">
                Baseline
              </th>
              <th scope="col" className="w-20 px-3 py-2 text-right font-medium">
                Candidate
              </th>
              <th scope="col" className="w-20 px-3 py-2 text-right font-medium">
                Δ
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {trials.map((t, i) => (
              <tr key={i} className="align-top">
                <td className="px-3 py-2 leading-snug text-slate-700 [overflow-wrap:anywhere]">{t.query}</td>
                <td className="px-3 py-2 text-right font-mono text-slate-500 tabular-nums">
                  {fmtScore(t.baseline)}
                </td>
                <td className="px-3 py-2 text-right font-mono font-medium text-slate-900 tabular-nums">
                  {fmtScore(t.candidate)}
                </td>
                <td className="px-3 py-2 text-right">
                  <Delta value={t.delta} />
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-slate-200/80 bg-slate-50/70">
              <th scope="row" colSpan={3} className="px-3 py-2 text-left text-xs font-medium text-slate-600">
                Mean change · {wins} better, {losses} worse
                {trials.length - wins - losses > 0 && `, ${trials.length - wins - losses} tied`}
              </th>
              <td className="px-3 py-2 text-right">
                <Delta value={exp.mean_delta} className="font-semibold" />
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
      </>
    ) : (
      <p className="text-sm text-slate-500 italic">No trial results were recorded.</p>
    )
  );
}

export function ExperimentCard({
  exp,
  label,
  defaultOpen = false,
  highlight = false,
}: {
  exp: Experiment;
  /** Display name of the component under test. */
  label: string;
  defaultOpen?: boolean;
  highlight?: boolean;
}) {
  const released = exp.decision === "released";
  const pending = isPending(exp);
  const lever = LEVER[exp.lever] ?? { label: exp.lever, icon: "spark" as IconName, hint: "" };
  const trials = exp.trials ?? [];

  return (
    <li
      id={`exp-${exp.id}`}
      className={cx(
        surface,
        "scroll-mt-24 overflow-hidden transition-shadow duration-700",
        highlight && "animate-enter ring-2 ring-accent-400/70 shadow-[0_0_60px_-20px_var(--color-accent-400)]",
      )}
    >
      <details open={defaultOpen} className="group">
        <summary className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-4 sm:px-5">
          <span className="flex min-w-0 flex-1 items-center gap-3">
            <span
              aria-hidden
              className={cx(
                "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ring-1",
                released ? "bg-accent-400/15 text-indigo-700 ring-accent-400/40" : "bg-slate-100 text-slate-600 ring-slate-500/15",
              )}
            >
              <Icon name={lever.icon} className="h-4.5 w-4.5" />
            </span>
            <span className="min-w-0">
              <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="text-base font-semibold text-slate-950">{label}</span>
                <span className="text-sm text-slate-500">· {lever.label}</span>
              </span>
              <span className="mt-0.5 block truncate text-sm text-slate-600">{exp.change?.summary || exp.hypothesis}</span>
            </span>
          </span>
          <span className="flex w-full items-center gap-3 pl-12 sm:w-auto sm:pl-0">
            <Delta value={exp.mean_delta} className="text-sm font-semibold" />
            {released ? (
              <span className={limePill}>
                <Icon name="check" className="h-3 w-3" strokeWidth={3} />
                Released
              </span>
            ) : pending ? (
              <Badge tone="mid" dot>
                Awaiting approval
              </Badge>
            ) : (
              <Badge tone="muted" dot>
                Not released
              </Badge>
            )}
            <Icon name="chevron" className="chevron ml-auto h-5 w-5 shrink-0 text-slate-400 transition-transform sm:ml-0" />
          </span>
        </summary>

        <div className="border-t border-slate-100 px-4 pt-5 pb-6 sm:px-5">
          <p className="mb-5 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-2xs text-slate-500">
            <span title={fullDate(exp.created_at)}>{timeAgo(exp.created_at) || fullDate(exp.created_at)}</span>
            <span aria-hidden>·</span>
            <span>
              v{exp.version_before}
              {released && exp.version_after != null ? ` → v${exp.version_after}` : " (unchanged)"}
            </span>
            <span aria-hidden>·</span>
            <span>
              {trials.length} paired quer{trials.length === 1 ? "y" : "ies"}
            </span>
          </p>

          <ol className="[&>li:last-child>span:first-child]:hidden">
            <Step n={1} title="Hypothesis">
              <p className="max-w-[72ch] text-base leading-7 text-slate-800">{exp.hypothesis}</p>
            </Step>

            <Step n={2} title="Change">
              {exp.change?.summary && <p className="text-sm font-medium text-slate-900">{exp.change.summary}</p>}
              {lever.hint && <p className="mt-0.5 text-xs text-slate-500">{lever.hint}</p>}
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                <div className="min-w-0 rounded-xl border border-slate-200/80 bg-slate-50/70 p-3 text-sm text-slate-700">
                  <p className={cx(monoLabel, "mb-2 text-slate-500")}>Before</p>
                  <PolicyValue value={exp.change?.before} />
                </div>
                <div className="min-w-0 rounded-xl border border-indigo-200/80 bg-indigo-50/50 p-3 text-sm text-slate-800">
                  <p className={cx(monoLabel, "mb-2 text-indigo-700")}>After</p>
                  <PolicyValue value={exp.change?.after} />
                </div>
              </div>
            </Step>

            <Step n={3} title="Paired trial">
              <TrialResults exp={exp} />
            </Step>

            <Step n={4} title="Decision">
              <div
                className={cx(
                  "flex gap-3 rounded-xl border p-4",
                  released ? "border-accent-400/40 bg-accent-400/[0.07]" : "border-slate-200/80 bg-slate-50/60",
                )}
              >
                <span
                  aria-hidden
                  className={cx(
                    "flex h-6 w-6 shrink-0 items-center justify-center rounded-full",
                    released ? "bg-accent-400 text-ink-950" : "bg-slate-500 text-white",
                  )}
                >
                  <Icon name={released ? "check" : "x"} className="h-3.5 w-3.5" strokeWidth={3} />
                </span>
                <div className="min-w-0 text-sm">
                  <p className="font-semibold text-slate-900">
                    {released
                      ? `Released as v${exp.version_after ?? exp.version_before + 1}`
                      : pending
                        ? `Passed replay · waiting for an admin to approve`
                        : `Rejected · v${exp.version_before} stays active`}
                  </p>
                  {exp.reason && <p className="mt-0.5 leading-relaxed text-slate-700">{exp.reason}</p>}
                </div>
              </div>
            </Step>
          </ol>
        </div>
      </details>
    </li>
  );
}
