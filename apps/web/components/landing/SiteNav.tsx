import Link from "next/link";
import { btn, cx } from "@/components/ui/styles";
import { Icon } from "@/components/ui/Icon";
import { Wordmark } from "./Wordmark";

const LINKS = [
  { href: "#how-it-works", label: "How it works" },
  { href: "#features", label: "Features" },
  { href: "#inside", label: "Under the hood" },
  { href: "#sample-report", label: "Sample report" },
  { href: "#faq", label: "FAQ" },
];

/** Floating glass nav. Section links collapse away on phones; the CTA stays. */
export function SiteNav() {
  return (
    <header className="fixed inset-x-0 top-3 z-50 px-3 sm:top-4 sm:px-6">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 rounded-full border border-white/10 bg-ink-950/90 pr-2 pl-4 shadow-[0_10px_40px_-12px_rgb(0_0_0/0.6)] backdrop-blur-xl sm:pl-5">
        <Wordmark tone="dark" />
        <nav aria-label="Main" className="hidden lg:block">
          <ul className="flex items-center gap-0.5">
            {LINKS.map((l) => (
              <li key={l.href}>
                <a
                  href={l.href}
                  className="rounded-full px-3.5 py-2 text-sm font-medium text-slate-300 transition-colors hover:bg-white/5 hover:text-white"
                >
                  {l.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <Link href="/research" className={cx(btn.light, "py-2")}>
          <span className="hidden sm:inline">Research a company</span>
          <span className="sm:hidden">Start</span>
          <Icon name="arrowRight" />
        </Link>
      </div>
    </header>
  );
}
