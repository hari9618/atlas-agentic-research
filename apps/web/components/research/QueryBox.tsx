"use client";

import { Icon } from "@/components/ui/Icon";
import { btn, cx } from "@/components/ui/styles";

const EXAMPLES: { text: string; demo?: boolean }[] = [
  { text: "Should I invest in NVIDIA?" },
  { text: "How does Stripe compare to Adyen?" },
  { text: "Reliance Industries: growth, competitors and risks" },
  { text: "Evaluate Helios Robotics as a competitor", demo: true },
  { text: "What are Helios Robotics' biggest risks?", demo: true },
];

export function QueryBox({
  query,
  setQuery,
  onSubmit,
  busy,
}: {
  query: string;
  setQuery: (q: string) => void;
  onSubmit: () => void;
  busy: boolean;
}) {
  const tooShort = query.trim().length < 3;
  return (
    <section
      aria-labelledby="ask-title"
      className="relative isolate overflow-hidden rounded-3xl bg-ink-950 px-5 py-8 text-white shadow-[0_30px_80px_-40px_rgb(5_7_13/0.7)] sm:px-10 sm:py-12"
    >
      <div aria-hidden className="absolute inset-0 -z-10 bg-grid" />
      <div
        aria-hidden
        className="absolute -top-40 left-1/2 -z-10 h-[26rem] w-[48rem] -translate-x-1/2 bg-[radial-gradient(closest-side,rgb(79_70_229/0.35),transparent)]"
      />
      <p className="font-mono text-[11px] tracking-[0.18em] text-indigo-300 uppercase">New research</p>
      <h1 id="ask-title" className="mt-3 font-display text-4xl leading-[1.05] tracking-tight text-balance sm:text-5xl">
        What company do you want <em className="text-shine pr-1">to understand?</em>
      </h1>
      <p className="mt-3 max-w-2xl text-sm text-slate-400 sm:text-base">
        Ask about a company, a competitor or a market, anywhere from NASDAQ to NSE. Atlas researches it, argues both
        sides, and drafts a cited brief for you to review.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
        className="mt-7 rounded-2xl border border-white/12 bg-white/[0.06] p-2 backdrop-blur-md transition-colors focus-within:border-indigo-400/60 focus-within:bg-white/[0.08] sm:rounded-full"
      >
        <label htmlFor="research-query" className="sr-only">
          Your research question
        </label>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <div className="flex min-w-0 flex-1 items-center gap-2.5 px-3">
            <Icon name="search" className="h-5 w-5 shrink-0 text-slate-500" />
            <input
              id="research-query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. Should I worry about Helios Robotics as a competitor?"
              autoComplete="off"
              className="w-full min-w-0 bg-transparent py-2.5 text-base text-white placeholder:text-slate-500 focus:outline-none"
            />
          </div>
          <button type="submit" disabled={busy || tooShort} className={cx(btn.light, "sm:px-6")}>
            {busy ? "Researching…" : "Run research"}
            {!busy && <Icon name="arrowRight" />}
          </button>
        </div>
      </form>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="font-mono text-[10px] tracking-wider text-slate-500 uppercase">Try</span>
        {EXAMPLES.map((ex) => (
          <button
            key={ex.text}
            type="button"
            onClick={() => setQuery(ex.text)}
            disabled={busy}
            title={ex.demo ? "Covered by the demo documents" : "Researched from live sources"}
            className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-slate-300 transition-colors hover:border-white/25 hover:text-white disabled:opacity-50"
          >
            {ex.text}
          </button>
        ))}
      </div>
    </section>
  );
}
