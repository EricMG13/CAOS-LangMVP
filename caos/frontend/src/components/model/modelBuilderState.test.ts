import assert from "node:assert/strict";
import test from "node:test";
import {
  applicationBuildDelta,
  applyAssumptionValue,
  formatModelValue,
  applyServerAssumptions,
  assumptionScope,
  mergeRebasedAssumptions,
  normalizeAssumptions,
  previewMatchesDraft,
  primaryModelAction,
  queueCalculation,
  scrubberCommitDecision,
  selectedWorksheetCell,
  sensitivityPeriodRows,
  tornadoOutputLabel,
  worksheetNavigationForIdentity,
  worksheetSourceLinks,
  worksheetCellAuthority,
  worksheetColumns,
  worksheetPeriodHeaderRows,
  worksheetPeriodFamilies,
  worksheetRowGroups,
  worksheetSections,
  type AssumptionDefinition,
  type ModelAssumptionValue,
  type ModelPreview,
} from "./modelBuilderState.ts";
import type { WorksheetTab } from "../../lib/api.ts";

const worksheetCell = (
  address: string,
  row: number,
  column: number,
  value: string | number,
  overrides: Partial<WorksheetTab["cells"][number]> = {},
): WorksheetTab["cells"][number] => ({
  address, row, column, value, value_type: typeof value === "number" ? "number" : "text",
  formula: null, semantic_id: null, owner: null, write_class: null, period_id: null,
  source_refs: null, source_links: [], ...overrides,
});

const realModelTab: WorksheetTab = {
  id: "MODEL",
  title: "Model",
  max_row: 81,
  max_column: 5,
  cells: [
    worksheetCell("B3", 3, 2, "QUARTER"),
    worksheetCell("C3", 3, 3, "QUARTER"),
    worksheetCell("D3", 3, 4, "BASE"),
    worksheetCell("E3", 3, 5, "DOWNSIDE"),
    worksheetCell("A4", 4, 1, "Metric"),
    worksheetCell("B4", 4, 2, "Q1 FY24"),
    worksheetCell("C4", 4, 3, "Q2 FY24"),
    worksheetCell("D4", 4, 4, "Base FY25"),
    worksheetCell("E4", 4, 5, "Downside FY25"),
    worksheetCell("A5", 5, 1, "Period end"),
    worksheetCell("B5", 5, 2, "2024-03-31T00:00:00"),
    worksheetCell("C5", 5, 3, "2024-06-30T00:00:00"),
    worksheetCell("D5", 5, 4, "2025-12-31T00:00:00"),
    worksheetCell("E5", 5, 5, "2025-12-31T00:00:00"),
    worksheetCell("A7", 7, 1, "Income Statement"),
    worksheetCell("A8", 8, 1, "Services"),
    worksheetCell("B8", 8, 2, 100, { semantic_id: "segment::services", period_id: "FY2024_Q1", write_class: "SOURCE" }),
    worksheetCell("A9", 9, 1, "Products"),
    worksheetCell("B9", 9, 2, 50, { semantic_id: "segment::products", period_id: "FY2024_Q1", write_class: "SOURCE" }),
    worksheetCell("B10", 10, 2, 150, { semantic_id: "revenue", period_id: "FY2024_Q1", write_class: "SOURCE" }),
    worksheetCell("A32", 32, 1, "Cash Flow"),
    worksheetCell("B33", 33, 2, 21, { semantic_id: "cash_flow_adjusted_ebitda", period_id: "FY2024_Q1", write_class: "FORMULA" }),
    worksheetCell("B38", 38, 2, 17, { semantic_id: "ffo", period_id: "FY2024_Q1", write_class: "FORMULA" }),
    worksheetCell("C38", 38, 3, 18, { semantic_id: "ffo", period_id: "FY2024_Q2", write_class: "FORMULA" }),
    worksheetCell("D38", 38, 4, 19, { semantic_id: "ffo", period_id: "FY2025", write_class: "FORMULA" }),
    worksheetCell("A54", 54, 1, "Balance Sheet and Debt"),
    worksheetCell("B55", 55, 2, 29, { semantic_id: "cash_and_equivalents", period_id: "FY2024_Q1", write_class: "SOURCE" }),
    worksheetCell("D55", 55, 4, 39, { semantic_id: "cash_and_equivalents", period_id: "FY2025", write_class: "FORMULA" }),
    worksheetCell("E55", 55, 5, 31, { semantic_id: "cash_and_equivalents", period_id: "FY2025", write_class: "FORMULA" }),
    worksheetCell("A57", 57, 1, "Secured debt"),
    worksheetCell("B58", 58, 2, 200, { semantic_id: "debt::term-loan::SECURED", period_id: "FY2024_Q1", write_class: "SOURCE" }),
    worksheetCell("A61", 61, 1, "Unsecured debt"),
    worksheetCell("B62", 62, 2, 50, { semantic_id: "debt::notes::UNSECURED", period_id: "FY2024_Q1", write_class: "SOURCE" }),
    worksheetCell("A64", 64, 1, "Other / security not stated"),
    worksheetCell("D65", 65, 4, -15, { semantic_id: "forecast::unallocated_debt_movement", period_id: "FY2025", write_class: "FORMULA" }),
    worksheetCell("A71", 71, 1, "Debt reconciliation"),
    worksheetCell("D71", 71, 4, 0, { semantic_id: "total_debt_variance", period_id: "FY2025", write_class: "FORMULA" }),
    worksheetCell("A80", 80, 1, "Credit Metrics"),
    worksheetCell("D81", 81, 4, 0.04, { semantic_id: "growth::revenue", period_id: "FY2025", write_class: "FORMULA" }),
  ],
};

