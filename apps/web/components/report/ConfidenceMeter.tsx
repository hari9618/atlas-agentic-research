import { cx } from "@/components/ui/styles";

type ConfidenceInfo = {
  label: string;
  hint: string;
  /** Bar fill on light surfaces. */
  bar: string;
  /** Label colour on light surfaces. */
  text: string;
  /** Ring stroke + label colour on ink surfaces. */
  ring: string;
  textDark: string;
};

/** Plain-English reading of a 0-1 confidence score. */
export function confidenceLabel(v: number): ConfidenceInfo {
  if (v >= 0.75)
    return {
      label: "High confidence",
      hint: "Strong, consistent evidence behind the main conclusions.",
      bar: "bg-emerald-500",
      text: "text-emerald-700",
      ring: "stroke-emerald-400",
      textDark: "text-emerald-300",
    };
  if (v >= 0.5)
    return {
      label: "Moderate confidence",
      hint: "The main points are supported, with some gaps in the evidence.",
      bar: "bg-amber-500",
      text: "text-amber-700",
      ring: "stroke-amber-400",
      textDark: "text-amber-200",
    };
  if (v >= 0.3)
    return {
      label: "Low confidence",
      hint: "Evidence is thin or mixed. Treat conclusions as provisional.",
      bar: "bg-rose-500",
      text: "text-rose-700",
      ring: "stroke-rose-400",
      textDark: "text-rose-300",
    };
  return {
    label: "Very low confidence",
    hint: "Little usable evidence was found for this question.",
    bar: "bg-rose-500",
    text: "text-rose-700",
    ring: "stroke-rose-400",
    textDark: "text-rose-300",
  };
}

/** Accepts 0-1 or 0-100 and returns a clamped 0-1 value (null when missing). */
export function normalizeConfidence(value: number | null | undefined): number | null {
  if (value == null || Number.isNaN(value)) return null;
  return Math.max(0, Math.min(1, value > 1 ? value / 100 : value));
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
  const v = normalizeConfidence(value);
  if (v == null) return null;
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

const R = 42;
const CIRC = 2 * Math.PI * R;
// A 270-degree gauge: the open quarter sits at the bottom, like an instrument dial.
const ARC = CIRC * 0.75;

/** Instrument-style confidence dial for the ink summary band. */
export function ConfidenceDial({ value, className }: { value: number | null | undefined; className?: string }) {
  const v = normalizeConfidence(value);
  if (v == null) return null;
  const pct = Math.round(v * 100);
  const info = confidenceLabel(v);

  return (
    <div className={cx("flex items-center gap-4", className)}>
      <div
        role="meter"
        aria-label="Confidence"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-valuetext={`${pct} out of 100, ${info.label.toLowerCase()}`}
        className="relative h-[6.5rem] w-[6.5rem] shrink-0"
      >
        <svg viewBox="0 0 100 100" className="h-full w-full rotate-[135deg]" aria-hidden>
          <circle
            cx="50"
            cy="50"
            r={R}
            fill="none"
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={`${ARC} ${CIRC}`}
            className="stroke-white/10"
          />
          <circle
            cx="50"
            cy="50"
            r={R}
            fill="none"
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={`${ARC * v} ${CIRC}`}
            className={cx("transition-[stroke-dasharray] duration-700", info.ring)}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center pt-1">
          <span className="font-mono text-[1.9rem] leading-none font-semibold tracking-tight text-white tabular-nums">
            {pct}
          </span>
          <span className="mt-1 font-mono text-[10px] tracking-wider text-slate-500">/ 100</span>
        </div>
      </div>
      <div className="min-w-0">
        <p className="font-mono text-[10.5px] font-medium tracking-[0.16em] text-slate-400 uppercase">Confidence</p>
        <p className={cx("mt-1 text-sm font-semibold", info.textDark)}>{info.label}</p>
        <p className="mt-1 max-w-[15rem] text-xs leading-relaxed text-slate-400">{info.hint}</p>
      </div>
    </div>
  );
}
