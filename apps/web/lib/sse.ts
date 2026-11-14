// A small `text/event-stream` parser for reading SSE over fetch. We can't use the
// browser's EventSource because it cannot send an Authorization header, and the API
// authenticates every stream with a bearer token.

export type SseMessage = { event: string; data: string; id?: string };

export type SseParser = {
  /** Feed decoded text, split anywhere (mid-line, mid-field, mid-CRLF). */
  push(chunk: string): void;
  /** The stream ended: drop whatever event was still being assembled. */
  end(): void;
};

/** Build an incremental parser that follows the WHATWG event-stream rules.
 *
 *  Edge cases it handles:
 *  - Line endings `\n`, `\r\n` and a lone `\r`, including a `\r\n` pair split across
 *    two chunks (the `\r` ends the line; a `\n` opening the next chunk is skipped).
 *  - Chunks that cut a line anywhere: the partial line is buffered until it ends.
 *  - Multi-line data: repeated `data:` lines are joined with `\n`.
 *  - Comment lines starting with `:` (sse-starlette's `: ping` keep-alives) are never
 *    dispatched as events; `onComment` lets the caller count them as a heartbeat.
 *  - One optional space after the colon is stripped; a line with no colon is a field
 *    with an empty value; unknown fields and `retry` are ignored (we never reconnect).
 *  - An event with no `data:` lines is not dispatched; the event name defaults to
 *    "message" and resets after every dispatch.
 *  - A leading UTF-8 BOM is dropped.
 *  - An event still unterminated when the stream ends is discarded, as the spec says.
 *    That matters here: a connection cut mid-event must not surface as a truncated
 *    `final` payload. */
export function createSseParser(
  onMessage: (m: SseMessage) => void,
  onComment?: (text: string) => void,
): SseParser {
  let buf = "";
  let started = false;
  let skipLF = false;
  let event = "";
  let data: string[] = [];
  let lastId: string | undefined;

  const dispatch = () => {
    if (data.length) onMessage({ event: event || "message", data: data.join("\n"), id: lastId });
    event = "";
    data = [];
  };

  const line = (l: string) => {
    if (l === "") return dispatch();
    if (l.charCodeAt(0) === 58 /* : */) return onComment?.(l.slice(1).trimStart());
    const colon = l.indexOf(":");
    const field = colon === -1 ? l : l.slice(0, colon);
    let value = colon === -1 ? "" : l.slice(colon + 1);
    if (value.charCodeAt(0) === 32 /* space */) value = value.slice(1);
    if (field === "event") event = value;
    else if (field === "data") data.push(value);
    else if (field === "id" && !value.includes("\0")) lastId = value;
  };

  return {
    push(chunk) {
      if (!chunk) return;
      if (!started) {
        started = true;
        if (chunk.charCodeAt(0) === 0xfeff) chunk = chunk.slice(1);
      }
      if (skipLF && chunk.charCodeAt(0) === 10) chunk = chunk.slice(1);
      skipLF = false;
      buf += chunk;

      let start = 0;
      for (let i = 0; i < buf.length; i++) {
        const c = buf.charCodeAt(i);
        if (c !== 10 && c !== 13) continue;
        line(buf.slice(start, i));
        if (c === 13) {
          if (i + 1 < buf.length) {
            if (buf.charCodeAt(i + 1) === 10) i++;
          } else {
            skipLF = true;
          }
        }
        start = i + 1;
      }
      buf = buf.slice(start);
    },
    end() {
      buf = "";
      event = "";
      data = [];
    },
  };
}
