import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const workspace = readFileSync(new URL("../Workspace.tsx", import.meta.url), "utf8");
const modelBuilder = readFileSync(new URL("./ModelBuilder.tsx", import.meta.url), "utf8");
const api = readFileSync(new URL("../../lib/api.ts", import.meta.url), "utf8");

test("Workspace delegates Model Builder to the extracted component", () => {
  assert.match(workspace, /import ModelBuilder from "\.\/model\/ModelBuilder";/);
  assert.match(workspace, /case "Model Builder": return <ModelBuilder caseId=\{caseId\} role=\{role\}/);
  assert.doesNotMatch(workspace, /function ModelView\(/);
  assert.doesNotMatch(workspace, /function WorksheetGrid\(/);
});

test("accepted-analysis loads and snapshot switches reject stale async completions", () => {
  const deepDive = workspace.slice(workspace.indexOf("function DeepDive("), workspace.indexOf("const loanColumns"));
  assert.match(deepDive, /const loadGeneration = useRef\(0\)/);
  assert.match(deepDive, /const selectedCaseId = selectedCase\?\.id \|\| ""/);
  assert.match(deepDive, /\}, \[selectedCaseId\]\)/);
  assert.ok((deepDive.match(/generation !== loadGeneration\.current/g) || []).length >= 4);
  assert.match(deepDive, /return \(\) => \{ ignore = true; loadGeneration\.current \+= 1; \}/);
  assert.match(deepDive, /if \(loading\) return [\s\S]*?<LoadState loading \/>/);
  assert.match(deepDive, /setArtifactError\(firstErrorMessage\(caught, "Unable to switch snapshot"\)\)/);
  assert.doesNotMatch(deepDive, /setMessage\(firstErrorMessage\(caught, "Unable to switch snapshot"\)\)/);
});

test("unknown identity roles fail closed before shared write controls are derived", () => {
  assert.match(workspace, /\["ANALYST", "APPROVER", "ADMIN"\]\.includes\(who\.role\) \? who\.role : "READER"/);
});

