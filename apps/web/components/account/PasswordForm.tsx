"use client";

import { type FormEvent, useId, useRef, useState } from "react";
import { type AuthError, changePassword } from "@/lib/auth";
import { Field, inputClass } from "@/components/auth/Field";
import { Icon } from "@/components/ui/Icon";
import { Spinner } from "@/components/ui/Spinner";
import { btn, cx, tap } from "@/components/ui/styles";

type Name = "current_password" | "new_password" | "confirm";
type Errors = Partial<Record<Name, string>>;

const MIN = 8;
const MAX = 128;

function validate(v: Record<Name, string>): Errors {
  const e: Errors = {};
  if (!v.current_password) e.current_password = "Enter your current password.";
  if (!v.new_password) e.new_password = "Choose a new password.";
  else if (v.new_password.length < MIN) e.new_password = `Use at least ${MIN} characters.`;
  else if (v.new_password.length > MAX) e.new_password = `Use at most ${MAX} characters.`;
  else if (v.new_password === v.current_password) e.new_password = "Pick something different from your current password.";
  if (!v.confirm) e.confirm = "Type the new password again.";
  else if (v.confirm !== v.new_password) e.confirm = "The passwords don't match.";
  return e;
}

/** Change password. The server signs out every other device and hands this browser a
 *  fresh session (the BFF rotates the cookie), so the user stays signed in here. */
export function PasswordForm() {
  const uid = useId();
  const [values, setValues] = useState<Record<Name, string>>({ current_password: "", new_password: "", confirm: "" });
  const [show, setShow] = useState(false);
  const [touched, setTouched] = useState<Partial<Record<Name, boolean>>>({});
  const [submitted, setSubmitted] = useState(false);
  const [server, setServer] = useState<Errors>({});
  const [error, setError] = useState<AuthError | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const currentRef = useRef<HTMLInputElement>(null);
  const newRef = useRef<HTMLInputElement>(null);
  const confirmRef = useRef<HTMLInputElement>(null);

  const local = validate(values);
  const shown = (n: Name) => server[n] ?? (touched[n] || submitted ? local[n] : undefined);
  const id = (n: Name) => `${uid}-${n}`;
  const focus = (n: Name) =>
    (n === "current_password" ? currentRef : n === "new_password" ? newRef : confirmRef).current?.focus();

  const set = (n: Name) => (v: string) => {
    setValues((s) => ({ ...s, [n]: v }));
    if (server[n]) setServer((s) => ({ ...s, [n]: undefined }));
    setError(null);
    setDone(false);
  };

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setSubmitted(true);
    const order: Name[] = ["current_password", "new_password", "confirm"];
    const bad = order.find((n) => local[n]);
    if (bad) return focus(bad);

    setBusy(true);
    setError(null);
    setServer({});
    const r = await changePassword(values.current_password, values.new_password);
    setBusy(false);
    if (r.ok) {
      setValues({ current_password: "", new_password: "", confirm: "" });
      setSubmitted(false);
      setTouched({});
      setDone(true);
      return;
    }
    const fields: Errors = {
      current_password: r.error.fields?.current_password,
      new_password: r.error.fields?.new_password,
    };
    setServer(fields);
    const firstField = order.find((n) => fields[n]);
    if (firstField) focus(firstField);
    else setError(r.error);
  }

  const input = (n: Name, autoComplete: string, ref: React.RefObject<HTMLInputElement | null>) => (
    <input
      ref={ref}
      id={id(n)}
      name={n}
      type={show ? "text" : "password"}
      autoComplete={autoComplete}
      value={values[n]}
      maxLength={MAX + 1}
      onChange={(e) => set(n)(e.target.value)}
      onBlur={() => setTouched((t) => ({ ...t, [n]: true }))}
      aria-invalid={!!shown(n) || undefined}
      aria-describedby={shown(n) || n === "new_password" ? `${id(n)}-msg` : undefined}
      aria-required
      disabled={busy}
      className={inputClass}
    />
  );

  return (
    <form noValidate onSubmit={onSubmit} className="space-y-4">
      {/* A hidden username lets password managers file the new password correctly. */}
      <input type="text" name="username" autoComplete="username" hidden readOnly />

      <Field
        id={id("current_password")}
        label="Current password"
        error={shown("current_password")}
        trailing={
          <button
            type="button"
            onClick={() => setShow((v) => !v)}
            aria-pressed={show}
            className="rounded-md px-1 text-xs font-medium text-indigo-700 hover:underline pointer-coarse:min-h-8"
          >
            {show ? "Hide" : "Show"}
            <span className="sr-only"> passwords</span>
          </button>
        }
      >
        {input("current_password", "current-password", currentRef)}
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field id={id("new_password")} label="New password" error={shown("new_password")} hint={`${MIN} to ${MAX} characters.`}>
          {input("new_password", "new-password", newRef)}
        </Field>
        <Field id={id("confirm")} label="Confirm new password" error={shown("confirm")}>
          {input("confirm", "new-password", confirmRef)}
        </Field>
      </div>

      <div aria-live="polite" aria-atomic="true">
        {error && (
          <p role="alert" className="flex animate-enter gap-2 rounded-xl border border-rose-200 bg-rose-50/70 p-3 text-sm text-rose-900">
            <Icon name="alert" className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
            {error.message}
          </p>
        )}
        {done && (
          <p className="flex animate-enter gap-2 rounded-xl border border-emerald-200 bg-emerald-50/70 p-3 text-sm text-emerald-900">
            <Icon name="check" className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" strokeWidth={3} />
            Password changed. Every other device has been signed out; this one stays signed in.
          </p>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={busy} className={cx(btn.primary, tap)}>
          {busy && <Spinner />}
          {busy ? "Updating…" : "Update password"}
        </button>
        <p className="text-xs text-slate-500">Changing it signs you out everywhere else.</p>
      </div>
    </form>
  );
}
