import type { Metadata } from "next";
import { AccountView } from "@/components/account/AccountView";
import { AppHeader } from "@/components/research/AppHeader";
import { Container } from "@/components/ui/Container";

export const metadata: Metadata = {
  title: "Your account",
  description: "Your Atlas profile, plan limits, password and sessions.",
  robots: { index: false },
};

// Gated by proxy.ts; the account itself is loaded client-side with the bearer token.
export default function AccountPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <AppHeader />
      <main>
        <Container size="narrow" className="py-8 sm:py-12">
          <header className="mb-6 max-w-2xl">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Your account</h1>
            <p className="mt-1 text-sm leading-relaxed text-slate-600">
              Your profile and limits, your password, and where you&apos;re signed in.
            </p>
          </header>
          <AccountView />
        </Container>
      </main>
    </div>
  );
}
