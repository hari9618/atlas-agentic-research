"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { btn, cx, monoLabel, surface } from "@/components/ui/styles";

export type ReviewEntry = { revision: number; action: "approve" | "revise"; feedback: string };

export const MAX_REVISIONS = 3;

const QUICK = [
  "More on competitors",
  "Deeper financials",
  "Simplify the language",
  "Focus on risks",
  "Add recent news",
];

/** Human-in-the-loop: approve the draft or ask for specific changes. The form's open
 *  state is controlled so other surfaces (the mobile action bar) can open it. */
export function ReviewPanel({
  id,
  mode,
  revision,
  autoApproved = false,
  history,
  open,
  onOpenChange,
  onApprove,
  onRevise,
}: {
  id?: string;
  /** review = waiting for you; busy = a resume is running; approved = done. */
  mode: "review" | "busy" | "approved";
  revision: number;
  /** Finished without a human review step (e.g. review disabled on the backend). */
  autoApproved?: boolean;
  history: ReviewEntry[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApprove: () => void;
  onRevise: (feedback: string) => void;
}) {
  const [text, setText] = useState("");
  const fieldId = useId();
  const fieldRef = useRef<HTMLTextAreaElement>(null);
  const limitReached = revision >= MAX_REVISIONS;
  const requested = history.filter((h) => h.action === "revise");
  const busy = mode === "busy";
  const showForm = open && !busy && !limitReached;

  // Move focus into the feedback field whenever the form opens.
  useEffect(() => {
    if (showForm) fieldRef.current?.focus();
  }, [showForm]);

  const addChip = (chip: string) =>
    setText((t) => (t.trim() ? `${t.trim().replace(/[.;,]?$/, ".")} ${chip}.` : `${chip}.`));

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    onRevise(text.trim());
    setText("");
    onOpenChange(false);
  };

  if (mode === "approved") {
    return (
      <section id={id} aria-labelledby="review-title" className={cx(surface, "scroll-mt-24 overflow-hidden")}>
        <div className="flex items-start gap-3 border-b border-emerald-100 bg-linear-to-b from-emerald-50 to-white px-4 py-4">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-white shadow-[0_6px_16px_-6px_rgb(5_150_105/0.6)]">
            <Icon name="check" strokeWidth={3} />
          </span>
          <div className="min-w-0">
            <h2 id="review-title" className="text-[15px] font-semibold text-emerald-950">
              {autoApproved ? "Brief complete" : "Brief approved"}
            </h2>
            <p className="mt-0.5 text-sm text-emerald-800">
              Final version{revision > 0 ? `, revision ${revision}` : ""}. Download it as a PDF or ask a new question.
            </p>
          </div>
        </div>
        <History items={requested} />
      </section>
    );
  }

  const left = Math.max(0, MAX_REVISIONS - revision);

  return (
    <section id={id} aria-labelledby="review-title" className={cx(surface, "scroll-mt-24 overflow-hidden")}>
      <div className="border-b border-slate-100 bg-linear-to-b from-indigo-50/80 to-white px-4 pt-4 pb-4">
        <div className="flex items-center justify-between gap-3">
          <p className={cx(monoLabel, "text-indigo-600")}>Your review</p>
          <span className="font-mono text-[10.5px] text-slate-500 tabular-nums">
            {revision === 0 ? "First draft" : `Revision ${revision}`}
          </span>
        </div>
        <h2 id="review-title" className="mt-2 text-[15px] font-semibold text-slate-950">
          {busy ? "Working on it…" : "Is this brief ready?"}
        </h2>
        <p className="mt-1 text-sm leading-relaxed text-slate-600">
          {busy
            ? "Atlas is applying your decision. Progress is shown in the run panel."
            : "Approve to finalize, or tell Atlas what to change and it will research your feedback for a new draft."}
        </p>
      </div>

      <div className="space-y-2 p-4">
        <button type="button" onClick={onApprove} disabled={busy} className={cx(btn.primary, "w-full")}>
          <Icon name="check" />
          Approve brief
        </button>
        <button
          type="button"
          onClick={() => onOpenChange(!open)}
          disabled={busy || limitReached}
          aria-expanded={showForm}
          aria-controls={`${fieldId}-form`}
          className={cx(btn.secondary, "w-full")}
        >
          <Icon name="edit" />
          Request changes
        </button>
        <div className="flex items-center justify-between gap-3 pt-1.5">
          <span className="text-xs text-slate-500">
            {limitReached ? "Revision limit reached" : `${left} revision${left === 1 ? "" : "s"} left`}
          </span>
          <span aria-hidden className="flex gap-1">
            {Array.from({ length: MAX_REVISIONS }, (_, i) => (
              <span key={i} className={cx("h-1.5 w-5 rounded-full", i < revision ? "bg-indigo-500" : "bg-slate-200")} />
            ))}
          </span>
        </div>
      </div>

      {showForm && (
        <form id={`${fieldId}-form`} onSubmit={submit} className="space-y-3 border-t border-slate-100 p-4">
          <label htmlFor={fieldId} className="block text-sm font-medium text-slate-900">
            What should change?
          </label>
          <textarea
            id={fieldId}
            ref={fieldRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={4}
            placeholder="e.g. Go deeper on how they compare with their two closest competitors."
            className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm placeholder:text-slate-500 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/15 focus:outline-none"
          />
          <div>
            <p className="mb-1.5 text-xs text-slate-500">Quick add</p>
            <div className="flex flex-wrap gap-1.5">
              {QUICK.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => addChip(q)}
                  className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-700 transition-colors hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700"
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
            <button type="button" onClick={() => onOpenChange(false)} className={btn.ghost}>
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
    <div className="border-t border-slate-100 px-4 py-4">
      <p className={cx(monoLabel, "mb-3 text-slate-500")}>Changes you requested</p>
      <ol className="relative space-y-3 border-l border-slate-200 pl-4">
        {items.map((h, i) => (
          <li key={i} className="relative text-sm">
            <span aria-hidden className="absolute top-1.5 -left-[1.3rem] h-2 w-2 rounded-full bg-indigo-500 ring-4 ring-white" />
            <span className="font-mono text-[10.5px] text-slate-500">Rev {h.revision}</span>
            <p className="mt-0.5 leading-relaxed text-slate-700">{h.feedback}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}
