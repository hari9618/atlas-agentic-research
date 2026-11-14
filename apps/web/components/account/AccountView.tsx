"use client";

import Link from "next/link";
import { isGuest } from "@/lib/auth-common";
import { useSession } from "@/lib/use-session";
import { Icon } from "@/components/ui/Icon";
import { btn, cx, surface, tap } from "@/components/ui/styles";
import { AccountSection } from "./AccountSection";
import { DangerZone } from "./DangerZone";
import { PasswordForm } from "./PasswordForm";
import { ProfileCard } from "./ProfileCard";
import { SessionsCard } from "./SessionsCard";

/** Everything on /account, once the session is known. Guests get the same page minus
 *  the password (they have none) and with a nudge to create a real account. */
export function AccountView() {
  const { status, user } = useSession();

  if (status !== "authenticated" || !user) return <AccountSkeleton />;
  const guest = isGuest(user);

  return (
    <div className="animate-enter space-y-6">
      <ProfileCard user={user} />

      <AccountSection
        id="password-title"
        title="Password"
        text={guest ? undefined : "Use 8 to 128 characters. A long passphrase beats a short clever one."}
      >
        {guest ? (
          <div className="flex flex-col gap-3 rounded-xl border border-dashed border-slate-300 p-4 sm:flex-row sm:items-center">
            <p className="min-w-0 flex-1 text-sm leading-relaxed text-slate-600">
              Demo sessions don&apos;t have a password. Create an account to set one, keep your reports and get a higher
              hourly limit.
            </p>
            <Link href="/login?mode=signup&next=%2Faccount" className={cx(btn.primary, "shrink-0", tap)}>
              Create an account
              <Icon name="arrowRight" />
            </Link>
          </div>
        ) : (
          <PasswordForm />
        )}
      </AccountSection>

      <AccountSection
        id="sessions-title"
        title="Signed-in devices"
        text="Lost a laptop or signed in on a shared computer? End every session at once."
      >
        <SessionsCard />
      </AccountSection>

      <AccountSection
        id="danger-title"
        tone="danger"
        title={guest ? "End this demo" : "Delete account"}
        text={guest ? "Remove this demo session and what was made in it." : "Remove your account and everything tied to it."}
      >
        <DangerZone guest={guest} />
      </AccountSection>
    </div>
  );
}

function AccountSkeleton() {
  const bar = "rounded-full bg-slate-200/80 animate-pulse-soft";
  return (
    <div aria-hidden className="space-y-6">
      {[0, 1, 2].map((i) => (
        <div key={i} className={cx(surface, "space-y-3 p-6")}>
          <div className={cx(bar, "h-4 w-40")} />
          <div className={cx(bar, "h-3 w-full")} />
          <div className={cx(bar, "h-3 w-2/3")} />
        </div>
      ))}
    </div>
  );
}
