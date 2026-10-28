"use client";

import { useId, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { btn, cardBase, cx } from "@/components/ui/styles";

export type ReviewEntry = { revision: number; action: "approve" | "revise"; feedback: string };

export const MAX_REVISIONS = 3;

const QUICK = [
  "More on competitors",
  "Deeper financials",
  "Simplify the language",
  "Focus on risks",
  "Add recent news",
];

/** Human-in-the-loop: approve the draft or ask for specific changes. */
export function ReviewPanel({
  mode,
  revision,
  autoApproved = false,
  history,
  onApprove,
  onRevise,
}: {
  /** review = waiting for you; busy = a resume is running; approved = done. */
  mode: "review" | "busy" | "approved";
  revision: number;
  /** Finished without a human review step (e.g. review disabled on the backend). */
  autoApproved?: boolean;
  history: ReviewEntry[];
  onApprove: () => void;
  onRevise: (feedback: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const fieldId = useId();
  const limitReached = revision >= MAX_REVISIONS;
  const requested = history.filter((h) => h.action === "revise");

  const addChip = (chip: string) =>
    setText((t) => (t.trim() ? `${t.trim().replace(/[.;,]?$/, ".")} ${chip}.` : `${chip}.`));

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    onRevise(text.trim());
    setText("");
    setOpen(false);
  };

  if (mode === "approved") {
    return (
      <section aria-labelledby="review-title" className={cx(cardBase, "border-emerald-200 bg-emerald-50/60 p-5")}>
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-white">
            <Icon name="check" strokeWidth={3} />
          </span>
          <div>
            <h2 id="review-title" className="text-base font-semibold text-emerald-900">
              {autoApproved ? "Report complete" : "Report approved"}
            </h2>
            <p className="mt-1 text-sm text-emerald-800">
              This is the final version{revision > 0 ? ` (revision ${revision})` : ""}. Download it as a PDF
              or start a new question.
            </p>
          </div>
        </div>
        <History items={requested} />
      </section>
    );
  }

  const busy = mode === "busy";

  return (
    <section aria-labelledby="review-title" className={cx(cardBase, "border-indigo-200 bg-white p-5 shadow-sm")}>
      <p className="text-xs font-semibold tracking-wider text-indigo-600 uppercase">Your review</p>
      <h2 id="review-title" className="mt-1 text-base font-semibold text-slate-900">
        {busy ? "Working on it…" : "Is this report ready?"}
      </h2>
      <p className="mt-1 text-sm text-slate-600">
        {busy
          ? "Atlas is applying your decision. Progress is shown above."
          : "Approve it to finalize, or tell Atlas what to change. It will research your feedback and write a new draft."}
      </p>

      <div className="mt-4 flex flex-col gap-2 sm:flex-row lg:flex-col xl:flex-row">
        <button type="button" onClick={onApprove} disabled={busy} className={cx(btn.primary, "flex-1")}>
          <Icon name="check" />
          Approve report
        </button>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          disabled={busy || limitReached}
          aria-expanded={open}
          aria-controls={`${fieldId}-form`}
          className={cx(btn.secondary, "flex-1")}
        >
          <Icon name="edit" />
          Request changes
        </button>
      </div>
      {limitReached && !busy && (
        <p className="mt-2 text-xs text-slate-500">
          You&apos;ve reached the limit of {MAX_REVISIONS} revisions for this report.
        </p>
      )}

      {open && !busy && (
        <form id={`${fieldId}-form`} onSubmit={submit} className="mt-4 space-y-3 border-t border-slate-200 pt-4">
          <label htmlFor={fieldId} className="block text-sm font-medium text-slate-900">
            What should change?
          </label>
          <textarea
            id={fieldId}
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={4}
            placeholder="e.g. Go deeper on how they compare with their two closest competitors."
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm placeholder:text-slate-500 focus:border-indigo-500 focus:outline-none"
          />
          <div>
            <p className="mb-1.5 text-xs text-slate-500">Quick add</p>
            <div className="flex flex-wrap gap-1.5">
              {QUICK.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => addChip(q)}
                  className="rounded-full border border-slate-300 bg-white px-2.5 py-1 text-xs text-slate-700 hover:border-indigo-400 hover:text-indigo-700"
                >
                  + {q}
                </button>
              ))}
            </div>
          </div>
          <div className="flex gap-2">
            <button type="submit" disabled={!text.trim()} className={cx(btn.primary, "flex-1")}>
              Send feedback
            </button>
            <button type="button" onClick={() => setOpen(false)} className={btn.ghost}>
              Cancel
            </button>
          </div>
        </form>
      )}

      <History items={requested} />
    </section>
  );
}

function History({ items }: { items: ReviewEntry[] }) {
  if (!items.length) return null;
  return (
    <div className="mt-5 border-t border-slate-200 pt-4">
      <p className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">Changes you requested</p>
      <ol className="space-y-2">
        {items.map((h, i) => (
          <li key={i} className="text-sm">
            <span className="mr-2 inline-block rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-600">
              Rev {h.revision}
            </span>
            <span className="text-slate-700">{h.feedback}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
