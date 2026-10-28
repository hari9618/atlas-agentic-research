import { Badge } from "@/components/ui/Badge";
import { Icon } from "@/components/ui/Icon";
import { cardBase, cx } from "@/components/ui/styles";

// Small, static UI mocks that illustrate each feature. Decorative: each feature's
// text carries the meaning, so the mocks are hidden from assistive tech.

function Frame({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      aria-hidden
      className={cx(
        cardBase,
        "border-slate-200/80 p-4 shadow-[0_12px_32px_-16px_rgb(15_23_42/0.18)] sm:p-5",
        !className?.includes("bg-") && "bg-white",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function SourcesVisual() {
  const rows = [
    ["SEC filings", "10-K, results and risk factors"],
    ["Market data", "Share price and recent moves"],
    ["Company news", "Latest headlines and sentiment"],
    ["Live web", "Fills gaps the other sources miss"],
    ["Your documents", "Decks, reports and notes you add"],
  ];
  return (
    <Frame>
      <p className="mb-3 text-xs font-semibold tracking-wide text-slate-500 uppercase">Sources checked</p>
      <ul className="space-y-2">
        {rows.map(([t, d]) => (
          <li key={t} className="flex items-center gap-3 rounded-lg border border-slate-200 px-3 py-2">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-600 text-white">
              <Icon name="check" className="h-3 w-3" strokeWidth={3} />
            </span>
            <span className="min-w-0">
              <span className="block text-sm font-medium text-slate-900">{t}</span>
              <span className="block truncate text-xs text-slate-500">{d}</span>
            </span>
          </li>
        ))}
      </ul>
    </Frame>
  );
}

function MockChip({ children }: { children: React.ReactNode }) {
  return (
    <span className="mx-0.5 inline-flex items-center rounded border border-slate-200 bg-slate-50 px-1.5 text-[10.5px] leading-4 font-medium text-slate-500">
      {children}
    </span>
  );
}

export function CitationsVisual() {
  return (
    <Frame>
      <p className="text-sm leading-relaxed text-slate-700">
        FY2025 revenue reached $4.2B, up 28% year over year <MockChip>SEC 1</MockChip>. A $900M contract
        signed in March 2026 is about 40% recurring software <MockChip>News 1</MockChip>.
      </p>
      <div className="mt-4 rounded-lg border border-indigo-200 bg-indigo-50/60 p-3">
        <p className="text-xs font-semibold text-indigo-800">SEC 1</p>
        <p className="mt-0.5 text-sm text-slate-700">Helios Robotics FY2025 10-K, results</p>
        <p className="mt-0.5 text-xs text-slate-500">Found by the financials analyst</p>
      </div>
    </Frame>
  );
}

export function DebateVisual() {
  return (
    <Frame className="space-y-3">
      <div className="rounded-lg border border-emerald-200 bg-emerald-50/60 p-3">
        <p className="text-xs font-semibold tracking-wide text-emerald-800 uppercase">Bull</p>
        <p className="mt-1 text-sm text-slate-700">28% growth and a rising software mix make this a durable competitor.</p>
      </div>
      <div className="rounded-lg border border-rose-200 bg-rose-50/60 p-3">
        <p className="text-xs font-semibold tracking-wide text-rose-800 uppercase">Bear</p>
        <p className="mt-1 text-sm text-slate-700">Three customers are 39% of revenue, and one supplier makes every actuator.</p>
      </div>
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold tracking-wide text-slate-700 uppercase">Judge</p>
          <Badge tone="mid">Neutral</Badge>
        </div>
        <p className="mt-1 text-sm text-slate-700">Both cases hold up. Net: neutral, moderate confidence.</p>
      </div>
    </Frame>
  );
}

export function ReviewVisual() {
  return (
    <Frame>
      <p className="text-xs font-semibold tracking-wider text-indigo-600 uppercase">Your review</p>
      <p className="mt-1 text-base font-semibold text-slate-900">Is this report ready?</p>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <span className="inline-flex items-center justify-center gap-1.5 rounded-full bg-indigo-600 px-3 py-2 text-sm font-semibold text-white">
          <Icon name="check" /> Approve
        </span>
        <span className="inline-flex items-center justify-center gap-1.5 rounded-full border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-800">
          <Icon name="edit" /> Request changes
        </span>
      </div>
      <div className="mt-3 rounded-lg border border-slate-300 p-3 text-sm text-slate-700">
        Go deeper on how they compare with Aster Dynamics.
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {["More on competitors", "Deeper financials", "Focus on risks"].map((c) => (
          <span key={c} className="rounded-full border border-slate-300 px-2.5 py-1 text-xs text-slate-700">
            + {c}
          </span>
        ))}
      </div>
    </Frame>
  );
}

export function CompetitorsVisual() {
  const rows: [string, string, "high" | "medium" | "low"][] = [
    ["Aster Dynamics", "Smaller software mix (~18%)", "medium"],
    ["Another rival", "How they compare, with a source", "low"],
  ];
  return (
    <Frame>
      <p className="mb-3 text-xs font-semibold tracking-wide text-slate-500 uppercase">Competitors</p>
      <ul className="divide-y divide-slate-100">
        {rows.map(([n, d, t]) => (
          <li key={n} className="flex items-center justify-between gap-3 py-2.5">
            <span className="min-w-0">
              <span className="block text-sm font-semibold text-slate-900">{n}</span>
              <span className="block truncate text-xs text-slate-500">{d}</span>
            </span>
            <Badge tone={t === "medium" ? "mid" : t === "high" ? "bad" : "good"} dot>
              {t[0].toUpperCase() + t.slice(1)} threat
            </Badge>
          </li>
        ))}
      </ul>
      <div className="mt-3 grid grid-cols-2 gap-2 border-t border-slate-100 pt-3">
        <div className="rounded-lg bg-emerald-50 p-2.5 text-xs text-emerald-800">Strength: recurring software</div>
        <div className="rounded-lg bg-rose-50 p-2.5 text-xs text-rose-800">Weakness: customer concentration</div>
      </div>
    </Frame>
  );
}

export function PdfVisual() {
  return (
    <Frame className="flex justify-center bg-slate-50">
      <div className="w-full max-w-[16rem] rounded-md border border-slate-200 bg-white p-4 shadow-md">
        <div className="border-b-2 border-indigo-700 pb-2">
          <p className="text-[9px] font-semibold tracking-widest text-slate-500 uppercase">Atlas · Due-diligence brief</p>
          <p className="mt-1 text-sm font-bold text-slate-900">Helios Robotics</p>
          <div className="mt-1 flex items-center gap-1.5">
            <span className="rounded-full bg-amber-50 px-1.5 text-[9px] font-semibold text-amber-800">Neutral</span>
            <span className="text-[9px] text-slate-500">Confidence 62/100</span>
          </div>
        </div>
        {["Executive summary", "Financials", "Key risks", "Sources"].map((h) => (
          <div key={h} className="mt-2.5">
            <p className="text-[9px] font-bold tracking-wider text-indigo-800 uppercase">{h}</p>
            <div className="mt-1 space-y-1">
              <div className="h-1.5 w-full rounded bg-slate-100" />
              <div className="h-1.5 w-4/5 rounded bg-slate-100" />
            </div>
          </div>
        ))}
      </div>
    </Frame>
  );
}
