import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";
import { initialAuthorityState, matchesAuthority, requestContext, workspaceAuthorityReducer } from "../src/lib/workspaceAuthority.ts";

// Execute the actual handler with the actual authority reducer; control only IO
// and React setters so successful and overlapping requests can be interleaved.
const source = ts.createSourceFile("Workspace.tsx", readFileSync(new URL("../src/components/Workspace.tsx", import.meta.url), "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
let handler;
function visit(node) {
  if (ts.isVariableDeclaration(node) && node.name.getText(source) === "submitIntake") handler = node.initializer.getText(source);
  ts.forEachChild(node, visit);
}
visit(source);
assert.ok(handler);
const compiled = ts.transpileModule(`(${handler})`, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;

function harness() {
  const state = { pending: "", authority: workspaceAuthorityReducer(initialAuthorityState, { type: "hydrate", caseId: "case-a", runId: "run-old" }) };
  const authorityRef = { get current() { return state.authority; } };
  const requests = [];
  const noop = () => {};
  const submit = runInNewContext(compiled, {
    FormData, requestContext, matchesAuthority, authorityRef,
    intakeRequest: { current: 0 }, casesRequest: { current: 0 },
    request: () => { const deferred = Promise.withResolvers(); requests.push(deferred); return deferred.promise; },
    setPendingAction: (value) => { state.pending = typeof value === "function" ? value(state.pending) : value; },
    dispatchAuthority: (event) => { state.authority = workspaceAuthorityReducer(state.authority, event); },
    setError: noop, setNotice: noop, setIntakeRefusal: noop, setCases: noop, setRun: noop, setIntake: noop,
    humanizeCode: (value) => value, ApiRequestError: Error, isIntakeRefusal: () => false, firstErrorMessage: () => "Failed",
    commitCaseSelection: () => { throw new Error("These requests must retain their case"); },
  });
  const response = (runId) => ({ case_id: "case-a", case: { id: "case-a" }, run: { id: runId, case_id: "case-a" }, documents: [{}], status: "started", route: { pathway: "FULL_CREDIT", depth: "full" } });
  return { state, requests, submit: () => submit([new File(["evidence"], "annual.txt")], "case-a"), response };
}

test("successful same-case intake clears busy before selecting its new run", async () => {
  const h = harness();
  const submitted = h.submit();
  assert.equal(h.state.pending, "intake");
  h.requests[0].resolve(h.response("run-new"));
  await submitted;
  assert.equal(h.state.authority.runId, "run-new");
  assert.equal(h.state.pending, "");
});

for (const outcome of ["success", "failure"]) test(`stale intake ${outcome} cannot clear a newer request's busy state`, async () => {
  const h = harness();
  const first = h.submit();
  const second = h.submit();
  if (outcome === "success") h.requests[0].resolve(h.response("run-stale"));
  else h.requests[0].reject(new Error("failed"));
  await first;
  assert.equal(h.state.pending, "intake");
  assert.equal(h.state.authority.runId, "run-old");
  h.requests[1].resolve(h.response("run-current"));
  await second;
  assert.equal(h.state.pending, "");
  assert.equal(h.state.authority.runId, "run-current");
});
