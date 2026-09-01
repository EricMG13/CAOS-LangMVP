import type { Metadata } from "next";
import Link from "next/link";

// The 404 owns its tab title. Without this it inherits the root layout's and a
// missing route is indistinguishable from the workspace in a tab strip.
export const metadata: Metadata = { title: "CAOS — Page not found" };

// `/cases/` keeps the trailing slash: `trailingSlash: true` means the router only
// fetches a route's client payload for a slashed pathname, and an unslashed href
// degrades into a full document load (see lib/workbench#withQuery). The href
// carries no `?case=` because this file is a server component in a static export
// and cannot read the query; it does not need to — the shell keeps the selection
// in workspace authority and re-resolves it on Cases (Workspace.tsx `resolvedCaseId`).
export default function NotFound() {
  return <section className="panel"><div className="panel-body flow"><p className="muted">This workspace destination does not exist. Your case selection is unchanged — the top bar still holds it.</p><div><Link className="button small" href="/cases/">Return to Cases</Link></div></div></section>;
}
