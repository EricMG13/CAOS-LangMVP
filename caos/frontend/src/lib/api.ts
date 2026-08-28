export type { CaseRecord, Snapshot, Snapshot as SnapshotRecord, SnapshotView } from "./workbench";

export type ResearchWorkstream = { id: string; kind: string; question: string; assigned_questions?: string[]; perspective: string; hypothesis: string; evidence_needs: string[]; source_classes: string[]; disconfirming_test: string; completion_test: string; effort_cap: string };
export type ResearchPlan = { methodology_build_id: string; brief_digest: string; source_set: { id: string; version: number }; upstream_artifacts: { module_id: string; artifact_id: string; digest: string }[]; scope: { type?: string | null; key?: string | null; source_mode?: string | null }; workstreams: ResearchWorkstream[] };
// `accepted_snapshot_id` is already on the wire (RunResponse in caos/server/caos/responses.py,
// projected by `_wire_run` and pinned in caos/tests/spec/test_http_contracts_spec.py) — this
// declaration only surfaces it to the client.
export type RunRecord = { id: string; case_id: string; status: string; plan: { pathway: string; depth: string; profile_id: string; selection_id: string }; nodes: { id: string; module_id: string; status: string; artifact_id?: string | null }[]; accepted_snapshot_id?: string | null; error?: { code?: string; message?: string } | null; research?: { phase?: string; proposed_plan_hash?: string | null; approved_plan_hash?: string | null; proposed_plan?: ResearchPlan | null } | null };
export type SourceRecord = { id: string; filename: string; sha256: string; blocks: { block_id: string; locator: Record<string, unknown>; text?: string }[] };
// Envelope: GET /api/cases/{case_id}/artifacts/{artifact_id} (ArtifactResponse in
// caos/server/caos/responses.py). `markdown` is null for deterministic payloads
// (caos.system_analysis.v1) and holds the canonical six-section document for agent
// payloads (caos.canonical.artifact.v1), whose evidence_refs are objects.
export type ArtifactRecord = {
  id: string;
  case_id?: string;
  run_id?: string;
  module_id: string;
  digest: string;
  input_fingerprint?: string;
  created_by?: string;
  created_at?: string;
  markdown?: string | null;
  payload?: {
    schema_version?: string;
    status?: string;
    summary?: string;
    evidence_refs?: string[] | { source_id: string; block_id?: string | null }[];
    lineage?: { input_fingerprint?: string; upstream_digests?: string[] };
    narrative?: { takeaway?: string; basis?: string; exceptions?: string };
    authority?: string;
    confidence?: { band?: string; qa_status?: string };
    provenance?: { executor?: string; profile_id?: string | null; selection_id?: string | null };
    canonical_output?: { markdown?: string; markdown_sha256?: string };
    inputs?: { loan_universe?: { identity?: Record<string, unknown>; rows?: Record<string, unknown>[] } };
  } | null;
};
export type LoanLocator = { sheet: string; row: number };
export type LoanRow = { instrument_key: string; company: string | null; borrower_name: string | null; business_description: string | null; sector: string; sub_sector: string | null; sub_group: string | null; public_private: string | null; bloomberg_loan_id: string | null; figi: string | null; loan_type: string | null; ranking: string | null; ratings: string | null; size_mn: number | null; margin_bps: number | null; maturity_date: string | null; bid_points: number | null; ask_points: number | null; change_1d_points: number | null; change_1w_points: number | null; change_1m_points: number | null; change_3m_points: number | null; change_6m_points: number | null; change_1yr_points: number | null; change_ytd_points: number | null; mid_ytm_pct: number | null; mid_3y_dm_bps: number | null; source_locators: LoanLocator[] };
export type LoanUniverse = { id: string; source_id: string; source_filename: string; source_sha256: string; workbook_date: string | null; template_version: string; importer_version: string; universe_digest: string; row_count: number; version: number; status: string; activated_at: string };
export type LoanUniverseResponse = { status: "ACTIVE" | "NO_ACTIVE_UNIVERSE"; universe: LoanUniverse | null; rows: LoanRow[] };
export type LoanFinding = { code: string; detail: string; sheet?: string | null; row?: number | null; column?: string | null };
export type ReportDraft = { thesis?: string; instrument?: string; recommendation?: string; evidenceIds?: string };
export type EvidenceOption = { id: string; kind: "Snapshot" | "Artifact" | "Source"; label: string };
export type ModelBuild = { id: string; case_id: string; accepted_run_id: string; accepted_snapshot_id: string; source_set_id: string; input_fingerprint: string; status: "QUEUED" | "BUILDING" | "READY" | "FAILED"; queued_at: string; started_at?: string | null; completed_at?: string | null; error?: { code: string; detail: string } | null; export: { status: "NOT_REQUESTED" | "QUEUED" | "EXPORTING" | "READY" | "FAILED"; error?: { code: string; detail: string } | null; filename?: string; sha256?: string; size?: number }; qa?: { status: string; semantic_check_count: number; formula_count: number; worksheet_cell_count: number; validation_warnings?: string[]; limitation_flags?: string[] }; payload_digest?: string };
export type ModelReadiness = { status: "NOT_READY" | "READY_TO_BUILD" | ModelBuild["status"]; module_id: "CP-MODEL"; accepted_snapshot: { id: string; run_id: string; digest?: string } | null; source_set: { id: string; version: number; digest: string } | null; requirements: { module_id: string; status: string; digest?: string }[]; blockers: { code: string; detail: string }[]; build: ModelBuild | null };
export type ModelInventory = { readiness: ModelReadiness; builds: ModelBuild[] };
export type WorksheetCell = { address: string; row: number; column: number; value: string | number | boolean | null; value_type: "formula" | "boolean" | "number" | "date" | "text"; formula: string | null; semantic_id: string | null; owner: string | null; write_class: string | null; period_id: string | null; source_refs: string | null; number_format: string; style: { bold: boolean; italic: boolean; fill: string | null; align: string | null; wrap: boolean } };
export type WorksheetTab = { id: string; name: string; max_row: number; max_column: number; freeze_panes: string; merged_cells: string[]; columns: { column: number; letter: string; width?: number; hidden: boolean }[]; cells: WorksheetCell[] };
export type WorksheetResponse = { build_id: string; input_fingerprint: string; payload_digest: string; qa: ModelBuild["qa"]; payload: { schema_version: string; identity: { issuer_id: string; issuer_name: string; analysis_date: string }; tabs: WorksheetTab[] } };

