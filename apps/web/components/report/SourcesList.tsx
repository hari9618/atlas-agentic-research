import type { Citation } from "@/lib/api";
import { chipLabel, citationKey, sourceAnchor } from "@/lib/citations";
import { Disclosure } from "@/components/ui/Disclosure";
import { card, cx } from "@/components/ui/styles";
import type { Ctx } from "./Section";

const AGENT: Record<string, string> = {
  fundamentals: "Financials analyst",
  news_sentiment: "News analyst",
  market: "Market analyst",
  risk: "Risk analyst",
  revise_research: "Follow-up research",
};

const URL_RE = /(https?:\/\/[^\s)]+)/;

/** Deduplicated sources; each has an anchor that inline source chips link to. */
export function SourcesList({ citations, c }: { citations: Citation[]; c: Ctx }) {
  const seen = new Set<string>();
  const items = citations.filter((x) => {
    if (!x?.citation) return false;
    const k = citationKey(x.citation);
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  if (!items.length) return null;

  return (
    <section id={`${c.ns}-sources`} className={cx(card, "scroll-mt-24 px-5 sm:px-6")}>
      <Disclosure
        summary={
          <span className="text-base font-semibold text-slate-900">
            Sources <span className="font-normal text-slate-500">({items.length})</span>
          </span>
        }
        summaryClassName="py-4"
      >
        <ol className="space-y-2 pb-5">
          {items.map((x, i) => {
            const key = citationKey(x.citation);
            const url = x.citation.match(URL_RE)?.[1];
            const web = /\[web\]/.test(x.citation);
            return (
              <li
                key={key}
                id={sourceAnchor(c.ns, key)}
                className="flex scroll-mt-24 gap-3 rounded-lg p-2 text-sm target:bg-indigo-50 target:ring-1 target:ring-indigo-200"
              >
                <span className="w-6 shrink-0 text-right text-slate-500 tabular-nums">{i + 1}.</span>
                <div className="min-w-0">
                  <p className="break-words text-slate-800">
                    {url ? (
                      <a href={url} target="_blank" rel="noreferrer" className="text-indigo-700 underline">
                        {x.citation.replace(/\s*\[(web|atlas-derived)\]/g, "")}
                      </a>
                    ) : (
                      x.citation.replace(/\s*\[(web|atlas-derived)\]/g, "")
                    )}
                  </p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {chipLabel(key)}
                    {x.agent && <> · {AGENT[x.agent] ?? x.agent}</>}
                    {web && <> · Web result, not a primary source</>}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
      </Disclosure>
    </section>
  );
}
