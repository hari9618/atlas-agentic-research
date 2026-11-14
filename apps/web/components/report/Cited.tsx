import { chipLabel, type CitationNumbers, sourceAnchor, splitCitations } from "@/lib/citations";
import { cx } from "@/components/ui/styles";

export type ChipTone = "light" | "dark";

const CHIP: Record<ChipTone, string> = {
  light:
    "border-slate-200/90 bg-slate-50 text-slate-600 hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-800 focus-visible:border-indigo-400",
  dark: "border-white/12 bg-white/[0.06] text-slate-300 hover:border-indigo-300/60 hover:bg-indigo-400/15 hover:text-white",
};

/** A small, subtle source chip that jumps to the matching entry in Sources. */
export function SourceChip({
  label,
  sourceKey,
  ns,
  nums,
  tone = "light",
}: {
  label: string;
  sourceKey: string;
  ns: string;
  /** The report's numbering; without it the chip shows only the source kind. */
  nums?: CitationNumbers;
  tone?: ChipTone;
}) {
  return (
    <a
      href={`#${sourceAnchor(ns, sourceKey)}`}
      title={label}
      aria-label={`Source: ${label}`}
      className={cx(
        "mx-[0.2em] inline-flex -translate-y-px items-center rounded-[5px] border px-2 align-middle font-mono text-2xs leading-[15px] font-medium tracking-tight whitespace-nowrap tabular-nums no-underline transition-colors duration-150",
        CHIP[tone],
      )}
    >
      {chipLabel(sourceKey, nums)}
    </a>
  );
}

/** Render report text with inline `[source#n]` labels turned into source chips. */
export function Cited({
  text,
  ns,
  nums,
  tone = "light",
}: {
  text: string | undefined;
  ns: string;
  nums?: CitationNumbers;
  tone?: ChipTone;
}) {
  if (!text) return null;
  return (
    <>
      {splitCitations(text).map((s, i) =>
        s.type === "text" ? (
          <span key={i}>{s.text}</span>
        ) : (
          <SourceChip key={i} label={s.label} sourceKey={s.key} ns={ns} nums={nums} tone={tone} />
        ),
      )}
    </>
  );
}
