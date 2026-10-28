import type { Metadata, Viewport } from "next";
import { Inter, Instrument_Serif, JetBrains_Mono } from "next/font/google";
import "./globals.css";

// Three faces: Inter for UI and body copy, Instrument Serif for editorial
// headlines, JetBrains Mono for figures, tickers and small labels. Exposed as CSS
// variables and mapped to font-sans / font-display / font-mono in globals.css.
const sans = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const display = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-instrument",
  display: "swap",
});
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains", display: "swap" });

export const metadata: Metadata = {
  title: {
    default: "Atlas — Due diligence on any company, in minutes",
    template: "%s · Atlas",
  },
  description:
    "Atlas is an AI analyst team that researches any company, argues the bull and bear case, and writes an investor-grade brief where every claim is cited.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#05070d",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`h-full ${sans.variable} ${display.variable} ${mono.variable}`}>
      <body className="min-h-full">{children}</body>
    </html>
  );
}
