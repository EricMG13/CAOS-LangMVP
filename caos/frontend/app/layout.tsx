import type { Metadata, Viewport } from "next";
import { Suspense } from "react";
import Workspace from "../src/components/Workspace";
import "./globals.css";

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
  return <html lang="en"><body><Suspense fallback={<div className="state-skeleton" role="status" aria-live="polite" aria-label="Loading"><span /><span /><span /></div>}><Workspace>{children}</Workspace></Suspense></body></html>;
}
