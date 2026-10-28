import Form from "next/form";
import { Icon } from "@/components/ui/Icon";

const TRUST = ["Every claim cited", "Both sides argued", "You approve the final report"];

/** Closing call to action. The form hands the question to /research?q=… (prefilled,
 *  not auto-run) and works without JavaScript. */
export function FinalCta() {
  return (
    <section aria-labelledby="cta-title" className="px-4 pb-20 sm:px-6 sm:pb-24 lg:px-8">
      <div className="mx-auto max-w-6xl rounded-2xl bg-indigo-700 px-6 py-12 text-white sm:px-10 sm:py-16">
        <div className="mx-auto max-w-2xl text-center">
          <h2 id="cta-title" className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            Know the company before you commit.
          </h2>
          <p className="mt-4 text-lg text-indigo-100">
            Ask your first question. You&apos;ll have a cited draft to review in minutes.
          </p>
          <Form action="/research" className="mx-auto mt-8 flex max-w-xl flex-col gap-2 sm:flex-row">
            <label htmlFor="cta-q" className="sr-only">
              Company or question
            </label>
            <input
              id="cta-q"
              name="q"
              required
              minLength={3}
              placeholder="e.g. How does Stripe compare to Adyen?"
              className="w-full min-w-0 flex-1 rounded-lg border border-indigo-400 bg-white px-4 py-3 text-base text-slate-900 placeholder:text-slate-500 focus:outline-none focus-visible:ring-4 focus-visible:ring-indigo-300"
            />
            <button
              type="submit"
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-white px-5 py-3 text-base font-semibold text-indigo-700 hover:bg-indigo-50 focus-visible:outline-white"
            >
              Research a company
              <Icon name="arrowRight" />
            </button>
          </Form>
          <ul className="mt-8 flex flex-col items-center justify-center gap-3 text-sm text-indigo-100 sm:flex-row sm:gap-6">
            {TRUST.map((t) => (
              <li key={t} className="flex items-center gap-2">
                <Icon name="check" className="h-4 w-4 text-emerald-300" strokeWidth={3} />
                {t}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
