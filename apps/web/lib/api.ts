// Typed client for the Atlas backend SSE research stream.

export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type Finding = { agent: string; claim: string; citation: string; confidence: number };
export type DebateTurn = { role: string; text: string; leaning?: string };
export type Citation = { citation: string; agent?: string };

export type ResearchResult = {
  report: string;
  confidence: number | null;
  uncertainties: string[];
  citations: Citation[];
  findings: Finding[];
  debate: DebateTurn[];
  plan: string[];
};

// Graph node names (must match the backend graph).
export const NODES = [
  "supervisor",
  "fundamentals",
  "news_sentiment",
  "risk",
  "market",
  "debate_round",
  "synthesize",
] as const;
export type NodeName = (typeof NODES)[number];

export const NODE_LABELS: Record<string, string> = {
  supervisor: "Supervisor",
  fundamentals: "Fundamentals",
  news_sentiment: "News & Sentiment",
  risk: "Risk",
  market: "Market / Competitor",
  debate_round: "Bull vs Bear",
  synthesize: "Synthesizer",
};

export type Handlers = {
  onStart?: (query: string) => void;
  onNode?: (node: string, data: Record<string, unknown>) => void;
  onFinal?: (data: ResearchResult) => void;
  onError?: (e: unknown) => void;
};

/** Open the SSE stream and dispatch per-agent events. Returns a cancel fn. */
export function runResearch(query: string, h: Handlers): () => void {
  const url = `${API}/research/stream?q=${encodeURIComponent(query)}&thread_id=${Date.now()}`;
  const es = new EventSource(url);
  let finished = false;

  const events = ["start", ...NODES, "final"];
  for (const ev of events) {
    es.addEventListener(ev, (e: MessageEvent) => {
      let data: Record<string, unknown> = {};
      try {
        data = JSON.parse(e.data);
      } catch {
        /* ignore malformed */
      }
      if (ev === "start") h.onStart?.(String(data.query ?? query));
      else if (ev === "final") {
        finished = true;
        h.onFinal?.(data as unknown as ResearchResult);
        es.close();
      } else h.onNode?.(ev, data);
    });
  }

  es.onerror = (e) => {
    if (!finished) h.onError?.(e);
    es.close();
  };

  return () => es.close();
}
