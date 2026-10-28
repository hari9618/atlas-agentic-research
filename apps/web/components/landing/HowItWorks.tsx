import { Container } from "@/components/ui/Container";
import { SectionHeading } from "./SectionHeading";

const STEPS = [
  {
    title: "Ask a question",
    body: "Name a company or ask what you need to know: \"Should I invest in NVIDIA?\" or \"How does Stripe compare to Adyen?\"",
  },
  {
    title: "Specialists research in parallel",
    body: "Four analysts work at once: financials, news and sentiment, market and competitors, and risk. Each pulls from filings, market data, news and the web.",
  },
  {
    title: "Bull vs bear debate",
    body: "One agent argues the optimistic case, another the cautious one, and a judge weighs them so you see both sides.",
  },
  {
    title: "A cited report",
    body: "Atlas writes a structured brief. Every claim carries a source, and a confidence score reflects how well the evidence covers it.",
  },
  {
    title: "You review and approve",
    body: "Approve the draft, or ask for changes like \"go deeper on financials\". Atlas researches your feedback and redrafts.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" aria-labelledby="how-title" className="scroll-mt-20 py-20 sm:py-24">
      <Container>
        <SectionHeading
          id="how-title"
          kicker="How it works"
          title="From question to reviewed brief"
          intro="The same process a good analyst follows, run by a team of agents and checked by you."
        />
        <ol className="mt-12 grid gap-6 md:grid-cols-5 md:gap-4">
          {STEPS.map((s, i) => (
            <li key={s.title} className="relative flex gap-4 md:flex-col md:gap-0">
              {i < STEPS.length - 1 && (
                <span
                  aria-hidden
                  className="absolute top-10 bottom-[-1.5rem] left-[19px] w-px bg-slate-200 md:top-5 md:right-[-1rem] md:bottom-auto md:left-12 md:h-px md:w-auto"
                />
              )}
              <span className="relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-indigo-200 bg-indigo-50 text-sm font-semibold text-indigo-700">
                {i + 1}
              </span>
              <div className="md:mt-4">
                <h3 className="text-base font-semibold text-slate-900">{s.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{s.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </Container>
    </section>
  );
}
