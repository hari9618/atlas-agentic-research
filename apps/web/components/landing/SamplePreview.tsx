import Link from "next/link";
import { SAMPLE_PAYLOAD } from "@/lib/sample-report";
import { StructuredReport } from "@/components/report/StructuredReport";
import { Container } from "@/components/ui/Container";
import { Icon } from "@/components/ui/Icon";
import { btn } from "@/components/ui/styles";
import { SectionHeading } from "./SectionHeading";

export function SamplePreview() {
  return (
    <section
      id="sample-report"
      aria-labelledby="sample-title"
      className="scroll-mt-24 bg-slate-50 py-20 sm:py-24"
    >
      <Container>
        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <SectionHeading
            id="sample-title"
            kicker="Sample report"
            title="A sample brief."
            intro="The real report layout, filled from the demo documents on a fictional company, Helios Robotics, asked as a competitor check."
          />
          <Link href="/research" className={btn.primary}>
            Run your own
            <Icon name="arrowRight" />
          </Link>
        </div>
        <div className="mx-auto mt-10 max-w-5xl">
          <StructuredReport payload={SAMPLE_PAYLOAD} ns="preview" headingLevel={3} revision={1} label="Sample" />
        </div>
      </Container>
    </section>
  );
}
