"use client";

import { useEffect, useId, useRef, useState } from "react";
import { signOutEverywhere } from "@/lib/auth";
import { Icon } from "@/components/ui/Icon";
import { Spinner } from "@/components/ui/Spinner";
import { btn, cx, tap } from "@/components/ui/styles";

/** "Sign out of all devices", behind a confirm step: it revokes every session of the
 *  account, this browser included, then lands on /login. */
export function SessionsCard() {
  const uid = useId();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (confirming) confirmRef.current?.focus();
  }, [confirming]);

  const cancel = () => {
    setConfirming(false);
    requestAnimationFrame(() => triggerRef.current?.focus());
  };

  async function confirm() {
    setBusy(true);
    setError(null);
    const r = await signOutEverywhere();
    // On success the page is already navigating to /login.
    if (!r.ok) {
      setBusy(false);
      setError(r.error.message);
    }
  }

  return (
    <div>
      {confirming ? (
        <div
          role="group"
          aria-labelledby={`${uid}-q`}
          className="animate-enter space-y-3 rounded-xl border border-amber-200 bg-amber-50/60 p-4"
          onKeyDown={(e) => e.key === "Escape" && !busy && cancel()}
        >
          <p id={`${uid}-q`} className="text-sm text-slate-800">
            <span className="font-semibold text-slate-950">Sign out everywhere, including this browser?</span>
            <span className="mt-0.5 block text-slate-600">
              Every device will need to sign in again. Runs already in progress keep going on the server.
            </span>
          </p>
          <div className="flex flex-wrap gap-2">
            <button ref={confirmRef} type="button" onClick={confirm} disabled={busy} className={cx(btn.primary, tap)}>
              {busy ? <Spinner /> : <Icon name="logOut" />}
              {busy ? "Signing out…" : "Sign out everywhere"}
            </button>
            <button type="button" onClick={cancel} disabled={busy} className={cx(btn.secondary, tap)}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button ref={triggerRef} type="button" onClick={() => setConfirming(true)} className={cx(btn.secondary, tap)}>
          <Icon name="logOut" />
          Sign out of all devices
        </button>
      )}
      <div aria-live="polite">
        {error && (
          <p role="alert" className="mt-3 flex gap-2 text-sm text-rose-700">
            <Icon name="alert" className="mt-0.5 h-4 w-4 shrink-0" />
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
