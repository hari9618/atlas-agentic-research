import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { btn } from "@/components/ui/styles";
import { Wordmark } from "./Wordmark";

const LINKS = [
  { href: "#how-it-works", label: "How it works" },
  { href: "#features", label: "Features" },
  { href: "#sample-report", label: "Sample report" },
  { href: "#faq", label: "FAQ" },
];

/** Sticky marketing nav. Section links collapse away on phones; the CTA stays. */
export function SiteNav() {
  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/90 backdrop-blur supports-[backdrop-filter]:bg-white/75">
      <Container className="flex h-16 items-center justify-between gap-4">
        <Wordmark />
        <nav aria-label="Main" className="hidden md:block">
          <ul className="flex items-center gap-1">
            {LINKS.map((l) => (
              <li key={l.href}>
                <a href={l.href} className="rounded-md px-3 py-2 text-sm font-medium text-slate-600 hover:text-slate-900">
                  {l.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <Link href="/research" className={btn.primary}>
          Research a company
        </Link>
      </Container>
    </header>
  );
}
