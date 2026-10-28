import { Icon } from "./Icon";
import { cx } from "./styles";

/** Collapsible section built on native <details>/<summary>: keyboard-operable and
 *  screen-reader friendly with zero JavaScript, so it also works in server components. */
export function Disclosure({
  summary,
  children,
  defaultOpen = false,
  className,
  summaryClassName,
  name,
}: {
  summary: React.ReactNode;
  children: React.ReactNode;
  defaultOpen?: boolean;
  className?: string;
  summaryClassName?: string;
  /** Same `name` on several disclosures makes them an exclusive accordion. */
  name?: string;
}) {
  return (
    <details open={defaultOpen} name={name} className={cx("group", className)}>
      <summary
        className={cx(
          "flex items-center justify-between gap-4 rounded-lg py-3 text-left",
          summaryClassName,
        )}
      >
        {summary}
        <Icon
          name="chevron"
          className="chevron h-5 w-5 shrink-0 text-slate-400 transition-transform"
        />
      </summary>
      {children}
    </details>
  );
}
