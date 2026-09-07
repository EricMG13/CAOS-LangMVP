import type { ModelReadiness, WorksheetResponse, WorksheetTab } from "../../lib/api";

export function modelDisplayStatus(readiness?: Pick<ModelReadiness, "status" | "build">) {
  return readiness?.status === "READY_TO_BUILD" ? readiness.build?.status || readiness.status : readiness?.status;
}

export type ModelCase = "BASE" | "DOWNSIDE";

let calculationTail: Promise<unknown> = Promise.resolve();

export function queueCalculation<T>(calculate: () => Promise<T>, isCurrent: () => boolean): Promise<T | null> {
  // Keep the queue across component remounts: aborting fetch does not stop server calculation.
  const next = calculationTail.then(() => isCurrent() ? calculate() : null);
  calculationTail = next.catch(() => undefined);
  return next;
}
export type AssumptionStatus = "READY" | "UNAVAILABLE" | "NOT_APPLICABLE";

// ponytail: one calculation at a time per tab; coordinate across tabs if needed.
// Cancelling queued work must not release an active server calculation's slot.
let calculationChain = Promise.resolve();
export function queueModelCalculation<T>(calculate: () => Promise<T>, signal?: AbortSignal): Promise<T> {
  const next = calculationChain.then(() => {
    signal?.throwIfAborted();
    return calculate();
  });
  calculationChain = next.then(() => {}, () => {});
  return next;
}

export function worksheetColumns(maxColumn: number): { column: number; letter: string }[] {
  return Array.from({ length: maxColumn }, (_, index) => {
    let value = index + 1;
    let letter = "";
    while (value > 0) {
      value -= 1;
      letter = String.fromCharCode(65 + value % 26) + letter;
      value = Math.floor(value / 26);
    }
    return { column: index + 1, letter };
  });
}

export type WorksheetSelection = { tabId: string; address: string };

export function selectedWorksheetCell(payload: WorksheetPayload, selection: WorksheetSelection | null) {
  if (!selection) return null;
  return payload.tabs.find((tab) => tab.id === selection.tabId)?.cells.find((cell) => cell.address === selection.address) || null;
}

const periodFamilyLabels: Record<string, string> = {
  QUARTER: "Quarter", YTD: "YTD", LTM: "LTM", PF: "Pro forma", BASE: "Base", DOWNSIDE: "Downside",
};

export function worksheetPeriodFamilies(tab: WorksheetTab) {
  const periodColumns = new Set<number>();
  for (const cell of tab.cells) {
    if (cell.period_id) periodColumns.add(cell.column);
  }
  const columns = new Map<number, string>();
  for (const cell of tab.cells) {
    if (periodColumns.has(cell.column)
      && cell.semantic_id === null
      && cell.period_id === null
      && typeof cell.value === "string"
      && cell.value in periodFamilyLabels) {
      columns.set(cell.column, cell.value);
    }
  }
  const families = new Map<string, number[]>();
  for (const [column, family] of columns) {
    const values = families.get(family) || [];
    values.push(column);
    families.set(family, values);
  }
  return [...families].map(([id, familyColumns]) => ({
    id,
    label: periodFamilyLabels[id] || id.replaceAll("_", " ").toLowerCase().replace(/^./, (letter) => letter.toUpperCase()),
    columns: familyColumns,
  }));
}

export function worksheetPeriodHeaderRows(
  tab: WorksheetTab,
  families = worksheetPeriodFamilies(tab),
) {
  const familyColumns = new Set(families.flatMap((family) => family.columns));
  const familyIds = new Set(families.map((family) => family.id));
  return [...new Set(tab.cells
    .filter((cell) => familyColumns.has(cell.column)
      && cell.semantic_id === null
      && cell.period_id === null
      && typeof cell.value === "string"
      && familyIds.has(cell.value))
    .map((cell) => cell.row))].sort((left, right) => left - right);
}

type WorksheetGroup = { id: string; label: string; startRow: number; endRow: number };
type WorksheetRowState = { cell: WorksheetTab["cells"][number]; populated: number };

const worksheetSectionAnchors = ["revenue", "cash_flow_adjusted_ebitda", "cash_and_equivalents", "growth::revenue"];

