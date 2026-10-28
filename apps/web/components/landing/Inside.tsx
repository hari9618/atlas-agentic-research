import { Container } from "@/components/ui/Container";
import { Icon, type IconName } from "@/components/ui/Icon";
import { cx } from "@/components/ui/styles";
import { SectionHeading } from "./SectionHeading";

// "Under the hood": the agent pipeline as a flow diagram, plus the engineering that
// makes it trustworthy. Every statement here describes what the backend really does.

const ANALYSTS = ["Fundamentals", "News & sentiment", "Market & competitors", "Risk"];

const PILLARS: { icon: IconName; title: string; body: string }[] = [
  {
    icon: "search",
    title: "Grounded retrieval",
    body: "Keyword + semantic search with re-ranking, and a self-correcting loop that falls back to the live web when your documents don't cover the company.",
  },
  {
    icon: "shield",
    title: "A citation guardrail",
    body: "Every claim must point to retrieved evidence. Coverage is measured, and thin evidence lowers the confidence score instead of hiding.",
  },
  {
    icon: "refresh",
    title: "Resilient by default",
    body: "Rate limits and timeouts retry with backoff. If one analyst still fails, its section is marked unavailable and the rest of the brief ships.",
  },
  {
    icon: "database",
    title: "Pause, review, resume",
    body: "Runs are checkpointed in Postgres, so a draft waiting for your review survives restarts and picks up exactly where it stopped.",
  },
  {
    icon: "activity",
    title: "Observed and scored",
    body: "Every agent step is traced, and each brief is scored for faithfulness, relevance and citation coverage.",
  },
  {
    icon: "layers",
    title: "Memory that compounds",
    body: "Past research is remembered and distilled, so the next question about a company starts from what Atlas already learned.",
  },
];

function Node({
  label,
  sub,
  tone = "default",
  className,
}: {
  label: string;
  sub?: string;
  tone?: "default" | "accent" | "bull" | "bear" | "you";
  className?: string;
}) {
  return (
    <div
      className={cx(
        "rounded-xl border px-3.5 py-2.5 text-center",
        tone === "default" && "border-white/10 bg-white/[0.04]",
        tone === "accent" && "border-indigo-400/30 bg-indigo-500/10",
        tone === "bull" && "border-emerald-400/25 bg-emerald-400/[0.07]",
        tone === "bear" && "border-rose-400/25 bg-rose-400/[0.07]",
        tone === "you" && "border-white/30 bg-white text-ink-950",
        className,
      )}
    >
      <p className={cx("text-sm font-medium", tone === "you" ? "text-ink-950" : "text-slate-100")}>{label}</p>
      {sub && <p className={cx("mt-0.5 text-[11px]", tone === "you" ? "text-slate-600" : "text-slate-500")}>{sub}</p>}
    </div>
  );
}

function Arrow() {
  return (
    <span aria-hidden className="flex items-center justify-center text-slate-600">
      <Icon name="arrowRight" className="hidden h-4 w-4 lg:block" />
      <Icon name="chevron" className="h-4 w-4 lg:hidden" />
    </span>
  );
}

function Pipeline() {
  return (
    <figure className="reveal relative mt-14 rounded-3xl border border-white/[0.08] bg-ink-900/60 p-5 sm:p-8">
      <figcaption className="mb-6 flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono text-[11px] tracking-[0.18em] text-slate-500 uppercase">One research run</span>
        <span className="font-mono text-[11px] text-slate-500">LangGraph · checkpointed state</span>
      </figcaption>
      <div className="grid items-center gap-3 lg:grid-cols-[1fr_auto_1fr_auto_1.4fr_auto_1fr_auto_1fr_auto_1fr]">
        <Node label="Your question" sub="any company" />
        <Arrow />
        <Node label="Supervisor" sub="plans the work" tone="accent" />
        <Arrow />
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-1">
          {ANALYSTS.map((a) => (
            <Node key={a} label={a} className="py-2" />
          ))}
        </div>
        <Arrow />
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-1">
          <Node label="Bull" sub="the upside" tone="bull" />
          <Node label="Bear" sub="the risks" tone="bear" />
        </div>
        <Arrow />
        <Node label="Writer + judge" sub="cited brief" tone="accent" />
        <Arrow />
        <Node label="You" sub="approve or revise" tone="you" />
      </div>
      <div className="mt-6 flex items-center gap-3 rounded-xl border border-dashed border-indigo-400/30 bg-indigo-500/[0.06] px-4 py-3 text-sm text-indigo-200">
        <Icon name="refresh" className="h-4 w-4 shrink-0" />
        <span>
          <span className="font-medium text-white">Request changes</span> and your feedback loops back to the analysts
          for targeted follow-up research, then a new revision. Up to three rounds.
        </span>
      </div>
    </figure>
  );
}

export function Inside() {
  return (
    <section
      id="inside"
      aria-labelledby="inside-title"
      className="relative isolate scroll-mt-24 overflow-hidden bg-ink-950 py-24 text-white sm:py-28"
    >
      <div aria-hidden className="absolute inset-0 -z-10 bg-grid" />
      <div
        aria-hidden
        className="absolute -top-40 right-0 -z-10 h-[34rem] w-[50rem] bg-[radial-gradient(closest-side,rgb(79_70_229/0.25),transparent)]"
      />
      <Container>
        <div className="reveal">
          <SectionHeading
            id="inside-title"
            tone="dark"
            kicker="Under the hood"
            title="Structured like an investment team,"
            accent="engineered like infrastructure."
            intro="A multi-agent system with grounded retrieval, guardrails, retries and a human in the loop, not a single prompt."
          />
        </div>
        <Pipeline />
        <ul className="mt-6 grid gap-px overflow-hidden rounded-3xl border border-white/[0.08] bg-white/[0.08] sm:grid-cols-2 lg:grid-cols-3">
          {PILLARS.map((p) => (
            <li key={p.title} className="reveal bg-ink-950 p-6 sm:p-7">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-indigo-300">
                <Icon name={p.icon} className="h-4.5 w-4.5" />
              </span>
              <h3 className="mt-5 text-base font-semibold text-white">{p.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">{p.body}</p>
            </li>
          ))}
        </ul>
      </Container>
    </section>
  );
}
