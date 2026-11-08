import Link from "next/link";
import { Icon } from "@/components/ui/Icon";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { Wordmark } from "./Wordmark";

const LINKS = [
  { href: "#how-it-works", label: "How it works" },
  { href: "#features", label: "Features" },
  { href: "#inside", label: "Under the hood" },
  { href: "#sample-report", label: "Sample report" },
  { href: "#faq", label: "FAQ" },
];

/** Hairline nav. Section links collapse away on small screens; the theme switch and CTA stay. */
export function SiteNav() {
  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b border-current/10 bg-surface/90 text-slate-950 backdrop-blur-lg">
      <div className="mx-auto flex h-16 max-w-[90rem] items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <Wordmark />
        <nav aria-label="Main" className="hidden lg:block">
          <ul className="flex items-center gap-7">
            {LINKS.map((l) => (
              <li key={l.href}>
                <a
                  href={l.href}
                  className="link-rule py-1 font-mono text-[11px] tracking-[0.16em] text-slate-800 uppercase"
                >
                  {l.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <Link
            href="/research"
            className="inline-flex min-h-10 items-center gap-2 rounded-full bg-accent-400 px-4 text-sm font-semibold text-ink-950 transition-colors hover:bg-accent-300"
          >
            <span className="hidden sm:inline">Research a company</span>
            <span className="sm:hidden">Start</span>
            <Icon name="arrowRight" />
          </Link>
        </div>
      </div>
    </header>
  );
}
