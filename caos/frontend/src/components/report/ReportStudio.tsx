"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { LoadState, StateBlock, StateNote } from "../states";
import EvidencePicker from "../EvidencePicker";
import { canApproveCase, formatDate, humanizeCode, withQuery } from "../../lib/workbench";
import { api as request, assumptionRegistryPath, firstErrorMessage, networkFetch, type CaseRecord, type RunRecord } from "../../lib/api";
import DeliverableDocument, {
  type DeliverableBlock,
  type EvidenceCitation,
  type FrozenPayload,
  type NarrativeBlock,
  type TemplateBlock,
} from "./DeliverableDocument";
import { draftTextSections, overlayAnalystText, type DocumentSection } from "./documentTypes";
import { browserTabId, claimBrowserTabId, parseReportRecovery, reportRecoveryKey, type OpinionForm, type RecoveryModelSelection, type ReportRecovery } from "./reportRecovery";
import { canFileFrozen, freezeChecklist, freezeJobIsPending, reportEvidenceRefs } from "./reportStudioState";

const apiBase = process.env.NEXT_PUBLIC_API_URL || "";
const AUTOSAVE_DELAY_MS = 850;
const FREEZE_POLL_MS = 1000;
const SAVE_RETRY_DELAY_MS = 5000;
const pathwayOptions = [
  ["FULL_CREDIT", "Full Credit"],
  ["EARNINGS_UPDATE", "Earnings Update"],
  ["COVENANT_REFINANCING", "Covenant & Refinancing"],
  ["RELATIVE_VALUE", "Relative Value"],
  ["DISTRESSED_RESTRUCTURING", "Distressed & Restructuring"],
  ["DEEP_RESEARCH", "Deep Research"],
] as const;

type Pathway = typeof pathwayOptions[number][0];
type OptionalPolicy = { kind: DeliverableBlock["kind"]; slot_stem: string; max_items: number; order: number; model_dependent: boolean };
type DeliverableTemplate = { template_id: string; template_version: string; pathway: Pathway; title: string; model_requirement: "REQUIRED" | "OPTIONAL"; allowed_appendices: string[]; optional_blocks: OptionalPolicy[]; blocks: TemplateBlock[]; sections?: { section_id: string; title: string; required: boolean }[]; optional_sections?: { section_id: string; title: string; default_included: boolean; omission_reason: string }[] };
type ReportPreview = { document_sections: DocumentSection[]; mapping_version: string; included_optional_section_ids: string[]; publication_blockers: { code: string; section_id: string; detail: string }[]; citation_union: EvidenceCitation[] };
type ModelSelection = RecoveryModelSelection;
type ModelEligibility = {
  active_revision: { revision_id: string; build_id: string; revision_number: number; signed_by: string; signed_at: string } | null;
  application_build: { build_id: string; accepted_snapshot_id: string; input_fingerprint: string; payload_digest: string; status: "READY" } | null;
  fallback_acknowledgement_required: boolean;
  default_model_selection: ModelSelection | null;
};
type DraftRevision = { id: string; draft_id: string; case_id: string; pathway: Pathway; version: number; author: string; created_at: string; template_id: string; template_version: string; digest: string; content: { template_id: string; template_version: string; document_schema_version?: string | null; document_sections?: DocumentSection[] | null; model_selection: ModelSelection | null; model_identity?: Record<string, unknown> | null; blocks: DeliverableBlock[]; generated_blocks: Record<string, unknown>; included_optional_section_ids?: string[]; publication_blockers?: ReportPreview["publication_blockers"]; citation_union?: EvidenceCitation[] } };
type ExportMetadata = { format: "md" | "pdf" | "xlsx"; sha256: string; size: number };
type FrozenDeliverable = { id: string; case_id: string; pathway: Pathway; draft_version: number; status: "FROZEN" | "FILED" | "SUPERSEDED" | "CHANGES_REQUESTED"; frozen_by: string; frozen_at: string; approved_by: string | null; approved_at: string | null; superseded_by_id: string | null; change_request: { comment?: string; requested_by?: string; requested_at?: string } | null; digest: string; preview_digest: string; input_fingerprint: string; payload: FrozenPayload; exports: Partial<Record<"md" | "pdf" | "xlsx", ExportMetadata>>; opinion_id?: string | null; signed_by?: string | null };
// Task 10: the analyst opinion is an append-only, digest-bound record on the exact revision.
type OpinionRecord = { opinion_id: string; case_id: string; pathway: Pathway; draft_id: string; revision_id: string; draft_version: number; draft_digest: string; binding: Record<string, unknown>; opinion: string; limitations: string; material_overrides: string; rationale: string; supersedes_opinion_id: string | null; signed_by: string; signed_at: string; opinion_digest: string };
type OpinionState = { head: OpinionRecord | null; current: boolean; reasons: string[] };
// A freeze is a worker job; the frozen record appears in frozen_history once the job is PUBLISHED.
type FreezeJob = { job_id: string; case_id: string; pathway: Pathway; status: "QUEUED" | "RENDERING" | "PUBLISHED" | "FAILED"; draft_version: number; draft_digest: string; deliverable_id: string | null; error: { code: string } | null; requested_by: string; requested_at: string; completed_at: string | null };
type FilingReceipt = { schema_version: string; receipt_id: string; deliverable_id: string; case_id: string; pathway: Pathway; draft_version: number; draft_digest: string; preview_digest: string; input_fingerprint: string; approval_hash: string; content_digest: string | null; exports: Record<string, string>; opinion_id: string | null; signed_by: string | null; frozen_by: string; frozen_at: string; approved_by: string; approved_at: string; receipt_digest: string };
type WorkspaceResponse = { template: DeliverableTemplate; current: DraftRevision | null; history: DraftRevision[]; frozen_history: FrozenDeliverable[]; model_eligibility: ModelEligibility; opinion: OpinionState; pending_freezes: FreezeJob[]; preview?: ReportPreview | null; latest_template?: DeliverableTemplate };
type SaveState = { kind: "IDLE" | "INCOMPLETE" | "DIRTY" | "SAVING" | "SAVED" | "CONFLICT" | "ERROR"; detail?: string; version?: number };
type RegistryResponse = {
  version: string;
  digest: string;
  build_id: string;
  definitions: { assumption_id: string; label?: string }[];
  defaults: { assumption_id: string; case: "BASE" | "DOWNSIDE"; period_id: string; status: string }[];
};
type ScenarioResponse = { draft_generation: number; scenario: Record<string, unknown>; scenario_digest: string };
type LifecycleToken = { caseId: string; pathway: Pathway; scope: string; generation: number };

class ReportRequestError extends Error {
  constructor(readonly status: number, readonly detail: unknown) {
    super(typeof detail === "string" ? detail : `Request failed (${status})`);
  }
}

async function reportRequest<T>(path: string, options: RequestInit = {}, signal?: AbortSignal): Promise<T> {
  const response = await networkFetch(path, { ...options, signal, headers: { "Content-Type": "application/json", ...options.headers } });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new ReportRequestError(response.status, body?.detail ?? body);
  return body as T;
}

