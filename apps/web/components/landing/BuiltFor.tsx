import { Container } from "@/components/ui/Container";

const AUDIENCES = [
  "Investors",
  "Founders & operators",
  "Corporate development",
  "Analysts",
  "Sales & partnerships",
];

export function BuiltFor() {
  return (
    <section id="built-for" aria-labelledby="built-for-title" className="scroll-mt-20 border-b border-slate-200 bg-slate-50">
      <Container className="flex flex-col items-center gap-4 py-8 md:flex-row md:justify-center md:gap-6">
        <h2 id="built-for-title" className="text-sm font-medium text-slate-600">
          Built for
        </h2>
        <ul className="flex flex-wrap justify-center gap-2">
          {AUDIENCES.map((a) => (
            <li
              key={a}
              className="rounded-full border border-slate-200 bg-white px-4 py-1.5 text-sm font-medium text-slate-800 shadow-xs"
            >
              {a}
            </li>
          ))}
        </ul>
      </Container>
    </section>
  );
}
