import { cx } from "@/components/ui/styles";

/** Plain-English reading of a 0-1 confidence score. */
export function confidenceLabel(v: number): { label: string; hint: string; bar: string; text: string } {
  if (v >= 0.75)
    return {
      label: "High confidence",
      hint: "Strong, consistent evidence behind the main conclusions.",
      bar: "bg-emerald-500",
      text: "text-emerald-700",
    };
  if (v >= 0.5)
    return {
      label: "Moderate confidence",
      hint: "The main points are supported, with some gaps in the evidence.",
      bar: "bg-amber-500",
      text: "text-amber-700",
    };
  if (v >= 0.3)
    return {
      label: "Low confidence",
      hint: "Evidence is thin or mixed. Treat conclusions as provisional.",
      bar: "bg-rose-500",
      text: "text-rose-700",
    };
  return {
    label: "Very low confidence",
    hint: "Little usable evidence was found for this question.",
    bar: "bg-rose-500",
    text: "text-rose-700",
  };
}

/** 0-100 confidence meter with a plain label. */
export function ConfidenceMeter({
  value,
  compact = false,
  className,
}: {
  value: number | null | undefined;
  compact?: boolean;
  className?: string;
}) {
  if (value == null || Number.isNaN(value)) return null;
  const v = Math.max(0, Math.min(1, value > 1 ? value / 100 : value));
  const pct = Math.round(v * 100);
  const info = confidenceLabel(v);

  return (
    <div className={cx("min-w-0", className)}>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-xs font-medium text-slate-500">Confidence</span>
        <span className="text-sm text-slate-500">
          <span className={cx("font-semibold tabular-nums", compact ? "text-lg" : "text-2xl", info.text)}>
            {pct}
          </span>
          <span>/100</span>
        </span>
      </div>
      <div
        role="meter"
        aria-label="Confidence"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-valuetext={`${pct} out of 100, ${info.label.toLowerCase()}`}
        className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-slate-100"
      >
        <div className={cx("h-full rounded-full transition-[width] duration-700", info.bar)} style={{ width: `${pct}%` }} />
      </div>
      <p className={cx("mt-1.5 text-xs font-medium", info.text)}>{info.label}</p>
      {!compact && <p className="mt-0.5 text-xs leading-relaxed text-slate-500">{info.hint}</p>}
    </div>
  );
}
