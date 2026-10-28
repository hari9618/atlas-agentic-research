import type { Metadata } from "next";
import Link from "next/link";
import { Wordmark } from "@/components/landing/Wordmark";
import { Workspace } from "@/components/research/Workspace";
import { Container } from "@/components/ui/Container";
import { Icon } from "@/components/ui/Icon";

export const metadata: Metadata = {
  title: "Research workspace",
  description: "Ask about any company. Atlas researches, debates both sides and drafts a cited brief for your review.",
};

export default async function ResearchPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  // Next 16: searchParams is a Promise. `?q=` lets the landing page hand off a question.
  const { q } = await searchParams;
  const initialQuery = (Array.isArray(q) ? q[0] : q)?.slice(0, 300) ?? "";

  return (
    <div className="min-h-screen bg-slate-50 print:min-h-0 print:bg-white">
      <header className="screen-only sticky top-0 z-40 border-b border-white/[0.08] bg-ink-950/95 text-white backdrop-blur-md">
        <Container size="wide" className="flex h-16 items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Wordmark tone="dark" />
            <span aria-hidden className="hidden h-5 w-px bg-white/15 sm:block" />
            <span className="hidden font-mono text-[11px] tracking-[0.18em] text-slate-400 uppercase sm:block">
              Research workspace
            </span>
          </div>
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium text-slate-300 transition-colors hover:bg-white/5 hover:text-white"
          >
            <Icon name="arrowLeft" />
            Back to site
          </Link>
        </Container>
      </header>
      <main>
        <Container size="wide" className="py-6 sm:py-8 print:p-0">
          <Workspace initialQuery={initialQuery} />
        </Container>
      </main>
    </div>
  );
}
