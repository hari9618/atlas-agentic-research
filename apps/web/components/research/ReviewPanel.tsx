"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { ReviewDecision, ReviewHistoryItem, ReviewSectionKey } from "@/lib/api";
import { ACTION_LABEL, draftName, onDraft, sectionDef, sectionLabel } from "@/lib/review";
import { Icon, type IconName } from "@/components/ui/Icon";
import { Spinner } from "@/components/ui/Spinner";
import { btn, cx, monoLabel, surface, tap, toggleChip } from "@/components/ui/styles";

/** A review decision as shown in the history; `pending` until the server confirms it. */
export type ReviewEntry = ReviewHistoryItem & { pending?: boolean };

export const MAX_REVISIONS = 3;
const MAX_FEEDBACK = 2000;

const QUICK: Record<string, string[]> = {
  all: ["Go deeper on competitors", "Add recent news", "Simplify the language", "Tighten the bottom line"],
  financials: ["Add margins and cash flow", "Compare with last year", "Explain the revenue mix"],
  risks: ["Quantify the top risks", "Add regulatory risk", "Separate near-term from long-term"],
  competitors: ["Add pricing comparison", "Include smaller challengers", "Explain the moat"],
  recent_developments: ["Cover the last 90 days", "Explain market reaction"],
  market_position: ["Size the market", "Explain share trends"],
  company_overview: ["Clarify the business model", "List key customers"],
  outlook: ["Add concrete catalysts", "Give a 12-month view"],
};

type SectionChip = { key: ReviewSectionKey; label: string };

type Props = {
  id?: string;
  /** review = waiting for you; busy = a decision is being applied; approved / rejected
   *  = final; ended = the run can no longer take decisions (expired). */
  mode: "review" | "busy" | "approved" | "rejected" | "ended";
  busyAction?: ReviewDecision;
  revision: number;
  /** Finished without a human decision (review off, or the revision limit). */
  autoApproved?: boolean;
  history: ReviewEntry[];
  /** Sections present in this draft, for targeting feedback. */
  sections: SectionChip[];
  /** Anchor namespace of the rendered report (section links in the history). */
  ns?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApprove: () => void;
  onRevise: (feedback: string, section: ReviewSectionKey | null) => void;
  onReject: (reason: string) => void;
};

/** Human-in-the-loop decision panel: approve, request changes (optionally about one
 *  section) or reject (with a confirm step). The changes form is controlled so other
 *  surfaces (the mobile action bar) can open it. */
