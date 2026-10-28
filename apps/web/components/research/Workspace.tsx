"use client";

import { useEffect, useRef, useState } from "react";
import {
  type DebateTurn,
  type Finding,
  type NodeName,
  type ResearchPayload,
  type ReportSections,
  SPECIALISTS,
  newThreadId,
  resumeResearch,
  startResearch,
  type StreamHandlers,
} from "@/lib/api";
import { SAMPLE_PAYLOAD, SAMPLE_QUERY } from "@/lib/sample-report";
import { ExportButton } from "@/components/report/ExportButton";
import { PrintableReport } from "@/components/report/PrintableReport";
import { StructuredReport } from "@/components/report/StructuredReport";
import { Badge } from "@/components/ui/Badge";
import { Icon, type IconName } from "@/components/ui/Icon";
import { btn, cardBase, cx, eyebrow, monoLabel, surface } from "@/components/ui/styles";
import { CorpusPanel } from "./CorpusPanel";
import {
  type ActivityEntry,
  clock,
  IDLE_STEPS,
  ProgressStepper,
  RunCard,
  type StepId,
  type Steps,
} from "./ProgressStepper";
import { QueryBox } from "./QueryBox";
import { MAX_REVISIONS, ReviewPanel, type ReviewEntry } from "./ReviewPanel";

type Phase = "idle" | "running" | "review" | "revising" | "approving" | "final" | "error";
type LastOp = { kind: "start" } | { kind: "resume"; action: "approve" | "revise"; feedback: string };

const SPECIALIST_LABEL: Record<string, string> = {
  fundamentals: "Fundamentals analyst",
  news_sentiment: "News analyst",
  market: "Market analyst",
  risk: "Risk analyst",
};

const HEADLINE: Record<Phase, string> = {
  idle: "",
  running: "Researching…",
  review: "Draft ready for your review",
  revising: "Revising the report with your feedback…",
  approving: "Finalizing the report…",
  final: "Research complete",
  error: "The run stopped",
};

const REVIEW_PANEL_ID = "review-panel";

const isSpecialist = (n: string) => (SPECIALISTS as readonly string[]).includes(n);

