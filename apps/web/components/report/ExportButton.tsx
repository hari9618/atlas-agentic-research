"use client";

import { Icon } from "@/components/ui/Icon";
import { btn } from "@/components/ui/styles";

/** Save the brief as a PDF via the browser's print dialog ("Save as PDF"). The paper
 *  layout lives in <PrintableReport>, which is only visible while printing. */
export function ExportButton({ ready }: { ready: boolean }) {
  return (
    <button
      type="button"
      onClick={() => window.print()}
      disabled={!ready}
      title={ready ? "Save this brief as a PDF" : "Run an analysis first"}
      className={btn.small}
    >
      <Icon name="download" className="h-3.5 w-3.5" />
      Download PDF
    </button>
  );
}
