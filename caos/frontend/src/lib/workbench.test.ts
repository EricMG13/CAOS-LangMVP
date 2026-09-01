import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { acceptanceSlotSummary, acceptedAuthorityMatch, destinationMeta, evidenceKind, formatBlockLocator, humanizeCode, moduleLabel, withQuery, workflows } from "./workbench.ts";

const workbenchShell = readFileSync(new URL("../components/WorkbenchShell.tsx", import.meta.url), "utf8");
const workspace = readFileSync(new URL("../components/Workspace.tsx", import.meta.url), "utf8");
const states = readFileSync(new URL("../components/states.tsx", import.meta.url), "utf8");
const modelBuilder = readFileSync(new URL("../components/model/ModelBuilder.tsx", import.meta.url), "utf8");
const deliverableDocument = readFileSync(new URL("../components/report/DeliverableDocument.tsx", import.meta.url), "utf8");
const reportStudio = readFileSync(new URL("../components/report/ReportStudio.tsx", import.meta.url), "utf8");
const styles = readFileSync(new URL("../../app/globals.css", import.meta.url), "utf8");
const smoke = readFileSync(new URL("../../scripts/workbench-smoke.mjs", import.meta.url), "utf8");

test("approved workspace labels preserve the existing routes", () => {
  assert.deepEqual(workflows.map(({ label, href }) => [label, href]), [
    ["Portfolio", "/cases"],
    ["Credit", "/command-center"],
    ["Sources", "/sources"],
    ["Analysis", "/deep-dive"],
    ["Market", "/rv-screener"],
    ["Model", "/model-builder"],
    ["Report", "/report-studio"],
  ]);
});

test("the shell omits the redundant reading taxonomy and renders its command shortcut as a key", () => {
  assert.ok(Object.values(destinationMeta).every((meta) => !("reading" in meta)));
  assert.doesNotMatch(workbenchShell, /Reading:/);
  assert.match(workbenchShell, /Command <kbd aria-hidden="true">⌘K<\/kbd>/);
});

