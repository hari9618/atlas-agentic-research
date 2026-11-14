// Chip numbering for one report: every source gets 1, 2, 3... by where it is first
// cited, reading the brief top to bottom. The same map feeds the inline chips, the
// Sources list and the PDF, so a source has one number everywhere in that report.

import type { ResearchPayload } from "./api";
import { buildCitationNumbers, citationKey, type CitationNumbers } from "./citations";

// Reading order of report_sections (header first, then the blocks as rendered).
const ORDER = [
  "headline",
  "financials",
  "bottom_line",
  "verdict",
  "snapshot",
  "executive_summary",
  "head_to_head",
  "custom_answers",
  "company_overview",
  "pricing",
  "strengths",
  "weaknesses",
  "market_position",
  "competitors",
  "recent_developments",
  "sentiment",
  "risks",
  "bull_case",
  "bear_case",
  "outlook",
  "uncertainties",
];

/** Every string inside a value, depth first, in key order. */
function* strings(v: unknown): Generator<string> {
  if (typeof v === "string") yield v;
  else if (Array.isArray(v)) for (const x of v) yield* strings(x);
  else if (v && typeof v === "object") for (const x of Object.values(v)) yield* strings(x);
}

export function reportCitationNumbers(p: Partial<ResearchPayload> | null | undefined): CitationNumbers {
  if (!p) return new Map();
  const s = (p.report_sections ?? {}) as Record<string, unknown>;
  function* texts() {
    for (const k of ORDER) yield* strings(s[k]);
    for (const k of Object.keys(s)) if (!ORDER.includes(k)) yield* strings(s[k]);
    yield* strings(p!.uncertainties);
    if (p!.report) yield p!.report;
    yield* strings(p!.findings);
  }
  const nums = new Map(buildCitationNumbers(texts()));
  // Sources that are listed but never cited inline still get a number, after the rest.
  for (const c of p.citations ?? []) {
    const key = c?.citation ? citationKey(c.citation.replace(/\s*\[(?:web|atlas-derived)\]/g, "")) : "";
    if (key && !nums.has(key)) nums.set(key, nums.size + 1);
  }
  return nums;
}
