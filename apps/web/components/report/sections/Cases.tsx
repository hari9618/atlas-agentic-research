import type { ReportSections } from "@/lib/api";
import { hasText, nonEmpty } from "@/lib/citations";
import { Icon } from "@/components/ui/Icon";
import { cx } from "@/components/ui/styles";
import { CitedOrMuted, Prose, Section, SubLabel, type Ctx } from "../Section";

type P = { s: ReportSections; c: Ctx; n?: number };

export const hasCases = (s: ReportSections) =>
  nonEmpty((s.bull_case ?? []).filter(hasText)) || nonEmpty((s.bear_case ?? []).filter(hasText));

function CaseColumn({ kind, items, c }: { kind: "bull" | "bear"; items: string[]; c: Ctx }) {
  const bull = kind === "bull";
  return (
    <div className="min-w-0">
      <div
        className={cx(
          "flex items-center justify-between gap-3 border-b px-5 py-3",
          bull ? "border-emerald-200/70 bg-emerald-50/60" : "border-rose-200/70 bg-rose-50/60",
        )}
      >
        <p className={cx("flex items-center gap-2 text-sm font-semibold", bull ? "text-emerald-900" : "text-rose-900")}>
          <Icon name={bull ? "trending" : "trendingDown"} className="h-4 w-4" />
          {bull ? "The bull case" : "The bear case"}
        </p>
        <span className={cx("font-mono text-[11px] tabular-nums", bull ? "text-emerald-700" : "text-rose-700")}>
          {items.length} point{items.length === 1 ? "" : "s"}
        </span>
      </div>
      {nonEmpty(items) ? (
        <ol className="divide-y divide-slate-100">
          {items.map((item, i) => (
            <li key={i} className="flex gap-3 px-5 py-3.5 text-sm leading-relaxed text-slate-700">
              <span
                aria-hidden
                className={cx("w-5 shrink-0 pt-px font-mono text-[11px] font-semibold", bull ? "text-emerald-600" : "text-rose-600")}
              >
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="min-w-0">
                <CitedOrMuted text={item} c={c} />
              </span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="px-5 py-4 text-sm text-slate-500 italic">
          No {bull ? "bull" : "bear"} points were supported by evidence.
        </p>
      )}
    </div>
  );
}

/** Both sides of the debate, side by side, with a "vs" marker on the seam. */
export function BullBear({ s, c, n }: P) {
  if (!hasCases(s)) return null;
  const bull = (s.bull_case ?? []).filter(hasText);
  const bear = (s.bear_case ?? []).filter(hasText);
  return (
    <Section c={c} id="cases" n={n} title="Bull vs bear" description="The strongest argument on each side of the evidence.">
      <div className="relative grid overflow-hidden rounded-xl border border-slate-200/80 @2xl:grid-cols-2">
        <CaseColumn kind="bull" items={bull} c={c} />
        <div className="border-t border-slate-200/80 @2xl:border-t-0 @2xl:border-l">
          <CaseColumn kind="bear" items={bear} c={c} />
        </div>
        <span
          aria-hidden
          className="absolute top-[0.6rem] left-1/2 hidden -translate-x-1/2 rounded-full bg-white px-2 py-0.5 font-mono text-[10px] font-semibold tracking-wider text-slate-500 uppercase shadow-xs ring-1 ring-slate-200 @2xl:block"
        >
          vs
        </span>
      </div>
    </Section>
  );
}

export const hasOutlook = (s: ReportSections) =>
  !!s.outlook && (hasText(s.outlook.summary) || nonEmpty((s.outlook.watch_items ?? []).filter(hasText)));

export function Outlook({ s, c, n }: P) {
  const o = s.outlook;
  if (!o || !hasOutlook(s)) return null;
  const items = (o.watch_items ?? []).filter(hasText);
  return (
    <Section c={c} id="outlook" n={n} title="Outlook" description="What to expect, and the signals worth tracking.">
      <Prose text={o.summary} c={c} />
      {nonEmpty(items) && (
        <div className={cx(hasText(o.summary) && "mt-7")}>
          <SubLabel className="mb-3">What to watch</SubLabel>
          <ul className="grid gap-3 @2xl:grid-cols-2">
            {items.map((w, i) => (
              <li
                key={i}
                className="flex gap-3 rounded-xl border border-slate-200/80 bg-white p-4 text-sm leading-relaxed text-slate-700 shadow-[0_1px_2px_rgb(15_23_42/0.04)]"
              >
                <span
                  aria-hidden
                  className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-500"
                >
                  <Icon name="eye" className="h-3.5 w-3.5" />
                </span>
                <span className="min-w-0">
                  <CitedOrMuted text={w} c={c} />
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Section>
  );
}

export function Uncertainties({ items, c, n }: { items: string[]; c: Ctx; n?: number }) {
  const list = items.filter(hasText);
  if (!nonEmpty(list)) return null;
  return (
    <Section
      c={c}
      id="uncertainties"
      n={n}
      title="What we're not sure about"
      description="Gaps in the evidence. Weigh these before acting on the brief."
    >
      <ul className="divide-y divide-amber-200/60 overflow-hidden rounded-xl border border-amber-200/80 bg-amber-50/50">
        {list.map((u, i) => (
          <li key={i} className="flex gap-3 px-4 py-3.5 text-sm leading-relaxed text-amber-950/90">
            <Icon name="help" className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
            <span className="min-w-0">
              <CitedOrMuted text={u} c={c} />
            </span>
          </li>
        ))}
      </ul>
    </Section>
  );
}
