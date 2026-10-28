import { Container } from "@/components/ui/Container";
import { Icon, type IconName } from "@/components/ui/Icon";
import { SectionHeading } from "./SectionHeading";

const STEPS: { icon: IconName; title: string; body: string }[] = [
  {
    icon: "search",
    title: "Ask a question",
    body: "Name a company or ask what you need to know: \"Should I invest in NVIDIA?\" or \"How does Stripe compare to Adyen?\"",
  },
  {
    icon: "users",
    title: "Analysts research in parallel",
    body: "Financials, news and sentiment, market and competitors, and risk, each pulling from filings, market data, news and the web.",
  },
  {
    icon: "scale",
    title: "Bull vs bear debate",
    body: "One agent argues the optimistic case, another the cautious one, and a judge weighs them so you see both sides.",
  },
  {
    icon: "file",
    title: "A cited brief",
    body: "A structured report where every claim carries a source, and a confidence score reflects how well evidence covers it.",
  },
  {
    icon: "check",
    title: "You review and approve",
    body: "Approve the draft, or ask for changes like \"go deeper on financials\". Atlas researches your feedback and redrafts.",
  },
];

export function HowItWorks() {
  return (
    <section
      id="how-it-works"
      aria-labelledby="how-title"
      className="relative isolate scroll-mt-24 overflow-hidden border-y border-slate-200/70 bg-slate-50 py-24 sm:py-28"
    >
      <div aria-hidden className="absolute inset-0 -z-10 bg-grid-light" />
      <Container>
        <div className="reveal">
          <SectionHeading
            id="how-title"
            kicker="How it works"
            title="From question to reviewed brief,"
            accent="in five steps."
            intro="The same process a good analyst follows, run by a team of agents and checked by you."
          />
        </div>
        <ol className="mt-14 grid gap-4 md:grid-cols-5">
          {STEPS.map((s, i) => (
            <li
              key={s.title}
              className="reveal relative flex flex-col rounded-2xl border border-slate-200/80 bg-white/90 p-5 shadow-[0_1px_2px_rgb(15_23_42/0.04)] backdrop-blur"
            >
              <div className="flex items-center justify-between">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-50 text-indigo-700 ring-1 ring-indigo-100">
                  <Icon name={s.icon} className="h-4.5 w-4.5" />
                </span>
                <span className="font-display text-3xl text-slate-300">{String(i + 1).padStart(2, "0")}</span>
              </div>
              <h3 className="mt-5 text-base font-semibold tracking-tight text-slate-950">{s.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">{s.body}</p>
              {i < STEPS.length - 1 && (
                <span
                  aria-hidden
                  className="absolute top-1/2 -right-3 z-10 hidden h-6 w-6 -translate-y-1/2 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-400 md:flex"
                >
                  <Icon name="arrowRight" className="h-3 w-3" />
                </span>
              )}
            </li>
          ))}
        </ol>
      </Container>
    </section>
  );
}
