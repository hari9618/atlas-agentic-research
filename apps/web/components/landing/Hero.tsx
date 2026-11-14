import type { CSSProperties } from "react";
import Form from "next/form";
import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { Icon } from "@/components/ui/Icon";
import { HeroStage } from "./HeroStage";
import { LiveRun } from "./LiveRun";

const EXAMPLES = [
  "My company is caughtleads.com. Should I worry about revsquad.ai?",
  "Should we buy from gong.io? What does it cost for 20 reps?",
  "Is linear.app a good investment?",
];

const STATS = [
  { value: "4", label: "analysts research each question in parallel" },
  { value: "2", label: "sides argued before anything is written" },
  { value: "6", label: "angles: investor, competitor, buyer, partner, job seeker, general" },
  { value: "~2 min", label: "from question to a cited draft" },
];

/** Position in the staggered entrance (see .hero-copy in globals.css). */
const order = (i: number) => ({ "--i": i }) as CSSProperties;

export function Hero() {
  return (
    <>
      <section className="hero-plate relative isolate overflow-hidden text-slate-950">
        <Container
          size="wide"
          className="relative z-10 grid min-h-[100svh] items-center gap-10 pt-24 pb-12 lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)] lg:gap-14 lg:pt-28"
        >
          <div className="hero-copy max-w-[35rem]">
            <p
              className="flex items-center gap-3 font-mono text-2xs tracking-label text-slate-700 uppercase"
              style={order(0)}
            >
              <span aria-hidden className="h-px w-8 bg-current" />
              Due diligence for private companies
            </p>
            <h1
              className="mt-5 font-display text-[3.1rem] leading-[0.98] tracking-tight text-balance sm:text-7xl xl:text-[5.4rem]"
              style={order(1)}
            >
              Know the company <em className="text-indigo-700">before you commit.</em>
            </h1>
            <p className="mt-5 max-w-md text-base leading-relaxed text-slate-700" style={order(2)}>
              A competitor, a vendor, an investment or an employer: most small companies have no analyst coverage.
              Tell Atlas who you are and what you need to decide. It researches the web, news and filings, argues both
              sides, and answers your question with every claim linked to its source.
            </p>
            <div style={order(3)}>
              <Form
                action="/research"
                className="mt-7 flex items-center gap-3 border-b border-current/30 pb-2 transition-colors focus-within:border-current"
              >
                <label htmlFor="hero-q" className="sr-only">
                  Company or question
                </label>
                <Icon name="search" className="h-4 w-4 shrink-0 text-slate-600" />
                <input
                  id="hero-q"
                  name="q"
                  required
                  minLength={3}
                  autoComplete="off"
                  placeholder="e.g. Should we buy from gong.io?"
                  className="w-full min-w-0 flex-1 bg-transparent py-2 text-base placeholder:text-slate-600 focus:outline-none"
                />
                <button
                  type="submit"
                  aria-label="Research"
                  className="inline-flex min-h-11 shrink-0 cursor-pointer items-center gap-2 rounded-lg bg-accent-400 px-5 text-sm font-medium text-ink-950 transition-colors hover:bg-accent-300"
                >
                  <span className="hidden sm:inline">Research</span>
                  <Icon name="arrowRight" />
                </button>
              </Form>
            </div>
            <ul className="mt-4 flex flex-col gap-1" aria-label="Example questions" style={order(4)}>
              {EXAMPLES.map((q) => (
                <li key={q}>
                  <Link
                    href={`/research?q=${encodeURIComponent(q)}`}
                    className="link-rule inline-block py-1 text-xs text-slate-700"
                  >
                    {q}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
          {/* The film, with the live sample run docked over its lower-left corner. */}
          <div className="hero-film-wrap relative lg:pl-10">
            <HeroStage className="aspect-[4/5] w-full shadow-[0_40px_140px_-40px_rgb(190_235_70/0.45)] sm:aspect-[16/11] lg:aspect-auto lg:h-[min(78svh,760px)]" />
            <div className="absolute bottom-8 -left-2 hidden w-[18.5rem] lg:block">
              <LiveRun />
            </div>
          </div>
        </Container>
      </section>

      <div className="border-b border-slate-200 bg-surface">
        <Container size="wide">
          <dl className="grid grid-cols-2 md:grid-cols-4">
            {STATS.map((s, i) => (
              <div key={s.label} className={i ? "border-slate-200 py-7 md:border-l md:pl-8" : "py-7"}>
                <dt className="sr-only">{s.label}</dt>
                <dd>
                  <span className="block font-mono text-3xl font-medium tracking-tight text-slate-950 tabular-nums">
                    {s.value}
                  </span>
                  <span className="mt-1 block text-xs text-slate-600 sm:text-sm">{s.label}</span>
                </dd>
              </div>
            ))}
          </dl>
        </Container>
      </div>
    </>
  );
}