test("derives spreadsheet columns from the engine's max-column metadata", () => {
  const columns = worksheetColumns(28);

  assert.deepEqual(columns.slice(0, 2), [
    { column: 1, letter: "A" },
    { column: 2, letter: "B" },
  ]);
  assert.deepEqual(columns.slice(-3), [
    { column: 26, letter: "Z" },
    { column: 27, letter: "AA" },
    { column: 28, letter: "AB" },
  ]);
});

test("minimum cash labels the exact returned forecast horizon", () => {
  assert.equal(tornadoOutputLabel("Minimum cash", [
    "BASE::FY2025", "BASE::FY2026", "BASE::FY2027",
  ]), "Minimum cash · FY2025–FY2027");
  assert.equal(tornadoOutputLabel("Period-end cash", [
    "DOWNSIDE::FY2027",
  ]), "Period-end cash · FY2027");
});

test("period families, sections, and business/debt groups derive from served worksheet cells", () => {
  assert.deepEqual(worksheetPeriodFamilies(realModelTab), [
    { id: "QUARTER", label: "Quarter", columns: [2, 3] },
    { id: "BASE", label: "Base", columns: [4] },
    { id: "DOWNSIDE", label: "Downside", columns: [5] },
  ]);
  assert.deepEqual(worksheetPeriodHeaderRows(realModelTab), [3, 4, 5]);
  assert.deepEqual(worksheetSections(realModelTab), [
    { id: "MODEL:7", label: "Income Statement", startRow: 7, endRow: 31 },
    { id: "MODEL:32", label: "Cash Flow", startRow: 32, endRow: 53 },
    { id: "MODEL:54", label: "Balance Sheet and Debt", startRow: 54, endRow: 79 },
    { id: "MODEL:80", label: "Credit Metrics", startRow: 80, endRow: 81 },
  ]);
  assert.deepEqual(worksheetRowGroups(realModelTab), [
    { id: "MODEL:business-segments", label: "Business segments", startRow: 7, endRow: 9 },
    { id: "MODEL:32", label: "Cash Flow", startRow: 32, endRow: 53 },
    { id: "MODEL:54", label: "Balance Sheet and Debt", startRow: 54, endRow: 79 },
    { id: "MODEL:debt-secured", label: "Secured debt", startRow: 57, endRow: 60 },
    { id: "MODEL:debt-unsecured", label: "Unsecured debt", startRow: 61, endRow: 63 },
    { id: "MODEL:debt-other", label: "Other / security not stated", startRow: 64, endRow: 79 },
  ]);
});