function worksheetStructure(tab: WorksheetTab) {
  const rows = new Map<number, WorksheetRowState>();
  const semantics = new Map<string, WorksheetTab["cells"][number]>();
  for (const cell of tab.cells) {
    if (cell.semantic_id && !semantics.has(cell.semantic_id)) semantics.set(cell.semantic_id, cell);
    if (cell.value === null || cell.value === "") continue;
    const state = rows.get(cell.row);
    if (state) state.populated += 1;
    else rows.set(cell.row, { cell, populated: 1 });
  }
  const headers = new Map<number, WorksheetTab["cells"][number]>();
  for (const [row, state] of rows) {
    if (state.populated === 1 && state.cell.column === 1 && typeof state.cell.value === "string") {
      headers.set(row, state.cell);
    }
  }
  const headerBefore = (anchorRow: number) => {
    let headerRow = anchorRow - 1;
    while (headerRow >= 1 && !headers.has(headerRow)) headerRow -= 1;
    if (headerRow < 1) return null;
    while (headerRow > 1 && headers.has(headerRow - 1)) headerRow -= 1;
    return { header: headers.get(headerRow)!, headerRow };
  };
  return { headerBefore, semantics };
}

function worksheetSectionEntries(tab: WorksheetTab, structure = worksheetStructure(tab)) {
  // The serializer's semantic mapping is durable authority metadata; workbook
  // paint is deliberately not part of the stored payload. Each anchor names the
  // first calculated/source row in a major Model section. The label is still
  // read from the served workbook's nearest preceding structural header.
  const groups = worksheetSectionAnchors.flatMap((semanticId) => {
    const anchor = structure.semantics.get(semanticId);
    if (!anchor) return [];
    const header = structure.headerBefore(anchor.row);
    return header ? [{
      anchor: semanticId,
      id: `${tab.id}:${header.headerRow}`,
      label: String(header.header.value),
      startRow: header.headerRow,
      endRow: tab.max_row,
    }] : [];
  }).sort((left, right) => left.startRow - right.startRow);
  return groups.map((group, index) => ({
    ...group,
    endRow: (groups[index + 1]?.startRow || tab.max_row + 1) - 1,
  }));
}

export function worksheetSections(tab: WorksheetTab): WorksheetGroup[] {
  return worksheetSectionEntries(tab).map((section) => ({
    id: section.id,
    label: section.label,
    startRow: section.startRow,
    endRow: section.endRow,
  }));
}

export function worksheetRowGroups(tab: WorksheetTab): WorksheetGroup[] {
  const structure = worksheetStructure(tab);
  const sections = worksheetSectionEntries(tab, structure);
  const groups: WorksheetGroup[] = sections
    .filter((section) => section.anchor === "cash_flow_adjusted_ebitda" || section.anchor === "cash_and_equivalents")
    .map((section) => ({
      id: section.id,
      label: section.label,
      startRow: section.startRow,
      endRow: section.endRow,
    }));

  let businessStart = Infinity;
  let businessEnd = -Infinity;
  for (const cell of tab.cells) {
    if (cell.semantic_id?.startsWith("segment::")) {
      businessStart = Math.min(businessStart, cell.row);
      businessEnd = Math.max(businessEnd, cell.row);
    }
  }
  if (businessStart !== Infinity) {
    const businessHeader = structure.headerBefore(businessStart);
    groups.push({
      id: `${tab.id}:business-segments`,
      label: "Business segments",
      startRow: businessHeader?.headerRow ?? Math.max(0, businessStart - 1),
      endRow: businessEnd,
    });
  }

  const debtSection = sections.find((section) => section.anchor === "cash_and_equivalents");
  if (debtSection) {
    const debtKinds = [
      ["secured", (semanticId: string) => semanticId.startsWith("debt::") && semanticId.endsWith("::SECURED")],
      ["unsecured", (semanticId: string) => semanticId.startsWith("debt::") && semanticId.endsWith("::UNSECURED")],
      ["other", (semanticId: string) => semanticId === "forecast::unallocated_debt_movement"],
    ] as const;
    const debtGroups = debtKinds.flatMap(([id, matches]) => {
      const anchor = tab.cells.find((cell) => cell.semantic_id && matches(cell.semantic_id));
      const header = anchor ? structure.headerBefore(anchor.row) : null;
      return header ? [{
        id: `${tab.id}:debt-${id}`,
        label: String(header.header.value),
        startRow: header.headerRow,
        endRow: debtSection.endRow,
      }] : [];
    }).sort((left, right) => left.startRow - right.startRow);
    debtGroups.forEach((group, index) => {
      groups.push({ ...group, endRow: (debtGroups[index + 1]?.startRow || debtSection.endRow + 1) - 1 });
    });
  }
  return groups.sort((left, right) => left.startRow - right.startRow);
}

