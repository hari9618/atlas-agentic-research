"use client";

import { useEffect, useRef, useState } from "react";
import { API } from "@/lib/api";
import { Icon } from "@/components/ui/Icon";
import { btn, cx, surface } from "@/components/ui/styles";

type CorpusDoc = { doc_id: string; title: string };
type CorpusStatus = { documents: CorpusDoc[]; document_count: number; chunk_count: number };

async function fetchStatus(): Promise<CorpusStatus | null> {
  try {
    const r = await fetch(`${API}/corpus/status`);
    return r.ok ? ((await r.json()) as CorpusStatus) : null;
  } catch {
    return null; // backend not up yet: the panel just shows no count
  }
}

/** "Your documents": add evidence the agents can search (upload a file, or pull a real
 *  SEC filing by ticker). Ingested documents are searchable on the very next run. */
export function CorpusPanel() {
  const [status, setStatus] = useState<CorpusStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [ticker, setTicker] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = async () => setStatus(await fetchStatus());

  useEffect(() => {
    let alive = true;
    fetchStatus().then((s) => alive && setStatus(s));
    return () => {
      alive = false;
    };
  }, []);

  const handle = async (run: () => Promise<Response>) => {
    setBusy(true);
    setMsg(null);
    try {
      const res = await run();
      const data = await res.json();
      if (data.error) {
        setMsg({ ok: false, text: data.error });
      } else {
        const dup = data.chunks_added === 0;
        setMsg({
          ok: true,
          text: dup
            ? `"${data.title}" was already in your documents.`
            : `Added "${data.title}" (${data.chunks_added} passages indexed).`,
        });
        refresh();
      }
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Couldn't add that document." });
    } finally {
      setBusy(false);
    }
  };

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const body = new FormData();
    body.append("file", file);
    handle(() => fetch(`${API}/corpus/upload`, { method: "POST", body }));
    e.target.value = "";
  };

  const onTicker = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!ticker.trim()) return;
    handle(() =>
      fetch(`${API}/corpus/sec`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker: ticker.trim(), form: "10-K" }),
      }),
    );
    setTicker("");
  };

  const onClear = async () => {
    if (!window.confirm("Remove all documents? Atlas will no longer be able to cite them.")) return;
    setBusy(true);
    setMsg(null);
    try {
      await fetch(`${API}/corpus`, { method: "DELETE" });
      setMsg({ ok: true, text: "All documents removed." });
      refresh();
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Could not remove documents." });
    } finally {
      setBusy(false);
    }
  };

  return (
    <details className={cx(surface, "group @container px-4 sm:px-5")}>
      <summary className="flex items-center justify-between gap-3 py-3.5">
        <span className="flex min-w-0 items-center gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-600">
            <Icon name="database" />
          </span>
          <span className="min-w-0">
            <span className="block text-sm font-semibold text-slate-900">Your documents</span>
            <span className="block truncate text-xs text-slate-500">
              {status
                ? `${status.document_count} document${status.document_count === 1 ? "" : "s"} Atlas can cite`
                : "Add filings, reports or notes for Atlas to cite"}
            </span>
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-1 text-xs font-medium text-indigo-700">
          <span className="hidden @sm:inline">Manage</span>
          <Icon name="chevron" className="chevron h-4 w-4 transition-transform" />
        </span>
      </summary>

      <div className="space-y-4 border-t border-slate-200 py-4">
        <p className="text-sm text-slate-600">
          Atlas also searches the live web, news, market data and SEC filings. Add your own documents
          (a pitch deck, a filing, internal notes) and they become citable on the next run.
        </p>

        <div className="grid gap-3 @lg:grid-cols-2">
          <div className="rounded-lg border border-dashed border-slate-300 p-4">
            <p className="text-sm font-medium text-slate-900">Upload a document</p>
            <p className="mt-0.5 text-xs text-slate-500">PDF, Word, Markdown or text, up to 10 MB</p>
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={busy}
              className={cx(btn.small, "mt-3")}
            >
              <Icon name="upload" className="h-3.5 w-3.5" />
              Choose file
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".md,.txt,.markdown,.pdf,.docx"
              onChange={onFile}
              className="sr-only"
              tabIndex={-1}
              aria-label="Upload a document"
            />
          </div>

          <form onSubmit={onTicker} className="rounded-lg border border-dashed border-slate-300 p-4">
            <label htmlFor="sec-ticker" className="text-sm font-medium text-slate-900">
              Pull a 10-K from SEC EDGAR
            </label>
            <p className="mt-0.5 text-xs text-slate-500">Enter a US stock ticker</p>
            <div className="mt-3 flex gap-2">
              <input
                id="sec-ticker"
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                placeholder="e.g. AAPL"
                autoComplete="off"
                className="w-full min-w-0 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm uppercase placeholder:normal-case placeholder:text-slate-500 focus:border-indigo-500 focus:outline-none"
              />
              <button type="submit" disabled={busy || !ticker.trim()} className={btn.small}>
                Fetch
              </button>
            </div>
          </form>
        </div>

        <div aria-live="polite">
          {busy && <p className="text-sm text-indigo-700">Reading and indexing the document…</p>}
          {msg && (
            <p className={cx("text-sm", msg.ok ? "text-emerald-700" : "text-rose-700")}>{msg.text}</p>
          )}
        </div>

        {status && status.documents.length > 0 && (
          <div>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-semibold tracking-wide text-slate-500 uppercase">
                Indexed documents
              </span>
              <button
                type="button"
                onClick={onClear}
                disabled={busy}
                className="text-xs font-medium text-rose-700 hover:underline disabled:opacity-50"
              >
                Remove all
              </button>
            </div>
            <ul className="max-h-40 divide-y divide-slate-100 overflow-y-auto rounded-lg border border-slate-200">
              {status.documents.map((d) => (
                <li key={d.doc_id} className="flex items-center gap-2 px-3 py-2 text-sm text-slate-700">
                  <Icon name="file" className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                  <span className="truncate">{d.title}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </details>
  );
}
