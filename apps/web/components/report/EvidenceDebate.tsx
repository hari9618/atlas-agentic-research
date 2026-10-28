import type { DebateTurn, Finding } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Disclosure } from "@/components/ui/Disclosure";
import { Icon, type IconName } from "@/components/ui/Icon";
import { cx, monoLabel, surface, titleCase, toneOf } from "@/components/ui/styles";

const AGENT_LABEL: Record<string, string> = {
  fundamentals: "Financials",
  news_sentiment: "News & sentiment",
  market: "Market & competitors",
  risk: "Risk",
  revise_research: "Follow-up research",
};

const ROLE: Record<string, { label: string; icon: IconName; avatar: string; bubble: string }> = {
  bull: {
    label: "Bull",
    icon: "trending",
    avatar: "bg-emerald-600 text-white",
    bubble: "border-emerald-200/80 bg-emerald-50/50",
  },
  bear: { label: "Bear", icon: "trendingDown", avatar: "bg-rose-600 text-white", bubble: "border-rose-200/80 bg-rose-50/50" },
  judge: { label: "Judge", icon: "scale", avatar: "bg-ink-950 text-white", bubble: "border-slate-200 bg-slate-50" },
};

function roleOf(role: string) {
  const r = role.toLowerCase();
  if (r.includes("bull")) return ROLE.bull;
  if (r.includes("bear")) return ROLE.bear;
  if (r.includes("judge")) return ROLE.judge;
  return {
    label: titleCase(role),
    icon: "users" as IconName,
    avatar: "bg-slate-200 text-slate-700",
    bubble: "border-slate-200 bg-white",
  };
}

/** The raw material behind the report, for anyone who wants to check the work. */
export function EvidenceDebate({
  findings,
  debate,
  defaultOpen = false,
  id,
}: {
  findings: Finding[];
  debate: DebateTurn[];
  defaultOpen?: boolean;
  id?: string;
}) {
  if (!findings.length && !debate.length) return null;
  return (
    <section id={id} aria-label="Evidence and debate" className={cx(surface, "scroll-mt-32 px-5 sm:px-6")}>
      <Disclosure
        defaultOpen={defaultOpen}
        summaryClassName="py-4"
        summary={
          <span className="flex min-w-0 items-center gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
              <Icon name="scale" className="h-4.5 w-4.5" />
            </span>
            <span className="min-w-0">
              <span className="block text-[15px] font-semibold text-slate-900">Appendix: evidence &amp; debate</span>
              <span className="block text-sm text-slate-500">
                {findings.length} specialist finding{findings.length === 1 ? "" : "s"}
                {debate.length > 0 && ` · ${debate.length} debate turn${debate.length === 1 ? "" : "s"}`}
              </span>
            </span>
          </span>
        }
      >
        <div className="grid gap-8 border-t border-slate-100 pt-5 pb-6 lg:grid-cols-2">
          {findings.length > 0 && (
            <div className="min-w-0">
              <p className={cx(monoLabel, "mb-3 text-slate-500")}>Specialist findings</p>
              <ul className="space-y-2">
                {findings.map((f, i) => {
                  const pct = Math.round(Math.max(0, Math.min(1, f.confidence ?? 0)) * 100);
                  return (
                    <li key={i} className="rounded-xl border border-slate-200/80 p-3.5 text-sm">
                      <div className="mb-1.5 flex items-center justify-between gap-3">
                        <span className="text-xs font-semibold text-indigo-700">{AGENT_LABEL[f.agent] ?? f.agent}</span>
                        <span className="flex items-center gap-2">
                          <span aria-hidden className="h-1 w-14 overflow-hidden rounded-full bg-slate-100">
                            <span className="block h-full rounded-full bg-indigo-500" style={{ width: `${pct}%` }} />
                          </span>
                          <span className="font-mono text-[11px] text-slate-500 tabular-nums">{pct}% confident</span>
                        </span>
                      </div>
                      <p className="leading-relaxed text-slate-700">{f.claim}</p>
                      {f.citation && f.citation !== "n/a" && (
                        <p className="mt-1.5 text-xs break-words text-slate-500">Source: {f.citation}</p>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
          {debate.length > 0 && (
            <div className="min-w-0">
              <p className={cx(monoLabel, "mb-3 text-slate-500")}>Bull vs bear transcript</p>
              <ol className="space-y-3">
                {debate.map((t, i) => {
                  const r = roleOf(t.role);
                  return (
                    <li key={i} className="flex gap-3">
                      <span
                        aria-hidden
                        className={cx(
                          "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
                          r.avatar,
                        )}
                      >
                        <Icon name={r.icon} className="h-3.5 w-3.5" />
                      </span>
                      <div className={cx("min-w-0 flex-1 rounded-xl border p-3.5 text-sm", r.bubble)}>
                        <div className="mb-1 flex items-center justify-between gap-2">
                          <span className="text-xs font-semibold tracking-wide text-slate-900 uppercase">{r.label}</span>
                          {t.leaning && <Badge tone={toneOf(t.leaning)}>{titleCase(t.leaning)}</Badge>}
                        </div>
                        <p className="leading-relaxed whitespace-pre-wrap text-slate-700">{t.text}</p>
                      </div>
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
