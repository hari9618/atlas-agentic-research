import { type CitationNumbers, isPlaceholder } from "@/lib/citations";
import { cx } from "@/components/ui/styles";
import { Cited } from "./Cited";

/** Rendering context threaded through the report: an anchor namespace (so two
 *  reports on one page don't clash), the heading level of the report title, an
 *  optional flagged section (e.g. the one a reviewer asked to change) and the report's
 *  citation numbering (shared by every chip and the Sources list). */
export type Ctx = { ns: string; hl: 2 | 3; flag?: { block: string; label: string }; nums?: CitationNumbers };

export function sectionId(c: Ctx, id: string) {
  return `${c.ns}-${id}`;
}

/** One section of the brief: a plain heading, an optional one-line description and a
 *  right-aligned aside (counts, overall tags). Sections sit inside a single document
 *  surface and are separated by hairlines, like a research note. `n` (reading order)
 *  drives the table of contents only. */
export function Section({
  c,
  id,
  title,
  description,
  aside,
  children,
  className,
}: {
  c: Ctx;
  id: string;
  n?: number;
  title: string;
  description?: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  const H = c.hl === 2 ? "h3" : "h4";
  const sid = sectionId(c, id);
  const flagged = c.flag?.block === id;
  return (
    <section
      id={sid}
      aria-labelledby={`${sid}-title`}
      className={cx(
        "relative scroll-mt-32 border-t border-slate-200/80 px-5 py-8 first-of-type:border-t-0 @2xl:px-10",
        flagged && "bg-indigo-50/40",
        className,
      )}
    >
      {flagged && <span aria-hidden className="absolute inset-y-0 left-0 w-0.5 bg-indigo-600" />}
      <header className="mb-6 flex flex-wrap items-start justify-between gap-x-6 gap-y-2">
        <div className="min-w-0">
          {flagged && (
            <p className="screen-only mb-2 inline-flex items-center gap-2 rounded-md bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-800">
              {c.flag!.label}
            </p>
          )}
          <H id={`${sid}-title`} className="text-lg leading-snug font-semibold tracking-tight text-slate-950">
            {title}
          </H>
          {description && <p className="mt-1 max-w-[60ch] text-sm leading-relaxed text-slate-500">{description}</p>}
        </div>
        {aside && <div className="flex shrink-0 flex-wrap items-center gap-2">{aside}</div>}
      </header>
      {children}
    </section>
  );
}

/** Paragraph of cited text; placeholders ("Not enough evidence yet.") render muted. */
export function Prose({ text, c, className }: { text?: string; c: Ctx; className?: string }) {
  if (!text?.trim()) return null;
  if (isPlaceholder(text)) return <Muted>{text}</Muted>;
  return (
    <p className={cx("max-w-[72ch] text-base leading-7 text-slate-700", className)}>
      <Cited text={text} ns={c.ns} nums={c.nums} />
    </p>
  );
}

export function Muted({ children, className }: { children: React.ReactNode; className?: string }) {
  return <p className={cx("text-sm text-slate-500 italic", className)}>{children}</p>;
}

/** Cited text inline, with placeholders muted. */
export function CitedOrMuted({ text, c }: { text: string; c: Ctx }) {
  return isPlaceholder(text) ? <span className="text-slate-500 italic">{text}</span> : <Cited text={text} ns={c.ns} nums={c.nums} />;
}

/** Bulleted list of cited strings with a coloured marker. */
export function BulletList({
  items,
  c,
  marker = "bg-indigo-500",
  className,
}: {
  items: string[];
  c: Ctx;
  marker?: string;
  className?: string;
}) {
  const list = items.filter((s) => s?.trim());
  if (!list.length) return null;
  return (
    <ul className={cx("space-y-2", className)}>
      {list.map((item, i) => (
        <li key={i} className="flex gap-3 text-sm leading-relaxed text-slate-700">
          <span aria-hidden className={cx("mt-2 h-1.5 w-1.5 shrink-0 rounded-full", marker)} />
          <span className="min-w-0">
            <CitedOrMuted text={item} c={c} />
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Small mono label used above a sub-block inside a section. */
export function SubLabel({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <p className={cx("font-mono text-2xs font-medium tracking-label text-slate-500 uppercase", className)}>
      {children}
    </p>
  );
}
