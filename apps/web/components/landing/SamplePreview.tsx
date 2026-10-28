import Link from "next/link";
import { SAMPLE_PAYLOAD } from "@/lib/sample-report";
import { StructuredReport } from "@/components/report/StructuredReport";
import { Container } from "@/components/ui/Container";
import { Icon } from "@/components/ui/Icon";
import { btn } from "@/components/ui/styles";
import { SectionHeading } from "./SectionHeading";

export function SamplePreview() {
  return (
    <section id="sample-report" aria-labelledby="sample-title" className="scroll-mt-20 py-20 sm:py-24">
      <Container>
        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <SectionHeading
            id="sample-title"
            kicker="Sample report"
            title="What you get back"
            intro="A real Atlas brief layout, filled with sample data from our demo documents on a fictional company, Helios Robotics."
          />
          <Link href="/research" className={btn.secondary}>
            Run your own
            <Icon name="arrowRight" />
          </Link>
        </div>
        <div className="mx-auto mt-10 max-w-4xl rounded-2xl border border-slate-200 bg-slate-50 p-2 sm:p-4">
          <StructuredReport payload={SAMPLE_PAYLOAD} ns="preview" headingLevel={3} revision={1} label="Sample" />
        </div>
      </Container>
    </section>
  );
}
