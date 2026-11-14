import type { ReportSections } from "@/lib/api";
import { hasText, isPlaceholder, nonEmpty } from "@/lib/citations";
import { Prose, Section, SubLabel, type Ctx, CitedOrMuted } from "../Section";

type P = { s: ReportSections; c: Ctx; n?: number };

export const hasExecutiveSummary = (s: ReportSections) => nonEmpty((s.executive_summary ?? []).filter(hasText));

/** The key points, numbered, at a slightly larger reading size. */
export function ExecutiveSummary({ s, c, n }: P) {
  const items = (s.executive_summary ?? []).filter(hasText);
  if (!nonEmpty(items)) return null;
  return (
    <Section c={c} id="summary" n={n} title="Executive summary" description="The key points, each tied to its source.">
      <ol className="divide-y divide-slate-100 border-y border-slate-100">
        {items.map((item, i) => (
          <li key={i} className="flex gap-4 py-4">
            <span
              aria-hidden
              className="w-5 shrink-0 pt-1 font-mono text-xs text-slate-500 tabular-nums"
            >
              {i + 1}
            </span>
            <p className="min-w-0 text-base leading-7 text-slate-800">
              <CitedOrMuted text={item} c={c} />
            </p>
          </li>
        ))}
      </ol>
    </Section>
  );
}

export const hasCompanyOverview = (s: ReportSections) => {
  const o = s.company_overview;
  return !!o && (hasText(o.what_they_do) || hasText(o.business_model) || hasText(o.customers) || nonEmpty((o.products ?? []).filter(hasText)));
};

/** A description list: label column on the left, answer on the right. */
export function CompanyOverview({ s, c, n }: P) {
  const o = s.company_overview;
  if (!o || !hasCompanyOverview(s)) return null;
  const products = (o.products ?? []).filter(hasText);
  const rows: [string, React.ReactNode][] = [];
  if (hasText(o.what_they_do)) rows.push(["What they do", <Prose key="w" text={o.what_they_do} c={c} />]);
  if (hasText(o.business_model)) rows.push(["How they make money", <Prose key="b" text={o.business_model} c={c} />]);
  if (nonEmpty(products))
    rows.push([
      "Products & services",
      <ul key="p" className="flex flex-wrap gap-2">
        {products.map((p) => (
          <li
            key={p}
            className={
              isPlaceholder(p)
                ? "text-sm text-slate-500 italic"
                : "rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-sm font-medium text-slate-700"
            }
          >
            {p}
          </li>
        ))}
      </ul>,
    ]);
  if (hasText(o.customers)) rows.push(["Customers", <Prose key="c" text={o.customers} c={c} />]);

  return (
    <Section c={c} id="overview" n={n} title="Company overview" description="What the business does and how it makes money.">
      <dl className="divide-y divide-slate-100 border-y border-slate-100">
        {rows.map(([label, body]) => (
          <div key={label} className="grid gap-2 py-4 @xl:grid-cols-[11rem_minmax(0,1fr)] @xl:gap-8">
            <dt className="@xl:pt-1">
              <SubLabel>{label}</SubLabel>
            </dt>
            <dd className="min-w-0">{body}</dd>
          </div>
        ))}
      </dl>
    </Section>
  );
}