export function ReviewPanel({
  id,
  mode,
  busyAction,
  revision,
  autoApproved = false,
  history,
  sections,
  ns = "run",
  open,
  onOpenChange,
  onApprove,
  onRevise,
  onReject,
}: Props) {
  const [text, setText] = useState("");
  const [section, setSection] = useState<ReviewSectionKey | null>(null);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const uid = useId();
  const fieldRef = useRef<HTMLTextAreaElement>(null);
  const reasonRef = useRef<HTMLTextAreaElement>(null);
  const rejectBtnRef = useRef<HTMLButtonElement>(null);

  const limitReached = revision >= MAX_REVISIONS;
  const reviewing = mode === "review";
  const showForm = open && reviewing && !limitReached && !rejecting;
  const showReject = rejecting && reviewing;
  const left = Math.max(0, MAX_REVISIONS - revision);
  // A section picked for an older draft may not exist in this one.
  const chosen = section && sections.some((s) => s.key === section) ? section : null;

  useEffect(() => {
    if (showForm) fieldRef.current?.focus();
  }, [showForm]);
  useEffect(() => {
    if (showReject) reasonRef.current?.focus();
  }, [showReject]);

  const addQuick = (q: string) =>
    setText((t) => (t.trim() ? `${t.trim().replace(/[.;,]?$/, ".")} ${q}.` : `${q}.`).slice(0, MAX_FEEDBACK));

  const submitRevise = (e?: React.FormEvent) => {
    e?.preventDefault();
    const fb = text.trim();
    if (!fb) return;
    onRevise(fb, chosen);
    setText("");
    setSection(null);
    onOpenChange(false);
  };

  const confirmReject = (e?: React.FormEvent) => {
    e?.preventDefault();
    onReject(reason.trim());
    setReason("");
    setRejecting(false);
  };

  const cancelReject = () => {
    setRejecting(false);
    requestAnimationFrame(() => rejectBtnRef.current?.focus());
  };

  const onFormKey = (e: React.KeyboardEvent, submit: () => void, cancel: () => void) => {
    if (e.key === "Escape") {
      e.preventDefault();
      cancel();
    } else if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      submit();
    }
  };

  // ---- Final states ---------------------------------------------------------
  if (mode === "approved" || mode === "rejected" || mode === "ended") {
    const rejected = mode === "rejected";
    const ended = mode === "ended";
    const rejectReason = rejected ? [...history].reverse().find((h) => h.action === "reject")?.feedback : "";
    return (
      <section id={id} aria-labelledby={`${uid}-title`} className={cx(surface, "animate-enter scroll-mt-24 overflow-hidden")}>
        <div
          className={cx(
            "flex items-start gap-3 border-b px-4 py-4",
            rejected
              ? "border-rose-100 bg-linear-to-b from-rose-50 to-surface"
              : ended
                ? "border-amber-100 bg-linear-to-b from-amber-50 to-surface"
                : "border-emerald-100 bg-linear-to-b from-emerald-50 to-surface",
          )}
        >
          <span
            className={cx(
              "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-white",
              rejected ? "bg-rose-600" : ended ? "bg-amber-500" : "bg-emerald-600",
            )}
          >
            <Icon name={rejected ? "x" : ended ? "clock" : "check"} strokeWidth={3} />
          </span>
          <div className="min-w-0">
            <h2
              id={`${uid}-title`}
              className={cx("text-[15px] font-semibold", rejected ? "text-rose-900" : ended ? "text-amber-950" : "text-emerald-950")}
            >
              {rejected ? "Brief rejected" : ended ? "Review closed" : autoApproved ? "Brief complete" : "Brief approved"}
            </h2>
            <p className={cx("mt-0.5 text-sm", rejected ? "text-rose-800" : ended ? "text-amber-800" : "text-emerald-800")}>
              {rejected
                ? "This draft won't be finalized. It stays here for reference."
                : ended
                  ? "This run can no longer take decisions. The draft stays here to read or download."
                  : `Final version${revision > 0 ? `, revision ${revision}` : ""}. Download it as a PDF or ask a new question.`}
            </p>
            {rejected && rejectReason && (
              <blockquote className="mt-2.5 border-l-2 border-rose-300 pl-3 text-sm leading-relaxed text-rose-900">
                {rejectReason}
              </blockquote>
            )}
          </div>
        </div>
        <History items={history} ns={ns} />
      </section>
    );
  }

  // ---- Applying a decision ----------------------------------------------------
  if (mode === "busy") {
    const last = [...history].reverse().find((h) => h.pending);
    const copy: Record<ReviewDecision, { title: string; body: string }> = {
      approve: { title: "Finalizing the brief…", body: "Approval received. Atlas is saving the final version." },
      revise: {
        title: "Revising with your feedback…",
        body: "Atlas is researching your request and will bring back a new draft for review.",
      },
      reject: { title: "Recording the rejection…", body: "Atlas is closing this run without finalizing the draft." },
    };
    const c = copy[busyAction ?? "approve"];
    return (
      <section
        id={id}
        aria-labelledby={`${uid}-title`}
        aria-busy="true"
        className={cx(surface, "animate-enter scroll-mt-24 overflow-hidden")}
      >
        <div className="border-b border-slate-100 bg-linear-to-b from-indigo-50/80 to-surface px-4 py-4" role="status">
          <p className={cx(monoLabel, "flex items-center gap-2 text-indigo-600")}>
            <Spinner className="h-3.5 w-3.5" />
            Decision sent
          </p>
          <h2 id={`${uid}-title`} className="mt-2 text-[15px] font-semibold text-slate-950">
            {c.title}
          </h2>
          <p className="mt-1 text-sm leading-relaxed text-slate-600">{c.body}</p>
          {busyAction === "revise" && last?.feedback && (
            <div className="mt-3 rounded-xl border border-slate-200/80 bg-surface p-3">
              {last.section && (
                <span className="mb-1.5 inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] font-medium text-indigo-800 ring-1 ring-indigo-600/15 ring-inset">
                  <Icon name="target" className="h-3 w-3" />
                  {sectionLabel(last.section)}
                </span>
              )}
              <p className="line-clamp-4 text-sm leading-relaxed text-slate-700">{last.feedback}</p>
            </div>
          )}
        </div>
        <History items={history.filter((h) => !h.pending)} ns={ns} />
      </section>
    );
  }

  // ---- Waiting for a decision -------------------------------------------------
  return (
    <section id={id} aria-labelledby={`${uid}-title`} className={cx(surface, "animate-enter scroll-mt-24 overflow-hidden")}>
      <div className="border-b border-slate-100 bg-linear-to-b from-indigo-50/70 to-surface px-4 pt-4 pb-4">
        <div className="flex items-center justify-between gap-3">
          <p className={cx(monoLabel, "text-indigo-600")}>Your review</p>
          <span className="font-mono text-[10.5px] text-slate-500 capitalize tabular-nums">{draftName(revision)}</span>
        </div>
        <h2 id={`${uid}-title`} className="mt-2 text-[15px] font-semibold text-slate-950">
          Is this brief ready?
        </h2>
        <p className="mt-1 text-sm leading-relaxed text-slate-600">
          Approve to finalize, ask for changes and Atlas researches them for a new draft, or reject it.
        </p>
      </div>

      <div className="space-y-2 p-4">
        <button type="button" onClick={onApprove} className={cx(btn.primary, "w-full", tap)}>
          <Icon name="check" />
          Approve brief
        </button>
        <button
          type="button"
          onClick={() => {
            setRejecting(false);
            onOpenChange(!open);
          }}
          disabled={limitReached}
          aria-expanded={showForm}
          aria-controls={`${uid}-form`}
          className={cx(btn.secondary, "w-full", tap)}
        >
          <Icon name="edit" />
          Request changes
        </button>
        <div className="flex items-center justify-between gap-3 pt-1">
          <span className="text-xs text-slate-500">
            {limitReached ? "Revision limit reached" : `${left} revision${left === 1 ? "" : "s"} left`}
          </span>
          <span aria-hidden className="flex gap-1">
            {Array.from({ length: MAX_REVISIONS }, (_, i) => (
              <span
                key={i}
                className={cx("h-1.5 w-5 rounded-full transition-colors", i < revision ? "bg-indigo-500" : "bg-slate-200")}
              />
            ))}
          </span>
        </div>
      </div>

      {showForm && (
        <form
          id={`${uid}-form`}
          onSubmit={submitRevise}
          onKeyDown={(e) => onFormKey(e, submitRevise, () => onOpenChange(false))}
          className="animate-enter space-y-4 border-t border-slate-100 p-4"
        >
          {sections.length > 0 && (
            <fieldset>
              <legend className="text-sm font-medium text-slate-900">About which part?</legend>
              <p className="mt-0.5 text-xs text-slate-500">Optional. Pick one section to focus the revision.</p>
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                <button type="button" aria-pressed={chosen === null} onClick={() => setSection(null)} className={toggleChip}>
                  {chosen === null && <Icon name="check" className="h-3 w-3" strokeWidth={3} />}
                  Whole brief
                </button>
                {sections.map((s) => (
                  <button
                    key={s.key}
                    type="button"
                    aria-pressed={chosen === s.key}
                    onClick={() => setSection(chosen === s.key ? null : s.key)}
                    className={toggleChip}
                  >
                    {chosen === s.key && <Icon name="check" className="h-3 w-3" strokeWidth={3} />}
                    {s.label}
                  </button>
                ))}
              </div>
            </fieldset>
          )}

          <div>
            <div className="flex items-baseline justify-between gap-3">
              <label htmlFor={`${uid}-feedback`} className="text-sm font-medium text-slate-900">
                What should change?
              </label>
              <span className="font-mono text-[10.5px] text-slate-400 tabular-nums" aria-hidden>
                {text.length}/{MAX_FEEDBACK}
              </span>
            </div>
            <textarea
              id={`${uid}-feedback`}
              ref={fieldRef}
              value={text}
              maxLength={MAX_FEEDBACK}
              onChange={(e) => setText(e.target.value)}
              rows={4}
              aria-describedby={`${uid}-feedback-hint`}
              placeholder={
                chosen
                  ? `e.g. What's missing or wrong in ${sectionLabel(chosen).toLowerCase()}?`
                  : "e.g. Go deeper on how they compare with their two closest competitors."
              }
              className="mt-2 w-full resize-y rounded-xl border border-slate-300 bg-surface px-3 py-2 text-sm text-slate-900 placeholder:text-slate-500 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/15 focus:outline-none"
            />
            <p id={`${uid}-feedback-hint`} className="mt-1 text-xs text-slate-500">
              <kbd className="font-mono">Ctrl</kbd>+<kbd className="font-mono">Enter</kbd> to send · Esc to close
            </p>
          </div>

          <div>
            <p className="mb-1.5 text-xs text-slate-500">Quick add</p>
            <div className="flex flex-wrap gap-1.5">
              {(QUICK[chosen ?? "all"] ?? QUICK.all).map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => addQuick(q)}
                  className={cx(
                    "inline-flex min-h-7 items-center rounded-full border border-dashed border-slate-300 px-2.5 py-1 text-xs text-slate-600 transition-colors hover:border-indigo-400 hover:bg-indigo-50 hover:text-indigo-800",
                    tap,
                  )}
                >
                  + {q}
                </button>
              ))}
            </div>
          </div>

          <div className="flex gap-2">
            <button type="submit" disabled={!text.trim()} className={cx(btn.primary, "flex-1", tap)}>
              Send feedback
            </button>
            <button type="button" onClick={() => onOpenChange(false)} className={cx(btn.ghost, tap)}>
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="border-t border-slate-100 px-4 py-3">
        {showReject ? (
          <form
            onSubmit={confirmReject}
            onKeyDown={(e) => onFormKey(e, confirmReject, cancelReject)}
            className="animate-enter space-y-3 py-1"
            aria-labelledby={`${uid}-reject-title`}
          >
            <div className="flex gap-2.5">
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-rose-100 text-rose-700">
                <Icon name="alert" className="h-3.5 w-3.5" />
              </span>
              <div className="min-w-0">
                <p id={`${uid}-reject-title`} className="text-sm font-semibold text-slate-950">
                  Reject this brief?
                </p>
                <p className="mt-0.5 text-xs leading-relaxed text-slate-600">
                  The run ends here and the draft is marked rejected. This can&apos;t be undone.
                </p>
              </div>
            </div>
            <div>
              <label htmlFor={`${uid}-reason`} className="text-xs font-medium text-slate-700">
                Reason <span className="font-normal text-slate-500">(optional)</span>
              </label>
              <textarea
                id={`${uid}-reason`}
                ref={reasonRef}
                value={reason}
                maxLength={MAX_FEEDBACK}
                onChange={(e) => setReason(e.target.value)}
                rows={2}
                placeholder="e.g. Wrong company, or the evidence is too thin to act on."
                className="mt-1.5 w-full resize-y rounded-xl border border-slate-300 bg-surface px-3 py-2 text-sm text-slate-900 placeholder:text-slate-500 focus:border-rose-500 focus:ring-2 focus:ring-rose-500/15 focus:outline-none"
              />
            </div>
            <div className="flex gap-2">
              <button
                type="submit"
                className={cx(
                  "inline-flex min-w-0 flex-1 items-center justify-center gap-2 rounded-full bg-rose-600 px-4 py-2.5 text-sm font-semibold whitespace-nowrap text-white transition-colors hover:bg-rose-700",
                  tap,
                )}
              >
                <Icon name="x" />
                Reject brief
              </button>
              <button type="button" onClick={cancelReject} className={cx(btn.ghost, "shrink-0 whitespace-nowrap", tap)}>
                Keep reviewing
              </button>
            </div>
          </form>
        ) : (
          <button
            ref={rejectBtnRef}
            type="button"
            onClick={() => {
              onOpenChange(false);
              setRejecting(true);
            }}
            className={cx(
              "inline-flex w-full items-center justify-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium text-slate-500 transition-colors hover:bg-rose-50 hover:text-rose-700",
              tap,
            )}
          >
            <Icon name="x" className="h-3.5 w-3.5" />
            Reject this brief
          </button>
        )}
      </div>

      <History items={history} ns={ns} />
    </section>
  );
}

