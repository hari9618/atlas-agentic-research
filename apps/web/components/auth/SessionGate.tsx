"use client";

import { useEffect } from "react";
import { redirectToLogin } from "@/lib/auth";
import { useSession } from "@/lib/use-session";

/** The proxy only checks that a session cookie exists. If that cookie turns out to be
 *  stale (refresh rejected, or signed out in another tab), send the user to sign in
 *  instead of leaving them on a page whose every call will fail. Renders nothing. */
export function SessionGate() {
  const { status } = useSession();
  useEffect(() => {
    if (status === "anonymous") redirectToLogin();
  }, [status]);
  return null;
}
