import type { ReportSections, Risk } from "@/lib/api";
import { hasText, nonEmpty } from "@/lib/citations";
import { cx, toneDot, toneOf } from "@/components/ui/styles";
import { LevelPill } from "../bits";
import { CitedOrMuted, Section, type Ctx } from "../Section";

type P = { s: ReportSections; c: Ctx; n?: number };

const ORDER: Record<string, number> = { high: 0, medium: 1, moderate: 1, low: 2 };
const rank = (r: Risk) => ORDER[(r.severity ?? "").toLowerCase().trim()] ?? 3;

const rowsOf = (s: ReportSections) =>
  (s.risks ?? []).filter((r) => hasText(r?.title) || hasText(r?.detail)).sort((a, b) => rank(a) - rank(b));

export const hasRisks = (s: ReportSections) => nonEmpty(rowsOf(s));

/** Risk register: sorted high → low, a severity stripe and pill on every row. */
export function Risks({ s, c, n }: P) {
  const rows = rowsOf(s);
  if (!nonEmpty(rows)) return null;
  const counts = (["high", "medium", "low"] as const)
    .map((lvl) => [lvl, rows.filter((r) => rank(r) === ORDER[lvl]).length] as const)
    .filter(([, k]) => k > 0);

  return (
    <Section
      c={c}
      id="risks"
      n={n}
      title="Key risks"
      description="What could go wrong, most severe first."
      aside={
        counts.length > 0 ? (
          <span className="flex flex-wrap items-center gap-3 font-mono text-[11px] text-slate-500">
            {counts.map(([lvl, k]) => (
              <span key={lvl} className="inline-flex items-center gap-1.5">
                <span aria-hidden className={cx("h-1.5 w-1.5 rounded-full", toneDot[toneOf(lvl)])} />
                {k} {lvl}
              </span>
            ))}
          </span>
        ) : undefined
      }
    >
      <ol className="overflow-hidden rounded-xl border border-slate-200/80 divide-y divide-slate-100">
        {rows.map((r, i) => {
          const tone = toneOf(r.severity);
          return (
            <li
              key={i}
              className="relative grid gap-x-6 gap-y-2 py-4 pr-4 pl-6 transition-colors hover:bg-slate-50/60 @xl:grid-cols-[minmax(0,15rem)_minmax(0,1fr)]"
            >
              <span aria-hidden className={cx("absolute top-4 bottom-4 left-0 w-[3px] rounded-r-full", toneDot[tone])} />
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[11px] text-slate-400 tabular-nums">R{i + 1}</span>
                  <LevelPill value={r.severity} />
                </div>
                {hasText(r.title) && (
                  <p className="mt-2 text-[15px] leading-snug font-semibold text-slate-900">{r.title}</p>
                )}
              </div>
              {hasText(r.detail) && (
                <p className="min-w-0 text-sm leading-relaxed text-slate-700 @xl:pt-0.5">
                  <CitedOrMuted text={r.detail} c={c} />
                </p>
              )}
            </li>
          );
        })}
      </ol>
    </Section>
  );
}
