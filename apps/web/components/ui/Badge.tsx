import { cx, toneBadge, toneDot, type ToneKey } from "./styles";

/** Small status pill. Colour is never the only signal: the label is always text. */
export function Badge({
  tone = "muted",
  children,
  dot = false,
  className,
}: {
  tone?: ToneKey;
  children: React.ReactNode;
  dot?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cx(
        "inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ring-1 ring-inset",
        toneBadge[tone],
        className,
      )}
    >
      {dot && <span aria-hidden className={cx("h-1.5 w-1.5 rounded-full", toneDot[tone])} />}
      {children}
    </span>
  );
}
