import Link from "next/link";

/** Atlas logo mark + wordmark. */
export function Wordmark({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="flex items-center gap-2 rounded-md text-slate-900" aria-label="Atlas home">
      <svg aria-hidden viewBox="0 0 32 32" className="h-7 w-7">
        <rect width="32" height="32" rx="8" className="fill-indigo-600" />
        <path d="M9 23l7-14 7 14" fill="none" stroke="white" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M11.8 18h8.4" stroke="white" strokeWidth="2.6" strokeLinecap="round" />
      </svg>
      <span className="text-lg font-semibold tracking-tight">Atlas</span>
    </Link>
  );
}
