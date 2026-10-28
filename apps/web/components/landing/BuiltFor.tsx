import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { Icon, type IconName } from "@/components/ui/Icon";
import { SectionHeading } from "./SectionHeading";

const AUDIENCES: { icon: IconName; title: string; body: string; ask: string }[] = [
  {
    icon: "trending",
    title: "Investors",
    body: "Pressure-test a thesis before the committee meeting, with both sides argued.",
    ask: "Should I invest in NVIDIA?",
  },
  {
    icon: "target",
    title: "Founders & operators",
    body: "Know exactly who you compete with, where they're strong and where they lag.",
    ask: "How does Stripe compare to Adyen?",
  },
  {
    icon: "building",
    title: "Corporate development",
    body: "A cited first look at an acquisition or partnership target, in minutes.",
    ask: "Evaluate Infosys as an acquisition partner",
  },
  {
    icon: "briefcase",
    title: "Sales & partnerships",
    body: "Walk into the meeting knowing their growth, news and priorities.",
    ask: "Reliance Industries: recent developments",
  },
];

export function BuiltFor() {
  return (
    <section id="built-for" aria-labelledby="built-for-title" className="relative scroll-mt-24 bg-white py-24 sm:py-28">
      <Container>
        <div className="reveal">
          <SectionHeading
            id="built-for-title"
            kicker="Who it's for"
            title="One brief, read by everyone"
            accent="who needs the facts."
            intro="Built for people who make decisions about companies and can't afford to guess."
          />
        </div>
        <ul className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {AUDIENCES.map((a) => (
            <li
              key={a.title}
              className="reveal group relative flex min-w-0 flex-col rounded-2xl border border-slate-200/80 bg-linear-to-b from-white to-slate-50/80 p-6 transition-all hover:-translate-y-0.5 hover:border-indigo-200 hover:shadow-[0_20px_50px_-24px_rgb(79_70_229/0.35)]"
            >
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-ink-950 text-indigo-200 shadow-[inset_0_1px_0_rgb(255_255_255/0.15)]">
                <Icon name={a.icon} className="h-5 w-5" />
              </span>
              <h3 className="mt-5 text-lg font-semibold tracking-tight text-slate-950">{a.title}</h3>
              <p className="mt-2 flex-1 text-sm leading-relaxed text-slate-600">{a.body}</p>
              <Link
                href={`/research?q=${encodeURIComponent(a.ask)}`}
                className="mt-5 flex items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 transition-colors group-hover:border-indigo-200 hover:text-indigo-700"
              >
                <span className="min-w-0 font-mono leading-snug">&ldquo;{a.ask}&rdquo;</span>
                <Icon name="arrowRight" className="h-3.5 w-3.5 shrink-0" />
              </Link>
            </li>
          ))}
        </ul>
      </Container>
    </section>
  );
}
