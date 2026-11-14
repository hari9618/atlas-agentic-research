"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, type KeyboardEvent, useId, useRef, useState } from "react";
import { type AuthError, continueAsGuest, signIn, signOut, signUp } from "@/lib/auth";
import { isGuest } from "@/lib/auth-common";
import { useSession } from "@/lib/use-session";
import { Icon } from "@/components/ui/Icon";
import { Spinner } from "@/components/ui/Spinner";
import { btn, cx, tap } from "@/components/ui/styles";
import { Field, inputClass } from "./Field";

export type AuthMode = "signin" | "signup";
type FieldName = "email" | "password" | "name";
type Errors = Partial<Record<FieldName, string>>;

const MIN_PASSWORD = 8;
const MAX_PASSWORD = 128;
const MAX_NAME = 80;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const COPY: Record<AuthMode, { title: string; sub: string; submit: string; busy: string }> = {
  signin: {
    title: "Welcome back",
    sub: "Sign in to run research and review your briefs.",
    submit: "Sign in",
    busy: "Signing in…",
  },
  signup: {
    title: "Create your account",
    sub: "Keep your reports and get a higher hourly research limit.",
    submit: "Create account",
    busy: "Creating your account…",
  },
};

function validate(mode: AuthMode, v: { email: string; password: string; name: string }): Errors {
  const e: Errors = {};
  const email = v.email.trim();
  if (!email) e.email = "Enter your email address.";
  else if (!EMAIL_RE.test(email)) e.email = "That doesn't look like an email address.";
  if (!v.password) e.password = mode === "signup" ? "Choose a password." : "Enter your password.";
  else if (mode === "signup" && v.password.length < MIN_PASSWORD) e.password = `Use at least ${MIN_PASSWORD} characters.`;
  else if (v.password.length > MAX_PASSWORD) e.password = `Use at most ${MAX_PASSWORD} characters.`;
  if (mode === "signup" && v.name.trim().length > MAX_NAME) e.name = `Keep it under ${MAX_NAME} characters.`;
  return e;
}

/** Sign in / create account / one-click demo. Validation runs on blur and submit; the
 *  backend's own messages are shown as-is (field-level where it names a field). */
