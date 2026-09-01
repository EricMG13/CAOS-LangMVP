import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const workspace = readFileSync(new URL("../Workspace.tsx", import.meta.url), "utf8");
const modelBuilder = readFileSync(new URL("./ModelBuilder.tsx", import.meta.url), "utf8");
const modelState = readFileSync(new URL("./modelBuilderState.ts", import.meta.url), "utf8");
const api = readFileSync(new URL("../../lib/api.ts", import.meta.url), "utf8");
const smoke = readFileSync(new URL("../../../scripts/workbench-smoke.mjs", import.meta.url), "utf8");

test("Workspace delegates Model Builder to the extracted component", () => {
  assert.match(workspace, /import ModelBuilder from "\.\/model\/ModelBuilder";/);
  assert.match(workspace, /case "Model Builder": return <ModelBuilder caseId=\{caseId\} role=\{role\}/);
  assert.doesNotMatch(workspace, /function ModelView\(/);
});

test("unknown identity roles fail closed before shared write controls are derived", () => {
  assert.match(workspace, /\["ANALYST", "APPROVER", "ADMIN"\]\.includes\(who\.role\) \? who\.role : "READER"/);
});

test("the builder exposes one model with the application build as its saved starting version", () => {
  assert.match(modelBuilder, /Application model/);
  assert.match(modelBuilder, /Application version/);
  assert.match(modelBuilder, /activeRevision\?\.worksheet \|\| applicationWorksheet\?\.payload/);
  assert.doesNotMatch(modelBuilder, /modelSurface|setModelSurface|function ApplicationModelBuild/);
  assert.doesNotMatch(modelBuilder, /Active Analyst Model|No Active Analyst Model|Application Model Build is available for comparison/);
  assert.doesNotMatch(modelBuilder, /label: "Sensitivities"|Multi-Driver Scenario|Apply to Draft/);
});

test("model builder headings lead directly without decorative eyebrow stacks", () => {
  assert.doesNotMatch(modelBuilder, /className="eyebrow"/);
  assert.match(modelBuilder, /id="forecast-assumptions-heading">Forecast assumptions<\/h3>/);
  assert.match(modelBuilder, /id="application-model-heading">\{displayWorksheet\?\.identity\.issuer_name \|\| "Application model"\}<\/h3>/);
  assert.match(modelBuilder, /id="tornado-heading">Tornado<\/h3>/);
});

test("the visible worksheet is the current forecast preview without making governed cells editable", () => {
  assert.match(modelState, /worksheet: WorksheetPayload/);
  assert.match(modelBuilder, /previewCurrent \? preview\?\.worksheet/);
  assert.match(modelBuilder, /function WorksheetGrid\(/);
  assert.match(modelBuilder, /worksheetCellAuthority\(cell\?\.write_class \?\? null\)/);
  assert.match(modelBuilder, /data-write-class=\{cell\?\.write_class \|\| "LOCKED"\}/);
  assert.match(modelBuilder, /Historical and calculated cells are locked/);
  assert.doesNotMatch(modelBuilder, /contentEditable|contenteditable/);
});

test("worksheet keyboard navigation and lineage remain accessible", () => {
  assert.match(modelBuilder, /ArrowUp:[\s\S]*ArrowDown:[\s\S]*ArrowLeft:[\s\S]*ArrowRight:/);
  assert.match(modelBuilder, /event\.key === "Enter" \|\| event\.key === " "/);
  assert.match(modelBuilder, /tabIndex=\{activeCell\.row === row && activeCell\.column === column \? 0 : -1\}/);
  assert.match(modelBuilder, /aria-controls="model-cell-lineage"/);
  assert.match(api, /WorksheetTab = \{ id: string; title: string;/);
  assert.match(modelBuilder, /worksheetColumns\(tab\.max_column\)/);
});

test("legacy-style forecast scrubbers support all-years and exact-period edits", () => {
  assert.match(modelBuilder, /function ForecastScrubber\(/);
  assert.match(modelBuilder, /PX_PER_STEP/);
  assert.match(modelBuilder, /setPointerCapture/);
  assert.match(modelBuilder, /onPointerMove/);
  assert.match(modelBuilder, /All forecast years/);
  assert.match(modelBuilder, /editAssumption\(definition, selectedCase, "ALL"/);
  assert.match(modelBuilder, /editAssumption\(definition, selectedCase, row\.period_id/);
  assert.match(modelBuilder, /disabled=\{!canWrite \|\| !scope\.editable\}/);
});

test("forecast edits preview the complete draft and only then become signable", () => {
  assert.match(modelBuilder, /assumptions: nextDraft/);
  assert.match(modelBuilder, /draft_generation: nextGeneration/);
  assert.match(modelBuilder, /previewMatchesDraft/);
  assert.match(modelBuilder, /expected_head_revision_id/);
  assert.match(modelBuilder, /Sign-Off Note/);
  assert.match(workspace, /beforeunload/);
  assert.doesNotMatch(modelBuilder, /localStorage|sessionStorage/);
});

test("the legacy tornado replaces sensitivities and scenarios", () => {
  assert.match(modelBuilder, /models\/tornado/);
  assert.match(modelBuilder, /assumptions: draftRows/);
  assert.match(modelBuilder, /next\.build_id !== build\.id/);
  assert.match(modelBuilder, /next\.output_period_id !== outputPeriodId/);
  assert.match(modelBuilder, /next\.intensity !== tornadoIntensity/);
  assert.match(modelBuilder, /Net leverage/);
  assert.match(modelBuilder, /Cumulative FCF/);
  assert.match(modelBuilder, /Interest coverage/);
  assert.match(modelBuilder, /role="group" aria-label=\{`\$\{metric\.label\} tornado/);
  assert.match(modelBuilder, /left: `\$\{scale\(low\)\}%`/);
  assert.match(modelBuilder, /width: `\$\{Math\.max\(0, scale\(high\) - scale\(low\)\)\}%`/);
  assert.doesNotMatch(modelBuilder, /models\/sensitivities\/one-way|models\/scenarios/);
});

test("signed records are versions of the same model and remain recoverable", () => {
  assert.match(modelBuilder, /Model versions/);
  assert.match(modelBuilder, /Application version/);
  assert.match(modelBuilder, /Compatible/);
  assert.match(modelBuilder, /Changed/);
  assert.match(modelBuilder, /Invalidated/);
  assert.match(modelBuilder, /mergeRebasedAssumptions/);
  assert.match(modelBuilder, /Review and rebase local draft/);
});

test("readers can inspect but cannot change forecasts or sign a version", () => {
  assert.match(modelBuilder, /const canWrite = role !== "READER"/);
  assert.match(modelBuilder, /Reader mode: the model and forecast assumptions remain readable/);
  assert.match(modelBuilder, /if \(!canWrite \|\| !build \|\| !registry/);
});

test("browser proof keeps historical and calculated cells unchanged after forecast edits", () => {
  assert.match(smoke, /data-write-class="SOURCE"/);
  assert.match(smoke, /data-write-class="FORMULA"/);
  assert.match(smoke, /forecast assumption changed a historical source cell/);
  assert.match(smoke, /forecast assumption changed a calculated historical cell/);
});
