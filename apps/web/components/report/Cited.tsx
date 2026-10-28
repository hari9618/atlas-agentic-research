import { chipLabel, sourceAnchor, splitCitations } from "@/lib/citations";

/** A small, subtle source chip that jumps to the matching entry in Sources. */
export function SourceChip({ label, sourceKey, ns }: { label: string; sourceKey: string; ns: string }) {
  return (
    <a
      href={`#${sourceAnchor(ns, sourceKey)}`}
      title={label}
      aria-label={`Source: ${label}`}
      className="mx-0.5 inline-flex translate-y-[-1px] items-center rounded border border-slate-200 bg-slate-50 px-1.5 py-px align-middle text-[10.5px] leading-4 font-medium whitespace-nowrap text-slate-500 no-underline transition-colors hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700"
    >
      {chipLabel(sourceKey)}
    </a>
  );
}

/** Render report text with inline `[source#n]` labels turned into source chips. */
export function Cited({ text, ns }: { text: string | undefined; ns: string }) {
  if (!text) return null;
  return (
    <>
      {splitCitations(text).map((s, i) =>
        s.type === "text" ? (
          <span key={i}>{s.text}</span>
        ) : (
          <SourceChip key={i} label={s.label} sourceKey={s.key} ns={ns} />
        ),
      )}
    </>
  );
}