const ACTION_STYLE: Record<string, { icon: IconName; dot: string; text: string }> = {
  approve: { icon: "check", dot: "bg-emerald-600 text-white", text: "text-emerald-800" },
  auto_approve: { icon: "check", dot: "bg-emerald-100 text-emerald-700", text: "text-emerald-800" },
  revise: { icon: "edit", dot: "bg-indigo-600 text-white", text: "text-indigo-800" },
  reject: { icon: "x", dot: "bg-rose-600 text-white", text: "text-rose-800" },
};

function History({ items, ns }: { items: ReviewEntry[]; ns: string }) {
  if (!items.length) return null;
  return (
    <div className="border-t border-slate-100 px-4 py-4">
      <p className={cx(monoLabel, "mb-3 text-slate-500")}>Review history</p>
      <ol className="relative space-y-3.5">
        <span aria-hidden className="absolute top-2 bottom-2 left-[0.6875rem] w-px bg-slate-200" />
        {items.map((h, i) => {
          const st = ACTION_STYLE[h.action] ?? ACTION_STYLE.revise;
          const sec = sectionDef(h.section);
          return (
            <li key={i} className={cx("relative flex gap-3 text-sm", h.pending && "opacity-70")}>
              <span
                aria-hidden
                className={cx("relative flex h-[1.375rem] w-[1.375rem] shrink-0 items-center justify-center rounded-full ring-4 ring-surface", st.dot)}
              >
                <Icon name={st.icon} className="h-3 w-3" strokeWidth={3} />
              </span>
              <div className="min-w-0 flex-1 pt-px">
                <p className="flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5">
                  <span className={cx("font-medium", st.text)}>{ACTION_LABEL[h.action] ?? h.action}</span>
                  <span className="text-xs text-slate-500">{onDraft(h.revision)}</span>
                  {h.pending && <span className="text-xs text-slate-500">· sending</span>}
                </p>
                {h.section &&
                  (sec ? (
                    <a
                      href={`#${ns}-${sec.block}`}
                      title={`Go to ${sec.label}`}
                      className="mt-1 inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700 transition-colors hover:bg-indigo-50 hover:text-indigo-800"
                    >
                      <Icon name="target" className="h-3 w-3" />
                      {sec.label}
                    </a>
                  ) : (
                    <span className="mt-1 inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700">
                      <Icon name="target" className="h-3 w-3" />
                      {sectionLabel(h.section)}
                    </span>
                  ))}
                {h.feedback && <p className="mt-1 leading-relaxed text-slate-700">{h.feedback}</p>}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
