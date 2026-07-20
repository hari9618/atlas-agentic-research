"use client";

/** Export the finished brief as a PDF via the browser's print dialog ("Save as PDF").
 *  The paper layout lives in <PrintableReport>, which is only visible while printing. */
export function ExportButton({ ready }: { ready: boolean }) {
  return (
    <button
      onClick={() => window.print()}
      disabled={!ready}
      title={ready ? "Save this brief as a PDF" : "Run an analysis first"}
      className="rounded-md border border-slate-700 px-2.5 py-1 text-xs font-medium text-slate-300 transition hover:border-sky-500 hover:text-sky-300 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-slate-700 disabled:hover:text-slate-300"
    >
      Download PDF
    </button>
  );
}
