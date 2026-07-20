"use client";

import { useEffect, useRef, useState } from "react";
import { API } from "@/lib/api";

type CorpusDoc = { doc_id: string; title: string };
type CorpusStatus = { documents: CorpusDoc[]; document_count: number; chunk_count: number };

/** Add evidence the agents can search: upload a file, paste text, or pull a real
 *  SEC filing by ticker. Ingested documents are searchable on the very next run. */
export function CorpusPanel() {
  const [status, setStatus] = useState<CorpusStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [ticker, setTicker] = useState("");
  const [open, setOpen] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = async () => {
    try {
      const r = await fetch(`${API}/corpus/status`);
      setStatus(await r.json());
    } catch {
      /* backend not up yet — the panel just shows nothing */
    }
  };

  useEffect(() => {
    refresh();
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
            ? `"${data.title}" was already indexed.`
            : `Added "${data.title}" — ${data.chunks_added} chunks indexed.`,
        });
        refresh();
      }
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Ingestion failed." });
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

  const onTicker = () => {
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

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-500">
          Knowledge base
          {status && (
            <span className="ml-2 normal-case tracking-normal text-slate-600">
              {status.document_count} docs · {status.chunk_count} chunks
            </span>
          )}
        </h2>
        <button
          onClick={() => setOpen((o) => !o)}
          className="rounded-md border border-slate-700 px-2.5 py-1 text-xs font-medium text-slate-300 transition hover:border-sky-500 hover:text-sky-300"
        >
          {open ? "Close" : "Add evidence"}
        </button>
      </div>

      {open && (
        <div className="mt-3 space-y-3 border-t border-slate-800 pt-3">
          <p className="text-xs text-slate-500">
            Agents can only cite what has been indexed. Add a document, then ask about it.
          </p>

          {/* Upload a file */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => fileRef.current?.click()}
              disabled={busy}
              className="rounded-md border border-slate-700 px-3 py-1.5 text-xs text-slate-200 transition hover:border-sky-500 disabled:opacity-50"
            >
              Upload .md / .txt
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".md,.txt,.markdown"
              onChange={onFile}
              className="hidden"
            />
            <span className="text-xs text-slate-600">plain text only, max 2 MB</span>
          </div>

          {/* Pull a real SEC filing */}
          <div className="flex flex-wrap items-center gap-2">
            <input
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && onTicker()}
              placeholder="Ticker (e.g. AAPL)"
              className="w-36 rounded-md border border-slate-700 bg-slate-900/70 px-2.5 py-1.5 text-xs outline-none focus:border-sky-500"
            />
            <button
              onClick={onTicker}
              disabled={busy || !ticker.trim()}
              className="rounded-md border border-slate-700 px-3 py-1.5 text-xs text-slate-200 transition hover:border-sky-500 disabled:opacity-50"
            >
              Fetch 10-K from SEC
            </button>
          </div>

          {busy && <p className="text-xs text-sky-300">Ingesting — chunking and embedding…</p>}
          {msg && (
            <p className={`text-xs ${msg.ok ? "text-emerald-300" : "text-red-300"}`}>{msg.text}</p>
          )}

          {status && status.documents.length > 0 && (
            <ul className="max-h-32 space-y-1 overflow-y-auto text-xs text-slate-400">
              {status.documents.map((d) => (
                <li key={d.doc_id} className="truncate">
                  📄 {d.title}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
