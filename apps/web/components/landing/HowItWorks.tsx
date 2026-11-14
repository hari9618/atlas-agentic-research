import { Container } from "@/components/ui/Container";
import { SectionHeading } from "./SectionHeading";

const STEPS: { title: string; body: string }[] = [
  {
    title: "Ask, and say who you are",
    body: "\"My company is caughtleads.com. Should I worry about revsquad.ai?\" The angle (competitor, buyer, investor...) shapes the brief.",
  },
  {
    title: "Analysts research in parallel",
    body: "Fundamentals, news and customer sentiment, market and competitors, and risk, from the web, news, filings and your documents.",
  },
  {
    title: "Bull vs bear",
    body: "One agent argues the case for, another the case against, and a judge weighs them on the same evidence.",
  },
  {
    title: "A cited brief, answer first",
    body: "Your verdict at the top, then the facts behind it. Every claim carries a source; thin evidence lowers the confidence score.",
  },
  {
    title: "You review",
    body: "Approve it, or ask for changes to one section. Atlas researches your feedback and redrafts, up to three times.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" aria-labelledby="how-title" className="scroll-mt-24 border-y border-slate-200/80 bg-slate-50 py-20 sm:py-24">
      <Container>
        <SectionHeading
          id="how-title"
          kicker="How it works"
          title="From question to reviewed brief."
          intro="The process a careful analyst follows, run by a team of agents and checked by you."
        />
        <ol className="mt-10 grid gap-x-8 gap-y-6 border-t border-slate-200/80 pt-8 sm:grid-cols-2 lg:grid-cols-5">
          {STEPS.map((s, i) => (
            <li key={s.title} className="min-w-0">
              <p className="font-mono text-xs text-slate-500 tabular-nums">{String(i + 1).padStart(2, "0")}</p>
              <h3 className="mt-2 text-base font-semibold text-slate-950">{s.title}</h3>
              <p className="mt-1 text-sm leading-relaxed text-slate-600">{s.body}</p>
            </li>
          ))}
        </ol>
      </Container>
    </section>
  );
}
