import type { Finding } from "@/lib/api";

const AGENT_COLOR: Record<string, string> = {
  fundamentals: "text-sky-300",
  news_sentiment: "text-violet-300",
  risk: "text-red-300",
  market: "text-emerald-300",
};

export function FindingsList({ findings }: { findings: Finding[] }) {
  if (!findings.length) {
    return <p className="text-sm text-slate-500">Specialist findings will appear here…</p>;
  }
  return (
    <ul className="space-y-2">
      {findings.map((f, i) => (
        <li key={i} className="rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-sm">
          <div className="mb-1 flex items-center gap-2">
            <span className={`text-xs font-semibold uppercase ${AGENT_COLOR[f.agent] ?? "text-slate-300"}`}>
              {f.agent}
            </span>
            <span className="text-[10px] text-slate-500">conf {Math.round((f.confidence ?? 0) * 100)}%</span>
          </div>
          <p className="text-slate-200">{f.claim}</p>
          {f.citation && f.citation !== "n/a" && (
            <p className="mt-1 text-[11px] text-slate-500">📎 {f.citation}</p>
          )}
        </li>
      ))}
    </ul>
  );
}
