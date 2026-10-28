import type { ReportSections } from "@/lib/api";
import { hasText, isPlaceholder, nonEmpty } from "@/lib/citations";
import { Icon } from "@/components/ui/Icon";
import { cardBase, cx } from "@/components/ui/styles";
import { Cited } from "../Cited";
import { BulletList, Prose, Section, sectionId, type Ctx } from "../Section";

export function BullBear({ s, c }: { s: ReportSections; c: Ctx }) {
  if (!nonEmpty(s.bull_case) && !nonEmpty(s.bear_case)) return null;
  return (
    <Section c={c} id="cases" title="Bull case vs bear case">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-4">
          <p className="mb-3 flex items-center gap-2 text-sm font-semibold text-emerald-800">
            <Icon name="chart" /> The bull case
          </p>
          {nonEmpty(s.bull_case) ? (
            <BulletList items={s.bull_case} c={c} marker="bg-emerald-500" />
          ) : (
            <p className="text-sm text-slate-500 italic">No bull points were supported by evidence.</p>
          )}
        </div>
        <div className="rounded-lg border border-rose-200 bg-rose-50/50 p-4">
          <p className="mb-3 flex items-center gap-2 text-sm font-semibold text-rose-800">
            <Icon name="alert" /> The bear case
          </p>
          {nonEmpty(s.bear_case) ? (
            <BulletList items={s.bear_case} c={c} marker="bg-rose-500" />
          ) : (
            <p className="text-sm text-slate-500 italic">No bear points were supported by evidence.</p>
          )}
        </div>
      </div>
    </Section>
  );
}

export function Outlook({ s, c }: { s: ReportSections; c: Ctx }) {
  const o = s.outlook;
  const items = (o?.watch_items ?? []).filter(hasText);
  if (!o || !(hasText(o.summary) || nonEmpty(items))) return null;
  return (
    <Section c={c} id="outlook" title="Outlook">
      <Prose text={o.summary} c={c} />
      {nonEmpty(items) && (
        <div className={cx(hasText(o.summary) && "mt-5")}>
          <p className="mb-2 text-sm font-semibold text-slate-900">What to watch</p>
          <ul className="space-y-2">
            {items.map((w, i) => (
              <li key={i} className="flex gap-3 text-sm leading-relaxed text-slate-700">
                <span
                  aria-hidden
                  className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border border-slate-300 bg-white"
                />
                <span className="min-w-0">
                  <Cited text={w} ns={c.ns} />
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Section>
  );
}

export function BottomLine({ s, c }: { s: ReportSections; c: Ctx }) {
  if (!hasText(s.bottom_line)) return null;
  const H = c.hl === 2 ? "h3" : "h4";
  return (
    <section
      id={sectionId(c, "bottom-line")}
      className={cx(cardBase, "scroll-mt-24 border-indigo-600 bg-indigo-600 p-5 text-white sm:p-6")}
    >
      <H className="text-xs font-semibold tracking-wider text-indigo-100 uppercase">Bottom line</H>
      {isPlaceholder(s.bottom_line) ? (
        <p className="mt-2 text-indigo-100 italic">{s.bottom_line}</p>
      ) : (
        <p className="mt-2 text-base leading-relaxed font-medium sm:text-lg [&_a]:border-indigo-300 [&_a]:bg-indigo-500 [&_a]:text-white">
          <Cited text={s.bottom_line} ns={c.ns} />
        </p>
      )}
    </section>
  );
}

export function Uncertainties({ items, c }: { items: string[]; c: Ctx }) {
  const list = items.filter(hasText);
  if (!nonEmpty(list)) return null;
  return (
    <Section
      c={c}
      id="uncertainties"
      title="What we're not sure about"
      className="border-amber-200 bg-amber-50/50"
    >
      <BulletList items={list} c={c} marker="bg-amber-500" />
    </Section>
  );
}
