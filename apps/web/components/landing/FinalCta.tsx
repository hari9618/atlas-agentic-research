import Form from "next/form";
import { Icon } from "@/components/ui/Icon";

const TRUST = ["Every claim cited", "Both sides argued", "You approve the final report"];

/** Closing call to action. The form hands the question to /research?q=… (prefilled,
 *  not auto-run) and works without JavaScript. */
export function FinalCta() {
  return (
    <section aria-labelledby="cta-title" className="bg-slate-50 px-3 pb-6 sm:px-6">
      <div className="relative isolate mx-auto max-w-6xl overflow-hidden rounded-[2rem] bg-ink-950 px-6 py-16 text-white sm:px-10 sm:py-24">
        <div aria-hidden className="absolute inset-0 -z-10 bg-grid" />
        <div
          aria-hidden
          className="absolute -bottom-56 left-1/2 -z-10 h-[34rem] w-[60rem] -translate-x-1/2 bg-[radial-gradient(closest-side,rgb(79_70_229/0.45),transparent)]"
        />
        <div className="reveal mx-auto max-w-2xl text-center">
          <h2 id="cta-title" className="font-display text-4xl leading-[1.02] tracking-tight text-balance sm:text-6xl">
            Know the company <em className="text-shine pr-1">before you commit.</em>
          </h2>
          <p className="mt-5 text-lg text-slate-400">
            Ask your first question. You&apos;ll have a cited draft to review in minutes.
          </p>
          <Form
            action="/research"
            className="mx-auto mt-9 flex max-w-xl items-center gap-2 rounded-full border border-white/12 bg-white/[0.06] p-1.5 pl-5 backdrop-blur-md transition-colors focus-within:border-indigo-400/60"
          >
            <label htmlFor="cta-q" className="sr-only">
              Company or question
            </label>
            <Icon name="search" className="h-4 w-4 shrink-0 text-slate-500" />
            <input
              id="cta-q"
              name="q"
              required
              minLength={3}
              autoComplete="off"
              placeholder="e.g. How does Stripe compare to Adyen?"
              className="w-full min-w-0 flex-1 bg-transparent py-2 text-base text-white placeholder:text-slate-500 focus:outline-none"
            />
            <button
              type="submit"
              className="inline-flex shrink-0 items-center gap-2 rounded-full bg-white px-4 py-2.5 text-sm font-semibold text-ink-950 transition-colors hover:bg-indigo-50 sm:px-5"
            >
              <span className="hidden sm:inline">Research</span>
              <Icon name="arrowRight" />
            </button>
          </Form>
          <ul className="mt-8 flex flex-col items-center justify-center gap-3 text-sm text-slate-400 sm:flex-row sm:gap-6">
            {TRUST.map((t) => (
              <li key={t} className="flex items-center gap-2">
                <Icon name="check" className="h-4 w-4 text-emerald-400" strokeWidth={3} />
                {t}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
