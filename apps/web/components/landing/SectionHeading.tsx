import { cx, eyebrow } from "@/components/ui/styles";

export function SectionHeading({
  id,
  kicker,
  title,
  intro,
  center = false,
}: {
  id: string;
  kicker: string;
  title: string;
  intro?: string;
  center?: boolean;
}) {
  return (
    <div className={cx("max-w-2xl", center && "mx-auto text-center")}>
      <p className={eyebrow}>{kicker}</p>
      <h2 id={id} className="mt-2 text-3xl font-semibold tracking-tight text-balance text-slate-900 sm:text-4xl">
        {title}
      </h2>
      {intro && <p className="mt-4 text-lg leading-relaxed text-slate-600">{intro}</p>}
    </div>
  );
}
