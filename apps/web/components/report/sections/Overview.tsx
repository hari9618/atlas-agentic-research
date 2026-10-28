import type { ReportSections } from "@/lib/api";
import { hasText, nonEmpty } from "@/lib/citations";
import { chip } from "@/components/ui/styles";
import { BulletList, Prose, Section, SubLabel, type Ctx } from "../Section";

export function ExecutiveSummary({ s, c }: { s: ReportSections; c: Ctx }) {
  if (!nonEmpty(s.executive_summary)) return null;
  return (
    <Section c={c} id="summary" title="Executive summary" className="border-indigo-200 bg-indigo-50/40">
      <BulletList items={s.executive_summary} c={c} />
    </Section>
  );
}

export function CompanyOverview({ s, c }: { s: ReportSections; c: Ctx }) {
  const o = s.company_overview;
  if (!o || !(hasText(o.what_they_do) || hasText(o.business_model) || hasText(o.customers) || nonEmpty(o.products)))
    return null;
  return (
    <Section c={c} id="overview" title="Company overview">
      <dl className="grid gap-5 sm:grid-cols-2">
        {hasText(o.what_they_do) && (
          <div>
            <dt><SubLabel>What they do</SubLabel></dt>
            <dd><Prose text={o.what_they_do} c={c} /></dd>
          </div>
        )}
        {hasText(o.business_model) && (
          <div>
            <dt><SubLabel>How they make money</SubLabel></dt>
            <dd><Prose text={o.business_model} c={c} /></dd>
          </div>
        )}
        {nonEmpty(o.products) && (
          <div>
            <dt><SubLabel>Products &amp; services</SubLabel></dt>
            <dd>
              <ul className="flex flex-wrap gap-2">
                {o.products.filter(hasText).map((p) => (
                  <li key={p} className={chip}>
                    {p}
                  </li>
                ))}
              </ul>
            </dd>
          </div>
        )}
        {hasText(o.customers) && (
          <div>
            <dt><SubLabel>Customers</SubLabel></dt>
            <dd><Prose text={o.customers} c={c} /></dd>
          </div>
        )}
      </dl>
    </Section>
  );
}