test("period families ignore row-three prose on tabs without period columns", () => {
  const proseTab: WorksheetTab = {
    id: "NOTES", title: "Notes", max_row: 3, max_column: 2,
    cells: [worksheetCell("B3", 3, 2, "BASE")],
  };
  assert.deepEqual(worksheetPeriodFamilies(proseTab), []);
  assert.deepEqual(worksheetPeriodHeaderRows(proseTab), []);
});

test("worksheet selection is stable by tab id and address across filtering", () => {
  const payload = { schema_version: "caos.model.worksheet.v1", identity: { issuer_id: "issuer", issuer_name: "Issuer", analysis_date: "2026-08-24" }, tabs: [realModelTab] };
  const selection = { tabId: "MODEL", address: "D55" };

  assert.equal(selectedWorksheetCell(payload, selection)?.semantic_id, "cash_and_equivalents");
  assert.equal(selectedWorksheetCell(payload, { ...selection, tabId: "KPIS" }), null);
  assert.equal(selectedWorksheetCell(payload, { ...selection, address: "D999" }), null);
});

test("legacy worksheet navigation requires the exact displayed identity and cell", () => {
  const navigation = {
    kind: "REVISION" as const,
    build_id: "mdl-1",
    revision_id: "rev-1",
    preview_digest: "digest-1",
    cells: [{
      tab_id: "MODEL",
      address: "A2",
      source_links: [{ source_id: "src-pinned", block_id: "b00001" }],
    }],
  };
  const exact = worksheetNavigationForIdentity(navigation, {
    kind: "REVISION",
    build_id: "mdl-1",
    revision_id: "rev-1",
    preview_digest: "digest-1",
  });

  assert.deepEqual(worksheetSourceLinks(
    worksheetCell("A2", 2, 1, 1, { source_refs: "opaque legacy reference", source_links: undefined }),
    "MODEL",
    exact,
  ), [{ source_id: "src-pinned", block_id: "b00001" }]);
  assert.deepEqual(worksheetSourceLinks(
    worksheetCell("A3", 3, 1, 1, { source_refs: "opaque legacy reference", source_links: undefined }),
    "MODEL",
    exact,
  ), []);
  assert.equal(worksheetNavigationForIdentity(navigation, {
    kind: "REVISION",
    build_id: "mdl-other",
    revision_id: "rev-1",
    preview_digest: "digest-1",
  }), null);
  assert.equal(worksheetNavigationForIdentity(navigation, {
    kind: "REVISION",
    build_id: "mdl-1",
    revision_id: "rev-other",
    preview_digest: "digest-1",
  }), null);
  assert.equal(worksheetNavigationForIdentity(navigation, {
    kind: "REVISION",
    build_id: "mdl-1",
    revision_id: "rev-1",
    preview_digest: "digest-other",
  }), null);
  assert.equal(worksheetNavigationForIdentity(navigation, {
    kind: "PREVIEW",
    build_id: "mdl-1",
    preview_digest: "digest-1",
  }), null);
});

test("worksheet authority keeps history and calculations locked", () => {
  assert.deepEqual(worksheetCellAuthority("SOURCE"), {
    className: "is-source",
    label: "Historical source — locked",
  });
  assert.deepEqual(worksheetCellAuthority("SNAPSHOT_SOURCE"), {
    className: "is-source",
    label: "Historical source — locked",
  });
  assert.deepEqual(worksheetCellAuthority("FORMULA"), {
    className: "is-calculated",
    label: "Calculated formula — locked",
  });
  assert.deepEqual(worksheetCellAuthority("CALCULATED"), {
    className: "is-calculated",
    label: "Calculated formula — locked",
  });
  assert.deepEqual(worksheetCellAuthority("ASSUMPTION"), {
    className: "is-assumption",
    label: "Forecast assumption — edit in Assumptions",
  });
});

