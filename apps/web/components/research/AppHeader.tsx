import Link from "next/link";
import { Wordmark } from "@/components/landing/Wordmark";
import { Container } from "@/components/ui/Container";
import { Icon } from "@/components/ui/Icon";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { cx } from "@/components/ui/styles";

const NAV = [
  { id: "research", href: "/research", label: "Research" },
  { id: "learning", href: "/learning", label: "Learning" },
] as const;

/** Sticky ink header shared by the app pages (research workspace, learning loop). */
export function AppHeader({ current }: { current: (typeof NAV)[number]["id"] }) {
  return (
    <header className="screen-only sticky top-0 z-40 border-b border-white/[0.08] bg-ink-950/95 text-white backdrop-blur-md">
      <Container size="wide" className="flex h-16 items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3 sm:gap-4">
          <Wordmark tone="dark" />
          <span aria-hidden className="hidden h-5 w-px bg-white/15 sm:block" />
          <nav aria-label="App" className="flex items-center rounded-full border border-white/10 bg-white/[0.04] p-0.5">
            {NAV.map((item) => {
              const active = item.id === current;
              return (
                <Link
                  key={item.id}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cx(
                    "inline-flex min-h-8 items-center rounded-full px-2.5 text-[13px] font-medium transition-colors sm:px-3.5 pointer-coarse:min-h-10",
                    active ? "bg-white/[0.12] text-white" : "text-slate-400 hover:text-white",
                  )}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <ThemeToggle />
          <Link
            href="/"
            className="hidden items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium text-slate-300 transition-colors hover:bg-white/5 hover:text-white md:inline-flex"
          >
            <Icon name="arrowLeft" />
            Back to site
          </Link>
        </div>
      </Container>
    </header>
  );
}
