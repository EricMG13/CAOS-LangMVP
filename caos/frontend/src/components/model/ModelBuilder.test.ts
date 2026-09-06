import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// The pins this file no longer carries (FE-A0 §4, FE-G1 commit 14): worksheet
// keyboard navigation, the READER write gate and the fail-closed identity
// default were regexes over the component source that every behaviour-removing
// mutation survived. The workbench smoke drives those behaviours in a browser
// (arrow-key moves, a READER's disabled inputs, the aborted /api/me floor); the
// pure decisions this component delegates to modelBuilderState.ts are tested
// there.

const workspace = readFileSync(new URL("../Workspace.tsx", import.meta.url), "utf8");
const modelBuilder = readFileSync(new URL("./ModelBuilder.tsx", import.meta.url), "utf8");
const modelState = readFileSync(new URL("./modelBuilderState.ts", import.meta.url), "utf8");
const smoke = readFileSync(new URL("../../../scripts/workbench-smoke.mjs", import.meta.url), "utf8");

test("Workspace delegates Model Builder to the extracted component", () => {
  assert.match(workspace, /import ModelBuilder from "\.\/model\/ModelBuilder";/);
  assert.match(workspace, /case "Model": return <ModelBuilder caseId=\{caseId\} role=\{role\}/);
  assert.doesNotMatch(workspace, /function ModelView\(/);
});

test("the builder exposes one model with the application build as its saved starting version", () => {
  assert.match(modelBuilder, /Application model/);
  assert.match(modelBuilder, /Application version/);
  assert.match(modelBuilder, /activeRevision\?\.worksheet \|\| applicationWorksheet\?\.payload/);
  assert.doesNotMatch(modelBuilder, /modelSurface|setModelSurface|function ApplicationModelBuild/);
  assert.doesNotMatch(modelBuilder, /Active Analyst Model|No Active Analyst Model|Application Model Build is available for comparison/);
  assert.doesNotMatch(modelBuilder, /label: "Sensitivities"|Multi-Driver Scenario|Apply to Draft/);
});

test("queued build feedback waits for a current authority refresh", () => {
  const buildFlow = modelBuilder.slice(modelBuilder.indexOf("const buildModel"), modelBuilder.indexOf("const signOff"));
  assert.match(buildFlow, /const refreshed = await refresh\(undefined, false\);\s*if \(!refreshed\) return;\s*setPending\(""\);\s*setMessage\(status === "FAILED" \? "Model rebuild queued\." : "Model build queued\."\)/);
  assert.match(modelBuilder, /if \(generation !== requestGeneration\.current \|\| expectedCaseId !== caseId\) return false;/);
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
  assert.doesNotMatch(modelBuilder, /localStorage|sessionStorage/);
});

test("model sign-off is one ordered approval sequence and remains reader-gated", () => {
  const start = modelBuilder.indexOf('data-model-approval');
  const end = modelBuilder.indexOf('</section>', start);
  const approval = modelBuilder.slice(start, end);
  assert.ok(start >= 0, "missing model approval panel");
  for (const token of ["What will bind", "Changed assumption slots", "Preview digest", "Sign-Off Note", "Save model version"]) {
    assert.match(approval, new RegExp(token));
  }
  assert.ok(approval.indexOf("What will bind") < approval.indexOf('className="state-facts"'));
  assert.ok(approval.indexOf('className="state-facts"') < approval.indexOf("Sign-Off Note"));
  assert.ok(approval.indexOf("Sign-Off Note") < approval.indexOf("Save model version"));
  assert.match(modelBuilder, /dirty && canWrite \? <section className="panel span-12" data-model-approval/);
  // FE-G4: the sign-off panel renders below the worksheet, never above it, so a
  // first edit does not displace the model; and a blank cell is never "selected".
  assert.ok(modelBuilder.indexOf("${styles.workspace}") < start, "the sign-off panel renders above the worksheet");
  assert.match(modelBuilder, /cell && selected\?\.address === cell\.address \? "is-selected"/);
  assert.doesNotMatch(modelBuilder.slice(modelBuilder.indexOf("model-builder-command-body"), start), /Save model version/);
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

test("export polling fetches only lightweight revision export states", () => {
  assert.match(modelBuilder, /model-revisions\/export-statuses/);
  assert.match(modelBuilder, /const refreshRevisionExports = useCallback/);
  assert.match(modelBuilder, /setRevisions\(\(current\) => current\.map/);
  assert.match(modelBuilder, /exportPending[\s\S]*refreshRevisionExports\(\)/);
});

test("revision export polling retries without overlapping requests", () => {
  // The interval is one named constant (W18), and the re-arm still rides it:
  // a poll schedules the next only after its own await, and only while mounted.
  assert.match(modelBuilder, /^const EXPORT_POLL_MS = \d+;$/m);
  assert.match(modelBuilder, /const poll = async \(\) => \{[\s\S]*await refreshRevisionExports\(\);[\s\S]*if \(active\) timer = window\.setTimeout\(poll, EXPORT_POLL_MS\)/);
  assert.doesNotMatch(modelBuilder, /setTimeout\(poll, \d+\)/);
  assert.match(modelBuilder, /active = false;[\s\S]*window\.clearTimeout\(timer\)/);
});

test("browser proof keeps historical and calculated cells unchanged after forecast edits", () => {
  assert.match(smoke, /data-write-class="SOURCE"/);
  assert.match(smoke, /data-write-class="FORMULA"/);
  assert.match(smoke, /forecast assumption changed a historical source cell/);
  assert.match(smoke, /forecast assumption changed a calculated historical cell/);
});
