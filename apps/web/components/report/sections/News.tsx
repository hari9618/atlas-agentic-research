import type { ReportSections } from "@/lib/api";
import { hasText, nonEmpty } from "@/lib/citations";
import { Badge } from "@/components/ui/Badge";
import { cx, titleCase, toneDot, toneOf } from "@/components/ui/styles";
import { Cited } from "../Cited";
import { Prose, Section, SubLabel, type Ctx } from "../Section";

type P = { s: ReportSections; c: Ctx; n?: number };

const MOOD: Record<string, string> = { positive: "Positive", mixed: "Mixed", negative: "Negative" };

const developments = (s: ReportSections) =>
  (s.recent_developments ?? []).filter((d) => hasText(d?.title) || hasText(d?.detail));

export const hasNews = (s: ReportSections) =>
  nonEmpty(developments(s)) || hasText(s.sentiment?.overall) || hasText(s.sentiment?.summary);

/** Recent developments as a dated timeline, led by the overall news sentiment. */
export function NewsAndSentiment({ s, c, n }: P) {
  if (!hasNews(s)) return null;
  const items = developments(s);
  const mood = s.sentiment?.overall;
  const moodKey = (mood ?? "").toLowerCase();
  return (
    <Section
      c={c}
      id="developments"
      n={n}
      title="News & sentiment"
      description="Recent events and how the market read them."
      aside={
        hasText(mood) ? (
          <Badge tone={toneOf(moodKey)} dot>
            {MOOD[moodKey] ?? titleCase(mood)} sentiment
          </Badge>
        ) : undefined
      }
    >
      {hasText(s.sentiment?.summary) && (
        <div className="mb-7 rounded-xl border border-slate-200/80 bg-slate-50/60 p-4 @2xl:p-5">
          <SubLabel className="mb-2">Overall sentiment</SubLabel>
          <Prose text={s.sentiment?.summary} c={c} />
        </div>
      )}

      {nonEmpty(items) && (
        <ol aria-label="Recent developments">
          {items.map((d, i) => {
            const tone = toneOf(d.sentiment);
            return (
              <li key={i} className="group grid @xl:grid-cols-[6.5rem_minmax(0,1fr)] @xl:gap-5">
                <div className="hidden pt-0.5 text-right font-mono text-xs text-slate-500 tabular-nums @xl:block">
                  {d.date}
                </div>
                <div className="relative border-l border-slate-200 pb-7 pl-6 group-last:pb-0">
                  <span
                    aria-hidden
                    className={cx("absolute top-1.5 -left-[5px] h-2.5 w-2.5 rounded-full ring-4 ring-white", toneDot[tone])}
                  />
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    {hasText(d.date) && (
                      <span className="font-mono text-xs text-slate-500 tabular-nums @xl:hidden">{d.date}</span>
                    )}
                    {hasText(d.title) && (
                      <p className="text-[15px] font-semibold text-slate-900">
                        <Cited text={d.title} ns={c.ns} />
                      </p>
                    )}
                    {hasText(d.sentiment) && <Badge tone={tone}>{titleCase(d.sentiment)}</Badge>}
                  </div>
                  {hasText(d.detail) && (
                    <p className="mt-1.5 max-w-[72ch] text-sm leading-relaxed text-slate-600">
                      <Cited text={d.detail} ns={c.ns} />
                    </p>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </Section>
  );
}
