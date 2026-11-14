import { cx } from "@/components/ui/styles";

/** Shared input look for the auth forms. 16px text on phones so iOS doesn't zoom on
 *  focus; the focus border uses indigo-600, which is deep green in light mode and lime
 *  in dark, so it keeps a 3:1 contrast on both. */
export const inputClass =
  "block w-full rounded-lg border border-slate-300 bg-surface px-3 py-2 text-base text-slate-950 transition-colors placeholder:text-slate-500 hover:border-slate-400 focus:border-indigo-600 focus:ring-4 focus:ring-indigo-600/15 focus:outline-none aria-invalid:border-rose-500 aria-invalid:focus:ring-rose-500/15 disabled:opacity-60 sm:text-base";

/** Label, control, then hint or error, wired up for screen readers: the error replaces
 *  the hint and is what aria-describedby points at while it shows. */
export function Field({
  id,
  label,
  optional = false,
  hint,
  error,
  trailing,
  children,
}: {
  id: string;
  label: string;
  optional?: boolean;
  hint?: React.ReactNode;
  error?: string;
  /** Right side of the label row (e.g. a "Show" toggle). */
  trailing?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-sm font-medium text-slate-800">
          {label}
          {optional && <span className="ml-2 text-xs font-normal text-slate-500">optional</span>}
        </label>
        {trailing}
      </div>
      {children}
      {error ? (
        <p id={`${id}-msg`} className="mt-2 flex items-start gap-2 text-sm leading-snug text-rose-700">
          <svg aria-hidden viewBox="0 0 16 16" className="mt-0.5 h-3.5 w-3.5 shrink-0" fill="currentColor">
            <path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 3.25a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0V5A.75.75 0 018 4.25zM8 11.5a.875.875 0 110-1.75.875.875 0 010 1.75z" />
          </svg>
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-msg`} className={cx("mt-2 text-sm leading-snug text-slate-500")}>
          {hint}
        </p>
      ) : null}
    </div>
  );
}
