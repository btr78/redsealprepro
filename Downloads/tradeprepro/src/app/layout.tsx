import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RedSeal Prep — Red Seal Exam Prep",
  description: "Pass your Red Seal exam on the first try. 135+ practice questions per trade with AI-powered tutoring. Built for Canadian tradespeople.",
  keywords: "red seal exam, 433A, millwright, electrician, trades exam prep, certificate of qualification",
  manifest: "/manifest.json",
};

export const viewport: Viewport = {
  themeColor: "#07090f",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
