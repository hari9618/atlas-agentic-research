import { NavSession } from "@/components/auth/NavSession";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { Wordmark } from "./Wordmark";

const LINKS = [
  { href: "#how-it-works", label: "How it works" },
  { href: "#features", label: "Features" },
  { href: "#inside", label: "Under the hood" },
  { href: "#sample-report", label: "Sample report" },
  { href: "#faq", label: "FAQ" },
];

/** Hairline nav. Section links collapse away on small screens; the theme switch and CTA
 *  stay. The CTA is a small client island that knows whether you're signed in. */
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
                  className="py-1 text-sm text-slate-700 transition-colors hover:text-slate-950"
                >
                  {l.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <NavSession />
        </div>
      </div>
    </header>
  );
}
