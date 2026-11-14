import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { Wordmark } from "./Wordmark";

const COLUMNS: { title: string; links: { href: string; label: string }[] }[] = [
  {
    title: "Product",
    links: [
      { href: "/research", label: "Research a company" },
      { href: "/#how-it-works", label: "How it works" },
      { href: "/#features", label: "Features" },
      { href: "/#sample-report", label: "Sample report" },
    ],
  },
  {
    title: "Trust",
    links: [
      { href: "/#faq", label: "Where the data comes from" },
      { href: "/#inside", label: "Under the hood" },
      { href: "/#faq", label: "Your documents" },
      { href: "/#compare", label: "Atlas vs alternatives" },
    ],
  },
];

export function SiteFooter() {
  return (
    <footer className="bg-slate-50 pt-6">
      <div className="bg-ink-950 text-slate-400">
        <Container className="grid gap-10 py-14 md:grid-cols-[1.4fr_repeat(2,1fr)]">
          <div className="max-w-xs">
            <Wordmark tone="dark" />
            <p className="mt-4 text-sm leading-relaxed">
              AI due diligence on private companies, with every claim cited. Research support, not investment advice.
            </p>
          </div>
          {COLUMNS.map((col) => (
            <nav key={col.title} aria-label={col.title}>
              <p className="font-mono text-2xs tracking-label text-slate-400 uppercase">{col.title}</p>
              <ul className="mt-4 space-y-2">
                {col.links.map((l) => (
                  <li key={l.label}>
                    <Link href={l.href} className="text-sm text-slate-300 transition-colors hover:text-white">
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </Container>
        <div className="border-t border-white/[0.07]">
          <Container className="flex flex-col gap-2 py-6 text-xs text-slate-400 sm:flex-row sm:justify-between">
            <p>&copy; {new Date().getFullYear()} Atlas. Research support only; not financial advice.</p>
            <p>Built with LangGraph, hybrid retrieval and cited evidence.</p>
          </Container>
        </div>
      </div>
    </footer>
  );
}
