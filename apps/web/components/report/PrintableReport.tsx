"use client";

import { createContext, useContext } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ResearchPayload } from "@/lib/api";
import {
  chipLabel,
  type CitationNumbers,
  citationKey,
  hasText,
  linkCitationsInMarkdown,
  nonEmpty,
  splitCitations,
} from "@/lib/citations";
import { briefLine } from "@/lib/persona";
import { reportCitationNumbers } from "@/lib/report-citations";
import { titleCase } from "@/components/ui/styles";
import { confidenceLabel } from "./ConfidenceMeter";

// Paper version of the brief. Hidden on screen (`print-only`) and rendered only by the
// browser's print / "Save as PDF" dialog. Colours are explicit hex values (print forces
// exact colour) so the PDF looks the same in every browser.

const TONE: Record<string, { fg: string; bg: string }> = {
  good: { fg: "#047857", bg: "#ecfdf5" },
  mid: { fg: "#b45309", bg: "#fffbeb" },
  bad: { fg: "#be123c", bg: "#fff1f2" },
  muted: { fg: "#475569", bg: "#f1f5f9" },
};

function tone(v?: string) {
  const k = (v ?? "").toLowerCase();
  if (["positive", "low", "approved"].includes(k)) return TONE.good;
  if (["neutral", "mixed", "medium"].includes(k)) return TONE.mid;
  if (["cautious", "negative", "high"].includes(k)) return TONE.bad;
  return TONE.muted;
}

function Tag({ value, suffix = "" }: { value?: string; suffix?: string }) {
  if (!value) return null;
  const t = tone(value);
  return (
    <span
      className="inline-block rounded-full px-2 py-[1px] text-[8.5pt] font-semibold whitespace-nowrap"
      style={{ color: t.fg, background: t.bg }}
    >
      {titleCase(value)}
      {suffix}
    </span>
  );
}

// The report's citation numbering, read by every source tag in the paper version.
const Nums = createContext<CitationNumbers | undefined>(undefined);

/** Citation labels become small grey source tags, e.g. "[Site 3]". */
function P({ text }: { text?: string }) {
  const nums = useContext(Nums);
  if (!text) return null;
  return (
    <>
      {splitCitations(text).map((s, i) =>
        s.type === "text" ? (
          <span key={i}>{s.text}</span>
        ) : (
          <span key={i} className="text-[7.5pt] whitespace-nowrap text-[#64748b]">
            {" "}[{chipLabel(s.key, nums)}]
          </span>
        ),
      )}
    </>
  );
}