export function Workspace({ initialQuery = "" }: { initialQuery?: string }) {
  const [query, setQuery] = useState(initialQuery);
  const [asked, setAsked] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [steps, setSteps] = useState<Steps>(IDLE_STEPS);
  const [counts, setCounts] = useState<Partial<Record<StepId, number>>>({});
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const [payload, setPayload] = useState<Partial<ResearchPayload> | null>(null);
  const [revision, setRevision] = useState(0);
  const [reviewStatus, setReviewStatus] = useState<string>("");
  const [history, setHistory] = useState<ReviewEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [showSample, setShowSample] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);

  const cancelRef = useRef<(() => void) | null>(null);
  const threadRef = useRef<string>("");
  const lastOpRef = useRef<LastOp>({ kind: "start" });
  const startedRef = useRef(0);
  const revisionRef = useRef(0);

  const live = phase === "running" || phase === "revising" || phase === "approving";

  // Tick the elapsed timer while a stream is open so the UI never looks frozen.
  useEffect(() => {
    if (!live) return;
    const t = setInterval(() => setElapsed(Math.floor((Date.now() - startedRef.current) / 1000)), 1000);
    return () => clearInterval(t);
  }, [live]);

  // Close any open stream when leaving the page.
  useEffect(() => () => cancelRef.current?.(), []);

  const since = () => Math.max(0, Math.floor((Date.now() - startedRef.current) / 1000));
  const log = (text: string) => setActivity((a) => [{ text, at: since() }, ...a].slice(0, 7));
  const setStep = (patch: Partial<Steps>) => setSteps((s) => ({ ...s, ...patch }));

  const mergePayload = (data: Record<string, unknown>) =>
    setPayload((p) => {
      const next: Partial<ResearchPayload> = { ...(p ?? {}) };
      if (data.report_sections && typeof data.report_sections === "object")
        next.report_sections = data.report_sections as ReportSections;
      if (typeof data.report === "string") next.report = data.report;
      if (typeof data.confidence === "number") next.confidence = data.confidence;
      if (Array.isArray(data.uncertainties)) next.uncertainties = data.uncertainties as string[];
      if (Array.isArray(data.citations)) next.citations = data.citations as ResearchPayload["citations"];
      if (typeof data.target === "string" && data.target) next.target = data.target;
      return next;
    });

  const handlers = (): StreamHandlers => ({
    onStart: (d) => {
      if (d.thread_id) threadRef.current = d.thread_id;
    },
    onNode: (node: NodeName, data) => {
      if (node === "recall") {
        log("Checked memory for related past research");
      } else if (node === "supervisor") {
        const target = typeof data.target === "string" ? data.target : "";
        setStep({ plan: "done", fundamentals: "active", news_sentiment: "active", market: "active", risk: "active" });
        if (target) setPayload((p) => ({ ...(p ?? {}), target }));
        log(target ? `Planned the research on ${target}` : "Planned the research");
      } else if (isSpecialist(node)) {
        const found = Array.isArray(data.findings) ? (data.findings as Finding[]) : [];
        setPayload((p) => ({ ...(p ?? {}), findings: [...(p?.findings ?? []), ...found] }));
        setCounts((c) => ({ ...c, [node]: (c[node as StepId] ?? 0) + found.length }));
        setSteps((s) => {
          const next: Steps = { ...s, [node]: "done" };
          if (SPECIALISTS.every((sp) => next[sp] === "done") && next.debate === "idle") next.debate = "active";
          return next;
        });
        log(`${SPECIALIST_LABEL[node]} finished with ${found.length} finding${found.length === 1 ? "" : "s"}`);
      } else if (node === "debate_round") {
        if (Array.isArray(data.debate)) setPayload((p) => ({ ...(p ?? {}), debate: data.debate as DebateTurn[] }));
        setStep({ debate: "done", writing: "active" });
        log("The bull and the bear made their cases");
      } else if (node === "revise_research") {
        const found = Array.isArray(data.findings) ? (data.findings as Finding[]) : [];
        if (found.length) setPayload((p) => ({ ...(p ?? {}), findings: [...(p?.findings ?? []), ...found] }));
        setStep({ followup: "done", writing: "active" });
        log(`Gathered ${found.length || "extra"} new finding${found.length === 1 ? "" : "s"} for your feedback`);
      } else if (node === "synthesize") {
        mergePayload(data);
        setStep({ writing: "done", review: "active" });
        log("Drafted the report");
      } else if (node === "remember") {
        log("Saved this research to memory");
      }
    },
    onReviewRequired: (d) => {
      if (d.thread_id) threadRef.current = d.thread_id;
      revisionRef.current = d.revision ?? revisionRef.current;
      setRevision(revisionRef.current);
      setPayload((p) => ({ ...(p ?? {}), ...d }));
      setSteps((s) => ({ ...s, plan: "done", ...doneSpecialists(), debate: "done", writing: "done", review: "active", followup: s.followup === "idle" ? "idle" : "done" }));
      setPhase("review");
      log(revisionRef.current > 0 ? `Revision ${revisionRef.current} is ready` : "First draft is ready");
    },
    onFinal: (d) => {
      if (d.thread_id) threadRef.current = d.thread_id;
      if (typeof d.revision === "number") {
        revisionRef.current = d.revision;
        setRevision(d.revision);
      }
      setPayload((p) => ({ ...(p ?? {}), ...d }));
      setReviewStatus(d.review_status || "auto_approved");
      setSteps((s) => Object.fromEntries(Object.entries(s).map(([k, v]) => [k, k === "followup" && v === "idle" ? "idle" : "done"])) as Steps);
      setPhase("final");
      log("Report approved and finalized");
    },
    onError: (msg) => {
      setError(msg);
      setSteps((s) => Object.fromEntries(Object.entries(s).map(([k, v]) => [k, v === "active" ? "error" : v])) as Steps);
      setPhase("error");
    },
  });

  function beginClock() {
    startedRef.current = Date.now();
    setElapsed(0);
  }

  function run(q: string) {
    const text = q.trim();
    if (text.length < 3 || live) return;
    cancelRef.current?.();
    lastOpRef.current = { kind: "start" };
    threadRef.current = newThreadId();
    revisionRef.current = 0;
    beginClock();
    setAsked(text);
    setShowSample(false);
    setError(null);
    setPayload(null);
    setRevision(0);
    setReviewStatus("");
    setHistory([]);
    setReviewOpen(false);
    setCounts({});
    setActivity([{ text: "Starting the research team…", at: 0 }]);
    setSteps({ ...IDLE_STEPS, plan: "active" });
    setPhase("running");
    cancelRef.current = startResearch(text, { review: true, threadId: threadRef.current }, handlers());
  }

  function resume(action: "approve" | "revise", feedback = "") {
    if (!threadRef.current || live) return;
    cancelRef.current?.();
    lastOpRef.current = { kind: "resume", action, feedback };
    setError(null);
    setReviewOpen(false);
    beginClock();
    if (action === "approve") {
      setHistory((h) => [...h, { revision: revisionRef.current, action, feedback: "" }]);
      setStep({ review: "active" });
      setActivity([{ text: "Finalizing your approved report…", at: 0 }]);
      setPhase("approving");
    } else {
      setHistory((h) => [...h, { revision: revisionRef.current + 1, action, feedback }]);
      setStep({ followup: "active", writing: "idle", review: "idle" });
      setActivity([{ text: "Researching your feedback…", at: 0 }]);
      setPhase("revising");
    }
    cancelRef.current = resumeResearch(threadRef.current, action, feedback, handlers());
  }

  function retry() {
    const op = lastOpRef.current;
    if (op.kind === "start") run(asked || query);
    else {
      // Roll back the history entry the failed attempt added, then try again.
      setHistory((h) => h.slice(0, -1));
      resume(op.action, op.feedback);
    }
  }

  function reset() {
    cancelRef.current?.();
    setPhase("idle");
    setPayload(null);
    setError(null);
    setSteps(IDLE_STEPS);
    setActivity([]);
    setHistory([]);
    setReviewOpen(false);
    setAsked("");
  }

  function openReview() {
    setReviewOpen(true);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    document.getElementById(REVIEW_PANEL_ID)?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  }

  const hasReport = !!payload && (!!payload.report_sections || !!payload.report);
  const compact = phase !== "idle";
  const draftStale = phase === "revising" || phase === "approving";
  const approved = phase === "final";
  const sampleOn = showSample && !compact;
  const showMobileBar = hasReport && (phase === "review" || live);
  const statusBadge = approved ? (
    <Badge tone="good" dot surface="dark">
      {reviewStatus === "auto_approved" ? "Final" : "Approved"}
    </Badge>
  ) : hasReport && phase !== "running" ? (
    <Badge tone="mid" surface="dark">
      Draft · awaiting review
    </Badge>
  ) : null;

  const progressProps = {
    steps,
    counts,
    headline: HEADLINE[phase],
    elapsed: live ? elapsed : undefined,
    activity,
    showFollowup: history.some((h) => h.action === "revise"),
    reviewLabel: phase === "approving" || approved ? "Approval" : "Your review",
  };

  return (
    <>
      <div className={cx("screen-only space-y-6", showMobileBar && "pb-24 lg:pb-0")}>
        <QueryBox query={query} setQuery={setQuery} onSubmit={() => run(query)} busy={live} compact={compact} />
        {!compact && <CorpusPanel />}

        {phase === "error" && error && (
          <div
            role="alert"
            className={cx(cardBase, "flex flex-col gap-3 border-rose-200 bg-rose-50/70 p-4 sm:flex-row sm:items-center")}
          >
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-rose-100 text-rose-700">
              <Icon name="alert" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-rose-900">Something went wrong</p>
              <p className="text-sm text-rose-800">{error}</p>
            </div>
            <div className="flex gap-2">
              <button type="button" onClick={retry} className={btn.primary}>
                <Icon name="refresh" />
                Try again
              </button>
              <button type="button" onClick={reset} className={btn.secondary}>
                Start over
              </button>
            </div>
          </div>
        )}

        {compact && !hasReport && (
          <>
            <ProgressStepper {...progressProps} question={asked} />
            {live && <ReportSkeleton />}
          </>
        )}

        {!compact && !showSample && <EmptyState onSample={() => setShowSample(true)} />}

        {sampleOn && (
          <ReportLayout
            aside={
              <section aria-labelledby="sample-rail-title" className={cx(surface, "p-4")}>
                <p className={cx(monoLabel, "text-indigo-600")}>Sample brief</p>
                <h2 id="sample-rail-title" className="mt-2 text-[15px] font-semibold text-slate-950">
                  Helios Robotics, from the demo documents
                </h2>
                <p className="mt-1 text-sm leading-relaxed text-slate-600">
                  A fictional company, so you can see the full layout before running your own question. Every figure is
                  cited to the demo corpus.
                </p>
                <div className="mt-4 space-y-2">
                  <ExportButton ready className={cx(btn.secondary, "w-full")} />
                  <button type="button" onClick={() => setShowSample(false)} className={cx(btn.ghost, "w-full")}>
                    Hide sample
                  </button>
                </div>
              </section>
            }
          >
            <StructuredReport payload={SAMPLE_PAYLOAD} ns="sample" label="Sample" tocStickyClass="top-[4.75rem]" />
          </ReportLayout>
        )}

        {hasReport && payload && (
          <ReportLayout
            aside={
              <>
                <RunCard {...progressProps} live={live} />
                {(phase === "review" || draftStale || approved) && (
                  <ReviewPanel
                    id={REVIEW_PANEL_ID}
                    mode={approved ? "approved" : draftStale ? "busy" : "review"}
                    revision={revision}
                    autoApproved={reviewStatus === "auto_approved"}
                    history={history}
                    open={reviewOpen}
                    onOpenChange={setReviewOpen}
                    onApprove={() => resume("approve")}
                    onRevise={(f) => resume("revise", f)}
                  />
                )}
                <div className={cx(surface, "space-y-2 p-3")}>
                  <ExportButton ready={hasReport} className={cx(btn.secondary, "w-full")} />
                  {(approved || phase === "error") && (
                    <button type="button" onClick={reset} className={cx(btn.ghost, "w-full")}>
                      <Icon name="refresh" />
                      Start new research
                    </button>
                  )}
                </div>
                <CorpusPanel />
              </>
            }
          >
            {draftStale && (
              <div
                role="status"
                className="mb-4 flex items-center gap-3 rounded-xl border border-indigo-200 bg-indigo-50/80 px-4 py-3 text-sm text-indigo-900"
              >
                <span aria-hidden className="h-2 w-2 shrink-0 animate-blink rounded-full bg-indigo-500" />
                {phase === "revising"
                  ? "Revising this draft with your feedback. The new revision replaces it when ready."
                  : "Finalizing the approved brief…"}
              </div>
            )}
            <div className={cx("transition-opacity", phase === "revising" && "opacity-60")}>
              <StructuredReport
                payload={payload}
                ns="run"
                revision={revision}
                status={statusBadge}
                tocStickyClass="top-[4.75rem]"
              />
            </div>
          </ReportLayout>
        )}
      </div>

      {showMobileBar && (
        <div className="screen-only fixed inset-x-0 bottom-0 z-40 border-t border-slate-200/80 bg-white/90 px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] shadow-[0_-12px_30px_-18px_rgb(15_23_42/0.35)] backdrop-blur-md lg:hidden">
          {phase === "review" ? (
            <div className="flex gap-2">
              <button type="button" onClick={() => resume("approve")} className={cx(btn.primary, "flex-1")}>
                <Icon name="check" />
                Approve
              </button>
              <button
                type="button"
                onClick={openReview}
                disabled={revision >= MAX_REVISIONS}
                className={cx(btn.secondary, "flex-1")}
              >
                <Icon name="edit" />
                Request changes
              </button>
            </div>
          ) : (
            <p role="status" className="flex items-center gap-2.5 text-sm font-medium text-slate-800">
              <span aria-hidden className="h-2 w-2 shrink-0 animate-blink rounded-full bg-indigo-500" />
              <span className="min-w-0 truncate">{HEADLINE[phase]}</span>
              <span className="ml-auto font-mono text-xs text-slate-500 tabular-nums">{clock(elapsed)}</span>
            </p>
          )}
        </div>
      )}

      <PrintableReport
        query={hasReport ? asked : sampleOn ? SAMPLE_QUERY : asked}
        payload={hasReport ? payload : sampleOn ? SAMPLE_PAYLOAD : null}
        revision={hasReport ? revision : sampleOn ? 1 : revision}
        status={
          hasReport
            ? approved
              ? reviewStatus === "auto_approved"
                ? "Final"
                : "Approved"
              : "Draft, not yet approved"
            : "Sample data"
        }
      />
    </>
  );
}

