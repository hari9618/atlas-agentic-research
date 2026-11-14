import type { Metadata } from "next";
import Link from "next/link";
import { AuthPanel, type AuthMode } from "@/components/auth/AuthPanel";
import { LoginAside } from "@/components/auth/LoginAside";
import { Wordmark } from "@/components/landing/Wordmark";
import { Icon } from "@/components/ui/Icon";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { safeNextPath } from "@/lib/auth-common";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to Atlas, create an account, or try the demo without one.",
  robots: { index: false },
};

const first = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  // Next 16: searchParams is a Promise. `next` is where to return after signing in
  // (validated as a same-site path); `mode=signup` opens on "Create account".
  const params = await searchParams;
  const next = safeNextPath(first(params.next));
  const mode: AuthMode = first(params.mode) === "signup" ? "signup" : "signin";

  return (
    <div className="min-h-dvh bg-surface lg:grid lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <LoginAside />

      <div className="flex min-h-dvh flex-col">
        <header className="flex h-16 items-center justify-between gap-3 px-4 sm:px-6 lg:justify-end lg:px-10">
          <div className="lg:hidden">
            <Wordmark />
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/"
              className="hidden items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-950 sm:inline-flex"
            >
              <Icon name="arrowLeft" />
              Back to site
            </Link>
            <ThemeToggle />
          </div>
        </header>

        <main className="flex flex-1 items-center justify-center px-4 pt-4 pb-12 sm:px-6">
          <div className="w-full max-w-[25rem]">
            <AuthPanel key={mode} next={next} initialMode={mode} />
            <p className="mt-6 flex items-start gap-2 border-t border-slate-200/80 pt-5 text-xs leading-relaxed text-slate-500">
              <Icon name="shield" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" />
              Your session is kept in a secure, http-only cookie on this site. Atlas never stores your password in the
              browser.
            </p>
          </div>
        </main>
      </div>
    </div>
  );
}
