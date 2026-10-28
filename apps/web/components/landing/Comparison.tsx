import { Container } from "@/components/ui/Container";
import { Icon } from "@/components/ui/Icon";
import { cx } from "@/components/ui/styles";
import { SectionHeading } from "./SectionHeading";

type Cell = { v: "yes" | "no" | "partial"; text: string };
const yes = (text: string): Cell => ({ v: "yes", text });
const no = (text: string): Cell => ({ v: "no", text });
const partial = (text: string): Cell => ({ v: "partial", text });

const COLS = ["Atlas", "General AI chatbot", "Manual analyst"] as const;

const ROWS: { label: string; cells: [Cell, Cell, Cell] }[] = [
  { label: "Every claim cited to a source", cells: [yes("Always, inline"), partial("Sometimes"), yes("Usually")] },
  { label: "Live filings, market data and news", cells: [yes("Built in"), partial("Depends on the tool"), yes("Yes")] },
  { label: "Structured, investor-style sections", cells: [yes("Every report"), no("Free-form text"), yes("Yes")] },
  { label: "Both sides argued", cells: [yes("Bull vs bear debate"), no("Rarely"), partial("Depends on the analyst")] },
  { label: "Says what it's not sure about", cells: [yes("Dedicated section"), no("Rarely"), partial("Sometimes")] },
  { label: "You review and request changes", cells: [yes("Built-in review loop"), partial("Re-prompt and hope"), yes("Back-and-forth")] },
  { label: "Turnaround", cells: [yes("Minutes"), yes("Seconds"), no("Days to weeks")] },
];

function Mark({ v }: { v: Cell["v"] }) {
  if (v === "yes")
    return (
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
        <Icon name="check" className="h-3 w-3" strokeWidth={3} />
        <span className="sr-only">Yes:</span>
      </span>
    );
  if (v === "no")
    return (
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        <Icon name="x" className="h-3 w-3" strokeWidth={3} />
        <span className="sr-only">No:</span>
      </span>
    );
  return (
    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-700">
      <span className="h-0.5 w-2.5 rounded bg-current" />
      <span className="sr-only">Partly:</span>
    </span>
  );
}

function CellView({ c, strong }: { c: Cell; strong?: boolean }) {
  return (
    <span className="flex items-center gap-2">
      <Mark v={c.v} />
      <span className={cx("text-sm", strong ? "font-medium text-slate-900" : "text-slate-600")}>{c.text}</span>
    </span>
  );
}

export function Comparison() {
  return (
    <section id="compare" aria-labelledby="compare-title" className="scroll-mt-24 bg-white py-24 sm:py-28">
      <Container>
        <div className="reveal">
          <SectionHeading
            id="compare-title"
            kicker="Compare"
            title="Faster than an analyst."
            accent="More careful than a chatbot."
            intro="Chatbots are quick but unsourced. Analysts are thorough but slow. Atlas aims for both speed and receipts."
          />
        </div>

        {/* Desktop table */}
        <div className="reveal mt-14 hidden overflow-hidden rounded-3xl border border-slate-200/80 bg-white shadow-[0_30px_80px_-40px_rgb(15_23_42/0.25)] md:block">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-slate-200">
                <th scope="col" className="w-[28%] bg-slate-50/70 px-6 py-5 text-sm font-medium text-slate-500">
                  <span className="sr-only">Capability</span>
                </th>
                {COLS.map((col, i) => (
                  <th
                    key={col}
                    scope="col"
                    className={cx(
                      "px-6 py-5 text-sm font-semibold",
                      i === 0 ? "bg-ink-950 text-white" : "bg-slate-50/70 text-slate-700",
                    )}
                  >
                    {i === 0 ? (
                      <span className="flex items-center gap-2">
                        <span className="font-display text-xl font-normal">Atlas</span>
                        <span className="rounded-full bg-indigo-500/20 px-2 py-0.5 font-mono text-[10px] tracking-wider text-indigo-200 uppercase">
                          You are here
                        </span>
                      </span>
                    ) : (
                      col
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {ROWS.map((r) => (
                <tr key={r.label}>
                  <th scope="row" className="px-6 py-4 text-sm font-medium text-slate-900">{r.label}</th>
                  {r.cells.map((c, i) => (
                    <td key={i} className={cx("px-6 py-4", i === 0 && "bg-indigo-50/50")}>
                      <CellView c={c} strong={i === 0} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Phone: one card per capability */}
        <ul className="mt-12 space-y-3 md:hidden">
          {ROWS.map((r) => (
            <li key={r.label} className="rounded-2xl border border-slate-200/80 bg-white p-4">
              <p className="text-sm font-semibold text-slate-900">{r.label}</p>
              <dl className="mt-3 space-y-2">
                {r.cells.map((c, i) => (
                  <div
                    key={i}
                    className={cx(
                      "flex items-center justify-between gap-3 rounded-lg px-2.5 py-1.5",
                      i === 0 && "bg-indigo-50",
                    )}
                  >
                    <dt className={cx("text-xs", i === 0 ? "font-semibold text-indigo-800" : "text-slate-500")}>
                      {COLS[i]}
                    </dt>
                    <dd>
                      <CellView c={c} strong={i === 0} />
                    </dd>
                  </div>
                ))}
              </dl>
            </li>
          ))}
        </ul>
      </Container>
    </section>
  );
}
