"use client";

import { useRef, useState } from "react";
import { AgentGraph, type NodeStatus } from "@/components/AgentGraph";
import { ConfidenceDial } from "@/components/ConfidenceDial";
import { CorpusPanel } from "@/components/CorpusPanel";
import { DebatePanel } from "@/components/DebatePanel";
import { ExportButton } from "@/components/ExportButton";
import { FindingsList } from "@/components/FindingsList";
import { PrintableReport } from "@/components/PrintableReport";
import { ReportView } from "@/components/ReportView";
import {
  type Citation,
  type DebateTurn,
  type Finding,
  NODES,
  type ResearchResult,
  runResearch,
} from "@/lib/api";

const SPECIALISTS = ["fundamentals", "news_sentiment", "risk", "market"];
const SAMPLES = [
  "Evaluate Helios Robotics as a competitor",
  "What are Helios Robotics' biggest risks?",
  "Compare Helios Robotics and Aster Dynamics",
];

function freshStatuses(): Record<string, NodeStatus> {
  return Object.fromEntries(NODES.map((n) => [n, "idle"]));
}

export default function Home() {
  const [query, setQuery] = useState(SAMPLES[0]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [statuses, setStatuses] = useState<Record<string, NodeStatus>>(freshStatuses());
  const [plan, setPlan] = useState<string[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [debate, setDebate] = useState<DebateTurn[]>([]);
  const [report, setReport] = useState("");
  const [confidence, setConfidence] = useState<number | null>(null);
  const [uncertainties, setUncertainties] = useState<string[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);

  const cancelRef = useRef<(() => void) | null>(null);

  function start() {
    if (running || query.trim().length < 3) return;
    cancelRef.current?.();
    setRunning(true);
    setError(null);
    setStatuses({ ...freshStatuses(), supervisor: "active" });
    setPlan([]);
    setFindings([]);
    setDebate([]);
    setReport("");
    setConfidence(null);
    setUncertainties([]);
    setCitations([]);

    cancelRef.current = runResearch(query.trim(), {
      onNode: (node, data) => {
        if (node === "supervisor") {
          setStatuses((s) => {
            const next: Record<string, NodeStatus> = { ...s, supervisor: "done" };
            SPECIALISTS.forEach((sp) => (next[sp] = "active"));
            return next;
          });
          if (Array.isArray(data.plan)) setPlan(data.plan as string[]);
        } else if (SPECIALISTS.includes(node)) {
          if (Array.isArray(data.findings))
            setFindings((f) => [...f, ...(data.findings as Finding[])]);
          setStatuses((s) => {
            const next: Record<string, NodeStatus> = { ...s, [node]: "done" };
            if (SPECIALISTS.every((sp) => next[sp] === "done")) next.debate_round = "active";
            return next;
          });
        } else if (node === "debate_round") {
          if (Array.isArray(data.debate)) setDebate(data.debate as DebateTurn[]);
          setStatuses((s) => ({ ...s, debate_round: "done", synthesize: "active" }));
        } else if (node === "synthesize") {
          setStatuses((s) => ({ ...s, synthesize: "done" }));
          if (typeof data.report === "string") setReport(data.report);
          if (typeof data.confidence === "number") setConfidence(data.confidence);
          if (Array.isArray(data.uncertainties)) setUncertainties(data.uncertainties as string[]);
          if (Array.isArray(data.citations)) setCitations(data.citations as Citation[]);
        }
      },
      onFinal: (d: ResearchResult) => {
        setReport(d.report ?? "");
        setConfidence(d.confidence ?? null);
        setUncertainties(d.uncertainties ?? []);
        setCitations(d.citations ?? []);
        if (d.findings?.length) setFindings(d.findings);
        if (d.debate?.length) setDebate(d.debate);
        setStatuses((s) => Object.fromEntries(Object.keys(s).map((k) => [k, "done"])));
        setRunning(false);
      },
      onError: () => {
        setError("Stream error — is the backend running on :8000?");
        setRunning(false);
      },
    });
  }

  return (
    <>
      <main className="screen-only mx-auto max-w-6xl px-5 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">
          Atlas <span className="text-sky-400">·</span>{" "}
          <span className="text-slate-300">Due-Diligence War Room</span>
        </h1>
        <p className="mt-1 text-sm text-slate-400">
          A team of AI agents researches, debates bull vs bear, and writes a cited brief — live.
        </p>
      </header>

      <div className="mb-4 flex flex-col gap-2 sm:flex-row">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && start()}
          placeholder="Ask about a company or market…"
          className="flex-1 rounded-lg border border-slate-700 bg-slate-900/70 px-4 py-2.5 text-sm outline-none focus:border-sky-500"
        />
        <button
          onClick={start}
          disabled={running}
          className="rounded-lg bg-sky-500 px-5 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-sky-400 disabled:opacity-50"
        >
          {running ? "Researching…" : "Run analysis"}
        </button>
      </div>
      <div className="mb-6 flex flex-wrap gap-2">
        {SAMPLES.map((s) => (
          <button
            key={s}
            onClick={() => setQuery(s)}
            className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-400 hover:border-slate-500 hover:text-slate-200"
          >
            {s}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-700/50 bg-red-500/10 p-3 text-sm text-red-200">
          {error}
        </div>
      )}

      <div className="mb-6">
        <CorpusPanel />
      </div>

      <section className="mb-6 rounded-xl border border-slate-800 bg-slate-950/50 p-4">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-500">
          Agent pipeline
        </h2>
        <AgentGraph statuses={statuses} />
        {plan.length > 0 && (
          <div className="mt-3 text-xs text-slate-500">
            <span className="text-slate-400">Plan:</span> {plan.join(" · ")}
          </div>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="space-y-6 lg:col-span-2">
          <Panel title="Synthesized brief" action={<ExportButton ready={Boolean(report)} />}>
            <ReportView report={report} uncertainties={uncertainties} citations={citations} />
          </Panel>
          <Panel title="Bull vs Bear debate">
            <DebatePanel debate={debate} />
          </Panel>
        </section>

        <section className="space-y-6">
          <Panel title="Verdict confidence">
            <div className="flex justify-center py-2">
              <ConfidenceDial value={confidence} />
            </div>
          </Panel>
          <Panel title={`Findings${findings.length ? ` (${findings.length})` : ""}`}>
            <FindingsList findings={findings} />
          </Panel>
        </section>
      </div>

      <footer className="mt-10 text-center text-xs text-slate-600">
        Groq Llama 3.3 70B · LangGraph · Hybrid RAG · traced in Langfuse
      </footer>
      </main>

      {/* Paper version — hidden on screen, rendered only by the print dialog. */}
      <PrintableReport
        query={query}
        report={report}
        confidence={confidence}
        findings={findings}
        uncertainties={uncertainties}
        citations={citations}
        debate={debate}
      />
    </>
  );
}

function Panel({
  title,
  action,
  children,
}: {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-500">{title}</h2>
        {action}
      </div>
      {children}
    </div>
  );
}
