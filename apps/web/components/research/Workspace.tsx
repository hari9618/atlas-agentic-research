"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import {
  type ApiFailure,
  type DebateTurn,
  ensureAwake,
  type Finding,
  isWarm,
  type NodeName,
  newThreadId,
  type ReportSections,
  type ResearchPayload,
  resumeResearch,
  type ReviewDecision,
  type ReviewHistoryItem,
  type ReviewSectionKey,
  SPECIALISTS,
  startResearch,
  type StreamHandlers,
} from "@/lib/api";
import { reviewableSections, sectionDef } from "@/lib/review";
import { SAMPLE_PAYLOAD, SAMPLE_QUERY } from "@/lib/sample-report";
import { ExportButton } from "@/components/report/ExportButton";
import { PrintableReport } from "@/components/report/PrintableReport";
import { StructuredReport } from "@/components/report/StructuredReport";
import { Badge } from "@/components/ui/Badge";
import { Icon, type IconName } from "@/components/ui/Icon";
import { Spinner } from "@/components/ui/Spinner";
import { btn, cardBase, cx, eyebrow, limePill, monoLabel, surface, tap } from "@/components/ui/styles";
import { CorpusPanel } from "./CorpusPanel";
import { describeFailure, type Recovery, type RunError } from "./failure";
import {
  type ActivityEntry,
  clock,
  IDLE_STEPS,
  ProgressStepper,
  RunCard,
  type RunMode,
  type StepId,
  type Steps,
} from "./ProgressStepper";
import { type EngineState, QueryBox } from "./QueryBox";
import { MAX_REVISIONS, ReviewPanel, type ReviewEntry } from "./ReviewPanel";

type Phase =
  | "idle"
  | "waking"
  | "running"
  | "review"
  | "revising"
  | "approving"
  | "rejecting"
  | "final"
  | "rejected"
  | "error";

type LastOp =
  | { kind: "start"; query: string }
  | { kind: "resume"; action: ReviewDecision; feedback: string; section: ReviewSectionKey | null };

const SPECIALIST_LABEL: Record<string, string> = {
  fundamentals: "Fundamentals analyst",
  news_sentiment: "News analyst",
  market: "Market analyst",
  risk: "Risk analyst",
};

const HEADLINE: Record<Phase, string> = {
  idle: "",
  waking: "Waking up the research engine…",
  running: "Researching…",
  review: "Draft ready for your review",
  revising: "Revising with your feedback…",
  approving: "Finalizing the brief…",
  rejecting: "Recording your decision…",
  final: "Research complete",
  rejected: "Brief rejected",
  error: "The run stopped",
};

const LIVE: Phase[] = ["waking", "running", "revising", "approving", "rejecting"];
const BUSY_ACTION: Partial<Record<Phase, ReviewDecision>> = {
  revising: "revise",
  approving: "approve",
  rejecting: "reject",
};

const REVIEW_PANEL_ID = "review-panel";
const QUERY_INPUT_ID = "research-query";

const isSpecialist = (n: string) => (SPECIALISTS as readonly string[]).includes(n);

function subscribeOnline(cb: () => void) {
  window.addEventListener("online", cb);
  window.addEventListener("offline", cb);
  return () => {
    window.removeEventListener("online", cb);
    window.removeEventListener("offline", cb);
  };
}
const useOnline = () =>
  useSyncExternalStore(
    subscribeOnline,
    () => navigator.onLine,
    () => true,
  );

const ACTIONS = new Set(["approve", "revise", "reject", "auto_approve"]);

/** The server's review history is authoritative; local entries only fill in the
 *  `section` an older backend may not echo back. */
function mergeHistory(server: unknown, local: ReviewEntry[]): ReviewEntry[] | null {
  if (!Array.isArray(server) || !server.length) return null;
  const valid = server.filter(
    (h): h is ReviewHistoryItem => !!h && typeof h === "object" && ACTIONS.has((h as ReviewHistoryItem).action),
  );
  if (!valid.length) return null;
  return valid.map((h) => {
    const twin = local.find((l) => l.revision === h.revision && l.action === h.action);
    return { ...h, feedback: h.feedback ?? "", section: h.section ?? twin?.section ?? null };
  });
}

