"use client";

import { useEffect } from "react";
import { ensureAwake } from "@/lib/http";

/** Start waking the API the moment a visitor lands, not when they first submit.
 *  A free Render instance naps after 15 idle minutes and needs a while to boot; doing
 *  that while someone reads the page or types their email hides most of the wait.
 *  Shares one in-flight ping with every other caller, so it costs one request. */
export function WakeApi() {
  useEffect(() => {
    void ensureAwake();
  }, []);
  return null;
}
