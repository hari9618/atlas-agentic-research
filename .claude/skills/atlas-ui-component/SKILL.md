---
name: atlas-ui-component
description: >
  Build a war-room UI component for the Atlas frontend the Atlas way — Next.js App
  Router, Tailwind + shadcn/ui, server components by default, and SSE consumption
  for live agent events. Use when the frontend-engineer adds a view/component such
  as the live agent graph, streaming debate panel, report+citations view, confidence
  dial, or Langfuse cost panel. Primarily for the frontend-engineer subagent.
---

# Skill: Atlas war-room UI component

## 1. Pick the rendering model
- Static/layout → **server component** (default, no directive).
- Needs state, effects, or live streams → add `"use client"` at the top.

## 2. Use shadcn primitives
Add components via the CLI rather than hand-rolling:
```bash
npx shadcn@latest add card badge progress scroll-area tabs
```
Compose with Tailwind utilities. Keep a consistent "war-room" look: dark surface,
status colors (idle/active/done), monospace for transcripts.

## 3. Consume the backend SSE stream (live agents)
```tsx
"use client";
import { useEffect, useState } from "react";

export function AgentStream({ query }: { query: string }) {
  const [events, setEvents] = useState<{event:string; data:string}[]>([]);
  useEffect(() => {
    const url = `${process.env.NEXT_PUBLIC_API_URL}/research`; // POST→SSE via fetch stream
    const es = new EventSource(`${url}?q=${encodeURIComponent(query)}`);
    es.onmessage = (e) => setEvents((p) => [...p, JSON.parse(e.data)]);
    es.addEventListener("status", (e) =>
      setEvents((p) => [...p, { event: "status", data: (e as MessageEvent).data }]));
    return () => es.close();
  }, [query]);
  return /* render events into the agent graph / debate transcript */ null;
}
```

## 4. The signature views (keep these crisp — they're the demo)
- **Agent graph**: nodes per agent; light up active, dim idle, check done.
- **Debate transcript**: bull (green) vs bear (red), streamed line by line.
- **Report**: markdown with clickable inline citations + a confidence dial.
- **Cost panel**: per-run tokens + $ pulled from the Langfuse-backed endpoint.

## 5. Conventions
- API base URL from `process.env.NEXT_PUBLIC_API_URL` — never hardcode.
- Keep client bundles lean; push data-fetching to server components where possible.
- Responsive + accessible (this is the screenshot recruiters see).

## 6. Verify
- `npm run lint` and `npm run build` pass.
- Report what renders, the route it lives on, and any new env var.
