import Link from "next/link";
import { SAMPLE_SECTIONS } from "@/lib/sample-report";
import { Cited } from "@/components/report/Cited";
import { ConfidenceMeter } from "@/components/report/ConfidenceMeter";
import { StanceBadge } from "@/components/report/ReportHeader";
import { Badge } from "@/components/ui/Badge";
import { Container } from "@/components/ui/Container";
import { Icon } from "@/components/ui/Icon";
import { btn, card, cx, toneOf } from "@/components/ui/styles";

const TRACK = [
  { label: "Ask", done: true },
  { label: "Research", done: true },
  { label: "Debate", done: true },
  { label: "Your review", done: false },
];

function StepTracker() {
  return (
    <ol aria-label="How a run progresses" className="mt-8 flex flex-wrap items-center gap-x-2 gap-y-3 text-sm">
      {TRACK.map((s, i) => (
        <li key={s.label} className="flex items-center gap-2">
          <span
            className={cx(
              "flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold",
              s.done ? "bg-emerald-600 text-white" : "bg-indigo-100 text-indigo-700 ring-2 ring-indigo-600",
            )}
          >
            {s.done ? <Icon name="check" className="h-3.5 w-3.5" strokeWidth={3} /> : i + 1}
          </span>
          <span className={s.done ? "text-slate-700" : "font-semibold text-slate-900"}>{s.label}</span>
          {i < TRACK.length - 1 && <span aria-hidden className="mx-1 h-px w-6 bg-slate-300" />}
        </li>
      ))}
    </ol>
  );
}

// Short labels for the small tiles (same sample facts as SAMPLE_SECTIONS.financials).
const MINI_METRICS = [
  { label: "Revenue FY25", value: "$4.2B" },
  { label: "Growth YoY", value: "+28%" },
  { label: "Software mix", value: ">30%" },
];

/** A realistic, compact report card built from the sample data. Labelled "Sample". */
function HeroMock() {
  const s = SAMPLE_SECTIONS;
  // Chips link into the full sample report further down the page.
  const ns = "preview";
  return (
    <div className="relative">
      <div aria-hidden className="absolute -inset-4 -z-10 rounded-3xl bg-linear-to-br from-indigo-100 via-white to-sky-100 blur-2xl" />
      <figure className={cx(card, "overflow-hidden shadow-xl shadow-slate-900/5")}>
        <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-4 py-2.5">
          <div className="flex items-center gap-1.5" aria-hidden>
            <span className="h-2.5 w-2.5 rounded-full bg-slate-300" />
            <span className="h-2.5 w-2.5 rounded-full bg-slate-300" />
            <span className="h-2.5 w-2.5 rounded-full bg-slate-300" />
          </div>
          <Badge tone="muted">Sample data</Badge>
        </div>
        <div className="space-y-4 p-5">
          <div className="flex flex-wrap items-center gap-2">
            <StanceBadge stance={s.stance} />
            <Badge tone="info">Revision 1</Badge>
          </div>
          <div>
            <p className="text-xl font-semibold tracking-tight text-slate-900">{s.company}</p>
            <p className="mt-1 text-sm leading-relaxed text-slate-600">
              Growing fast toward recurring software revenue, with customer and supplier concentration to watch.
            </p>
          </div>
          <ConfidenceMeter value={s.confidence} compact />
          <div className="grid grid-cols-3 gap-2">
            {MINI_METRICS.map((m) => (
              <div key={m.label} className="rounded-lg border border-slate-200 bg-slate-50 p-2.5">
                <p className="truncate text-[11px] text-slate-500">{m.label}</p>
                <p className="text-base font-semibold text-slate-900 tabular-nums">{m.value}</p>
              </div>
            ))}
          </div>
          <ul className="space-y-2 text-sm text-slate-700">
            {(s.executive_summary ?? []).slice(0, 2).map((b, i) => (
              <li key={i} className="flex gap-2.5">
                <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-500" />
                <span className="min-w-0 leading-relaxed">
                  <Cited text={b} ns={ns} />
                </span>
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap gap-1.5 border-t border-slate-100 pt-3">
            {(s.risks ?? []).slice(0, 2).map((r) => (
              <Badge key={r.title} tone={toneOf(r.severity)} dot>
                {r.title}
              </Badge>
            ))}
          </div>
        </div>
        <figcaption className="sr-only">Sample Atlas report for Helios Robotics, built from demo data.</figcaption>
      </figure>
    </div>
  );
}

export function Hero() {
  return (
    <section className="relative overflow-hidden border-b border-slate-200 bg-white">
      <div aria-hidden className="absolute inset-x-0 top-0 -z-0 h-80 bg-linear-to-b from-slate-50 to-white" />
      <Container className="relative grid items-center gap-12 py-14 sm:py-20 lg:grid-cols-[1.05fr_1fr] lg:gap-16 lg:py-24">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-800">
            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-indigo-600" />
            An AI analyst team for company research
          </p>
          <h1 className="mt-5 text-4xl font-semibold tracking-tight text-balance text-slate-900 sm:text-5xl lg:text-[3.4rem] lg:leading-[1.08]">
            Due diligence on any company, in minutes.
          </h1>
          <p className="mt-5 max-w-xl text-lg leading-relaxed text-slate-600">
            Ask a question about a company or competitor. Specialist AI analysts research financials,
            news, market and risk in parallel, argue the bull and bear case, and hand you a brief where
            every claim links to its source.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link href="/research" className={cx(btn.primary, btn.lg)}>
              Research a company
              <Icon name="arrowRight" />
            </Link>
            <a href="#sample-report" className={cx(btn.secondary, btn.lg)}>
              See a sample report
            </a>
          </div>
          <StepTracker />
        </div>
        <HeroMock />
      </Container>
    </section>
  );
}
