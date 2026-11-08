import type { ApiFailure } from "@/lib/api";

/** What the user can do next. `back` returns to the draft so a different decision can
 *  be made; `new` starts over; `edit` puts focus back on the question. */
export type Recovery = "retry" | "back" | "new" | "edit";

export type RunError = {
  title: string;
  message: string;
  /** Primary action first. */
  actions: Recovery[];
  /** Whether the paused run is still usable (the draft can still be reviewed). */
  threadAlive: boolean;
  tone: "bad" | "mid";
};

/** Turn a classified failure into calm, specific copy and the right way out. */
export function describeFailure(f: ApiFailure, during: "start" | "resume"): RunError {
  const resume = during === "resume";
  const retryOrBack: Recovery[] = resume ? ["retry", "back"] : ["retry", "edit"];

  switch (f.kind) {
    case "offline":
      return {
        title: "You're offline",
        message: "Reconnect to the internet, then try again. Nothing has been lost.",
        actions: retryOrBack,
        threadAlive: true,
        tone: "mid",
      };
    case "unreachable":
      return {
        title: "Can't reach the research engine",
        message:
          "The server didn't answer, even after waiting for it to wake up. It may be restarting; give it a moment and try again.",
        actions: retryOrBack,
        threadAlive: true,
        tone: "bad",
      };
    case "server":
      return {
        title: "The research engine returned an error",
        message: "This is usually brief, for example during a restart or deploy. Try again in a few seconds.",
        actions: retryOrBack,
        threadAlive: true,
        tone: "bad",
      };
    case "dropped":
      return resume
        ? {
            title: "The connection dropped",
            message:
              "Your decision may still have gone through in the background. Try again: if the run has already moved on, Atlas will tell you.",
            actions: ["retry", "back"],
            threadAlive: true,
            tone: "mid",
          }
        : {
            title: "The connection dropped mid-run",
            message:
              "The live stream was interrupted. Atlas doesn't silently reconnect, so no duplicate run was started. Try again to start a fresh run.",
            actions: ["retry", "edit"],
            threadAlive: true,
            tone: "mid",
          };
    case "stalled":
    case "timeout":
      return {
        title: "The run went quiet",
        message: "There was no progress for several minutes, so Atlas stopped waiting. Try again in a moment.",
        actions: retryOrBack,
        threadAlive: true,
        tone: "mid",
      };
    case "aborted":
      return { title: "Cancelled", message: "", actions: [], threadAlive: true, tone: "mid" };
    case "in_band":
      break;
  }

  switch (f.code) {
    case "bad_request":
      return {
        title: resume ? "Atlas couldn't accept that decision" : "Atlas couldn't accept that question",
        message: f.message,
        actions: resume ? ["back"] : ["edit"],
        threadAlive: true,
        tone: "mid",
      };
    case "not_configured":
      return {
        title: "The research engine isn't configured",
        message:
          "The server has no language-model key set, so it can't run research right now. This is a server setting, not something you did.",
        actions: resume ? ["back"] : ["edit"],
        threadAlive: true,
        tone: "bad",
      };
    case "not_paused":
      return {
        title: "This draft can't be changed any more",
        message:
          "The run has already moved past review (it may have finished in the background). The draft stays here to read or download; start a new run to continue.",
        actions: ["new"],
        threadAlive: false,
        tone: "mid",
      };
    case "unknown_thread":
      return {
        title: "This run has expired",
        message:
          "The server no longer has this run, often because it restarted. Your draft stays here to read or download; start a new run to continue.",
        actions: ["new"],
        threadAlive: false,
        tone: "mid",
      };
    case "run_failed":
    default:
      return {
        title: "The run hit an error",
        message: f.message,
        actions: retryOrBack,
        threadAlive: true,
        tone: "bad",
      };
  }
}