const definition: AssumptionDefinition = {
  assumption_id: "operating.revenue_growth.division_1",
  label: "Division 1 revenue growth",
  family: "OPERATING",
  description: "Canonical division growth.",
  unit: "PERCENT_DECIMAL",
  cases: ["BASE", "DOWNSIDE"],
  sensitivity_default: { range: "0.02", step: "0.01" },
  hard_min: "-0.75",
  hard_max: "2",
  affected_outputs: ["revenue", "total_leverage"],
};

const rows = ["BASE", "DOWNSIDE"].flatMap((caseName) => ["FY2025", "FY2026", "FY2027"].map((period, index) => ({
  assumption_id: definition.assumption_id,
  case: caseName as "BASE" | "DOWNSIDE",
  period_id: period,
  unit: definition.unit,
  status: "READY" as const,
  value: String(0.03 + index / 100),
  gap_code: null,
  default_value: String(0.03 + index / 100),
  default_status: "READY" as const,
  default_gap_code: null,
  source_context: { authority_module: "CP-2G" as const, gap_code: "", provenance: [{ source_id: "src_1", source_locator: "page 4", as_of: "2026-08-25" }] },
  source_context_digest: "a".repeat(64),
})));

test("normalizes methodology numeric strings without dropping source context", () => {
  const normalized = normalizeAssumptions(rows);

  assert.equal(normalized[0].value, 0.03);
  assert.equal(normalized[0].default_value, 0.03);
  assert.equal(normalized[0].source_context?.provenance[0].source_locator, "page 4");
  assert.notStrictEqual(normalized[0], rows[0]);
});

test("assumption delta is measured against the Application Model Build default", () => {
  const row = normalizeAssumptions(rows)[0];
  const signedValue = { ...row, value: 0.02, default_value: 0.03 };
  const localDraft = { ...signedValue, value: 0.04 };

  assert.ok(Math.abs(applicationBuildDelta(localDraft)! - 0.01) < Number.EPSILON);
  assert.equal(applicationBuildDelta({ ...localDraft, default_value: null }), null);
});

test("all-year editing broadcasts within one case and enforces methodology bounds", () => {
  const normalized = normalizeAssumptions(rows);
  const changed = applyAssumptionValue(normalized, definition, "BASE", "ALL", 0.12);

  assert.deepEqual(changed.filter((row) => row.case === "BASE").map((row) => row.value), [0.12, 0.12, 0.12]);
  assert.deepEqual(changed.filter((row) => row.case === "DOWNSIDE").map((row) => row.value), [0.03, 0.04, 0.05]);
  assert.throws(() => applyAssumptionValue(normalized, definition, "BASE", "FY2026", 2.01), /ASSUMPTION_OUT_OF_BOUNDS/);
});

test("server scenario and rebase assumptions replace the draft locally by identity", () => {
  const normalized = normalizeAssumptions(rows);
  const serverRows: ModelAssumptionValue[] = normalized.map((row) => row.case === "DOWNSIDE" && row.period_id === "FY2027" ? { ...row, value: -0.2 } : row);
  const applied = applyServerAssumptions(normalized, serverRows);

  assert.equal(applied.find((row) => row.case === "DOWNSIDE" && row.period_id === "FY2027")?.value, -0.2);
  assert.equal(applied.length, normalized.length);
});

test("preview eligibility binds draft generation, build, registry, parent, and active head", () => {
  const preview = {
    build_id: "model_1",
    build_input_fingerprint: "b".repeat(64),
    build_payload_digest: "c".repeat(64),
    registry_version: "registry.v1",
    registry_digest: "d".repeat(64),
    parent_revision_id: "revision_1",
    draft_generation: 7,
    preview_digest: "e".repeat(64),
  } as ModelPreview;
  const identity = {
    buildId: "model_1",
    buildInputFingerprint: "b".repeat(64),
    buildPayloadDigest: "c".repeat(64),
    registryVersion: "registry.v1",
    registryDigest: "d".repeat(64),
    parentRevisionId: "revision_1",
    expectedHeadRevisionId: "revision_1",
    currentHeadRevisionId: "revision_1",
    draftGeneration: 7,
  };

  assert.equal(previewMatchesDraft(preview, identity), true);
  assert.equal(previewMatchesDraft(preview, { ...identity, draftGeneration: 8 }), false);
  assert.equal(previewMatchesDraft(preview, { ...identity, currentHeadRevisionId: "revision_2" }), false);
  assert.equal(previewMatchesDraft(preview, { ...identity, buildPayloadDigest: "f".repeat(64) }), false);
  assert.equal(previewMatchesDraft({ ...preview, parent_revision_id: null }, { ...identity, parentRevisionId: null }), true,
    "a new build has no compatible parent but still compares against the case's previous head");
});

