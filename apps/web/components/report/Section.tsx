import { isPlaceholder } from "@/lib/citations";
import { card, cardBase, cx } from "@/components/ui/styles";
import { Cited } from "./Cited";

/** Rendering context threaded through the report: an anchor namespace (so two
 *  reports on one page don't clash) and the heading level of the report title. */
export type Ctx = { ns: string; hl: 2 | 3 };

export function sectionId(c: Ctx, id: string) {
  return `${c.ns}-${id}`;
}

/** A titled report section card. Heading level follows the report title level. */
export function Section({
  c,
  id,
  title,
  aside,
  children,
  className,
}: {
  c: Ctx;
  id: string;
  title: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
  /** Optional border + background colours replacing the default white card. */
  className?: string;
}) {
  const H = c.hl === 2 ? "h3" : "h4";
  return (
    <section
      id={sectionId(c, id)}
      aria-labelledby={`${sectionId(c, id)}-title`}
      className={cx(className ? cardBase : card, "scroll-mt-24 p-5 sm:p-6", className)}
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <H id={`${sectionId(c, id)}-title`} className="text-base font-semibold text-slate-900">
          {title}
        </H>
        {aside}
      </div>
      {children}
    </section>
  );
}

/** Paragraph of cited text; placeholders ("Not enough evidence yet.") render muted. */
export function Prose({ text, c, className }: { text?: string; c: Ctx; className?: string }) {
  if (!text?.trim()) return null;
  if (isPlaceholder(text)) return <Muted>{text}</Muted>;
  return (
    <p className={cx("text-sm leading-relaxed text-slate-700", className)}>
      <Cited text={text} ns={c.ns} />
    </p>
  );
}

export function Muted({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-slate-500 italic">{children}</p>;
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
            {isPlaceholder(item) ? (
              <span className="text-slate-500 italic">{item}</span>
            ) : (
              <Cited text={item} ns={c.ns} />
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Small label used above a sub-block inside a section. */
export function SubLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-1.5 text-xs font-semibold tracking-wide text-slate-500 uppercase">{children}</p>
  );
}
