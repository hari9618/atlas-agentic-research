import { chipLabel, sourceAnchor, splitCitations } from "@/lib/citations";
import { cx } from "@/components/ui/styles";

export type ChipTone = "light" | "dark";

const CHIP: Record<ChipTone, string> = {
  light:
    "border-slate-200 bg-slate-50 text-slate-500 hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700",
  dark: "border-white/15 bg-white/[0.06] text-slate-300 hover:border-indigo-300/60 hover:bg-indigo-400/15 hover:text-white",
};

/** A small, subtle source chip that jumps to the matching entry in Sources. */
export function SourceChip({
  label,
  sourceKey,
  ns,
  tone = "light",
}: {
  label: string;
  sourceKey: string;
  ns: string;
  tone?: ChipTone;
}) {
  return (
    <a
      href={`#${sourceAnchor(ns, sourceKey)}`}
      title={label}
      aria-label={`Source: ${label}`}
      className={cx(
        "mx-0.5 inline-flex translate-y-[-1px] items-center rounded border px-1.5 py-px align-middle font-mono text-[10px] leading-4 font-medium whitespace-nowrap no-underline transition-colors",
        CHIP[tone],
      )}
    >
      {chipLabel(sourceKey)}
    </a>
  );
}

/** Render report text with inline `[source#n]` labels turned into source chips. */
export function Cited({ text, ns, tone = "light" }: { text: string | undefined; ns: string; tone?: ChipTone }) {
  if (!text) return null;
  return (
    <>
      {splitCitations(text).map((s, i) =>
        s.type === "text" ? (
          <span key={i}>{s.text}</span>
        ) : (
          <SourceChip key={i} label={s.label} sourceKey={s.key} ns={ns} tone={tone} />
        ),
      )}
    </>
  );
}
