import { NODE_LABELS } from "@/lib/api";

export type NodeStatus = "idle" | "active" | "done";

const COLUMNS: { title: string; nodes: string[] }[] = [
  { title: "Plan", nodes: ["supervisor"] },
  { title: "Specialists", nodes: ["fundamentals", "news_sentiment", "risk", "market"] },
  { title: "Debate", nodes: ["debate_round"] },
  { title: "Synthesize", nodes: ["synthesize"] },
];

const STYLES: Record<NodeStatus, string> = {
  idle: "border-slate-700 bg-slate-900/60 text-slate-500",
  active: "border-sky-400 bg-sky-500/10 text-sky-200 active-node",
  done: "border-emerald-500 bg-emerald-500/10 text-emerald-200",
};

export function AgentGraph({ statuses }: { statuses: Record<string, NodeStatus> }) {
  return (
    <div className="flex items-stretch gap-2 overflow-x-auto">
      {COLUMNS.map((col, i) => (
        <div key={col.title} className="flex items-center gap-2">
          <div className="flex min-w-[150px] flex-col gap-2">
            <span className="text-[10px] uppercase tracking-widest text-slate-500">
              {col.title}
            </span>
            {col.nodes.map((n) => {
              const s = statuses[n] ?? "idle";
              return (
                <div
                  key={n}
                  className={`rounded-lg border px-3 py-2 text-sm transition-colors ${STYLES[s]}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{NODE_LABELS[n] ?? n}</span>
                    <span className="text-xs">
                      {s === "done" ? "✓" : s === "active" ? "●" : "○"}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
          {i < COLUMNS.length - 1 && <div className="text-slate-600">→</div>}
        </div>
      ))}
    </div>
  );
}
