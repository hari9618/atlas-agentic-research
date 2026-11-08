"use client";

import { useEffect } from "react";

/** Everything that should answer a press with a ripple. `data-no-ripple` opts out. */
const PRESSABLE = 'button:not(:disabled), a[class*="rounded-full"], [data-ripple]';
const MIN_VISIBLE_MS = 220;

/**
 * Site-wide micro-interactions, mounted once in the root layout. Delegated listeners
 * mean server-rendered buttons and cards get them too, with no per-component code:
 *
 * - Press ripple from the exact pointer point (idea from the 21st.dev "Ripple Button"
 *   by ddoemonn: it grows from the press, holds a minimum time, fades on release).
 * - Cursor spotlight on `.spotlight` surfaces (idea from the 21st.dev "Spotlight" by
 *   kevingirelli: only two CSS variables change per frame, so nothing re-renders).
 *
 * The visuals live in globals.css. Both effects skip touch hover and reduced motion.
 */
export function Interactions() {
  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0;

    function ripple(e: PointerEvent) {
      if (reduce.matches || (e.pointerType === "mouse" && e.button !== 0)) return;
      const el = (e.target as Element | null)?.closest<HTMLElement>(PRESSABLE);
      if (!el || el.closest("[data-no-ripple]")) return;
      if (getComputedStyle(el).position === "static") el.style.position = "relative";

      const box = el.getBoundingClientRect();
      const x = e.clientX - box.left;
      const y = e.clientY - box.top;
      const reach = Math.hypot(Math.max(x, box.width - x), Math.max(y, box.height - y));

      const clip = document.createElement("span");
      clip.className = "ripple-clip";
      clip.setAttribute("aria-hidden", "true");
      const wave = document.createElement("span");
      wave.className = "ripple";
      wave.style.cssText = `left:${x}px;top:${y}px;width:${reach * 2}px;height:${reach * 2}px`;
      clip.append(wave);
      el.append(clip);

      const born = performance.now();
      const release = () => {
        window.removeEventListener("pointerup", release);
        window.removeEventListener("pointercancel", release);
        window.setTimeout(
          () => {
            wave.classList.add("is-out");
            window.setTimeout(() => clip.remove(), 400);
          },
          Math.max(0, MIN_VISIBLE_MS - (performance.now() - born)),
        );
      };
      window.addEventListener("pointerup", release);
      window.addEventListener("pointercancel", release);
    }

    function spotlight(e: PointerEvent) {
      if (e.pointerType !== "mouse") return;
      const el = (e.target as Element | null)?.closest<HTMLElement>(".spotlight");
      if (!el) return;
      const { clientX, clientY } = e;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const box = el.getBoundingClientRect();
        el.style.setProperty("--sx", `${clientX - box.left}px`);
        el.style.setProperty("--sy", `${clientY - box.top}px`);
      });
    }

    document.addEventListener("pointerdown", ripple, { passive: true });
    document.addEventListener("pointermove", spotlight, { passive: true });
    return () => {
      document.removeEventListener("pointerdown", ripple);
      document.removeEventListener("pointermove", spotlight);
      cancelAnimationFrame(frame);
    };
  }, []);

  return null;
}