/** Report column + sticky right rail (review, run status, actions). On narrow screens
 *  the rail follows the report. */
function ReportLayout({ children, aside }: { children: React.ReactNode; aside: React.ReactNode }) {
  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_18.5rem] xl:gap-8">
      <div className="min-w-0">{children}</div>
      <aside
        aria-label="Review and actions"
        className="space-y-4 lg:sticky lg:top-[5.5rem] lg:max-h-[calc(100vh-6.5rem)] lg:overflow-y-auto lg:px-1 lg:pb-2 lg:[scrollbar-width:thin]"
      >
        {aside}
      </aside>
    </div>
  );
}

/** Placeholder shapes of the brief while the analysts work (decorative). */
function ReportSkeleton() {
  const bar = "rounded-full animate-pulse-soft";
  return (
    <div className="space-y-3">
      <p className="flex items-center gap-2 text-sm text-slate-500">
        <Icon name="file" className="h-4 w-4" />
        Your brief appears here as soon as the writer finishes.
      </p>
      <div aria-hidden className="space-y-4">
        <div className="rounded-2xl bg-ink-950 p-6 ring-1 ring-ink-700/70 sm:p-8">
          <div className={cx(bar, "h-3 w-40 bg-white/10")} />
          <div className={cx(bar, "mt-6 h-10 w-2/3 max-w-md bg-white/10")} />
          <div className={cx(bar, "mt-4 h-3 w-full max-w-2xl bg-white/[0.07]")} />
          <div className={cx(bar, "mt-2 h-3 w-4/5 max-w-xl bg-white/[0.07]")} />
          <div className="mt-8 grid grid-cols-2 gap-px overflow-hidden rounded-xl bg-white/[0.06] sm:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="bg-ink-900 p-4">
                <div className={cx(bar, "h-2 w-16 bg-white/10")} />
                <div className={cx(bar, "mt-3 h-6 w-20 bg-white/[0.12]")} />
              </div>
            ))}
          </div>
        </div>
        <div className={cx(surface, "space-y-3 p-6 sm:p-8")}>
          <div className={cx(bar, "h-2.5 w-10 bg-indigo-100")} />
          <div className={cx(bar, "h-6 w-48 bg-slate-100")} />
          <div className={cx(bar, "h-3 w-full bg-slate-100")} />
          <div className={cx(bar, "h-3 w-11/12 bg-slate-100")} />
          <div className={cx(bar, "h-3 w-3/4 bg-slate-100")} />
        </div>
      </div>
    </div>
  );
}

