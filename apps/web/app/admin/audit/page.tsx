import type { Metadata } from "next";
import { AuditLog } from "@/components/admin/AuditLog";
import { AppHeader } from "@/components/research/AppHeader";
import { Container } from "@/components/ui/Container";

export const metadata: Metadata = {
  title: "Audit log",
  description: "Recent security and admin events.",
  robots: { index: false },
};

// Gated by proxy.ts (signed in) and by the API (admins only).
export default function AuditPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <AppHeader />
      <main>
        <Container size="wide" className="py-8 sm:py-12">
          <header className="mb-6 max-w-3xl">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-950">Audit log</h1>
            <p className="mt-1 text-sm leading-relaxed text-slate-600">
              Sign-ins, password changes, revocations and admin actions, newest first.
            </p>
          </header>
          <AuditLog />
        </Container>
      </main>
    </div>
  );
}
