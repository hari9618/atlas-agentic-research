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
        <rect width="32" height="32" rx="9" fill="#d4f75a" />
        <path d="M9 23l7-14 7 14" fill="none" stroke="#0c100b" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M11.8 18h8.4" stroke="#0c100b" strokeWidth="2.6" strokeLinecap="round" />
      </svg>
      <span className="font-display text-[1.6rem] leading-none tracking-tight">Atlas</span>
    </Link>
  );
}
