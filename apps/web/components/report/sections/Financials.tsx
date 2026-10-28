import type { Metric, ReportSections } from "@/lib/api";
import { hasText, isPlaceholder, nonEmpty } from "@/lib/citations";
import { cx } from "@/components/ui/styles";
import { CiteChips, Trend } from "../bits";
import { Prose, Section, type Ctx } from "../Section";

type P = { s: ReportSections; c: Ctx; n?: number };

const usable = (m: Metric | undefined) => !!m && (hasText(m.value) || hasText(m.label));

export const hasFinancials = (s: ReportSections) => {
  const f = s.financials;
  return !!f && (hasText(f.summary) || nonEmpty((f.metrics ?? []).filter(usable)));
};

/** KPI card: label + source on top, the figure large, the change as a trend line. */
function MetricCard({ m, c }: { m: Metric; c: Ctx }) {
  const placeholder = isPlaceholder(m.value);
  const long = (m.value ?? "").length > 11;
  return (
    <li className="flex min-w-0 flex-col rounded-xl border border-slate-200/80 bg-linear-to-b from-slate-50/90 to-white p-4 shadow-[0_1px_2px_rgb(15_23_42/0.04)]">
      <div className="flex items-start justify-between gap-2">
        <span className="min-w-0 text-xs leading-snug font-medium text-slate-500">{m.label}</span>
        <span className="-mt-0.5 shrink-0">
          <CiteChips citation={m.citation} ns={c.ns} />
        </span>
      </div>
      {placeholder ? (
        <span className="mt-3 text-sm text-slate-500 italic">{m.value}</span>
      ) : (
        <span
          className={cx(
            "mt-2 font-mono font-semibold tracking-tight text-slate-950 tabular-nums [overflow-wrap:anywhere]",
            long ? "text-lg leading-snug" : "text-[1.65rem] leading-tight",
          )}
        >
          {m.value || "—"}
        </span>
      )}
      {hasText(m.change) && (
        <div className="mt-auto border-t border-dashed border-slate-200 pt-2.5 [&>span]:mt-0">
          <Trend change={m.change} />
        </div>
      )}
    </li>
  );
}

export function Financials({ s, c, n }: P) {
  const f = s.financials;
  if (!f || !hasFinancials(s)) return null;
  const metrics = (f.metrics ?? []).filter(usable);
  return (
    <Section
      c={c}
      id="financials"
      n={n}
      title="Financials"
      description="Headline figures and the trend behind them."
      aside={
        nonEmpty(metrics) ? (
          <span className="font-mono text-[11px] text-slate-400">
            {metrics.length} figure{metrics.length === 1 ? "" : "s"}
          </span>
        ) : undefined
      }
    >
      {nonEmpty(metrics) && (
        <ul className="grid grid-cols-1 gap-3 @md:grid-cols-2 @3xl:grid-cols-4 [&>li]:min-h-[8.5rem]">
          {metrics.map((m, i) => (
            <MetricCard key={i} m={m} c={c} />
          ))}
        </ul>
      )}
      <Prose text={f.summary} c={c} className={cx(nonEmpty(metrics) && "mt-6")} />
    </Section>
  );
}
