import Link from "next/link";
import { cx } from "@/components/ui/styles";

/** Atlas logo mark + wordmark. `tone="dark"` for ink (dark) surfaces. */
export function Wordmark({ href = "/", tone = "light" }: { href?: string; tone?: "light" | "dark" }) {
  return (
    <Link
      href={href}
      className={cx("flex items-center gap-2.5 rounded-md", tone === "dark" ? "text-white" : "text-slate-900")}
      aria-label="Atlas home"
    >
      <svg aria-hidden viewBox="0 0 32 32" className="h-7 w-7">
        <defs>
          <linearGradient id="atlas-mark" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#818cf8" />
            <stop offset="0.55" stopColor="#4f46e5" />
            <stop offset="1" stopColor="#0ea5e9" />
          </linearGradient>
        </defs>
        <rect width="32" height="32" rx="9" fill="url(#atlas-mark)" />
        <rect x="0.5" y="0.5" width="31" height="31" rx="8.5" fill="none" stroke="white" strokeOpacity="0.25" />
        <path d="M9 23l7-14 7 14" fill="none" stroke="white" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M11.8 18h8.4" stroke="white" strokeWidth="2.6" strokeLinecap="round" />
      </svg>
      <span className="font-display text-[1.6rem] leading-none tracking-tight">Atlas</span>
    </Link>
  );
}
