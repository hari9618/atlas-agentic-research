import type { Fact, HeadToHeadRow, PricingPlan, ReportSections } from "@/lib/api";
import { citationKey, hasText, isPlaceholder, nonEmpty } from "@/lib/citations";
import { personaLabel } from "@/lib/persona";
import { Icon } from "@/components/ui/Icon";
import { cx, monoLabel } from "@/components/ui/styles";
import { CiteChips } from "../bits";
import { Cited } from "../Cited";
import { CitedOrMuted, Prose, Section, type Ctx } from "../Section";
import { Ledger } from "./Market";

type P = { s: ReportSections; c: Ctx; n?: number };

/** A field's own `citation`, unless its text already cites that source inline. */
const extra = (citation: string | undefined, ...texts: (string | undefined)[]) =>
  hasText(citation) && !texts.some((t) => (t ?? "").includes(citationKey(citation))) ? citation : undefined;

// ---------------------------------------------------------------------------
// Verdict: the direct answer to the question, first thing in the brief.
// ---------------------------------------------------------------------------

export const hasVerdict = (s: ReportSections) => hasText(s.verdict?.answer) || hasText(s.verdict?.recommendation);

export function Verdict({ s, c, n }: P) {
  const v = s.verdict;
  if (!v || !hasVerdict(s)) return null;
  const persona = hasText(s.brief?.persona) ? personaLabel(s.brief?.persona) : "";
  return (
    <Section
      c={c}
      id="verdict"
      n={n}
      title="Verdict"
      description={persona ? `The answer to your question, as a ${persona.toLowerCase()}.` : "The answer to your question."}
    >
      <div className="border-l-2 border-indigo-600 pl-4 @2xl:pl-6">
        {hasText(v.recommendation) && (
          <p className="text-xl leading-snug font-semibold tracking-tight text-slate-950 @2xl:text-2xl">
            <CitedOrMuted text={v.recommendation} c={c} />
          </p>
        )}
        {hasText(v.answer) && <Prose text={v.answer} c={c} className={cx(hasText(v.recommendation) && "mt-2")} />}
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------------------
// Snapshot: quick facts as a definition list.
// ---------------------------------------------------------------------------

const facts = (s: ReportSections): Fact[] => (s.snapshot ?? []).filter((f) => hasText(f?.label) && hasText(f?.value));

export const hasSnapshot = (s: ReportSections) => nonEmpty(facts(s));

export function Snapshot({ s, c, n }: P) {
  const list = facts(s);
  if (!nonEmpty(list)) return null;
  return (
    <Section c={c} id="snapshot" n={n} title="Snapshot" description="Quick facts, each with its source.">
      <dl className="grid grid-cols-1 border-t border-slate-200/80 @md:grid-cols-2 @3xl:grid-cols-3">
        {list.map((f, i) => (
          // The label may wrap and is capped at 45% of the row: a `shrink-0` label once
          // took the whole width when the model sent an over-long one, squeezing the
          // value into a one-character column that rendered as a vertical strip.
          <div key={i} className="flex min-w-0 items-baseline justify-between gap-4 border-b border-slate-200/80 py-3 @md:pr-6">
            <dt className="max-w-[45%] text-sm text-slate-500 [overflow-wrap:break-word]">{f.label}</dt>
            <dd className="min-w-0 flex-1 text-right text-sm font-medium text-slate-900 [overflow-wrap:break-word]">
              {isPlaceholder(f.value) ? (
                <span className="font-normal text-slate-500 italic">{f.value}</span>
              ) : (
                <Cited text={f.value} ns={c.ns} nums={c.nums} />
              )}
              <CiteChips citation={extra(f.citation, f.value)} ns={c.ns} nums={c.nums} />
            </dd>
          </div>
        ))}
      </dl>
    </Section>
  );
}

// ---------------------------------------------------------------------------
// Strengths vs weaknesses (top-level since the persona-aware schema).
// ---------------------------------------------------------------------------

export const topStrengths = (s: ReportSections) => (s.strengths ?? []).filter(hasText);
export const topWeaknesses = (s: ReportSections) => (s.weaknesses ?? []).filter(hasText);
export const hasStrengthsWeaknesses = (s: ReportSections) => nonEmpty(topStrengths(s)) || nonEmpty(topWeaknesses(s));

export function StrengthsWeaknesses({ s, c, n }: P) {
  const good = topStrengths(s);
  const bad = topWeaknesses(s);
  if (!nonEmpty(good) && !nonEmpty(bad)) return null;
  return (
    <Section c={c} id="strengths" n={n} title="Strengths and weaknesses" description="What works in their favour, and what to be wary of.">
      <div className={cx("grid gap-4", nonEmpty(good) && nonEmpty(bad) && "@2xl:grid-cols-2")}>
        {nonEmpty(good) && <Ledger kind="good" title="Strengths" items={good} c={c} />}
        {nonEmpty(bad) && <Ledger kind="bad" title="Weaknesses & red flags" items={bad} c={c} />}
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------------------
// Pricing
// ---------------------------------------------------------------------------

const plans = (s: ReportSections): PricingPlan[] => (s.pricing?.plans ?? []).filter((p) => hasText(p?.name) || hasText(p?.price));

export const hasPricing = (s: ReportSections) => hasText(s.pricing?.summary) || nonEmpty(plans(s));

export function Pricing({ s, c, n }: P) {
  const list = plans(s);
  if (!hasPricing(s)) return null;
  const grid = "@xl:grid-cols-[minmax(0,12rem)_minmax(0,10rem)_minmax(0,1fr)] @xl:gap-6";
  return (
    <Section c={c} id="pricing" n={n} title="Pricing" description="Published plans. Negotiated prices can differ.">
      <Prose text={s.pricing?.summary} c={c} />
      {nonEmpty(list) && (
        <div className={cx("overflow-hidden rounded-lg border border-slate-200/80", hasText(s.pricing?.summary) && "mt-6")}>
          <div aria-hidden className={cx("hidden border-b border-slate-200/80 bg-slate-50 px-4 py-2 text-slate-500 @xl:grid", grid, monoLabel)}>
            <span>Plan</span>
            <span>Price</span>
            <span>Notes</span>
          </div>
          <ul className="divide-y divide-slate-200/80">
            {list.map((p, i) => (
              <li key={i} className={cx("grid gap-1 px-4 py-3 @xl:items-baseline", grid)}>
                <p className="text-sm font-semibold text-slate-900">{p.name || "Plan"}</p>
                <p className="font-mono text-sm text-slate-900 tabular-nums">
                  {hasText(p.price) ? p.price : <span className="font-sans text-slate-500 italic">Price not public</span>}
                </p>
                <p className="min-w-0 text-sm leading-relaxed text-slate-600">
                  {hasText(p.notes) && <CitedOrMuted text={p.notes} c={c} />}
                  <CiteChips citation={extra(p.citation, p.notes)} ns={c.ns} nums={c.nums} />
                </p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Section>
  );
}

// ---------------------------------------------------------------------------
// Head to head: the subject vs the asker's own company.
// ---------------------------------------------------------------------------

const h2hRows = (s: ReportSections): HeadToHeadRow[] =>
  (s.head_to_head?.rows ?? []).filter((r) => hasText(r?.dimension) && (hasText(r?.subject) || hasText(r?.asker)));

export const hasHeadToHead = (s: ReportSections) =>
  hasText(s.head_to_head?.asker) && (hasText(s.head_to_head?.summary) || nonEmpty(h2hRows(s)) || hasText(s.head_to_head?.overlap));

const OVERLAP: Record<string, { title: string; tone: string; icon: "check" | "alert" | "scale" }> = {
  none: { title: "Not a direct competitor", tone: "border-emerald-200 bg-emerald-50/60 text-emerald-900", icon: "check" },
  low: { title: "Low overlap", tone: "border-emerald-200 bg-emerald-50/60 text-emerald-900", icon: "check" },
  medium: { title: "Partial overlap", tone: "border-amber-200 bg-amber-50/60 text-amber-950", icon: "scale" },
  high: { title: "High overlap: you compete directly", tone: "border-rose-200 bg-rose-50/60 text-rose-900", icon: "alert" },
};

function EdgeCell({ edge, subject, asker }: { edge?: string; subject: string; asker: string }) {
  const e = (edge ?? "").toLowerCase();
  if (e === "subject") return <span className="font-medium text-slate-900">{subject}</span>;
  if (e === "asker") return <span className="font-medium text-indigo-700">{asker}</span>;
  if (e === "even") return <span className="text-slate-500">Even</span>;
  return <span className="text-slate-500">—</span>;
}

export function HeadToHead({ s, c, n }: P) {
  const h = s.head_to_head;
  if (!h || !hasHeadToHead(s)) return null;
  const subject = s.company || "Them";
  const asker = h.asker!.trim();
  const rows = h2hRows(s);
  const overlap = OVERLAP[(h.overlap ?? "").toLowerCase().trim()];

  return (
    <Section c={c} id="head-to-head" n={n} title={`${subject} vs ${asker}`} description="Side by side on what matters for your decision.">
      {(overlap || hasText(h.summary)) && (
        <div className={cx("flex gap-3 rounded-lg border p-4", overlap?.tone ?? "border-slate-200 bg-slate-50 text-slate-900")}>
          {overlap && <Icon name={overlap.icon} className="mt-0.5 h-4 w-4 shrink-0" />}
          <div className="min-w-0">
            {overlap && <p className="text-sm font-semibold">{overlap.title}</p>}
            {hasText(h.summary) && (
              <p className={cx("text-sm leading-relaxed text-slate-700", overlap && "mt-1")}>
                <CitedOrMuted text={h.summary} c={c} />
              </p>
            )}
          </div>
        </div>
      )}

      {nonEmpty(rows) && (
        <>
          {/* Wide containers: a real table. */}
          <div className="mt-6 hidden overflow-hidden rounded-lg border border-slate-200/80 @2xl:block">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">
                {subject} compared with {asker}
              </caption>
              <thead className="border-b border-slate-200/80 bg-slate-50">
                <tr>
                  {["Dimension", subject, asker, "Edge"].map((th, i) => (
                    <th key={i} scope="col" className={cx(monoLabel, "px-4 py-2 font-medium text-slate-500")}>
                      {th}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200/80">
                {rows.map((r, i) => (
                  <tr key={i} className="align-top">
                    <th scope="row" className="w-[22%] px-4 py-3 font-medium text-slate-900">
                      {r.dimension}
                    </th>
                    <td className="px-4 py-3 leading-relaxed text-slate-700">
                      {hasText(r.subject) ? <CitedOrMuted text={r.subject} c={c} /> : "—"}
                    </td>
                    <td className="px-4 py-3 leading-relaxed text-slate-700">
                      {hasText(r.asker) ? <CitedOrMuted text={r.asker} c={c} /> : "—"}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <EdgeCell edge={r.edge} subject={subject} asker={asker} />
                      <CiteChips citation={extra(r.citation, r.subject, r.asker)} ns={c.ns} nums={c.nums} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Narrow containers: one block per dimension. */}
          <ul className="mt-6 divide-y divide-slate-200/80 border-y border-slate-200/80 @2xl:hidden">
            {rows.map((r, i) => (
              <li key={i} className="py-3">
                <div className="flex items-baseline justify-between gap-3">
                  <p className="text-sm font-semibold text-slate-900">{r.dimension}</p>
                  <p className="shrink-0 text-xs text-slate-500">
                    Edge: <EdgeCell edge={r.edge} subject={subject} asker={asker} />
                  </p>
                </div>
                <dl className="mt-2 grid gap-2 text-sm">
                  {[
                    [subject, r.subject],
                    [asker, r.asker],
                  ].map(([who, what]) => (
                    <div key={who} className="grid grid-cols-[6rem_minmax(0,1fr)] gap-3">
                      <dt className="truncate text-slate-500">{who}</dt>
                      <dd className="min-w-0 leading-relaxed text-slate-700">
                        {hasText(what) ? <CitedOrMuted text={what} c={c} /> : "—"}
                      </dd>
                    </div>
                  ))}
                </dl>
                <CiteChips citation={extra(r.citation, r.subject, r.asker)} ns={c.ns} nums={c.nums} />
              </li>
            ))}
          </ul>
        </>
      )}
    </Section>
  );
}

// ---------------------------------------------------------------------------
// Your questions: answers to the extra asks in the question.
// ---------------------------------------------------------------------------

const answers = (s: ReportSections) => (s.custom_answers ?? []).filter((a) => hasText(a?.question) && hasText(a?.answer));

export const hasCustomAnswers = (s: ReportSections) => nonEmpty(answers(s));

export function CustomAnswers({ s, c, n }: P) {
  const list = answers(s);
  if (!nonEmpty(list)) return null;
  return (
    <Section c={c} id="answers" n={n} title="Your questions" description="Direct answers to what you asked.">
      <dl className="divide-y divide-slate-200/80 border-y border-slate-200/80">
        {list.map((a, i) => (
          <div key={i} className="py-4">
            <dt className="text-sm font-semibold text-slate-900">{a.question}</dt>
            <dd className="mt-1 max-w-[72ch] text-sm leading-relaxed text-slate-700">
              <CitedOrMuted text={a.answer!} c={c} />
              <CiteChips citation={extra(a.citation, a.answer)} ns={c.ns} nums={c.nums} />
            </dd>
          </div>
        ))}
      </dl>
    </Section>
  );
}
