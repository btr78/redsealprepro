import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://www.redsealprep.pro"),
  title: "Red Seal Practice Exams — 9 Trades, AI Tutor | RedSeal Prep Pro",
  description: "Canada's Red Seal exam prep with 1,145+ practice questions across 9 trades — Electrician, Plumber, Welder, Carpenter, Millwright, Auto, Steamfitter & more. AI tutor explains every answer. Start free.",
  keywords: "red seal practice exam, red seal practice test, certificate of qualification, electrician 309A, industrial electrician 442A, plumber 306A, welder 456A, millwright 433A, carpenter 403A, auto service technician 310S, steamfitter pipefitter 307A, tool and die maker 430A, trades exam prep",
  alternates: { canonical: "https://www.redsealprep.pro" },
  openGraph: { title: "Red Seal Practice Exams — 9 Trades, AI Tutor", description: "1,145+ realistic practice questions across 9 Red Seal trades with an AI tutor that explains every answer. Start free.", url: "https://www.redsealprep.pro", siteName: "RedSeal Prep Pro", type: "website" },
  twitter: { card: "summary_large_image", title: "Red Seal Practice Exams — 9 Trades, AI Tutor", description: "1,145+ realistic Red Seal practice questions with an AI tutor. Start free." },
  manifest: "/manifest.json",
};

export const viewport: Viewport = {
  themeColor: "#07090f",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