export function worksheetCellAuthority(writeClass: string | null) {
  if (writeClass === "SOURCE" || writeClass === "SNAPSHOT_SOURCE") {
    return { className: "is-source", label: "Historical source — locked" };
  }
  if (writeClass === "FORMULA" || writeClass === "CALCULATED") {
    return { className: "is-calculated", label: "Calculated formula — locked" };
  }
  if (writeClass === "ASSUMPTION") {
    return { className: "is-assumption", label: "Forecast assumption — edit in Assumptions" };
  }
  return { className: "is-locked", label: "Worksheet cell — locked" };
}

export type AssumptionSourceContext = {
  authority_module: "CP-2G";
  gap_code: string;
  provenance: { source_id: string; source_locator: string; as_of: string }[];
};

export type ModelAssumptionValue = {
  assumption_id: string;
  case: ModelCase;
  period_id: string;
  unit: string;
  status: AssumptionStatus;
  value: number | null;
  gap_code: string | null;
  default_value: number | null;
  default_status: AssumptionStatus | null;
  default_gap_code: string | null;
  source_context: AssumptionSourceContext | null;
  source_context_digest: string | null;
};

export type WireAssumptionValue = Omit<ModelAssumptionValue, "value" | "default_value"> & {
  value: number | string | null;
  default_value: number | string | null;
};

export type AssumptionDefinition = {
  assumption_id: string;
  label: string;
  family: string;
  description: string;
  unit: string;
  cases: ModelCase[];
  sensitivity_default: { range: string; step: string };
  hard_min: string;
  hard_max: string;
  affected_outputs: string[];
  allowed_statuses?: AssumptionStatus[];
  slot_id?: string;
};

export type AssumptionRegistry = {
  version: string;
  digest: string;
  definitions: AssumptionDefinition[];
  build_id: string;
  accepted_snapshot_id: string;
  input_fingerprint: string;
  defaults: WireAssumptionValue[];
};

export type WorksheetPayload = WorksheetResponse["payload"];

export type ModelPreview = {
  case_id: string;
  build_id: string;
  accepted_snapshot_id: string;
  build_input_fingerprint: string;
  build_payload_digest: string;
  registry_version: string;
  registry_digest: string;
  calculation_contract_version: string;
  parent_revision_id: string | null;
  draft_generation: number;
  effective_assumptions: WireAssumptionValue[];
  assumptions_digest: string;
  outputs: Record<string, unknown>;
  outputs_digest: string;
  worksheet: WorksheetPayload;
  deltas: Record<string, unknown>;
  preview_digest: string;
};

export type PreviewIdentity = {
  buildId: string;
  buildInputFingerprint: string;
  buildPayloadDigest: string;
  registryVersion: string;
  registryDigest: string;
  parentRevisionId: string | null;
  expectedHeadRevisionId: string | null;
  currentHeadRevisionId: string | null;
  draftGeneration: number;
};

export type PrimaryModelAction = "BUILD" | "PREVIEW" | "SIGN_OFF";

function finiteNumber(value: number | string | null, field: string): number | null {
  if (value === null) return null;
  const parsed = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(parsed)) throw new Error(`INVALID_${field.toUpperCase()}`);
  return parsed;
}

export function assumptionKey(row: Pick<ModelAssumptionValue, "assumption_id" | "case" | "period_id">) {
  return `${row.assumption_id}\u0000${row.case}\u0000${row.period_id}`;
}

export function applicationBuildDelta(row: Pick<ModelAssumptionValue, "value" | "default_value">) {
  return row.value === null || row.default_value === null ? null : row.value - row.default_value;
}

