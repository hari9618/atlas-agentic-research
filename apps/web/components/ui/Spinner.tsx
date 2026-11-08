import { cx } from "./styles";

/** Small circular spinner for in-button and inline busy states (decorative; pair it
 *  with visible text). Under reduced motion it holds still as a partial ring. */
export function Spinner({ className }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className={cx("h-4 w-4 shrink-0 animate-spin motion-reduce:animate-none", className)}>
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="2.5" opacity="0.2" />
      <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

/** Indeterminate progress track: for work with no measurable progress (cold starts,
 *  long server jobs). Static under reduced motion. */
export function IndeterminateBar({ className, tone = "light" }: { className?: string; tone?: "light" | "dark" }) {
  return (
    <div
      aria-hidden
      className={cx("h-1 overflow-hidden rounded-full", tone === "dark" ? "bg-white/[0.08]" : "bg-slate-200/70", className)}
    >
      <div
        className={cx(
          "h-full w-2/5 animate-indeterminate rounded-full motion-reduce:w-full motion-reduce:animate-none motion-reduce:opacity-40",
          tone === "dark" ? "bg-linear-to-r from-accent-400/0 via-accent-300 to-accent-400/0" : "bg-linear-to-r from-indigo-500/0 via-indigo-500 to-indigo-400/0",
        )}
      />
    </div>
  );
}
