import type { Metadata } from "next";
import { AppHeader } from "@/components/research/AppHeader";
import { Workspace } from "@/components/research/Workspace";
import { Container } from "@/components/ui/Container";

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
    <div className="min-h-screen bg-slate-50 print:min-h-0 print:bg-surface">
      <AppHeader current="research" />
      <main>
        <Container size="wide" className="py-6 sm:py-8 print:p-0">
          <Workspace initialQuery={initialQuery} />
        </Container>
      </main>
    </div>
  );
}