test("calculations finish serially, skip obsolete drafts, and recover after rejection", async () => {
  const events: string[] = [];
  let release!: () => void;
  const blocked = new Promise<void>((resolve) => { release = resolve; });
  const first = queueCalculation(async () => { events.push("start"); await blocked; events.push("finish"); }, () => true);
  const obsolete = queueCalculation(async () => { events.push("obsolete"); }, () => false);
  const latest = queueCalculation(async () => { events.push("latest"); return 3; }, () => true);
  await Promise.resolve();
  assert.deepEqual(events, ["start"]);
  release();
  await first;
  assert.equal(await obsolete, null);
  assert.equal(await latest, 3);
  assert.deepEqual(events, ["start", "finish", "latest"]);
  await assert.rejects(queueCalculation(async () => { throw new Error("refused"); }, () => true));
  assert.equal(await queueCalculation(async () => 4, () => true), 4);
});

test("the workflow exposes only the primary action appropriate to current state", () => {
  assert.equal(primaryModelAction({ status: "READY_TO_BUILD", canWrite: true, dirty: false, previewCurrent: false }), "BUILD");
  assert.equal(primaryModelAction({ status: "READY", canWrite: true, dirty: true, previewCurrent: false }), "PREVIEW");
  assert.equal(primaryModelAction({ status: "READY", canWrite: true, dirty: true, previewCurrent: true }), "SIGN_OFF");
  assert.equal(primaryModelAction({ status: "READY", canWrite: false, dirty: true, previewCurrent: true }), null);
});

test("one-way rows consume nested Base and Downside annual server outputs exactly", () => {
  const result = {
    case: "BASE" as const,
    period_scope: "ALL",
    output_id: "total_leverage",
    points: [
      { value: 0.01, outputs: { BASE: { FY2025: { total_leverage: "4.3" }, FY2026: { total_leverage: null } }, DOWNSIDE: { FY2025: { total_leverage: "5.1" } } }, deltas: { BASE: { FY2025: { total_leverage: "0.1" }, FY2026: { total_leverage: null } }, DOWNSIDE: { FY2025: { total_leverage: "0.2" } } } },
      { value: 0.05, outputs: { BASE: { FY2025: { total_leverage: "3.9" }, FY2026: { total_leverage: "3.7" } }, DOWNSIDE: { FY2025: { total_leverage: "4.8" } } }, deltas: { BASE: { FY2025: { total_leverage: "-0.3" }, FY2026: { total_leverage: "-0.4" } }, DOWNSIDE: { FY2025: { total_leverage: "-0.1" } } } },
    ],
  };

  assert.deepEqual(sensitivityPeriodRows(result), [
    { input: 0.01, periodId: "FY2025", output: "4.3", delta: "0.1" },
    { input: 0.01, periodId: "FY2026", output: null, delta: null },
    { input: 0.05, periodId: "FY2025", output: "3.9", delta: "-0.3" },
    { input: 0.05, periodId: "FY2026", output: "3.7", delta: "-0.4" },
  ]);
  assert.deepEqual(sensitivityPeriodRows({ ...result, case: "DOWNSIDE", period_scope: "FY2025" }), [
    { input: 0.01, periodId: "FY2025", output: "5.1", delta: "0.2" },
    { input: 0.05, periodId: "FY2025", output: "4.8", delta: "-0.1" },
  ]);
});