export function normalizeAssumptions(rows: readonly WireAssumptionValue[]): ModelAssumptionValue[] {
  const seen = new Set<string>();
  return rows.map((row) => {
    const key = assumptionKey(row as ModelAssumptionValue);
    if (seen.has(key)) throw new Error("DUPLICATE_ASSUMPTION_IDENTITY");
    seen.add(key);
    const value = finiteNumber(row.value, "assumption_value");
    const defaultValue = finiteNumber(row.default_value, "default_value");
    if (row.status === "READY" && value === null) throw new Error("READY_ASSUMPTION_VALUE_REQUIRED");
    return {
      ...row,
      value,
      default_value: defaultValue,
      source_context: row.source_context ? {
        ...row.source_context,
        provenance: row.source_context.provenance.map((item) => ({ ...item })),
      } : null,
    };
  });
}

export function applyAssumptionValue(
  rows: readonly ModelAssumptionValue[],
  definition: AssumptionDefinition,
  caseName: ModelCase,
  periodScope: "ALL" | string,
  value: number,
) {
  if (!Number.isFinite(value)) throw new Error("ASSUMPTION_VALUE_NOT_FINITE");
  if (value < Number(definition.hard_min) || value > Number(definition.hard_max)) {
    throw new Error("ASSUMPTION_OUT_OF_BOUNDS");
  }
  let changed = 0;
  const next = rows.map((row) => {
    const matches = row.assumption_id === definition.assumption_id
      && row.case === caseName
      && (periodScope === "ALL" || row.period_id === periodScope);
    if (!matches) return row;
    if (row.status !== "READY") throw new Error("ASSUMPTION_NOT_EDITABLE");
    changed += 1;
    return { ...row, value };
  });
  if (changed === 0) throw new Error("ASSUMPTION_NOT_APPLICABLE");
  return next;
}

export function applyServerAssumptions(
  current: readonly ModelAssumptionValue[],
  serverRows: readonly (WireAssumptionValue | ModelAssumptionValue)[],
) {
  const normalized = normalizeAssumptions(serverRows);
  const byKey = new Map(normalized.map((row) => [assumptionKey(row), row]));
  if (byKey.size !== current.length || current.some((row) => !byKey.has(assumptionKey(row)))) {
    throw new Error("ASSUMPTION_IDENTITY_SET_CHANGED");
  }
  return current.map((row) => byKey.get(assumptionKey(row))!);
}

export function assumptionScope(
  rows: readonly ModelAssumptionValue[],
  assumptionId: string,
  caseName: ModelCase,
  periodScope: "ALL" | string,
) {
  const selected = rows.filter((row) => row.assumption_id === assumptionId
    && row.case === caseName
    && (periodScope === "ALL" || row.period_id === periodScope));
  const editable = selected.length > 0 && selected.every((row) => row.status === "READY" && row.value !== null);
  const values = selected.map((row) => row.value);
  const mixed = editable && values.some((value) => value !== values[0]);
  return {
    rows: selected,
    editable,
    mixed,
    value: editable && !mixed ? String(values[0]) : "",
  };
}

export function mergeRebasedAssumptions(
  baseline: readonly ModelAssumptionValue[],
  draft: readonly ModelAssumptionValue[],
  candidate: readonly (WireAssumptionValue | ModelAssumptionValue)[],
) {
  const rebased = applyServerAssumptions(baseline, candidate);
  const baselineByKey = new Map(baseline.map((row) => [assumptionKey(row), row]));
  const draftByKey = new Map(draft.map((row) => [assumptionKey(row), row]));
  return rebased.map((row) => {
    const key = assumptionKey(row);
    const before = baselineByKey.get(key);
    const local = draftByKey.get(key);
    if (!before || !local || before.value === local.value && before.status === local.status) return row;
    return { ...row, value: local.value, status: local.status, gap_code: local.gap_code };
  });
}

type SensitivityAnnualPoint = {
  value: number | string;
  outputs: Record<string, Record<string, Record<string, unknown>>>;
  deltas: Record<string, Record<string, Record<string, unknown>>>;
};

