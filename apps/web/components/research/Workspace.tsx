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
import { SAMPLE_PAYLOAD } from "@/lib/sample-report";
import { ExportButton } from "@/components/report/ExportButton";
import { PrintableReport } from "@/components/report/PrintableReport";
import { StructuredReport } from "@/components/report/StructuredReport";
import { Badge } from "@/components/ui/Badge";
import { Icon, type IconName } from "@/components/ui/Icon";
import { btn, card, cardBase, cx, eyebrow } from "@/components/ui/styles";
import { CorpusPanel } from "./CorpusPanel";
import { IDLE_STEPS, ProgressStepper, type StepId, type Steps } from "./ProgressStepper";
import { QueryBox } from "./QueryBox";
import { ReviewPanel, type ReviewEntry } from "./ReviewPanel";

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

const isSpecialist = (n: string) => (SPECIALISTS as readonly string[]).includes(n);

export function Workspace({ initialQuery = "" }: { initialQuery?: string }) {
  const [query, setQuery] = useState(initialQuery);
  const [asked, setAsked] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [steps, setSteps] = useState<Steps>(IDLE_STEPS);
  const [counts, setCounts] = useState<Partial<Record<StepId, number>>>({});
  const [activity, setActivity] = useState<string[]>([]);
  const [payload, setPayload] = useState<Partial<ResearchPayload> | null>(null);
  const [revision, setRevision] = useState(0);
  const [reviewStatus, setReviewStatus] = useState<string>("");
  const [history, setHistory] = useState<ReviewEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [showSample, setShowSample] = useState(false);

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

  const log = (line: string) => setActivity((a) => [line, ...a].slice(0, 6));
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
    setAsked(text);
    setShowSample(false);
    setError(null);
    setPayload(null);
    setRevision(0);
    setReviewStatus("");
    setHistory([]);
    setCounts({});
    setActivity(["Starting the research team…"]);
    setSteps({ ...IDLE_STEPS, plan: "active" });
    setPhase("running");
    beginClock();
    cancelRef.current = startResearch(text, { review: true, threadId: threadRef.current }, handlers());
  }

  function resume(action: "approve" | "revise", feedback = "") {
    if (!threadRef.current || live) return;
    cancelRef.current?.();
    lastOpRef.current = { kind: "resume", action, feedback };
    setError(null);
    beginClock();
    if (action === "approve") {
      setHistory((h) => [...h, { revision: revisionRef.current, action, feedback: "" }]);
      setStep({ review: "active" });
      setActivity(["Finalizing your approved report…"]);
      setPhase("approving");
    } else {
      setHistory((h) => [...h, { revision: revisionRef.current + 1, action, feedback }]);
      setStep({ followup: "active", writing: "idle", review: "idle" });
      setActivity(["Researching your feedback…"]);
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
    setAsked("");
  }

  const hasReport = !!payload && (!!payload.report_sections || !!payload.report);
  const showProgress = phase !== "idle";
  const draftStale = phase === "revising" || phase === "approving";
  const approved = phase === "final";
  const statusBadge = approved ? (
    <Badge tone="good" dot>
      {reviewStatus === "auto_approved" ? "Final" : "Approved"}
    </Badge>
  ) : hasReport && phase !== "running" ? (
    <Badge tone="mid">Draft · awaiting review</Badge>
  ) : null;

  return (
    <>
      <div className="screen-only space-y-6">
        <QueryBox query={query} setQuery={setQuery} onSubmit={() => run(query)} busy={live} />
        <CorpusPanel />

        {phase === "error" && error && (
          <div role="alert" className={cx(cardBase, "flex flex-col gap-3 border-rose-200 bg-rose-50/60 p-4 sm:flex-row sm:items-center")}>
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

        {showProgress && (
          <ProgressStepper
            steps={steps}
            counts={counts}
            headline={HEADLINE[phase]}
            elapsed={live ? elapsed : undefined}
            activity={activity}
            showFollowup={history.some((h) => h.action === "revise")}
            reviewLabel={phase === "approving" || approved ? "Approval" : "Your review"}
          />
        )}

        {!showProgress && !showSample && <EmptyState onSample={() => setShowSample(true)} />}

        {showSample && !showProgress && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm text-slate-600">
                A sample brief built from the demo documents. Run your own question above.
              </p>
              <button type="button" onClick={() => setShowSample(false)} className={btn.ghost}>
                Hide sample
              </button>
            </div>
            <StructuredReport payload={SAMPLE_PAYLOAD} ns="sample" label="Sample" />
          </div>
        )}

        {hasReport && payload && (
          <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
            <div className={cx("min-w-0 transition-opacity", draftStale && phase === "revising" && "opacity-60")}>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <p className="min-w-0 truncate text-sm text-slate-500">
                  <span className="font-medium text-slate-700">Question:</span> {asked}
                </p>
                <ExportButton ready={hasReport} />
              </div>
              <StructuredReport payload={payload} ns="run" revision={revision} status={statusBadge} />
            </div>
            <aside className="space-y-4 lg:sticky lg:top-20">
              {(phase === "review" || draftStale || approved) && (
                <ReviewPanel
                  mode={approved ? "approved" : draftStale ? "busy" : "review"}
                  revision={revision}
                  autoApproved={reviewStatus === "auto_approved"}
                  history={history}
                  onApprove={() => resume("approve")}
                  onRevise={(f) => resume("revise", f)}
                />
              )}
              {approved && (
                <button type="button" onClick={reset} className={cx(btn.secondary, "w-full")}>
                  Start new research
                </button>
              )}
            </aside>
          </div>
        )}
      </div>

      <PrintableReport
        query={asked}
        payload={hasReport ? payload : null}
        revision={revision}
        status={approved ? (reviewStatus === "auto_approved" ? "Final" : "Approved") : "Draft, not yet approved"}
      />
    </>
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
    <section aria-labelledby="empty-title" className={cx(card, "p-5 sm:p-7")}>
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
