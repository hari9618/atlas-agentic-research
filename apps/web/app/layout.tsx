import type { Metadata, Viewport } from "next";
import "./globals.css";

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
  themeColor: "#ffffff",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full">{children}</body>
    </html>
  );
}
