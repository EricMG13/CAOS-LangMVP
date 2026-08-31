import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono, Space_Grotesk } from "next/font/google";
import { Suspense } from "react";
import Workspace from "../src/components/Workspace";
import "./globals.css";

const sans = Inter({ subsets: ["latin"], display: "swap", variable: "--font-sans" });
const mono = JetBrains_Mono({ subsets: ["latin"], display: "swap", variable: "--font-mono" });
// Display face for the wordmark, page titles and display headings only. Body
// prose stays Inter and numerics stay JetBrains Mono; the paper surface never
// uses it. Self-hosted at build by next/font, so it costs nothing at runtime.
const display = Space_Grotesk({ subsets: ["latin"], display: "swap", variable: "--font-display" });

export const metadata: Metadata = {
  title: "CAOS — Credit Agent OS",
  description: "Evidence-forward institutional credit analysis",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#0a0c10",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" className={`${sans.variable} ${mono.variable} ${display.variable}`}><body><Suspense fallback={<div className="state-skeleton" role="status" aria-live="polite" aria-label="Loading"><span /><span /><span /></div>}><Workspace>{children}</Workspace></Suspense></body></html>;
}
