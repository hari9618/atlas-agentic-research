import type { ReportSections } from "@/lib/api";
import { hasText, nonEmpty } from "@/lib/citations";
import { Badge } from "@/components/ui/Badge";
import { titleCase, toneOf } from "@/components/ui/styles";
import { Cited } from "../Cited";
import { Section, type Ctx } from "../Section";

const ORDER: Record<string, number> = { high: 0, medium: 1, low: 2 };

function Severity({ value }: { value?: string }) {
  if (!value) return null;
  return (
    <Badge tone={toneOf(value)} dot>
      {titleCase(value)}
    </Badge>
  );
}

/** Risks sorted high → low. Table on desktop, stacked cards on phones. */
export function Risks({ s, c }: { s: ReportSections; c: Ctx }) {
  const rows = (s.risks ?? [])
    .filter((r) => hasText(r?.title) || hasText(r?.detail))
    .sort(
      (a, b) => (ORDER[(a.severity ?? "").toLowerCase()] ?? 3) - (ORDER[(b.severity ?? "").toLowerCase()] ?? 3),
    );
  if (!nonEmpty(rows)) return null;
  return (
    <Section c={c} id="risks" title="Key risks">
      <table className="hidden w-full text-left text-sm md:table">
        <thead>
          <tr className="border-b border-slate-200 text-xs text-slate-500">
            <th scope="col" className="w-1/4 pb-2 font-medium">Risk</th>
            <th scope="col" className="w-28 pb-2 font-medium">Severity</th>
            <th scope="col" className="pb-2 font-medium">Why it matters</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r, i) => (
            <tr key={i} className="align-top">
              <th scope="row" className="py-3 pr-4 font-semibold text-slate-900">{r.title}</th>
              <td className="py-3 pr-4"><Severity value={r.severity} /></td>
              <td className="py-3 leading-relaxed text-slate-700"><Cited text={r.detail} ns={c.ns} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <ul className="space-y-3 md:hidden">
        {rows.map((r, i) => (
          <li key={i} className="rounded-lg border border-slate-200 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-semibold text-slate-900">{r.title}</p>
              <Severity value={r.severity} />
            </div>
            {hasText(r.detail) && (
              <p className="mt-2 text-sm leading-relaxed text-slate-700">
                <Cited text={r.detail} ns={c.ns} />
              </p>
            )}
          </li>
        ))}
      </ul>
    </Section>
  );
}
