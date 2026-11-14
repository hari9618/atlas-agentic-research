import { Wordmark } from "@/components/landing/Wordmark";
import { Icon } from "@/components/ui/Icon";
import { cx, monoLabel } from "@/components/ui/styles";

type Lane = { name: string; detail: string; state: "done" | "active" | "idle" };

const LANES: Lane[] = [
  { name: "Fundamentals analyst", detail: "12 findings · 10-K, Q2 call", state: "done" },
  { name: "News analyst", detail: "8 findings · 30-day window", state: "done" },
  { name: "Risk analyst", detail: "Reading filings…", state: "active" },
  { name: "Market analyst", detail: "Sizing the category…", state: "active" },
  { name: "Bull vs bear debate", detail: "Waiting for evidence", state: "idle" },
];

const PROMISES = ["Every claim cited", "Both sides argued", "You approve the final brief"];

/** The brand half of the sign-in page (wide screens only): what Atlas is, and a still
 *  of a run in progress. Decorative apart from the headline; server-rendered. */
export function LoginAside() {
  return (
    <aside className="hidden bg-ink-950 text-white lg:flex lg:flex-col lg:justify-between lg:p-12 xl:p-16">

      <Wordmark tone="dark" />

      <div className="max-w-xl">
        <p className="font-mono text-2xs font-medium tracking-label text-slate-400 uppercase">Due diligence for private companies</p>
        <h2 className="mt-4 font-display text-5xl leading-[1.02] tracking-tight text-balance">
          Know the company before you commit.
        </h2>
        <p className="mt-5 max-w-md text-base leading-relaxed text-slate-400">
          Say who you are and what you need to decide. Atlas answers that first, argues both sides, and cites every
          claim.
        </p>

        <div
          aria-hidden
          className="mt-10 rounded-xl border border-white/10 bg-white/[0.03] p-4"
        >
          <div className="flex items-center justify-between border-b border-white/[0.08] pb-3">
            <p className={cx(monoLabel, "text-slate-400")}>Sample run · Helios Robotics</p>
            <span className="font-mono text-xs text-slate-400 tabular-nums">01:12</span>
          </div>
          <ul className="mt-2 divide-y divide-white/[0.06]">
            {LANES.map((l) => (
              <li key={l.name} className="flex items-center gap-3 py-2">
                <span
                  className={cx(
                    "flex h-6 w-6 shrink-0 items-center justify-center rounded-full",
                    l.state === "done" && "bg-emerald-400/15 text-emerald-300",
                    l.state === "active" && "bg-accent-400/15",
                    l.state === "idle" && "border border-white/10",
                  )}
                >
                  {l.state === "done" && <Icon name="check" className="h-3.5 w-3.5" strokeWidth={3} />}
                  {l.state === "active" && (
                    <>
                      <span className="h-2 w-2 rounded-full bg-accent-300" />
                    </>
                  )}
                </span>
                <span className="min-w-0 flex-1 text-sm text-slate-200">{l.name}</span>
                <span className="truncate font-mono text-2xs text-slate-400">{l.detail}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <ul className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-400">
        {PROMISES.map((p) => (
          <li key={p} className="flex items-center gap-2">
            <Icon name="check" className="h-4 w-4 text-accent-300" strokeWidth={3} />
            {p}
          </li>
        ))}
      </ul>
    </aside>
  );
}
