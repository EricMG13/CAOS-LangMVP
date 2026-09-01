import assert from "node:assert/strict";
import test from "node:test";

import { freezeChecklist } from "./reportStudioState.ts";

const ready = {
  canWrite: true,
  exactSavedRevision: true,
  currentModelSelection: true,
  requiredModelAvailable: true,
};

test("freeze checklist is ready only when every prerequisite is satisfied", () => {
  assert.deepEqual(freezeChecklist(ready), [
    { id: "write-access", label: "Write access", ready: true },
    { id: "saved-revision", label: "Exact saved revision", ready: true },
    { id: "model-selection", label: "Current model selection", ready: true },
    { id: "model-availability", label: "Required model availability", ready: true },
  ]);
});

for (const [field, blockedId] of [
  ["canWrite", "write-access"],
  ["exactSavedRevision", "saved-revision"],
  ["currentModelSelection", "model-selection"],
  ["requiredModelAvailable", "model-availability"],
] as const) {
  test(`freeze checklist exposes the ${blockedId} blocker`, () => {
    const checklist = freezeChecklist({ ...ready, [field]: false });
    assert.deepEqual(checklist.filter((item) => !item.ready).map((item) => item.id), [blockedId]);
  });
}
