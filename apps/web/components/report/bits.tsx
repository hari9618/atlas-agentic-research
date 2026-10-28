import { citationKey, hasText, splitCitations } from "@/lib/citations";
import { Icon } from "@/components/ui/Icon";
import { cx, titleCase, toneBadge, toneBadgeDark, toneDot, toneOf } from "@/components/ui/styles";
import { SourceChip, type ChipTone } from "./Cited";

const LEVEL_BARS: Record<string, number> = { high: 3, medium: 2, moderate: 2, low: 1 };
const BAR_HEIGHT = ["h-1.5", "h-2", "h-2.5"];

/** Severity / threat pill: a three-bar glyph plus the level as text, so colour is
 *  never the only signal. Unknown values fall back to a neutral pill. */
export function LevelPill({
  value,
  suffix = "",
  surface = "light",
  className,
}: {
  value?: string;
  suffix?: string;
  surface?: "light" | "dark";
  className?: string;
}) {
  if (!hasText(value)) return null;
  const tone = toneOf(value);
  const filled = LEVEL_BARS[value.toLowerCase().trim()] ?? 0;
  return (
    <span
      className={cx(
        "inline-flex shrink-0 items-center gap-2 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ring-1 ring-inset",
        surface === "dark" ? toneBadgeDark[tone] : toneBadge[tone],
        className,
      )}
    >
      <span aria-hidden className="flex items-end gap-[2px]">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className={cx("w-[3px] rounded-full", BAR_HEIGHT[i], i < filled ? toneDot[tone] : "bg-current opacity-25")}
          />
        ))}
      </span>
      {titleCase(value)}
      {suffix}
    </span>
  );
}

export type Direction = "up" | "down" | "flat";

/** Read a metric's change text ("+28% YoY", "down 4%") as a direction. */
export function changeDirection(change: string | undefined): Direction {
  const t = (change ?? "").trim();
  if (/^[+▲↑]|\bup\b|increase|growth|grew|higher|rise|rose/i.test(t)) return "up";
  if (/^[-−▼↓]\s*\d|\bdown\b|decline|decrease|lower|fell|drop/i.test(t)) return "down";
  return "flat";
}

const TREND_TEXT: Record<Direction, Record<"light" | "dark", string>> = {
  up: { light: "text-emerald-700", dark: "text-emerald-300" },
  down: { light: "text-rose-700", dark: "text-rose-300" },
  flat: { light: "text-slate-500", dark: "text-slate-400" },
};

/** Change text with a direction arrow (shape + colour, never colour alone). */
export function Trend({ change, surface = "light" }: { change?: string; surface?: "light" | "dark" }) {
  if (!hasText(change)) return null;
  const d = changeDirection(change);
  return (
    <span className={cx("inline-flex min-w-0 items-start gap-1 text-xs font-medium", TREND_TEXT[d][surface])}>
      {d !== "flat" && (
        <Icon name={d === "up" ? "trending" : "trendingDown"} className="mt-px h-3.5 w-3.5 shrink-0" strokeWidth={2.25} />
      )}
      <span className="min-w-0">{change}</span>
    </span>
  );
}

/** Chips for a `citation` field such as "[sec_edgar#0]" or "[a#0; b#1]". */
export function CiteChips({ citation, ns, tone = "light" }: { citation?: string; ns: string; tone?: ChipTone }) {
  if (!hasText(citation)) return null;
  const cites = splitCitations(citation).filter((x) => x.type === "cite");
  if (!cites.length) return <SourceChip label={citation} sourceKey={citationKey(citation)} ns={ns} tone={tone} />;
  return (
    <>
      {cites.map((x, i) =>
        x.type === "cite" ? <SourceChip key={i} label={x.label} sourceKey={x.key} ns={ns} tone={tone} /> : null,
      )}
    </>
  );
}

/** Two-letter monogram tile for a company name (decorative). */
export function Monogram({ name, className }: { name: string; className?: string }) {
  const letters =
    name
      .replace(/[^A-Za-z0-9 ]+/g, " ")
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((w) => w[0]?.toUpperCase())
      .join("") || "?";
  return (
    <span
      aria-hidden
      className={cx(
        "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-ink-950 font-mono text-[11px] font-semibold text-white ring-1 ring-ink-700",
        className,
      )}
    >
      {letters}
    </span>
  );
}
