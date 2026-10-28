// Typed client for the Atlas backend. Contract: docs/investor-platform-design.md §1 + §4.

export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ---------------------------------------------------------------------------
// Report schema (§1). Every field is optional: the UI renders what is present.
// Enum fields are typed loosely (`| string`) because they come from an LLM; the
// report components normalise unknown values to a neutral style.
// ---------------------------------------------------------------------------

export type Stance = "positive" | "neutral" | "cautious";
export type Level = "high" | "medium" | "low";
export type Tone = "positive" | "neutral" | "negative";
export type OverallSentiment = "positive" | "mixed" | "negative";

export type Metric = { label?: string; value?: string; change?: string; citation?: string };
export type Competitor = {
  name?: string;
  comparison?: string;
  threat?: Level | string;
  citation?: string;
};
export type Development = {
  date?: string;
  title?: string;
  detail?: string;
  sentiment?: Tone | string;
  citation?: string;
};
export type Risk = { title?: string; severity?: Level | string; detail?: string; citation?: string };

export type ReportSections = {
  company?: string;
  headline?: string;
  stance?: Stance | string;
  confidence?: number;
  executive_summary?: string[];
  company_overview?: {
    what_they_do?: string;
    business_model?: string;
    products?: string[];
    customers?: string;
  };
  financials?: { summary?: string; metrics?: Metric[] };
  market_position?: { summary?: string; strengths?: string[]; weaknesses?: string[] };
  competitors?: Competitor[];
  recent_developments?: Development[];
  sentiment?: { overall?: OverallSentiment | string; summary?: string };
  risks?: Risk[];
  bull_case?: string[];
  bear_case?: string[];
  outlook?: { summary?: string; watch_items?: string[] };
  bottom_line?: string;
  uncertainties?: string[];
};

export type Finding = { agent: string; claim: string; citation: string; confidence: number };
export type DebateTurn = { role: string; text: string; leaning?: string };
export type Citation = { citation: string; agent?: string };

/** The full result of a run (§4). */
export type ResearchPayload = {
  report: string;
  report_sections: ReportSections | null;
  confidence: number | null;
  uncertainties: string[];
  citations: Citation[];
  findings: Finding[];
  debate: DebateTurn[];
  plan: string[];
  target?: string;
};

export type ReviewRequired = ResearchPayload & { thread_id: string; revision: number };
export type FinalPayload = ResearchPayload & {
  thread_id: string;
  revision: number;
  review_status: string;
};

// Graph node names streamed as SSE event names (must match the backend graph, §3/§4).
export const NODE_EVENTS = [
  "recall",
  "supervisor",
  "fundamentals",
  "news_sentiment",
  "risk",
  "market",
  "debate_round",
  "synthesize",
  "human_review",
  "revise_research",
  "remember",
] as const;
export type NodeName = (typeof NODE_EVENTS)[number];

export const SPECIALISTS = ["fundamentals", "news_sentiment", "market", "risk"] as const;

export type StreamHandlers = {
  onStart?: (data: { query?: string; thread_id?: string }) => void;
  onNode?: (node: NodeName, data: Record<string, unknown>) => void;
  onReviewRequired?: (data: ReviewRequired) => void;
  onFinal?: (data: FinalPayload) => void;
  /** A friendly, user-facing message. */
  onError?: (message: string) => void;
};

const CONNECTION_ERROR =
  "We couldn't reach the Atlas research service. Check your connection and try again.";
// /research/resume answers 404/422 (not SSE) when the run is no longer paused, e.g. it
// expired or the server restarted. EventSource can't read that body, so say it plainly.
const RESUME_ERROR =
  "We couldn't continue this run. It may have expired or already finished. Try again, or start a new research run.";

function parse(raw: unknown): Record<string, unknown> {
  if (typeof raw !== "string" || !raw) return {};
  try {
    const v = JSON.parse(raw);
    return v && typeof v === "object" ? (v as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

/** Open an SSE stream and dispatch Atlas events. Closes itself on a terminal event
 *  (`review_required`, `final`, `error`). Returns a cancel fn. */
function openStream(url: string, h: StreamHandlers, fallbackError = CONNECTION_ERROR): () => void {
  const es = new EventSource(url);
  let done = false;
  const finish = () => {
    done = true;
    es.close();
  };

  es.addEventListener("start", (e) => h.onStart?.(parse((e as MessageEvent).data)));

  for (const node of NODE_EVENTS) {
    es.addEventListener(node, (e) => {
      if (!done) h.onNode?.(node, parse((e as MessageEvent).data));
    });
  }

  es.addEventListener("review_required", (e) => {
    finish();
    h.onReviewRequired?.(parse((e as MessageEvent).data) as unknown as ReviewRequired);
  });

  es.addEventListener("final", (e) => {
    finish();
    h.onFinal?.(parse((e as MessageEvent).data) as unknown as FinalPayload);
  });

  // `error` is both a server-sent event name (MessageEvent with data) and the
  // EventSource connection-failure event (plain Event). Handle both, once.
  es.addEventListener("error", (e) => {
    if (done) return;
    finish();
    const data = parse((e as MessageEvent).data);
    const msg = typeof data.error === "string" && data.error ? data.error : fallbackError;
    h.onError?.(msg);
  });

  return () => {
    done = true;
    es.close();
  };
}

/** A run id that works outside secure contexts too (randomUUID needs https/localhost). */
export function newThreadId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/** Start a run. With `review: true` the backend pauses with `review_required`. */
export function startResearch(
  query: string,
  opts: { review?: boolean; threadId?: string },
  h: StreamHandlers,
): () => void {
  const params = new URLSearchParams({
    q: query,
    thread_id: opts.threadId ?? newThreadId(),
    review: opts.review === false ? "0" : "1",
  });
  return openStream(`${API}/research/stream?${params}`, h);
}

/** Resume a paused run: approve the draft, or request a revision with feedback. */
export function resumeResearch(
  threadId: string,
  action: "approve" | "revise",
  feedback: string,
  h: StreamHandlers,
): () => void {
  const params = new URLSearchParams({ thread_id: threadId, action });
  if (action === "revise" && feedback.trim()) params.set("feedback", feedback.trim());
  return openStream(`${API}/research/resume?${params}`, h, RESUME_ERROR);
}
