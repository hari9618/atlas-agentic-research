import { cx, surface } from "@/components/ui/styles";

/** One block of the account page: title, a line of context, then the content.
 *  `tone="danger"` for irreversible actions. */
export function AccountSection({
  id,
  title,
  text,
  tone = "default",
  children,
}: {
  id: string;
  title: string;
  text?: React.ReactNode;
  tone?: "default" | "danger";
  children: React.ReactNode;
}) {
  const danger = tone === "danger";
  return (
    <section
      aria-labelledby={id}
      className={cx(danger ? "rounded-xl border border-rose-200 bg-rose-50/40" : surface, "p-5 sm:p-6")}
    >
      <div>
        <div className="min-w-0">
          <h2 id={id} className={cx("text-base font-semibold", danger ? "text-rose-900" : "text-slate-950")}>
            {title}
          </h2>
          {text && <p className="mt-0.5 text-sm leading-relaxed text-slate-600">{text}</p>}
        </div>
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}
