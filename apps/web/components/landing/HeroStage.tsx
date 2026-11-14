"use client";

import Image from "next/image";
import { useEffect, useRef, useState, useSyncExternalStore, type PointerEvent } from "react";
import { cx } from "@/components/ui/styles";

const REDUCED = "(prefers-reduced-motion: reduce)";

function subscribeReduced(onChange: () => void) {
  const mq = window.matchMedia(REDUCED);
  mq.addEventListener("change", onChange);
  return () => mq.removeEventListener("change", onChange);
}

/**
 * The hero film: the macaw flies in and lands, once, then rests on the last frame.
 *
 * The video's first frame IS the poster (an empty branch) and its last frame IS the
 * perched still, so there is no media swap and no seam at the "freeze": the video
 * simply ends. Visitors who prefer reduced motion get the still. The pointer leans
 * the shot slightly; Replay appears once the landing has played.
 */
export function HeroStage({ className }: { className?: string }) {
  const stage = useRef<HTMLDivElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const [ended, setEnded] = useState(false);
  const reduced = useSyncExternalStore(subscribeReduced, () => window.matchMedia(REDUCED).matches, () => false);

  useEffect(() => {
    const v = video.current;
    const el = stage.current;
    if (!v || !el || reduced) return;
    // Started from code (not the autoplay attribute) so reduced-motion visitors never
    // play it, and only once the panel is in view — on phones it sits below the
    // headline, and a landing that plays off-screen is a landing nobody sees.
    // Muted + playsInline keep mobile autoplay policies happy.
    const io = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        io.disconnect();
        v.play().catch(() => setEnded(true)); // autoplay refused: poster stays, offer Replay
      },
      { threshold: 0.45 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [reduced]);

  function replay() {
    const v = video.current;
    if (!v) return;
    setEnded(false);
    v.currentTime = 0;
    v.play().catch(() => setEnded(true));
  }

  function lean(e: PointerEvent<HTMLDivElement>) {
    if (e.pointerType !== "mouse" || !stage.current) return;
    const { left, top, width, height } = stage.current.getBoundingClientRect();
    stage.current.style.setProperty("--px", ((e.clientX - left) / width - 0.5).toFixed(3));
    stage.current.style.setProperty("--py", ((e.clientY - top) / height - 0.5).toFixed(3));
  }

  return (
    <div
      ref={stage}
      onPointerMove={lean}
      className={cx(
        "hero-film relative isolate overflow-hidden rounded-xl border border-current/10 bg-[#c9cfba] text-slate-950",
        className,
      )}
    >
      {reduced ? (
        <Image
          src="/hero/still.webp"
          alt="A blue-and-gold macaw perched on a bare branch"
          fill
          priority
          sizes="(min-width: 1024px) 55vw, 100vw"
          className="hero-film-media object-cover"
        />
      ) : (
        <video
          ref={video}
          muted
          playsInline
          preload="auto"
          poster="/hero/poster.webp"
          onEnded={() => setEnded(true)}
          aria-label="A blue-and-gold macaw flies in and lands on a bare branch"
          className="hero-film-media absolute inset-0 h-full w-full object-cover"
        >
          <source src="/hero/landing.webm" type="video/webm" />
          <source src="/hero/landing.mp4" type="video/mp4" />
        </video>
      )}
      {/* A soft vignette ties the sage film into the dark page without touching it. */}
      <div aria-hidden className="pointer-events-none absolute inset-0 rounded-[inherit] shadow-[inset_0_0_120px_rgb(0_0_0/0.18)]" />
      {!reduced && (
        <button
          type="button"
          onClick={replay}
          className={cx(
            "absolute top-4 right-4 z-10 min-h-9 cursor-pointer rounded-full border border-black/10 bg-white/55 px-4 font-mono text-2xs tracking-label text-ink-950 uppercase backdrop-blur-md transition-all duration-500 hover:bg-white/80",
            ended ? "opacity-100" : "pointer-events-none translate-y-1 opacity-0",
          )}
          tabIndex={ended ? 0 : -1}
        >
          Replay
        </button>
      )}
    </div>
  );
}
