import type { ReportSections } from "@/lib/api";
import { hasText, nonEmpty } from "@/lib/citations";
import { Badge } from "@/components/ui/Badge";
import { cx, titleCase, toneDot, toneOf } from "@/components/ui/styles";
import { Cited } from "../Cited";
import { Prose, Section, type Ctx } from "../Section";

export function RecentDevelopments({ s, c }: { s: ReportSections; c: Ctx }) {
  const items = (s.recent_developments ?? []).filter((d) => hasText(d?.title) || hasText(d?.detail));
  if (!nonEmpty(items)) return null;
  return (
    <Section c={c} id="developments" title="Recent developments">
      <ol className="relative space-y-6 border-l border-slate-200 pl-6">
        {items.map((d, i) => {
          const tone = toneOf(d.sentiment);
          return (
            <li key={i} className="relative">
              <span
                aria-hidden
                className={cx(
                  "absolute top-1.5 -left-[29px] h-2.5 w-2.5 rounded-full ring-4 ring-white",
                  toneDot[tone],
                )}
              />
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                {hasText(d.date) && (
                  <span className="text-xs font-medium text-slate-500 tabular-nums">{d.date}</span>
                )}
                {hasText(d.sentiment) && <Badge tone={tone}>{titleCase(d.sentiment)}</Badge>}
              </div>
              {hasText(d.title) && (
                <p className="mt-1 text-sm font-semibold text-slate-900">
                  <Cited text={d.title} ns={c.ns} />
                </p>
              )}
              {hasText(d.detail) && (
                <p className="mt-1 text-sm leading-relaxed text-slate-700">
                  <Cited text={d.detail} ns={c.ns} />
                </p>
              )}
            </li>
          );
        })}
      </ol>
    </Section>
  );
}

const MOOD: Record<string, string> = {
  positive: "Positive",
  mixed: "Mixed",
  negative: "Negative",
};

export function SentimentSection({ s, c }: { s: ReportSections; c: Ctx }) {
  const m = s.sentiment;
  if (!m || !(hasText(m.overall) || hasText(m.summary))) return null;
  const key = (m.overall ?? "").toLowerCase();
  return (
    <Section
      c={c}
      id="sentiment"
      title="Overall sentiment"
      aside={
        hasText(m.overall) ? (
          <Badge tone={toneOf(key)} dot>
            {MOOD[key] ?? titleCase(m.overall)}
          </Badge>
        ) : undefined
      }
    >
      <Prose text={m.summary} c={c} />
    </Section>
  );
}
