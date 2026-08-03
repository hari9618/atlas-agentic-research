import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Citation, DebateTurn, Finding } from "@/lib/api";

// A paper-formatted version of the run. Hidden on screen (`print-only`), rendered
// only by the browser's print / "Save as PDF" dialog, so the dark war-room UI never
// bleeds into the document. Colours are set explicitly (the print stylesheet forces
// exact colour rendering) to produce a clean, structured investor brief.

const INK = "text-[#1e2230]";
const ACCENT = "text-[#3730a3]"; // indigo — structural accent

// Rich markdown styling so the synthesized brief keeps a clear visual hierarchy.
const MD: Components = {
  h2: ({ children }) => (
    <h2
      className={`mt-5 mb-2 border-b-2 border-[#c7d2fe] pb-1 text-[13px] font-bold uppercase tracking-wider ${ACCENT}`}
    >
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className={`mt-3 mb-1 text-[12.5px] font-bold ${INK}`}>{children}</h3>
  ),
  p: ({ children }) => (
    <p className="mb-2 text-[11px] leading-[1.55] text-[#333743]">{children}</p>
  ),
  ul: ({ children }) => (
    <ul className="mb-2 ml-1 list-disc space-y-1 pl-4 text-[11px] text-[#333743]">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-2 ml-1 list-decimal space-y-1 pl-4 text-[11px] text-[#333743]">{children}</ol>
  ),
  li: ({ children }) => <li className="leading-[1.5]">{children}</li>,
  strong: ({ children }) => <strong className={`font-semibold ${INK}`}>{children}</strong>,
  em: ({ children }) => <em className="text-[#4b5563]">{children}</em>,
  a: ({ children }) => <span className={ACCENT}>{children}</span>,
};

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex-1 rounded-md border border-[#e2e5ee] bg-[#f7f8fc] px-3 py-2">
      <div className="text-[8.5px] font-semibold uppercase tracking-[0.15em] text-[#8a90a2]">
        {label}
      </div>
      <div className={`text-[15px] font-bold leading-tight ${INK}`}>{value}</div>
    </div>
  );
}

function SectionTitle({ n, title }: { n: string; title: string }) {
  return (
    <div className="mb-2 flex items-center gap-2 border-b-2 border-[#c7d2fe] pb-1">
      <span
        className="flex h-[16px] w-[16px] items-center justify-center rounded-[3px] bg-[#3730a3] text-[9px] font-bold text-white"
      >
        {n}
      </span>
      <h2 className={`text-[12px] font-bold uppercase tracking-wider ${ACCENT}`}>{title}</h2>
    </div>
  );
}

// Colour a debate role: bull green, bear red, judge slate.
function roleStyle(role: string): { label: string; box: string; tag: string } {
  const r = role.toLowerCase();
  if (r.includes("bull")) return { label: "BULL", box: "border-[#bbe7cf] bg-[#f0faf4]", tag: "text-[#1a7f4b]" };
  if (r.includes("bear")) return { label: "BEAR", box: "border-[#f2c7c1] bg-[#fdf3f1]", tag: "text-[#b23b2e]" };
  return { label: role.toUpperCase(), box: "border-[#dfe2ec] bg-[#f7f8fc]", tag: "text-[#4b5563]" };
}

