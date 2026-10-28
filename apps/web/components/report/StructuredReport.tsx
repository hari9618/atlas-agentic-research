import type { ResearchPayload } from "@/lib/api";
import { hasText } from "@/lib/citations";
import { cx } from "@/components/ui/styles";
import { EvidenceDebate } from "./EvidenceDebate";
import { MarkdownReport } from "./MarkdownReport";
import { ReportHeader } from "./ReportHeader";
import type { Ctx } from "./Section";
import { SourcesList } from "./SourcesList";
import { BottomLine, BullBear, Outlook, Uncertainties } from "./sections/Cases";
import { Financials } from "./sections/Financials";
import { Competitors, MarketPosition } from "./sections/Market";
import { RecentDevelopments, SentimentSection } from "./sections/News";
import { CompanyOverview, ExecutiveSummary } from "./sections/Overview";
import { Risks } from "./sections/Risks";

/** The investor brief. Renders `report_sections` (every section optional, empty ones
 *  hidden); falls back to the markdown `report` when sections are missing. */
export function StructuredReport({
  payload,
  ns = "report",
  headingLevel = 2,
  revision,
  label,
  status,
  showEvidence = true,
  className,
}: {
  payload: Partial<ResearchPayload>;
  ns?: string;
  headingLevel?: 2 | 3;
  revision?: number;
  label?: string;
  status?: React.ReactNode;
  showEvidence?: boolean;
  className?: string;
}) {
  const c: Ctx = { ns, hl: headingLevel };
  const s = payload.report_sections;
  const uncertainties = s?.uncertainties?.length ? s.uncertainties : payload.uncertainties ?? [];
  const confidence = payload.confidence ?? s?.confidence ?? null;

  return (
    <div className={cx("space-y-4 sm:space-y-5", className)}>
      {s ? (
        <>
          <ReportHeader s={s} c={c} revision={revision} confidence={confidence} label={label} status={status} />
          <ExecutiveSummary s={s} c={c} />
          <CompanyOverview s={s} c={c} />
          <Financials s={s} c={c} />
          <MarketPosition s={s} c={c} />
          <Competitors s={s} c={c} />
          <RecentDevelopments s={s} c={c} />
          <SentimentSection s={s} c={c} />
          <Risks s={s} c={c} />
          <BullBear s={s} c={c} />
          <Outlook s={s} c={c} />
          <BottomLine s={s} c={c} />
        </>
      ) : (
        <>
          <ReportHeader
            s={{ company: payload.target || "Research brief" }}
            c={c}
            revision={revision}
            confidence={confidence}
            label={label}
            status={status}
          />
          {hasText(payload.report) && <MarkdownReport report={payload.report} ns={ns} />}
        </>
      )}
      <Uncertainties items={uncertainties} c={c} />
      <SourcesList citations={payload.citations ?? []} c={c} />
      {showEvidence && <EvidenceDebate findings={payload.findings ?? []} debate={payload.debate ?? []} />}
    </div>
  );
}
