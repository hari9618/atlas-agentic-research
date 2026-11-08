// Shared Tailwind class recipes so buttons, cards and badges stay consistent.

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

const btnBase =
  "inline-flex items-center justify-center gap-2 rounded-full font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-50";

export const btn = {
  /** The one filled accent: gold reads the same on every surface and in both themes. */
  primary: `${btnBase} cursor-pointer bg-accent-400 px-4 py-2.5 text-sm text-ink-950 hover:bg-accent-300`,
  secondary: `${btnBase} border border-slate-300 bg-surface px-4 py-2.5 text-sm text-slate-800 shadow-xs hover:border-slate-400 hover:bg-slate-50`,
  ghost: `${btnBase} px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 hover:text-slate-900`,
  small: `${btnBase} border border-slate-300 bg-surface px-3 py-1.5 text-xs text-slate-700 hover:border-slate-400 hover:bg-slate-50`,
  /** Bright pill for ink (dark) surfaces. */
  light: `${btnBase} bg-white px-4 py-2.5 text-sm text-ink-950 shadow-[0_8px_30px_-8px_rgb(190_235_70/0.55)] hover:bg-accent-300`,
  /** Outline pill for ink (dark) surfaces. */
  ghostDark: `${btnBase} border border-white/15 bg-white/5 px-4 py-2.5 text-sm text-white backdrop-blur hover:border-white/30 hover:bg-white/10`,
  lg: "px-6 py-3 text-base",
};

/** 44 px minimum hit area on touch screens, without inflating dense desktop controls. */
export const tap = "pointer-coarse:min-h-11";

/** Lime status pills ("Released", "Approved", "Active"): filled, or outlined for quieter use. */
export const limePill =
  "inline-flex shrink-0 items-center gap-1.5 rounded-full bg-accent-400 px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap text-ink-950";
export const limeOutline =
  "inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap text-indigo-700 ring-1 ring-accent-400/60 ring-inset";

/** Toggle chip (section pickers, filters); pair with aria-pressed. */
export const toggleChip = `inline-flex min-h-8 items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${tap} border-slate-200 bg-surface text-slate-700 hover:border-slate-300 hover:bg-slate-50 aria-pressed:border-indigo-500 aria-pressed:bg-indigo-50 aria-pressed:text-indigo-800 aria-pressed:hover:bg-indigo-100`;

/** Card shape only; pair with your own border + background colours. */
export const cardBase = "rounded-2xl border";
export const card = `${cardBase} border-slate-200/80 bg-surface shadow-[0_1px_2px_rgb(15_23_42/0.04)]`;
export const cardPad = "p-5 sm:p-6";

export const eyebrow = "font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-indigo-600";
export const eyebrowDark = "font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-indigo-300";

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

/** The same tones for ink (dark) surfaces. */
export const toneBadgeDark: Record<ToneKey, string> = {
  good: "bg-emerald-400/10 text-emerald-300 ring-emerald-400/25",
  mid: "bg-amber-400/10 text-amber-200 ring-amber-400/25",
  bad: "bg-rose-400/10 text-rose-300 ring-rose-400/25",
  info: "bg-indigo-400/10 text-indigo-200 ring-indigo-400/25",
  muted: "bg-white/5 text-slate-300 ring-white/15",
};

export const toneText: Record<ToneKey, string> = {
  good: "text-emerald-700",
  mid: "text-amber-700",
  bad: "text-rose-700",
  info: "text-indigo-700",
  muted: "text-slate-500",
};

/** Raised white surface used for workspace rail cards and the report document. */
export const surface =
  "rounded-2xl border border-slate-200/80 bg-surface shadow-[0_1px_2px_rgb(15_23_42/0.04),0_12px_32px_-18px_rgb(15_23_42/0.14)]";

/** Small mono uppercase label (KPI labels, column headers, meta rows). */
export const monoLabel = "font-mono text-[10.5px] font-medium uppercase tracking-[0.16em]";

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