export function sensitivityPeriodRows(result: {
  case: ModelCase;
  period_scope: string;
  output_id: string;
  points: readonly SensitivityAnnualPoint[];
}) {
  return result.points.flatMap((point) => {
    const outputs = point.outputs[result.case] || {};
    const deltas = point.deltas[result.case] || {};
    const periods = result.period_scope === "ALL"
      ? [...new Set([...Object.keys(outputs), ...Object.keys(deltas)])].sort()
      : [result.period_scope];
    return periods.map((periodId) => ({
      input: point.value,
      periodId,
      output: outputs[periodId]?.[result.output_id] ?? null,
      delta: deltas[periodId]?.[result.output_id] ?? null,
    }));
  });
}

export function assumptionChangeCount(
  baseline: readonly ModelAssumptionValue[],
  draft: readonly ModelAssumptionValue[],
) {
  const baselineByKey = new Map(baseline.map((row) => [assumptionKey(row), row]));
  return draft.reduce((count, row) => {
    const before = baselineByKey.get(assumptionKey(row));
    return count + (before && before.value === row.value && before.status === row.status ? 0 : 1);
  }, 0);
}

export function previewMatchesDraft(preview: ModelPreview | null, identity: PreviewIdentity) {
  return Boolean(preview
    && preview.build_id === identity.buildId
    && preview.build_input_fingerprint === identity.buildInputFingerprint
    && preview.build_payload_digest === identity.buildPayloadDigest
    && preview.registry_version === identity.registryVersion
    && preview.registry_digest === identity.registryDigest
    && preview.parent_revision_id === identity.parentRevisionId
    && preview.draft_generation === identity.draftGeneration
    && identity.expectedHeadRevisionId === identity.currentHeadRevisionId);
}

export function primaryModelAction({
  status,
  canWrite,
  dirty,
  previewCurrent,
}: {
  status?: string;
  canWrite: boolean;
  dirty: boolean;
  previewCurrent: boolean;
}): PrimaryModelAction | null {
  if (canWrite && (status === "READY_TO_BUILD" || status === "FAILED")) return "BUILD";
  if (status !== "READY" || !dirty) return null;
  if (previewCurrent) return canWrite ? "SIGN_OFF" : null;
  return "PREVIEW";
}


// Model outputs and assumption defaults reach the client as Decimal-serialized
// strings, so this lives beside the other pure state helpers where it can be
// tested directly — the component file cannot be imported by `node --test`.
export function formatModelValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Unavailable";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  const round = (numeric: number) => new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(numeric);
  if (typeof value === "number") return Number.isFinite(value) ? round(value) : "Unavailable";
  if (typeof value !== "string") return String(value);
  // The calculation engine serializes Decimals, so an output arrives as a numeric
  // *string* — "136.8800000000000000000000000". Rounding those to two places is the
  // point; silently rendering a *different* number is not, and a double cannot
  // carry every Decimal ("12345678901234567890.5" comes back as …567000). So the
  // rounded form is used only inside the range a double reproduces exactly;
  // anything outside it, and anything that is not a number at all, keeps the
  // digits the server sent. Ugly and exact beats tidy and wrong here.
  const trimmed = value.trim();
  if (!/^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/.test(trimmed)) return value;
  const numeric = Number(trimmed);
  if (!Number.isFinite(numeric) || Math.abs(numeric) > Number.MAX_SAFE_INTEGER) return value;
  return round(numeric);
}

// A blur commits only a change. The scrubber used to commit whatever it held on
// every blur, so Tab from an untouched input re-keyed every scrubber, unmounted
// the input that had just taken focus and posted a tornado — one remount and one
// request per fieldset the analyst tabbed through (FE-A0 F1). Numeric equality,
// so "5.0" is not a change from "5"; an empty or non-numeric entry reverts.
export function scrubberCommitDecision(next: string, committed: string): "commit" | "unchanged" | "revert" {
  const trimmed = next.trim();
  if (trimmed === "") return "revert";
  if (trimmed === committed.trim()) return "unchanged";
  const numeric = (value: string) => value.trim() === "" ? NaN : Number(value);
  const entered = numeric(trimmed);
  const current = numeric(committed);
  if (Number.isFinite(entered) && Number.isFinite(current) && entered === current) return "unchanged";
  return "commit";
}
