import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { type CitationNumbers, linkCitationsInMarkdown } from "@/lib/citations";
import { card, cx } from "@/components/ui/styles";

// Fallback for runs where the backend only returned the markdown `report`
// (report_sections missing). Citations are rewritten into source-chip links.
const MD: Components = {
  h1: ({ children }) => <h3 className="mt-6 mb-3 text-xl font-semibold text-slate-900 first:mt-0">{children}</h3>,
  h2: ({ children }) => (
    <h3 className="mt-6 mb-2 border-b border-slate-200 pb-2 text-lg font-semibold text-slate-900 first:mt-0">
      {children}
    </h3>
  ),
  h3: ({ children }) => <h4 className="mt-4 mb-2 font-semibold text-slate-900">{children}</h4>,
  p: ({ children }) => <p className="mb-3 text-base leading-7 text-slate-700">{children}</p>,
  ul: ({ children }) => <ul className="mb-3 list-disc space-y-2 pl-5 text-sm text-slate-700">{children}</ul>,
  ol: ({ children }) => <ol className="mb-3 list-decimal space-y-2 pl-5 text-sm text-slate-700">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-slate-900">{children}</strong>,
  a: ({ href, title, children }) =>
    href?.startsWith("#") ? (
      <a
        href={href}
        title={title}
        className="mx-0.5 inline-flex items-center rounded border border-slate-200 bg-slate-50 px-2 py-px align-middle font-mono text-2xs leading-4 font-medium whitespace-nowrap text-slate-500 no-underline hover:border-indigo-300 hover:text-indigo-700"
      >
        {children}
      </a>
    ) : (
      <a href={href} target="_blank" rel="noreferrer" className="text-indigo-700 underline">
        {children}
      </a>
    ),
  table: ({ children }) => (
    <div className="mb-4 overflow-x-auto">
      <table className="w-full text-left text-sm">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="border-b border-slate-200 py-2 pr-3 text-xs font-medium text-slate-500">{children}</th>,
  td: ({ children }) => <td className="border-b border-slate-100 py-2 pr-3 align-top text-slate-700">{children}</td>,
  code: ({ children }) => <code className="rounded bg-slate-100 px-1 py-0.5 text-xs text-slate-800">{children}</code>,
};

export function MarkdownReport({
  report,
  ns,
  nums,
  className,
  bare = false,
}: {
  report: string;
  ns: string;
  /** The report's citation numbering (chips show only the source kind without it). */
  nums?: CitationNumbers;
  className?: string;
  /** Render without the card shell (when embedded inside the report document). */
  bare?: boolean;
}) {
  if (!report?.trim()) return null;
  return (
    <article className={cx(!bare && card, !bare && "p-5 sm:p-6", "max-w-[76ch]", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD}>
        {linkCitationsInMarkdown(report, ns, nums)}
      </ReactMarkdown>
    </article>
  );
}
