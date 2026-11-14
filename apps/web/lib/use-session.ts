"use client";

import { useSyncExternalStore } from "react";
import { getSnapshot, LOADING_SNAPSHOT, type SessionSnapshot, subscribe } from "./auth";

/** The signed-in user, or "loading" until the first silent refresh settles. The server
 *  render always sees "loading", so markup that depends on it hydrates cleanly. */
export function useSession(): SessionSnapshot {
  return useSyncExternalStore(subscribe, getSnapshot, () => LOADING_SNAPSHOT);
}