function aggregateCitations(blocks: DeliverableBlock[]): EvidenceCitation[] {
  const seen = new Set<string>();
  return blocks.flatMap((block) => "citations" in block ? block.citations : []).filter((citation) => {
    const key = `${citation.source_id}\u0000${citation.block_ids.join("\u0000")}\u0000${citation.claim}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function initializeBlocks(template: DeliverableTemplate): DeliverableBlock[] {
  return template.blocks.map((block) => block.kind === "EVIDENCE_REGISTER"
    ? { kind: "EVIDENCE_REGISTER", block_id: block.block_id, slot_id: block.slot_id, citations: [] }
    : { kind: "NARRATIVE", block_id: block.block_id, slot_id: block.slot_id, text: "", content_mode: "ANALYST_JUDGMENT", citations: [] }) as DeliverableBlock[];
}

const CONTRACT_KEYS: Record<DeliverableBlock["kind"], string[]> = {
  NARRATIVE: ["text", "content_mode", "citations"],
  EVIDENCE_REGISTER: ["citations"],
  LIMITATIONS: ["text", "citations"],
  GENERATED_METRIC: ["metric_ids"],
  GENERATED_TABLE: ["table_id", "field_ids"],
  GENERATED_CHART: ["recipe"],
  SCENARIO_EXHIBIT: ["title", "shocks", "scenario", "scenario_digest"],
  MODEL_APPENDIX: [],
};

function contractBlock(block: DeliverableBlock): DeliverableBlock {
  const record = block as unknown as Record<string, unknown>;
  return Object.fromEntries([
    ["kind", block.kind], ["block_id", block.block_id], ["slot_id", block.slot_id],
    ...CONTRACT_KEYS[block.kind].map((key) => [key, record[key]]),
  ]) as unknown as DeliverableBlock;
}

function blocksForSave(blocks: DeliverableBlock[]): DeliverableBlock[] {
  const citations = aggregateCitations(blocks.filter((block) => block.kind !== "EVIDENCE_REGISTER"));
  // Server-computed enrichments (generated values, model digests) never round-trip:
  // the strict wire contract rejects client-supplied copies of them.
  return blocks.map((block) => contractBlock(block.kind === "EVIDENCE_REGISTER" ? { ...block, citations } : block));
}

function draftIsValid(blocks: DeliverableBlock[], template: DeliverableTemplate): boolean {
  const required = new Map(template.blocks.map((block) => [block.block_id, block]));
  return blocks.every((block) => {
    if (block.kind === "NARRATIVE") return Boolean(block.text.trim()) && (block.content_mode === "ANALYST_JUDGMENT" || block.citations.length > 0);
    if (block.kind === "LIMITATIONS") return Boolean(block.text.trim());
    return true;
  }) && [...required].every(([id, definition]) => blocks.some((block) => block.block_id === id && block.kind === definition.kind));
}

function modelSelectionIsCurrent(selection: ModelSelection | null, eligibility: ModelEligibility): boolean {
  if (!selection) return true;
  if (selection.kind === "ANALYST_REVISION") return selection.revision_id === eligibility.active_revision?.revision_id && selection.build_id === eligibility.active_revision?.build_id;
  return eligibility.active_revision === null && selection.build_id === eligibility.application_build?.build_id;
}

function optionalBlock(policy: OptionalPolicy, index: number): DeliverableBlock {
  const identity = { block_id: `${policy.slot_stem}.${index.toString().padStart(2, "0")}`, slot_id: `${policy.slot_stem}.${index.toString().padStart(2, "0")}` };
  if (policy.kind === "NARRATIVE") return { ...identity, kind: "NARRATIVE", text: "", content_mode: "ANALYST_JUDGMENT", citations: [] };
  if (policy.kind === "GENERATED_METRIC") return { ...identity, kind: "GENERATED_METRIC", metric_ids: ["total_leverage", "accessible_liquidity"] };
  if (policy.kind === "GENERATED_TABLE") return { ...identity, kind: "GENERATED_TABLE", table_id: "annual_model", field_ids: ["revenue", "adjusted_ebitda_calc", "fcf", "total_leverage"] };
  if (policy.kind === "GENERATED_CHART") return { ...identity, kind: "GENERATED_CHART", recipe: { kind: "scenario_path", schema_version: "1.0", fields: ["total_leverage"], units: "x", metric_ids: ["total_leverage"], polarity: "higher_is_worse", accessible_table: true } };
  if (policy.kind === "MODEL_APPENDIX") return { ...identity, kind: "MODEL_APPENDIX" };
  return { ...identity, kind: "LIMITATIONS", text: "Limitations and unavailable authority.", citations: [] };
}

function saveLabel(state: SaveState): string {
  if (state.kind === "SAVING") return "Saving";
  if (state.kind === "SAVED") return `Saved v${state.version}`;
  if (state.kind === "CONFLICT") return "Conflict";
  if (state.kind === "INCOMPLETE") return "Complete required sections to autosave";
  if (state.kind === "ERROR") return state.detail || "Save failed";
  return state.kind === "DIRTY" ? "Unsaved changes" : "Ready";
}

function readBrowserRecovery(caseId: string, pathway: Pathway, subject: string) {
  try { return { raw: window.localStorage.getItem(reportRecoveryKey(caseId, pathway, subject, browserTabId())), failed: false }; }
  catch { return { raw: null, failed: true }; }
}

function storeBrowserRecovery(copy: ReportRecovery) {
  try { window.localStorage.setItem(reportRecoveryKey(copy.caseId, copy.pathway, copy.subject, browserTabId()), JSON.stringify(copy)); return true; }
  catch { return false; }
}

function clearBrowserRecovery(caseId: string, pathway: Pathway, subject: string) {
  try { window.localStorage.removeItem(reportRecoveryKey(caseId, pathway, subject, browserTabId())); return true; }
  catch { return false; }
}

const EMPTY_OPINION: OpinionForm = { opinion: "", limitations: "", material_overrides: "", rationale: "" };

type ReportProps = { caseId: string; role: string; subject?: string; selectedCase: CaseRecord | null; acceptedRunId?: string | null; authorityUnavailable?: boolean; onDraftStateChange: (dirty: boolean) => void; requestDraftDiscard: (detail: string, confirm: () => void, cancel?: () => void, trigger?: HTMLElement | null) => boolean };

export default function ReportStudio(props: ReportProps) {
  const [initialPathway, setInitialPathway] = useState<Pathway | null>(null);
  const [contextError, setContextError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (initialPathway || props.acceptedRunId === undefined) return;
    const controller = new AbortController();
    const resolve = async () => {
      setContextError("");
      if (props.acceptedRunId === null) { setInitialPathway("FULL_CREDIT"); return; }
      try {
        const run = await request<RunRecord>(`/api/runs/${encodeURIComponent(props.acceptedRunId!)}?include_events=false`, {}, controller.signal);
        if (controller.signal.aborted) return;
        if (run.case_id !== props.caseId || run.id !== props.acceptedRunId || !pathwayOptions.some(([id]) => id === run.plan.pathway)) throw new Error("Accepted report context does not match this case.");
        setInitialPathway(run.plan.pathway as Pathway);
      } catch (caught) { if (!controller.signal.aborted) setContextError(firstErrorMessage(caught, "Unable to resolve the accepted report pathway.")); }
    };
    void resolve();
    return () => controller.abort();
  }, [initialPathway, props.acceptedRunId, props.caseId, retry]);
  if (!initialPathway) return <div className="panel"><div className="panel-body"><LoadState loading={!contextError && !props.authorityUnavailable} error={contextError || (props.authorityUnavailable ? "Accepted case authority is unavailable. Reload the case to retry." : "")} onRetry={contextError && props.acceptedRunId !== undefined ? () => setRetry((value) => value + 1) : undefined} /></div></div>;
  // Once the editor exists, default changes never replace its explicit or dirty choice.
  return <ReportEditor {...props} initialPathway={initialPathway} />;
}

function ReportEditor({ caseId, role, subject = "", selectedCase, onDraftStateChange: notifyDraftStateChange, requestDraftDiscard, initialPathway }: ReportProps & { initialPathway: Pathway }) {
  const [pathway, setPathway] = useState<Pathway>(initialPathway);
  const [workspace, setWorkspace] = useState<WorkspaceResponse | null>(null);
  const [blocks, setBlocks] = useState<DeliverableBlock[]>([]);
  const [modelSelection, setModelSelection] = useState<ModelSelection | null>(null);
  const [includedOptionalSectionIds, setIncludedOptionalSectionIds] = useState<string[]>([]);
  const optionalSectionIdsRef = useRef<string[]>([]);
  const [showControls, setShowControls] = useState(false);
  const [selectedBlockId, setSelectedBlockId] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [saveState, setSaveState] = useState<SaveState>({ kind: "IDLE" });
  const [recovery, setRecovery] = useState<ReportRecovery | null>(null);
  const [recoveryError, setRecoveryError] = useState("");
  const [draftIsUnsaved, setDraftIsUnsaved] = useState(false);
  const [persistedVersion, setPersistedVersion] = useState(0);
  const [conflict, setConflict] = useState<DraftRevision | null>(null);
  const [selectedFrozen, setSelectedFrozen] = useState<FrozenDeliverable | null>(null);
  const [pending, setPending] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [changeComment, setChangeComment] = useState("");
  const [opinionForm, setOpinionForm] = useState<OpinionForm>(EMPTY_OPINION);
  const opinionFormRef = useRef<OpinionForm>(EMPTY_OPINION);
  const onDraftStateChange = useCallback((dirty: boolean) => {
    notifyDraftStateChange(dirty || Object.values(opinionFormRef.current).some(Boolean));
  }, [notifyDraftStateChange]);
  const [receipt, setReceipt] = useState<FilingReceipt | null>(null);
  const [registry, setRegistry] = useState<RegistryResponse | null>(null);
  const [scenarioForm, setScenarioForm] = useState({ assumptionId: "", case: "BASE", periodId: "", value: "" });
  const loadGeneration = useRef(0);
  const draftGeneration = useRef(0);
  const saveGeneration = useRef(0);
  const savedVersion = useRef(0);
  const unsavedDraft = useRef(false);
  const saveTimer = useRef<number | null>(null);
  const saveChain = useRef<Promise<void>>(Promise.resolve());
  const editorFocus = useRef<HTMLTextAreaElement | null>(null);
  const currentScope = useRef("");
  const freezePollTimer = useRef<number | null>(null);
  const lifecycleGeneration = useRef(0);
  const lifecycleInFlight = useRef(false);
  const canWrite = role !== "READER";
  const canApprove = canApproveCase(role, subject, selectedCase?.members);
  const pathwayLabel = pathwayOptions.find(([id]) => id === pathway)?.[1] || pathway;

  const lifecycleIsCurrent = useCallback((token: LifecycleToken) => (
    token.generation === lifecycleGeneration.current
    && token.scope === currentScope.current
  ), []);

  const beginLifecycle = useCallback((operation: string): LifecycleToken | null => {
    const scope = `${caseId}\u0000${pathway}`;
    if (lifecycleInFlight.current || currentScope.current !== scope) return null;
    const token = { caseId, pathway, scope, generation: ++lifecycleGeneration.current };
    lifecycleInFlight.current = true;
    setPending(operation);
    setError("");
    return token;
  }, [caseId, pathway]);

  const finishLifecycle = useCallback((token: LifecycleToken) => {
    if (!lifecycleIsCurrent(token)) return;
    lifecycleInFlight.current = false;
    setPending("");
  }, [lifecycleIsCurrent]);

  const invalidateLifecycle = useCallback((nextScope: string) => {
    lifecycleGeneration.current += 1;
    lifecycleInFlight.current = false;
    currentScope.current = nextScope;
    setPending("");
  }, []);

  const load = useCallback(async (signal?: AbortSignal) => {
    if (!caseId) return;
    const generation = ++loadGeneration.current;
    const scope = `${caseId}\u0000${pathway}`;
    currentScope.current = scope;
    setLoading(true); setLoadError(""); setError(""); setMessage(""); setSelectedFrozen(null); setReceipt(null); setConflict(null);
    try {
      await claimBrowserTabId().catch(() => undefined);
      const next = await reportRequest<WorkspaceResponse>(`/api/cases/${caseId}/deliverables/${pathway}/draft`, {}, signal);
      if (generation !== loadGeneration.current || currentScope.current !== scope) return;
      const nextBlocks = next.current?.content.blocks || initializeBlocks(next.template);
      savedVersion.current = next.current?.version || 0;
      unsavedDraft.current = false;
      setDraftIsUnsaved(false);
      opinionFormRef.current = EMPTY_OPINION;
      setOpinionForm(EMPTY_OPINION);
      setPersistedVersion(savedVersion.current);
      optionalSectionIdsRef.current = next.current?.content.included_optional_section_ids ?? next.preview?.included_optional_section_ids ?? [];
      setIncludedOptionalSectionIds(optionalSectionIdsRef.current);
      const nextModelSelection = next.current?.content.model_selection || next.model_eligibility.default_model_selection;
      setWorkspace(next); setBlocks(nextBlocks); setModelSelection(nextModelSelection); setSelectedBlockId(nextBlocks[0]?.block_id || ""); setSaveState(next.current ? { kind: "SAVED", version: next.current.version } : { kind: "IDLE" });
      const recoveryRead = readBrowserRecovery(caseId, pathway, subject);
      const storedRecovery = parseReportRecovery(recoveryRead.raw, caseId, pathway, subject);
      setRecovery(storedRecovery);
      setRecoveryError(recoveryRead.failed ? "Browser recovery is unavailable in this session." : recoveryRead.raw && !storedRecovery ? "A stored recovery copy was unreadable and was not restored." : "");
      const buildId = nextModelSelection?.build_id;
      if (buildId) {
        void request<RegistryResponse>(assumptionRegistryPath(caseId, buildId), {}, signal).then((value) => {
          if (generation !== loadGeneration.current || currentScope.current !== scope) return;
          if (value.build_id !== buildId) throw new Error("Scenario registry identity does not match the selected model build.");
          const scenarioDefault = value.defaults.find((row) => row.case === "BASE" && row.status === "READY") || value.defaults.find((row) => row.status === "READY");
          setRegistry(value);
          setScenarioForm({
            assumptionId: scenarioDefault?.assumption_id || value.definitions[0]?.assumption_id || "",
            case: scenarioDefault?.case || "BASE",
            periodId: scenarioDefault?.period_id || "",
            value: "",
          });
        }).catch((caught) => {
          if (generation !== loadGeneration.current || currentScope.current !== scope) return;
          setRegistry(null);
          setError(firstErrorMessage(caught, "Scenario registry unavailable"));
        });
      } else setRegistry(null);
      onDraftStateChange(false);
    } catch (caught) {
      if (generation !== loadGeneration.current || caught instanceof DOMException && caught.name === "AbortError") return;
      setLoadError(firstErrorMessage(caught, "Unable to load Report."));
    } finally { if (generation === loadGeneration.current) setLoading(false); }
    // `subject` is a load input: the recovery slot is keyed by it, and it resolves
    // from /api/me after the first render on a cold deep link.
  }, [caseId, onDraftStateChange, pathway, subject]);

  useEffect(() => () => notifyDraftStateChange(false), [notifyDraftStateChange]);

  useEffect(() => {
    loadGeneration.current += 1; draftGeneration.current = 0; saveGeneration.current = 0; savedVersion.current = 0; unsavedDraft.current = false; saveChain.current = Promise.resolve();
    lifecycleGeneration.current += 1; lifecycleInFlight.current = false; currentScope.current = `${caseId}\u0000${pathway}`;
    if (saveTimer.current !== null) window.clearTimeout(saveTimer.current);
    if (freezePollTimer.current !== null) window.clearTimeout(freezePollTimer.current);
    const controller = new AbortController();
    const timer = window.setTimeout(() => void load(controller.signal), 0);
    return () => { controller.abort(); window.clearTimeout(timer); loadGeneration.current += 1; lifecycleGeneration.current += 1; lifecycleInFlight.current = false; if (saveTimer.current !== null) window.clearTimeout(saveTimer.current); if (freezePollTimer.current !== null) window.clearTimeout(freezePollTimer.current); };
  }, [caseId, load, pathway]);

  const retainRecovery = useCallback((nextBlocks: DeliverableBlock[], selection: ModelSelection | null, opinion: OpinionForm, unsaved: boolean, optionalIds = optionalSectionIdsRef.current, template = workspace?.template) => {
    const dirty = unsaved || Object.values(opinion).some((value) => value.length > 0);
    onDraftStateChange(dirty);
    if (!dirty) {
      const cleared = clearBrowserRecovery(caseId, pathway, subject);
      setRecovery(null);
      setRecoveryError(cleared ? "" : "The saved work's browser recovery copy could not be cleared.");
    } else if (template) {
      const copy: ReportRecovery = { subject, caseId, pathway, savedAt: Date.now(), expectedVersion: savedVersion.current, templateId: template.template_id, templateVersion: template.template_version, modelSelection: selection, blocks: nextBlocks, opinionForm: opinion, includedOptionalSectionIds: optionalIds };
      if (storeBrowserRecovery(copy)) { setRecovery((current) => current ? copy : null); setRecoveryError(""); }
      else setRecoveryError("Browser recovery could not be updated. Keep this tab open until your work is saved and signed.");
    }
  }, [caseId, onDraftStateChange, pathway, subject, workspace]);

  const changeOpinion = (patch: Partial<OpinionForm>) => {
    const next = { ...opinionFormRef.current, ...patch };
    opinionFormRef.current = next;
    setOpinionForm(next);
    retainRecovery(blocks, modelSelection, next, unsavedDraft.current);
  };

  const enqueueSave = useCallback((snapshot: DeliverableBlock[], selection: ModelSelection | null, generation: number, scope: string, optionalIds = optionalSectionIdsRef.current) => {
    if (!workspace || !canWrite || scope !== currentScope.current) return;
    const prepared = workspace.template.sections ? snapshot.map(contractBlock) : blocksForSave(snapshot);
    if (!draftIsValid(prepared, workspace.template)) { setSaveState({ kind: "INCOMPLETE" }); return; }
    setSaveState({ kind: "SAVING" });
    saveChain.current = saveChain.current.then(async () => {
      if (scope !== currentScope.current || generation > saveGeneration.current) return;
      try {
        const next = await reportRequest<WorkspaceResponse>(`/api/cases/${caseId}/deliverables/${pathway}/draft`, { method: "PUT", body: JSON.stringify({ expected_version: savedVersion.current, template_id: workspace.template.template_id, template_version: workspace.template.template_version, model_selection: selection, blocks: prepared, ...(workspace.template.sections ? { included_optional_section_ids: optionalIds } : {}) }) });
        if (scope !== currentScope.current) return;
        savedVersion.current = next.current?.version || savedVersion.current;
        setPersistedVersion(savedVersion.current);
        setWorkspace(next); setConflict(null);
        if (generation === saveGeneration.current) { unsavedDraft.current = false; setDraftIsUnsaved(false); setBlocks(next.current?.content.blocks || prepared); setSaveState({ kind: "SAVED", version: savedVersion.current }); retainRecovery(next.current?.content.blocks || prepared, selection, opinionFormRef.current, false); }
      } catch (caught) {
        if (scope !== currentScope.current) return;
        if (caught instanceof ReportRequestError && caught.status === 409 && typeof caught.detail === "object" && caught.detail) {
          const detail = caught.detail as { code?: string; current?: DraftRevision | null };
          if (detail.code === "DELIVERABLE_VERSION_CONFLICT") { setRecovery(parseReportRecovery(readBrowserRecovery(caseId, pathway, subject).raw, caseId, pathway, subject)); setConflict(detail.current || null); setSaveState({ kind: "CONFLICT", detail: "A newer shared revision is available." }); return; }
        }
        setRecovery(parseReportRecovery(readBrowserRecovery(caseId, pathway, subject).raw, caseId, pathway, subject));
        setSaveState({ kind: "ERROR", detail: firstErrorMessage(caught, "Autosave failed") });
      }
    });
  }, [canWrite, caseId, pathway, retainRecovery, subject, workspace]);

  const markChanged = useCallback((nextBlocks: DeliverableBlock[], nextSelection = modelSelection, optionalIds = optionalSectionIdsRef.current) => {
    optionalSectionIdsRef.current = optionalIds;
    setIncludedOptionalSectionIds(optionalIds);
    setBlocks(nextBlocks); setModelSelection(nextSelection); setSelectedFrozen(null); setMessage(""); setError(""); setConflict(null);
    const generation = ++draftGeneration.current;
    saveGeneration.current = generation;
    unsavedDraft.current = true;
    setDraftIsUnsaved(true);
    setSaveState({ kind: "DIRTY" });
    retainRecovery(nextBlocks, nextSelection, opinionFormRef.current, true, optionalIds);
    if (saveTimer.current !== null) window.clearTimeout(saveTimer.current);
    const scope = currentScope.current;
    saveTimer.current = window.setTimeout(() => enqueueSave(nextBlocks, nextSelection, generation, scope, optionalIds), AUTOSAVE_DELAY_MS);
  }, [enqueueSave, modelSelection, retainRecovery]);

  useEffect(() => {
    if (saveState.kind !== "ERROR" || !draftIsUnsaved || !canWrite) return;
    const timer = window.setTimeout(() => enqueueSave(blocks, modelSelection, saveGeneration.current, currentScope.current), SAVE_RETRY_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [blocks, canWrite, draftIsUnsaved, enqueueSave, modelSelection, saveState.kind]);

  const applyRecovery = (retryNow: boolean) => {
    if (!workspace || !recovery || recovery.templateId !== workspace.template.template_id || recovery.templateVersion !== workspace.template.template_version) { setRecoveryError("This recovery copy belongs to a different template version and cannot be restored here."); return; }
    savedVersion.current = recovery.expectedVersion;
    opinionFormRef.current = recovery.opinionForm || EMPTY_OPINION;
    setOpinionForm(opinionFormRef.current);
    markChanged(recovery.blocks, recovery.modelSelection, recovery.includedOptionalSectionIds ?? []);
    setSelectedBlockId(recovery.blocks[0]?.block_id || "");
    if (retryNow) { if (saveTimer.current !== null) window.clearTimeout(saveTimer.current); enqueueSave(recovery.blocks, recovery.modelSelection, draftGeneration.current, currentScope.current); }
  };

  const discardRecovery = () => { if (clearBrowserRecovery(caseId, pathway, subject)) { setRecovery(null); setRecoveryError(""); } else setRecoveryError("The browser recovery copy could not be discarded in this session."); };
  const downloadRecovery = () => {
    if (!recovery) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(recovery, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = `caos-report-recovery-${pathway.toLowerCase()}.json`; link.click(); URL.revokeObjectURL(url);
  };

  const updateNarrative = (blockId: string, patch: Partial<NarrativeBlock>) => markChanged(blocks.map((block) => block.block_id === blockId && block.kind === "NARRATIVE" ? { ...block, ...patch } : block));
  const selectedBlock = blocks.find((block) => block.block_id === selectedBlockId) || null;
  const scenarioPeriods = [...new Set(registry?.defaults.filter((row) => row.status === "READY" && row.assumption_id === scenarioForm.assumptionId && row.case === scenarioForm.case).map((row) => row.period_id) || [])].sort();

  const cite = (sourceId: string, blockId: string) => {
    if (selectedBlock?.kind !== "NARRATIVE" && selectedBlock?.kind !== "LIMITATIONS") return;
    const citation = { source_id: sourceId, block_ids: [blockId], claim: selectedBlock.kind === "NARRATIVE" ? selectedBlock.text.slice(0, 1000) || "Evidence supporting this section." : "Evidence supporting this limitation." };
    markChanged(blocks.map((block) => block.block_id === selectedBlock.block_id && "citations" in block ? { ...block, citations: [...block.citations.filter((item) => !(item.source_id === sourceId && item.block_ids.includes(blockId))), citation] } : block));
  };

  const removeCitation = (sourceId: string, blockId: string) => {
    if (!selectedBlock || !("citations" in selectedBlock)) return;
    markChanged(blocks.map((block) => block.block_id === selectedBlock.block_id && "citations" in block ? { ...block, citations: block.citations.filter((item) => !(item.source_id === sourceId && item.block_ids.includes(blockId))) } : block));
  };

  // The server refuses optional blocks that are not in the template's declared
  // order (DELIVERABLE_TEMPLATE_ORDER_INVALID), so EVERY insertion re-sorts —
  // appending a scenario (order 4) after a limitations block (order 6) built a
  // draft that could never be saved. Required blocks all resolve to order 0 and
  // keep their template order under a stable sort.
  const inTemplateOrder = (list: DeliverableBlock[]) => [...list].sort((left, right) => {
    const orderOf = (block: DeliverableBlock) =>
      workspace?.template.optional_blocks.find((item) => item.kind === block.kind)?.order || 0;
    return orderOf(left) - orderOf(right);
  });

  const addOptional = (policy: OptionalPolicy) => {
    const count = blocks.filter((block) => block.kind === policy.kind).length + 1;
    if (count > policy.max_items || policy.kind === "SCENARIO_EXHIBIT") return;
    const added = optionalBlock(policy, count);
    markChanged(inTemplateOrder([...blocks, added]));
    setSelectedBlockId(added.block_id);
    setShowControls(true);
  };

  const removeOptional = (blockId: string) => {
    if (workspace?.template.blocks.some((block) => block.block_id === blockId)) return;
    const remaining = blocks.filter((block) => block.block_id !== blockId);
    const counts = new Map<string, number>();
    markChanged(remaining.map((block) => {
      const policy = workspace?.template.optional_blocks.find((item) => item.kind === block.kind);
      if (!policy) return block;
      const index = (counts.get(block.kind) || 0) + 1; counts.set(block.kind, index);
      return { ...block, block_id: `${policy.slot_stem}.${index.toString().padStart(2, "0")}`, slot_id: `${policy.slot_stem}.${index.toString().padStart(2, "0")}` } as DeliverableBlock;
    }));
  };

  const chooseModel = (kind: "ACTIVE" | "FALLBACK" | "NONE") => {
    if (!workspace) return;
    let selection: ModelSelection | null = null;
    if (kind === "ACTIVE" && workspace.model_eligibility.active_revision) selection = { kind: "ANALYST_REVISION", build_id: workspace.model_eligibility.active_revision.build_id, revision_id: workspace.model_eligibility.active_revision.revision_id };
    if (kind === "FALLBACK" && workspace.model_eligibility.application_build) selection = { kind: "APPLICATION_BUILD", build_id: workspace.model_eligibility.application_build.build_id, fallback_acknowledged: true };
    markChanged(blocks, selection);
  };

  const insertScenario = async () => {
    if (!workspace || !registry || !modelSelection || !scenarioForm.assumptionId || !scenarioForm.value) return;
    const numeric = Number(scenarioForm.value);
    if (!Number.isFinite(numeric)) { setError("Scenario value must be finite."); return; }
    const token = beginLifecycle("scenario");
    if (!token) return;
    const generation = ++draftGeneration.current;
    try {
      const shocks = [{ assumption_id: scenarioForm.assumptionId, case: scenarioForm.case, period_id: scenarioForm.periodId, value: numeric }];
      const next = await reportRequest<ScenarioResponse>(`/api/cases/${caseId}/models/scenarios`, { method: "POST", body: JSON.stringify({ build_id: modelSelection.build_id, base_revision_id: modelSelection.kind === "ANALYST_REVISION" ? modelSelection.revision_id : null, registry_version: registry.version, registry_digest: registry.digest, shocks, draft_generation: generation }) });
      if (!lifecycleIsCurrent(token) || generation !== draftGeneration.current || next.draft_generation !== generation) return;
      const policy = workspace.template.optional_blocks.find((item) => item.kind === "SCENARIO_EXHIBIT");
      if (!policy) return;
      const index = blocks.filter((block) => block.kind === "SCENARIO_EXHIBIT").length + 1;
      markChanged(inTemplateOrder([...blocks, { kind: "SCENARIO_EXHIBIT", block_id: `${policy.slot_stem}.${index.toString().padStart(2, "0")}`, slot_id: `${policy.slot_stem}.${index.toString().padStart(2, "0")}`, title: `Scenario · ${scenarioForm.assumptionId}`, shocks, scenario: next.scenario, scenario_digest: next.scenario_digest }]));
      setMessage("Server-calculated Scenario Exhibit inserted into the Draft.");
    } catch (caught) { if (lifecycleIsCurrent(token)) setError(firstErrorMessage(caught, "Scenario calculation failed")); }
    finally { finishLifecycle(token); }
  };

  const restoreRevision = async (revision: DraftRevision) => {
    if (!workspace || !canWrite || unsavedDraft.current || saveState.kind !== "SAVED") return;
    const token = beginLifecycle("restore");
    if (!token) return;
    try {
      const next = await reportRequest<WorkspaceResponse>(`/api/cases/${caseId}/deliverables/${pathway}/draft`, { method: "PUT", body: JSON.stringify({ expected_version: workspace.current?.version || 0, template_id: revision.template_id, template_version: revision.template_version, model_selection: revision.content.model_selection, blocks: revision.content.blocks.map(contractBlock), ...(revision.content.included_optional_section_ids !== undefined ? { included_optional_section_ids: revision.content.included_optional_section_ids } : {}) }) });
      if (!lifecycleIsCurrent(token)) return;
      savedVersion.current = next.current?.version || savedVersion.current; unsavedDraft.current = false; setDraftIsUnsaved(false); setPersistedVersion(savedVersion.current); setWorkspace(next); setBlocks(next.current?.content.blocks || revision.content.blocks); setModelSelection(next.current?.content.model_selection || null); setSelectedFrozen(null); setSaveState({ kind: "SAVED", version: savedVersion.current });
      optionalSectionIdsRef.current = next.current?.content.included_optional_section_ids ?? [];
      setIncludedOptionalSectionIds(optionalSectionIdsRef.current);
      retainRecovery(next.current?.content.blocks || revision.content.blocks, next.current?.content.model_selection || null, opinionFormRef.current, false, optionalSectionIdsRef.current, next.template);
      setMessage(`Restored v${revision.version} as new revision v${savedVersion.current}.`); editorFocus.current?.focus();
    } catch (caught) { if (lifecycleIsCurrent(token)) setError(firstErrorMessage(caught, "Unable to restore revision")); }
    finally { finishLifecycle(token); }
  };

  const upgradeTemplate = async () => {
    const latest = workspace?.latest_template;
    if (!workspace?.current || !latest || latest.template_id === workspace.template.template_id || !canWrite || unsavedDraft.current || Object.values(opinionFormRef.current).some(Boolean)) return;
    const token = beginLifecycle("upgrade");
    if (!token) return;
    const commentary = workspace.current.content.blocks.filter((block) => block.kind === "NARRATIVE").map((block, index) => ({ ...block, block_id: `appendix.commentary.${String(index + 1).padStart(2, "0")}`, slot_id: `appendix.commentary.${String(index + 1).padStart(2, "0")}` }));
    const other = workspace.current.content.blocks.filter((block) => block.kind !== "NARRATIVE" && block.kind !== "EVIDENCE_REGISTER");
    const evidence = initializeBlocks(latest).map((block) => block.kind === "EVIDENCE_REGISTER" ? { ...block, citations: aggregateCitations(workspace.current!.content.blocks) } : block);
    try {
      const next = await reportRequest<WorkspaceResponse>(`/api/cases/${caseId}/deliverables/${pathway}/draft`, { method: "PUT", body: JSON.stringify({ expected_version: savedVersion.current, template_id: latest.template_id, template_version: latest.template_version, model_selection: modelSelection, blocks: [...evidence, ...commentary, ...other].map(contractBlock), included_optional_section_ids: [] }) });
      if (!lifecycleIsCurrent(token)) return;
      setWorkspace(next); setBlocks(next.current!.content.blocks); setSelectedFrozen(null);
      savedVersion.current = next.current!.version; setPersistedVersion(savedVersion.current); setSaveState({ kind: "SAVED", version: savedVersion.current });
      optionalSectionIdsRef.current = []; setIncludedOptionalSectionIds([]);
      setMessage("Created a module-populated revision. Prior versions are retained; renewed opinion sign-off is required.");
    } catch (caught) { if (lifecycleIsCurrent(token)) setError(firstErrorMessage(caught, "Unable to create the new template revision")); }
    finally { finishLifecycle(token); }
  };

  const signOpinion = async () => {
    const current = workspace?.current;
    if (!current || !canWrite || unsavedDraft.current || saveState.kind !== "SAVED" || current.version !== savedVersion.current) return;
    if (!opinionForm.opinion.trim() || !opinionForm.limitations.trim() || !opinionForm.material_overrides.trim() || !opinionForm.rationale.trim()) return;
    const token = beginLifecycle("sign");
    if (!token) return;
    try {
      // Expected-head CAS: the sign-off names the opinion it believes is current.
      const signed = await reportRequest<OpinionRecord>(`/api/cases/${caseId}/deliverables/${pathway}/opinion`, { method: "POST", body: JSON.stringify({ draft_id: current.draft_id, draft_version: current.version, draft_digest: current.digest, expected_head_opinion_id: workspace.opinion?.head?.opinion_id ?? null, ...opinionForm }) });
      if (!lifecycleIsCurrent(token)) return;
      setWorkspace((value) => value ? { ...value, opinion: { head: signed, current: true, reasons: [] } } : value);
      setOpinionForm(EMPTY_OPINION);
      opinionFormRef.current = EMPTY_OPINION;
      retainRecovery(blocks, modelSelection, EMPTY_OPINION, unsavedDraft.current);
      setMessage(`Opinion signed on saved Draft v${current.version}.`);
    } catch (caught) { if (lifecycleIsCurrent(token)) setError(firstErrorMessage(caught, "Unable to sign the opinion")); }
    finally { finishLifecycle(token); }
  };

  const trackFreezeJob = useCallback((job: FreezeJob, token: LifecycleToken) => {
    // The worker owns the render: poll the job until it is PUBLISHED or FAILED,
    // then refetch the workspace so the frozen record comes from the server.
    const poll = async () => {
      if (!lifecycleIsCurrent(token)) return;
      try {
        const tracked = await reportRequest<FreezeJob>(`/api/cases/${caseId}/deliverables/freeze-jobs/${job.job_id}`);
        if (!lifecycleIsCurrent(token)) return;
        if (freezeJobIsPending(tracked.status)) {
          // Still rendering: keep the lifecycle held and ask again.
          setWorkspace((value) => value ? { ...value, pending_freezes: (value.pending_freezes ?? []).map((item) => item.job_id === tracked.job_id ? tracked : item) } : value);
          freezePollTimer.current = window.setTimeout(() => void poll(), FREEZE_POLL_MS);
          return;
        }
        const next = await reportRequest<WorkspaceResponse>(`/api/cases/${caseId}/deliverables/${pathway}/draft`);
        if (!lifecycleIsCurrent(token)) return;
        setWorkspace(next);
        if (tracked.status === "PUBLISHED") {
          const frozen = next.frozen_history.find((item) => item.id === tracked.deliverable_id) || null;
          setSelectedFrozen(frozen);
          setMessage(`Frozen exact Draft v${tracked.draft_version}: every export was published and verified by the worker.`);
        } else setError(`Freeze failed: ${tracked.error?.code || "DELIVERABLE_RENDER_FAILED"}. The draft is unchanged; retry after the cause is fixed.`);
      } catch (caught) { if (lifecycleIsCurrent(token)) setError(firstErrorMessage(caught, "Unable to track the freeze")); }
      if (lifecycleIsCurrent(token)) finishLifecycle(token);
    };
    freezePollTimer.current = window.setTimeout(() => void poll(), FREEZE_POLL_MS);
  }, [caseId, finishLifecycle, lifecycleIsCurrent, pathway]);

  const freeze = async () => {
    const current = workspace?.current;
    if (!current || unsavedDraft.current || Object.values(opinionFormRef.current).some(Boolean) || saveState.kind !== "SAVED" || current.version !== savedVersion.current || !modelSelectionIsCurrent(modelSelection, workspace.model_eligibility) || !workspace.opinion?.current) return;
    const token = beginLifecycle("freeze");
    if (!token) return;
    try {
      const job = await reportRequest<FreezeJob>(`/api/cases/${caseId}/deliverables/${pathway}/freeze`, { method: "POST", body: JSON.stringify({ draft_id: current.draft_id, draft_version: current.version, draft_digest: current.digest }) });
      if (!lifecycleIsCurrent(token)) return;
      setWorkspace((value) => value ? { ...value, pending_freezes: [...(value.pending_freezes ?? []).filter((item) => item.job_id !== job.job_id), job] } : value);
      setMessage(`Freeze of Draft v${current.version} queued: the worker is publishing every export.`);
      if (freezeJobIsPending(job.status)) { trackFreezeJob(job, token); return; }
      const next = await reportRequest<WorkspaceResponse>(`/api/cases/${caseId}/deliverables/${pathway}/draft`);
      if (!lifecycleIsCurrent(token)) return;
      setWorkspace(next); setSelectedFrozen(next.frozen_history.find((item) => item.id === job.deliverable_id) || null);
      finishLifecycle(token);
    } catch (caught) { if (lifecycleIsCurrent(token)) { setError(firstErrorMessage(caught, "Unable to freeze Deliverable")); finishLifecycle(token); } }
  };

  useEffect(() => {
    const controller = new AbortController();
    const loadReceipt = async () => {
      setReceipt(null);
      if (!selectedFrozen?.approved_by) return;
      try {
        const next = await reportRequest<FilingReceipt>(`/api/cases/${caseId}/deliverables/by-id/${selectedFrozen.id}/receipt`, {}, controller.signal);
        if (controller.signal.aborted) return;
        if (next.case_id !== caseId || next.deliverable_id !== selectedFrozen.id) throw new Error("Filing receipt identity does not match this frozen output.");
        setReceipt(next);
      } catch (caught) {
        // Older filed records have no detached receipt.
        if (!controller.signal.aborted && !(caught instanceof ReportRequestError && caught.status === 404)) setError(firstErrorMessage(caught, "Unable to load the filing receipt"));
      }
    };
    void loadReceipt();
    return () => controller.abort();
  }, [caseId, selectedFrozen]);

  const selectFrozen = (frozen: FrozenDeliverable | null) => {
    setReceipt(null);
    setSelectedFrozen(frozen);
  };

  const fileFrozen = async () => {
    if (!selectedFrozen || !canApprove) return;
    const token = beginLifecycle("file");
    if (!token) return;
    try {
      const filed = await reportRequest<FrozenDeliverable>(`/api/cases/${caseId}/deliverables/by-id/${selectedFrozen.id}/approve`, { method: "POST", body: JSON.stringify({ preview_digest: selectedFrozen.preview_digest, input_fingerprint: selectedFrozen.input_fingerprint }) });
      if (!lifecycleIsCurrent(token)) return;
      setSelectedFrozen(filed); setWorkspace((current) => current ? { ...current, frozen_history: current.frozen_history.map((item) => item.id === filed.id ? filed : item.status === "FILED" ? { ...item, status: "SUPERSEDED", superseded_by_id: filed.id } : item) } : current); setMessage("Exact Frozen Deliverable filed; the detached receipt records the approver.");
    } catch (caught) { if (lifecycleIsCurrent(token)) setError(firstErrorMessage(caught, "Unable to file Deliverable")); }
    finally { finishLifecycle(token); }
  };

  const requestChanges = async () => {
    if (!selectedFrozen || !canApprove || !changeComment.trim()) return;
    const token = beginLifecycle("changes");
    if (!token) return;
    try {
      const next = await reportRequest<{ frozen: FrozenDeliverable; draft: DraftRevision }>(`/api/cases/${caseId}/deliverables/by-id/${selectedFrozen.id}/request-changes`, { method: "POST", body: JSON.stringify({ preview_digest: selectedFrozen.preview_digest, input_fingerprint: selectedFrozen.input_fingerprint, comment: changeComment.trim() }) });
      if (!lifecycleIsCurrent(token)) return;
      const shared = await reportRequest<WorkspaceResponse>(`/api/cases/${caseId}/deliverables/${pathway}/draft`);
      if (!lifecycleIsCurrent(token) || !shared.current) return;
      adoptSharedDraft(shared);
      setChangeComment(""); setMessage(`Changes requested; editable Draft v${next.draft.version} created.`);
      window.setTimeout(() => { if (lifecycleIsCurrent(token)) editorFocus.current?.focus(); }, 0);
    } catch (caught) { if (lifecycleIsCurrent(token)) setError(firstErrorMessage(caught, "Unable to request changes")); }
    finally { finishLifecycle(token); }
  };

  const adoptSharedDraft = (next: WorkspaceResponse) => {
    const draft = next.current;
    if (!draft) return;
    optionalSectionIdsRef.current = draft.content.included_optional_section_ids ?? [];
    setIncludedOptionalSectionIds(optionalSectionIdsRef.current);
    setBlocks(draft.content.blocks); setModelSelection(draft.content.model_selection); setWorkspace(next);
    savedVersion.current = draft.version; unsavedDraft.current = false; setDraftIsUnsaved(false);
    setPersistedVersion(draft.version); setSelectedFrozen(null); setConflict(null); setSaveState({ kind: "SAVED", version: draft.version });
    retainRecovery(draft.content.blocks, draft.content.model_selection, opinionFormRef.current, false, optionalSectionIdsRef.current, next.template);
  };

  const acceptSharedDraft = async () => {
    const token = beginLifecycle("shared");
    if (!token) return;
    try {
      const next = await reportRequest<WorkspaceResponse>(`/api/cases/${caseId}/deliverables/${pathway}/draft`);
      if (lifecycleIsCurrent(token)) adoptSharedDraft(next);
    } catch (caught) { if (lifecycleIsCurrent(token)) setError(firstErrorMessage(caught, "Unable to load the shared revision")); }
    finally { finishLifecycle(token); }
  };

  const switchPathway = (next: Pathway, trigger?: HTMLElement | null) => {
    if (next === pathway) return;
    const change = () => {
      invalidateLifecycle(`${caseId}\u0000${next}`);
      onDraftStateChange(false); setPathway(next);
    };
    if (unsavedDraft.current || Object.values(opinionFormRef.current).some(Boolean) || ["DIRTY", "SAVING", "INCOMPLETE", "ERROR"].includes(saveState.kind)) {
      requestDraftDiscard("Discard the unsaved draft before changing pathway?", change, undefined, trigger);
    } else change();
  };

  if (loading || loadError || !workspace) return <div className="panel"><div className="panel-body"><LoadState loading={loading} error={loadError} title="Unable to load Report." onRetry={() => void load()} /></div></div>;

  const savedSections = workspace.current?.content.document_sections || workspace.preview?.document_sections || draftTextSections(blocks, workspace.template.blocks);
  const previewSections = selectedFrozen
    ? selectedFrozen.payload.content.document_sections || draftTextSections(selectedFrozen.payload.content.blocks, workspace.template.blocks)
    : overlayAnalystText(savedSections, blocks);
  const modelStale = !modelSelectionIsCurrent(modelSelection, workspace.model_eligibility);
  const requiredModelMissing = workspace.template.model_requirement === "REQUIRED" && modelSelection === null;
  const exactSavedRevision = Boolean(workspace.current) && !draftIsUnsaved && saveState.kind === "SAVED" && workspace.current?.version === persistedVersion;
  const opinionState: OpinionState = workspace.opinion ?? { head: null, current: false, reasons: ["OPINION_SIGNOFF_REQUIRED"] };
  const pendingJobs: FreezeJob[] = workspace.pending_freezes ?? [];
  const opinionCurrent = Boolean(opinionState.head) && opinionState.current && exactSavedRevision && !Object.values(opinionForm).some(Boolean);
  const [writeCheck, revisionCheck, selectionCheck, availabilityCheck, opinionCheck] = freezeChecklist({
    canWrite,
    exactSavedRevision,
    currentModelSelection: !modelStale,
    requiredModelAvailable: !requiredModelMissing,
    currentOpinion: opinionCurrent,
  });
  const reportBlockers = workspace.current?.content.publication_blockers ?? workspace.preview?.publication_blockers ?? [];
  const freezeReady = !reportBlockers.length && [writeCheck, revisionCheck, selectionCheck, availabilityCheck, opinionCheck].every((check) => check.ready);
  const opinionFormComplete = Object.values(opinionForm).every((value) => value.trim());
  const pendingFreeze = pendingJobs.find((job) => freezeJobIsPending(job.status)) || null;
  const failedFreeze = pendingJobs.find((job) => job.status === "FAILED") || null;
  const canFileSelected = selectedFrozen ? canFileFrozen(role, subject, { signed_by: selectedFrozen.signed_by, frozen_by: selectedFrozen.frozen_by }, selectedCase?.members) : false;
  const lifecycleBusy = pending !== "";
  const authoringLocked = lifecycleBusy;
  const selectedNarrative = selectedBlock?.kind === "NARRATIVE" ? selectedBlock : null;
  const controlsVisible = showControls || Boolean(recovery || recoveryError || conflict || error || pendingFreeze || failedFreeze || selectedFrozen) || ["ERROR", "INCOMPLETE"].includes(saveState.kind);

  return <div className={`report-studio report-studio-structured${workspace.template.sections ? " report-generated" : ""}${controlsVisible ? " report-controls-open" : ""}`}>
    <aside className="panel report-outline" aria-label="Deliverable composition">
      <div className="panel-header"><h2>Structure</h2><span className="panel-meta">{workspace.template.template_version}</span></div>
      <div className="panel-body report-rail-scroll">
        <div className="field"><label htmlFor="report-pathway">Pathway template</label><select id="report-pathway" value={pathway} onChange={(event) => switchPathway(event.target.value as Pathway, event.currentTarget)}>{pathwayOptions.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></div>
        {workspace.template.sections ? <>
          <nav className="report-section-nav" aria-label="Generated document sections">{[...new Set(previewSections.map((section) => section.page))].map((page) => <button key={page} type="button" onClick={() => Array.from(document.querySelectorAll<HTMLElement>("[data-document-page]")).find((element) => element.dataset.documentPage === page)?.scrollIntoView({ block: "start" })}>{page}</button>)}</nav>
          <p className="report-save-state" role="status">{saveLabel(saveState)}</p>
          <button type="button" className="button small" aria-expanded={controlsVisible} onClick={() => setShowControls((value) => !value)}>Commentary, model and publication</button>
          {!workspace.current ? <button type="button" className="button small" onClick={() => markChanged(blocks)} disabled={!canWrite || authoringLocked || requiredModelMissing}>Save module-populated draft</button> : null}
          {workspace.template.optional_sections?.map((section) => <label className="report-section-choice" key={section.section_id}><input type="checkbox" checked={includedOptionalSectionIds.includes(section.section_id)} disabled={!canWrite || authoringLocked} onChange={(event) => markChanged(blocks, modelSelection, event.target.checked ? [...includedOptionalSectionIds, section.section_id] : includedOptionalSectionIds.filter((id) => id !== section.section_id))} />Include {section.title}<small>{section.omission_reason}</small></label>)}
          {reportBlockers.length ? <details className="report-input-blockers"><summary>{reportBlockers.length} publication blocker{reportBlockers.length === 1 ? "" : "s"}</summary><ul>{reportBlockers.map((blocker) => <li key={`${blocker.section_id}:${blocker.code}`}><strong>{blocker.code}</strong> · {blocker.detail}</li>)}</ul></details> : null}
        </> : workspace.latest_template && workspace.latest_template.template_id !== workspace.template.template_id ? <button type="button" className="button small" onClick={() => void upgradeTemplate()} disabled={!canWrite || lifecycleBusy || draftIsUnsaved || saveState.kind !== "SAVED" || Object.values(opinionForm).some(Boolean)}>Create module-populated revision</button> : null}
        <nav className="report-section-nav" aria-label="Deliverable sections">{blocks.map((block, index) => <button key={block.block_id} type="button" className={selectedBlockId === block.block_id ? "is-active" : ""} aria-current={selectedBlockId === block.block_id ? "true" : undefined} onClick={() => { setSelectedBlockId(block.block_id); setShowControls(true); }}><span>{(index + 1).toString().padStart(2, "0")}</span>{workspace.template.blocks.find((item) => item.block_id === block.block_id)?.title || (block.kind === "SCENARIO_EXHIBIT" ? block.title : humanizeCode(block.kind))}<small>{workspace.template.blocks.some((item) => item.block_id === block.block_id) ? "Required" : "Optional"}</small></button>)}</nav>
        <details className="report-optional"><summary>Optional composition</summary><div className="report-optional-actions">{workspace.template.optional_blocks.map((policy) => <button className="button small" type="button" key={policy.kind} onClick={() => addOptional(policy)} disabled={!canWrite || authoringLocked || policy.kind === "SCENARIO_EXHIBIT" || policy.model_dependent && !modelSelection || blocks.filter((block) => block.kind === policy.kind).length >= policy.max_items}>Add {humanizeCode(policy.kind).toLowerCase()}</button>)}</div></details>
        <div className="report-history"><h3>Draft revisions</h3>{[...workspace.history].reverse().map((revision) => <div className="history-entry" key={revision.id}><strong>v{revision.version}</strong><span>{revision.author} · {formatDate(revision.created_at)}</span><button className="button small" type="button" onClick={() => void restoreRevision(revision)} disabled={!canWrite || lifecycleBusy || draftIsUnsaved || saveState.kind !== "SAVED"}>Restore as new revision</button></div>)}<h3>Frozen / Filed</h3>{[...workspace.frozen_history].reverse().map((item) => <button className="history-entry history-button" type="button" key={item.id} onClick={() => selectFrozen(item)} disabled={lifecycleBusy}><strong>{humanizeCode(item.status)} · Draft v{item.draft_version}</strong><span>{item.frozen_by} · {formatDate(item.frozen_at)}{item.signed_by ? ` · signed by ${item.signed_by}` : ""}</span></button>)}</div>
      </div>
    </aside>

    <section className="panel report-compose" aria-labelledby="report-compose-title">
      <div className="panel-header"><h2 id="report-compose-title">Compose</h2><span className={`status ${saveState.kind === "SAVED" ? "success" : saveState.kind === "CONFLICT" || saveState.kind === "ERROR" ? "critical" : "warning"}`} aria-live="polite">{saveLabel(saveState)}</span></div>
      <div className="panel-body report-editor-scroll">
        {selectedFrozen ? <div className="flow"><p className="status warning">Immutable {humanizeCode(selectedFrozen.status)} review · Draft v{selectedFrozen.draft_version}</p><dl className="state-facts"><dt>Opinion signed by</dt><dd>{selectedFrozen.signed_by || "Unavailable"}</dd><dt>Frozen by</dt><dd>{selectedFrozen.frozen_by}</dd><dt>Approval state</dt><dd>{selectedFrozen.approved_by ? `Filed by ${selectedFrozen.approved_by} · ${formatDate(selectedFrozen.approved_at || "")}` : "Pending approval · the frozen bytes never name an approver"}</dd>{receipt ? <><dt>Filing receipt</dt><dd className="mono" data-filing-receipt>{receipt.receipt_id} · {receipt.receipt_digest}</dd></> : null}</dl><button className="button small" type="button" onClick={() => selectFrozen(null)} disabled={lifecycleBusy}>Return to shared Draft</button>{selectedFrozen.status === "FROZEN" && canApprove && !canFileSelected ? <p className="status idle" data-separation-of-duties>Separation of duties · the opinion signer and the freeze actor cannot file this output</p> : null}{selectedFrozen.status === "FROZEN" && canFileSelected ? <div className="approval-panel"><button className="button primary" type="button" onClick={() => void fileFrozen()} disabled={lifecycleBusy}>{pending === "file" ? "Filing…" : "File exact Frozen version"}</button><div className="field"><label htmlFor="change-request-comment">Required comment to request changes</label><textarea id="change-request-comment" value={changeComment} maxLength={2000} onChange={(event) => setChangeComment(event.target.value)} disabled={lifecycleBusy} /></div><button className="button" type="button" onClick={() => void requestChanges()} disabled={!changeComment.trim() || lifecycleBusy}>{pending === "changes" ? "Creating new Draft…" : "Request changes"}</button></div> : null}{["FILED", "SUPERSEDED"].includes(selectedFrozen.status) ? <div className="proof-actions">{(["md", "pdf", "xlsx"] as const).map((format) => <a className="button small" key={format} download href={`${apiBase}/api/cases/${caseId}/deliverables/by-id/${selectedFrozen.id}/export/${format}`}>{format.toUpperCase()}</a>)}</div> : <p className="muted">Downloads unlock after filing.</p>}</div> : <>
          {recovery ? <section className="report-recovery" aria-labelledby="report-recovery-title"><div><span className="flag">RECOVERY COPY</span><h3 id="report-recovery-title">Unsaved browser copy from {formatDate(new Date(recovery.savedAt).toISOString())}</h3><p>Not shared authority · based on server v{recovery.expectedVersion}. Restore explicitly or retry the server save.</p></div><div className="row-actions"><button className="button small" type="button" onClick={() => applyRecovery(false)} disabled={!canWrite || authoringLocked}>Restore copy</button><button className="button small primary" type="button" onClick={() => applyRecovery(true)} disabled={!canWrite || authoringLocked}>Retry save now</button><button className="button small" type="button" onClick={downloadRecovery}>Download JSON</button><button className="button small" type="button" onClick={discardRecovery} disabled={authoringLocked}>Discard copy</button></div></section> : null}
          {recoveryError ? <StateNote tone="warning" live="status">{recoveryError}</StateNote> : null}
          {selectedNarrative ? <div className="flow"><div className="field"><label htmlFor={`narrative-${selectedNarrative.block_id}`}>{workspace.template.blocks.find((item) => item.block_id === selectedNarrative.block_id)?.title || "Analyst commentary"}</label><textarea ref={editorFocus} id={`narrative-${selectedNarrative.block_id}`} value={selectedNarrative.text} maxLength={20000} rows={8} onChange={(event) => updateNarrative(selectedNarrative.block_id, { text: event.target.value })} disabled={!canWrite || authoringLocked} /><span className="field-meta">{selectedNarrative.text.length.toLocaleString()} / 20,000</span></div><fieldset><legend>Claim authority</legend><label><input type="radio" name={`mode-${selectedNarrative.block_id}`} checked={selectedNarrative.content_mode === "EVIDENCE"} onChange={() => updateNarrative(selectedNarrative.block_id, { content_mode: "EVIDENCE" })} disabled={!canWrite || authoringLocked} />Evidence-bound</label><label><input type="radio" name={`mode-${selectedNarrative.block_id}`} checked={selectedNarrative.content_mode === "ANALYST_JUDGMENT"} onChange={() => updateNarrative(selectedNarrative.block_id, { content_mode: "ANALYST_JUDGMENT" })} disabled={!canWrite || authoringLocked} />Analyst judgment</label></fieldset>{selectedNarrative.content_mode === "EVIDENCE" && !selectedNarrative.citations.length ? <StateNote tone="critical" live="alert">Evidence-bound narrative requires at least one citation.</StateNote> : null}{!workspace.template.blocks.some((item) => item.block_id === selectedNarrative.block_id) ? <button type="button" className="button small" onClick={() => removeOptional(selectedNarrative.block_id)} disabled={!canWrite || authoringLocked}>Omit commentary</button> : null}</div> : selectedBlock?.kind === "LIMITATIONS" ? <div className="field"><label htmlFor="report-limitations-overlay">Analyst limitations</label><textarea id="report-limitations-overlay" value={selectedBlock.text} maxLength={10000} disabled={!canWrite || authoringLocked} onChange={(event) => markChanged(blocks.map((block) => block.block_id === selectedBlock.block_id ? { ...selectedBlock, text: event.target.value } : block))} /><button type="button" className="button small" onClick={() => removeOptional(selectedBlock.block_id)} disabled={!canWrite || authoringLocked}>Omit limitations</button></div> : selectedBlock ? <div className="generated-block-card"><span className="meta-label">{humanizeCode(selectedBlock.kind)}</span><h3>Read-only structured block</h3><p>Calculated values and Scenario outputs are accepted only from the server response.</p>{!workspace.template.blocks.some((item) => item.block_id === selectedBlock.block_id) ? <button className="button small" type="button" onClick={() => removeOptional(selectedBlock.block_id)} disabled={!canWrite || authoringLocked}>Omit block</button> : null}</div> : null}
          <div className="report-authority-strip"><div><span className="meta-label">Model authority</span><strong>{modelSelection?.kind === "ANALYST_REVISION" ? `Active Revision ${workspace.model_eligibility.active_revision?.revision_number || ""}` : modelSelection?.kind === "APPLICATION_BUILD" ? "Application Model Build · acknowledged fallback" : "No model selected"}</strong></div>{modelStale ? <span className="status critical">Stale model identity</span> : null}</div>
          <fieldset className="report-model-picker"><legend>Deliverable model</legend>{workspace.model_eligibility.active_revision ? <label><input type="radio" name="report-model" checked={modelSelection?.kind === "ANALYST_REVISION"} onChange={() => chooseModel("ACTIVE")} disabled={!canWrite || authoringLocked} />Active Analyst Model <code>{workspace.model_eligibility.active_revision.revision_id}</code></label> : null}{!workspace.model_eligibility.active_revision && workspace.model_eligibility.application_build ? <label><input type="checkbox" checked={modelSelection?.kind === "APPLICATION_BUILD"} onChange={(event) => chooseModel(event.target.checked ? "FALLBACK" : "NONE")} disabled={!canWrite || authoringLocked} />I acknowledge fallback to the Application Model Build <code>{workspace.model_eligibility.application_build.build_id}</code></label> : null}{workspace.template.model_requirement === "OPTIONAL" ? <button className="button small" type="button" onClick={() => chooseModel("NONE")} disabled={!canWrite || authoringLocked || modelSelection === null}>Omit model</button> : null}</fieldset>
          <EvidencePicker key={caseId} caseId={caseId} canCite={canWrite && !authoringLocked && Boolean(selectedBlock && "citations" in selectedBlock)} isCited={(sourceId, blockId) => Boolean(selectedBlock && "citations" in selectedBlock && selectedBlock.citations.some((citation) => citation.source_id === sourceId && citation.block_ids.includes(blockId)))} onCite={cite} onRemove={removeCitation} />
          {modelSelection && registry ? <details className="scenario-insert"><summary>Scenario insertion <span>Temporary server calculation</span></summary><div className="scenario-fields"><div className="field"><label htmlFor="scenario-assumption">Assumption</label><select id="scenario-assumption" value={scenarioForm.assumptionId} onChange={(event) => { const assumptionId = event.target.value; const available = registry.defaults.find((row) => row.assumption_id === assumptionId && row.case === scenarioForm.case && row.status === "READY") || registry.defaults.find((row) => row.assumption_id === assumptionId && row.status === "READY"); setScenarioForm((current) => ({ ...current, assumptionId, case: available?.case || current.case, periodId: available?.period_id || "" })); }} disabled={authoringLocked}>{registry.definitions.map((definition) => <option key={definition.assumption_id} value={definition.assumption_id}>{definition.label || definition.assumption_id}</option>)}</select></div><div className="field"><label htmlFor="scenario-case">Case</label><select id="scenario-case" value={scenarioForm.case} onChange={(event) => { const caseName = event.target.value as "BASE" | "DOWNSIDE"; const available = registry.defaults.find((row) => row.assumption_id === scenarioForm.assumptionId && row.case === caseName && row.status === "READY"); setScenarioForm((current) => ({ ...current, case: caseName, periodId: available?.period_id || "" })); }} disabled={authoringLocked}><option value="BASE">Base</option><option value="DOWNSIDE">Downside</option></select></div><div className="field"><label htmlFor="scenario-period">Period</label><select id="scenario-period" value={scenarioForm.periodId} onChange={(event) => setScenarioForm((current) => ({ ...current, periodId: event.target.value }))} disabled={authoringLocked}>{scenarioPeriods.map((periodId) => <option key={periodId} value={periodId}>{periodId}</option>)}</select></div><div className="field"><label htmlFor="scenario-value">Shock value</label><input id="scenario-value" inputMode="decimal" value={scenarioForm.value} onChange={(event) => setScenarioForm((current) => ({ ...current, value: event.target.value }))} disabled={authoringLocked} /></div></div><button className="button small" type="button" onClick={() => void insertScenario()} disabled={!canWrite || authoringLocked || !scenarioForm.periodId || !scenarioForm.value}>{pending === "scenario" ? "Calculating…" : "Calculate and insert exact exhibit"}</button></details> : null}
          {conflict ? <StateBlock shape="action" tone="warning" live="alert" title="Shared Draft conflict" body={<>{conflict.author} saved v{conflict.version} at {formatDate(conflict.created_at)}. Your local content remains unchanged.{conflict.template_id !== workspace.template.template_id ? " The shared template changed. Use the shared revision before editing; your recovery copy remains available." : ""}</>}><button className="button small" type="button" onClick={() => { savedVersion.current = conflict.version; setPersistedVersion(conflict.version); setWorkspace((current) => current ? { ...current, current: conflict, history: [...current.history.filter((item) => item.id !== conflict.id), conflict] } : current); setSaveState({ kind: "DIRTY" }); markChanged(blocks); }} disabled={authoringLocked || conflict.template_id !== workspace.template.template_id}>Retry over current v{conflict.version}</button><button className="button small" type="button" onClick={() => void acceptSharedDraft()} disabled={authoringLocked}>Use shared v{conflict.version}</button></StateBlock> : null}
          <section className="approval-panel" data-freeze-approval aria-labelledby="freeze-approval-title">
            <div><span className="meta-label">What will bind</span><h3 id="freeze-approval-title">Exact saved Draft revision as an immutable Deliverable</h3></div>
            <dl className="state-facts">
              <dt>Draft authority</dt><dd><span className="mono">{workspace.current ? `v${workspace.current.version}` : "Unavailable"}</span>{workspace.current?.digest ? <div className="mono muted">{workspace.current.digest}</div> : null}</dd>
              <dt>Write access</dt><dd><span className={`status ${writeCheck.ready ? "success" : "warning"}`}>{writeCheck.ready ? "Ready" : "Blocked"}</span></dd>
              <dt>Exact saved revision</dt><dd><span className={`status ${revisionCheck.ready ? "success" : "warning"}`}>{revisionCheck.ready ? "Ready" : "Blocked"}</span>{!revisionCheck.ready ? <div className="muted">Wait for the shared Draft to finish saving at this exact version.</div> : null}</dd>
              <dt>Current model selection</dt><dd><span className={`status ${selectionCheck.ready ? "success" : "warning"}`}>{selectionCheck.ready ? "Ready" : "Blocked"}</span>{!selectionCheck.ready ? <div><Link href={withQuery("/model", { case: caseId })}>Open Model</Link> to resolve the stale model authority.</div> : null}</dd>
              <dt>Required model availability</dt><dd><span className={`status ${availabilityCheck.ready ? "success" : "warning"}`}>{availabilityCheck.ready ? "Ready" : "Blocked"}</span>{!availabilityCheck.ready ? <div>{workspace.model_eligibility.active_revision || workspace.model_eligibility.application_build ? <Link href={withQuery("/model", { case: caseId })}>Open Model</Link> : <Link href={withQuery("/run", { case: caseId })}>Open Run</Link>} to establish the required model prerequisite.</div> : null}</dd>
              <dt>Current opinion sign-off</dt><dd><span className={`status ${opinionCheck.ready ? "success" : "warning"}`}>{opinionCheck.ready ? "Ready" : "Blocked"}</span>{opinionState.head ? <div className="opinion-record" data-opinion-head><p><strong>{opinionState.head.signed_by}</strong> · {formatDate(opinionState.head.signed_at)} · Draft v{opinionState.head.draft_version}</p><p>{opinionState.head.opinion}</p>{!opinionState.current ? <p className="muted">Stale: {opinionState.reasons.map(humanizeCode).join(", ")}. Sign again on the current revision.</p> : null}</div> : <div className="muted">No signed opinion yet. The analyst signs the opinion, limitations, material overrides and rationale on the exact saved revision.</div>}</dd>
            </dl>
            {canWrite ? <form className="opinion-form" data-opinion-form onSubmit={(event) => { event.preventDefault(); void signOpinion(); }}>
              <div className="field"><label htmlFor="opinion-text">Opinion</label><textarea id="opinion-text" value={opinionForm.opinion} maxLength={4000} onChange={(event) => changeOpinion({ opinion: event.target.value })} disabled={authoringLocked} /></div>
              <div className="field"><label htmlFor="opinion-limitations">Limitations</label><textarea id="opinion-limitations" value={opinionForm.limitations} maxLength={4000} onChange={(event) => changeOpinion({ limitations: event.target.value })} disabled={authoringLocked} /></div>
              <div className="field"><label htmlFor="opinion-overrides">Material overrides (write “None” explicitly)</label><textarea id="opinion-overrides" value={opinionForm.material_overrides} maxLength={4000} onChange={(event) => changeOpinion({ material_overrides: event.target.value })} disabled={authoringLocked} /></div>
              <div className="field"><label htmlFor="opinion-rationale">Rationale</label><textarea id="opinion-rationale" value={opinionForm.rationale} maxLength={8000} onChange={(event) => changeOpinion({ rationale: event.target.value })} disabled={authoringLocked} /></div>
              <div className="report-actions"><button className="button" type="submit" disabled={!exactSavedRevision || !opinionFormComplete || lifecycleBusy}>{pending === "sign" ? "Signing…" : `Sign opinion on saved v${workspace.current?.version || "—"}`}</button><span>The sign-off binds this exact revision, snapshot, source set and model identity; editing any of them requires signing again.</span></div>
            </form> : null}
            {pendingFreeze ? <p className="status warning freeze-job" role="status" aria-live="polite" data-freeze-job>Freeze of Draft v{pendingFreeze.draft_version} is {humanizeCode(pendingFreeze.status).toLowerCase()} · the worker publishes and verifies every export before the frozen record exists.</p> : null}
            {failedFreeze && !pendingFreeze ? <StateNote tone="critical" live="status">Freeze of Draft v{failedFreeze.draft_version} failed: {failedFreeze.error?.code || "DELIVERABLE_RENDER_FAILED"}. Freeze again to requeue.</StateNote> : null}
            <div className="report-actions report-freeze-actions">{canWrite ? <button className="button primary" data-primary-report-action type="button" onClick={() => void freeze()} disabled={!freezeReady || lifecycleBusy || Boolean(pendingFreeze)}>{pending === "freeze" ? "Freezing…" : `Freeze saved v${workspace.current?.version || "—"}`}</button> : <span className="status idle">Reader mode · Freeze is an analyst action</span>}<span>Freeze revalidates the saved revision, the signed opinion and current authority on the server; the worker publishes every export before the frozen record exists.</span></div>
          </section>
        </>}
        {message ? <p className="status success" role="status" aria-live="polite">{message}</p> : null}{error ? <StateNote tone="critical" live="alert">{error}</StateNote> : null}
      </div>
    </section>

    <section className="report-proof-stage" aria-label="Deliverable paper preview" tabIndex={0}><DeliverableDocument title={selectedFrozen?.payload.template.title || workspace.template.title} issuer={selectedCase ? `${selectedCase.issuer} — ${selectedCase.name}` : workspace.template.title} pathwayLabel={pathwayLabel} status={selectedFrozen?.status || (draftIsUnsaved ? "UNSAVED" : "DRAFT")} version={selectedFrozen?.draft_version || workspace.current?.version} digest={selectedFrozen?.digest || (draftIsUnsaved ? undefined : workspace.current?.digest)} sections={previewSections} caseId={caseId} evidenceRefs={reportEvidenceRefs(selectedFrozen ? selectedFrozen.payload.evidence : workspace.current?.content.citation_union ?? workspace.preview?.citation_union ?? [])} onAddCommentary={!selectedFrozen && workspace.template.sections && canWrite && !authoringLocked ? () => { const policy = workspace.template.optional_blocks.find((item) => item.kind === "NARRATIVE"); if (policy) addOptional(policy); } : undefined} publication={selectedFrozen?.payload.publication ?? null} /></section>
  </div>;
}
