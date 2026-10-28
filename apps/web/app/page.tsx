import { BuiltFor } from "@/components/landing/BuiltFor";
import { Comparison } from "@/components/landing/Comparison";
import { Faq } from "@/components/landing/Faq";
import { Features } from "@/components/landing/Features";
import { FinalCta } from "@/components/landing/FinalCta";
import { Hero } from "@/components/landing/Hero";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { Inside } from "@/components/landing/Inside";
import { Markets } from "@/components/landing/Markets";
import { SamplePreview } from "@/components/landing/SamplePreview";
import { SiteFooter } from "@/components/landing/SiteFooter";
import { SiteNav } from "@/components/landing/SiteNav";

// Marketing site. A server component: the whole page is static HTML; the only
// client JS is Next's <Link>/<Form> runtime. Motion is CSS-only.
export default function Home() {
  return (
    <>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[60] focus:rounded-md focus:bg-white focus:px-3 focus:py-2 focus:text-sm focus:shadow"
      >
        Skip to content
      </a>
      <SiteNav />
      <main id="main">
        <Hero />
        <Markets />
        <BuiltFor />
        <HowItWorks />
        <Features />
        <Inside />
        <SamplePreview />
        <Comparison />
        <Faq />
        <FinalCta />
      </main>
      <SiteFooter />
    </>
  );
}
