import { cx, eyebrow, eyebrowDark } from "@/components/ui/styles";

/** Section kicker + serif headline + intro. `tone="dark"` for ink sections. */
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
  /** Optional trailing phrase set in italic gradient, e.g. "not just believed". */
  accent?: string;
  intro?: string;
  center?: boolean;
  tone?: "light" | "dark";
}) {
  const dark = tone === "dark";
  return (
    <div className={cx("max-w-2xl", center && "mx-auto text-center")}>
      <p className={cx(dark ? eyebrowDark : eyebrow, "inline-flex items-center gap-2")}>
        <span aria-hidden className={cx("h-px w-6", dark ? "bg-indigo-300/60" : "bg-indigo-600/50")} />
        {kicker}
      </p>
      <h2
        id={id}
        className={cx(
          "mt-4 font-display text-4xl leading-[1.05] tracking-tight text-balance sm:text-5xl",
          dark ? "text-white" : "text-slate-950",
        )}
      >
        {title}
        {accent && (
          <>
            {" "}
            <em className={dark ? "text-shine" : "text-shine-dark"}>{accent}</em>
          </>
        )}
      </h2>
      {intro && (
        <p className={cx("mt-5 text-lg leading-relaxed", dark ? "text-slate-400" : "text-slate-600")}>{intro}</p>
      )}
    </div>
  );
}
