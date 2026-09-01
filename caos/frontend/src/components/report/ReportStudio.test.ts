import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const workspace = readFileSync(new URL("../Workspace.tsx", import.meta.url), "utf8");
const studio = readFileSync(new URL("./ReportStudio.tsx", import.meta.url), "utf8");
const document = readFileSync(new URL("./DeliverableDocument.tsx", import.meta.url), "utf8");
const documentTypes = readFileSync(new URL("./documentTypes.ts", import.meta.url), "utf8");
const styles = readFileSync(new URL("../../../app/globals.css", import.meta.url), "utf8");
const smoke = readFileSync(new URL("../../../scripts/workbench-smoke.mjs", import.meta.url), "utf8");

test("Workspace delegates Report Studio to the structured component", () => {
  assert.match(workspace, /import ReportStudio from "\.\/report\/ReportStudio";/);
  assert.match(workspace, /case "Report Studio": return <ReportStudio/);
  assert.doesNotMatch(workspace, /function ReportView\(/);
  assert.doesNotMatch(workspace, /caos-report-draft|sessionStorage/);
});

test("authoring uses the six server templates and shared append-only draft route", () => {
  for (const pathway of ["FULL_CREDIT", "EARNINGS_UPDATE", "COVENANT_REFINANCING", "RELATIVE_VALUE", "DISTRESSED_RESTRUCTURING", "DEEP_RESEARCH"]) {
    assert.match(studio, new RegExp(pathway));
  }
  assert.match(studio, /deliverables\/\$\{pathway\}\/draft/);
  assert.match(studio, /expected_version/);
  assert.match(studio, /850/);
  assert.match(studio, /Saving/);
  assert.match(studio, /Saved v/);
  assert.match(studio, /Conflict/);
  assert.match(studio, /saveGeneration/);
  assert.match(studio, /saveChain/);
});

test("the structured document is safe and keeps generated content read-only", () => {
  assert.match(document, /DocumentTableSection/);
  assert.match(document, /DocumentChartSection/);
  assert.match(document, /scope="row"/);
  assert.match(document, /scope="col"/);
  assert.match(document, /Locked ·/);
  assert.match(documentTypes, /section\.editable && section\.origin\.kind === "ANALYST"/);
  assert.doesNotMatch(document, /dangerouslySetInnerHTML|contentEditable|contenteditable/);
  assert.doesNotMatch(studio, /eval\(|Function\(/);
  assert.doesNotMatch(studio, /sessionStorage/);
});

test("unsaved report work has a scoped non-authoritative recovery copy and automatic retry", () => {
  assert.match(studio, /reportRecoveryKey\(caseId, pathway\)/);
  assert.match(studio, /window\.localStorage\.setItem/);
  assert.match(studio, /clearBrowserRecovery/);
  assert.match(studio, /SAVE_RETRY_DELAY_MS/);
  assert.match(studio, /Not shared authority/);
  for (const label of ["Restore copy", "Retry save now", "Download JSON", "Discard copy"]) assert.match(studio, new RegExp(label));
  const applyRecovery = studio.slice(studio.indexOf("const applyRecovery"), studio.indexOf("const discardRecovery"));
  assert.ok(applyRecovery.indexOf("savedVersion.current = recovery.expectedVersion") < applyRecovery.indexOf("markChanged(recovery.blocks"), "recovery must preserve its original compare-and-swap base before saving");
});

test("exact Frozen and Filed lifecycle is identity-bound and role-gated", () => {
  assert.match(studio, /draft_digest/);
  assert.match(studio, /preview_digest/);
  assert.match(studio, /input_fingerprint/);
  assert.match(studio, /role === "APPROVER" \|\| role === "ADMIN"/);
  assert.match(studio, /request-changes/);
  assert.match(studio, /export\/\$\{format\}/);
  assert.match(studio, /frozen_history/);
  assert.match(studio, /Restore as new revision/);
  assert.match(studio, /const unsavedDraft = useRef\(false\)/);
  assert.match(studio, /if \(!workspace \|\| !canWrite \|\| unsavedDraft\.current \|\| saveState\.kind !== "SAVED"\) return/);
  assert.match(studio, /disabled=\{!canWrite \|\| lifecycleBusy \|\| draftIsUnsaved \|\| saveState\.kind !== "SAVED"\}/);
  assert.doesNotMatch(studio, /onClick=\{\(\) => setBlocks\(revision\.content\.blocks\)\}/);
});

test("freeze remains a reserved approval sequence with complete blockers and governed links", () => {
  assert.match(studio, /freezeChecklist\(\{/);
  const start = studio.indexOf('data-freeze-approval');
  const end = studio.indexOf('</section>', start);
  const approval = studio.slice(start, end);
  assert.ok(start >= 0, "missing freeze approval panel");
  for (const label of ["Write access", "Exact saved revision", "Current model selection", "Required model availability"]) {
    assert.match(approval, new RegExp(label));
  }
  assert.match(approval, /withQuery\("\/model-builder", \{ case: caseId \}\)/);
  assert.match(approval, /withQuery\("\/run-console", \{ case: caseId \}\)/);
  assert.match(approval, /canWrite \? <button[^>]+data-primary-report-action/);
  assert.match(approval, /className="status idle">Reader mode/);
});

test("model fallback, evidence, scenario, focus, and case fences remain explicit", () => {
  assert.match(studio, /fallback_acknowledged: true/);
  assert.match(studio, /ANALYST_REVISION/);
  assert.match(studio, /APPLICATION_BUILD/);
  assert.match(studio, /models\/scenarios/);
  assert.match(studio, /draft_generation/);
  assert.match(studio, /AbortController/);
  assert.match(studio, /aria-live="polite"/);
  assert.match(studio, /onDraftStateChange/);
});

test("evidence search covers every served source block without silent truncation", () => {
  assert.match(studio, /block\.text/);
  assert.match(studio, /JSON\.stringify\(block\.locator\)/);
  assert.match(studio, /visibleEvidenceBlocks/);
  assert.doesNotMatch(studio, /visibleSources\.slice/);
  assert.doesNotMatch(studio, /source\.blocks\.slice/);
});

test("the selected editor leads and expert composition tools are progressively disclosed", () => {
  const compose = studio.slice(studio.indexOf('className="panel-body report-editor-scroll"'));
  const editor = compose.indexOf('narrative-${selectedNarrative.block_id}');
  assert.ok(editor >= 0 && editor < compose.indexOf('className="report-authority-strip"'), "model authority precedes the selected editor");
  assert.match(compose, /rows=\{8\}/);
  for (const label of ["Evidence search and citations", "Scenario insertion"]) assert.match(compose, new RegExp(`<summary>${label}`));
  const outline = studio.slice(studio.indexOf('className="panel-body report-rail-scroll"'), studio.indexOf('className="panel report-compose"'));
  assert.match(outline, /<details className="report-optional"><summary>Optional composition<\/summary>/);
});

test("Scenario registry is build-bound and seeded only from server defaults", () => {
  assert.match(studio, /assumptionRegistryPath\(caseId, buildId\)/);
  assert.match(studio, /value\.build_id !== buildId/);
  assert.match(studio, /value\.defaults\.find\(\(row\) => row\.case === "BASE" && row\.status === "READY"\)/);
  assert.match(studio, /<select id="scenario-period"/);
  assert.doesNotMatch(studio, /<input id="scenario-period"/);
  assert.doesNotMatch(studio, /FY2025/);
  assert.match(studio, /Scenario registry unavailable/);
});

test("every lifecycle mutation shares one scope generation and in-flight gate", () => {
  assert.match(studio, /type LifecycleToken/);
  assert.match(studio, /const lifecycleGeneration = useRef\(0\)/);
  assert.match(studio, /const lifecycleInFlight = useRef\(false\)/);
  assert.match(studio, /beginLifecycle/);
  assert.match(studio, /lifecycleIsCurrent/);
  assert.match(studio, /invalidateLifecycle/);
  assert.match(studio, /const lifecycleBusy = pending !== ""/);
  assert.match(studio, /disabled=\{[^}]*lifecycleBusy[^}]*\}/);
  assert.doesNotMatch(studio, /await load\(\);\s*setSelectedFrozen/);
});

test("one lifecycle lock disables every draft-mutating authoring control", () => {
  assert.match(studio, /const authoringLocked = lifecycleBusy/);
  assert.match(studio, /narrative-\$\{selectedNarrative\.block_id\}[\s\S]*?disabled=\{!canWrite \|\| authoringLocked\}/);
  assert.match(studio, /name=\{`mode-\$\{selectedNarrative\.block_id\}`\}[\s\S]*?disabled=\{!canWrite \|\| authoringLocked\}/);
  assert.match(studio, /name="report-model"[\s\S]*?disabled=\{!canWrite \|\| authoringLocked\}/);
  assert.match(studio, /disabled=\{[^}]*authoringLocked[^}]*\}>Add \{humanizeCode\(policy\.kind\)\.toLowerCase\(\)\}/);
  assert.match(studio, /disabled=\{[^}]*authoringLocked[^}]*\}>Omit block/);
  assert.match(studio, /disabled=\{[^}]*authoringLocked[^}]*\}>Remove citation/);
  assert.match(studio, /disabled=\{[^}]*authoringLocked[^}]*\}>Cite block/);
  for (const id of ["scenario-assumption", "scenario-case", "scenario-period", "scenario-value"]) {
    assert.match(studio, new RegExp(`id="${id}"[\\s\\S]{0,500}?disabled=\\{authoringLocked\\}`));
  }
  assert.match(studio, /disabled=\{authoringLocked\}>Retry over current v\{conflict\.version\}/);
  assert.match(studio, /disabled=\{authoringLocked\}>Use shared v\{conflict\.version\}/);
  assert.match(studio, /disabled=\{lifecycleBusy\}>\{pending === "file"/);
  assert.match(studio, /disabled=\{!changeComment\.trim\(\) \|\| lifecycleBusy\}/);
  assert.match(studio, /disabled=\{!canWrite \|\| lifecycleBusy \|\| draftIsUnsaved/);
});

