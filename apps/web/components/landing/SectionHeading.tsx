import { cx } from "@/components/ui/styles";

/** Section label + headline + intro for the landing page. The optional `accent` is the
 *  second clause of the headline, set in a quieter colour (not a different face). */
export function SectionHeading({
  id,
  kicker,
  title,
  accent,
  intro,
  center = false,
  tone = "light",
}: {
  id: string;
  kicker: string;
  title: string;
  accent?: string;
  intro?: string;
  center?: boolean;
  tone?: "light" | "dark";
}) {
  const dark = tone === "dark";
  return (
    <div className={cx("max-w-2xl", center && "mx-auto text-center")}>
      <p className={cx("text-sm font-medium", dark ? "text-indigo-300" : "text-indigo-700")}>{kicker}</p>
      <h2
        id={id}
        className={cx(
          "mt-2 text-3xl leading-tight font-semibold tracking-tight text-balance sm:text-4xl",
          dark ? "text-white" : "text-slate-950",
        )}
      >
        {title}
        {accent && <span className={dark ? "text-slate-400" : "text-slate-500"}> {accent}</span>}
      </h2>
      {intro && (
        <p className={cx("mt-4 text-base leading-relaxed sm:text-lg", dark ? "text-slate-400" : "text-slate-600")}>
          {intro}
        </p>
      )}
    </div>
  );
}
