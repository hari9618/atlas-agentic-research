import type { DebateTurn, Finding } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Disclosure } from "@/components/ui/Disclosure";
import { card, cx, titleCase, toneOf } from "@/components/ui/styles";

const AGENT_LABEL: Record<string, string> = {
  fundamentals: "Financials",
  news_sentiment: "News & sentiment",
  market: "Market & competitors",
  risk: "Risk",
  revise_research: "Follow-up research",
};

const ROLE: Record<string, { label: string; box: string; tag: string }> = {
  bull: { label: "Bull", box: "border-emerald-200 bg-emerald-50/50", tag: "text-emerald-800" },
  bear: { label: "Bear", box: "border-rose-200 bg-rose-50/50", tag: "text-rose-800" },
  judge: { label: "Judge", box: "border-slate-200 bg-slate-50", tag: "text-slate-800" },
};

function roleOf(role: string) {
  const r = role.toLowerCase();
  if (r.includes("bull")) return ROLE.bull;
  if (r.includes("bear")) return ROLE.bear;
  if (r.includes("judge")) return ROLE.judge;
  return { label: titleCase(role), box: "border-slate-200 bg-white", tag: "text-slate-800" };
}

/** The raw material behind the report, for anyone who wants to check the work. */
export function EvidenceDebate({
  findings,
  debate,
  defaultOpen = false,
}: {
  findings: Finding[];
  debate: DebateTurn[];
  defaultOpen?: boolean;
}) {
  if (!findings.length && !debate.length) return null;
  return (
    <section className={cx(card, "px-5 sm:px-6")}>
      <Disclosure
        defaultOpen={defaultOpen}
        summaryClassName="py-4"
        summary={
          <span>
            <span className="block text-base font-semibold text-slate-900">Evidence &amp; debate</span>
            <span className="block text-sm text-slate-500">
              {findings.length} findings from the specialist agents
              {debate.length > 0 && ` · ${debate.length} debate turns`}
            </span>
          </span>
        }
      >
        <div className="grid gap-6 pb-6 lg:grid-cols-2">
          {findings.length > 0 && (
            <div>
              <p className="mb-3 text-sm font-semibold text-slate-900">Specialist findings</p>
              <ul className="space-y-2">
                {findings.map((f, i) => (
                  <li key={i} className="rounded-lg border border-slate-200 p-3 text-sm">
                    <div className="mb-1 flex flex-wrap items-center gap-2">
                      <span className="text-xs font-semibold text-indigo-700">
                        {AGENT_LABEL[f.agent] ?? f.agent}
                      </span>
                      <span className="text-xs text-slate-500">
                        {Math.round((f.confidence ?? 0) * 100)}% confident
                      </span>
                    </div>
                    <p className="leading-relaxed text-slate-700">{f.claim}</p>
                    {f.citation && f.citation !== "n/a" && (
                      <p className="mt-1 text-xs break-words text-slate-500">Source: {f.citation}</p>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {debate.length > 0 && (
            <div>
              <p className="mb-3 text-sm font-semibold text-slate-900">Bull vs bear debate</p>
              <ol className="space-y-2">
                {debate.map((t, i) => {
                  const r = roleOf(t.role);
                  return (
                    <li key={i} className={cx("rounded-lg border p-3 text-sm", r.box)}>
                      <div className="mb-1 flex items-center justify-between gap-2">
                        <span className={cx("text-xs font-semibold tracking-wide uppercase", r.tag)}>
                          {r.label}
                        </span>
                        {t.leaning && <Badge tone={toneOf(t.leaning)}>{titleCase(t.leaning)}</Badge>}
                      </div>
                      <p className="leading-relaxed whitespace-pre-wrap text-slate-700">{t.text}</p>
                    </li>
                  );
                })}
              </ol>
            </div>
          )}
        </div>
      </Disclosure>
    </section>
  );
}
