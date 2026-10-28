import type { ReportSections } from "@/lib/api";
import { hasText, nonEmpty } from "@/lib/citations";
import { Badge } from "@/components/ui/Badge";
import { titleCase, toneOf } from "@/components/ui/styles";
import { Cited } from "../Cited";
import { BulletList, Prose, Section, type Ctx } from "../Section";

export function MarketPosition({ s, c }: { s: ReportSections; c: Ctx }) {
  const m = s.market_position;
  if (!m || !(hasText(m.summary) || nonEmpty(m.strengths) || nonEmpty(m.weaknesses))) return null;
  return (
    <Section c={c} id="market" title="Market position">
      <Prose text={m.summary} c={c} className="mb-5" />
      <div className="grid gap-4 md:grid-cols-2">
        {nonEmpty(m.strengths) && (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-4">
            <p className="mb-3 text-sm font-semibold text-emerald-800">Strengths</p>
            <BulletList items={m.strengths} c={c} marker="bg-emerald-500" />
          </div>
        )}
        {nonEmpty(m.weaknesses) && (
          <div className="rounded-lg border border-rose-200 bg-rose-50/50 p-4">
            <p className="mb-3 text-sm font-semibold text-rose-800">Weaknesses</p>
            <BulletList items={m.weaknesses} c={c} marker="bg-rose-500" />
          </div>
        )}
      </div>
    </Section>
  );
}

function ThreatBadge({ threat }: { threat?: string }) {
  if (!threat) return null;
  return (
    <Badge tone={toneOf(threat)} dot>
      {titleCase(threat)} threat
    </Badge>
  );
}

/** Table on desktop, stacked cards on phones. */
export function Competitors({ s, c }: { s: ReportSections; c: Ctx }) {
  const rows = (s.competitors ?? []).filter((r) => hasText(r?.name));
  if (!nonEmpty(rows)) return null;
  return (
    <Section c={c} id="competitors" title="Competitors">
      <table className="hidden w-full text-left text-sm md:table">
        <thead>
          <tr className="border-b border-slate-200 text-xs text-slate-500">
            <th scope="col" className="w-1/4 pb-2 font-medium">Company</th>
            <th scope="col" className="pb-2 font-medium">How they compare</th>
            <th scope="col" className="w-36 pb-2 text-right font-medium">Threat</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r, i) => (
            <tr key={i} className="align-top">
              <th scope="row" className="py-3 pr-4 font-semibold text-slate-900">{r.name}</th>
              <td className="py-3 pr-4 leading-relaxed text-slate-700">
                <Cited text={r.comparison} ns={c.ns} />
              </td>
              <td className="py-3 text-right"><ThreatBadge threat={r.threat} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <ul className="space-y-3 md:hidden">
        {rows.map((r, i) => (
          <li key={i} className="rounded-lg border border-slate-200 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-semibold text-slate-900">{r.name}</p>
              <ThreatBadge threat={r.threat} />
            </div>
            {hasText(r.comparison) && (
              <p className="mt-2 text-sm leading-relaxed text-slate-700">
                <Cited text={r.comparison} ns={c.ns} />
              </p>
            )}
          </li>
        ))}
      </ul>
    </Section>
  );
}
