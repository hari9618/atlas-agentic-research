import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Citation } from "@/lib/api";

const MD: Components = {
  h2: ({ children }) => (
    <h2 className="mt-5 mb-2 border-b border-slate-800 pb-1 text-lg font-semibold text-sky-200">
      {children}
    </h2>
  ),
  h3: ({ children }) => <h3 className="mt-3 mb-1 font-semibold text-slate-100">{children}</h3>,
  p: ({ children }) => <p className="mb-3 text-sm leading-relaxed text-slate-300">{children}</p>,
  ul: ({ children }) => <ul className="mb-3 list-disc space-y-1 pl-5 text-sm text-slate-300">{children}</ul>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-slate-100">{children}</strong>,
  code: ({ children }) => (
    <code className="rounded bg-slate-800 px-1 py-0.5 text-[12px] text-amber-200">{children}</code>
  ),
};

export function ReportView({
  report,
  uncertainties,
  citations,
}: {
  report: string;
  uncertainties: string[];
  citations: Citation[];
}) {
  if (!report) {
    return <p className="text-sm text-slate-500">The synthesized brief will render here…</p>;
  }
  return (
    <div>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD}>
        {report}
      </ReactMarkdown>

      {uncertainties?.length > 0 && (
        <div className="mt-4 rounded-lg border border-amber-700/40 bg-amber-500/5 p-3">
          <h3 className="mb-1 text-sm font-semibold text-amber-300">What we&apos;re not sure about</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm text-amber-100/80">
            {uncertainties.map((u, i) => (
              <li key={i}>{u}</li>
            ))}
          </ul>
        </div>
      )}

      {citations?.length > 0 && (
        <div className="mt-4">
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-widest text-slate-500">
            Sources
          </h3>
          <ul className="space-y-1 text-xs text-slate-400">
            {citations.map((c, i) => (
              <li key={i}>📎 {c.citation}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
