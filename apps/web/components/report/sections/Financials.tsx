import type { Metric, ReportSections } from "@/lib/api";
import { citationKey, hasText, nonEmpty, splitCitations } from "@/lib/citations";
import { cx } from "@/components/ui/styles";
import { SourceChip } from "../Cited";
import { Prose, Section, type Ctx } from "../Section";

function changeTone(change: string): string {
  const t = change.trim();
  if (/^[+▲]|\bup\b|increase|growth/i.test(t)) return "text-emerald-700";
  if (/^[-−▼]|\bdown\b|decline|decrease/i.test(t)) return "text-rose-700";
  return "text-slate-500";
}

function MetricTile({ m, c }: { m: Metric; c: Ctx }) {
  const cites = m.citation ? splitCitations(m.citation).filter((x) => x.type === "cite") : [];
  return (
    <li className="flex min-w-0 flex-col rounded-lg border border-slate-200 bg-slate-50/60 p-4">
      <span className="text-xs font-medium text-slate-500">{m.label}</span>
      <span className="mt-1 text-2xl font-semibold tracking-tight text-slate-900 tabular-nums">
        {m.value}
      </span>
      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-2">
        {hasText(m.change) ? (
          <span className={cx("text-xs font-medium", changeTone(m.change))}>{m.change}</span>
        ) : (
          <span />
        )}
        {cites.map((x, i) =>
          x.type === "cite" ? <SourceChip key={i} label={x.label} sourceKey={x.key} ns={c.ns} /> : null,
        )}
        {!cites.length && hasText(m.citation) && (
          <SourceChip label={m.citation} sourceKey={citationKey(m.citation)} ns={c.ns} />
        )}
      </div>
    </li>
  );
}

export function Financials({ s, c }: { s: ReportSections; c: Ctx }) {
  const f = s.financials;
  const metrics = (f?.metrics ?? []).filter((m) => hasText(m?.value) || hasText(m?.label));
  if (!f || !(hasText(f.summary) || nonEmpty(metrics))) return null;
  return (
    <Section c={c} id="financials" title="Financials">
      {nonEmpty(metrics) && (
        <ul className="mb-4 grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 lg:grid-cols-4">
          {metrics.map((m, i) => (
            <MetricTile key={i} m={m} c={c} />
          ))}
        </ul>
      )}
      <Prose text={f.summary} c={c} />
    </Section>
  );
}
