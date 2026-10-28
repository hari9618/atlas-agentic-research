import Form from "next/form";
import Link from "next/link";
import { SAMPLE_SECTIONS } from "@/lib/sample-report";
import { Cited } from "@/components/report/Cited";
import { ConfidenceMeter } from "@/components/report/ConfidenceMeter";
import { StanceBadge } from "@/components/report/ReportHeader";
import { Badge } from "@/components/ui/Badge";
import { Container } from "@/components/ui/Container";
import { Icon } from "@/components/ui/Icon";
import { cx, toneOf } from "@/components/ui/styles";

const EXAMPLES = [
  "Should I invest in NVIDIA?",
  "Reliance Industries: growth and risks",
  "How does Stripe compare to Adyen?",
];

const STATS = [
  { value: "4", label: "specialist analysts per question" },
  { value: "2", label: "sides argued before anything is written" },
  { value: "17", label: "sections in every investor brief" },
  { value: "~2 min", label: "from question to cited draft" },
];

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
        <p className="font-mono text-[10px] tracking-[0.18em] text-slate-400 uppercase">Research team</p>
        <span className="flex items-center gap-1.5 font-mono text-[10px] text-emerald-300">
          <span className="h-1.5 w-1.5 animate-blink rounded-full bg-emerald-400" />
          LIVE
        </span>
      </div>
      <ul className="mt-4 space-y-2">
        {TEAM.map((t) => (
          <li key={t.name} className="rounded-xl border border-white/[0.07] bg-white/[0.03] px-3 py-2.5">
            <div className="flex items-center gap-2.5">
              <span
                className={cx(
                  "flex h-5 w-5 shrink-0 items-center justify-center rounded-full",
                  t.state === "done" ? "bg-emerald-500/90 text-ink-950" : "bg-indigo-500/20 text-indigo-300",
                )}
              >
                {t.state === "done" ? (
                  <Icon name="check" className="h-3 w-3" strokeWidth={3} />
                ) : (
                  <span className="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-indigo-300" />
                )}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-medium text-slate-100">{t.name}</span>
                <span className="block truncate text-[11px] text-slate-500">{t.role}</span>
              </span>
            </div>
            {t.state === "working" && (
              <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/[0.06]">
                <div
                  className="h-full animate-scan rounded-full bg-linear-to-r from-indigo-500 via-sky-400 to-emerald-300"
                  style={{ animationDelay: t.delay }}
                />
              </div>
            )}
          </li>
        ))}
      </ul>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/[0.06] px-3 py-2">
          <p className="font-mono text-[10px] tracking-wider text-emerald-300 uppercase">Bull</p>
          <p className="mt-0.5 text-[11px] leading-snug text-slate-300">28% growth, rising software mix</p>
        </div>
        <div className="rounded-xl border border-rose-400/20 bg-rose-400/[0.06] px-3 py-2">
          <p className="font-mono text-[10px] tracking-wider text-rose-300 uppercase">Bear</p>
          <p className="mt-0.5 text-[11px] leading-snug text-slate-300">3 customers are 39% of revenue</p>
        </div>
      </div>
    </div>
  );
}