test("Draft and Frozen review render the same canonical governed document", () => {
  assert.match(studio, /payload: FrozenPayload/);
  assert.match(studio, /document_schema_version\?: string/);
  assert.match(studio, /document_sections\?: DocumentSection\[\]/);
  assert.match(studio, /selectedFrozen\.payload\.content\.document_sections/);
  assert.match(studio, /: overlayAnalystText\(savedSections, blocks\)/);
  assert.match(studio, /sections=\{previewSections\}/);
  assert.match(document, /groupDocumentPages\(sections\)/);
  assert.doesNotMatch(document, /FrozenEnvelope|flatten\(|application_build/);
});

test("browser proof carries the signed model into the canonical report and downloads the filed memo", () => {
  assert.match(smoke, /document_schema_version: "caos\.deliverable\.document\.v1"/);
  assert.match(smoke, /revision_id: signedReportRevision\.id/);
  assert.match(smoke, /document_sections: reportDocumentSections/);
  assert.match(smoke, /waitForEvent\("download"\)/);
});

test("paper columns collapse at the paper boundary before text is crushed", () => {
  assert.match(styles, /\.report-paper \{[^}]*container-type: inline-size/);
  assert.match(styles, /@container \(max-width: 660px\)[\s\S]*?\.rd-cols-2[\s\S]*?grid-template-columns: 1fr/);
});

test("Workspace owns and retires at most one shared draft-history sentinel", () => {
  assert.match(workspace, /historyTraversalRef/);
  assert.match(workspace, /retireOwnedHistoryGuard/);
  assert.match(workspace, /if \(!modelHistoryGuardRef\.current\)/);
  assert.equal(workspace.match(/if \(!modelDraftDirtyRef\.current && !reportDraftDirtyRef\.current\) releaseCleanDraftGuard\(\)/g)?.length, 2);
  assert.match(workspace, /from !== null && window\.location\.href !== from/);
});

test("every optional-block insertion re-sorts into template order", () => {
  // The server refuses out-of-order optional blocks (DELIVERABLE_TEMPLATE_ORDER_INVALID),
  // so appending a scenario (order 4) after a limitations block (order 6) built a draft
  // that could never be saved. Both insertion sites must go through the comparator.
  assert.match(studio, /const inTemplateOrder =/);
  const appends = studio.match(/markChanged\(\s*\[\.\.\.blocks,/g) ?? [];
  assert.equal(appends.length, 0, "an insertion appends without re-sorting into template order");
  assert.equal((studio.match(/inTemplateOrder\(\[\.\.\.blocks,/g) ?? []).length, 2);
});