export function assumptionRegistryPath(caseId: string, buildId: string) {
  return `/api/cases/${caseId}/models/assumption-registry?build_id=${encodeURIComponent(buildId)}`;
}

// Failures from the shared request helper carry the HTTP status so a surface can
// distinguish a route this deployment does not serve (observed 404) from a failure
// worth retrying. The message stays the served `detail` string when there is one.
export class ApiRequestError extends Error {
  // Explicit field declarations: node --test runs this file with type-stripping
  // only, which does not support constructor parameter properties.
  readonly status: number;
  readonly detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" && detail ? detail : `Request failed (${status})`);
    this.status = status;
    this.detail = detail;
  }
}

// Observed-404 capability gate — no hardcoded capability map. A capability call that
// returns HTTP 404 means the route is absent on this deployment: the control renders
// its "Not available in this deployment." block instead of a retryable error, and the
// gate stays truthful automatically as routes land. Works for any request-helper
// error that carries a numeric `status` (ApiRequestError, ModelRequestError,
// ReportRequestError).
//
// Also treats 405 as route-absent. This server mounts `StaticFiles(html=True)` at
// "/" as the catch-all for every path this build does not route: a GET to an absent
// path falls through to that catch-all and gets a genuine 404, but Starlette's
// StaticFiles app answers any non-GET method with 405 Method Not Allowed instead —
// so a POST-only capability (one-way sensitivity, rebase-preview, revision export,
// model XLSX export) hits 405, not 404, when its route isn't served here. All
// registered routes this frontend calls are invoked with their correct HTTP method,
// so a genuine method-mismatch 405 is not an expected path — observing one here
// means the route itself is absent, exactly like a 404.
export function isUnavailableRoute(caught: unknown): boolean {
  if (!(caught instanceof Error) || !("status" in caught)) return false;
  const status = (caught as { status?: unknown }).status;
  return status === 404 || status === 405;
}

export async function api<T>(path: string, options: RequestInit = {}, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { ...options, signal, headers: options.body instanceof FormData ? options.headers : { "Content-Type": "application/json", ...options.headers } });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiRequestError(response.status, body.detail);
  }
  return response.json() as Promise<T>;
}
