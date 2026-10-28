import { BuiltFor } from "@/components/landing/BuiltFor";
import { Comparison } from "@/components/landing/Comparison";
import { Faq } from "@/components/landing/Faq";
import { Features } from "@/components/landing/Features";
import { FinalCta } from "@/components/landing/FinalCta";
import { Hero } from "@/components/landing/Hero";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { SamplePreview } from "@/components/landing/SamplePreview";
import { SiteFooter } from "@/components/landing/SiteFooter";
import { SiteNav } from "@/components/landing/SiteNav";

// Marketing site. A server component: the whole page is static HTML; the only
// client JS is Next's <Link>/<Form> runtime.
export default function Home() {
  return (
    <>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-md focus:bg-white focus:px-3 focus:py-2 focus:text-sm focus:shadow"
      >
        Skip to content
      </a>
      <SiteNav />
      <main id="main">
        <Hero />
        <BuiltFor />
        <HowItWorks />
        <Features />
        <SamplePreview />
        <Comparison />
        <Faq />
        <FinalCta />
      </main>
      <SiteFooter />
    </>
  );
}
