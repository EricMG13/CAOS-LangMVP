"use client";

import { useEffect } from "react";
import { historyStateForExternalReplace } from "../lib/workbench";

// The page of a pre-Align slug (FE-A1 D2, lib/workbench#forwardedRoutes). A static
// export cannot serve a redirect, so the page replaces history — never pushes — to
// the destination that absorbed the slug, carrying the query string and the hash
// intact. The write goes through the same external `replaceState` the workspace
// uses for its own URL writes: Next's patched `replaceState` syncs `usePathname`
// to the new address in place, keeps the entry router-owned (so back and forward
// stay soft traversals), and fetches nothing — the shell has already resolved the
// slug to its destination (lib/workbench#destinationFromSlug) and renders that
// surface. A `router.replace` transition would instead race the workspace's own
// URL-sync effect, which rewrites the current address on the same commit and
// wins whenever it lands second. `to` ends in a slash (lib/workbench#withQuery).
export default function RouteForwarder({ to }: { to: string }) {
  useEffect(() => {
    window.history.replaceState(historyStateForExternalReplace(window.history.state), "", `${to}${window.location.search}${window.location.hash}`);
  }, [to]);
  return null;
}
