import type { Metric, ReportSections } from "@/lib/api";
import { hasText, isPlaceholder, nonEmpty } from "@/lib/citations";
import { Badge } from "@/components/ui/Badge";
import { cx, titleCase, toneOf } from "@/components/ui/styles";
import { CiteChips, LevelPill, Trend } from "./bits";
import { Cited } from "./Cited";
import { ConfidenceDial } from "./ConfidenceMeter";
import { sectionId, type Ctx } from "./Section";

const STANCE_TEXT: Record<string, string> = {
  positive: "Positive outlook",
  neutral: "Neutral outlook",
  cautious: "Cautious outlook",
};

export function StanceBadge({ stance, surface = "light" }: { stance?: string; surface?: "light" | "dark" }) {
  if (!stance) return null;
  const key = stance.toLowerCase();
  return (
    <Badge tone={toneOf(key)} dot surface={surface}>
      {STANCE_TEXT[key] ?? titleCase(stance)}
    </Badge>
  );
}

export function RevisionBadge({ revision, surface = "light" }: { revision?: number; surface?: "light" | "dark" }) {
  if (revision == null) return null;
  return (
    <Badge tone="info" surface={surface}>
      {revision === 0 ? "First draft" : `Revision ${revision}`}
    </Badge>
  );
}

type Cell = { key: string; label: string; value: React.ReactNode; foot?: React.ReactNode; long?: boolean };

const SEVERITY_RANK: Record<string, number> = { high: 0, medium: 1, moderate: 1, low: 2 };

/** Headline KPIs for the band: the first reported metrics, topped up with the top
 *  risk and overall sentiment when the brief has fewer than two usable figures. */
function headlineCells(s: ReportSections, c: Ctx): Cell[] {
  const metrics: Metric[] = (s.financials?.metrics ?? []).filter(
    (m) => hasText(m?.value) && !isPlaceholder(m.value) && hasText(m.label),
  );
  const cells: Cell[] = metrics.slice(0, 4).map((m, i) => ({
    key: `m${i}`,
    label: m.label!,
    value: m.value!,
    long: m.value!.length > 11,
    foot:
      hasText(m.change) || hasText(m.citation) ? (
        <>
          <Trend change={m.change} surface="dark" />
          <span className="ml-auto shrink-0">
            <CiteChips citation={m.citation} ns={c.ns} tone="dark" />
          </span>
        </>
      ) : undefined,
  }));
  if (cells.length >= 2) return cells;

  const topRisk = [...(s.risks ?? [])]
    .filter((r) => hasText(r?.title))
    .sort((a, b) => (SEVERITY_RANK[(a.severity ?? "").toLowerCase()] ?? 3) - (SEVERITY_RANK[(b.severity ?? "").toLowerCase()] ?? 3))[0];
  if (topRisk) {
    cells.push({
      key: "risk",
      label: "Top risk",
      value: <span className="font-sans text-base font-semibold">{topRisk.title}</span>,
      foot: <LevelPill value={topRisk.severity} surface="dark" />,
    });
  }
  const mood = s.sentiment?.overall;
  if (hasText(mood)) {
    cells.push({
      key: "sentiment",
      label: "News sentiment",
      value: <span className="font-sans text-base font-semibold">{titleCase(mood)}</span>,
    });
  }
  return cells;
}

const COLS: Record<number, string> = {
  1: "@3xl:grid-cols-1",
  2: "@3xl:grid-cols-2",
  3: "@3xl:grid-cols-3",
  4: "@3xl:grid-cols-4",
};

