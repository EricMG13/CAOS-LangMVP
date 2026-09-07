import assert from "node:assert/strict";
import test from "node:test";

import { canFileFrozen, freezeChecklist, freezeJobIsPending, reportEvidenceRefs } from "./reportStudioState.ts";

test("report source links merge claims without inventing cross-source block pairs", () => {
  assert.deepEqual(reportEvidenceRefs([
    { source_id: "source-a", block_ids: ["b1"] },
    { source_id: "source-a", block_ids: ["b1", "b2"] },
    { source_id: "source-b", block_ids: ["b3"] },
  ]), [{ sourceId: "source-a", blockIds: ["b1", "b2"] }, { sourceId: "source-b", blockIds: ["b3"] }]);
});

const ready = {
  canWrite: true,
  exactSavedRevision: true,
  currentModelSelection: true,
  requiredModelAvailable: true,
  currentOpinion: true,
};

test("freeze checklist is ready only when every prerequisite is satisfied", () => {
  assert.deepEqual(freezeChecklist(ready), [
    { id: "write-access", label: "Write access", ready: true },
    { id: "saved-revision", label: "Exact saved revision", ready: true },
    { id: "model-selection", label: "Current model selection", ready: true },
    { id: "model-availability", label: "Required model availability", ready: true },
    { id: "opinion-signoff", label: "Current opinion sign-off", ready: true },
  ]);
});

for (const [field, blockedId] of [
  ["canWrite", "write-access"],
  ["exactSavedRevision", "saved-revision"],
  ["currentModelSelection", "model-selection"],
  ["requiredModelAvailable", "model-availability"],
  ["currentOpinion", "opinion-signoff"],
] as const) {
  test(`freeze checklist exposes the ${blockedId} blocker`, () => {
    const checklist = freezeChecklist({ ...ready, [field]: false });
    assert.deepEqual(checklist.filter((item) => !item.ready).map((item) => item.id), [blockedId]);
  });
}

test("freeze polling continues only while the worker owes a render", () => {
  assert.equal(freezeJobIsPending("QUEUED"), true);
  assert.equal(freezeJobIsPending("RENDERING"), true);
  assert.equal(freezeJobIsPending("PUBLISHED"), false);
  assert.equal(freezeJobIsPending("FAILED"), false);
});

test("filing requires both current writer identity and stored approver standing, then independence", () => {
  const frozen = { signed_by: "signer", frozen_by: "freezer" };
  for (const role of ["ANALYST", "APPROVER", "ADMIN"]) {
    for (const standing of ["APPROVER", "ADMIN"]) assert.equal(canFileFrozen(role, "independent", frozen, { independent: standing }), true);
    for (const standing of ["READER", "ANALYST"]) assert.equal(canFileFrozen(role, "independent", frozen, { independent: standing }), false);
    assert.equal(canFileFrozen(role, "independent", frozen), false);
    for (const subject of ["signer", "freezer"]) assert.equal(canFileFrozen(role, subject, frozen, { [subject]: "APPROVER" }), false);
  }
  assert.equal(canFileFrozen("READER", "independent", frozen, { independent: "APPROVER" }), false);
  assert.equal(canFileFrozen("APPROVER", "", frozen, { "": "APPROVER" }), false);
});
