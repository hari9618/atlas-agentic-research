"use client";

import { type FormEvent, useId, useState } from "react";
import { deleteAccount } from "@/lib/auth";
import { Field, inputClass } from "@/components/auth/Field";
import { Icon } from "@/components/ui/Icon";
import { Spinner } from "@/components/ui/Spinner";
import { cx, tap } from "@/components/ui/styles";

const PHRASE = "DELETE";

/** Delete the account. Two deliberate inputs: the typed phrase (so it can't happen by a
 *  stray click) and, for password accounts, the password (so an unattended signed-in
 *  browser can't do it). */
export function DangerZone({ guest }: { guest: boolean }) {
  const uid = useId();
  const [phrase, setPhrase] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; field?: "password" } | null>(null);

  const ready = phrase === PHRASE && (guest || password.length > 0);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!ready || busy) return;
    setBusy(true);
    setError(null);
    const r = await deleteAccount(guest ? undefined : password);
    // On success the page is already navigating home.
    if (!r.ok) {
      setBusy(false);
      setError({
        message: r.error.message,
        field: r.error.code === "invalid_credentials" ? "password" : undefined,
      });
    }
  }

  return (
    <form noValidate onSubmit={onSubmit} className="space-y-4">
      <ul className="space-y-2 text-sm text-slate-700">
        {(guest
          ? ["Ends this demo session for good.", "Removes the runs and reports made in it."]
          : ["Permanently removes your account and sign-in.", "Signs out every device.", "This can't be undone."]
        ).map((t) => (
          <li key={t} className="flex gap-2">
            <Icon name="x" className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
            {t}
          </li>
        ))}
      </ul>

      <div className={cx("grid gap-4", !guest && "sm:grid-cols-2")}>
        <Field id={`${uid}-phrase`} label={`Type ${PHRASE} to confirm`}>
          <input
            id={`${uid}-phrase`}
            value={phrase}
            onChange={(e) => {
              setPhrase(e.target.value);
              setError(null);
            }}
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            disabled={busy}
            className={cx(inputClass, "font-mono tracking-wider")}
            placeholder={PHRASE}
          />
        </Field>
        {!guest && (
          <Field
            id={`${uid}-password`}
            label="Your password"
            error={error?.field === "password" ? error.message : undefined}
          >
            <input
              id={`${uid}-password`}
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                setError(null);
              }}
              aria-invalid={error?.field === "password" || undefined}
              aria-describedby={error?.field === "password" ? `${uid}-password-msg` : undefined}
              disabled={busy}
              className={inputClass}
            />
          </Field>
        )}
      </div>

      <div aria-live="polite">
        {error && !error.field && (
          <p role="alert" className="flex gap-2 text-sm text-rose-700">
            <Icon name="alert" className="mt-0.5 h-4 w-4 shrink-0" />
            {error.message}
          </p>
        )}
      </div>

      <button
        type="submit"
        disabled={!ready || busy}
        className={cx(
          "inline-flex items-center justify-center gap-2 rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-50",
          tap,
        )}
      >
        {busy ? <Spinner /> : <Icon name="trash" />}
        {busy ? "Deleting…" : guest ? "End and delete this session" : "Delete my account"}
      </button>
    </form>
  );
}
