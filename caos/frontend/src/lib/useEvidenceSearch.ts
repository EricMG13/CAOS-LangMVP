"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, firstErrorMessage, type EvidenceSearchPage } from "./api";

export function useEvidenceSearch(caseId: string, query: string, enabled = true) {
  const [page, setPage] = useState<EvidenceSearchPage>({ matches: [], next_cursor: null });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const requestRef = useRef<AbortController | null>(null);
  const fetchPage = useCallback(async (cursor?: string) => {
    const current = ++generation.current;
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    setLoading(true); setError("");
    if (!cursor) setPage({ matches: [], next_cursor: null });
    try {
      const params = new URLSearchParams({ q: query.trim(), limit: "25" });
      if (cursor) params.set("cursor", cursor);
      const next = await api<EvidenceSearchPage>(`/api/cases/${caseId}/evidence-search?${params}`, {}, controller.signal);
      if (current === generation.current) setPage((previous) => ({ ...next, matches: cursor ? [...previous.matches, ...next.matches] : next.matches }));
    } catch (caught) {
      if (current === generation.current && !controller.signal.aborted) setError(firstErrorMessage(caught, "Unable to search case evidence."));
    } finally { if (current === generation.current) setLoading(false); }
  }, [caseId, query]);
  useEffect(() => {
    // The query and case are external search boundaries, never draft mutations.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPage({ matches: [], next_cursor: null }); setError(""); setLoading(enabled);
    const timer = enabled ? window.setTimeout(() => void fetchPage(), 250) : null;
    return () => { if (timer !== null) window.clearTimeout(timer); generation.current += 1; requestRef.current?.abort(); };
  }, [enabled, fetchPage]);
  return { ...page, loading, error, more: () => page.next_cursor && !loading ? fetchPage(page.next_cursor) : Promise.resolve() };
}
