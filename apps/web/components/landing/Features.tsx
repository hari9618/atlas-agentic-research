import { Container } from "@/components/ui/Container";
import type { IconName } from "@/components/ui/Icon";
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

// Bento layout on a 6-column grid: two wide cards, three narrow, one wide footer card.
const FEATURES: { icon: IconName; title: string; body: string; visual: React.ReactNode; span: string; wide?: boolean }[] = [
  {
    icon: "link",
    title: "Every claim cited",
    body: "Numbers and statements link to the source they came from. A guardrail checks coverage and lowers the confidence score when evidence is thin.",
    visual: <CitationsVisual />,
    span: "lg:col-span-3",
  },
  {
    icon: "globe",
    title: "Made for companies nobody covers",
    body: "Startups and private companies included. Live web search, news, SEC filings where they exist, plus anything you upload.",
    visual: <SourcesVisual />,
    span: "lg:col-span-3",
  },
  {
    icon: "scale",
    title: "Bull vs bear stress test",
    body: "Both sides are argued from the same evidence, and a judge weighs them, so the report doesn't just tell you what you want to hear.",
    visual: <DebateVisual />,
    span: "lg:col-span-2",
  },
  {
    icon: "edit",
    title: "Human review loop",
    body: "Nothing is final until you approve it. Ask for changes and Atlas researches your feedback, up to three revisions.",
    visual: <ReviewVisual />,
    span: "lg:col-span-2",
  },
  {
    icon: "target",
    title: "Competitor intelligence",
    body: "Who the rivals are, how they compare, and how much of a threat each one is, in plain words.",
    visual: <CompetitorsVisual />,
    span: "lg:col-span-2",
  },
  {
    icon: "download",
    title: "Export a board-ready PDF",
    body: "A clean, paginated brief with a masthead, every section in order and sources at the end. Share it with a partner, an investment committee or your team.",
    visual: <PdfVisual />,
    span: "lg:col-span-6",
    wide: true,
  },
];

export function Features() {
  return (
    <section id="features" aria-labelledby="features-title" className="scroll-mt-24 bg-surface py-20 sm:py-24">
      <Container>
        <div className="">
          <SectionHeading
            id="features-title"
            kicker="Features"
            title="Built to be checked,"
            accent="not just believed."
            intro="Atlas is designed around one idea: you should be able to see where every conclusion came from."
          />
        </div>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
          {FEATURES.map((f) => (
            <article
              key={f.title}
              className={cx(
                "flex min-w-0 flex-col overflow-hidden rounded-xl border border-slate-200/80 bg-surface p-6",
                f.span,
                f.wide && "sm:col-span-2 lg:grid lg:grid-cols-[1fr_1.1fr] lg:items-center lg:gap-10",
              )}
            >
              <div>
                <h3 className="text-lg font-semibold tracking-tight text-slate-950">{f.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">{f.body}</p>
              </div>
              <div className={cx("min-w-0", f.wide ? "mt-6 lg:mt-0" : "mt-6 flex-1")}>{f.visual}</div>
            </article>
          ))}
        </div>
      </Container>
    </section>
  );
}
