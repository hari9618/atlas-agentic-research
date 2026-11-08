import type { Metadata } from "next";
import { LearningDashboard } from "@/components/learning/LearningDashboard";
import { AppHeader } from "@/components/research/AppHeader";
import { Container } from "@/components/ui/Container";
import { Icon, type IconName } from "@/components/ui/Icon";
import { cx, monoLabel } from "@/components/ui/styles";

export const metadata: Metadata = {
  title: "How Atlas learns",
  description:
    "Atlas's self-improvement loop: every run is scored, failures become patterns, and one change at a time is tested against the current policy before release.",
};

const LOOP: { icon: IconName; title: string; text: string }[] = [
  { icon: "file", title: "Run & review", text: "A brief is drafted; a person approves, revises or rejects it." },
  { icon: "chart", title: "Score", text: "Each run is evaluated automatically for grounding and quality." },
  { icon: "search", title: "Diagnose", text: "Low scores and feedback cluster into failure patterns per agent." },
  { icon: "scale", title: "Experiment", text: "One change to one agent, tested against the current policy on the same queries." },
  { icon: "check", title: "Release or reject", text: "Only a change that wins ships, as a new version you can roll back." },
];

export default function LearningPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <AppHeader current="learning" />
      <main>
        <Container size="wide" className="py-8 sm:py-12">
          <header className="max-w-3xl">
            <p className={cx(monoLabel, "text-indigo-600")}>LLM Ops · self-improvement</p>
            <h1 className="mt-3 font-display text-4xl leading-[1.05] tracking-tight text-balance text-slate-950 sm:text-5xl">
              How Atlas gets better <em className="text-shine-dark">with every run</em>
            </h1>
            <p className="mt-4 text-base leading-relaxed text-slate-600">
              Nothing here is hand-tuned. Atlas scores its own work, finds where an agent keeps failing, proposes a single
              targeted change and runs a paired trial against the live policy. A change is released only if it wins, and every
              release is versioned.
            </p>
          </header>

          <ol aria-label="The improvement loop" className="mt-8 grid gap-2 sm:grid-cols-2 lg:grid-cols-5 lg:gap-3">
            {LOOP.map((s, i) => (
              <li
                key={s.title}
                className="relative flex gap-3 rounded-2xl border border-slate-200/80 bg-surface p-4 lg:flex-col lg:gap-0"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-indigo-700 ring-1 ring-slate-200/80">
                  <Icon name={s.icon} className="h-4.5 w-4.5" />
                </span>
                <div className="min-w-0 lg:mt-4">
                  <p className="flex items-baseline gap-2 text-sm font-semibold text-slate-950">
                    <span aria-hidden className="font-mono text-[10.5px] text-slate-400 tabular-nums">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    {s.title}
                  </p>
                  <p className="mt-1 text-[13px] leading-relaxed text-slate-600">{s.text}</p>
                </div>
                {i < LOOP.length - 1 && (
                  <Icon
                    name="arrowRight"
                    className="absolute top-1/2 -right-[0.875rem] z-10 hidden h-4 w-4 -translate-y-1/2 rounded-full bg-slate-50 text-slate-400 lg:block"
                  />
                )}
              </li>
            ))}
          </ol>

          <div className="mt-12 border-t border-slate-200/80 pt-8">
            <LearningDashboard />
          </div>
        </Container>
      </main>
    </div>
  );
}
