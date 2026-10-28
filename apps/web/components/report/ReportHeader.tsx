import type { ReportSections } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { card, cx, titleCase, toneOf } from "@/components/ui/styles";
import { Cited } from "./Cited";
import { ConfidenceMeter } from "./ConfidenceMeter";
import type { Ctx } from "./Section";

const STANCE_TEXT: Record<string, string> = {
  positive: "Positive outlook",
  neutral: "Neutral outlook",
  cautious: "Cautious outlook",
};

export function StanceBadge({ stance }: { stance?: string }) {
  if (!stance) return null;
  const key = stance.toLowerCase();
  return (
    <Badge tone={toneOf(key)} dot>
      {STANCE_TEXT[key] ?? titleCase(stance)}
    </Badge>
  );
}

export function RevisionBadge({ revision }: { revision?: number }) {
  if (revision == null) return null;
  return <Badge tone="info">{revision === 0 ? "First draft" : `Revision ${revision}`}</Badge>;
}

/** Company, one-line answer, stance, confidence and revision. */
export function ReportHeader({
  s,
  c,
  revision,
  confidence,
  label,
  status,
}: {
  s: ReportSections;
  c: Ctx;
  revision?: number;
  confidence?: number | null;
  /** e.g. "Sample" — always shown for sample data. */
  label?: string;
  status?: React.ReactNode;
}) {
  const H = c.hl === 2 ? "h2" : "h3";
  const conf = confidence ?? s.confidence;
  return (
    <header className={cx(card, "overflow-hidden")}>
      <div className="h-1 bg-linear-to-r from-indigo-600 via-indigo-500 to-sky-400" aria-hidden />
      <div className="grid gap-6 p-5 sm:p-6 md:grid-cols-[1fr_15rem] md:gap-8">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            {label && <Badge tone="muted">{label}</Badge>}
            <StanceBadge stance={s.stance} />
            <RevisionBadge revision={revision} />
            {status}
          </div>
          <p className="mt-5 font-mono text-[11px] tracking-[0.18em] text-indigo-600 uppercase">
            Due-diligence brief
          </p>
          <H className="mt-1.5 font-display text-4xl leading-[1.05] tracking-tight text-slate-950 sm:text-5xl">
            {s.company || "Research brief"}
          </H>
          {s.headline && (
            <p className="mt-3 text-base leading-relaxed text-slate-700 sm:text-lg">
              <Cited text={s.headline} ns={c.ns} />
            </p>
          )}
        </div>
        {conf != null && (
          <div className="self-start rounded-2xl border border-slate-200/80 bg-slate-50/70 p-4">
            <ConfidenceMeter value={conf} />
          </div>
        )}
      </div>
    </header>
  );
}
