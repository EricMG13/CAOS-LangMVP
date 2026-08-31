import type { DeliverableBlock, EvidenceCitation } from "./DeliverableDocument";

export type RecoveryModelSelection = { kind: "ANALYST_REVISION"; build_id: string; revision_id: string } | { kind: "APPLICATION_BUILD"; build_id: string; fallback_acknowledged: true };
export type ReportRecovery = { caseId: string; pathway: string; savedAt: number; expectedVersion: number; templateId: string; templateVersion: string; modelSelection: RecoveryModelSelection | null; blocks: DeliverableBlock[] };

const MAX_RECOVERY_LENGTH = 5_000_000;
const MAX_JSON_DEPTH = 32;
const MAX_JSON_VALUES = 100_000;

const record = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const boundedString = (value: unknown, maximum: number, allowEmpty = false): value is string =>
  typeof value === "string" && value.length <= maximum && (allowEmpty || value.length > 0);
const boundedStrings = (value: unknown, minimum: number, maximum: number, itemMaximum = 120): value is string[] =>
  Array.isArray(value) && value.length >= minimum && value.length <= maximum && value.every((item) => boundedString(item, itemMaximum));
const safeInteger = (value: unknown, maximum = Number.MAX_SAFE_INTEGER): value is number =>
  typeof value === "number" && Number.isSafeInteger(value) && value >= 0 && value <= maximum;
const digest = (value: unknown): value is string => typeof value === "string" && /^[0-9a-f]{64}$/.test(value);

function boundedJson(value: unknown, depth = 0, budget = { remaining: MAX_JSON_VALUES }): boolean {
  if (budget.remaining-- <= 0 || depth > MAX_JSON_DEPTH) return false;
  if (value === null || typeof value === "string" || typeof value === "boolean") return true;
  if (typeof value === "number") return Number.isFinite(value);
  if (Array.isArray(value)) return value.every((item) => boundedJson(item, depth + 1, budget));
  return record(value) && Object.values(value).every((item) => boundedJson(item, depth + 1, budget));
}

const citations = (value: unknown, maximum: number): value is EvidenceCitation[] =>
  Array.isArray(value) && value.length <= maximum && value.every((item) =>
    record(item) && boundedString(item.source_id, 120) && boundedStrings(item.block_ids, 1, 50) && boundedString(item.claim, 1000)
  );
const validTimestamp = (value: unknown): value is number =>
  safeInteger(value) && !Number.isNaN(new Date(value).getTime());

function recoveryShock(value: unknown): value is Record<string, unknown> {
  return record(value) && boundedString(value.assumption_id, 160) &&
    (value.case === "BASE" || value.case === "DOWNSIDE") &&
    typeof value.period_id === "string" && /^FY[0-9]{4}$/.test(value.period_id) &&
    typeof value.value === "number" && Number.isFinite(value.value);
}

function recoveryScenario(value: unknown, caseId: string): value is Record<string, unknown> {
  return record(value) && value.case_id === caseId && boundedString(value.build_id, 120) &&
    (value.base_revision_id === null || boundedString(value.base_revision_id, 120)) &&
    boundedString(value.registry_version, 160) && digest(value.registry_digest) &&
    safeInteger(value.draft_generation, 2_147_483_647) &&
    Array.isArray(value.effective_assumptions) && value.effective_assumptions.length >= 1 && value.effective_assumptions.length <= 256 && value.effective_assumptions.every(record) &&
    digest(value.assumptions_digest) && record(value.outputs) && digest(value.outputs_digest) && record(value.deltas);
}

function recoveryBlock(value: unknown, caseId: string): value is DeliverableBlock {
  if (!record(value) || !boundedString(value.block_id, 160) || !boundedString(value.slot_id, 160)) return false;
  switch (value.kind) {
    case "NARRATIVE":
      return boundedString(value.text, 20_000, true) &&
        (value.content_mode === "EVIDENCE" || value.content_mode === "ANALYST_JUDGMENT") &&
        citations(value.citations, 100);
    case "EVIDENCE_REGISTER": return citations(value.citations, 500);
    case "LIMITATIONS": return boundedString(value.text, 10_000, true) && citations(value.citations, 100);
    case "GENERATED_METRIC": return boundedStrings(value.metric_ids, 1, 40);
    case "GENERATED_TABLE": return boundedString(value.table_id, 120) && boundedStrings(value.field_ids, 1, 80);
    case "GENERATED_CHART": return record(value.recipe);
    case "SCENARIO_EXHIBIT":
      return boundedString(value.title, 240) &&
        Array.isArray(value.shocks) && value.shocks.length >= 1 && value.shocks.length <= 256 && value.shocks.every(recoveryShock) &&
        recoveryScenario(value.scenario, caseId) && digest(value.scenario_digest);
    case "MODEL_APPENDIX": return true;
    default: return false;
  }
}

function recoverySelection(value: unknown): value is RecoveryModelSelection | null {
  if (value === null) return true;
  if (!record(value) || !boundedString(value.build_id, 120)) return false;
  return value.kind === "ANALYST_REVISION"
    ? boundedString(value.revision_id, 120)
    : value.kind === "APPLICATION_BUILD" && value.fallback_acknowledged === true;
}

export function reportRecoveryKey(caseId: string, pathway: string) {
  return `caos:report-recovery:${encodeURIComponent(caseId)}:${pathway}`;
}

export function parseReportRecovery(raw: string | null, caseId: string, pathway: string): ReportRecovery | null {
  if (!raw || raw.length > MAX_RECOVERY_LENGTH) return null;
  try {
    const value: unknown = JSON.parse(raw);
    if (
      !boundedJson(value) || !record(value) || value.caseId !== caseId || value.pathway !== pathway ||
      !validTimestamp(value.savedAt) || !safeInteger(value.expectedVersion) ||
      !boundedString(value.templateId, 160) || !boundedString(value.templateVersion, 160) ||
      !recoverySelection(value.modelSelection) ||
      !Array.isArray(value.blocks) || value.blocks.length < 1 || value.blocks.length > 120 || !value.blocks.every((block) => recoveryBlock(block, caseId))
    ) return null;
    return value as ReportRecovery;
  } catch {
    return null;
  }
}