function BriefPanel() {
  const s = SAMPLE_SECTIONS;
  const ns = "preview"; // chips jump into the full sample report further down the page
  return (
    <div className="bg-white p-5 text-slate-900 sm:p-7">
      <div className="flex flex-wrap items-center gap-2">
        <StanceBadge stance={s.stance} />
        <Badge tone="info">Revision 1</Badge>
        <Badge tone="muted">Sample data</Badge>
      </div>
      <p className="mt-5 font-mono text-[10px] tracking-[0.18em] text-indigo-600 uppercase">Due-diligence brief</p>
      <p className="mt-1 font-display text-3xl leading-tight tracking-tight sm:text-4xl">{s.company}</p>
      <p className="mt-2 text-sm leading-relaxed text-slate-600">
        Growing fast toward recurring software revenue, with customer and supplier concentration to watch.
      </p>
      <div className="mt-5 grid gap-5 md:grid-cols-[1fr_11rem]">
        <div className="grid grid-cols-3 gap-2">
          {MINI_METRICS.map((m) => (
            <div key={m.label} className="rounded-xl border border-slate-200 bg-slate-50/70 p-3">
              <p className="truncate text-[11px] text-slate-500">{m.label}</p>
              <p className="mt-0.5 font-mono text-lg font-semibold tracking-tight text-slate-900 tabular-nums">{m.value}</p>
            </div>
          ))}
        </div>
        <ConfidenceMeter value={s.confidence} compact />
      </div>
      <ul className="mt-5 space-y-2.5 text-sm text-slate-700">
        {(s.executive_summary ?? []).slice(0, 2).map((b, i) => (
          <li key={i} className="flex gap-2.5">
            <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-500" />
            <span className="min-w-0 leading-relaxed">
              <Cited text={b} ns={ns} />
            </span>
          </li>
        ))}
      </ul>
      <div className="mt-5 flex flex-wrap gap-1.5 border-t border-slate-100 pt-4">
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
    <figure className="relative mx-auto mt-16 max-w-5xl text-left sm:mt-20">
      <div
        aria-hidden
        className="absolute -inset-x-10 -top-10 -bottom-4 -z-10 rounded-[3rem] bg-[radial-gradient(60%_60%_at_50%_30%,rgb(99_102_241/0.35),transparent_70%)] blur-2xl"
      />
      <div className="overflow-hidden rounded-[1.4rem] border border-white/10 bg-ink-850 p-1.5 shadow-[0_40px_120px_-30px_rgb(0_0_0/0.8)] ring-1 ring-white/5">
        <div className="flex items-center gap-3 px-3 py-2.5">
          <div className="flex gap-1.5" aria-hidden>
            <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
            <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
            <span className="h-2.5 w-2.5 rounded-full bg-white/15" />
          </div>
          <div className="mx-auto flex max-w-sm min-w-0 flex-1 items-center justify-center gap-2 rounded-full bg-white/5 px-3 py-1 font-mono text-[11px] text-slate-400">
            <Icon name="search" className="h-3 w-3 shrink-0" />
            <span className="truncate">Should I worry about Helios Robotics as a competitor?</span>
          </div>
          <span className="hidden w-12 sm:block" aria-hidden />
        </div>
        <div className="grid overflow-hidden rounded-2xl lg:grid-cols-[17rem_1fr]">
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

// ---- Hero ------------------------------------------------------------------

export function Hero() {
  return (
    <section className="relative isolate overflow-hidden bg-ink-950 text-white">
      <div aria-hidden className="absolute inset-0 -z-10 bg-grid" />
      <div
        aria-hidden
        className="absolute -top-48 left-1/2 -z-10 h-[42rem] w-[72rem] -translate-x-1/2 bg-[radial-gradient(closest-side,rgb(79_70_229/0.38),transparent)]"
      />
      <div
        aria-hidden
        className="absolute top-40 -right-40 -z-10 h-[28rem] w-[28rem] bg-[radial-gradient(closest-side,rgb(14_165_233/0.16),transparent)]"
      />

      <Container className="pt-32 pb-16 text-center sm:pt-40 sm:pb-20">
        <Link
          href={`/research?q=${encodeURIComponent("Reliance Industries: growth, competitors and risks")}`}
          className="group inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 py-1 pr-3 pl-1 text-xs text-slate-300 backdrop-blur transition-colors hover:border-white/20 hover:text-white"
        >
          <span className="rounded-full bg-indigo-500/90 px-2 py-0.5 font-mono text-[10px] font-semibold tracking-wider text-white uppercase">
            New
          </span>
          Indian &amp; global markets: NSE, BSE, LSE and more
          <Icon name="arrowRight" className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
        </Link>

        <h1 className="mx-auto mt-7 max-w-4xl font-display text-[2.9rem] leading-[0.98] tracking-tight text-balance sm:text-7xl lg:text-[5.6rem]">
          Due diligence on any company, <em className="text-shine pr-1">in minutes.</em>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-slate-400 sm:text-lg">
          A team of AI analysts researches financials, news, market and risk in parallel, argues the bull and bear
          case, and hands you an investor-grade brief where every claim links to its source.
        </p>

        <Form
          action="/research"
          className="mx-auto mt-9 flex max-w-xl items-center gap-2 rounded-full border border-white/12 bg-white/[0.06] p-1.5 pl-5 shadow-[0_0_0_1px_rgb(255_255_255/0.02),0_20px_60px_-20px_rgb(79_70_229/0.5)] backdrop-blur-md transition-colors focus-within:border-indigo-400/60"
        >
          <label htmlFor="hero-q" className="sr-only">
            Company or question
          </label>
          <Icon name="search" className="h-4 w-4 shrink-0 text-slate-500" />
          <input
            id="hero-q"
            name="q"
            required
            minLength={3}
            autoComplete="off"
            placeholder="Ask about any company…"
            className="w-full min-w-0 flex-1 bg-transparent py-2 text-base text-white placeholder:text-slate-500 focus:outline-none"
          />
          <button
            type="submit"
            className="inline-flex shrink-0 items-center gap-2 rounded-full bg-white px-4 py-2.5 text-sm font-semibold text-ink-950 transition-colors hover:bg-indigo-50 sm:px-5"
          >
            <span className="hidden sm:inline">Research</span>
            <Icon name="arrowRight" />
          </button>
        </Form>

        <ul className="mt-4 flex flex-wrap justify-center gap-2" aria-label="Example questions">
          {EXAMPLES.map((q) => (
            <li key={q}>
              <Link
                href={`/research?q=${encodeURIComponent(q)}`}
                className="inline-block rounded-full border border-white/10 px-3 py-1 text-xs text-slate-400 transition-colors hover:border-white/25 hover:text-slate-200"
              >
                {q}
              </Link>
            </li>
          ))}
        </ul>

        <ProductShot />
      </Container>

      <div className="border-t border-white/[0.07] bg-ink-950/60">
        <Container>
          <dl className="grid grid-cols-2 divide-white/[0.07] py-8 md:grid-cols-4 md:divide-x">
            {STATS.map((s) => (
              <div key={s.label} className="px-2 py-3 text-center md:px-6">
                <dt className="sr-only">{s.label}</dt>
                <dd>
                  <span className="block font-display text-4xl tracking-tight text-white sm:text-5xl">{s.value}</span>
                  <span className="mt-1 block text-xs text-slate-400 sm:text-sm">{s.label}</span>
                </dd>
              </div>
            ))}
          </dl>
        </Container>
      </div>
    </section>
  );
}
