// Inline citation handling. Evidence labels arrive as bracketed text inside report
// strings, e.g. "[Pricing | RevSquad (company_website#5575051) [web]]", possibly several
// per bracket separated by ";" (each with its own "[web]" / "[atlas-derived]"
// provenance marker). We turn them into small source chips that link to the Sources
// list instead of showing raw brackets.
//
// The number after "#" is a stable content hash, not a rank, so chips are numbered by
// order of first appearance in the report (see buildCitationNumbers), never by it.

export type Segment = { type: "text"; text: string } | { type: "cite"; label: string; key: string };

/** key ("company_website#5575051") -> display number within one report (1, 2, 3...). */
export type CitationNumbers = ReadonlyMap<string, number>;

// Provenance markers are stripped before matching (the backend verifier does the same),
// which leaves at most one level of brackets per citation group.
const MARKER_RE = /\s*\[(?:web|atlas-derived)\]/g;
// One bracket group that contains at least one `source#n` key.
const CITE_RE = /\[([^[\]]*?[A-Za-z0-9_.\-]+#\d+[^[\]]*?)\]/g;
const KEY_RE = /([A-Za-z0-9_.\-]+)#(\d+)/;

/** The stable `source#n` key inside a label (used for anchors). */
export function citationKey(label: string): string {
  const m = label.match(KEY_RE);
  return m ? `${m[1]}#${m[2]}` : label.trim();
}

/** DOM-safe anchor id for a citation key. */
export function sourceAnchor(ns: string, key: string): string {
  return `${ns}-src-${key.replace(/[^A-Za-z0-9_-]+/g, "-")}`;
}

// Specific kinds first: several of them contain "web" or "site" and would otherwise
// fall through to the generic Web rule.
const KIND: [RegExp, string][] = [
  [/website_audit/i, "Site check"],
  [/asker_website/i, "Your site"],
  [/company_website/i, "Site"],
  [/employee_reviews/i, "Employees"],
  [/reviews/i, "Reviews"],
  [/linkedin/i, "LinkedIn"],
  [/funding/i, "Funding"],
  [/alternatives/i, "Alternatives"],
  [/sec|edgar|10-?k|filing/i, "SEC"],
  [/news/i, "News"],
  [/web|tavily|(?:^|_)search/i, "Web"], // not "research"
  [/stock|market|stooq|quote/i, "Market"],
  [/memory|episod|derived/i, "Memory"],
  [/research|profile|report/i, "Research"],
  [/upload|doc|corpus|file/i, "Doc"],
];

/** The source type as a short label ("Site", "Reviews", "SEC"). */
export function sourceKind(key: string): string {
  const m = key.match(KEY_RE);
  if (!m) return "Source";
  const source = m[1];
  return KIND.find(([re]) => re.test(source))?.[1] ?? source.replace(/[_-]+/g, " ").slice(0, 14);
}

/** A short chip label, e.g. "Site 3". The number is the key's position in the report
 *  (from `nums`); without a map the label is just the kind. */
export function chipLabel(key: string, nums?: CitationNumbers): string {
  const n = nums?.get(key);
  return n ? `${sourceKind(key)} ${n}` : sourceKind(key);
}

/** "a#0; b#1" -> ["a#0", "b#1"], without breaking titles that contain commas. */
function splitGroup(inner: string): string[] {
  const out: string[] = [];
  let buf = "";
  for (const part of inner.split(/([;,])/)) {
    buf += part;
    if (KEY_RE.test(buf) && !/^[;,]$/.test(part)) {
      out.push(buf.replace(/^[;,\s]+/, "").trim());
      buf = "";
    }
  }
  if (buf.trim() && out.length) out[out.length - 1] += buf.replace(/[;,\s]+$/, "");
  else if (buf.trim()) out.push(buf.trim());
  return out;
}

/** Split text into plain segments and citation segments. Multi-citation groups like
 *  "[sec_edgar#0; news#1]" become one chip per key. */
// Some models cite with CJK lenticular brackets ("【web_search#0】"); the API now
// normalises them, but reports saved before that still carry them.
const FULLWIDTH_RE = /[【［]|[】］]/g;

export function splitCitations(raw: string): Segment[] {
  const text = raw.replace(FULLWIDTH_RE, (c) => (c === "【" || c === "［" ? "[" : "]")).replace(MARKER_RE, "");
  const out: Segment[] = [];
  let last = 0;
  for (const m of text.matchAll(CITE_RE)) {
    const idx = m.index ?? 0;
    if (idx > last) out.push({ type: "text", text: text.slice(last, idx) });
    for (const p of splitGroup(m[1])) out.push({ type: "cite", label: p, key: citationKey(p) });
    last = idx + m[0].length;
  }
  if (last < text.length) out.push({ type: "text", text: text.slice(last) });
  // Tidy the space before a chip.
  return out
    .map((s, i, arr) =>
      s.type === "text" && arr[i + 1]?.type === "cite" ? { ...s, text: s.text.replace(/\s+$/, " ") } : s,
    )
    .filter((s) => s.type === "cite" || s.text.length > 0);
}

/** Rewrite citation brackets in markdown into chip links, for the markdown fallback. */
export function linkCitationsInMarkdown(md: string, ns: string, nums?: CitationNumbers): string {
  return md.replace(MARKER_RE, "").replace(CITE_RE, (_all, inner: string) =>
    splitGroup(inner)
      .map((p) => {
        const key = citationKey(p);
        return `[${chipLabel(key, nums)}](#${sourceAnchor(ns, key)} "${p.replace(/"/g, "'")}")`;
      })
      .join(" "),
  );
}

/** Keys cited in a string, in order (duplicates kept). */
export function citedKeys(text: string): string[] {
  return splitCitations(text).flatMap((s) => (s.type === "cite" ? [s.key] : []));
}

/** Number every cited key by order of first appearance across `texts` (pass them in
 *  reading order). Pure and deterministic, so server, client and print agree. */
export function buildCitationNumbers(texts: Iterable<string>): CitationNumbers {
  const nums = new Map<string, number>();
  for (const t of texts) {
    if (!t) continue;
    for (const k of citedKeys(t)) if (!nums.has(k)) nums.set(k, nums.size + 1);
  }
  return nums;
}

/** Placeholder the synthesizer uses when it has no evidence for a field. */
export function isPlaceholder(s: string | undefined | null): boolean {
  return !!s && /^\s*not enough evidence/i.test(s);
}

export function hasText(s: string | undefined | null): s is string {
  return typeof s === "string" && s.trim().length > 0;
}

export function nonEmpty<T>(arr: T[] | undefined | null): arr is T[] {
  return Array.isArray(arr) && arr.length > 0;
}
