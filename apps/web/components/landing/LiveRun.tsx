"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { cx } from "@/components/ui/styles";

const STEPS = [
  "Supervisor scopes the question",
  "Four analysts research",
  "Bull and bear argue",
  "Judge weighs the evidence",
  "Brief drafted and cited",
];

/** The hero's one filled panel: the Atlas pipeline stepping through, linking to the sample brief. */
export function LiveRun() {
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const timer = setInterval(() => setStep((s) => (s + 1) % STEPS.length), 1700);
    return () => clearInterval(timer);
  }, []);

  return (
    <a
      href="#sample-report"
      className="group block rounded-xl border border-white/10 bg-ink-900/90 p-5 text-white backdrop-blur"
    >
      <span className="flex items-center justify-between font-mono text-2xs tracking-label text-slate-400 uppercase">
        Sample run
        <span className="text-slate-300">Helios Robotics</span>
      </span>
      <ol className="mt-4 space-y-2">
        {STEPS.map((label, i) => (
          <li
            key={label}
            className={cx(
              "flex items-center gap-2 text-sm transition-colors duration-300",
              i === step ? "text-white" : "text-slate-400",
            )}
          >
            <span
              aria-hidden
              className={cx(
                "flex h-4 w-4 shrink-0 items-center justify-center rounded-full border transition-colors duration-300",
                i === step ? "border-accent-400 bg-accent-400" : "border-white/20",
              )}
            >
              {i < step && <Icon name="check" className="h-2.5 w-2.5 text-slate-300" strokeWidth={3} />}
            </span>
            {label}
          </li>
        ))}
      </ol>
      <span className="mt-4 flex items-center justify-between border-t border-white/10 pt-3 text-sm font-medium">
        Read the sample brief
        <Icon name="arrowRight" className="h-4 w-4 text-accent-400 transition-transform group-hover:translate-x-1" />
      </span>
    </a>
  );
}
