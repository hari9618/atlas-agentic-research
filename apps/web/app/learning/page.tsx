import type { Metadata } from "next";
import { LearningDashboard } from "@/components/learning/LearningDashboard";
import { AppHeader } from "@/components/research/AppHeader";
import { Container } from "@/components/ui/Container";
import { Icon } from "@/components/ui/Icon";

export const metadata: Metadata = {
  title: "Learning loop",
  description:
    "How Atlas improves: runs are scored, failures become patterns, and one change at a time is tested against the live policy before release.",
};

const LOOP = ["Run & review", "Score", "Diagnose", "Experiment", "Release or reject"];

export default function LearningPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <AppHeader current="learning" />
      <main>
        <Container size="wide" className="py-8">
          <header className="max-w-3xl">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Learning loop</h1>
            <p className="mt-1 text-sm leading-relaxed text-slate-600">
              Every finished run is scored. Recurring failures become a single, targeted change to one agent, which is
              tested against the live policy on the same questions. A change ships only if it wins, as a new version
              that can be rolled back.
            </p>
            <ol aria-label="The improvement loop" className="mt-4 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-slate-600">
              {LOOP.map((step, i) => (
                <li key={step} className="flex items-center gap-2">
                  {i > 0 && <Icon name="arrowRight" className="h-3.5 w-3.5 text-slate-400" />}
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </header>

          <div className="mt-8 border-t border-slate-200/80 pt-8">
            <LearningDashboard />
          </div>
        </Container>
      </main>
    </div>
  );
}