export function PrintableReport({
  query,
  report,
  confidence,
  findings,
  uncertainties,
  citations,
  debate,
}: {
  query: string;
  report: string;
  confidence: number | null;
  findings: Finding[];
  uncertainties: string[];
  citations: Citation[];
  debate: DebateTurn[];
}) {
  const pct = confidence === null ? null : Math.round(confidence * 100);
  const confColor =
    pct === null ? "#6b7280" : pct >= 66 ? "#1a7f4b" : pct >= 40 ? "#b8860b" : "#b23b2e";

  return (
    <div className="print-only bg-white text-[#1e2230]">
      {/* ---------- Masthead ---------- */}
      <header className="flex items-start justify-between gap-4 border-b-[3px] border-[#3730a3] pb-3">
        <div>
          <p className="text-[9px] font-bold uppercase tracking-[0.22em] text-[#8a90a2]">
            Atlas · Autonomous Due-Diligence Desk
          </p>
          <h1 className={`mt-1 max-w-[85%] text-[19px] font-extrabold leading-[1.15] ${INK}`}>
            {query || "Research Brief"}
          </h1>
          <p className="mt-1 text-[9.5px] text-[#8a90a2]">
            Evidence-grounded multi-agent research brief
          </p>
        </div>
        {pct !== null && (
          <div
            className="flex w-[92px] flex-col items-center rounded-lg border-2 px-2 py-2 text-center"
            style={{ borderColor: confColor }}
          >
            <span className="text-[8px] font-bold uppercase tracking-wider text-[#8a90a2]">
              Confidence
            </span>
            <span className="text-[26px] font-extrabold leading-none" style={{ color: confColor }}>
              {pct}
            </span>
            <span className="text-[8px] text-[#8a90a2]">out of 100</span>
          </div>
        )}
      </header>

      {/* ---------- Metrics strip ---------- */}
      <div className="mt-3 flex gap-2">
        <Stat label="Findings" value={String(findings?.length ?? 0)} />
        <Stat label="Sources" value={String(citations?.length ?? 0)} />
        <Stat label="Open questions" value={String(uncertainties?.length ?? 0)} />
        <Stat label="Debate turns" value={String(debate?.length ?? 0)} />
      </div>

      {/* ---------- The synthesized brief ---------- */}
      <section className="mt-4">
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD}>
          {report}
        </ReactMarkdown>
      </section>

      {/* ---------- What we're not sure about ---------- */}
      {uncertainties?.length > 0 && (
        <section className="mt-4 break-inside-avoid rounded-md border border-[#f0d9a8] bg-[#fdf8ee] p-3">
          <h2 className="mb-1 text-[11px] font-bold uppercase tracking-wider text-[#9a6a12]">
            What we&apos;re not sure about
          </h2>
          <ul className="ml-1 list-disc space-y-1 pl-4 text-[11px] text-[#6b5320]">
            {uncertainties.map((u, i) => (
              <li key={i} className="leading-[1.5]">{u}</li>
            ))}
          </ul>
        </section>
      )}

      {/* ---------- Findings ---------- */}
      {findings?.length > 0 && (
        <section className="mt-4">
          <SectionTitle n="1" title={`Evidence & Findings (${findings.length})`} />
          <div className="space-y-1.5">
            {findings.map((f, i) => (
              <div
                key={i}
                className="break-inside-avoid rounded-md border border-[#e2e5ee] bg-[#fafbff] px-3 py-2"
              >
                <div className="mb-0.5 flex items-center gap-2">
                  <span className="rounded-[3px] bg-[#e7e9f7] px-1.5 py-[1px] text-[8.5px] font-bold uppercase tracking-wide text-[#3730a3]">
                    {f.agent}
                  </span>
                  <span className="text-[8.5px] text-[#8a90a2]">
                    confidence {Math.round(f.confidence * 100)}%
                  </span>
                </div>
                <div className="text-[11px] leading-[1.5] text-[#333743]">{f.claim}</div>
                {f.citation && f.citation !== "n/a" && (
                  <div className="mt-0.5 text-[9px] italic text-[#8a90a2]">↳ {f.citation}</div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ---------- Bull vs Bear ---------- */}
      {debate?.length > 0 && (
        <section className="mt-4">
          <SectionTitle n="2" title="Bull vs Bear Debate" />
          <div className="space-y-1.5">
            {debate.map((d, i) => {
              const s = roleStyle(d.role);
              return (
                <div key={i} className={`break-inside-avoid rounded-md border ${s.box} px-3 py-2`}>
                  <div className="mb-0.5 flex items-center gap-2">
                    <span className={`text-[9px] font-bold uppercase tracking-wider ${s.tag}`}>
                      {s.label}
                    </span>
                    {d.leaning && (
                      <span className="text-[8.5px] text-[#8a90a2]">leaning: {d.leaning}</span>
                    )}
                  </div>
                  <div className="text-[11px] leading-[1.5] text-[#333743]">{d.text}</div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ---------- Sources ---------- */}
      {citations?.length > 0 && (
        <section className="mt-4 break-inside-avoid">
          <SectionTitle n="3" title="Sources" />
          <ol className="ml-1 list-decimal space-y-0.5 pl-4 text-[9.5px] text-[#4b5563]">
            {citations.map((c, i) => (
              <li key={i} className="leading-[1.45]">{c.citation}</li>
            ))}
          </ol>
        </section>
      )}

      {/* ---------- Footer ---------- */}
      <footer className="mt-6 border-t border-[#e2e5ee] pt-2 text-[9px] leading-[1.5] text-[#8a90a2]">
        Generated by <span className="font-semibold text-[#3730a3]">Atlas</span> — a multi-agent
        research system. Every claim is grounded in the cited evidence above; the confidence score
        is capped by citation coverage, and web / derived sources are marked as such.
      </footer>
    </div>
  );
}
