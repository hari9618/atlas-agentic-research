import type { ReportSections } from "@/lib/api";
import { hasText, nonEmpty } from "@/lib/citations";
import { Badge } from "@/components/ui/Badge";
import { cx, titleCase, toneDot, toneOf } from "@/components/ui/styles";
import { Cited } from "../Cited";
import { BulletList, Prose, Section, SubLabel, type Ctx } from "../Section";

type P = { s: ReportSections; c: Ctx; n?: number };

const MOOD: Record<string, string> = { positive: "Positive", mixed: "Mixed", negative: "Negative" };

const developments = (s: ReportSections) =>
  (s.recent_developments ?? []).filter((d) => hasText(d?.title) || hasText(d?.detail));
const praise = (s: ReportSections) => (s.sentiment?.praise ?? []).filter(hasText);
const complaints = (s: ReportSections) => (s.sentiment?.complaints ?? []).filter(hasText);

export const hasNews = (s: ReportSections) =>
  nonEmpty(developments(s)) ||
  hasText(s.sentiment?.overall) ||
  hasText(s.sentiment?.summary) ||
  nonEmpty(praise(s)) ||
  nonEmpty(complaints(s));

/** Customer voice (praise / complaints), the overall read, then recent events as a
 *  dated timeline. */
export function NewsAndSentiment({ s, c, n }: P) {
  if (!hasNews(s)) return null;
  const items = developments(s);
  const good = praise(s);
  const bad = complaints(s);
  const mood = s.sentiment?.overall;
  const moodKey = (mood ?? "").toLowerCase();
  const voice = nonEmpty(good) || nonEmpty(bad);
  return (
    <Section
      c={c}
      id="developments"
      n={n}
      title="News & sentiment"
      description={voice ? "What customers say, and what has happened recently." : "Recent events and how they were received."}
      aside={
        hasText(mood) ? (
          <Badge tone={toneOf(moodKey)} dot>
            {MOOD[moodKey] ?? titleCase(mood)} overall
          </Badge>
        ) : undefined
      }
    >
      <Prose text={s.sentiment?.summary} c={c} />

      {voice && (
        <div className={cx("grid gap-6", hasText(s.sentiment?.summary) && "mt-6", nonEmpty(good) && nonEmpty(bad) && "@2xl:grid-cols-2")}>
          {nonEmpty(good) && (
            <div>
              <SubLabel className="mb-3">What customers praise</SubLabel>
              <BulletList items={good} c={c} marker="bg-emerald-500" />
            </div>
          )}
          {nonEmpty(bad) && (
            <div>
              <SubLabel className="mb-3">What customers complain about</SubLabel>
              <BulletList items={bad} c={c} marker="bg-rose-500" />
            </div>
          )}
        </div>
      )}

      {nonEmpty(items) && (
        <div className={cx((voice || hasText(s.sentiment?.summary)) && "mt-8")}>
          {(voice || hasText(s.sentiment?.summary)) && <SubLabel className="mb-4">Recent developments</SubLabel>}
          <ol aria-label="Recent developments">
            {items.map((d, i) => {
              const tone = toneOf(d.sentiment);
              return (
                <li key={i} className="group grid @xl:grid-cols-[6.5rem_minmax(0,1fr)] @xl:gap-5">
                  <div className="hidden pt-1 text-right font-mono text-xs text-slate-500 tabular-nums @xl:block">{d.date}</div>
                  <div className="relative border-l border-slate-200 pb-6 pl-6 group-last:pb-0">
                    <span
                      aria-hidden
                      className={cx("absolute top-2 -left-[4px] h-2 w-2 rounded-full ring-4 ring-surface", toneDot[tone])}
                    />
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                      {hasText(d.date) && (
                        <span className="font-mono text-xs text-slate-500 tabular-nums @xl:hidden">{d.date}</span>
                      )}
                      {hasText(d.title) && (
                        <p className="text-sm font-semibold text-slate-900">
                          <Cited text={d.title} ns={c.ns} nums={c.nums} />
                        </p>
                      )}
                      {hasText(d.sentiment) && <Badge tone={tone}>{titleCase(d.sentiment)}</Badge>}
                    </div>
                    {hasText(d.detail) && (
                      <p className="mt-1 max-w-[72ch] text-sm leading-relaxed text-slate-600">
                        <Cited text={d.detail} ns={c.ns} nums={c.nums} />
                      </p>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </Section>
  );
}
