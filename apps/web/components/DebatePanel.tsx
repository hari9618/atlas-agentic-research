import type { DebateTurn } from "@/lib/api";

const ROLE_STYLE: Record<string, { label: string; cls: string }> = {
  bull: { label: "🐂 Bull", cls: "border-emerald-600/50 bg-emerald-500/5" },
  bear: { label: "🐻 Bear", cls: "border-red-600/50 bg-red-500/5" },
  judge: { label: "⚖️ Judge", cls: "border-amber-500/50 bg-amber-500/5" },
};

export function DebatePanel({ debate }: { debate: DebateTurn[] }) {
  if (!debate.length) {
    return <p className="text-sm text-slate-500">The debate transcript will stream here…</p>;
  }
  return (
    <div className="space-y-3">
      {debate.map((t, i) => {
        const r = ROLE_STYLE[t.role] ?? { label: t.role, cls: "border-slate-700" };
        return (
          <div key={i} className={`rounded-lg border p-3 ${r.cls}`}>
            <div className="mb-1 flex items-center justify-between">
              <span className="text-sm font-semibold">{r.label}</span>
              {t.leaning && (
                <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] uppercase tracking-wide text-slate-300">
                  {t.leaning}
                </span>
              )}
            </div>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-300">{t.text}</p>
          </div>
        );
      })}
    </div>
  );
}
