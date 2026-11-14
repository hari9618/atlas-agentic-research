import { reportCitationNumbers } from "@/lib/report-citations";
import { SAMPLE_PAYLOAD, SAMPLE_SECTIONS } from "@/lib/sample-report";
import { Cited } from "@/components/report/Cited";
import { ConfidenceMeter } from "@/components/report/ConfidenceMeter";
import { StanceBadge } from "@/components/report/ReportHeader";
import { Badge } from "@/components/ui/Badge";
import { Container } from "@/components/ui/Container";
import { Icon } from "@/components/ui/Icon";
import { cx, toneOf } from "@/components/ui/styles";

// ---- Product shot ----------------------------------------------------------
// A static, decorative picture of a run: the agent team on the left (with gently
// animated "working" bars), the drafted brief on the right. Built from the sample
// data and labelled as such.

const TEAM: { name: string; role: string; state: "done" | "working"; delay?: string }[] = [
  { name: "Supervisor", role: "Scoped the question", state: "done" },
  { name: "Fundamentals", role: "SEC filings · financials", state: "working", delay: "0s" },
  { name: "News & sentiment", role: "Headlines · tone", state: "working", delay: "0.6s" },
  { name: "Market", role: "Quotes · competitors", state: "working", delay: "1.2s" },
  { name: "Risk", role: "Concentration · supply", state: "working", delay: "1.8s" },
];

const MINI_METRICS = [
  { label: "Revenue FY25", value: "$4.2B" },
  { label: "Growth YoY", value: "+28%" },
  { label: "Software mix", value: ">30%" },
];

function TeamPanel() {
  return (
    <div className="border-b border-white/10 bg-ink-900/80 p-4 sm:p-5 lg:border-r lg:border-b-0">
      <div className="flex items-center justify-between">
        <p className="font-mono text-2xs tracking-label text-slate-400 uppercase">Research team</p>
        <span className="flex items-center gap-2 font-mono text-2xs text-emerald-300">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          LIVE
        </span>
      </div>
      <ul className="mt-4 space-y-2">
        {TEAM.map((t) => (
          <li key={t.name} className="rounded-xl border border-white/[0.07] bg-white/[0.03] px-3 py-2">
            <div className="flex items-center gap-2">
              <span
                className={cx(
                  "flex h-5 w-5 shrink-0 items-center justify-center rounded-full",
                  t.state === "done" ? "bg-emerald-500/90 text-ink-950" : "bg-indigo-500/20 text-indigo-300",
                )}
              >
                {t.state === "done" ? (
                  <Icon name="check" className="h-3 w-3" strokeWidth={3} />
                ) : (
                  <span className="h-1.5 w-1.5 rounded-full bg-indigo-300" />
                )}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-slate-100">{t.name}</span>
                <span className="block truncate text-2xs text-slate-400">{t.role}</span>
              </span>
            </div>
          </li>
        ))}
      </ul>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/[0.06] px-3 py-2">
          <p className="font-mono text-2xs tracking-wider text-emerald-300 uppercase">Bull</p>
          <p className="mt-0.5 text-2xs leading-snug text-slate-300">28% growth, rising software mix</p>
        </div>
        <div className="rounded-xl border border-rose-400/20 bg-rose-400/[0.06] px-3 py-2">
          <p className="font-mono text-2xs tracking-wider text-rose-300 uppercase">Bear</p>
          <p className="mt-0.5 text-2xs leading-snug text-slate-300">3 customers are 39% of revenue</p>
        </div>
      </div>
    </div>
  );
}

function BriefPanel() {
  const s = SAMPLE_SECTIONS;
  // Same numbers as the full sample report further down, which these chips jump to.
  const nums = reportCitationNumbers(SAMPLE_PAYLOAD);
  const ns = "preview"; // chips jump into the full sample report further down the page
  return (
    <div className="bg-surface p-5 text-slate-900 sm:p-7">
      <div className="flex flex-wrap items-center gap-2">
        <StanceBadge stance={s.stance} />
        <Badge tone="info">Revision 1</Badge>
        <Badge tone="muted">Sample data</Badge>
      </div>
      <p className="mt-5 font-mono text-2xs tracking-label text-indigo-600 uppercase">Due-diligence brief</p>
      <p className="mt-1 font-display text-3xl leading-tight tracking-tight sm:text-4xl">{s.company}</p>
      <p className="mt-2 text-sm leading-relaxed text-slate-600">
        Growing fast toward recurring software revenue, with customer and supplier concentration to watch.
      </p>
      <div className="mt-5 grid gap-5 md:grid-cols-[1fr_11rem]">
        <div className="grid grid-cols-3 gap-2">
          {MINI_METRICS.map((m) => (
            <div key={m.label} className="rounded-xl border border-slate-200 bg-slate-50/70 p-3">
              <p className="truncate text-2xs text-slate-500">{m.label}</p>
              <p className="mt-0.5 font-mono text-lg font-semibold tracking-tight text-slate-900 tabular-nums">{m.value}</p>
            </div>
          ))}
        </div>
        <ConfidenceMeter value={s.confidence} compact />
      </div>
      <ul className="mt-5 space-y-2 text-sm text-slate-700">
        {(s.executive_summary ?? []).slice(0, 2).map((b, i) => (
          <li key={i} className="flex gap-2">
            <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-500" />
            <span className="min-w-0 leading-relaxed">
              <Cited text={b} ns={ns} nums={nums} />
            </span>
          </li>
        ))}
      </ul>
      <div className="mt-5 flex flex-wrap gap-2 border-t border-slate-100 pt-4">
        {(s.risks ?? []).slice(0, 2).map((r) => (
          <Badge key={r.title} tone={toneOf(r.severity)} dot>
            {r.title}
          </Badge>
        ))}
      </div>
    </div>
  );
}

function ProductShot() {
  return (
    <figure className="mx-auto max-w-5xl pt-4 text-left">
      <div className="overflow-hidden rounded-xl border border-white/10 bg-ink-850 p-2">
        <div className="flex items-center gap-3 px-3 py-2">
          <div className="mx-auto flex max-w-sm min-w-0 flex-1 items-center justify-center gap-2 rounded-md bg-white/5 px-3 py-1 font-mono text-2xs text-slate-400">
            <Icon name="search" className="h-3 w-3 shrink-0" />
            <span className="truncate">Should I worry about Helios Robotics as a competitor?</span>
          </div>
        </div>
        <div className="grid overflow-hidden rounded-xl lg:grid-cols-[17rem_1fr]">
          <TeamPanel />
          <BriefPanel />
        </div>
      </div>
      <figcaption className="sr-only">
        Sample Atlas run on Helios Robotics, a fictional company from the demo documents: the research team on the
        left, the drafted brief on the right.
      </figcaption>
    </figure>
  );
}

export function RunShowcase() {
  return (
    <section
      aria-label="A sample Atlas run"
      className="bg-ink-950 pb-20 text-white sm:pb-24"
    >
      <Container>
        <ProductShot />
      </Container>
    </section>
  );
}
