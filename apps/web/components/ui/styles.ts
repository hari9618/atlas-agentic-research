// Shared Tailwind class recipes so buttons, cards and badges stay consistent.
//
// Shape rules: containers rounded-xl (12px), controls rounded-lg (8px), tags rounded-md
// (6px); full rounding only for dots, avatars and the theme switch. Lime (accent) fills
// only the primary action and a few key status signals.

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

const btnBase =
  "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";

export const btn = {
  /** The one filled accent: lime reads the same on every surface and in both themes. */
  primary: `${btnBase} cursor-pointer bg-accent-400 px-4 py-2 text-sm text-ink-950 hover:bg-accent-300`,
  secondary: `${btnBase} border border-slate-300 bg-surface px-4 py-2 text-sm text-slate-800 hover:border-slate-400 hover:bg-slate-50`,
  ghost: `${btnBase} px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 hover:text-slate-900`,
  small: `${btnBase} border border-slate-300 bg-surface px-3 py-1 text-xs text-slate-700 hover:border-slate-400 hover:bg-slate-50`,
  /** Primary action on ink (dark) surfaces. */
  light: `${btnBase} bg-white px-4 py-2 text-sm text-ink-950 hover:bg-accent-300`,
};

/** 44 px minimum hit area on touch screens, without inflating dense desktop controls. */
export const tap = "pointer-coarse:min-h-11";

/** Lime status pills ("Released", "Approved", "Active"): filled, or outlined for quieter use. */
export const limePill =
  "inline-flex shrink-0 items-center gap-1 rounded-md bg-accent-400 px-2 py-0.5 text-xs font-medium whitespace-nowrap text-ink-950";
export const limeOutline =
  "inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium whitespace-nowrap text-indigo-700 ring-1 ring-indigo-600/30 ring-inset";

/** Toggle chip (section pickers, filters); pair with aria-pressed. */
export const toggleChip = `inline-flex min-h-8 items-center gap-2 rounded-md border px-3 py-1 text-xs font-medium transition-colors ${tap} border-slate-200 bg-surface text-slate-700 hover:border-slate-300 hover:bg-slate-50 aria-pressed:border-indigo-500 aria-pressed:bg-indigo-50 aria-pressed:text-indigo-800 aria-pressed:hover:bg-indigo-100`;

/** Card shape only; pair with your own border + background colours. */
export const cardBase = "rounded-xl border";
export const card = `${cardBase} border-slate-200/80 bg-surface`;

export const eyebrow = "font-mono text-2xs font-medium uppercase tracking-label text-indigo-600";
export const eyebrowDark = "font-mono text-2xs font-medium uppercase tracking-label text-indigo-300";

// Tone palette: positive / neutral / negative and low / medium / high severity.
export type ToneKey = "good" | "mid" | "bad" | "info" | "muted";

export const toneBadge: Record<ToneKey, string> = {
  good: "bg-emerald-50 text-emerald-800 ring-emerald-600/20",
  mid: "bg-amber-50 text-amber-800 ring-amber-600/25",
  bad: "bg-rose-50 text-rose-800 ring-rose-600/20",
  info: "bg-indigo-50 text-indigo-800 ring-indigo-600/20",
  muted: "bg-slate-100 text-slate-700 ring-slate-500/20",
};

/** The same tones for ink (dark) surfaces. */
export const toneBadgeDark: Record<ToneKey, string> = {
  good: "bg-emerald-400/10 text-emerald-300 ring-emerald-400/25",
  mid: "bg-amber-400/10 text-amber-200 ring-amber-400/25",
  bad: "bg-rose-400/10 text-rose-300 ring-rose-400/25",
  info: "bg-indigo-400/10 text-indigo-200 ring-indigo-400/25",
  muted: "bg-white/5 text-slate-300 ring-white/15",
};

/** The standard panel: workspace rail cards, dashboard blocks, the report document. A
 *  hairline border does the separating; no drop shadow. */
export const surface = "rounded-xl border border-slate-200/80 bg-surface";

/** Small mono uppercase label (KPI labels, column headers, meta rows). */
export const monoLabel = "font-mono text-2xs font-medium uppercase tracking-label";

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
