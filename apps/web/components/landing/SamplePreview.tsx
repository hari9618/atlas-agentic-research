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
      className="relative isolate scroll-mt-24 overflow-hidden bg-slate-50 py-24 sm:py-28"
    >
      <div aria-hidden className="absolute inset-x-0 top-0 -z-10 h-[40rem] bg-grid-light" />
      <Container>
        <div className="reveal flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <SectionHeading
            id="sample-title"
            kicker="Sample report"
            title="What lands on"
            accent="your desk."
            intro="A real Atlas brief layout, filled with sample data from our demo documents on a fictional company, Helios Robotics."
          />
          <Link href="/research" className={btn.primary}>
            Run your own
            <Icon name="arrowRight" />
          </Link>
        </div>
        <div className="relative mx-auto mt-12 max-w-4xl">
          <div
            aria-hidden
            className="absolute -inset-6 -z-10 rounded-[2.5rem] bg-[radial-gradient(60%_50%_at_50%_0%,rgb(99_102_241/0.18),transparent_70%)] blur-xl"
          />
          <div className="rounded-[1.75rem] border border-slate-200/80 bg-white/70 p-2 shadow-[0_40px_100px_-40px_rgb(15_23_42/0.35)] backdrop-blur sm:p-3">
            <div className="flex items-center gap-1.5 px-3 pt-1 pb-3" aria-hidden>
              <span className="h-2.5 w-2.5 rounded-full bg-slate-200" />
              <span className="h-2.5 w-2.5 rounded-full bg-slate-200" />
              <span className="h-2.5 w-2.5 rounded-full bg-slate-200" />
              <span className="ml-3 font-mono text-[11px] text-slate-400">atlas · helios-robotics-brief</span>
            </div>
            <div className="rounded-[1.25rem] bg-slate-50 p-2 sm:p-4">
              <StructuredReport payload={SAMPLE_PAYLOAD} ns="preview" headingLevel={3} revision={1} label="Sample" />
            </div>
          </div>
        </div>
      </Container>
    </section>
  );
}
