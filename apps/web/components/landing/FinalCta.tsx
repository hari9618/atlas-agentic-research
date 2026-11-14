import Form from "next/form";
import { Icon } from "@/components/ui/Icon";

const TRUST = ["Every claim cited", "Both sides argued", "You approve the final report"];

/** Closing call to action. The form hands the question to /research?q=… (prefilled,
 *  not auto-run) and works without JavaScript. */
export function FinalCta() {
  return (
    <section aria-labelledby="cta-title" className="bg-slate-50 px-3 pb-6 sm:px-6">
      <div className="mx-auto max-w-6xl rounded-xl bg-ink-950 px-6 py-16 text-white sm:px-10 sm:py-20">
        <div className="mx-auto max-w-2xl text-center">
          <h2 id="cta-title" className="text-3xl leading-tight font-semibold tracking-tight text-balance sm:text-4xl">
            Ask about a company you need to decide on.
          </h2>
          <p className="mt-5 text-lg text-slate-400">
            Say who you are and what you need to know. You&apos;ll have a cited draft to review in about two minutes.
          </p>
          <Form
            action="/research"
            className="mx-auto mt-9 flex max-w-xl items-center gap-2 rounded-lg border border-white/15 bg-white/[0.06] p-2 pl-4 transition-colors focus-within:border-indigo-400/60"
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
              placeholder="e.g. Is linear.app a good investment?"
              className="w-full min-w-0 flex-1 bg-transparent py-2 text-base text-white placeholder:text-slate-400 focus:outline-none"
            />
            <button
              type="submit"
              className="inline-flex shrink-0 items-center gap-2 rounded-md bg-accent-400 px-4 py-2 text-sm font-medium text-ink-950 transition-colors hover:bg-accent-300 sm:px-5"
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
