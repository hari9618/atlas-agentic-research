import { cx } from "./styles";

/** Max-width page container with 16px gutters on phones, wider on desktop. */
export function Container({
  children,
  className,
  size = "default",
}: {
  children: React.ReactNode;
  className?: string;
  size?: "default" | "narrow";
}) {
  return (
    <div
      className={cx(
        "mx-auto w-full px-4 sm:px-6 lg:px-8",
        size === "narrow" ? "max-w-4xl" : "max-w-6xl",
        className,
      )}
    >
      {children}
    </div>
  );
}
