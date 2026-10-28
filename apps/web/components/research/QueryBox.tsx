"use client";

import { Icon } from "@/components/ui/Icon";
import { btn, cx } from "@/components/ui/styles";

const EXAMPLES: { text: string; demo?: boolean }[] = [
  { text: "Should I invest in NVIDIA?" },
  { text: "How does Stripe compare to Adyen?" },
  { text: "Evaluate Helios Robotics as a competitor", demo: true },
  { text: "What are Helios Robotics' biggest risks?", demo: true },
  { text: "Compare Helios Robotics and Aster Dynamics", demo: true },
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
    <section aria-labelledby="ask-title">
      <h1 id="ask-title" className="text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">
        What company do you want to understand?
      </h1>
      <p className="mt-1.5 text-sm text-slate-600 sm:text-base">
        Ask about a company, a competitor or a market. Atlas researches it, argues both sides, and
        drafts a cited brief for you to review.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
        className="mt-5 rounded-xl border border-slate-300 bg-white p-2 shadow-sm focus-within:border-indigo-500 focus-within:ring-4 focus-within:ring-indigo-100"
      >
        <label htmlFor="research-query" className="sr-only">
          Your research question
        </label>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <div className="flex min-w-0 flex-1 items-center gap-2 px-2">
            <Icon name="search" className="h-5 w-5 shrink-0 text-slate-400" />
            <input
              id="research-query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. Should I worry about Helios Robotics as a competitor?"
              autoComplete="off"
              className="w-full min-w-0 bg-transparent py-2.5 text-base text-slate-900 placeholder:text-slate-500 focus:outline-none"
            />
          </div>
          <button type="submit" disabled={busy || tooShort} className={cx(btn.primary, "sm:px-5")}>
            {busy ? "Researching…" : "Run research"}
            {!busy && <Icon name="arrowRight" />}
          </button>
        </div>
      </form>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="text-xs text-slate-500">Try:</span>
        {EXAMPLES.map((ex) => (
          <button
            key={ex.text}
            type="button"
            onClick={() => setQuery(ex.text)}
            disabled={busy}
            title={ex.demo ? "Covered by the demo documents" : "Researched from live sources"}
            className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-700 transition-colors hover:border-indigo-300 hover:text-indigo-700 disabled:opacity-50"
          >
            {ex.text}
          </button>
        ))}
      </div>
    </section>
  );
}
