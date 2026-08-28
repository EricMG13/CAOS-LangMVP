import test from "node:test";
import assert from "node:assert/strict";
import { acceptedAuthorityMatch, withQuery } from "./workbench.ts";

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

test("acceptance aftermath binds to the matching snapshot id", () => {
  assert.equal(acceptedAuthorityMatch("snap_a", "", "snap_a"), "snap_a", "the served run field matches the authority");
  assert.equal(acceptedAuthorityMatch(null, "snap_a", "snap_a"), "snap_a", "the locally returned snapshot covers a server without the run field");
  assert.equal(acceptedAuthorityMatch("snap_a", "snap_b", "snap_a"), "snap_a", "the served run field wins over local state");
  assert.equal(acceptedAuthorityMatch("snap_a", "snap_b", "snap_b"), "", "local state never overrides a served mismatch");
});