function doneSpecialists(): Partial<Steps> {
  return Object.fromEntries(SPECIALISTS.map((s) => [s, "done"])) as Partial<Steps>;
}

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
  const [error, setError] = useState<RunError | null>(null);
  const [errorDuring, setErrorDuring] = useState<"start" | "resume">("start");
  const [elapsed, setElapsed] = useState(0);
  const [showSample, setShowSample] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [engine, setEngine] = useState<EngineState>("checking");
  const online = useOnline();

  const cancelRef = useRef<(() => void) | null>(null);
  const wakeAbortRef = useRef<AbortController | null>(null);
  const threadRef = useRef<string>("");
  const lastOpRef = useRef<LastOp>({ kind: "start", query: "" });
  const startedRef = useRef(0);
  const revisionRef = useRef(0);
  const stepsBeforeRef = useRef<Steps>(IDLE_STEPS);
  // Every run / resume / reset takes a new token; callbacks from an older stream or
  // wake-up check compare tokens and quietly drop themselves.
  const tokenRef = useRef(0);

  const live = LIVE.includes(phase);

  // Warm the API in the background as soon as the page opens, so that by the time the
  // question is typed a sleeping free-tier server is already booting.
  useEffect(() => {
    const ctrl = new AbortController();
    ensureAwake({ signal: ctrl.signal, onSlow: () => setEngine("waking") }).then((r) => {
      if (r.ok) setEngine("ready");
      else if (r.failure.kind !== "aborted") setEngine(r.failure.kind === "offline" ? "offline" : "unreachable");
    });
    return () => ctrl.abort();
  }, []);

  // Tick the elapsed timer while anything is in flight so the UI never looks frozen.
  useEffect(() => {
    if (!live) return;
    const t = setInterval(() => setElapsed(Math.floor((Date.now() - startedRef.current) / 1000)), 1000);
    return () => clearInterval(t);
  }, [live]);

  // Close any open stream when leaving the page.
  useEffect(
    () => () => {
      cancelRef.current?.();
      wakeAbortRef.current?.abort();
    },
    [],
  );

  const since = () => Math.max(0, Math.floor((Date.now() - startedRef.current) / 1000));
  const log = (text: string) => setActivity((a) => [{ text, at: since() }, ...a].slice(0, 7));
  const setStep = (patch: Partial<Steps>) => setSteps((s) => ({ ...s, ...patch }));

  function stopAll() {
    cancelRef.current?.();
    cancelRef.current = null;
    wakeAbortRef.current?.abort();
    wakeAbortRef.current = null;
  }

  function beginClock() {
    startedRef.current = Date.now();
    setElapsed(0);
  }

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

  function fail(f: ApiFailure, token: number) {
    if (token !== tokenRef.current || f.kind === "aborted") return;
    const op = lastOpRef.current;
    const during = op.kind === "start" ? "start" : "resume";
    const e = describeFailure(f, during);
    cancelRef.current = null;
    setError(e);
    setErrorDuring(during);
    setHistory((h) => h.filter((x) => !x.pending));
    if (f.kind === "unreachable") setEngine("unreachable");
    if (during === "resume" && e.threadAlive) {
      // The draft is still waiting for a decision: put the review back as it was.
      setSteps(stepsBeforeRef.current);
      setPhase("review");
      log("Your decision didn't go through");
    } else {
      setSteps((s) => Object.fromEntries(Object.entries(s).map(([k, v]) => [k, v === "active" ? "error" : v])) as Steps);
      setPhase("error");
    }
  }

  const handlers = (token: number): StreamHandlers => {
    const current = () => token === tokenRef.current;
    return {
      onStart: (d) => {
        if (current() && d.thread_id) threadRef.current = d.thread_id;
      },
      onNode: (node: NodeName, data) => {
        if (!current()) return;
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
        if (!current()) return;
        cancelRef.current = null;
        if (d.thread_id) threadRef.current = d.thread_id;
        revisionRef.current = d.revision ?? revisionRef.current;
        setRevision(revisionRef.current);
        setPayload((p) => ({ ...(p ?? {}), ...d }));
        setHistory((h) => mergeHistory(d.review_history, h) ?? h.map((x) => ({ ...x, pending: false })));
        setSteps((s) => ({
          ...s,
          plan: "done",
          ...doneSpecialists(),
          debate: "done",
          writing: "done",
          review: "active",
          followup: s.followup === "idle" ? "idle" : "done",
        }));
        setPhase("review");
        log(revisionRef.current > 0 ? `Revision ${revisionRef.current} is ready for review` : "First draft is ready for review");
      },
      onFinal: (d) => {
        if (!current()) return;
        cancelRef.current = null;
        if (d.thread_id) threadRef.current = d.thread_id;
        if (typeof d.revision === "number") {
          revisionRef.current = d.revision;
          setRevision(d.revision);
        }
        const status = d.review_status || "auto_approved";
        setPayload((p) => ({ ...(p ?? {}), ...d }));
        setReviewStatus(status);
        setHistory((h) => mergeHistory(d.review_history, h) ?? h.map((x) => ({ ...x, pending: false })));
        setSteps(
          (s) =>
            Object.fromEntries(
              Object.entries(s).map(([k, v]) => [
                k,
                k === "followup" && v === "idle"
                  ? "idle"
                  : k === "review" && status === "rejected"
                    ? "error" // a rejected brief ends in red, not a success tick
                    : "done",
              ]),
            ) as Steps,
        );
        if (status === "rejected") {
          setPhase("rejected");
          log("Brief rejected; the run is closed");
        } else {
          setPhase("final");
          log(status === "auto_approved" ? "Brief finalized" : "Brief approved and finalized");
        }
      },
      onError: (f) => fail(f, token),
    };
  };

  /** Wait for the API to be awake; explains a cold start via `onSlow`. */
  async function wake(token: number, onSlow: () => void): Promise<boolean> {
    if (isWarm()) return true;
    const ctrl = new AbortController();
    wakeAbortRef.current = ctrl;
    const r = await ensureAwake({
      signal: ctrl.signal,
      onSlow: () => token === tokenRef.current && onSlow(),
    });
    if (token !== tokenRef.current) return false;
    wakeAbortRef.current = null;
    if (!r.ok) {
      fail(r.failure, token);
      return false;
    }
    setEngine("ready");
    return true;
  }

  async function run(q: string) {
    const text = q.trim();
    if (text.length < 3 || live) return;
    stopAll();
    const token = ++tokenRef.current;
    lastOpRef.current = { kind: "start", query: text };
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
    setSteps(IDLE_STEPS);
    setActivity([{ text: "Connecting to the research engine…", at: 0 }]);
    setPhase("running");

    let woke = false;
    const ok = await wake(token, () => {
      woke = true;
      setEngine("waking");
      setPhase("waking");
    });
    if (!ok) return;

    if (woke) log("The research engine is awake");
    setSteps({ ...IDLE_STEPS, plan: "active" });
    setPhase("running");
    log("Starting the research team…");
    threadRef.current = newThreadId();
    cancelRef.current = startResearch(text, { review: true, threadId: threadRef.current }, handlers(token));
  }

  async function resume(action: ReviewDecision, feedback = "", section: ReviewSectionKey | null = null) {
    if (!threadRef.current || phase !== "review") return;
    stopAll();
    const token = ++tokenRef.current;
    lastOpRef.current = { kind: "resume", action, feedback, section };
    stepsBeforeRef.current = steps;
    setError(null);
    setReviewOpen(false);
    beginClock();
    setHistory((h) => [
      ...h.filter((x) => !x.pending),
      {
        revision: revisionRef.current,
        action,
        feedback: action === "approve" ? "" : feedback,
        section: action === "approve" ? null : section,
        pending: true,
      },
    ]);
    if (action === "approve") {
      setStep({ review: "active" });
      setActivity([{ text: "Approval sent. Finalizing the brief…", at: 0 }]);
      setPhase("approving");
    } else if (action === "reject") {
      setStep({ review: "active" });
      setActivity([{ text: "Rejection sent. Closing the run…", at: 0 }]);
      setPhase("rejecting");
    } else {
      setStep({ followup: "active", writing: "idle", review: "idle" });
      setActivity([{ text: "Feedback sent. Researching it…", at: 0 }]);
      setPhase("revising");
    }

    const ok = await wake(token, () => log("Waking up the research engine (it naps when idle)…"));
    if (!ok) return;
    cancelRef.current = resumeResearch(threadRef.current, action, { feedback, section }, handlers(token));
  }

  function backToIdle() {
    stopAll();
    tokenRef.current++;
    setPhase("idle");
    setPayload(null);
    setError(null);
    setSteps(IDLE_STEPS);
    setActivity([]);
    setHistory([]);
    setCounts({});
    setReviewOpen(false);
    setAsked("");
  }

  function focusQuery() {
    requestAnimationFrame(() => {
      const el = document.getElementById(QUERY_INPUT_ID) as HTMLInputElement | null;
      el?.focus();
      el?.select();
    });
  }

  function recover(r: Recovery) {
    const op = lastOpRef.current;
    if (r === "retry") {
      if (op.kind === "start") run(op.query || asked || query);
      else resume(op.action, op.feedback, op.section);
    } else if (r === "back") {
      setError(null);
    } else if (r === "edit") {
      if (op.kind === "start" && op.query) setQuery(op.query);
      backToIdle();
      focusQuery();
    } else {
      backToIdle();
      focusQuery();
    }
  }

  function openReview() {
    setReviewOpen(true);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    document.getElementById(REVIEW_PANEL_ID)?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  }

  // ---- Derived view state -------------------------------------------------------
  const hasReport = !!payload && (!!payload.report_sections || !!payload.report);
  const compact = phase !== "idle";
  const busyAction = BUSY_ACTION[phase];
  const draftStale = !!busyAction;
  const approved = phase === "final";
  const rejected = phase === "rejected";
  const reviewClosed = phase === "error" && errorDuring === "resume";
  const sampleOn = showSample && !compact;
  const reviewError = phase === "review" && error ? error : null;
  const showMobileBar = hasReport && (phase === "review" || live);
  const sections = reviewableSections(payload?.report_sections).map((d) => ({ key: d.key, label: d.label }));
  const runMode: RunMode = phase === "waking" ? "waking" : phase === "error" ? "stopped" : live ? "live" : "settled";

  // Mark the section the latest feedback was about, while it is revised and once the
  // new draft is back.
  const lastRevise = [...history].reverse().find((h) => h.action === "revise");
  const flagDef = lastRevise ? sectionDef(lastRevise.section) : undefined;
  const flag =
    flagDef && (phase === "revising" || (phase === "review" && revision === lastRevise!.revision + 1))
      ? { block: flagDef.block, label: phase === "revising" ? "Revising per your feedback" : "Updated per your feedback" }
      : undefined;

  const statusBadge = approved ? (
    <span className={limePill}>
      <Icon name="check" className="h-3 w-3" strokeWidth={3} />
      {reviewStatus === "auto_approved" ? "Final" : "Approved"}
    </span>
  ) : rejected ? (
    <Badge tone="bad" dot surface="dark">
      Rejected
    </Badge>
  ) : reviewClosed ? (
    <Badge tone="muted" surface="dark">
      Draft · review closed
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
    reviewLabel: approved || phase === "approving" ? "Approval" : rejected ? "Rejected" : "Your review",
  };

  const reviewMode = approved
    ? "approved"
    : rejected
      ? "rejected"
      : reviewClosed
        ? "ended"
        : draftStale
          ? "busy"
          : "review";
  const showReviewPanel = phase === "review" || draftStale || approved || rejected || reviewClosed;

  return (
    <>
      <div className={cx("screen-only space-y-6", showMobileBar && "pb-28 lg:pb-0")}>
        <QueryBox
          query={query}
          setQuery={setQuery}
          onSubmit={() => run(query)}
          busy={live}
          busyLabel={phase === "waking" ? "Starting…" : "Working…"}
          compact={compact}
          engine={engine}
          offline={!online}
        />

        {!online && compact && (
          <p
            role="status"
            className="flex animate-enter items-center gap-2.5 rounded-xl border border-amber-200 bg-amber-50/80 px-4 py-3 text-sm text-amber-800"
          >
            <Icon name="alert" className="h-4 w-4 shrink-0 text-amber-600" />
            You&apos;re offline. Your work is safe here; reconnect to continue.
          </p>
        )}

        {!compact && <CorpusPanel />}

        {phase === "error" && error && <ErrorCard error={error} onAction={recover} />}

        {compact && !hasReport && (
          <>
            <ProgressStepper
              {...progressProps}
              question={asked}
              mode={runMode}
              onCancel={phase === "waking" || phase === "running" ? backToIdle : undefined}
            />
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
                  <ExportButton ready className={cx(btn.secondary, "w-full", tap)} />
                  <button type="button" onClick={() => setShowSample(false)} className={cx(btn.ghost, "w-full", tap)}>
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
                <RunCard
                  {...progressProps}
                  live={live}
                  outcome={approved ? "approved" : rejected ? "rejected" : phase === "error" ? "stopped" : undefined}
                />
                {reviewError && <ErrorCard error={reviewError} onAction={recover} compact />}
                {showReviewPanel && (
                  <ReviewPanel
                    id={REVIEW_PANEL_ID}
                    mode={reviewMode}
                    busyAction={busyAction}
                    revision={revision}
                    autoApproved={reviewStatus === "auto_approved"}
                    history={history}
                    sections={sections}
                    ns="run"
                    open={reviewOpen}
                    onOpenChange={setReviewOpen}
                    onApprove={() => resume("approve")}
                    onRevise={(f, s) => resume("revise", f, s)}
                    onReject={(reason) => resume("reject", reason)}
                  />
                )}
                <div className={cx(surface, "space-y-2 p-3")}>
                  <ExportButton ready={hasReport} className={cx(btn.secondary, "w-full", tap)} />
                  {(approved || rejected || phase === "error") && (
                    <button
                      type="button"
                      onClick={() => {
                        backToIdle();
                        focusQuery();
                      }}
                      className={cx(btn.ghost, "w-full", tap)}
                    >
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
                className="mb-4 flex animate-enter items-center gap-3 rounded-xl border border-indigo-200 bg-indigo-50/80 px-4 py-3 text-sm text-indigo-900"
              >
                <Spinner className="h-4 w-4 text-indigo-600" />
                <span className="min-w-0">
                  {phase === "revising"
                    ? "Revising this draft with your feedback. The new revision replaces it when ready."
                    : phase === "approving"
                      ? "Finalizing the approved brief…"
                      : "Closing the run. The draft stays here for reference."}
                </span>
                <span className="ml-auto hidden font-mono text-xs text-indigo-700 tabular-nums sm:inline">
                  {clock(elapsed)}
                </span>
              </div>
            )}
            <div className={cx("transition-opacity duration-500", phase === "revising" && "opacity-60")}>
              <StructuredReport
                payload={payload}
                ns="run"
                revision={revision}
                status={statusBadge}
                flag={flag}
                tocStickyClass="top-[4.75rem]"
              />
            </div>
          </ReportLayout>
        )}
      </div>

      {showMobileBar && (
        <div className="screen-only fixed inset-x-0 bottom-0 z-40 border-t border-slate-200/80 bg-surface/90 px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] shadow-[0_-12px_30px_-18px_rgb(15_23_42/0.35)] backdrop-blur-md lg:hidden">
          {phase === "review" && reviewError ? (
            <div className="flex items-center gap-3" role="alert">
              <Icon name="alert" className="h-4 w-4 shrink-0 text-rose-600" />
              <p className="min-w-0 flex-1 truncate text-sm font-medium text-slate-900">{reviewError.title}</p>
              {reviewError.actions.includes("retry") && (
                <button type="button" onClick={() => recover("retry")} className={cx(btn.primary, "shrink-0", tap)}>
                  <Icon name="refresh" />
                  Retry
                </button>
              )}
              <button type="button" onClick={() => recover("back")} className={cx(btn.ghost, "shrink-0", tap)}>
                Dismiss
              </button>
            </div>
          ) : phase === "review" ? (
            <div className="flex gap-2">
              <button type="button" onClick={() => resume("approve")} className={cx(btn.primary, "flex-1", tap)}>
                <Icon name="check" />
                Approve
              </button>
              <button type="button" onClick={openReview} className={cx(btn.secondary, "flex-1", tap)}>
                <Icon name="edit" />
                {revision >= MAX_REVISIONS ? "Review options" : "Request changes"}
              </button>
            </div>
          ) : (
            <p role="status" className="flex min-h-11 items-center gap-2.5 text-sm font-medium text-slate-800">
              <Spinner className="h-4 w-4 text-indigo-600" />
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
              : rejected
                ? "Rejected by reviewer"
                : "Draft, not yet approved"
            : "Sample data"
        }
      />
    </>
  );
}

const RECOVERY_LABEL: Record<Recovery, { text: string; icon?: IconName }> = {
  retry: { text: "Try again", icon: "refresh" },
  back: { text: "Back to the draft" },
  new: { text: "Start new research", icon: "arrowRight" },
  edit: { text: "Edit question", icon: "edit" },
};

/** A failure, said plainly, with the right way out as the primary button. */
function ErrorCard({
  error,
  onAction,
  compact = false,
}: {
  error: RunError;
  onAction: (r: Recovery) => void;
  compact?: boolean;
}) {
  const bad = error.tone === "bad";
  return (
    <div
      role="alert"
      className={cx(
        cardBase,
        "flex animate-enter gap-3",
        compact ? "flex-col p-4" : "flex-col p-4 sm:flex-row sm:items-center sm:p-5",
        bad ? "border-rose-200 bg-rose-50/70" : "border-amber-200 bg-amber-50/70",
      )}
    >
      <div className="flex min-w-0 flex-1 gap-3">
        <span
          className={cx(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-full",
            bad ? "bg-rose-100 text-rose-700" : "bg-amber-100 text-amber-700",
          )}
        >
          <Icon name="alert" />
        </span>
        <div className="min-w-0">
          <p className={cx("text-sm font-semibold", bad ? "text-rose-900" : "text-amber-950")}>{error.title}</p>
          {error.message && (
            <p className={cx("mt-0.5 text-sm leading-relaxed", bad ? "text-rose-800" : "text-amber-800")}>
              {error.message}
            </p>
          )}
        </div>
      </div>
      {error.actions.length > 0 && (
        <div className={cx("flex flex-wrap gap-2", compact ? "pl-12" : "sm:shrink-0")}>
          {error.actions.map((a, i) => {
            const l = RECOVERY_LABEL[a];
            return (
              <button
                key={a}
                type="button"
                onClick={() => onAction(a)}
                className={cx(i === 0 ? btn.primary : btn.secondary, tap)}
              >
                {l.icon && <Icon name={l.icon} />}
                {l.text}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

/** Report column + sticky right rail (review, run status, actions). On narrow screens
 *  the rail follows the report. */
function ReportLayout({ children, aside }: { children: React.ReactNode; aside: React.ReactNode }) {
  return (
    <div className="grid animate-enter items-start gap-6 lg:grid-cols-[minmax(0,1fr)_18.5rem] xl:gap-8">
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
    <div className="animate-enter space-y-3">
      <p className="flex items-center gap-2 text-sm text-slate-500">
        <Icon name="file" className="h-4 w-4" />
        Your brief takes shape here as soon as the writer finishes.
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

function EmptyState({ onSample }: { onSample: () => void }) {
  const steps: [IconName, string, string][] = [
    ["target", "Plan", "Atlas scopes your question and picks what to research."],
    ["users", "Research", "Four analysts cover financials, news, market and risk in parallel."],
    ["scale", "Debate", "A bull and a bear argue both sides of the evidence."],
    ["check", "Review", "You approve the cited draft, send it back with changes, or reject it."],
  ];
  return (
    <section aria-labelledby="empty-title" className={cx(surface, "animate-enter p-5 sm:p-7")}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className={eyebrow}>What happens next</p>
          <h2 id="empty-title" className="mt-2 text-lg font-semibold tracking-tight text-slate-950">
            Four steps from question to reviewed brief
          </h2>
        </div>
        <span className="font-mono text-xs text-slate-500">~2 min per run</span>
      </div>
      <ol className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {steps.map(([icon, t, d], i) => (
          <li key={t} className="rounded-2xl border border-slate-200/80 bg-slate-50/60 p-4">
            <div className="flex items-center justify-between">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-surface text-indigo-700 shadow-xs ring-1 ring-slate-200">
                <Icon name={icon} className="h-4.5 w-4.5" />
              </span>
              <span aria-hidden className="font-display text-2xl text-slate-300">
                {String(i + 1).padStart(2, "0")}
              </span>
            </div>
            <p className="mt-4 text-sm font-semibold text-slate-950">{t}</p>
            <p className="mt-1 text-sm leading-relaxed text-slate-600">{d}</p>
          </li>
        ))}
      </ol>
      <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-slate-200/80 pt-5">
        <button type="button" onClick={onSample} className={cx(btn.secondary, tap)}>
          <Icon name="file" />
          Preview a sample report
        </button>
        <span className="text-xs text-slate-500">Progress streams in live as each analyst finishes.</span>
      </div>
    </section>
  );
}
