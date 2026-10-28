import { Fragment } from "react";
import type { ReportSections, ResearchPayload } from "@/lib/api";
import { hasText, nonEmpty } from "@/lib/citations";
import { cx, surface } from "@/components/ui/styles";
import { EvidenceDebate } from "./EvidenceDebate";
import { MarkdownReport } from "./MarkdownReport";
import { ReportHeader } from "./ReportHeader";
import { ReportToc, type TocItem } from "./ReportToc";
import { Section, sectionId, type Ctx } from "./Section";
import { SourcesList, uniqueSources } from "./SourcesList";
import { BullBear, hasCases, hasOutlook, Outlook, Uncertainties } from "./sections/Cases";
import { Financials, hasFinancials } from "./sections/Financials";
import { Competitors, hasCompetitors, hasMarketPosition, MarketPosition } from "./sections/Market";
import { hasNews, NewsAndSentiment } from "./sections/News";
import { CompanyOverview, ExecutiveSummary, hasCompanyOverview, hasExecutiveSummary } from "./sections/Overview";
import { hasRisks, Risks } from "./sections/Risks";

type Block = { id: string; label: string; render: (n: number) => React.ReactNode };

/** The sections of a structured brief, in reading order, keeping only those with
 *  content. The same list drives the numbering and the table of contents. */
function structuredBlocks(s: ReportSections, c: Ctx, uncertainties: string[]): Block[] {
  const all: (Block & { show: boolean })[] = [
    { id: "summary", label: "Executive summary", show: hasExecutiveSummary(s), render: (n) => <ExecutiveSummary s={s} c={c} n={n} /> },
    { id: "overview", label: "Company overview", show: hasCompanyOverview(s), render: (n) => <CompanyOverview s={s} c={c} n={n} /> },
    { id: "financials", label: "Financials", show: hasFinancials(s), render: (n) => <Financials s={s} c={c} n={n} /> },
    { id: "market", label: "Market position", show: hasMarketPosition(s), render: (n) => <MarketPosition s={s} c={c} n={n} /> },
    { id: "competitors", label: "Competitors", show: hasCompetitors(s), render: (n) => <Competitors s={s} c={c} n={n} /> },
    { id: "developments", label: "News & sentiment", show: hasNews(s), render: (n) => <NewsAndSentiment s={s} c={c} n={n} /> },
    { id: "risks", label: "Key risks", show: hasRisks(s), render: (n) => <Risks s={s} c={c} n={n} /> },
    { id: "cases", label: "Bull vs bear", show: hasCases(s), render: (n) => <BullBear s={s} c={c} n={n} /> },
    { id: "outlook", label: "Outlook", show: hasOutlook(s), render: (n) => <Outlook s={s} c={c} n={n} /> },
    {
      id: "uncertainties",
      label: "Open questions",
      show: nonEmpty(uncertainties.filter(hasText)),
      render: (n) => <Uncertainties items={uncertainties} c={c} n={n} />,
    },
  ];
  return all.filter((b) => b.show);
}

/** The investor brief. Renders `report_sections` (every section optional, empty ones
 *  hidden); falls back to the markdown `report` when sections are missing.
 *
 *  Layout adapts to the width of its container (not the viewport), so it reads the
 *  same in the workspace, beside a review rail, and inside the landing-page frame. */
export function StructuredReport({
  payload,
  ns = "report",
  headingLevel = 2,
  revision,
  label,
  status,
  showEvidence = true,
  tocStickyClass = "top-20",
  className,
}: {
  payload: Partial<ResearchPayload>;
  ns?: string;
  headingLevel?: 2 | 3;
  revision?: number;
  label?: string;
  status?: React.ReactNode;
  showEvidence?: boolean;
  /** Sticky offset of the mobile section chips; match the page's sticky header. */
  tocStickyClass?: string;
  className?: string;
}) {
  const c: Ctx = { ns, hl: headingLevel };
  const s = payload.report_sections;
  const uncertainties = s?.uncertainties?.length ? s.uncertainties : payload.uncertainties ?? [];
  const confidence = payload.confidence ?? s?.confidence ?? null;
  const sources = uniqueSources(payload.citations ?? []);
  const findings = payload.findings ?? [];
  const debate = payload.debate ?? [];
  const hasEvidence = showEvidence && (findings.length > 0 || debate.length > 0);

  const blocks: Block[] = s
    ? structuredBlocks(s, c, uncertainties)
    : [
        ...(hasText(payload.report)
          ? [
              {
                id: "full-report",
                label: "Full report",
                render: (n: number) => (
                  <Section c={c} id="full-report" n={n} title="Full report" description="The analyst write-up, as drafted.">
                    <MarkdownReport report={payload.report!} ns={ns} bare />
                  </Section>
                ),
              },
            ]
          : []),
        ...(nonEmpty(uncertainties.filter(hasText))
          ? [
              {
                id: "uncertainties",
                label: "Open questions",
                render: (n: number) => <Uncertainties items={uncertainties} c={c} n={n} />,
              },
            ]
          : []),
      ];
  if (sources.length) {
    blocks.push({ id: "sources", label: "Sources", render: (n) => <SourcesList citations={sources} c={c} n={n} /> });
  }

  const toc: TocItem[] = [
    { id: sectionId(c, "brief"), label: "At a glance" },
    ...blocks.map((b, i) => ({ id: sectionId(c, b.id), label: b.label, n: i + 1 })),
    ...(hasEvidence ? [{ id: sectionId(c, "evidence"), label: "Appendix" }] : []),
  ];
  const company = s?.company || payload.target || "Research brief";

  return (
    <div className={cx("@container", className)}>
      <ReportHeader
        s={s ?? { company }}
        c={c}
        revision={revision}
        confidence={confidence}
        label={label}
        status={status}
      />

      <div className="mt-4 flex flex-col gap-4 @4xl:mt-6 @4xl:grid @4xl:grid-cols-[10.5rem_minmax(0,1fr)] @4xl:gap-8">
        <ReportToc items={toc} stickyClass={tocStickyClass} />

        <div className="min-w-0 space-y-4">
          {blocks.length > 0 && (
            <article aria-label={`${company} brief`} className={cx(surface, "@container overflow-hidden")}>
              <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-slate-200/70 bg-slate-50/60 px-5 py-2.5 font-mono text-[10.5px] tracking-[0.14em] text-slate-500 uppercase @2xl:px-10">
                <span className="min-w-0 truncate">Investor brief · {company}</span>
                <span className="tabular-nums">
                  {blocks.length} section{blocks.length === 1 ? "" : "s"}
                  {sources.length > 0 && ` · ${sources.length} source${sources.length === 1 ? "" : "s"}`}
                </span>
              </div>
              {blocks.map((b, i) => (
                <Fragment key={b.id}>{b.render(i + 1)}</Fragment>
              ))}
            </article>
          )}
          {hasEvidence && <EvidenceDebate id={sectionId(c, "evidence")} findings={findings} debate={debate} />}
        </div>
      </div>
    </div>
  );
}
