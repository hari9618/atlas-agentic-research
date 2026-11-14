"use client";

import { Icon } from "@/components/ui/Icon";
import { Spinner } from "@/components/ui/Spinner";
import { btn, cx, surface, tap } from "@/components/ui/styles";

/** Background health of the API (it cold-starts on a free tier). */
export type EngineState = "checking" | "ready" | "waking" | "unreachable" | "offline";

const MAX_QUERY = 500;

const ENGINE: Record<EngineState, { dot: string; text: string }> = {
  checking: { dot: "bg-slate-400", text: "Checking the research engine…" },
  ready: { dot: "bg-emerald-500", text: "Research engine online" },
  waking: { dot: "bg-amber-500", text: "Research engine is waking up. The first run may take a minute to start." },
  unreachable: { dot: "bg-rose-500", text: "Research engine not responding. Atlas will keep trying when you run." },
  offline: { dot: "bg-rose-500", text: "You're offline. Reconnect to run research." },
};

function EngineStatus({ state }: { state: EngineState }) {
  const e = ENGINE[state];
  return (
    <p role="status" className="flex items-center gap-2 text-xs text-slate-500">
      <span aria-hidden className={cx("h-1.5 w-1.5 shrink-0 rounded-full", e.dot)} />
      <span className="min-w-0">{e.text}</span>
    </p>
  );
}

/** One per angle, so the examples also teach that saying who you are changes the brief. */
const EXAMPLES: { label: string; text: string; demo?: boolean }[] = [
  { label: "Competitor", text: "My company is caughtleads.com. Should I worry about revsquad.ai?" },
  { label: "Buyer", text: "Should we buy from gong.io? What does it cost for 20 reps?" },
  { label: "Investor", text: "Is linear.app a good investment?" },
  { label: "Job seeker", text: "I have an offer from posthog.com. Is it a stable place to join?" },
  { label: "Demo data", text: "Should I worry about Helios Robotics as a competitor?", demo: true },
];

/** The question composer. A full panel with examples before the first run; once a run
 *  starts it collapses into a slim bar so the brief gets the screen. */
export function QueryBox({
  query,
  setQuery,
  onSubmit,
  busy,
  busyLabel = "Researching…",
  compact = false,
  engine,
  offline = false,
}: {
  query: string;
  setQuery: (q: string) => void;
  onSubmit: () => void;
  busy: boolean;
  busyLabel?: string;
  compact?: boolean;
  engine?: EngineState;
  offline?: boolean;
}) {
  const tooShort = query.trim().length < 3;
  const blocked = busy || tooShort || offline;
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit();
  };

  const field = (placeholder: string) => (
    <div className="relative min-w-0 flex-1">
      <Icon name="search" className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-500" />
      <input
        id="research-query"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={placeholder}
        autoComplete="off"
        maxLength={MAX_QUERY}
        enterKeyHint="go"
        className="h-10 w-full rounded-lg border border-slate-300 bg-surface pr-3 pl-10 text-base text-slate-950 placeholder:text-slate-500 hover:border-slate-400 focus:border-indigo-600 focus:ring-4 focus:ring-indigo-600/15 focus:outline-none sm:text-sm"
      />
    </div>
  );

  const button = (idle: string) => (
    <button type="submit" disabled={blocked} className={cx(btn.primary, "h-10 shrink-0", tap)}>
      {busy ? (
        <>
          <Spinner className="h-4 w-4" />
          {busyLabel}
        </>
      ) : (
        <>
          {idle}
          <Icon name="arrowRight" />
        </>
      )}
    </button>
  );

  if (compact) {
    return (
      <section aria-labelledby="ask-title" className={cx(surface, "p-2")}>
        <h1 id="ask-title" className="sr-only">
          Research workspace
        </h1>
        <form onSubmit={submit} className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <label htmlFor="research-query" className="sr-only">
            Your research question
          </label>
          {field("Ask about another company…")}
          {button("New research")}
        </form>
      </section>
    );
  }

  return (
    <section aria-labelledby="ask-title" className={cx(surface, "p-5 sm:p-6")}>
      <h1 id="ask-title" className="text-xl font-semibold tracking-tight text-slate-950">
        New research
      </h1>
      <p className="mt-1 max-w-2xl text-sm leading-relaxed text-slate-600">
        Name the company, and say who you are and what you need to decide. Atlas answers that first, with a source for
        every claim.
      </p>

      <form onSubmit={submit} className="mt-4 flex flex-col gap-2 sm:flex-row">
        <label htmlFor="research-query" className="sr-only">
          Your research question
        </label>
        {field("e.g. My company is acme.com. Should I worry about rival.io?")}
        {button("Run research")}
      </form>

      <div className="mt-3">
        <EngineStatus state={offline ? "offline" : (engine ?? "checking")} />
      </div>

      <div className="mt-5 border-t border-slate-200/80 pt-4">
        <p className="text-xs font-medium text-slate-500">Examples</p>
        <ul className="mt-2 -mx-2">
          {EXAMPLES.map((ex) => (
            <li key={ex.text}>
              <button
                type="button"
                onClick={() => setQuery(ex.text)}
                disabled={busy}
                title={ex.demo ? "Covered by the demo documents" : "Researched from live sources"}
                className={cx(
                  "flex w-full flex-col gap-0 rounded-md px-2 py-1 text-left text-sm transition-colors hover:bg-slate-100 disabled:opacity-50 sm:flex-row sm:items-baseline sm:gap-3",
                  tap,
                )}
              >
                <span className="shrink-0 text-xs text-slate-500 sm:w-24">{ex.label}</span>
                <span className="min-w-0 text-slate-800">{ex.text}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
