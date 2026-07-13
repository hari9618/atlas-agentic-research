import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Atlas — Due-Diligence War Room",
  description:
    "A team of AI agents that research a company, debate bull vs bear, and produce a cited brief.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="warroom-bg min-h-full">{children}</body>
    </html>
  );
}
