// Formatting for the learning dashboard. Scores arrive as plain numbers (0-1 from the
// evaluators); anything larger is shown with one decimal rather than guessed at.

export function fmtScore(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return Math.abs(n) <= 1 ? n.toFixed(2) : n.toFixed(1);
}

export function fmtDelta(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  if (Math.abs(n) < 0.005) return "±0.00";
  return `${n > 0 ? "+" : "−"}${fmtScore(Math.abs(n))}`;
}

export type Direction = "up" | "down" | "flat";
export const direction = (n: number | null | undefined): Direction =>
  n == null || Math.abs(n) < 0.005 ? "flat" : n > 0 ? "up" : "down";

export function pct(part: number, whole: number): string {
  if (!whole) return "—";
  return `${Math.round((part / whole) * 100)}%`;
}

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 31_536_000],
  ["month", 2_592_000],
  ["week", 604_800],
  ["day", 86_400],
  ["hour", 3_600],
  ["minute", 60],
];

/** "3 hours ago". Only ever called on the client (data is fetched after mount), so it
 *  can't cause a hydration mismatch. */
export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const s = Math.round((t - Date.now()) / 1000);
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  for (const [unit, secs] of UNITS) {
    if (Math.abs(s) >= secs) return rtf.format(Math.round(s / secs), unit);
  }
  return "just now";
}

export function fullDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso;
  return new Date(t).toLocaleString("en", { dateStyle: "medium", timeStyle: "short" });
}

/** snake_case / kebab-case to "Sentence case". */
export function humanize(s: string | null | undefined): string {
  if (!s) return "";
  const t = s.replace(/[_-]+/g, " ").trim();
  return t.charAt(0).toUpperCase() + t.slice(1);
}
