// Shared Tailwind class recipes so buttons, cards and badges stay consistent.

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

const btnBase =
  "inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50";

export const btn = {
  primary: `${btnBase} bg-indigo-600 px-4 py-2.5 text-sm text-white shadow-sm hover:bg-indigo-700`,
  secondary: `${btnBase} border border-slate-300 bg-white px-4 py-2.5 text-sm text-slate-800 hover:border-slate-400 hover:bg-slate-50`,
  ghost: `${btnBase} px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 hover:text-slate-900`,
  small: `${btnBase} border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 hover:border-slate-400 hover:bg-slate-50`,
  lg: "px-5 py-3 text-base",
};

/** Card shape only; pair with your own border + background colours. */
export const cardBase = "rounded-xl border";
export const card = `${cardBase} border-slate-200 bg-white`;
export const cardPad = "p-5 sm:p-6";

export const eyebrow = "text-xs font-semibold uppercase tracking-wider text-indigo-600";

export const chip =
  "inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700";

// Tone palette: positive / neutral / negative and low / medium / high severity.
export type ToneKey = "good" | "mid" | "bad" | "info" | "muted";

export const toneBadge: Record<ToneKey, string> = {
  good: "bg-emerald-50 text-emerald-800 ring-emerald-600/20",
  mid: "bg-amber-50 text-amber-800 ring-amber-600/25",
  bad: "bg-rose-50 text-rose-800 ring-rose-600/20",
  info: "bg-indigo-50 text-indigo-800 ring-indigo-600/20",
  muted: "bg-slate-100 text-slate-700 ring-slate-500/20",
};

export const toneDot: Record<ToneKey, string> = {
  good: "bg-emerald-500",
  mid: "bg-amber-500",
  bad: "bg-rose-500",
  info: "bg-indigo-500",
  muted: "bg-slate-400",
};

/** Map any enum value from the report schema to a tone. */
export function toneOf(value: string | undefined): ToneKey {
  switch ((value ?? "").toLowerCase().trim()) {
    case "positive":
    case "low":
    case "approved":
      return "good";
    case "neutral":
    case "mixed":
    case "medium":
    case "moderate":
      return "mid";
    case "cautious":
    case "negative":
    case "high":
      return "bad";
    default:
      return "muted";
  }
}

export function titleCase(s: string | undefined): string {
  if (!s) return "";
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
}