/** The summary band: company, one-line verdict, stance, confidence dial, headline
 *  KPIs and the bottom line, so an investor gets the answer before scrolling. */
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
  const cells = headlineCells(s, c);
  const odd = cells.length % 2 === 1;
  const bottom = hasText(s.bottom_line) ? s.bottom_line : null;

  return (
    <header
      id={sectionId(c, "brief")}
      className="relative isolate scroll-mt-32 overflow-hidden rounded-2xl bg-ink-950 text-white shadow-[0_30px_70px_-40px_rgb(5_7_13/0.7)] ring-1 ring-ink-700/70"
    >
      <div aria-hidden className="absolute inset-0 -z-10 bg-grid" />
      <div
        aria-hidden
        className="absolute -top-40 -left-24 -z-10 h-[26rem] w-[44rem] bg-[radial-gradient(closest-side,rgb(79_70_229/0.34),transparent)]"
      />
      <div
        aria-hidden
        className="absolute -right-24 -bottom-40 -z-10 h-[22rem] w-[30rem] bg-[radial-gradient(closest-side,rgb(14_165_233/0.12),transparent)]"
      />

      <div className="px-5 pt-5 pb-6 @2xl:px-8 @2xl:pt-6 @2xl:pb-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="flex items-center gap-2 font-mono text-[10.5px] font-medium tracking-[0.2em] text-slate-400 uppercase">
            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-indigo-400" />
            Due-diligence brief
          </p>
          <div className="flex flex-wrap items-center gap-2">
            {label && <Badge surface="dark">{label}</Badge>}
            <RevisionBadge revision={revision} surface="dark" />
            {status}
          </div>
        </div>

        <div className="mt-7 grid gap-7 @3xl:grid-cols-[minmax(0,1fr)_auto] @3xl:items-end @3xl:gap-10">
          <div className="min-w-0">
            <StanceBadge stance={s.stance} surface="dark" />
            <H className="mt-3 font-display text-[2.6rem] leading-[1] tracking-tight text-balance text-white @2xl:text-6xl">
              {s.company || "Research brief"}
            </H>
            {hasText(s.headline) && (
              <p className="mt-4 max-w-3xl text-base leading-relaxed text-slate-300 @2xl:text-lg">
                <Cited text={s.headline} ns={c.ns} tone="dark" />
              </p>
            )}
          </div>
          {conf != null && <ConfidenceDial value={conf} className="@3xl:pb-1" />}
        </div>

        {nonEmpty(cells) && (
          <dl
            aria-label="Headline figures"
            className={cx(
              "mt-8 grid grid-cols-2 gap-px overflow-hidden rounded-xl bg-white/[0.08] ring-1 ring-white/[0.08]",
              COLS[cells.length],
            )}
          >
            {cells.map((cell, i) => (
              <div
                key={cell.key}
                className={cx(
                  "flex min-w-0 flex-col bg-ink-900/85 p-3.5 backdrop-blur @md:p-4 @2xl:p-5",
                  odd && i === cells.length - 1 && "col-span-2 @3xl:col-span-1",
                )}
              >
                <dt className="min-h-[2.75em] font-mono text-[10px] leading-snug font-medium tracking-[0.16em] text-slate-400 uppercase">
                  {cell.label}
                </dt>
                <dd
                  className={cx(
                    "mt-1 font-mono font-semibold tracking-tight text-white tabular-nums [overflow-wrap:anywhere]",
                    cell.long ? "text-base @md:text-lg" : "text-xl @md:text-2xl",
                  )}
                >
                  {cell.value}
                </dd>
                {cell.foot && <dd className="mt-auto flex flex-wrap items-start gap-2 pt-3">{cell.foot}</dd>}
              </div>
            ))}
          </dl>
        )}

        {bottom && (
          <div className="mt-6 grid gap-2 border-t border-white/[0.08] pt-5 @2xl:grid-cols-[9rem_minmax(0,1fr)] @2xl:gap-6">
            <p className="font-mono text-[10.5px] font-medium tracking-[0.16em] text-indigo-300 uppercase @2xl:pt-1">
              Bottom line
            </p>
            {isPlaceholder(bottom) ? (
              <p className="text-slate-400 italic">{bottom}</p>
            ) : (
              <p className="max-w-[75ch] text-[15px] leading-7 font-medium text-slate-100 @2xl:text-base">
                <Cited text={bottom} ns={c.ns} tone="dark" />
              </p>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
