"use client";

import Link from "next/link";
import {
  KeyboardEvent as ReactKeyboardEvent,
  PointerEvent as ReactPointerEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { LoadState, StateBlock, Unavailable } from "../states";
import {
  api as request,
  assumptionRegistryPath,
  firstErrorMessage,
  isUnavailableRoute,
  type ModelBuild,
  type ModelInventory,
  type ModelReadiness,
  type WorksheetCell,
  type WorksheetResponse,
  type WorksheetTab,
} from "../../lib/api";
import { formatDate, humanizeCode, withQuery } from "../../lib/workbench";
import {
  applyAssumptionValue,
  assumptionChangeCount,
  assumptionKey,
  assumptionScope,
  mergeRebasedAssumptions,
  normalizeAssumptions,
  previewMatchesDraft,
  primaryModelAction,
  worksheetCellAuthority,
  worksheetColumns,
  formatModelValue,
  type AssumptionDefinition,
  type AssumptionRegistry,
  type ModelAssumptionValue,
  type ModelCase,
  type ModelPreview,
  type WireAssumptionValue,
  type WorksheetPayload,
} from "./modelBuilderState";
import styles from "./ModelBuilder.module.css";

const apiBase = process.env.NEXT_PUBLIC_API_URL || "";
const PX_PER_STEP = 4;
const TORNADO_METRICS = [
  { id: "net_leverage", label: "Net leverage", unit: "x" },
  { id: "cumulative_fcf", label: "Cumulative FCF", unit: "$M" },
  { id: "cash_and_equivalents", label: "Cash", unit: "$M" },
  { id: "interest_coverage", label: "Interest coverage", unit: "x" },
] as const;

const worksheetFillClasses: Record<string, string> = {
  "0a2e63": "worksheet-fill-section",
  "1f4e78": "worksheet-fill-header",
  d9eaf7: "worksheet-fill-subheader",
  eaf3f8: "worksheet-fill-label",
  fff4cc: "worksheet-fill-input",
  e2f0d9: "worksheet-fill-positive",
  fce4d6: "worksheet-fill-negative",
  e7e6e6: "worksheet-fill-muted",
};

type RevisionExport = {
  status: "NOT_REQUESTED" | "QUEUED" | "EXPORTING" | "READY" | "FAILED";
  error?: { code: string; detail: string } | null;
  filename?: string;
};
type ModelRevision = Omit<ModelPreview, "draft_generation" | "deltas" | "worksheet"> & {
  id: string;
  effective_assumptions: WireAssumptionValue[];
  worksheet?: WorksheetPayload;
  note: string;
  revision_number: number;
  created_by: string;
  created_at: string;
  state: "ACTIVE" | "SUPERSEDED" | "STALE";
  export?: RevisionExport | null;
};
type RebasePreview = {
  build_id: string;
  compatible: Record<string, unknown>[];
  changed: Record<string, unknown>[];
  invalidated: Record<string, unknown>[];
  candidate_assumptions: WireAssumptionValue[];
};
type TornadoBar = {
  assumption_id: string;
  label: string;
  unit: string;
  swing: string;
  low: string;
  high: string;
};
type TornadoResult = {
  build_id: string;
  draft_generation: number;
  case: ModelCase;
  output_period_id: string;
  output_id: string;
  intensity: number;
  baseline: string;
  bars: TornadoBar[];
};
type ConflictMetadata = {
  current?: ModelRevision | null;
  current_build?: { id?: string; input_fingerprint?: string; payload_digest?: string } | null;
};
type DraftAuthority = { buildId: string; registryDigest: string; parentRevisionId: string | null };

class ModelRequestError extends Error {
  constructor(readonly status: number, readonly detail: unknown) {
    super(typeof detail === "string" ? detail : `Request failed (${status})`);
  }
}

async function modelRequest<T>(path: string, options: RequestInit, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    ...options,
    signal,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new ModelRequestError(response.status, body?.detail ?? body);
  return body as T;
}

function formatWorksheetValue(cell?: WorksheetCell) {
  if (!cell || cell.value === null || cell.value === "") return "";
  if (typeof cell.value !== "number") return String(cell.value);
  const numberFormat = cell.number_format || "";
  if (numberFormat.includes("%")) return `${(cell.value * 100).toFixed(1)}%`;
  if (numberFormat.includes("0.0x")) return `${cell.value.toFixed(1)}x`;
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(cell.value);
}

function WorksheetGrid({
  tab,
  selected,
  onSelect,
}: {
  tab: WorksheetTab;
  selected: WorksheetCell | null;
  onSelect: (cell: WorksheetCell) => void;
}) {
  const cells = useMemo(() => new Map(tab.cells.map((cell) => [`${cell.row}:${cell.column}`, cell])), [tab.cells]);
  const columns = useMemo(() => worksheetColumns(tab.max_column), [tab.max_column]);
  const [activeCell, setActiveCell] = useState({ row: 1, column: 1 });
  const onCellKeyDown = (event: ReactKeyboardEvent<HTMLTableCellElement>, row: number, column: number, cell?: WorksheetCell) => {
    if ((event.key === "Enter" || event.key === " ") && cell && (cell.source_refs || cell.formula)) {
      event.preventDefault();
      onSelect(cell);
      return;
    }
    const movement = {
      ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1],
    }[event.key];
    if (!movement) return;
    event.preventDefault();
    const next = {
      row: Math.min(tab.max_row, Math.max(1, row + movement[0])),
      column: Math.min(tab.max_column, Math.max(1, column + movement[1])),
    };
    setActiveCell(next);
    event.currentTarget.closest("table")?.querySelector<HTMLTableCellElement>(`td[data-row="${next.row}"][data-column="${next.column}"]`)?.focus();
  };
  return <div className="worksheet-scroll" tabIndex={0} role="region" aria-label={`${tab.title} worksheet; scroll horizontally and vertically`}>
    <p className="worksheet-authority-note">Historical and calculated cells are locked. Change forward inputs in Forecast assumptions; only projected periods recalculate.</p>
    <table className="worksheet-grid">
      <caption className="sr-only">Read-only {tab.title} worksheet. Formula values are calculated on the server.</caption>
      <colgroup><col className="worksheet-row-number" />{columns.map((column) => <col key={column.column} />)}</colgroup>
      <thead><tr><th scope="col"><span className="sr-only">Row number</span></th>{columns.map((column) => <th scope="col" key={column.column}>{column.letter}</th>)}</tr></thead>
      <tbody>{Array.from({ length: tab.max_row }, (_, rowIndex) => {
        const row = rowIndex + 1;
        return <tr key={row}><th scope="row">{row}</th>{Array.from({ length: tab.max_column }, (_unused, columnIndex) => {
          const cell = cells.get(`${row}:${columnIndex + 1}`);
          const fillClass = cell?.style?.fill ? worksheetFillClasses[cell.style.fill.toLowerCase()] || "" : "";
          const authority = worksheetCellAuthority(cell?.write_class ?? null);
          const className = [
            "worksheet-cell", authority.className, fillClass,
            cell?.style?.bold ? "is-bold" : "", cell?.style?.italic ? "is-italic" : "",
            cell?.value_type === "number" || cell?.value_type === "formula" && typeof cell.value === "number" ? "num" : "",
            selected?.address === cell?.address ? "is-selected" : "",
          ].filter(Boolean).join(" ");
          const value = formatWorksheetValue(cell);
          const column = columnIndex + 1;
          const address = cell?.address || `${columns[columnIndex]?.letter || column}${row}`;
          const hasLineage = Boolean(cell && (cell.source_refs || cell.formula));
          return <td key={column} className={className} title={cell?.formula ? `${authority.label} · ${cell.formula}` : authority.label} data-write-class={cell?.write_class || "LOCKED"} data-address={address} data-row={row} data-column={column} tabIndex={activeCell.row === row && activeCell.column === column ? 0 : -1} aria-label={`${address}: ${value || "blank"}. ${authority.label}.${hasLineage ? " Press Enter to show lineage." : ""}`} onFocus={() => setActiveCell({ row, column })} onKeyDown={(event) => onCellKeyDown(event, row, column, cell)}>{hasLineage && cell ? <button className="worksheet-cell-link" type="button" tabIndex={-1} aria-label={`Show lineage for ${cell.semantic_id || cell.address}`} aria-controls="model-cell-lineage" aria-expanded={selected?.address === cell.address} onClick={() => { setActiveCell({ row, column }); onSelect(cell); }}>{value || "—"}</button> : value}</td>;
        })}</tr>;
      })}</tbody>
    </table>
  </div>;
}

