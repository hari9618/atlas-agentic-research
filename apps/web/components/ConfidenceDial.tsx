type Props = { value: number | null };

export function ConfidenceDial({ value }: Props) {
  const v = value == null ? 0 : Math.max(0, Math.min(1, value));
  const pct = Math.round(v * 100);
  const r = 42;
  const c = 2 * Math.PI * r;
  const dash = c * v;
  const color = v >= 0.7 ? "#34d399" : v >= 0.45 ? "#fbbf24" : "#f87171";

  return (
    <div className="flex flex-col items-center">
      <svg width="120" height="120" viewBox="0 0 120 120" className="-rotate-90">
        <circle cx="60" cy="60" r={r} fill="none" stroke="#1e293b" strokeWidth="10" />
        <circle
          cx="60"
          cy="60"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c}`}
          style={{ transition: "stroke-dasharray 0.6s ease" }}
        />
      </svg>
      <div className="-mt-[82px] flex flex-col items-center">
        <span className="text-3xl font-bold" style={{ color }}>
          {value == null ? "—" : pct}
        </span>
        <span className="text-[10px] uppercase tracking-widest text-slate-400">confidence</span>
      </div>
    </div>
  );
}
