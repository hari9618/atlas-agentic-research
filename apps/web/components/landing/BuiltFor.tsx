import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { Icon } from "@/components/ui/Icon";
import { SectionHeading } from "./SectionHeading";

// The personas the backend recognises (plus "general"). Each row says what changes in
// the brief for that reader, with a question that triggers it.
const PERSONAS: { who: string; gets: string; ask: string }[] = [
  {
    who: "Competitor",
    gets: "A threat level, a side-by-side table against your company, and where they are weak.",
    ask: "My company is caughtleads.com. Should I worry about revsquad.ai?",
  },
  {
    who: "Buyer",
    gets: "Plans and published prices, what customers praise and complain about, and red flags.",
    ask: "Should we buy from gong.io? What does it cost for 20 reps?",
  },
  {
    who: "Investor",
    gets: "Traction, funding and team signals, both sides of the case, and what is still unknown.",
    ask: "Is linear.app a good investment?",
  },
  {
    who: "Partner",
    gets: "Who they sell to, how they make money, and whether the fit holds up.",
    ask: "Would partnering with resend.com make sense for our email product?",
  },
  {
    who: "Job seeker",
    gets: "Funding, team growth, recent news and what employees say.",
    ask: "I have an offer from posthog.com. Is it a stable place to join?",
  },
];

export function BuiltFor() {
  return (
    <section id="built-for" aria-labelledby="built-for-title" className="scroll-mt-24 bg-surface py-20 sm:py-24">
      <Container>
        <SectionHeading
          id="built-for-title"
          kicker="Who it's for"
          title="The brief changes with who is asking."
          intro="Say who you are in the question. Atlas answers your question first; everything after it is the evidence."
        />
        <div className="mt-10 overflow-hidden rounded-xl border border-slate-200/80">
          <table className="w-full text-left">
            <caption className="sr-only">What each kind of reader gets, with an example question</caption>
            <thead className="hidden border-b border-slate-200/80 bg-slate-50 md:table-header-group">
              <tr className="font-mono text-2xs tracking-label text-slate-500 uppercase">
                <th scope="col" className="px-5 py-3 font-medium">
                  If you are a
                </th>
                <th scope="col" className="px-5 py-3 font-medium">
                  You get
                </th>
                <th scope="col" className="px-5 py-3 font-medium">
                  Try asking
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200/80">
              {PERSONAS.map((p) => (
                <tr key={p.who} className="grid gap-1 px-5 py-4 md:table-row md:p-0">
                  <th scope="row" className="text-sm font-semibold text-slate-950 md:w-36 md:px-5 md:py-4 md:align-top">
                    {p.who}
                  </th>
                  <td className="text-sm leading-relaxed text-slate-600 md:px-5 md:py-4 md:align-top">{p.gets}</td>
                  <td className="pt-1 md:w-[26rem] md:px-5 md:py-4 md:align-top">
                    <Link
                      href={`/research?q=${encodeURIComponent(p.ask)}`}
                      className="inline-flex items-start gap-2 text-sm text-indigo-700 hover:underline"
                    >
                      <span>{p.ask}</span>
                      <Icon name="arrowRight" className="mt-1 h-3.5 w-3.5 shrink-0" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Container>
    </section>
  );
}