function WorksheetSurface({ payload }: { payload: WorksheetPayload }) {
  const [activeTab, setActiveTab] = useState(payload.tabs[0]?.id || "");
  const [selectedCell, setSelectedCell] = useState<WorksheetCell | null>(null);
  const tab = payload.tabs.find((item) => item.id === activeTab) || payload.tabs[0] || null;
  const selectTab = (next: WorksheetTab) => { setActiveTab(next.id); setSelectedCell(null); };
  const onTabKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>, index: number) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const nextIndex = event.key === "Home" ? 0 : event.key === "End" ? payload.tabs.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + payload.tabs.length) % payload.tabs.length;
    selectTab(payload.tabs[nextIndex]);
    document.getElementById(`model-tab-${payload.tabs[nextIndex].id}`)?.focus();
  };
  if (!tab) return <div className="empty">The saved model has no worksheet tabs.</div>;
  return <>
    <div className="worksheet-tabs" role="tablist" aria-label="Model worksheets">{payload.tabs.map((item, index) => <button id={`model-tab-${item.id}`} key={item.id} className="worksheet-tab" type="button" role="tab" aria-selected={item.id === tab.id} aria-controls="model-worksheet-panel" tabIndex={item.id === tab.id ? 0 : -1} onClick={() => selectTab(item)} onKeyDown={(event) => onTabKeyDown(event, index)}>{item.title}</button>)}</div>
    <div id="model-worksheet-panel" role="tabpanel" aria-labelledby={`model-tab-${tab.id}`}><WorksheetGrid tab={tab} selected={selectedCell} onSelect={setSelectedCell} /></div>
    <aside className={styles.lineage} id="model-cell-lineage" aria-labelledby="model-cell-lineage-heading">
      <h3 id="model-cell-lineage-heading">Cell lineage</h3>
      {selectedCell ? <><dl className="state-facts"><dt>Cell</dt><dd className="mono">{tab.title}!{selectedCell.address}</dd><dt>Owner</dt><dd>{selectedCell.owner || "CP-MODEL"}</dd><dt>Period</dt><dd className="mono">{selectedCell.period_id || "—"}</dd></dl>{selectedCell.formula ? <code className="lineage-code">{selectedCell.formula}</code> : null}<p className="mono lineage-source">{selectedCell.source_refs || "Calculated on the server from mapped inputs."}</p></> : <p className="muted">Select a sourced or calculated worksheet value to inspect its lineage.</p>}
    </aside>
  </>;
}

