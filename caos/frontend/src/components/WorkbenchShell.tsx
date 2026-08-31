"use client";

import Link from "next/link";
import { KeyboardEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import {
  CaseRecord,
  Destination,
  SnapshotView,
  destinationMeta,
  evidenceKind,
  withQuery,
  workflowFor,
  workflows,
} from "../lib/workbench";
// The authority lifecycle has one declaration, in the reducer that owns it.
import type { AuthorityStatus } from "../lib/workspaceAuthority";

export type DrawerState = {
  kind: "evidence";
  evidenceId: string;
  source: {
    id: string;
    filename: string;
    sha256: string;
    blocks: { block_id: string; locator: Record<string, unknown>; text?: string }[];
  };
};

type Props = {
  active: Destination;
  authority: SnapshotView | null;
  authorityStatus: AuthorityStatus;
  cases: CaseRecord[];
  caseId: string;
  drawer: DrawerState | null;
  error: string;
  onCaseChange: (caseId: string) => void;
  onDrawerChange: (drawer: DrawerState | null) => void;
  role: string;
  runId: string;
  runIsLive: boolean;
  selectedCase: CaseRecord | null;
  // An unrecognised path still gets the shell, but it must not claim to be a
  // destination: `active` falls back to Cases for the rail, the title does not.
  unknownRoute?: boolean;
  children: ReactNode;
};

export default function WorkbenchShell({
  active,
  authority,
  authorityStatus,
  cases,
  caseId,
  drawer,
  error,
  onCaseChange,
  onDrawerChange,
  role,
  runId,
  runIsLive,
  selectedCase,
  unknownRoute = false,
  children,
}: Props) {
  const activeWorkflow = workflowFor(active);
  const meta = destinationMeta[active];
  const railRef = useRef<HTMLElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const drawerRef = useRef<HTMLDialogElement>(null);
  const drawerHeadingRef = useRef<HTMLHeadingElement>(null);
  const drawerTriggerRef = useRef<HTMLElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeResult, setActiveResult] = useState(0);

  const caseItems = useMemo(() => cases.filter((item) =>
    `${item.issuer} ${item.name} ${item.sector}`.toLowerCase().includes(query.toLowerCase()),
  ), [cases, query]);
  const workflowItems = useMemo(() => workflows.filter((item) =>
    item.label.toLowerCase().includes(query.toLowerCase()),
  ), [query]);
  const toolItems = useMemo(() => workflows.flatMap((workflow) => workflow.tools ?? []).filter((tool) =>
    !workflows.some((workflow) => workflow.href === tool.href)
      && tool.label.toLowerCase().includes(query.toLowerCase()),
  ), [query]);
  const exactEvidenceKind = caseId ? evidenceKind(query) : null;
  const resultCount = caseItems.length + workflowItems.length + toolItems.length + (exactEvidenceKind ? 1 : 0);

  const openPalette = () => {
    setPaletteOpen(true);
    setQuery("");
    setActiveResult(0);
    if (!dialogRef.current?.open) dialogRef.current?.showModal();
    window.requestAnimationFrame(() => searchRef.current?.focus());
  };

  const closePalette = () => dialogRef.current?.close();

  const closeDrawer = () => {
    onDrawerChange(null);
    const trigger = drawerTriggerRef.current;
    window.requestAnimationFrame(() => trigger?.focus());
  };

  useEffect(() => {
    railRef.current?.querySelector<HTMLElement>('[aria-current="page"]')?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [active]);

  useEffect(() => {
    const dialog = drawerRef.current;
    if (!dialog) return;
    if (!drawer) {
      if (dialog.open) dialog.close();
      return;
    }
    if (!dialog.open) {
      drawerTriggerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      dialog.showModal();
    }
    const frame = window.requestAnimationFrame(() => drawerHeadingRef.current?.focus());
    return () => window.cancelAnimationFrame(frame);
  }, [drawer]);

  useEffect(() => {
    const openShortcut = (event: globalThis.KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        openPalette();
      }
    };
    window.addEventListener("keydown", openShortcut);
    return () => window.removeEventListener("keydown", openShortcut);
  });

  const paletteKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closePalette();
      return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!resultCount) return;
      const step = event.key === "ArrowDown" ? 1 : -1;
      setActiveResult((current) => (current + step + resultCount) % resultCount);
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      resultRef.current?.querySelectorAll<HTMLElement>("[role=option]")[activeResult]?.click();
    }
  };

  const workflowHref = (href: string, destination?: Destination) => withQuery(href, {
    case: caseId || undefined,
    run: destination === "Run Console" ? runId || undefined : undefined,
  });
  const accepted = authority?.accepted;
  const authorityPending = Boolean(caseId) && (authorityStatus === "idle" || authorityStatus === "loading");
  const acceptedSnapshotIdentity = !caseId
    ? "No case selected"
    : authorityPending
    ? "Loading authority…"
    : authorityStatus === "error"
      ? "Authority unavailable"
      : accepted?.id ?? "No accepted snapshot";
  const acceptedSourceSetIdentity = !caseId
    ? "Not applicable"
    : authorityPending
    ? "Loading authority…"
    : authorityStatus === "error"
      ? "Authority unavailable"
      : accepted
        ? accepted.source_set_version == null ? "Version unavailable" : `v${accepted.source_set_version}`
        : "No accepted source set";
  const drawerTitle = drawer ? `Evidence ${drawer.evidenceId}` : "Context";
  let drawerBody: ReactNode = null;
  if (drawer) {
    drawerBody = <div className="state-block">
      <dl>
        <dt>Stable ID</dt><dd className="mono">{drawer.evidenceId}</dd>
        <dt>Filename</dt><dd>{drawer.source.filename}</dd>
        <dt>SHA-256</dt><dd className="mono">{drawer.source.sha256}</dd>
        <dt>Accepted snapshot</dt><dd className="mono">{acceptedSnapshotIdentity}</dd>
        <dt>Accepted source set</dt><dd className="mono">{acceptedSourceSetIdentity}</dd>
      </dl>
      <p className="status warning">Source-level reference; no block locator supplied by this artifact.</p>
      <h3>Available source text</h3>
      <div className="source-blocks">
        {drawer.source.blocks.slice(0, 20).map((block) => <article className="source-block" key={block.block_id}>
          <div className="eyebrow">{block.block_id}</div>
          <p>{block.text || "No extracted text."}</p>
        </article>)}
        {!drawer.source.blocks.length && <p className="muted">No extracted source text.</p>}
        {drawer.source.blocks.length > 20 && <p className="muted">Showing the first 20 blocks. Open the full source for the remaining {drawer.source.blocks.length - 20} blocks.</p>}
      </div>
      <Link className="button small" href={`${withQuery("/sources", { case: caseId })}#source-${drawer.source.id}`} onNavigate={closeDrawer}>Open full source</Link>
    </div>;
  }
  const evidenceHref = exactEvidenceKind === "source"
    ? withQuery("/sources", { case: caseId, source: query.trim() })
    : withQuery("/sources", { case: caseId, artifact: query.trim() });
  let resultIndex = 0;

  return <>
    <a className="skip-link" href="#main-content">Skip to content</a>
    <div className="app-shell">
      <aside ref={railRef} className="rail" aria-label="Primary navigation">
        <Link href={workflowHref("/cases")} className="wordmark"><span className="brand-mark" aria-hidden="true">C</span><span>CAOS<small>Credit Agent OS</small></span></Link>
        <nav aria-label="Workflows" className="nav-group">
          <div className="nav-label">Workspace</div>
          {workflows.map((workflow) => {
            // Exactly one rail entry per page carries aria-current="page" and the
            // active fill: the most specific match for the destination — a tool link
            // when one targets it, the Admin Studio utility link on that surface,
            // otherwise the workflow link.
            const current = workflow.id === activeWorkflow.id
              && !activeWorkflow.tools?.some((tool) => tool.destination === active)
              && active !== "Admin Studio";
            return <Link
              aria-current={current ? "page" : undefined}
              className={`nav-link ${current ? "active" : ""}`}
              href={workflowHref(workflow.href)}
              key={workflow.id}
            >{workflow.label}</Link>;
          })}
        </nav>
        {activeWorkflow.tools?.length ? <nav aria-label={`${activeWorkflow.label} tools`} className="nav-group">
          <div className="nav-label">Analysis tools</div>
          {activeWorkflow.tools.map((tool) => <Link
            aria-current={active === tool.destination ? "page" : undefined}
            className={`nav-link ${active === tool.destination ? "active" : ""}`}
            href={workflowHref(tool.href, tool.destination)}
            key={tool.destination}
          >{tool.label}{tool.destination === "Run Console" && runIsLive && <span className="shortcut">LIVE<span className="sr-only"> run in progress</span></span>}</Link>)}
        </nav> : null}
        <div className="rail-spacer" />
        <nav className="nav-group governance-nav" aria-label="Governance"><div className="nav-label">Governance</div><Link className={`nav-link ${active === "Admin Studio" ? "active" : ""}`} aria-current={active === "Admin Studio" ? "page" : undefined} href={workflowHref("/admin-studio")}>Admin</Link></nav>
        <div className="rail-meta"><span>{role === "READER" ? "Reader" : role.toLowerCase().replace(/^./, (value) => value.toUpperCase())}</span><span>{selectedCase ? selectedCase.issuer : "No credit selected"}</span><span>Desktop workbench</span></div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="topbar-heading"><span className="meta-label">{meta.kicker}</span><h1>{unknownRoute ? "Page not found" : meta.title}</h1></div>
          <div className="top-actions">
            {selectedCase && active !== "Sources" ? <Link className="button quiet" href={workflowHref("/sources")}>Sources &amp; evidence</Link> : null}
            <span className="reading-label">Reading: {meta.reading}</span>
            <label className="sr-only" htmlFor="case-select">Select case</label>
            <select id="case-select" aria-label="Select case" value={caseId} onChange={(event) => onCaseChange(event.target.value)}>
              <option value="">Select case</option>
              {cases.map((item) => <option key={item.id} value={item.id}>{item.issuer} — {item.name}</option>)}
            </select>
            <button ref={triggerRef} className="button small" type="button" aria-label="Open command palette" onClick={openPalette}>Command <span className="shortcut">⌘K</span></button>
          </div>
        </header>
        <div role="region" className="authority-strip" aria-label="Visible authority" tabIndex={0}>
          <span className="authority-dot" aria-hidden="true" />
          <span><b>Credit:</b> {selectedCase ? selectedCase.issuer : "None selected"}</span>
          <span><b>Accepted:</b> {acceptedSnapshotIdentity}</span>
          <span><b>Selected run:</b> {runId ? `${runId}${runIsLive ? " · live" : ""}` : "None"}</span>
          <span><b>Source set:</b> {acceptedSourceSetIdentity}</span>
          {(authority?.switch_required || authority?.diff?.changed) && <span className="status warning">Review required</span>}
        </div>
        {/* `tabIndex={-1}` is what makes this landmark a real focus target. Without
            it the skip link moved the scroll and the browser's sequential focus
            starting point but left `document.activeElement` on <body>, so a screen
            reader never entered the content (WCAG 2.4.1); it is also where Workspace
            sends focus when a route change or a governed write destroys the element
            the user was on (WCAG 2.4.3). */}
        <main className={`content${active === "Report Studio" ? " report-content" : ""}`} id="main-content" tabIndex={-1}>
          {error && <div className="error global-error" role="alert" aria-live="assertive">{error}</div>}
          {children}
        </main>
      </div>
    </div>
    <dialog
      ref={dialogRef}
      aria-labelledby="palette-title"
      onClose={() => { setPaletteOpen(false); setQuery(""); triggerRef.current?.focus(); }}
    >
      <div className="dialog-body">
        <div className="panel-header"><h2 id="palette-title">Command palette</h2><button type="button" className="button small" onClick={closePalette}>Close</button></div>
        <div className="field">
          <label htmlFor="command-search">Search cases, workflows or evidence IDs</label>
          <input
            ref={searchRef}
            id="command-search"
            role="combobox"
            aria-controls="command-results"
            aria-expanded={paletteOpen}
            aria-activedescendant={resultCount ? `command-result-${activeResult}` : undefined}
            autoComplete="off"
            value={query}
            onChange={(event) => { setQuery(event.target.value); setActiveResult(0); }}
            onKeyDown={paletteKeyDown}
          />
        </div>
        <div ref={resultRef} id="command-results" role="listbox">
          {caseItems.length > 0 && <div role="group" aria-labelledby="palette-cases-label"><div className="palette-group-label" id="palette-cases-label">Cases</div>{caseItems.map((item) => {
            const index = resultIndex++;
            return <button
              id={`command-result-${index}`}
              role="option"
              aria-selected={activeResult === index}
              className="nav-link"
              type="button"
              tabIndex={-1}
              key={item.id}
              onClick={() => { onCaseChange(item.id); closePalette(); }}
            >{item.issuer} / {item.name}<span className="muted">{item.sector}</span></button>;
          })}</div>}
          {workflowItems.length > 0 && <div role="group" aria-labelledby="palette-workflows-label"><div className="palette-group-label" id="palette-workflows-label">Workflows</div>{workflowItems.map((workflow) => {
            const index = resultIndex++;
            return <Link
              id={`command-result-${index}`}
              role="option"
              aria-selected={activeResult === index}
              className="nav-link"
              tabIndex={-1}
              key={workflow.id}
              href={workflowHref(workflow.href)}
              onClick={closePalette}
            >Open {workflow.label}</Link>;
          })}</div>}
          {toolItems.length > 0 && <div role="group" aria-labelledby="palette-tools-label"><div className="palette-group-label" id="palette-tools-label">Tools</div>{toolItems.map((tool) => {
            const index = resultIndex++;
            return <Link
              id={`command-result-${index}`}
              role="option"
              aria-selected={activeResult === index}
              className="nav-link"
              tabIndex={-1}
              key={tool.destination}
              href={workflowHref(tool.href, tool.destination)}
              onClick={closePalette}
            >Open {tool.label}</Link>;
          })}</div>}
          {exactEvidenceKind && (() => {
            const index = resultIndex++;
            return <Link
              id={`command-result-${index}`}
              role="option"
              aria-selected={activeResult === index}
              className="nav-link"
              tabIndex={-1}
              href={evidenceHref}
              onClick={closePalette}
            >Open {exactEvidenceKind} ID in this case</Link>;
          })()}
          {!resultCount && <p className="muted">No matches</p>}
        </div>
      </div>
    </dialog>
    <dialog
      className="context-drawer"
      id="context-drawer"
      ref={drawerRef}
      aria-labelledby="drawer-title"
      onClose={closeDrawer}
    >
      <div className="drawer-header">
        <div>
          <span className="eyebrow">CONTEXT</span>
          <h2 id="drawer-title" ref={drawerHeadingRef} tabIndex={-1}>{drawerTitle}</h2>
        </div>
        <button className="button small" type="button" onClick={() => drawerRef.current?.close()}>Close</button>
      </div>
      <div className="drawer-body">{drawerBody}</div>
    </dialog>
  </>;
}
