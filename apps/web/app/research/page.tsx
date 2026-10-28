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
      <header className="screen-only sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur">
        <Container className="flex h-16 items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Wordmark />
            <span aria-hidden className="hidden h-5 w-px bg-slate-200 sm:block" />
            <span className="hidden text-sm font-medium text-slate-600 sm:block">Research workspace</span>
          </div>
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 text-sm font-medium text-slate-600 hover:text-slate-900"
          >
            <Icon name="arrowLeft" />
            Back to site
          </Link>
        </Container>
      </header>
      <main>
        <Container className="py-8 sm:py-10 print:p-0">
          <Workspace initialQuery={initialQuery} />
        </Container>
      </main>
    </div>
  );
}
