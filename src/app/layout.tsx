import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RedSeal Prep — Pass Your Red Seal Exam on the First Try",
  description: "Canada's #1 Red Seal exam prep. 135+ original practice questions for Millwright 433A, Electrician 309A/442A and more. AI-powered tutoring. Study anywhere.",
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
