import type { ReportSections } from "@/lib/api";
import { hasText, nonEmpty } from "@/lib/citations";
import { Icon } from "@/components/ui/Icon";
import { cx, monoLabel } from "@/components/ui/styles";
import { LevelPill, Monogram } from "../bits";
import { CitedOrMuted, Prose, Section, type Ctx } from "../Section";

type P = { s: ReportSections; c: Ctx; n?: number };

export const hasMarketPosition = (s: ReportSections) => {
  const m = s.market_position;
  return !!m && (hasText(m.summary) || nonEmpty((m.strengths ?? []).filter(hasText)) || nonEmpty((m.weaknesses ?? []).filter(hasText)));
};

/** A titled column of points with a header strip (strengths / weaknesses). */
function Ledger({ kind, items, c }: { kind: "good" | "bad"; items: string[]; c: Ctx }) {
  const good = kind === "good";
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200/80">
      <div className="flex items-center justify-between gap-3 border-b border-slate-200/80 bg-slate-50/70 px-4 py-2.5">
        <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          <span
            aria-hidden
            className={cx(
              "flex h-5 w-5 items-center justify-center rounded-md",
              good ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700",
            )}
          >
            <Icon name={good ? "plus" : "minus"} className="h-3 w-3" strokeWidth={3} />
          </span>
          {good ? "Strengths" : "Weaknesses"}
        </p>
        <span className="font-mono text-[11px] text-slate-400 tabular-nums">{items.length}</span>
      </div>
      <ul className="divide-y divide-slate-100">
        {items.map((item, i) => (
          <li key={i} className="flex gap-3 px-4 py-3 text-sm leading-relaxed text-slate-700">
            <span
              aria-hidden
              className={cx("mt-[0.55rem] h-1.5 w-1.5 shrink-0 rounded-full", good ? "bg-emerald-500" : "bg-rose-500")}
            />
            <span className="min-w-0">
              <CitedOrMuted text={item} c={c} />
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function MarketPosition({ s, c, n }: P) {
  const m = s.market_position;
  if (!m || !hasMarketPosition(s)) return null;
  const strengths = (m.strengths ?? []).filter(hasText);
  const weaknesses = (m.weaknesses ?? []).filter(hasText);
  const both = nonEmpty(strengths) && nonEmpty(weaknesses);
  return (
    <Section c={c} id="market" n={n} title="Market position" description="Where the company stands, and where it is exposed.">
      <Prose text={m.summary} c={c} />
      {(nonEmpty(strengths) || nonEmpty(weaknesses)) && (
        <div className={cx("grid gap-4", hasText(m.summary) && "mt-6", both && "@2xl:grid-cols-2")}>
          {nonEmpty(strengths) && <Ledger kind="good" items={strengths} c={c} />}
          {nonEmpty(weaknesses) && <Ledger kind="bad" items={weaknesses} c={c} />}
        </div>
      )}
    </Section>
  );
}

export const hasCompetitors = (s: ReportSections) => nonEmpty((s.competitors ?? []).filter((r) => hasText(r?.name)));

/** A table on wide containers, stacked rows on narrow ones, from one markup. */
export function Competitors({ s, c, n }: P) {
  const rows = (s.competitors ?? []).filter((r) => hasText(r?.name));
  if (!nonEmpty(rows)) return null;
  const grid = "@xl:grid-cols-[minmax(0,13rem)_minmax(0,1fr)_8.5rem] @xl:gap-6";
  return (
    <Section
      c={c}
      id="competitors"
      n={n}
      title="Competitors"
      description="How the closest rivals compare."
      aside={
        <span className="font-mono text-[11px] text-slate-400">
          {rows.length} compan{rows.length === 1 ? "y" : "ies"}
        </span>
      }
    >
      <div className="overflow-hidden rounded-xl border border-slate-200/80">
        <div aria-hidden className={cx("hidden border-b border-slate-200/80 bg-slate-50/70 px-4 py-2.5 text-slate-500 @xl:grid", grid, monoLabel)}>
          <span>Company</span>
          <span>How they compare</span>
          <span className="text-right">Threat</span>
        </div>
        <ul className="divide-y divide-slate-100">
          {rows.map((r, i) => (
            <li
              key={i}
              className={cx("grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-2 px-4 py-4 transition-colors hover:bg-slate-50/60", grid)}
            >
              <p className="col-start-1 row-start-1 flex min-w-0 items-center gap-3 font-semibold text-slate-900">
                <Monogram name={r.name!} />
                <span className="min-w-0 [overflow-wrap:anywhere]">{r.name}</span>
              </p>
              <div className="col-start-2 row-start-1 self-center justify-self-end @xl:col-start-3">
                {hasText(r.threat) ? (
                  <LevelPill value={r.threat} suffix=" threat" />
                ) : (
                  <span className="text-xs text-slate-400">Not rated</span>
                )}
              </div>
              {hasText(r.comparison) && (
                <p className="col-span-2 row-start-2 min-w-0 text-sm leading-relaxed text-slate-700 @xl:col-span-1 @xl:col-start-2 @xl:row-start-1 @xl:self-center">
                  <CitedOrMuted text={r.comparison} c={c} />
                </p>
              )}
            </li>
          ))}
        </ul>
      </div>
    </Section>
  );
}