function H2({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mt-5 mb-2 border-b-2 border-[#c7d2fe] pb-1 text-[10.5pt] font-bold tracking-wider text-[#3730a3] uppercase">
      {children}
    </h2>
  );
}

function Bullets({ items }: { items?: string[] }) {
  const list = (items ?? []).filter(hasText);
  if (!list.length) return null;
  return (
    <ul className="ml-4 list-disc space-y-1 text-[9.5pt] leading-[1.5] text-[#334155]">
      {list.map((x, i) => (
        <li key={i}>
          <P text={x} />
        </li>
      ))}
    </ul>
  );
}

function Para({ text }: { text?: string }) {
  if (!hasText(text)) return null;
  return (
    <p className="mb-2 text-[9.5pt] leading-[1.55] text-[#334155]">
      <P text={text} />
    </p>
  );
}

const MD: Components = {
  h1: ({ children }) => <H2>{children}</H2>,
  h2: ({ children }) => <H2>{children}</H2>,
  h3: ({ children }) => <h3 className="mt-3 mb-1 text-[10pt] font-bold text-[#0f172a]">{children}</h3>,
  p: ({ children }) => <p className="mb-2 text-[9.5pt] leading-[1.55] text-[#334155]">{children}</p>,
  ul: ({ children }) => <ul className="mb-2 ml-4 list-disc space-y-1 text-[9.5pt] text-[#334155]">{children}</ul>,
  ol: ({ children }) => <ol className="mb-2 ml-4 list-decimal space-y-1 text-[9.5pt] text-[#334155]">{children}</ol>,
  strong: ({ children }) => <strong className="font-semibold text-[#0f172a]">{children}</strong>,
  a: ({ children }) => <span className="text-[7.5pt] text-[#64748b]">[{children}]</span>,
};

const th = "border-b border-[#cbd5e1] py-1 pr-3 text-left text-[8pt] font-semibold text-[#64748b]";
const td = "border-b border-[#e2e8f0] py-2 pr-3 align-top text-[9pt] leading-[1.45] text-[#334155]";

export function PrintableReport({
  query,
  payload,
  revision,
  status,
}: {
  query: string;
  payload: Partial<ResearchPayload> | null;
  revision?: number;
  status?: string;
}) {
  if (!payload || !(payload.report_sections || hasText(payload.report))) return null;
  const s = payload.report_sections ?? null;
  const conf = payload.confidence ?? s?.confidence ?? null;
  const pct = conf == null ? null : Math.round(Math.max(0, Math.min(1, conf)) * 100);
  const confInfo = conf == null ? null : confidenceLabel(conf);
  const uncertainties = s?.uncertainties?.length ? s.uncertainties : payload.uncertainties ?? [];
  const nums = reportCitationNumbers(payload);
  const rank = (c: string) => nums.get(citationKey(c)) ?? Number.MAX_SAFE_INTEGER;
  const seen = new Set<string>();
  const sources = (payload.citations ?? []).filter((x) => {
    const k = citationKey(x.citation ?? "");
    if (!x.citation || seen.has(k)) return false;
    seen.add(k);
    return true;
  }).sort((a, b) => rank(a.citation) - rank(b.citation));
  const date = new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });
  const who = briefLine(s?.brief);
  const strengths = (s?.strengths ?? []).filter(hasText);
  const weaknesses = (s?.weaknesses ?? []).filter(hasText);
  const mirrored = strengths.length > 0 || weaknesses.length > 0;
  const facts = (s?.snapshot ?? []).filter((f) => hasText(f?.label) && hasText(f?.value));
  const plans = (s?.pricing?.plans ?? []).filter((x) => hasText(x?.name) || hasText(x?.price));
  const h2h = s?.head_to_head;
  const h2hRows = (h2h?.rows ?? []).filter((r) => hasText(r?.dimension));
  const answers = (s?.custom_answers ?? []).filter((a) => hasText(a?.question) && hasText(a?.answer));

  return (
    <Nums.Provider value={nums}>
    <div className="print-only bg-surface text-[#0f172a]">
      {/* Masthead */}
      <header className="border-b-[3px] border-[#3730a3] pb-3">
        <div className="flex items-center justify-between text-[8pt] font-semibold tracking-label text-[#64748b] uppercase">
          <span>Atlas · Due-diligence brief</span>
          <span>{date}</span>
        </div>
        <div className="mt-2 flex items-start justify-between gap-6">
          <div className="min-w-0">
            <h1 className="font-display text-[26pt] leading-tight font-normal">
              {s?.company || payload.target || "Research brief"}
            </h1>
            {(who || hasText(s?.brief?.goal)) && (
              <p className="mt-1 text-[9pt] text-[#475569]">
                {who}
                {who && hasText(s?.brief?.goal) && " · "}
                {s?.brief?.goal}
              </p>
            )}
            {s?.headline && (
              <p className="mt-1 text-[11pt] leading-[1.45] text-[#334155]">
                <P text={s.headline} />
              </p>
            )}
            <div className="mt-2 flex flex-wrap items-center gap-2 text-[8.5pt] text-[#64748b]">
              {s?.stance && <Tag value={s.stance} suffix=" outlook" />}
              {revision != null && <span>{revision === 0 ? "First draft" : `Revision ${revision}`}</span>}
              {status && <span>· {status}</span>}
            </div>
          </div>
          {pct != null && confInfo && (
            <div className="w-[96px] shrink-0 rounded-lg border-2 border-[#c7d2fe] px-2 py-2 text-center">
              <div className="text-[7pt] font-bold tracking-wider text-[#64748b] uppercase">Confidence</div>
              <div className="text-[22pt] leading-none font-extrabold text-[#3730a3]">{pct}</div>
              <div className="mt-0.5 text-[7pt] text-[#64748b]">out of 100</div>
              <div className="mt-0.5 text-[7pt] font-semibold text-[#334155]">{confInfo.label}</div>
            </div>
          )}
        </div>
        {query && (
          <p className="mt-2 text-[8.5pt] text-[#64748b]">
            Question: <span className="text-[#334155]">{query}</span>
          </p>
        )}
      </header>

      {s ? (
        <>
          {(hasText(s.verdict?.recommendation) || hasText(s.verdict?.answer)) && (
            <section className="avoid-break mt-4 border-l-[3px] border-[#3730a3] pl-3">
              <h2 className="text-[8.5pt] font-bold tracking-wider text-[#3730a3] uppercase">Verdict</h2>
              {hasText(s.verdict?.recommendation) && (
                <p className="mt-1 text-[12pt] leading-snug font-semibold text-[#0f172a]">
                  <P text={s.verdict?.recommendation} />
                </p>
              )}
              <Para text={s.verdict?.answer} />
            </section>
          )}

          {facts.length > 0 && (
            <section className="avoid-break">
              <H2>Snapshot</H2>
              <div className="grid grid-cols-3 gap-x-4">
                {facts.map((f, i) => (
                  <div key={i} className="flex justify-between gap-2 border-b border-[#e2e8f0] py-1 text-[9pt]">
                    <span className="text-[#64748b]">{f.label}</span>
                    <span className="text-right font-semibold text-[#0f172a]">
                      <P text={f.value} />
                      {f.citation && <P text={` ${f.citation}`} />}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {nonEmpty(s.executive_summary) && (
            <section className="avoid-break mt-4 rounded-md border border-[#c7d2fe] bg-[#eef2ff] p-3">
              <h2 className="mb-2 text-[10.5pt] font-bold tracking-wider text-[#3730a3] uppercase">
                Executive summary
              </h2>
              <Bullets items={s.executive_summary} />
            </section>
          )}

          {h2h && hasText(h2h.asker) && (hasText(h2h.summary) || h2hRows.length > 0) && (
            <section>
              <H2>
                {s.company || "Them"} vs {h2h.asker}
              </H2>
              {hasText(h2h.overlap) && (
                <p className="mb-1 text-[9pt] font-semibold text-[#0f172a]">
                  {h2h.overlap?.toLowerCase() === "none" ? "Not a direct competitor" : `${titleCase(h2h.overlap)} overlap`}
                </p>
              )}
              <Para text={h2h.summary} />
              {h2hRows.length > 0 && (
                <table className="w-full border-collapse">
                  <thead>
                    <tr>
                      <th className={th}>Dimension</th>
                      <th className={th}>{s.company || "Them"}</th>
                      <th className={th}>{h2h.asker}</th>
                      <th className={th}>Edge</th>
                    </tr>
                  </thead>
                  <tbody>
                    {h2hRows.map((r, i) => (
                      <tr key={i} className="avoid-break">
                        <td className={`${td} font-semibold text-[#0f172a]`}>{r.dimension}</td>
                        <td className={td}><P text={r.subject} /></td>
                        <td className={td}><P text={r.asker} /></td>
                        <td className={td}>
                          {r.edge === "subject" ? s.company : r.edge === "asker" ? h2h.asker : r.edge === "even" ? "Even" : ""}
                          {r.citation && <P text={` ${r.citation}`} />}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>
          )}

          {answers.length > 0 && (
            <section>
              <H2>Your questions</H2>
              {answers.map((a, i) => (
                <div key={i} className="avoid-break mb-2">
                  <p className="text-[9.5pt] font-semibold text-[#0f172a]">{a.question}</p>
                  <Para text={a.citation ? `${a.answer} ${a.citation}` : a.answer} />
                </div>
              ))}
            </section>
          )}

          {s.company_overview && (
            <section>
              <H2>Company overview</H2>
              {hasText(s.company_overview.what_they_do) && (
                <Para text={`What they do: ${s.company_overview.what_they_do}`} />
              )}
              {hasText(s.company_overview.business_model) && (
                <Para text={`How they make money: ${s.company_overview.business_model}`} />
              )}
              {nonEmpty(s.company_overview.products) && (
                <Para text={`Products & services: ${s.company_overview.products.join(", ")}`} />
              )}
              {hasText(s.company_overview.customers) && <Para text={`Customers: ${s.company_overview.customers}`} />}
            </section>
          )}

          {(hasText(s.pricing?.summary) || plans.length > 0) && (
            <section>
              <H2>Pricing</H2>
              <Para text={s.pricing?.summary} />
              {plans.length > 0 && (
                <table className="w-full border-collapse">
                  <thead>
                    <tr>
                      <th className={th}>Plan</th>
                      <th className={th}>Price</th>
                      <th className={th}>Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {plans.map((x, i) => (
                      <tr key={i} className="avoid-break">
                        <td className={`${td} font-semibold text-[#0f172a]`}>{x.name}</td>
                        <td className={td}>{hasText(x.price) ? x.price : "Price not public"}</td>
                        <td className={td}><P text={x.citation ? `${x.notes ?? ""} ${x.citation}` : x.notes} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>
          )}

          {s.financials && (nonEmpty(s.financials.metrics) || hasText(s.financials.summary)) && (
            <section>
              <H2>Financials</H2>
              {nonEmpty(s.financials.metrics) && (
                <div className="avoid-break mb-2 grid grid-cols-4 gap-2">
                  {s.financials.metrics.map((m, i) => (
                    <div key={i} className="rounded-md border border-[#e2e8f0] bg-[#f8fafc] px-2 py-2">
                      <div className="text-[7.5pt] text-[#64748b]">{m.label}</div>
                      <div className="text-[13pt] font-bold">{m.value}</div>
                      <div className="text-[7.5pt] text-[#334155]">
                        {m.change}
                        {m.citation && <P text={` ${m.citation}`} />}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <Para text={s.financials.summary} />
            </section>
          )}

          {mirrored && (
            <section>
              <H2>Strengths and weaknesses</H2>
              <div className="avoid-break grid grid-cols-2 gap-3">
                {strengths.length > 0 && (
                  <div>
                    <h3 className="mb-1 text-[9pt] font-bold text-[#047857]">Strengths</h3>
                    <Bullets items={strengths} />
                  </div>
                )}
                {weaknesses.length > 0 && (
                  <div>
                    <h3 className="mb-1 text-[9pt] font-bold text-[#be123c]">Weaknesses &amp; red flags</h3>
                    <Bullets items={weaknesses} />
                  </div>
                )}
              </div>
            </section>
          )}

          {s.market_position && (hasText(s.market_position.summary) || !mirrored) && (
            <section>
              <H2>Market position</H2>
              <Para text={s.market_position.summary} />
              <div className="avoid-break grid grid-cols-2 gap-3">
                {!mirrored && nonEmpty(s.market_position.strengths) && (
                  <div>
                    <h3 className="mb-1 text-[9pt] font-bold text-[#047857]">Strengths</h3>
                    <Bullets items={s.market_position.strengths} />
                  </div>
                )}
                {!mirrored && nonEmpty(s.market_position.weaknesses) && (
                  <div>
                    <h3 className="mb-1 text-[9pt] font-bold text-[#be123c]">Weaknesses</h3>
                    <Bullets items={s.market_position.weaknesses} />
                  </div>
                )}
              </div>
            </section>
          )}

          {/* Long sections flow across pages; only rows/cards are kept whole. Keeping a
              whole section together pushes it to the next page and leaves a blank gap. */}
          {nonEmpty(s.competitors) && (
            <section>
              <H2>Competitors</H2>
              <table className="w-full border-collapse">
                <thead>
                  <tr>
                    <th className={th}>Company</th>
                    <th className={th}>How they compare</th>
                    <th className={th}>Threat</th>
                  </tr>
                </thead>
                <tbody>
                  {s.competitors.map((r, i) => (
                    <tr key={i} className="avoid-break">
                      <td className={`${td} font-semibold text-[#0f172a]`}>{r.name}</td>
                      <td className={td}><P text={r.comparison} /></td>
                      <td className={td}><Tag value={r.threat} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          {nonEmpty(s.recent_developments) && (
            <section>
              <H2>Recent developments</H2>
              <ul className="space-y-2">
                {s.recent_developments.map((d, i) => (
                  <li key={i} className="avoid-break text-[9.5pt] leading-[1.5] text-[#334155]">
                    <span className="font-semibold text-[#0f172a]">
                      {d.date ? `${d.date} — ` : ""}
                      {d.title}
                    </span>{" "}
                    {d.sentiment && <Tag value={d.sentiment} />}
                    <br />
                    <P text={d.detail} />
                  </li>
                ))}
              </ul>
            </section>
          )}

          {s.sentiment &&
            (hasText(s.sentiment.summary) ||
              hasText(s.sentiment.overall) ||
              nonEmpty(s.sentiment.praise) ||
              nonEmpty(s.sentiment.complaints)) && (
            <section>
              <H2>Overall sentiment</H2>
              {s.sentiment.overall && (
                <p className="mb-1">
                  <Tag value={s.sentiment.overall} />
                </p>
              )}
              <Para text={s.sentiment.summary} />
              <div className="avoid-break grid grid-cols-2 gap-3">
                {nonEmpty(s.sentiment.praise) && (
                  <div>
                    <h3 className="mb-1 text-[9pt] font-bold text-[#047857]">What customers praise</h3>
                    <Bullets items={s.sentiment.praise} />
                  </div>
                )}
                {nonEmpty(s.sentiment.complaints) && (
                  <div>
                    <h3 className="mb-1 text-[9pt] font-bold text-[#be123c]">What customers complain about</h3>
                    <Bullets items={s.sentiment.complaints} />
                  </div>
                )}
              </div>
            </section>
          )}

          {nonEmpty(s.risks) && (
            <section>
              <H2>Key risks</H2>
              <table className="w-full border-collapse">
                <thead>
                  <tr>
                    <th className={th}>Risk</th>
                    <th className={th}>Severity</th>
                    <th className={th}>Why it matters</th>
                  </tr>
                </thead>
                <tbody>
                  {s.risks.map((r, i) => (
                    <tr key={i} className="avoid-break">
                      <td className={`${td} font-semibold text-[#0f172a]`}>{r.title}</td>
                      <td className={td}><Tag value={r.severity} /></td>
                      <td className={td}><P text={r.detail} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          {(nonEmpty(s.bull_case) || nonEmpty(s.bear_case)) && (
            <section>
              <H2>Bull case vs bear case</H2>
              <div className="avoid-break grid grid-cols-2 gap-3">
                <div className="rounded-md border border-[#a7f3d0] bg-[#ecfdf5] p-2">
                  <h3 className="mb-1 text-[9pt] font-bold text-[#047857]">Bull case</h3>
                  <Bullets items={s.bull_case} />
                </div>
                <div className="rounded-md border border-[#fecdd3] bg-[#fff1f2] p-2">
                  <h3 className="mb-1 text-[9pt] font-bold text-[#be123c]">Bear case</h3>
                  <Bullets items={s.bear_case} />
                </div>
              </div>
            </section>
          )}

          {s.outlook && (hasText(s.outlook.summary) || nonEmpty(s.outlook.watch_items)) && (
            <section>
              <H2>Outlook</H2>
              <Para text={s.outlook.summary} />
              {nonEmpty(s.outlook.watch_items) && (
                <>
                  <h3 className="mb-1 text-[9pt] font-bold text-[#0f172a]">What to watch</h3>
                  <Bullets items={s.outlook.watch_items} />
                </>
              )}
            </section>
          )}

          {hasText(s.bottom_line) && (
            <section className="avoid-break mt-5 rounded-md bg-[#3730a3] p-3 text-white">
              <h2 className="text-[8.5pt] font-bold tracking-wider text-[#c7d2fe] uppercase">Bottom line</h2>
              <p className="mt-1 text-[10.5pt] leading-[1.5] font-medium [&_span]:text-[#c7d2fe]">
                <P text={s.bottom_line} />
              </p>
            </section>
          )}
        </>
      ) : (
        <section className="mt-3">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD}>
            {linkCitationsInMarkdown(payload.report ?? "", "print", nums)}
          </ReactMarkdown>
        </section>
      )}

      {nonEmpty(uncertainties) && (
        <section className="avoid-break mt-4 rounded-md border border-[#fde68a] bg-[#fffbeb] p-3">
          <h2 className="mb-1 text-[10pt] font-bold tracking-wider text-[#92400e] uppercase">
            What we&apos;re not sure about
          </h2>
          <Bullets items={uncertainties} />
        </section>
      )}

      {sources.length > 0 && (
        <section className="mt-4">
          <H2>Sources</H2>
          <ol className="space-y-0.5 text-[8.5pt] leading-[1.45] text-[#475569]">
            {sources.map((x, i) => (
              <li key={i}>
                <span className="font-semibold text-[#334155]">[{chipLabel(citationKey(x.citation), nums)}]</span>{" "}
                {x.citation.replace(/\s*\[(web|atlas-derived)\]/g, " (web)")}
              </li>
            ))}
          </ol>
        </section>
      )}

      <footer className="mt-6 border-t border-[#e2e8f0] pt-2 text-[7.5pt] leading-[1.5] text-[#64748b]">
        Generated by <span className="font-semibold text-[#3730a3]">Atlas</span>, an AI due-diligence
        analyst. Every claim is tied to a cited source; confidence is capped by how well the evidence
        covers the claims. This is research support, not investment advice.
      </footer>
    </div>
    </Nums.Provider>
  );
}
