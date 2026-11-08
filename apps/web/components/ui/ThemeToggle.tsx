"use client";

import { useSyncExternalStore, type MouseEvent } from "react";
import { cx } from "./styles";

type Theme = "light" | "dark";

function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => observer.disconnect();
}

const current = (): Theme => (document.documentElement.dataset.theme === "dark" ? "dark" : "light");

/** Sliding light/dark switch. The stored choice is applied before paint by the script in app/layout.tsx. */
export function ThemeToggle({ className }: { className?: string }) {
  const theme = useSyncExternalStore<Theme>(subscribe, current, () => "dark");
  const dark = theme === "dark";

  function toggle(e: MouseEvent<HTMLButtonElement>) {
    const next: Theme = dark ? "light" : "dark";
    const apply = () => {
      document.documentElement.dataset.theme = next;
      try {
        localStorage.setItem("atlas-theme", next);
      } catch {
        // Private mode or blocked storage: the switch still works for this visit.
      }
    };
    if (!document.startViewTransition || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      apply();
      return;
    }
    // The new theme opens as a circle growing out of the switch.
    const box = e.currentTarget.getBoundingClientRect();
    const x = box.left + box.width / 2;
    const y = box.top + box.height / 2;
    const r = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
    document.startViewTransition(apply).ready.then(() => {
      document.documentElement.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${r}px at ${x}px ${y}px)`] },
        { duration: 600, easing: "cubic-bezier(0.22, 1, 0.36, 1)", pseudoElement: "::view-transition-new(root)" },
      );
    });
  }

  return (
    <button
      type="button"
      role="switch"
      aria-checked={dark}
      aria-label="Dark theme"
      onClick={toggle}
      className={cx(
        "relative inline-flex h-9 w-16 shrink-0 cursor-pointer items-center rounded-full border border-current/25 transition-colors hover:border-current/50",
        className,
      )}
    >
      <span
        aria-hidden
        className={cx(
          "absolute top-1 left-1 h-[1.625rem] w-[1.625rem] rounded-full bg-accent-400 transition-transform duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]",
          dark && "translate-x-7",
        )}
      />
      <svg
        aria-hidden
        viewBox="0 0 24 24"
        className={cx("relative ml-[0.5625rem] h-3.5 w-3.5 transition-colors", !dark && "text-ink-950")}
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      >
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
      </svg>
      <svg
        aria-hidden
        viewBox="0 0 24 24"
        className={cx("relative ml-[0.8125rem] h-3.5 w-3.5 transition-colors", dark && "text-ink-950")}
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />
      </svg>
    </button>
  );
}
