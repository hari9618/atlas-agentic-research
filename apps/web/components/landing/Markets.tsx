// Exchanges Atlas can pull live quotes for (Yahoo Finance symbols; see
// apps/api/atlas/core/tools/symbols.py). A CSS-only marquee: the list is rendered
// twice and the track slides by half its width, so the loop is seamless.

const MARKETS: [string, string][] = [
  ["NASDAQ", "NVDA"],
  ["NSE", "RELIANCE.NS"],
  ["NYSE", "JPM"],
  ["BSE", "500325.BO"],
  ["LSE", "VOD.L"],
  ["Tokyo", "7203.T"],
  ["HKEX", "0700.HK"],
  ["NSE", "TCS.NS"],
  ["TSX", "SHOP.TO"],
  ["ASX", "BHP.AX"],
  ["XETRA", "SAP.DE"],
  ["Euronext", "MC.PA"],
  ["SGX", "D05.SI"],
  ["Private cos.", "web + news"],
];

function Row({ hidden = false }: { hidden?: boolean }) {
  return (
    <ul aria-hidden={hidden || undefined} className="flex shrink-0 items-center gap-3 pr-3">
      {MARKETS.map(([exchange, symbol], i) => (
        <li
          key={`${symbol}-${i}`}
          className="flex items-center gap-2.5 rounded-full border border-white/[0.08] bg-white/[0.03] py-1.5 pr-4 pl-1.5 whitespace-nowrap"
        >
          <span className="rounded-full bg-white/[0.07] px-2 py-0.5 font-mono text-[10px] tracking-wider text-slate-400 uppercase">
            {exchange}
          </span>
          <span className="font-mono text-sm text-slate-200">{symbol}</span>
        </li>
      ))}
    </ul>
  );
}

export function Markets() {
  return (
    <section aria-labelledby="markets-title" className="border-t border-white/[0.06] bg-ink-950 py-10">
      <h2
        id="markets-title"
        className="text-center font-mono text-[11px] tracking-[0.2em] text-slate-500 uppercase"
      >
        Research companies listed across global exchanges
      </h2>
      <div className="group mt-6 flex overflow-hidden mask-fade-x">
        <div className="flex animate-marquee group-hover:[animation-play-state:paused]">
          <Row />
          <Row hidden />
        </div>
      </div>
    </section>
  );
}
