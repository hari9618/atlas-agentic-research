// Labels for the persona-aware brief: who asked, and how to say it in one line.
// Pure, so the server-rendered report and the client both use it.

import type { Brief } from "./api";

const PERSONA: Record<string, { label: string; short: string }> = {
  investor: { label: "Investor view", short: "Investor view" },
  competitor: { label: "Competitor check", short: "Competitor check" },
  buyer: { label: "Buyer evaluation", short: "Buyer evaluation" },
  partner: { label: "Partner check", short: "Partner check" },
  job_seeker: { label: "Job seeker view", short: "Job seeker view" },
  general: { label: "Company research", short: "Brief" },
};

const text = (v: unknown): v is string => typeof v === "string" && v.trim().length > 0;

export function personaLabel(persona: string | undefined): string {
  const key = (persona ?? "").toLowerCase().trim();
  return PERSONA[key]?.label ?? (key ? key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()) : "Brief");
}

/** "Competitor check for CaughtLeads · revsquad.ai", "Investor view · linear.app". */
export function briefLine(b: Brief | undefined): string {
  if (!b) return "";
  const parts: string[] = [];
  const persona = text(b.persona) ? personaLabel(b.persona) : "";
  if (persona) parts.push(text(b.asker) ? `${persona} for ${b.asker.trim()}` : persona);
  else if (text(b.asker)) parts.push(`For ${b.asker.trim()}`);
  if (text(b.subject_domain)) parts.push(b.subject_domain.trim());
  return parts.join(" · ");
}

/** Short heading for the document strip ("Competitor check", "Brief"). */
export function briefKind(b: Brief | undefined): string {
  const key = (b?.persona ?? "").toLowerCase().trim();
  return PERSONA[key]?.short ?? "Brief";
}