export function AuthPanel({ next, initialMode }: { next: string; initialMode: AuthMode }) {
  const router = useRouter();
  const uid = useId();
  const { status, user } = useSession();

  const [mode, setMode] = useState<AuthMode>(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [capsLock, setCapsLock] = useState(false);
  const [touched, setTouched] = useState<Partial<Record<FieldName, boolean>>>({});
  const [submitted, setSubmitted] = useState(false);
  const [serverFields, setServerFields] = useState<Errors>({});
  const [error, setError] = useState<AuthError | null>(null);
  const [busy, setBusy] = useState<null | "form" | "guest">(null);
  const [slow, setSlow] = useState(false);

  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  const signinTabRef = useRef<HTMLButtonElement>(null);
  const signupTabRef = useRef<HTMLButtonElement>(null);
  const focusField = (f: FieldName) =>
    (f === "email" ? emailRef : f === "password" ? passwordRef : nameRef).current?.focus();

  const local = validate(mode, { email, password, name });
  const shown = (f: FieldName) => serverFields[f] ?? (touched[f] || submitted ? local[f] : undefined);
  const copy = COPY[mode];
  const ids = { email: `${uid}-email`, password: `${uid}-password`, name: `${uid}-name` };
  const describedBy = (f: FieldName, hasHint = false) => (shown(f) || hasHint ? `${ids[f]}-msg` : undefined);

  function switchMode(m: AuthMode) {
    if (m === mode || busy) return;
    setMode(m);
    setError(null);
    setServerFields({});
    setSubmitted(false);
    setTouched({});
  }

  function onTabKey(e: KeyboardEvent<HTMLButtonElement>) {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight" && e.key !== "Home" && e.key !== "End") return;
    e.preventDefault();
    const target: AuthMode =
      e.key === "Home" ? "signin" : e.key === "End" ? "signup" : mode === "signin" ? "signup" : "signin";
    switchMode(target);
    (target === "signin" ? signinTabRef : signupTabRef).current?.focus();
  }

  const edit = (f: FieldName, set: (v: string) => void) => (v: string) => {
    set(v);
    if (serverFields[f]) setServerFields((s) => ({ ...s, [f]: undefined }));
    if (error) setError(null);
  };

  function done() {
    // Keep the busy state: the page is navigating away.
    router.replace(next);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setSubmitted(true);
    const order: FieldName[] = mode === "signup" ? ["name", "email", "password"] : ["email", "password"];
    const firstBad = order.find((f) => local[f]);
    if (firstBad) {
      focusField(firstBad);
      return;
    }
    setBusy("form");
    setError(null);
    setServerFields({});
    setSlow(false);
    const onSlow = () => setSlow(true);
    const r =
      mode === "signin"
        ? await signIn(email.trim(), password, onSlow)
        : await signUp(email.trim(), password, name.trim() || undefined, onSlow);
    if (r.ok) return done();
    setBusy(null);
    setSlow(false);
    setError(r.error);
    setServerFields(r.error.fields ?? {});
    const bad = order.find((f) => r.error.fields?.[f]);
    if (bad) focusField(bad);
  }

  async function onGuest() {
    if (busy) return;
    setBusy("guest");
    setError(null);
    setServerFields({});
    setSlow(false);
    const r = await continueAsGuest(() => setSlow(true));
    if (r.ok) return done();
    setBusy(null);
    setSlow(false);
    setError(r.error);
  }

  const signedIn = status === "authenticated" && user && !isGuest(user) && !busy;
  // Field-level problems show under their fields; everything else gets the banner.
  const formError = !!error && !Object.values(error.fields ?? {}).some(Boolean);

  return (
    <div>
      {signedIn && (
        <div className="mb-6 flex animate-enter flex-col gap-3 rounded-xl border border-indigo-200/70 bg-indigo-50/50 p-4">
          <p className="text-sm text-slate-700">
            You&apos;re already signed in as{" "}
            <span className="font-semibold break-all text-slate-950">{user.email || user.name}</span>.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Link href={next} className={cx(btn.primary, tap)}>
              Continue to Atlas
              <Icon name="arrowRight" />
            </Link>
            <button type="button" onClick={() => signOut(`/login?next=${encodeURIComponent(next)}`)} className={cx(btn.ghost, tap)}>
              Use another account
            </button>
          </div>
        </div>
      )}

      <h1 className="text-2xl font-semibold tracking-tight text-slate-950">{copy.title}</h1>
      <p className="mt-2 text-base leading-relaxed text-slate-600">{copy.sub}</p>

      <div
        role="tablist"
        aria-label="Account"
        className="mt-6 grid grid-cols-2 rounded-lg border border-slate-200 bg-slate-100/70 p-1"
      >
        {(["signin", "signup"] as const).map((m) => (
          <button
            key={m}
            ref={m === "signin" ? signinTabRef : signupTabRef}
            id={`${uid}-tab-${m}`}
            type="button"
            role="tab"
            aria-selected={mode === m}
            aria-controls={`${uid}-panel`}
            tabIndex={mode === m ? 0 : -1}
            onClick={() => switchMode(m)}
            onKeyDown={onTabKey}
            className={cx(
              "min-h-8 rounded-md px-3 text-sm font-medium transition-colors pointer-coarse:min-h-11",
              mode === m ? "bg-surface text-slate-950 ring-1 ring-slate-200" : "text-slate-600 hover:text-slate-900",
            )}
          >
            {m === "signin" ? "Sign in" : "Create account"}
          </button>
        ))}
      </div>

      <form
        id={`${uid}-panel`}
        role="tabpanel"
        aria-labelledby={`${uid}-tab-${mode}`}
        noValidate
        onSubmit={onSubmit}
        className="mt-6 space-y-4"
      >
        {mode === "signup" && (
          <Field id={ids.name} label="Name" optional error={shown("name")}>
            <input
              ref={nameRef}
              id={ids.name}
              name="name"
              autoComplete="name"
              value={name}
              onChange={(e) => edit("name", setName)(e.target.value)}
              onBlur={() => setTouched((t) => ({ ...t, name: true }))}
              aria-invalid={!!shown("name") || undefined}
              aria-describedby={describedBy("name")}
              disabled={!!busy}
              className={inputClass}
              placeholder="Ada Lovelace"
            />
          </Field>
        )}

        <Field id={ids.email} label="Email" error={shown("email")}>
          <input
            ref={emailRef}
            id={ids.email}
            name="email"
            type="email"
            inputMode="email"
            autoComplete={mode === "signin" ? "username" : "email"}
            autoCapitalize="none"
            spellCheck={false}
            value={email}
            onChange={(e) => edit("email", setEmail)(e.target.value)}
            onBlur={() => setTouched((t) => ({ ...t, email: true }))}
            aria-invalid={!!shown("email") || undefined}
            aria-describedby={describedBy("email")}
            aria-required
            disabled={!!busy}
            className={inputClass}
            placeholder="you@company.com"
          />
        </Field>

        <Field
          id={ids.password}
          label="Password"
          error={shown("password")}
          hint={capsLock ? "Caps Lock is on." : mode === "signup" ? `${MIN_PASSWORD} to ${MAX_PASSWORD} characters.` : undefined}
          trailing={
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              aria-pressed={showPassword}
              aria-controls={ids.password}
              className="rounded-md px-1 text-xs font-medium text-indigo-700 hover:underline pointer-coarse:min-h-8"
            >
              {showPassword ? "Hide" : "Show"}
              <span className="sr-only"> password</span>
            </button>
          }
        >
          <input
            ref={passwordRef}
            id={ids.password}
            name="password"
            type={showPassword ? "text" : "password"}
            autoComplete={mode === "signin" ? "current-password" : "new-password"}
            value={password}
            maxLength={MAX_PASSWORD + 1}
            onChange={(e) => edit("password", setPassword)(e.target.value)}
            onBlur={() => setTouched((t) => ({ ...t, password: true }))}
            onKeyUp={(e) => setCapsLock(e.getModifierState("CapsLock"))}
            aria-invalid={!!shown("password") || undefined}
            aria-describedby={describedBy("password", mode === "signup" || capsLock)}
            aria-required
            disabled={!!busy}
            className={inputClass}
          />
        </Field>

        <div aria-live="assertive" aria-atomic="true">
          {formError && error && (
            <div role="alert" className="flex animate-enter gap-2 rounded-xl border border-rose-200 bg-rose-50/70 p-3 text-sm">
              <Icon name="alert" className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
              <div className="min-w-0">
                <p className="leading-relaxed text-rose-900">{error.message}</p>
                {error.code === "email_taken" && (
                  <button
                    type="button"
                    onClick={() => switchMode("signin")}
                    className="mt-1 font-medium text-rose-900 underline underline-offset-2 hover:no-underline"
                  >
                    Sign in instead
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        <button type="submit" disabled={!!busy} className={cx(btn.primary, "w-full py-3", tap)}>
          {busy === "form" ? <Spinner /> : null}
          {busy === "form" ? copy.busy : copy.submit}
          {busy !== "form" && <Icon name="arrowRight" />}
        </button>
      </form>

      <div className="my-6 flex items-center gap-3" aria-hidden>
        <span className="h-px flex-1 bg-slate-200" />
        <span className="font-mono text-2xs tracking-label text-slate-500 uppercase">or</span>
        <span className="h-px flex-1 bg-slate-200" />
      </div>

      <button
        type="button"
        onClick={onGuest}
        disabled={!!busy}
        aria-describedby={`${uid}-guest-hint`}
        className={cx(
          "group flex w-full items-center gap-3 rounded-lg border border-slate-300 bg-surface p-3 text-left transition-colors hover:border-indigo-600/50 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60",
          tap,
        )}
      >
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent-400 text-ink-950">
          {busy === "guest" ? <Spinner className="h-4 w-4" /> : <Icon name="spark" className="h-4.5 w-4.5" />}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold text-slate-950">
            {busy === "guest" ? "Starting your demo…" : "Try the demo — no account"}
          </span>
          <span id={`${uid}-guest-hint`} className="block text-sm text-slate-500">
            One click. A limited demo session, no email needed.
          </span>
        </span>
        <Icon
          name="arrowRight"
          className="h-4 w-4 shrink-0 text-slate-400 transition-transform group-hover:translate-x-0.5 group-hover:text-slate-700"
        />
      </button>

      <p role="status" aria-live="polite" className="mt-4 min-h-[2.5rem] text-sm leading-relaxed text-slate-500">
        {busy && slow ? (
          <span className="flex items-start gap-2 text-slate-700">
            <Spinner className="mt-0.5 h-3.5 w-3.5 text-indigo-600" />
            Waking up the server. The free instance naps when idle, so this first step can take up to a minute.
          </span>
        ) : null}
      </p>
    </div>
  );
}
