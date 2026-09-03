import assert from "node:assert/strict";
import test from "node:test";

import { canFileFrozen, freezeChecklist, freezeJobIsPending } from "./reportStudioState.ts";

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

test("the opinion signer and the freeze actor never see a File control for their own output", () => {
  const frozen = { signed_by: "signer", frozen_by: "freezer" };
  assert.equal(canFileFrozen("APPROVER", "independent", frozen), true);
  assert.equal(canFileFrozen("ADMIN", "independent", frozen), true);
  assert.equal(canFileFrozen("APPROVER", "signer", frozen), false);
  assert.equal(canFileFrozen("APPROVER", "freezer", frozen), false);
  assert.equal(canFileFrozen("ANALYST", "independent", frozen), false);
  assert.equal(canFileFrozen("APPROVER", "", frozen), false, "an unresolved identity never files");
});
