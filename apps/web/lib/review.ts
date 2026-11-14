// Which report sections a reviewer can aim feedback at, and how they map onto the
// rendered brief. Kept free of React so both the client review panel and the server-
// rendered report can use it.

import type { ReportSections, ReviewAction, ReviewSectionKey } from "./api";

type SectionDef = {
  key: ReviewSectionKey;
  /** Short chip label. */
  label: string;
  /** Block id used by StructuredReport (anchor = `${ns}-${block}`). */
  block: string;
  present: (s: ReportSections) => boolean;
};

const text = (v: unknown) => typeof v === "string" && v.trim().length > 0;
const some = (v: string[] | undefined) => Array.isArray(v) && v.some(text);

// In reading order (the order StructuredReport renders them).
export const REVIEW_SECTIONS: SectionDef[] = [
  {
    key: "verdict",
    label: "Verdict",
    block: "verdict",
    present: (s) => text(s.verdict?.answer) || text(s.verdict?.recommendation),
  },
  {
    key: "snapshot",
    label: "Snapshot",
    block: "snapshot",
    present: (s) => (s.snapshot ?? []).some((f) => text(f?.label) && text(f?.value)),
  },
  {
    key: "head_to_head",
    label: "Head to head",
    block: "head-to-head",
    present: (s) => text(s.head_to_head?.asker) && (text(s.head_to_head?.summary) || (s.head_to_head?.rows ?? []).length > 0),
  },
  {
    key: "custom_answers",
    label: "Your questions",
    block: "answers",
    present: (s) => (s.custom_answers ?? []).some((a) => text(a?.question) && text(a?.answer)),
  },
  {
    key: "company_overview",
    label: "Overview",
    block: "overview",
    present: (s) => {
      const o = s.company_overview;
      return !!o && (text(o.what_they_do) || text(o.business_model) || text(o.customers) || some(o.products));
    },
  },
  {
    key: "pricing",
    label: "Pricing",
    block: "pricing",
    present: (s) => text(s.pricing?.summary) || (s.pricing?.plans ?? []).some((p) => text(p?.name) || text(p?.price)),
  },
  {
    key: "financials",
    label: "Financials",
    block: "financials",
    present: (s) =>
      !!s.financials &&
      (text(s.financials.summary) || (s.financials.metrics ?? []).some((m) => text(m?.value) || text(m?.label))),
  },
  {
    key: "strengths",
    label: "Strengths",
    block: "strengths",
    present: (s) => some(s.strengths),
  },
  {
    key: "weaknesses",
    label: "Weaknesses",
    block: "strengths",
    present: (s) => some(s.weaknesses),
  },
  {
    key: "market_position",
    label: "Market position",
    block: "market",
    present: (s) =>
      !!s.market_position &&
      (text(s.market_position.summary) || some(s.market_position.strengths) || some(s.market_position.weaknesses)),
  },
  {
    key: "competitors",
    label: "Competitors",
    block: "competitors",
    present: (s) => (s.competitors ?? []).some((c) => text(c?.name)),
  },
  {
    key: "recent_developments",
    label: "News",
    block: "developments",
    present: (s) => (s.recent_developments ?? []).some((d) => text(d?.title) || text(d?.detail)),
  },
  {
    key: "risks",
    label: "Risks",
    block: "risks",
    present: (s) => (s.risks ?? []).some((r) => text(r?.title) || text(r?.detail)),
  },
  {
    key: "outlook",
    label: "Outlook",
    block: "outlook",
    present: (s) => !!s.outlook && (text(s.outlook.summary) || some(s.outlook.watch_items)),
  },
];

/** Sections present in this draft, in reading order. */
export function reviewableSections(s: ReportSections | null | undefined): SectionDef[] {
  if (!s) return [];
  return REVIEW_SECTIONS.filter((d) => d.present(s));
}

export function sectionDef(key: string | null | undefined): SectionDef | undefined {
  return key ? REVIEW_SECTIONS.find((d) => d.key === key) : undefined;
}

/** Human label for a section key, falling back to a tidy version of the raw key. */
export function sectionLabel(key: string | null | undefined): string {
  if (!key) return "";
  return sectionDef(key)?.label ?? key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

export const ACTION_LABEL: Record<ReviewAction, string> = {
  approve: "Approved",
  revise: "Changes requested",
  reject: "Rejected",
  auto_approve: "Approved automatically",
};

export function draftName(revision: number): string {
  return revision <= 0 ? "first draft" : `revision ${revision}`;
}

/** "on the first draft" / "on revision 2" (history lines). */
export function onDraft(revision: number): string {
  return revision <= 0 ? "on the first draft" : `on revision ${revision}`;
}
