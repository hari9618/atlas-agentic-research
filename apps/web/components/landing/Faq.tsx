import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { Icon } from "@/components/ui/Icon";
import { btn, cx } from "@/components/ui/styles";
import { Disclosure } from "@/components/ui/Disclosure";
import { SectionHeading } from "./SectionHeading";

const FAQS: { q: string; a: string }[] = [
  {
    q: "Where does the data come from?",
    a: "Atlas searches several sources for each question: SEC EDGAR filings, stock market data, recent company news and live web search. It also searches any documents you add in the workspace. Every source used is listed at the end of the report.",
  },
  {
    q: "How accurate is it, and how do citations work?",
    a: "Every claim in a report must point to a piece of retrieved evidence, and a guardrail checks how many claims are actually covered. If coverage is weak, the confidence score drops. Atlas is still an AI system and can misread a source, so click through the citations for any number you plan to rely on.",
  },
  {
    q: "Can it research private companies?",
    a: "Yes, from what is publicly available: news, the web and any documents you provide. Private companies don't file with the SEC or have stock data, so expect a lower confidence score and a longer \"what we're not sure about\" list.",
  },
  {
    q: "What does the confidence score mean?",
    a: "It's a 0 to 100 measure of how well the evidence supports the report's conclusions, adjusted down when claims aren't backed by citations. It is not the probability that an investment or partnership will work out.",
  },
  {
    q: "What happens to my documents?",
    a: "Documents you upload are split into passages and indexed so the agents can search and cite them. They stay in your Atlas knowledge base, on the server running Atlas, until you remove them from \"Your documents\". Only upload material you're allowed to share with that server.",
  },
  {
    q: "Is this investment advice?",
    a: "No. Atlas is research support: it gathers evidence, lays out both sides and tells you what it doesn't know. Decisions are yours, and for significant ones you should talk to a qualified adviser.",
  },
];

export function Faq() {
  return (
    <section id="faq" aria-labelledby="faq-title" className="scroll-mt-24 border-t border-slate-200/70 bg-slate-50 py-24 sm:py-28">
      <Container className="grid gap-12 lg:grid-cols-[0.8fr_1.2fr] lg:gap-16">
        <div className="reveal lg:sticky lg:top-28 lg:self-start">
          <SectionHeading id="faq-title" kicker="FAQ" title="Straight" accent="answers." />
          <p className="mt-5 text-base leading-relaxed text-slate-600">
            How Atlas sources, cites and scores its research, and what it is not.
          </p>
          <Link href="/research" className={cx(btn.secondary, "mt-7")}>
            Try it on a company
            <Icon name="arrowRight" />
          </Link>
        </div>
        <div className="reveal divide-y divide-slate-200 rounded-3xl border border-slate-200/80 bg-white px-5 shadow-[0_1px_2px_rgb(15_23_42/0.04)] sm:px-7">
          {FAQS.map((f, i) => (
            <Disclosure
              key={f.q}
              name="faq"
              defaultOpen={i === 0}
              summaryClassName="py-5"
              summary={<h3 className="text-base font-semibold text-slate-900">{f.q}</h3>}
            >
              <p className="pb-5 text-sm leading-relaxed text-slate-600">{f.a}</p>
            </Disclosure>
          ))}
        </div>
      </Container>
    </section>
  );
}
