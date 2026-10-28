// Inline citation handling. Evidence labels arrive as bracketed text inside report
// strings, e.g. "[sec_edgar#0]" or "[Helios 10-K (sec_edgar#1)]" (optionally with a
// trailing "[web]" / "[atlas-derived]" provenance marker). We turn them into small
// source chips that link to the Sources list instead of showing raw brackets.

export type Segment = { type: "text"; text: string } | { type: "cite"; label: string; key: string };

// One bracket group that contains a `source#n` key, with an optional provenance marker.
const CITE_RE = /\[([^[\]]*?[A-Za-z0-9_.\-]+#\d+[^[\]]*?)(?:\s*\[(?:web|atlas-derived)\])?\]/g;
const KEY_RE = /([A-Za-z0-9_.\-]+)#(\d+)/;
const STRAY_MARKER_RE = /\s*\[(?:web|atlas-derived)\]/g;

/** The stable `source#n` key inside a label (used for anchors). */
export function citationKey(label: string): string {
  const m = label.match(KEY_RE);
  return m ? `${m[1]}#${m[2]}` : label.trim();
}

/** DOM-safe anchor id for a citation key. */
export function sourceAnchor(ns: string, key: string): string {
  return `${ns}-src-${key.replace(/[^A-Za-z0-9_-]+/g, "-")}`;
}

const KIND: [RegExp, string][] = [
  [/sec|edgar|10-?k|filing/i, "SEC"],
  [/news/i, "News"],
  [/web|tavily|search/i, "Web"],
  [/stock|market|stooq|quote/i, "Market"],
  [/memory|episod|derived/i, "Memory"],
  [/research|profile|report/i, "Research"],
  [/upload|doc|corpus|file/i, "Doc"],
];

/** A short human label for the source type, e.g. "SEC 1", "News 2". */
export function chipLabel(key: string): string {
  const m = key.match(KEY_RE);
  if (!m) return "Source";
  const source = m[1];
  const n = Number(m[2]) + 1;
  const kind = KIND.find(([re]) => re.test(source))?.[1];
  const name = kind ?? source.replace(/[_-]+/g, " ").slice(0, 14);
  return `${name} ${n}`;
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
export function splitCitations(text: string): Segment[] {
  const out: Segment[] = [];
  let last = 0;
  for (const m of text.matchAll(CITE_RE)) {
    const idx = m.index ?? 0;
    if (idx > last) out.push({ type: "text", text: text.slice(last, idx) });
    for (const p of splitGroup(m[1])) out.push({ type: "cite", label: p, key: citationKey(p) });
    last = idx + m[0].length;
  }
  if (last < text.length) out.push({ type: "text", text: text.slice(last) });
  // Tidy leftovers: stray provenance markers and the space before a chip.
  return out
    .map((s) => (s.type === "text" ? { ...s, text: s.text.replace(STRAY_MARKER_RE, "") } : s))
    .map((s, i, arr) =>
      s.type === "text" && arr[i + 1]?.type === "cite" ? { ...s, text: s.text.replace(/\s+$/, " ") } : s,
    )
    .filter((s) => s.type === "cite" || s.text.length > 0);
}

/** Text with citations removed (for compact places like the landing mock). */
export function stripCitations(text: string): string {
  return text.replace(CITE_RE, "").replace(STRAY_MARKER_RE, "").replace(/\s+([.,;:])/g, "$1").trim();
}

/** Rewrite citation brackets in markdown into chip links, for the markdown fallback. */
export function linkCitationsInMarkdown(md: string, ns: string): string {
  return md.replace(CITE_RE, (_all, inner: string) =>
    splitGroup(inner)
      .map((p) => {
        const key = citationKey(p);
        return `[${chipLabel(key)}](#${sourceAnchor(ns, key)} "${p.replace(/"/g, "'")}")`;
      })
      .join(" "),
  );
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
