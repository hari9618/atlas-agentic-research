import { isPlaceholder } from "@/lib/citations";
import { cx } from "@/components/ui/styles";
import { Cited } from "./Cited";

/** Rendering context threaded through the report: an anchor namespace (so two
 *  reports on one page don't clash) and the heading level of the report title. */
export type Ctx = { ns: string; hl: 2 | 3 };

export function sectionId(c: Ctx, id: string) {
  return `${c.ns}-${id}`;
}

/** One section of the brief: numbered mono eyebrow, serif title, optional one-line
 *  description and a right-aligned aside (counts, overall pills). Sections sit inside a
 *  single document surface and are separated by hairlines, like a research note. */
export function Section({
  c,
  id,
  n,
  title,
  description,
  aside,
  children,
  className,
}: {
  c: Ctx;
  id: string;
  /** Position in the brief, shown as "01", "02"… */
  n?: number;
  title: string;
  description?: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  const H = c.hl === 2 ? "h3" : "h4";
  const sid = sectionId(c, id);
  return (
    <section
      id={sid}
      aria-labelledby={`${sid}-title`}
      className={cx(
        "scroll-mt-32 border-t border-slate-200/70 px-5 py-8 first-of-type:border-t-0 @2xl:px-10 @2xl:py-10",
        className,
      )}
    >
      <header className="mb-6 flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          {n != null && (
            <p aria-hidden className="flex items-center gap-2.5 font-mono text-[11px] font-medium text-indigo-600 tabular-nums">
              {String(n).padStart(2, "0")}
              <span className="h-px w-8 bg-indigo-600/30" />
            </p>
          )}
          <H id={`${sid}-title`} className="mt-2 font-display text-[1.75rem] leading-[1.1] tracking-tight text-slate-950">
            {title}
          </H>
          {description && <p className="mt-1.5 text-sm text-slate-500">{description}</p>}
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
    <p className={cx("max-w-[72ch] text-[15px] leading-7 text-slate-700", className)}>
      <Cited text={text} ns={c.ns} />
    </p>
  );
}

export function Muted({ children, className }: { children: React.ReactNode; className?: string }) {
  return <p className={cx("text-sm text-slate-500 italic", className)}>{children}</p>;
}

/** Cited text inline, with placeholders muted. */
export function CitedOrMuted({ text, c }: { text: string; c: Ctx }) {
  return isPlaceholder(text) ? <span className="text-slate-500 italic">{text}</span> : <Cited text={text} ns={c.ns} />;
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
    <ul className={cx("space-y-2.5", className)}>
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
    <p className={cx("font-mono text-[10.5px] font-medium tracking-[0.16em] text-slate-500 uppercase", className)}>
      {children}
    </p>
  );
}
