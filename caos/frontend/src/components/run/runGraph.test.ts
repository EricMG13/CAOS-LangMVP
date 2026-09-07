import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runEdgePath, runGraph } from "./runGraph.ts";

test("siblings are not displayed as dependencies", () => {
  const result = runGraph([
    { module_id: "A", stage: 0, dependencies: [] },
    { module_id: "B", stage: 1, dependencies: ["A"] },
    { module_id: "C", stage: 1, dependencies: ["A"] },
    { module_id: "D", stage: 2, dependencies: ["B", "C"] },
  ]);
  assert.deepEqual(result.edges, [["A", "B"], ["A", "C"], ["B", "D"], ["C", "D"]]);
  assert.deepEqual(result.stages.map(([stage, nodes]) => [stage, nodes.map((node) => node.module_id)]), [
    [0, ["A"]],
    [1, ["B", "C"]],
    [2, ["D"]],
  ]);
});

test("an edge that skips an intervening stage uses a reserved lane", () => {
  const path = runEdgePath({ x: 208, y: 90 }, { x: 528, y: 90 }, 2, 12);
  assert.equal(path, "M 208 90 H 220 V 12 H 516 V 90 H 528");
  assert.equal(path.match(/ V /g)?.length, 2, "the route leaves and re-enters the node field vertically");
  assert.match(runEdgePath({ x: 208, y: 90 }, { x: 264, y: 182 }, 1, 0), /^M 208 90 C /);
});

test("invalid served graphs fail closed", () => {
  for (const nodes of [
    [{ module_id: "A", stage: 0, dependencies: [] }, { module_id: "A", stage: 1, dependencies: [] }],
    [{ module_id: "A", stage: -1, dependencies: [] }],
    [{ module_id: "A", stage: 0.5, dependencies: [] }],
    [{ module_id: "A", stage: 0, dependencies: ["missing"] }],
    [{ module_id: "A", stage: 0, dependencies: ["A"] }],
  ]) assert.throws(() => runGraph(nodes), { message: "RUN_GRAPH_INVALID" });
});

test("the presentational boundary keeps an accessible served-node fallback and exact status vocabulary", () => {
  const component = readFileSync(new URL("./RunGraphView.tsx", import.meta.url), "utf8");
  assert.match(component, /try\s*\{[\s\S]*runGraph\(run\.nodes\)[\s\S]*catch/);
  assert.match(component, /Dependency graph unavailable/);
  assert.match(component, /<ol[\s\S]*run\.nodes\.map/);
  assert.match(component, /Upstream (?:inputs|dependencies)/);
  assert.match(component, /Array\.isArray\(node\.dependencies\)/, "malformed dependencies cannot break the fallback");
  assert.match(component, /downstream === undefined \? "Unavailable while the dependency graph is invalid"/, "invalid edges are unknown, not absent");
  assert.match(component, /selectedNodeId/, "duplicate module ids still select the exact served node");
  for (const status of ["pending", "ready", "running", "succeeded", "failed", "cancelled"]) {
    assert.match(component, new RegExp(`"${status}"`));
  }
  assert.doesNotMatch(component, /"blocked"/);
});

test("SSE freshness is identity-scoped and never changes execution state", () => {
  const workspace = readFileSync(new URL("../Workspace.tsx", import.meta.url), "utf8");
  const effect = workspace.slice(workspace.indexOf("const runSettled ="), workspace.indexOf("const createCase ="));
  assert.match(effect, /let disposed = false/);
  assert.match(effect, /const current = \(\) => !disposed[\s\S]*authorityRef\.current\.caseId === context\.caseId[\s\S]*authorityRef\.current\.runId === context\.runId/);
  assert.doesNotMatch(effect, /const current = \(\) => !disposed && matchesAuthority/);
  assert.match(effect, /source\.onopen = \(\) => \{[\s\S]*status: "live"[\s\S]*refresh\(\)/);
  assert.match(effect, /source\.onerror = \(\) => \{[\s\S]*status: "stale"/);
  assert.match(effect, /return \(\) => \{ disposed = true; source\.close\(\); \}/);
  assert.match(workspace, /next\.caseId !== authorityRef\.current\.caseId \|\| next\.runId !== authorityRef\.current\.runId[\s\S]*status: next\.runId \? "connecting" : "idle"/);
  assert.match(workspace, /runSettled \? "settled" : runConnection\.caseId === caseId && runConnection\.runId === runId/);
  assert.doesNotMatch(effect, /setRun\([^)]*(?:failed|status)/, "connection callbacks must not mutate execution state");
});