test("assumption scopes expose controlled same/mixed values and disable unavailable scopes", () => {
  const normalized = normalizeAssumptions(rows);
  assert.deepEqual(assumptionScope(normalized, definition.assumption_id, "BASE", "ALL"), {
    rows: normalized.filter((row) => row.case === "BASE"),
    editable: true,
    mixed: true,
    value: "",
  });
  const same = applyAssumptionValue(normalized, definition, "BASE", "ALL", 0.12);
  assert.equal(assumptionScope(same, definition.assumption_id, "BASE", "ALL").value, "0.12");
  const unavailable = same.map((row) => row.case === "BASE" && row.period_id === "FY2026" ? { ...row, status: "UNAVAILABLE" as const, value: null, gap_code: "LIQUIDITY_UNAVAILABLE" } : row);
  assert.equal(assumptionScope(unavailable, definition.assumption_id, "BASE", "ALL").editable, false);
  assert.equal(assumptionScope(unavailable, definition.assumption_id, "BASE", "FY2025").editable, true);
});

test("rebase candidates retain local draft shocks over the server-owned candidate", () => {
  const baseline = normalizeAssumptions(rows);
  const draft = applyAssumptionValue(baseline, definition, "BASE", "FY2025", 0.12);
  const candidate = baseline.map((row) => row.case === "DOWNSIDE" && row.period_id === "FY2027" ? { ...row, value: -0.15 } : row);
  const merged = mergeRebasedAssumptions(baseline, draft, candidate);

  assert.equal(merged.find((row) => row.case === "BASE" && row.period_id === "FY2025")?.value, 0.12);
  assert.equal(merged.find((row) => row.case === "DOWNSIDE" && row.period_id === "FY2027")?.value, -0.15);
});


test("model outputs read as audited numbers whether the wire sends them as numbers or Decimal strings", () => {
  // The calculation engine serializes Decimals, so this is the common shape.
  assert.equal(formatModelValue("136.8800000000000000000000000"), "136.88");
  assert.equal(formatModelValue("0.20"), "0.2");
  assert.equal(formatModelValue("-1.5e2"), "-150");
  assert.equal(formatModelValue(136.88), "136.88");
  assert.equal(formatModelValue(0), "0");
  assert.equal(formatModelValue(false), "No");
  assert.equal(formatModelValue(true), "Yes");
  // Absent is never a number.
  assert.equal(formatModelValue(null), "Unavailable");
  assert.equal(formatModelValue(undefined), "Unavailable");
  assert.equal(formatModelValue(""), "Unavailable");
  assert.equal(formatModelValue(Number.NaN), "Unavailable");
  assert.equal(formatModelValue(Number.POSITIVE_INFINITY), "Unavailable");
  // A string that is not a number is shown exactly as served, never coerced.
  assert.equal(formatModelValue("COVENANT_HEADROOM_UNAVAILABLE"), "COVENANT_HEADROOM_UNAVAILABLE");
  assert.equal(formatModelValue("Infinity"), "Infinity");
  assert.equal(formatModelValue("12 months"), "12 months");
  // Outside the range a double reproduces, the served digits survive intact —
  // rounding these would print a number the server never calculated.
  assert.equal(formatModelValue("12345678901234567890.5"), "12345678901234567890.5");
  assert.equal(formatModelValue("1e309"), "1e309");
  assert.equal(formatModelValue(String(Number.MAX_SAFE_INTEGER)), "9,007,199,254,740,991");
});

test("a forecast scrubber commits only a changed value", () => {
  assert.equal(scrubberCommitDecision("0.04", "0.03"), "commit");
  assert.equal(scrubberCommitDecision("0.03", "0.03"), "unchanged", "blur without a change is not a commit");
  assert.equal(scrubberCommitDecision(" 0.03 ", "0.03"), "unchanged");
  assert.equal(scrubberCommitDecision("5.0", "5"), "unchanged", "numeric equality, not text");
  assert.equal(scrubberCommitDecision("0", "", ), "commit", "a value entered into a mixed scope is a change");
  assert.equal(scrubberCommitDecision("", "0.03"), "revert");
  assert.equal(scrubberCommitDecision("   ", "0.03"), "revert");
  assert.equal(scrubberCommitDecision("abc", "0.03"), "commit", "a non-numeric entry reaches the bounds check and is refused there");
});
