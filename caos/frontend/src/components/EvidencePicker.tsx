"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, firstErrorMessage, type SourceRecord, type SourceSummaryPage } from "../lib/api";
import { formatBlockLocator, withQuery } from "../lib/workbench";
import { useEvidenceSearch } from "../lib/useEvidenceSearch";
import { LoadState, StateNote } from "./states";

export default function EvidencePicker({ caseId, canCite, isCited, onCite, onRemove }: { caseId: string; canCite: boolean; isCited: (sourceId: string, blockId: string) => boolean; onCite: (sourceId: string, blockId: string) => void; onRemove: (sourceId: string, blockId: string) => void }) {
  const [query, setQuery] = useState("");
  const [inventory, setInventory] = useState<SourceSummaryPage>({ sources: [], next_cursor: null });
  const [inventoryError, setInventoryError] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [source, setSource] = useState<SourceRecord | null>(null);
  const [sourceError, setSourceError] = useState("");
  const [blockLimit, setBlockLimit] = useState(40);
  const [moreBusy, setMoreBusy] = useState(false);
  const search = useEvidenceSearch(caseId, query, Boolean(query.trim()));
  useEffect(() => {
    const controller = new AbortController();
    void api<SourceSummaryPage>(`/api/cases/${caseId}/source-summaries?limit=50`, {}, controller.signal).then(setInventory).catch((caught) => { if (!controller.signal.aborted) setInventoryError(firstErrorMessage(caught, "Evidence inventory unavailable.")); });
    return () => controller.abort();
  }, [caseId]);
  useEffect(() => {
    const controller = new AbortController();
    // A different selected source replaces the reader; it never changes the draft.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSource(null); setSourceError(""); setBlockLimit(40);
    if (selectedId) void api<SourceRecord>(`/api/cases/${caseId}/sources/${encodeURIComponent(selectedId)}`, {}, controller.signal).then(setSource).catch((caught) => { if (!controller.signal.aborted) setSourceError(firstErrorMessage(caught, "Evidence source unavailable.")); });
    return () => controller.abort();
  }, [caseId, selectedId]);
  const moreSources = async () => {
    if (!inventory.next_cursor || moreBusy) return;
    setMoreBusy(true); setInventoryError("");
    try {
      const next = await api<SourceSummaryPage>(`/api/cases/${caseId}/source-summaries?limit=50&cursor=${encodeURIComponent(inventory.next_cursor)}`);
      setInventory((previous) => ({ ...next, sources: [...previous.sources, ...next.sources] }));
    } catch (caught) { setInventoryError(firstErrorMessage(caught, "Evidence inventory unavailable.")); }
    finally { setMoreBusy(false); }
  };
  const block = (sourceId: string, blockId: string, text: string, locator: Record<string, unknown>, withdrawn = false) => <div className="evidence-source-block" key={`${sourceId}:${blockId}`}><p>{text || blockId}</p><p className="muted">{formatBlockLocator(locator)}</p><Link className="button small" href={withQuery("/sources/", { case: caseId, source: sourceId, block: blockId })}>Read exact block</Link>{isCited(sourceId, blockId) ? <button className="button small" type="button" onClick={() => onRemove(sourceId, blockId)} disabled={!canCite}>Remove citation</button> : <button className="button small" type="button" onClick={() => onCite(sourceId, blockId)} disabled={!canCite || withdrawn}>Cite block</button>}</div>;
  return <details className="evidence-inspector"><summary>Evidence search and citations <span>{inventory.sources.length}{inventory.next_cursor ? "+" : ""} sources</span></summary>
    <div className="field"><label htmlFor="report-evidence-search">Find filenames, source IDs, block text or locators</label><input id="report-evidence-search" type="search" maxLength={200} value={query} onChange={(event) => setQuery(event.target.value)} /></div>
    {inventoryError ? <StateNote tone="critical" live="alert">{inventoryError}</StateNote> : null}
    {query.trim() ? <>{search.loading || search.error || !search.matches.length ? <LoadState loading={search.loading} error={search.error} empty="No case evidence matches this search." /> : null}<div className="evidence-source-list">{search.matches.map((match) => <section key={`${match.source_id}:${match.block_id}`}><h4>{match.filename}</h4>{block(match.source_id, match.block_id, match.text, match.locator)}</section>)}</div>{search.next_cursor ? <button className="button small" type="button" disabled={search.loading} onClick={() => void search.more()}>More search results</button> : null}</> : <div className="evidence-source-list">
      {inventory.sources.map((summary) => <details key={summary.id} onToggle={(event) => { if (event.currentTarget.open) setSelectedId(summary.id); }}><summary>{summary.filename}<code>{summary.id}</code> · {summary.block_count} blocks{summary.withdrawn ? " · Withdrawn" : ""}</summary>{selectedId === summary.id ? <>{!source || sourceError ? <LoadState loading={!source && !sourceError} error={sourceError} /> : null}{source?.id === summary.id ? <>{source.withdrawn ? <StateNote tone="warning">Withdrawn evidence cannot be cited as current support.</StateNote> : null}{source.blocks.slice(0, blockLimit).map((item) => block(source.id, item.block_id, item.text || "", item.locator, source.withdrawn))}{source.blocks.length > blockLimit ? <button className="button small" type="button" onClick={() => setBlockLimit((limit) => limit + 40)}>Show more blocks</button> : null}</> : null}</> : null}</details>)}
      {inventory.next_cursor ? <button className="button small" type="button" disabled={moreBusy} onClick={() => void moreSources()}>More sources</button> : null}
    </div>}
  </details>;
}
