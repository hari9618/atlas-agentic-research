import { Container } from "@/components/ui/Container";
import { Icon, type IconName } from "@/components/ui/Icon";
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
    title: "Research any company",
    body: "Public or private, US or Indian, a market leader or a startup. Live web, SEC filings, market data, news, plus anything you upload.",
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
    <section id="features" aria-labelledby="features-title" className="scroll-mt-24 bg-white py-24 sm:py-28">
      <Container>
        <div className="reveal">
          <SectionHeading
            id="features-title"
            kicker="Features"
            title="Built to be checked,"
            accent="not just believed."
            intro="Atlas is designed around one idea: you should be able to see where every conclusion came from."
          />
        </div>
        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
          {FEATURES.map((f) => (
            <article
              key={f.title}
              className={cx(
                "reveal group relative flex min-w-0 flex-col overflow-hidden rounded-3xl border border-slate-200/80 bg-linear-to-b from-slate-50 to-white p-6 transition-shadow hover:shadow-[0_30px_60px_-30px_rgb(15_23_42/0.25)] sm:p-7",
                f.span,
                f.wide && "sm:col-span-2 lg:grid lg:grid-cols-[1fr_1.1fr] lg:items-center lg:gap-10",
              )}
            >
              <div>
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white text-indigo-700 shadow-xs ring-1 ring-slate-200">
                  <Icon name={f.icon} className="h-4.5 w-4.5" />
                </span>
                <h3 className="mt-5 text-xl font-semibold tracking-tight text-slate-950">{f.title}</h3>
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