function ForecastScrubber({
  value,
  mixed = false,
  disabled,
  label,
  minimum,
  maximum,
  step,
  onCommit,
}: {
  value: string;
  mixed?: boolean;
  disabled: boolean;
  label: string;
  minimum: number;
  maximum: number;
  step: number;
  onCommit: (value: string) => boolean;
}) {
  const [input, setInput] = useState(value);
  const inputRef = useRef(value);
  const drag = useRef<{ x: number; value: number } | null>(null);
  const update = (next: string) => { inputRef.current = next; setInput(next); };
  const commit = (next = inputRef.current) => {
    if (next.trim() === "" || !onCommit(next)) update(value);
  };
  const onPointerDown = (event: ReactPointerEvent<HTMLInputElement>) => {
    if (disabled || event.button !== 0) return;
    const numeric = Number(inputRef.current);
    if (!Number.isFinite(numeric)) return;
    drag.current = { x: event.clientX, value: numeric };
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const onPointerMove = (event: ReactPointerEvent<HTMLInputElement>) => {
    if (!drag.current) return;
    const steps = Math.round((event.clientX - drag.current.x) / PX_PER_STEP);
    const next = Math.min(maximum, Math.max(minimum, drag.current.value + steps * step));
    update(String(Number(next.toFixed(10))));
  };
  const finishDrag = (event: ReactPointerEvent<HTMLInputElement>, save: boolean) => {
    if (!drag.current) return;
    drag.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    if (save) commit();
  };
  return <input className={styles.scrubber} aria-label={label} title={`${label}. Drag horizontally or type a value.`} type="number" inputMode="decimal" min={minimum} max={maximum} step={step} value={input} placeholder={mixed ? "Mixed" : undefined} disabled={disabled} onChange={(event) => update(event.currentTarget.value)} onBlur={() => commit()} onKeyDown={(event) => { if (event.key === "Enter") event.currentTarget.blur(); }} onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={(event) => finishDrag(event, true)} onPointerCancel={(event) => finishDrag(event, false)} />;
}

function TornadoChart({ result, metric }: { result: TornadoResult; metric: (typeof TORNADO_METRICS)[number] }) {
  const baseline = Number(result.baseline);
  const values = [baseline, ...result.bars.flatMap((bar) => [Number(bar.low), Number(bar.high)])].filter(Number.isFinite);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const span = maximum - minimum || 1;
  const scale = (value: number) => (value - minimum) / span * 100;
  const format = (value: number) => metric.unit === "x" ? `${value.toFixed(2)}x` : `$${Math.round(value).toLocaleString()}M`;
  return <div className={styles.tornadoChart} role="group" aria-label={`${metric.label} tornado for ${result.case}, ${result.output_period_id}`}>
    {result.bars.map((bar) => {
      const first = Number(bar.low);
      const second = Number(bar.high);
      const low = Math.min(first, second);
      const high = Math.max(first, second);
      return <div className={styles.tornadoRow} key={bar.assumption_id} title={`${bar.label}: ${format(first)} to ${format(second)}`}>
        <span>{bar.label}</span><span className="mono num">{format(low)}</span>
        <span className={styles.tornadoTrack}><span className={styles.tornadoBar} style={{ left: `${scale(low)}%`, width: `${Math.max(0, scale(high) - scale(low))}%` }} /><span className={styles.tornadoBase} style={{ left: `${scale(baseline)}%` }} /></span>
        <span className="mono num">{format(high)}</span>
      </div>;
    })}
    <p className="muted">Bar = low–high outcome · tick = {format(baseline)} current forecast · all other drivers held constant.</p>
  </div>;
}

function modelStatusTone(status?: ModelReadiness["status"]) {
  if (status === "READY") return "success";
  if (status === "FAILED" || status === "NOT_READY") return "critical";
  return "warning";
}

export default function ModelBuilder({
  caseId,
  role,
  onDraftStateChange,
}: {
  caseId: string;
  role: string;
  onDraftStateChange?: (dirty: boolean) => void;
}) {
  const [inventory, setInventory] = useState<ModelInventory | null>(null);
  const [applicationWorksheet, setApplicationWorksheet] = useState<WorksheetResponse | null>(null);
  const [registry, setRegistry] = useState<AssumptionRegistry | null>(null);
  const [revisions, setRevisions] = useState<ModelRevision[]>([]);
  const [baseline, setBaseline] = useState<ModelAssumptionValue[]>([]);
  const [draft, setDraft] = useState<ModelAssumptionValue[]>([]);
  const [draftGeneration, setDraftGeneration] = useState(0);
  const [draftAuthority, setDraftAuthority] = useState<DraftAuthority | null>(null);
  const [preview, setPreview] = useState<ModelPreview | null>(null);
  const [rebase, setRebase] = useState<RebasePreview | null>(null);
  const [tornado, setTornado] = useState<TornadoResult | null>(null);
  const [tornadoLoading, setTornadoLoading] = useState(false);
  const [tornadoError, setTornadoError] = useState("");
  const [selectedCase, setSelectedCase] = useState<ModelCase>("BASE");
  const [tornadoOutputId, setTornadoOutputId] = useState<(typeof TORNADO_METRICS)[number]["id"]>("net_leverage");
  const [tornadoIntensity, setTornadoIntensity] = useState(1);
  const [signOffNote, setSignOffNote] = useState("");
  const [conflict, setConflict] = useState<ConflictMetadata | null>(null);
  const [unavailable, setUnavailable] = useState<{ worksheet?: boolean; tornado?: boolean; rebase?: boolean; revisionExport?: boolean; revisionDownload?: boolean }>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [pending, setPending] = useState("");
  const [message, setMessage] = useState("");
  const [loadedCaseId, setLoadedCaseId] = useState("");
  const requestGeneration = useRef(0);
  const actionGeneration = useRef(0);
  const previewGeneration = useRef(0);
  const tornadoGeneration = useRef(0);
  const previewTimer = useRef(0);
  const draftGenerationRef = useRef(0);
  const authorityKey = useRef("");
  const draftCaseIdRef = useRef("");
  const baselineRef = useRef<ModelAssumptionValue[]>([]);
  const draftRef = useRef<ModelAssumptionValue[]>([]);
  const dirtyRef = useRef(false);
  const draftAuthorityRef = useRef<DraftAuthority | null>(null);
  const canWrite = role !== "READER";

  const refresh = useCallback(async (signal?: AbortSignal, showLoading = true) => {
    if (!caseId) return;
    const expectedCaseId = caseId;
    const generation = ++requestGeneration.current;
    if (showLoading) setLoading(true);
    setLoadError("");
    try {
      const [nextReadiness, nextModels] = await Promise.all([
        request<ModelReadiness>(`/api/cases/${expectedCaseId}/model`, {}, signal),
        request<{ builds: ModelBuild[] }>(`/api/cases/${expectedCaseId}/models`, {}, signal),
      ]);
      const nextInventory: ModelInventory = { readiness: nextReadiness, builds: nextModels.builds };
      const nextBuild = nextInventory.readiness.build || nextInventory.builds[0] || null;
      let nextRegistry: AssumptionRegistry | null = null;
      let nextRevisions: ModelRevision[] = [];
      let nextWorksheet: WorksheetResponse | null = null;
      let worksheetUnavailable = false;
      if (nextBuild?.status === "READY") {
        const [registryResponse, revisionResponse, worksheetResponse] = await Promise.all([
          request<AssumptionRegistry>(assumptionRegistryPath(expectedCaseId, nextBuild.id), {}, signal),
          request<{ revisions: ModelRevision[] }>(`/api/cases/${expectedCaseId}/model-revisions`, {}, signal),
          request<WorksheetResponse>(`/api/cases/${expectedCaseId}/models/${nextBuild.id}/worksheet`, {}, signal).catch((caught) => {
            if (!isUnavailableRoute(caught)) throw caught;
            worksheetUnavailable = true;
            return null;
          }),
        ]);
        if (registryResponse.build_id !== nextBuild.id || registryResponse.input_fingerprint !== nextBuild.input_fingerprint) throw new Error("Assumption registry identity does not match the application model.");
        if (worksheetResponse && (worksheetResponse.build_id !== nextBuild.id || worksheetResponse.input_fingerprint !== nextBuild.input_fingerprint || nextBuild.payload_digest && worksheetResponse.payload_digest !== nextBuild.payload_digest)) throw new Error("Worksheet identity does not match the application model.");
        nextRegistry = registryResponse;
        nextRevisions = revisionResponse.revisions;
        nextWorksheet = worksheetResponse;
      }
      if (generation !== requestGeneration.current || expectedCaseId !== caseId) return;
      const nextActive = nextRevisions.find((item) => item.state === "ACTIVE" && item.build_id === nextBuild?.id) || null;
      const nextAuthorityKey = nextBuild && nextRegistry ? [expectedCaseId, nextBuild.id, nextBuild.input_fingerprint, nextBuild.payload_digest || "", nextRegistry.digest, nextActive?.id || ""].join("|") : `${expectedCaseId}|${nextInventory.readiness.status}`;
      if (nextAuthorityKey !== authorityKey.current) {
        actionGeneration.current += 1;
        previewGeneration.current += 1;
        tornadoGeneration.current += 1;
        const preserveDirtyDraft = draftCaseIdRef.current === expectedCaseId && dirtyRef.current;
        authorityKey.current = nextAuthorityKey;
        if (preserveDirtyDraft) {
          setConflict((current) => current || { current: nextActive, current_build: nextBuild });
          setMessage("Authority changed. Your local forecast is preserved; review and rebase before saving it.");
        } else {
          draftGenerationRef.current = 0;
          const nextBaseline = nextRegistry ? normalizeAssumptions(nextActive?.effective_assumptions || nextRegistry.defaults) : [];
          const nextDraftAuthority = nextBuild && nextRegistry ? { buildId: nextBuild.id, registryDigest: nextRegistry.digest, parentRevisionId: nextActive?.id || null } : null;
          draftCaseIdRef.current = expectedCaseId;
          baselineRef.current = nextBaseline;
          draftRef.current = nextBaseline;
          dirtyRef.current = false;
          draftAuthorityRef.current = nextDraftAuthority;
          setBaseline(nextBaseline);
          setDraft(nextBaseline);
          setDraftGeneration(0);
          setDraftAuthority(nextDraftAuthority);
          setPreview(null);
          setRebase(null);
          setTornado(null);
          setConflict(null);
          setSignOffNote("");
          setMessage("");
        }
        setPending("");
      }
      setInventory(nextInventory);
      setApplicationWorksheet(nextWorksheet);
      setUnavailable((current) => ({ ...current, worksheet: worksheetUnavailable }));
      setRegistry(nextRegistry);
      setRevisions(nextRevisions);
      setLoadedCaseId(expectedCaseId);
    } catch (caught) {
      if (generation !== requestGeneration.current || caught instanceof DOMException && caught.name === "AbortError") return;
      setLoadError(firstErrorMessage(caught, "Unable to load Model Builder"));
      setLoadedCaseId(expectedCaseId);
    } finally {
      if (generation === requestGeneration.current) setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    requestGeneration.current += 1;
    actionGeneration.current += 1;
    previewGeneration.current += 1;
    tornadoGeneration.current += 1;
    authorityKey.current = "";
    const controller = new AbortController();
    queueMicrotask(() => { if (!controller.signal.aborted) void refresh(controller.signal); });
    return () => { controller.abort(); window.clearTimeout(previewTimer.current); requestGeneration.current += 1; };
  }, [refresh]);

  const status = inventory?.readiness.status;
  const build = inventory?.readiness.build || inventory?.builds[0] || null;
  const activeRevision = revisions.find((item) => item.state === "ACTIVE" && item.build_id === build?.id) || null;
  const currentHeadRevisionId = activeRevision?.id || null;
  const dirtyCount = assumptionChangeCount(baseline, draft);
  const dirty = dirtyCount > 0;
  const authorityMismatch = Boolean(build && registry && draftAuthority && (draftAuthority.buildId !== build.id || draftAuthority.registryDigest !== registry.digest || draftAuthority.parentRevisionId !== currentHeadRevisionId));
  const previewCurrent = Boolean(build && registry && previewMatchesDraft(preview, {
    buildId: build.id,
    buildInputFingerprint: build.input_fingerprint,
    buildPayloadDigest: build.payload_digest || "",
    registryVersion: registry.version,
    registryDigest: registry.digest,
    parentRevisionId: draftAuthority?.parentRevisionId || null,
    expectedHeadRevisionId: draftAuthority?.parentRevisionId || null,
    currentHeadRevisionId,
    draftGeneration,
  }));
  const primaryAction = authorityMismatch ? null : primaryModelAction({ status, canWrite, dirty, previewCurrent });
  const displayWorksheet = (previewCurrent ? preview?.worksheet : null) || activeRevision?.worksheet || applicationWorksheet?.payload || null;
  const worksheetKey = previewCurrent ? preview?.preview_digest : activeRevision?.id || build?.id;
  const selectedMetric = TORNADO_METRICS.find((item) => item.id === tornadoOutputId) || TORNADO_METRICS[0];
  const conflictSourceRevision = draftAuthority?.parentRevisionId ? revisions.find((item) => item.id === draftAuthority.parentRevisionId) || null : null;
  const conflictRebaseRevision = conflictSourceRevision || activeRevision;

  useEffect(() => {
    dirtyRef.current = dirty;
    baselineRef.current = baseline;
    draftRef.current = draft;
    draftAuthorityRef.current = draftAuthority;
  }, [baseline, draft, draftAuthority, dirty]);
  useEffect(() => { onDraftStateChange?.(dirty); }, [dirty, onDraftStateChange]);
  useEffect(() => () => onDraftStateChange?.(false), [onDraftStateChange]);
  useEffect(() => {
    const exportPending = revisions.some((item) => item.export?.status === "QUEUED" || item.export?.status === "EXPORTING");
    if (status !== "QUEUED" && status !== "BUILDING" && !exportPending) return;
    const timer = window.setTimeout(() => { void refresh(undefined, false); }, 1500);
    return () => window.clearTimeout(timer);
  }, [refresh, revisions, status]);

  const previewDraft = async (nextDraft = draftRef.current, nextGeneration = draftGenerationRef.current) => {
    const authority = draftAuthorityRef.current;
    if (!canWrite || !build || !registry || !authority
      || authority.buildId !== build.id || authority.registryDigest !== registry.digest
      || authority.parentRevisionId !== currentHeadRevisionId
      || assumptionChangeCount(baselineRef.current, nextDraft) === 0) return;
    const generation = ++previewGeneration.current;
    const expectedAuthority = authorityKey.current;
    setPending("preview");
    setMessage("");
    try {
      const next = await modelRequest<ModelPreview>(`/api/cases/${caseId}/models/previews`, {
        method: "POST",
        body: JSON.stringify({ build_id: build.id, parent_revision_id: authority.parentRevisionId, registry_version: registry.version, registry_digest: registry.digest, assumptions: nextDraft, draft_generation: nextGeneration }),
      });
      if (generation !== previewGeneration.current || expectedAuthority !== authorityKey.current || nextGeneration !== draftGenerationRef.current || next.draft_generation !== nextGeneration) return;
      setPreview(next);
      setMessage("Forecast recalculated. Historical accounts remain locked; review the model and tornado before saving this version.");
    } catch (caught) {
      if (generation === previewGeneration.current && expectedAuthority === authorityKey.current) setMessage(firstErrorMessage(caught, "Unable to recalculate the forecast"));
    } finally {
      if (generation === previewGeneration.current) setPending("");
    }
  };

  const invalidatePreview = (next: ModelAssumptionValue[]) => {
    actionGeneration.current += 1;
    previewGeneration.current += 1;
    tornadoGeneration.current += 1;
    draftGenerationRef.current += 1;
    draftRef.current = next;
    dirtyRef.current = assumptionChangeCount(baselineRef.current, next) > 0;
    setDraft(next);
    setDraftGeneration(draftGenerationRef.current);
    setTornado(null);
    setMessage("");
    if (pending === "preview") setPending("");
    return draftGenerationRef.current;
  };

  const editAssumption = (definition: AssumptionDefinition, caseName: ModelCase, scope: string, rawValue: string) => {
    if (!canWrite || rawValue.trim() === "") return false;
    try {
      const next = applyAssumptionValue(draftRef.current, definition, caseName, scope, Number(rawValue));
      const generation = invalidatePreview(next);
      window.clearTimeout(previewTimer.current);
      previewTimer.current = window.setTimeout(() => { void previewDraft(next, generation); }, 250);
      return true;
    } catch (caught) {
      setMessage(`${firstErrorMessage(caught, "Unable to update assumption")}. Enter a finite value from ${definition.hard_min} to ${definition.hard_max} for a READY forecast.`);
      return false;
    }
  };

  const runTornado = useCallback(async (draftRows: ModelAssumptionValue[], nextGeneration: number) => {
    if (!canWrite || !build || !registry || !draftAuthority) return;
    const periods = [...new Set(draftRows.filter((row) => row.case === selectedCase).map((row) => row.period_id))].sort();
    const period = periods.at(-1);
    if (!period) return;
    const outputPeriodId = `${selectedCase}::${period}`;
    const generation = ++tornadoGeneration.current;
    const expectedAuthority = authorityKey.current;
    const isCurrent = () => generation === tornadoGeneration.current
      && expectedAuthority === authorityKey.current
      && nextGeneration === draftGenerationRef.current;
    setTornadoLoading(true);
    setTornadoError("");
    try {
      const next = await modelRequest<TornadoResult>(`/api/cases/${caseId}/models/tornado`, {
        method: "POST",
        body: JSON.stringify({ build_id: build.id, parent_revision_id: draftAuthority.parentRevisionId, registry_version: registry.version, registry_digest: registry.digest, assumptions: draftRows, draft_generation: nextGeneration, case: selectedCase, output_period_id: outputPeriodId, output_id: tornadoOutputId, intensity: tornadoIntensity }),
      });
      if (!isCurrent()
        || next.build_id !== build.id
        || next.draft_generation !== nextGeneration
        || next.case !== selectedCase
        || next.output_period_id !== outputPeriodId
        || next.output_id !== tornadoOutputId
        || next.intensity !== tornadoIntensity) return;
      setTornado(next);
    } catch (caught) {
      if (!isCurrent()) return;
      if (isUnavailableRoute(caught)) setUnavailable((current) => ({ ...current, tornado: true }));
      else setTornadoError(firstErrorMessage(caught, "Unable to calculate tornado"));
    } finally {
      if (isCurrent()) setTornadoLoading(false);
    }
  }, [build, canWrite, caseId, draftAuthority, registry, selectedCase, tornadoIntensity, tornadoOutputId]);

  useEffect(() => {
    if (!canWrite || !build || !registry || !draft.length || authorityMismatch || unavailable.tornado) return;
    const timer = window.setTimeout(() => { void runTornado(draft, draftGeneration); }, 150);
    return () => window.clearTimeout(timer);
  }, [authorityMismatch, build, canWrite, draft, draftGeneration, registry, runTornado, unavailable.tornado]);

  const buildModel = async () => {
    const action = ++actionGeneration.current;
    setPending("build"); setMessage("");
    try { await request(`/api/cases/${caseId}/models`, { method: "POST" }); if (action !== actionGeneration.current) return; setMessage(status === "FAILED" ? "Model rebuild queued." : "Model build queued."); await refresh(undefined, false); }
    catch (caught) { if (action === actionGeneration.current) setMessage(firstErrorMessage(caught, "Unable to queue model build")); }
    finally { if (action === actionGeneration.current) setPending(""); }
  };

  const signOff = async () => {
    if (!canWrite || !build || !registry || !draftAuthority || !previewCurrent || !preview || !signOffNote.trim()) return;
    const action = ++actionGeneration.current;
    const expectedAuthority = authorityKey.current;
    setPending("sign-off"); setMessage(""); setConflict(null);
    try {
      await modelRequest<ModelRevision>(`/api/cases/${caseId}/model-revisions/sign-off`, {
        method: "POST",
        body: JSON.stringify({ build_id: build.id, parent_revision_id: draftAuthority.parentRevisionId, registry_version: registry.version, registry_digest: registry.digest, assumptions: draft, draft_generation: draftGeneration, preview_digest: preview.preview_digest, expected_head_revision_id: draftAuthority.parentRevisionId, note: signOffNote.trim() }),
      });
      if (action !== actionGeneration.current || expectedAuthority !== authorityKey.current || draftGeneration !== draftGenerationRef.current) return;
      dirtyRef.current = false;
      setMessage("Model version saved. Exact XLSX export queued.");
      await refresh(undefined, false);
    } catch (caught) {
      if (action !== actionGeneration.current || expectedAuthority !== authorityKey.current) return;
      if (caught instanceof ModelRequestError && caught.status === 409 && caught.detail && typeof caught.detail === "object") {
        setConflict(caught.detail as ConflictMetadata);
        setMessage("Save conflict. The model authority changed; review and rebase your local forecast.");
        await refresh(undefined, false);
      } else setMessage(firstErrorMessage(caught, "Unable to save model version"));
    } finally { if (action === actionGeneration.current) setPending(""); }
  };

  const requestRebase = async (revision: ModelRevision) => {
    if (!canWrite || !build) return;
    const action = ++actionGeneration.current;
    setPending(`rebase:${revision.id}`); setMessage("");
    try {
      const next = await modelRequest<RebasePreview>(`/api/cases/${caseId}/model-revisions/rebase-preview`, { method: "POST", body: JSON.stringify({ revision_id: revision.id, build_id: build.id, draft_generation: draftGeneration + 1 }) });
      if (action !== actionGeneration.current || next.build_id !== build.id) return;
      setRebase(next); setMessage("Rebase candidate calculated. Nothing has been stored.");
    } catch (caught) {
      if (action !== actionGeneration.current) return;
      if (isUnavailableRoute(caught)) setUnavailable((current) => ({ ...current, rebase: true }));
      else setMessage(firstErrorMessage(caught, "Unable to calculate rebase candidate"));
    } finally { if (action === actionGeneration.current) setPending(""); }
  };

  const applyRebase = () => {
    if (!canWrite || !rebase || rebase.build_id !== build?.id || !registry || rebase.invalidated.length) return;
    try {
      const nextBaseline = normalizeAssumptions(activeRevision?.effective_assumptions || rebase.candidate_assumptions);
      const nextDraft = mergeRebasedAssumptions(baselineRef.current, draftRef.current, nextBaseline);
      baselineRef.current = nextBaseline;
      draftAuthorityRef.current = { buildId: build.id, registryDigest: registry.digest, parentRevisionId: activeRevision?.id || null };
      setBaseline(nextBaseline);
      setDraftAuthority(draftAuthorityRef.current);
      setConflict(null);
      const generation = invalidatePreview(nextDraft);
      setRebase(null);
      window.clearTimeout(previewTimer.current);
      previewTimer.current = window.setTimeout(() => { void previewDraft(nextDraft, generation); }, 250);
      setMessage("Local forecast rebased. A fresh preview is being calculated before it can be saved.");
    } catch (caught) { setMessage(firstErrorMessage(caught, "Rebase candidate no longer matches the registry")); }
  };

  const queueRevisionExport = async (revision: ModelRevision) => {
    const action = ++actionGeneration.current;
    setPending(`export:${revision.id}`); setMessage("");
    try { await request(`/api/cases/${caseId}/model-revisions/${revision.id}/export`, { method: "POST" }); if (action !== actionGeneration.current) return; setMessage("Exact version XLSX export queued."); await refresh(undefined, false); }
    catch (caught) {
      if (action !== actionGeneration.current) return;
      if (isUnavailableRoute(caught)) setUnavailable((current) => ({ ...current, revisionExport: true }));
      else setMessage(firstErrorMessage(caught, "Unable to queue version export"));
    } finally { if (action === actionGeneration.current) setPending(""); }
  };

  const downloadRevisionExport = async (revision: ModelRevision) => {
    const action = ++actionGeneration.current;
    setPending(`download:${revision.id}`); setMessage("");
    try {
      const response = await fetch(`${apiBase}/api/cases/${caseId}/model-revisions/${revision.id}/download`);
      if (response.status === 404) { if (action === actionGeneration.current) setUnavailable((current) => ({ ...current, revisionDownload: true })); return; }
      if (!response.ok) throw new Error(`Unable to download the exact version XLSX (${response.status})`);
      const blob = await response.blob();
      if (action !== actionGeneration.current) return;
      const disposition = response.headers.get("content-disposition") || "";
      const filename = /filename="?([^";]+)"?/i.exec(disposition)?.[1] || revision.export?.filename || `${revision.id}.xlsx`;
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url; anchor.download = filename; document.body.appendChild(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url);
    } catch (caught) { if (action === actionGeneration.current) setMessage(firstErrorMessage(caught, "Unable to download the exact version XLSX")); }
    finally { if (action === actionGeneration.current) setPending(""); }
  };

  if (loadError && loadedCaseId === caseId) return <div className="grid"><section className="panel span-12"><div className="panel-header"><h2>Model Builder</h2><span className="status critical">Unavailable</span></div><div className="panel-body"><LoadState loading={false} error={loadError} /></div></section></div>;
  if (!caseId || loadedCaseId !== caseId || loading && !inventory) return <div className="grid"><section className="panel span-12"><div className="panel-header"><h2>Model Builder</h2></div><div className="panel-body"><LoadState loading error={loadError} /></div></section></div>;

  const renderPrimaryAction = () => {
    if (!primaryAction) return null;
    if (primaryAction === "BUILD") return <button data-primary-model-action="BUILD" className="button primary" type="button" disabled={pending === "build"} onClick={() => void buildModel()}>{pending === "build" ? "Queuing…" : status === "FAILED" ? "Retry build" : "Build model"}</button>;
    if (primaryAction === "PREVIEW") return <button data-primary-model-action="PREVIEW" className="button primary" type="button" disabled={pending === "preview"} onClick={() => void previewDraft()}>{pending === "preview" ? "Recalculating…" : "Recalculate forecast"}</button>;
    return <button data-primary-model-action="SIGN_OFF" className="button primary" type="button" disabled={pending === "sign-off" || !signOffNote.trim()} onClick={() => void signOff()}>{pending === "sign-off" ? "Saving…" : "Save model version"}</button>;
  };

  return <div className="grid model-builder analyst-model-builder">
    <section className="panel span-12 model-builder-command">
      <div className="panel-header"><h2>Model Builder</h2><span className={`status ${modelStatusTone(status)}`} role="status" aria-live="polite">{status?.replaceAll("_", " ")}</span></div>
      <div className="panel-body model-builder-command-body"><div><strong>Application model · {activeRevision ? `R${activeRevision.revision_number}` : "Application version"}</strong><p className="muted">{activeRevision ? `${activeRevision.created_by} · ${formatDate(activeRevision.created_at)} · ${activeRevision.note}` : status === "READY" ? "Built from the accepted application and saved as the starting version. Forecast assumptions create the next version." : "Build the application model from accepted credit analysis."}</p></div><div className="model-primary-action">{renderPrimaryAction()}<button className="button small" type="button" disabled={loading} onClick={() => void refresh()}>{loading ? "Refreshing…" : "Refresh"}</button></div></div>
      {status === "NOT_READY" ? <StateBlock tone="warning" title="Accepted analysis required" body="Accept a completed Full Credit run before building the application model." /> : null}
      {status === "NOT_READY" ? <Link className="button small" href={withQuery("/run-console", { case: caseId })}>Open Run Console</Link> : null}
      {status === "QUEUED" || status === "BUILDING" ? <StateBlock title={status === "QUEUED" ? "Build queued" : "Calculating application model"} body="The server is validating canonical inputs and saving the reconciled worksheet." /> : null}
      {status === "FAILED" ? <StateBlock tone="warning" live="alert" code={build?.error?.code || "MODEL_CALCULATION_FAILED"} body={build?.error?.detail || "The model calculation did not complete."} /> : null}
      {inventory?.readiness.blockers.map((blocker) => <div className="callout warning model-blocker" key={blocker.code}><strong>{humanizeCode(blocker.code)}</strong><br />{blocker.detail}</div>)}
      {message ? <p className={message.includes("Unable") || message.includes("conflict") || message.includes("changed") ? "error" : "muted"} role="status" aria-live="polite">{message}</p> : null}
      {conflict || authorityMismatch ? <div className="callout warning" role="alert"><strong>Model authority changed</strong><p>Your local forecast is preserved. Current version <span className="mono">{conflict?.current?.id || currentHeadRevisionId || "Application version"}</span>; draft parent <span className="mono">{draftAuthority?.parentRevisionId || "Application version"}</span>.</p>{conflictRebaseRevision && build?.status === "READY" ? unavailable.rebase ? <Unavailable title="Rebase preview" /> : <button className="button small" type="button" disabled={pending === `rebase:${conflictRebaseRevision.id}`} onClick={() => void requestRebase(conflictRebaseRevision)}>Review and rebase local draft</button> : null}</div> : null}
    </section>

    {status === "READY" && registry ? <section className={`panel span-12 ${styles.workspace}`}>
      <aside className={styles.assumptions} aria-labelledby="forecast-assumptions-heading">
        <div className={styles.sectionHeader}><h3 id="forecast-assumptions-heading">Forecast assumptions</h3><span className={`status ${dirty ? "warning" : "success"}`}>{dirtyCount} CHANGES</span></div>
        <div className={styles.caseSwitch} role="group" aria-label="Forecast case"><button type="button" className={selectedCase === "BASE" ? "button small is-active" : "button small"} aria-pressed={selectedCase === "BASE"} onClick={() => setSelectedCase("BASE")}>Base</button><button type="button" className={selectedCase === "DOWNSIDE" ? "button small is-active" : "button small"} aria-pressed={selectedCase === "DOWNSIDE"} onClick={() => setSelectedCase("DOWNSIDE")}>Downside</button></div>
        <p className="muted">Only forward periods are editable. Drag any value horizontally or type it. “All” broadcasts to exactly the available forecast years.</p>
        <div className={styles.driverList}>{registry.definitions.map((definition) => {
          const rows = draft.filter((row) => row.assumption_id === definition.assumption_id && row.case === selectedCase).sort((left, right) => left.period_id.localeCompare(right.period_id));
          if (!rows.length) return null;
          const scope = assumptionScope(draft, definition.assumption_id, selectedCase, "ALL");
          const step = Number(definition.sensitivity_default.step);
          return <fieldset className={styles.driver} key={`${definition.assumption_id}:${selectedCase}`}><legend><span>{definition.label}</span><small>{definition.unit}</small></legend><div className={styles.forecastValues}><label><span>All forecast years</span><ForecastScrubber key={`${definition.assumption_id}:${selectedCase}:ALL:${draftGeneration}`} value={scope.value} mixed={scope.mixed} label={`${definition.label}, all forecast years, ${selectedCase}`} minimum={Number(definition.hard_min)} maximum={Number(definition.hard_max)} step={step} disabled={!canWrite || !scope.editable} onCommit={(value) => editAssumption(definition, selectedCase, "ALL", value)} /></label>{rows.map((row) => <label key={assumptionKey(row)}><span>{row.period_id}</span><ForecastScrubber key={`${assumptionKey(row)}:${draftGeneration}`} value={row.value === null ? "" : String(row.value)} label={`${definition.label}, ${row.period_id}, ${selectedCase}`} minimum={Number(definition.hard_min)} maximum={Number(definition.hard_max)} step={step} disabled={!canWrite || row.status !== "READY"} onCommit={(value) => editAssumption(definition, selectedCase, row.period_id, value)} />{row.status !== "READY" ? <small>{row.gap_code || row.status}</small> : <small>App {formatModelValue(row.default_value)}</small>}</label>)}</div></fieldset>;
        })}</div>
        {dirty && canWrite ? <div className={styles.signOff}><label htmlFor="model-signoff-note">Sign-Off Note <span aria-hidden="true">*</span></label><textarea id="model-signoff-note" required maxLength={2000} value={signOffNote} onChange={(event) => setSignOffNote(event.target.value)} placeholder="What changed, why, and the evidence behind it." /><p className="muted">Saved with this model version after the current forecast preview completes.</p></div> : null}
        {!canWrite ? <p className="callout">Reader mode: the model and forecast assumptions remain readable. Changes, recalculation, tornado refresh, and saving are unavailable.</p> : null}
      </aside>

      <main className={styles.model} aria-labelledby="application-model-heading">
        <div className={styles.sectionHeader}><h3 id="application-model-heading">{displayWorksheet?.identity.issuer_name || "Application model"}</h3>{pending === "preview" ? <span className="status warning">RECALCULATING</span> : previewCurrent ? <span className="status success">CURRENT</span> : null}</div>
        {displayWorksheet ? <WorksheetSurface key={worksheetKey} payload={displayWorksheet} /> : unavailable.worksheet ? <Unavailable title="Application model worksheet" /> : <LoadState loading error="" />}
      </main>

      <aside className={styles.tornado} aria-labelledby="tornado-heading">
        <div className={styles.sectionHeader}><h3 id="tornado-heading">Tornado</h3>{tornadoLoading ? <span className="status warning">CALCULATING</span> : null}</div>
        <label className={styles.control}>Output<select value={tornadoOutputId} onChange={(event) => setTornadoOutputId(event.target.value as typeof tornadoOutputId)}>{TORNADO_METRICS.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
        <div className={styles.intensity} role="group" aria-label="Driver swing intensity"><span>Swing</span>{([0.5, 1, 1.5] as const).map((value) => <button type="button" className={tornadoIntensity === value ? "button small is-active" : "button small"} aria-pressed={tornadoIntensity === value} key={value} onClick={() => setTornadoIntensity(value)}>±{value}×</button>)}</div>
        {unavailable.tornado ? <Unavailable title="Tornado" /> : tornado && tornado.output_id === tornadoOutputId && tornado.case === selectedCase ? <TornadoChart result={tornado} metric={selectedMetric} /> : tornadoError ? <p className="error" role="alert">{tornadoError}</p> : <p className="muted">The four legacy drivers recalculate against the complete current forecast.</p>}
      </aside>
    </section> : null}

    {status === "READY" ? <section className={`panel span-12 ${styles.versions}`}>
      <details open={Boolean(rebase)}><summary>Model versions</summary>
        <div className="table-wrap" tabIndex={0} role="region" aria-label="Model versions"><table><thead><tr><th scope="col">Version</th><th scope="col">State</th><th scope="col">Saved</th><th scope="col">Sign-Off Note</th><th scope="col">Exact XLSX</th></tr></thead><tbody><tr><th scope="row">Application version</th><td><span className={`status ${activeRevision ? "idle" : "success"}`}>{activeRevision ? "BASELINE" : "CURRENT"}</span></td><td>{build?.completed_at ? formatDate(build.completed_at) : "—"}</td><td>Accepted application assumptions</td><td>{build?.export?.status === "READY" ? <a className="button small" href={`${apiBase}/api/cases/${caseId}/models/${build.id}/download`} download>Download</a> : <span className="muted">{build?.export?.status?.replaceAll("_", " ") || "Not requested"}</span>}</td></tr>{revisions.map((revision) => <tr key={revision.id}><th scope="row">R{revision.revision_number}<br /><span className="mono">{revision.id}</span></th><td><span className={`status ${revision.state === "ACTIVE" ? "success" : revision.state === "STALE" ? "warning" : "idle"}`}>{revision.state}</span></td><td>{revision.created_by}<br /><span className="muted">{formatDate(revision.created_at)}</span></td><td>{revision.note}</td><td><div className="row-actions">{revision.export?.status === "READY" ? unavailable.revisionDownload ? <Unavailable title="Exact version download" /> : <button className="button small" type="button" disabled={pending === `download:${revision.id}`} onClick={() => void downloadRevisionExport(revision)}>Download</button> : null}{canWrite && (revision.export?.status === "FAILED" || revision.export?.status === "NOT_REQUESTED") ? unavailable.revisionExport ? <Unavailable title="Exact version export" /> : <button className="button small" type="button" disabled={pending === `export:${revision.id}`} onClick={() => void queueRevisionExport(revision)}>Export</button> : null}{revision.export?.status === "QUEUED" || revision.export?.status === "EXPORTING" ? <span className="status warning">{revision.export.status}</span> : null}{canWrite && revision.state !== "ACTIVE" && build?.status === "READY" && !unavailable.rebase ? <button className="button small" type="button" disabled={pending === `rebase:${revision.id}`} onClick={() => void requestRebase(revision)}>Rebase</button> : null}</div></td></tr>)}</tbody></table></div>
        {rebase ? <div className={styles.rebase}><div><h4>Compatible</h4><p className="num">{rebase.compatible.length}</p></div><div><h4>Changed</h4><p className="num">{rebase.changed.length}</p></div><div><h4>Invalidated</h4><p className="num">{rebase.invalidated.length}</p></div><button className="button" type="button" disabled={!canWrite || Boolean(rebase.invalidated.length)} onClick={applyRebase}>Apply rebase to local forecast</button></div> : null}
      </details>
    </section> : null}
  </div>;
}
