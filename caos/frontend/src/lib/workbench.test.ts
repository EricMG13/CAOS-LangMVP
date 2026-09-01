import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { acceptedAuthorityMatch, destinationMeta, evidenceKind, formatBlockLocator, humanizeCode, moduleLabel, withQuery, workflows } from "./workbench.ts";

const workbenchShell = readFileSync(new URL("../components/WorkbenchShell.tsx", import.meta.url), "utf8");

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

test("acceptance aftermath binds to the matching snapshot id", () => {
  assert.equal(acceptedAuthorityMatch("snap_a", "", "snap_a"), "snap_a", "the served run field matches the authority");
  assert.equal(acceptedAuthorityMatch(null, "snap_a", "snap_a"), "snap_a", "the locally returned snapshot covers a server without the run field");
  assert.equal(acceptedAuthorityMatch("snap_a", "snap_b", "snap_a"), "snap_a", "the served run field wins over local state");
  assert.equal(acceptedAuthorityMatch("snap_a", "snap_b", "snap_b"), "", "local state never overrides a served mismatch");
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
