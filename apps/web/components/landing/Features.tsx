import { Container } from "@/components/ui/Container";
import { Icon } from "@/components/ui/Icon";
import { cx } from "@/components/ui/styles";
import {
  CitationsVisual,
  CompetitorsVisual,
  DebateVisual,
  PdfVisual,
  ReviewVisual,
  SourcesVisual,
} from "./FeatureVisuals";
import { SectionHeading } from "./SectionHeading";

const FEATURES: { title: string; body: string; bullets: string[]; visual: React.ReactNode }[] = [
  {
    title: "Research any company",
    body: "Public or private, a market leader or a startup. Atlas pulls live web results, SEC filings, market data and recent news, plus anything you upload.",
    bullets: [
      "SEC EDGAR filings and stock data for listed companies",
      "News and web coverage for private companies",
      "Your own decks, reports and notes, searchable on the next run",
    ],
    visual: <SourcesVisual />,
  },
  {
    title: "Every claim cited",
    body: "Numbers and statements in the report link to the source they came from. A guardrail checks coverage and lowers the confidence score when evidence is thin.",
    bullets: [
      "Inline source tags you can click through",
      "Web results are marked so they aren't mistaken for primary sources",
      "An explicit list of what we're not sure about",
    ],
    visual: <CitationsVisual />,
  },
  {
    title: "Bull vs bear stress test",
    body: "Before anything is written, one agent argues the optimistic case and another the cautious one. A judge weighs both, so the report doesn't just tell you what you want to hear.",
    bullets: [
      "Both sides argued from the same evidence",
      "The stance (positive, neutral or cautious) comes out of the debate",
      "The full transcript is in the report for anyone who wants to check",
    ],
    visual: <DebateVisual />,
  },
  {
    title: "Human review loop",
    body: "Nothing is final until you say so. Approve the draft or tell Atlas what to change; it researches your feedback and writes a new revision.",
    bullets: [
      "One-click requests like \"deeper financials\" or \"focus on risks\"",
      "Each revision is numbered so you can see what changed",
      "Up to three rounds of changes per report",
    ],
    visual: <ReviewVisual />,
  },
  {
    title: "Competitor intelligence",
    body: "Ask how a company stacks up and get a side-by-side view: who the competitors are, how they compare and how much of a threat each one is.",
    bullets: [
      "Threat level for each competitor",
      "Strengths and weaknesses in plain words",
      "Market position and what to watch next",
    ],
    visual: <CompetitorsVisual />,
  },
  {
    title: "Export to PDF",
    body: "Download a clean, paginated brief to share with a partner, an investment committee or your team.",
    bullets: [
      "Masthead with company, stance and confidence",
      "Every section in order, with sources at the end",
      "Prints cleanly from any modern browser",
    ],
    visual: <PdfVisual />,
  },
];

export function Features() {
  return (
    <section id="features" aria-labelledby="features-title" className="scroll-mt-20 border-y border-slate-200 bg-slate-50 py-20 sm:py-24">
      <Container>
        <SectionHeading
          id="features-title"
          kicker="Features"
          title="Built to be checked, not just believed"
          intro="Atlas is designed around one idea: you should be able to see where every conclusion came from."
        />
        <div className="mt-14 space-y-16 sm:space-y-20">
          {FEATURES.map((f, i) => (
            <div key={f.title} className="grid items-center gap-8 md:grid-cols-2 md:gap-14">
              <div className={cx(i % 2 === 1 && "md:order-2")}>
                <h3 className="text-2xl font-semibold tracking-tight text-slate-900">{f.title}</h3>
                <p className="mt-3 text-base leading-relaxed text-slate-600">{f.body}</p>
                <ul className="mt-5 space-y-2.5">
                  {f.bullets.map((b) => (
                    <li key={b} className="flex gap-3 text-sm text-slate-700">
                      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-50 text-indigo-700">
                        <Icon name="check" className="h-3 w-3" strokeWidth={3} />
                      </span>
                      {b}
                    </li>
                  ))}
                </ul>
              </div>
              <div className={cx("min-w-0", i % 2 === 1 && "md:order-1")}>{f.visual}</div>
            </div>
          ))}
        </div>
      </Container>
    </section>
  );
}
