"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { cx } from "@/components/ui/styles";

export type TocItem = { id: string; label: string; n?: number };

/** Sticky "on this page" navigation with scroll-spy. One element, two layouts via
 *  container queries on the report: a horizontally scrolling chip row on narrow
 *  containers, a left rail with an active marker on wide ones. */
export function ReportToc({
  items,
  stickyClass = "top-20",
}: {
  items: TocItem[];
  /** Sticky offset for the chip row, matching the page's own sticky header. */
  stickyClass?: string;
}) {
  const key = items.map((i) => i.id).join("|");
  const ids = useMemo(() => (key ? key.split("|") : []), [key]);
  const [active, setActive] = useState<string>(ids[0] ?? "");
  const listRef = useRef<HTMLOListElement>(null);

  // Scroll-spy: a thin trigger line ~28% down the viewport. Sections are contiguous, so
  // at most one crosses it; in the gaps between blocks the previous choice is kept.
  useEffect(() => {
    const els = ids.map((id) => document.getElementById(id)).filter((el): el is HTMLElement => !!el);
    if (!els.length || typeof IntersectionObserver === "undefined") return;
    const visible = new Map<string, boolean>();
    const pick = () => {
      const first = ids.find((id) => visible.get(id));
      if (first) setActive(first);
    };
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) visible.set(e.target.id, e.isIntersecting);
        pick();
      },
      { rootMargin: "-28% 0px -71% 0px" },
    );
    els.forEach((el) => io.observe(el));

    // The last section can be too short to ever reach the band: select it once the
    // page bottom is reached while it is on screen.
    const last = els[els.length - 1];
    const onScroll = () => {
      const atBottom = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4;
      if (atBottom && last.getBoundingClientRect().top < window.innerHeight) setActive(last.id);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      io.disconnect();
      window.removeEventListener("scroll", onScroll);
    };
  }, [ids]);

  // Keep the active chip in view when the list scrolls horizontally (narrow layout).
  useEffect(() => {
    const list = listRef.current;
    if (!list || list.scrollWidth <= list.clientWidth + 1) return;
    const link = list.querySelector<HTMLElement>(`[data-toc="${CSS.escape(active)}"]`);
    if (!link) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    list.scrollTo({
      left: link.offsetLeft - list.clientWidth / 2 + link.offsetWidth / 2,
      behavior: reduce ? "auto" : "smooth",
    });
  }, [active]);

  if (items.length < 2) return null;

  return (
    <nav
      aria-label="Report sections"
      className={cx(
        "screen-only sticky z-30 min-w-0 @4xl:top-24 @4xl:self-start",
        stickyClass,
      )}
    >
      <p className="mb-3 hidden font-mono text-[10.5px] font-medium tracking-[0.16em] text-slate-400 uppercase @4xl:block">
        On this page
      </p>
      <div className="overflow-hidden rounded-full border border-slate-200/80 bg-white/90 p-1 shadow-[0_10px_30px_-14px_rgb(15_23_42/0.35)] backdrop-blur-md @4xl:overflow-visible @4xl:rounded-none @4xl:border-0 @4xl:bg-transparent @4xl:p-0 @4xl:shadow-none @4xl:backdrop-blur-none">
        <ol
          ref={listRef}
          className="relative flex gap-1 overflow-x-auto [scrollbar-width:none] @4xl:flex-col @4xl:gap-0 @4xl:overflow-visible @4xl:border-l @4xl:border-slate-200 [&::-webkit-scrollbar]:hidden"
        >
          {items.map((item) => {
            const current = item.id === active;
            return (
              <li key={item.id} className="shrink-0">
                <a
                  href={`#${item.id}`}
                  data-toc={item.id}
                  aria-current={current ? "location" : undefined}
                  onClick={() => setActive(item.id)}
                  className={cx(
                    "flex items-baseline gap-2 rounded-full px-3 py-1.5 text-xs font-medium whitespace-nowrap transition-colors",
                    "@4xl:-ml-px @4xl:rounded-none @4xl:border-l-2 @4xl:py-[0.45rem] @4xl:pr-0 @4xl:pl-3.5 @4xl:text-[13px] @4xl:whitespace-normal",
                    current
                      ? "bg-ink-950 text-white @4xl:border-indigo-600 @4xl:bg-transparent @4xl:text-slate-950"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 @4xl:border-transparent @4xl:text-slate-500 @4xl:hover:border-slate-300 @4xl:hover:bg-transparent",
                  )}
                >
                  {item.n != null && (
                    <span
                      aria-hidden
                      className={cx(
                        "hidden font-mono text-[10px] tabular-nums @4xl:inline",
                        current ? "text-indigo-600" : "text-slate-400",
                      )}
                    >
                      {String(item.n).padStart(2, "0")}
                    </span>
                  )}
                  {item.label}
                </a>
              </li>
            );
          })}
        </ol>
      </div>
    </nav>
  );
}