test("extraction preserves the read-only worksheet keyboard and lineage contract", () => {
  assert.match(modelBuilder, /function WorksheetGrid\(/);
  assert.match(modelBuilder, /ArrowUp:[\s\S]*ArrowDown:[\s\S]*ArrowLeft:[\s\S]*ArrowRight:/);
  assert.match(modelBuilder, /event\.key === "Enter" \|\| event\.key === " "/);
  assert.match(modelBuilder, /tabIndex=\{activeCell\.row === row && activeCell\.column === column \? 0 : -1\}/);
  assert.match(modelBuilder, /aria-controls="model-cell-lineage"/);
  assert.match(modelBuilder, /READ ONLY/);
  assert.doesNotMatch(modelBuilder, /contentEditable|contenteditable/);
});

test("worksheet rendering consumes the engine tab contract", () => {
  assert.match(api, /WorksheetTab = \{ id: string; title: string;/);
  assert.match(modelBuilder, /worksheetColumns\(tab\.max_column\)/);
  assert.match(modelBuilder, /tab\.title/);
  assert.doesNotMatch(modelBuilder, /tab\.columns/);
});

test("worksheet rendering explains locked history, calculations, and forecast inputs", () => {
  assert.match(modelBuilder, /worksheetCellAuthority\(cell\?\.write_class \?\? null\)/);
  assert.match(modelBuilder, /data-write-class=\{cell\?\.write_class \|\| "LOCKED"\}/);
  assert.match(modelBuilder, /Historical and calculated cells are locked/);
  assert.match(modelBuilder, /Change forward inputs in Assumptions/);
  assert.doesNotMatch(modelBuilder, /contentEditable|contenteditable/);
});

test("authoring is registry-driven, browser-memory-only, and identity fenced", () => {
  for (const label of ["Model", "Assumptions", "Sensitivities", "History"]) {
    assert.match(modelBuilder, new RegExp(`label: "${label}"`));
  }
  assert.match(modelBuilder, /assumptionRegistryPath\(expectedCaseId, nextBuild\.id\)/);
  assert.match(api, /models\/assumption-registry\?build_id=/);
  for (const route of [
    "models/previews",
    "model-revisions/sign-off",
    "model-revisions/rebase-preview",
    "models/scenarios",
    "models/sensitivities/one-way",
  ]) {
    assert.ok(modelBuilder.includes(route), `missing Phase 3 route ${route}`);
  }
  assert.match(modelBuilder, /previewMatchesDraft/);
  assert.match(modelBuilder, /draftGeneration/);
  assert.match(modelBuilder, /expected_head_revision_id/);
  assert.match(workspace, /beforeunload/);
  assert.doesNotMatch(modelBuilder, /localStorage|sessionStorage/);
  assert.doesNotMatch(modelBuilder, /eval\(|Function\(/);
});

test("the component exposes the accepted analyst journeys and role gates", () => {
  assert.match(modelBuilder, /Sign-Off Note/);
  assert.match(modelBuilder, /Compatible/);
  assert.match(modelBuilder, /Changed/);
  assert.match(modelBuilder, /Invalidated/);
  assert.match(modelBuilder, /One-way table/);
  assert.match(modelBuilder, /One-way tornado/);
  assert.match(modelBuilder, /Breakpoint/);
  assert.match(modelBuilder, /Multi-Driver Scenario/);
  assert.match(modelBuilder, /Apply to Draft/);
  assert.match(modelBuilder, /Application Model Build/);
  assert.match(modelBuilder, /data-primary-model-action/);
  assert.match(modelBuilder, /role !== "READER"/);
});

test("readers stay read-only because server calculation routes require write access", () => {
  assert.match(modelBuilder, /disabled=\{!canWrite \|\| row\.status !== "READY"\}/);
  assert.match(modelBuilder, /if \(!canWrite \|\| !build \|\| !registry\) return/);
  assert.match(modelBuilder, /canWrite && scenario/);
  assert.match(modelBuilder, /Reader mode: assumptions and outputs remain readable/);
  assert.match(modelBuilder, /canWrite && .*Sign Off|canWrite \? "SIGN_OFF"/s);
  // Optional-chained: a revision with no export record must still render its row.
  assert.match(modelBuilder, /canWrite && \(revision\?\.export\?\.status/);
});

test("authoring tabs implement roving WAI-ARIA keyboard semantics", () => {
  assert.match(modelBuilder, /model-builder-tab-\$\{item\.id\.toLowerCase\(\)\}/);
  assert.match(modelBuilder, /tabIndex=\{view === item\.id \? 0 : -1\}/);
  assert.match(modelBuilder, /ArrowLeft/);
  assert.match(modelBuilder, /ArrowRight/);
  assert.match(modelBuilder, /Home/);
  assert.match(modelBuilder, /End/);
  assert.match(modelBuilder, /aria-controls=\{`model-builder-panel-/);
  for (const view of ["model", "assumptions", "sensitivities", "history"]) {
    assert.match(modelBuilder, new RegExp(`aria-labelledby="model-builder-tab-${view}"`));
  }
});

test("assumption review exposes application defaults, application-build deltas, mixed state, and applicability", () => {
  assert.match(modelBuilder, /Application default/);
  assert.match(modelBuilder, /Effective minus Application build/);
  assert.match(modelBuilder, /applicationBuildDelta\(row\)/);
  assert.match(modelBuilder, /mixed=\{broadcastScope\.mixed\}/);
  assert.match(modelBuilder, /broadcastScope\.editable/);
  assert.match(modelBuilder, /sensitivityScope\.editable/);
  assert.match(modelBuilder, /<label>Output<select/);
  assert.doesNotMatch(modelBuilder, /Output ID<input/);
  assert.match(modelBuilder, /aria-live="polite"/);
});

test("last successful preview remains visible but non-signable when stale or retry fails", () => {
  assert.match(modelBuilder, /Last successful preview/);
  assert.match(modelBuilder, /Preview stale/);
  assert.doesNotMatch(modelBuilder, /const invalidatePreview[\s\S]{0,400}setPreview\(null\)/);
});

test("dead capability routes degrade to the observed-404 unavailable block", () => {
  assert.match(modelBuilder, /isUnavailableRoute/);
  assert.match(api, /export function isUnavailableRoute/);
  for (const title of [
    "One-way sensitivity",
    "Rebase preview",
    "Exact revision export",
    "Exact revision download",
    "Model XLSX export",
    "Application Model Build worksheet",
  ]) {
    assert.ok(modelBuilder.includes(`<Unavailable title="${title}"`), `missing observed-404 gate for ${title}`);
  }
  // The exact revision XLSX is downloaded through fetch so a 404 is observed; the
  // only remaining bare download anchor is the served build-level download route.
  assert.doesNotMatch(modelBuilder, /model-revisions\/\$\{revision\.id\}\/download`\} download>/);
  assert.match(modelBuilder, /models\/\$\{build\.id\}\/download`\} download>/);
});

test("dirty conflicts and navigation are recoverable rather than destructive", () => {
  assert.match(modelBuilder, /mergeRebasedAssumptions/);
  assert.match(modelBuilder, /Review and rebase local Draft/);
  assert.match(workspace, /popstate/);
  assert.match(workspace, /modelDraftDirtyRef/);
  assert.match(workspace, /suppressNextModelHistoryPopRef/);
});