function doneSpecialists(): Partial<Steps> {
  return Object.fromEntries(SPECIALISTS.map((s) => [s, "done"])) as Partial<Steps>;
}

function EmptyState({ onSample }: { onSample: () => void }) {
  const steps: [IconName, string, string][] = [
    ["target", "Plan", "Atlas scopes your question and picks what to research."],
    ["users", "Research", "Four analysts cover financials, news, market and risk in parallel."],
    ["scale", "Debate", "A bull and a bear argue both sides of the evidence."],
    ["check", "Review", "You get a cited draft to approve or send back with changes."],
  ];
  return (
    <section aria-labelledby="empty-title" className={cx(surface, "p-5 sm:p-7")}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className={eyebrow}>What happens next</p>
          <h2 id="empty-title" className="mt-2 text-lg font-semibold tracking-tight text-slate-950">
            Four steps from question to reviewed brief
          </h2>
        </div>
        <span className="font-mono text-xs text-slate-400">~2 min per run</span>
      </div>
      <ol className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {steps.map(([icon, t, d], i) => (
          <li key={t} className="rounded-2xl border border-slate-200/80 bg-slate-50/60 p-4">
            <div className="flex items-center justify-between">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white text-indigo-700 shadow-xs ring-1 ring-slate-200">
                <Icon name={icon} className="h-4.5 w-4.5" />
              </span>
              <span className="font-display text-2xl text-slate-300">{String(i + 1).padStart(2, "0")}</span>
            </div>
            <p className="mt-4 text-sm font-semibold text-slate-950">{t}</p>
            <p className="mt-1 text-sm leading-relaxed text-slate-600">{d}</p>
          </li>
        ))}
      </ol>
      <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-slate-200/80 pt-5">
        <button type="button" onClick={onSample} className={btn.secondary}>
          <Icon name="file" />
          Preview a sample report
        </button>
        <span className="text-xs text-slate-500">Progress streams in live as each analyst finishes.</span>
      </div>
    </section>
  );
}
