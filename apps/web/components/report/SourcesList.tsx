import type { Citation } from "@/lib/api";
import { chipLabel, citationKey, sourceAnchor } from "@/lib/citations";
import { Icon } from "@/components/ui/Icon";
import { Section, type Ctx } from "./Section";

const AGENT: Record<string, string> = {
  fundamentals: "Financials analyst",
  news_sentiment: "News analyst",
  market: "Market analyst",
  risk: "Risk analyst",
  revise_research: "Follow-up research",
};

const URL_RE = /(https?:\/\/[^\s)]+)/;
const MARKER_RE = /\s*\[(web|atlas-derived)\]/g;

/** Deduplicated sources, in citation order. */
export function uniqueSources(citations: Citation[]): Citation[] {
  const seen = new Set<string>();
  return citations.filter((x) => {
    if (!x?.citation) return false;
    const k = citationKey(x.citation);
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

/** Compact source list. Always expanded, so every inline chip lands on a visible
 *  anchor; the targeted row is highlighted. */
export function SourcesList({ citations, c, n }: { citations: Citation[]; c: Ctx; n?: number }) {
  const items = uniqueSources(citations);
  if (!items.length) return null;

  return (
    <Section
      c={c}
      id="sources"
      n={n}
      title="Sources"
      description="Every document this brief cites. Source chips in the text jump here."
      aside={<span className="font-mono text-[11px] text-slate-400">{items.length} cited</span>}
    >
      <ol className="-mx-2 divide-y divide-slate-100">
        {items.map((x) => {
          const key = citationKey(x.citation);
          const url = x.citation.match(URL_RE)?.[1];
          const web = /\[web\]/.test(x.citation);
          const title = x.citation.replace(MARKER_RE, "");
          return (
            <li
              key={key}
              id={sourceAnchor(c.ns, key)}
              className="grid scroll-mt-32 grid-cols-[4.75rem_minmax(0,1fr)] gap-3 rounded-md px-2 py-2.5 text-[13px] transition-colors target:bg-indigo-50/80 target:ring-1 target:ring-indigo-200 @xl:grid-cols-[5.5rem_minmax(0,1fr)] @xl:gap-4"
            >
              <span className="pt-px">
                <span className="inline-flex rounded border border-slate-200 bg-slate-50 px-1.5 py-px font-mono text-[10px] leading-4 font-medium whitespace-nowrap text-slate-600">
                  {chipLabel(key)}
                </span>
              </span>
              <div className="min-w-0">
                <p className="leading-snug break-words text-slate-800">
                  {url ? (
                    <a
                      href={url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-start gap-1 text-indigo-700 underline decoration-indigo-300 underline-offset-2 hover:decoration-indigo-600"
                    >
                      {title}
                      <Icon name="link" className="mt-0.5 h-3 w-3 shrink-0" />
                      <span className="sr-only">(opens in a new tab)</span>
                    </a>
                  ) : (
                    title
                  )}
                </p>
                {(x.agent || web) && (
                  <p className="mt-0.5 text-xs text-slate-500">
                    {x.agent && (AGENT[x.agent] ?? x.agent)}
                    {x.agent && web && " · "}
                    {web && "Web result, not a primary source"}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </Section>
  );
}