test("navigation and data captions use the four-role label taxonomy", () => {
  assert.equal(workbenchShell.match(/className="nav-label palette-group-label"/g)?.length, 3);
  assert.doesNotMatch(styles, /\.palette-group-label\s*\{[^}]*text-transform/);
  assert.match(workbenchShell, /<dt className="meta-label">Source ID<\/dt>/);
  assert.doesNotMatch(styles, /\.state-block dt\s*\{/);
  assert.match(reportStudio, /report-authority-strip"><div><span className="meta-label">Model authority<\/span>/);
  assert.doesNotMatch(styles, /\.report-authority-strip div > span\s*\{/);
  assert.match(workspace, /analysis-provenance"><dt className="meta-label">Artifact<\/dt>/);
  assert.match(workspace, /loan-authority"><dl><dt className="meta-label">Workbook date<\/dt>/);
  assert.doesNotMatch(styles, /[^{}]*\bdt\b[^{}]*\{[^{}]*(?:letter-spacing|text-transform)/);
});

test("Cases makes opening the selected credit primary and keeps portfolio limits secondary", () => {
  const register = workspace.slice(workspace.indexOf('className="panel cases-register"'), workspace.indexOf('className="panel cases-create"'));
  assert.match(register, /<tr aria-current=\{caseId === item\.id \? "true" : undefined\}/);
  assert.match(register, /className="button small primary"[^>]*>Open credit/);
  assert.match(register, /className="button primary"[^>]*>Reset filters/);
  assert.ok(workspace.indexOf('id="portfolio-contract-title"') > workspace.indexOf('className="panel cases-fit"'), "portfolio limitation did not follow the primary work");
});

test("RV keeps core filters visible and discloses retained advanced bounds", () => {
  const screener = workspace.slice(workspace.indexOf('className="panel span-12"><div className="panel-header"><h2>Loan screener'));
  const advanced = screener.slice(screener.indexOf('<details className="loan-advanced-filters">'), screener.indexOf('</details>'));
  for (const id of ["loan-maturity-from", "loan-maturity-to", "loan-margin-min", "loan-margin-max", "loan-dm-min", "loan-dm-max"]) assert.match(advanced, new RegExp(id));
  assert.match(screener, /<caption className="sr-only">27 columns\. Scroll horizontally to review all workbook fields; column labels state source units\.<\/caption>/);
});

test("draft navigation uses one focus-returning native dialog and preserves beforeunload", () => {
  assert.doesNotMatch(workspace, /window\.confirm/);
  assert.doesNotMatch(reportStudio, /window\.confirm/);
  assert.match(workspace, /function DraftDiscardDialog/);
  assert.match(workspace, /<dialog[^>]+aria-labelledby="discard-dialog-title"[^>]+onClose=\{close\}/);
  assert.match(workspace, /window\.addEventListener\("beforeunload", guardUnload\)/);
  assert.match(workspace, /requestDraftDiscard/);
  assert.match(workspace, /if \(discardPromptRef\.current\) \{ cancel\?\.\(\); return false; \}/);
  assert.match(workspace, /if \(state\?\.caosModelDraftGuard \|\| state\?\.caosReportDraftGuard\) \{ modelHistoryGuardRef\.current = true; return; \}/);
  const finish = workspace.slice(workspace.indexOf("const finishDraftDiscard"), workspace.indexOf("const commitCaseSelection"));
  assert.doesNotMatch(finish, /(?:model|report)DraftDirtyRef\.current = false|modelHistoryGuardRef\.current = false/);
  assert.match(reportStudio, /useEffect\(\(\) => \(\) => onDraftStateChange\(false\), \[onDraftStateChange\]\)/);
  assert.match(workbenchShell, /document\.querySelector\("dialog\[open\]"\)/);
  for (const proof of ["modified dirty link was intercepted", "dirty same-route confirmation dropped protection", "command shortcut opened a nested modal", "dirty pathway cancel changed pathway", "dirty pathway confirm did not change pathway", "confirming browser history did not traverse exactly one boundary"]) assert.match(smoke, new RegExp(proof));
});

test("draft link interception accepts only an unmodified primary same-tab gesture", async () => {
  const workbenchModule = await import("./workbench.ts") as unknown as { isSameTabPrimaryGesture?: (event: { button: number; metaKey: boolean; ctrlKey: boolean; shiftKey: boolean; altKey: boolean }, target?: string) => boolean };
  assert.equal(typeof workbenchModule.isSameTabPrimaryGesture, "function");
  const gesture = { button: 0, metaKey: false, ctrlKey: false, shiftKey: false, altKey: false };
  assert.equal(workbenchModule.isSameTabPrimaryGesture?.(gesture), true);
  for (const change of [
    { button: 1 },
    { metaKey: true },
    { ctrlKey: true },
    { shiftKey: true },
    { altKey: true },
  ]) assert.equal(workbenchModule.isSameTabPrimaryGesture?.({ ...gesture, ...change }), false, JSON.stringify(change));
  assert.equal(workbenchModule.isSameTabPrimaryGesture?.(gesture, "_blank"), false);
  assert.equal(workbenchModule.isSameTabPrimaryGesture?.(gesture, "_self"), true);
  assert.equal(workbenchModule.isSameTabPrimaryGesture?.(gesture, "_SELF"), true);
});

test("discard resolution invokes one deferred callback without changing caller-owned protection", async () => {
  const workbenchModule = await import("./workbench.ts") as unknown as { resolveDraftDiscard?: (request: { confirm: () => void; cancel?: () => void }, confirmed: boolean) => void };
  assert.equal(typeof workbenchModule.resolveDraftDiscard, "function");
  const protectedDraft = true;
  let confirms = 0;
  let cancels = 0;
  const request = { confirm: () => { confirms += 1; }, cancel: () => { cancels += 1; } };
  workbenchModule.resolveDraftDiscard?.(request, true);
  assert.deepEqual({ protectedDraft, confirms, cancels }, { protectedDraft: true, confirms: 1, cancels: 0 });
  workbenchModule.resolveDraftDiscard?.(request, false);
  assert.deepEqual({ protectedDraft, confirms, cancels }, { protectedDraft: true, confirms: 1, cancels: 1 });
});

test("Workspace settles history moves only at their tagged destination entry", () => {
  assert.match(workspace, /historyTraversalRef/);
  assert.match(workspace, /beginDraftHistoryTraversal/);
  assert.match(workspace, /observeDraftHistoryPop\(activeTraversal, event\.state\)/);
  assert.match(workspace, /draftHistoryEntryId\(window\.history\.state\) !== activeTraversal\.expectedDestinationId/);
  assert.match(workspace, /caosDraftHistorySentinelId/);
  assert.match(workspace, /protectDirtyDraftUnload\(event, modelDraftDirtyRef\.current \|\| reportDraftDirtyRef\.current\)/);
  assert.doesNotMatch(workspace, /isConfirmedDraftHistoryTraversal/);
  assert.doesNotMatch(workspace, /historyGuardRetiringRef|historyGuardRearmRef|suppressNextModelHistoryPopRef|confirmedHistoryPopRef/);
});

test("DAG nodes use neutral containers and shape-coded visible statuses", async () => {
  const workbench = await import("./workbench.ts") as unknown as { nodeStatusTone?: (status: string) => string };
  for (const [status, tone] of [
    ["pending", "idle"],
    ["ready", "idle"],
    ["running", "running"],
    ["blocked", "warning"],
    ["cancelled", "warning"],
    ["failed", "critical"],
    ["succeeded", "success"],
  ]) assert.equal(workbench.nodeStatusTone?.(status), tone, status);
  assert.doesNotMatch(styles, /\.dag-node\.(?:succeeded|running|failed)\s*\{/);
  assert.doesNotMatch(workspace, /className=\{`dag-node \$\{node\.status\}`\}/);
  assert.match(workspace, /className=\{`status \$\{nodeStatusTone\(node\.status\)\}`\}>\{node\.status\}<\/div>/);
  assert.match(workspace, /dag-node-open dag-node-placeholder" aria-hidden="true">Open output/, "unfinished DAG nodes must reserve the completed-output row");
  assert.match(styles, /\.status\.running::before\s*\{/);
});

test("every route path keeps its trailing slash", () => {
  assert.equal(withQuery("/run-console", { case: "case_1" }), "/run-console/?case=case_1");
  assert.equal(withQuery("/sources/", { case: "case_1" }), "/sources/?case=case_1");
  assert.equal(withQuery("/cases", {}), "/cases/");
  assert.equal(withQuery("/", {}), "/");
});

test("values set, replace, and clear query keys", () => {
  assert.equal(withQuery("/run-console?run=run_old", { run: "run_new" }), "/run-console/?run=run_new");
  assert.equal(withQuery("/run-console?run=run_old", { run: undefined }), "/run-console/");
  assert.equal(withQuery("/run-console?case=case_1", { run: "run_1" }), "/run-console/?case=case_1&run=run_1");
});

test("acceptance stays live until the run's snapshot is the case authority", () => {
  assert.equal(acceptedAuthorityMatch(null, "", "snap_a"), "", "an unaccepted run offers the action");
  assert.equal(acceptedAuthorityMatch(undefined, undefined, undefined), "", "no authority, no aftermath");
  assert.equal(acceptedAuthorityMatch("snap_a", "", null), "", "authority not yet loaded keeps the action live");
  assert.equal(acceptedAuthorityMatch("snap_a", "", "snap_b"), "", "a different accepted authority keeps the action live");
});

test("a positional block locator reads as English and every other shape keeps its JSON", () => {
  assert.equal(formatBlockLocator({ line: 4 }), "line 4");
  assert.equal(formatBlockLocator({ LINE: 4 }), "line 4");
  assert.equal(formatBlockLocator({ page: 12 }), "page 12");
  assert.equal(formatBlockLocator({ PAGE: "12" }), "page 12");
  // builtin-v2 groups lines once a document is large, which is every real filing.
  assert.equal(formatBlockLocator({ lines: [1, 95] }), "lines 1\u201395");
  assert.equal(formatBlockLocator({ LINES: ["96", "179"] }), "lines 96\u2013179");
  assert.equal(formatBlockLocator({ lines: [7, 7] }), "line 7");
  assert.equal(formatBlockLocator({ pages: [2, 5] }), "pages 2\u20135");
  // A range that is not a well-formed pair keeps its JSON rather than inventing one.
  assert.equal(formatBlockLocator({ lines: [1] }), '{"lines":[1]}');
  assert.equal(formatBlockLocator({ lines: [1, 2, 3] }), '{"lines":[1,2,3]}');
  assert.equal(formatBlockLocator({ lines: [1, null] }), '{"lines":[1,null]}');
  // Unknown shapes are shown exactly as they were before, never dropped.
  assert.equal(formatBlockLocator({ sheet: "Summary", row: 4 }), '{"sheet":"Summary","row":4}');
  assert.equal(formatBlockLocator({ offset: 4 }), '{"offset":4}');
  assert.equal(formatBlockLocator({ line: null }), '{"line":null}');
  assert.equal(formatBlockLocator({ line: "" }), '{"line":""}');
  assert.equal(formatBlockLocator([{ line: 4 }]), '[{"line":4}]');
  assert.equal(formatBlockLocator({}), "{}");
  assert.equal(formatBlockLocator(undefined), "");
});

test("module ids carry their registry name, and an unknown id stays the id", () => {
  assert.equal(moduleLabel("CP-1"), "Canonical Data Foundation");
  assert.equal(moduleLabel("CP-2A"), "Downside Pathway");
  assert.equal(moduleLabel("CP-L10"), "Financial Change Screen");
  // No registry slug, or not a registry module: never a name this client invented.
  assert.equal(moduleLabel("CP-PARSE"), "CP-PARSE");
  assert.equal(moduleLabel("CP-MODEL"), "CP-MODEL");
  assert.equal(moduleLabel("CP-DR"), "CP-DR");
  // Superseded ids are not aliased onto their absorbers.
  assert.equal(moduleLabel("CP-2B"), "CP-2B");
});

test("a server code is never presented as a raw identifier", () => {
  assert.equal(humanizeCode("MODEL_EXPORT_FAILED"), "MODEL EXPORT FAILED");
  assert.equal(humanizeCode("PAUSED"), "PAUSED");
});

test("workspace identities compact only beyond the exact display threshold", async () => {
  const workbench = await import("./workbench.ts") as unknown as {
    compactIdentity?: (value: string, leading?: number, trailing?: number) => string;
  };
  assert.equal(typeof workbench.compactIdentity, "function");
  assert.equal(workbench.compactIdentity?.(""), "");
  assert.equal(workbench.compactIdentity?.("short-id"), "short-id");
  assert.equal(workbench.compactIdentity?.("1234567890123456"), "1234567890123456");
  assert.equal(workbench.compactIdentity?.("0123456789abcdef0123456789abcdef"), "0123456789ab…cdef");
  assert.equal(workbench.compactIdentity?.("model-version-identity", 5, 3), "model…ity");
});

test("the identity presenter retains exact pointer text and stays scoped to display values", () => {
  assert.match(states, /export function IdentityValue/);
  assert.match(states, /title=\{value\}/);
  assert.match(workbenchShell, /visibleSnapshotId \? <IdentityValue value=\{visibleSnapshotId\}/);
  assert.doesNotMatch(workbenchShell, /<IdentityValue value=\{visibleSnapshotIdentity\}/);
  assert.match(workspace, /<IdentityValue value=\{selectedSource\.sha256\}/);
  assert.match(workspace, /<IdentityValue value=\{selectedArtifact\.digest\}/);
  assert.match(modelBuilder, /<IdentityValue value=\{revision\.id\}/);
  assert.doesNotMatch(modelBuilder, /<IdentityValue[^>]*(?:Recalculation required|Application version)/);
  assert.match(deliverableDocument, /Exact identity · \{digest\}/, "governed paper keeps its exact identity");
  assert.match(styles, /\.rd-identity\s*\{[^}]*overflow-wrap:\s*anywhere;[^}]*word-break:/);
});

test("command center selects a credit conclusion before preparation output", async () => {
  const workbench = await import("./workbench.ts") as unknown as {
    selectConclusionArtifact?: <T extends { module_id: string }>(artifacts: readonly T[]) => T | null;
  };
  assert.equal(typeof workbench.selectConclusionArtifact, "function");
  const preparation = { module_id: "CP-PARSE", payload: { summary: "Sources prepared" } };
  const readiness = { module_id: "CP-0", payload: { summary: "Ready" } };
  const credit = { module_id: "CP-1", payload: { narrative: { takeaway: "Credit conclusion" } } };
  const synthesis = { module_id: "CP-2", payload: { summary: "Preferred synthesis" } };
  assert.equal(workbench.selectConclusionArtifact?.([preparation, readiness, credit]), credit);
  assert.equal(workbench.selectConclusionArtifact?.([credit, synthesis]), synthesis);
  assert.equal(workbench.selectConclusionArtifact?.([readiness, preparation]), preparation);
});

test("command center renders the served snapshot diff shape honestly", () => {
  const commandView = workspace.slice(workspace.indexOf("function CommandView("), workspace.indexOf("function AdminView("));
  assert.match(commandView, /useState<SnapshotView \| null>/);
  assert.match(commandView, /selectConclusionArtifact\(artifacts\)/);
  assert.match(commandView, /diff\.modified(?:\?\.|\.)map\(\(item\)[\s\S]*?<IdentityValue value=\{item\.digest\}/);
  assert.doesNotMatch(commandView, /item\.(?:before|after)/);
  assert.doesNotMatch(workspace, /slice\(0,\s*12\)/);
});

test("acceptance aftermath binds to the matching snapshot id", () => {
  assert.equal(acceptedAuthorityMatch("snap_a", "", "snap_a"), "snap_a", "the served run field matches the authority");
  assert.equal(acceptedAuthorityMatch(null, "snap_a", "snap_a"), "snap_a", "the locally returned snapshot covers a server without the run field");
  assert.equal(acceptedAuthorityMatch("snap_a", "snap_b", "snap_a"), "snap_a", "the served run field wins over local state");
  assert.equal(acceptedAuthorityMatch("snap_a", "snap_b", "snap_b"), "", "local state never overrides a served mismatch");
});

test("acceptance replacement and aftermath use the latest accepted authority", () => {
  assert.match(workspace, /authority\?\.latest_accepted\?\.id/);
  assert.match(workspace, /replaces=\{authority\?\.latest_accepted \?\? null\}/);
  assert.doesNotMatch(workspace, /replaces=\{authority\?\.accepted \?\? null\}/);
});

test("a switch-required accepted run stays accepted while the visible lens is disclosed separately", () => {
  const visibleSnapshotId = "snap_visible";
  const latestAcceptedId = "snap_latest";
  assert.equal(acceptedAuthorityMatch(latestAcceptedId, "", latestAcceptedId), latestAcceptedId);
  assert.equal(acceptedAuthorityMatch(latestAcceptedId, "", visibleSnapshotId), "", "the visible lens is not the acceptance ledger");
  assert.match(workspace, /switchRequired=\{authority\?\.switch_required === true\}/);
  const acceptedBranch = workspace.slice(workspace.indexOf("if (acceptedSnapshotId)"), workspace.indexOf("else if (run.status === \"succeeded\")"));
  assert.match(acceptedBranch, /Latest accepted authority/);
  assert.match(acceptedBranch, /Visible lens remains/);
  assert.doesNotMatch(acceptedBranch, /Ready for acceptance|Accept analytical snapshot/);
});

test("the shell names the visible lens instead of conflating it with latest acceptance", () => {
  assert.match(workbenchShell, /<b>Visible snapshot:<\/b>/);
  assert.doesNotMatch(workbenchShell, /<b>Accepted:<\/b>/);
});

test("the browser geometry fixture covers every acceptance-region state", () => {
  assert.match(smoke, /\["queued", "running", "succeeded", "accepted", "failed", "paused"\]/);
  assert.match(smoke, /accepted_snapshot_id: acceptanceRunPhase === "accepted" \? acceptanceSnapshot\.id : null/);
  for (const state of ["Accepted", "Acceptance blocked", "Ready for acceptance", "Acceptance waiting"]) {
    assert.match(smoke, new RegExp(state));
  }
});

test("failed and paused runs never announce a pending module as current progress", () => {
  const runStatus = workspace.slice(workspace.indexOf("function RunStatus("), workspace.indexOf("function RunConsole("));
  assert.match(runStatus, /const current = \(run\.status === "queued" \|\| run\.status === "running"\)[\s\S]*?\? run\.nodes\.find\(\(node\) => node\.status === "running"\) \|\| run\.nodes\.find\(\(node\) => node\.status === "pending"\)[\s\S]*?: undefined;/);
  assert.match(runStatus, /run\.status === "failed" \? "Execution stopped" : "Execution paused"/);
  assert.match(runStatus, /aria-valuetext=\{`\$\{complete\} of \$\{run\.nodes\.length\} modules complete\$\{current \?/);
});

test("acceptance review classifies authority slots without claiming artifact byte changes", () => {
  const summary = acceptanceSlotSummary(
    [{ module_id: "CP-0" }, { module_id: "CP-1" }, { module_id: "CP-5" }, { module_id: "CP-5" }],
    [{ module_id: "CP-0" }, { module_id: "CP-2" }, { module_id: "CP-5" }],
  );

  assert.deepEqual(summary, {
    added: ["CP-1"],
    replaced: ["CP-0", "CP-5"],
    removed: ["CP-2"],
  });
  assert.doesNotMatch(workspace, /v\{(?:run\.plan|replaces)\.source_set_version \?\? "Unavailable"\}/, "missing versions must not render as vUnavailable");
});

test("an evidence id resolves whatever this store minted", () => {
  assert.equal(evidenceKind("src-6b1f2a"), "source");
  assert.equal(evidenceKind("art-6b1f2a"), "artifact");
  // A promoted analyst note is `src-note-<hex>`: the tail is itself hyphenated.
  assert.equal(evidenceKind("src-note-6b1f2a"), "source");
  assert.equal(evidenceKind("  src_6b1f2a  "), "source", "the legacy underscore form still resolves");
  assert.equal(evidenceKind("case-6b1f2a"), null);
  assert.equal(evidenceKind("src-"), null);
});
