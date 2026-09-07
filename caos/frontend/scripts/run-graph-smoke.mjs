import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const baseURL = process.env.CAOS_URL || "http://127.0.0.1:19181";
const resultsDir = process.env.CAOS_RESULTS_DIR || "test-results/run-graph";
mkdirSync(resultsDir, { recursive: true });

const provider_identity = { provider_name: "host_control", model: "fixture-model" };
const nodes = [
  { id: "node-parse", module_id: "CP-PARSE", stage: 0, dependencies: [], status: "succeeded", artifact_id: "art-parse" },
  { id: "node-ready", module_id: "CP-0", stage: 1, dependencies: ["CP-PARSE"], status: "succeeded", artifact_id: "art-ready" },
  { id: "node-left", module_id: "CP-1A", stage: 2, dependencies: ["CP-0"], status: "running", artifact_id: null },
  { id: "node-right", module_id: "CP-1B", stage: 2, dependencies: ["CP-0"], status: "running", artifact_id: null },
  { id: "node-merge", module_id: "CP-2", stage: 3, dependencies: ["CP-1A", "CP-1B"], status: "pending", artifact_id: null },
];
const run = (id, case_id, status, runNodes, extra = {}) => ({
  id, case_id, status, provider_identity,
  plan: { pathway: "FULL_CREDIT", depth: "full", profile_id: "FULL_CREDIT_32", selection_id: "FULL_CREDIT_ASSESSMENT" },
  nodes: runNodes, accepted_snapshot_id: null, error: null, ...extra,
});
const running = run("run-live", "case-a", "running", nodes);
const failed = run("run-live", "case-a", "failed", nodes.map((node) => node.id === "node-left" ? { ...node, status: "failed", error: { code: "OUTPUT_SCHEMA_INVALID", module_id: "CP-1A" } } : node.status === "running" || node.status === "pending" ? { ...node, status: "cancelled" } : node), { error: { code: "OUTPUT_SCHEMA_INVALID", module_id: "CP-1A" } });
const research = run("run-research", "case-a", "paused", [
  { id: "research-upstream", module_id: "CP-PARSE", stage: 0, dependencies: [], status: "succeeded", artifact_id: "art-rp" },
  { id: "research-node", module_id: "CP-DR", stage: 1, dependencies: ["CP-PARSE"], status: "ready", artifact_id: null },
], { plan: { pathway: "DEEP_RESEARCH", depth: "full", profile_id: "FULL_CREDIT_32", selection_id: "DEEP_RESEARCH" }, error: { code: "PLAN_APPROVAL_REQUIRED", module_id: "CP-DR", message: "Approve the persisted research plan." }, research: { phase: "awaiting_approval", proposed_plan_hash: "sha256:fixture", proposed_plan: null } });
const invalid = run("run-invalid", "case-a", "running", [
  { id: "duplicate-first", module_id: "CP-1", stage: 0, dependencies: [], status: "pending", artifact_id: null },
  { id: "duplicate-second", module_id: "CP-1", stage: 1, dependencies: [null], status: "ready", artifact_id: null },
]);
const other = run("run-other", "case-b", "succeeded", [{ id: "other-node", module_id: "CP-4C", stage: 0, dependencies: [], status: "succeeded", artifact_id: "art-other" }]);
let currentLive = running;
const cases = [
  { id: "case-a", name: "Graph QA", issuer: "Branch and Merge", sector: "Services", source_count: 1, current_execution_id: running.id, members: { "analyst.qa@local.invalid": "ANALYST" }, accepted_snapshot_id: null, available_pathways: ["FULL_CREDIT", "DEEP_RESEARCH"], deep_research_available: true, latest_intake_id: null },
  { id: "case-b", name: "Switch QA", issuer: "Other Credit", sector: "Industrials", source_count: 1, current_execution_id: other.id, members: { "analyst.qa@local.invalid": "ANALYST" }, accepted_snapshot_id: null, available_pathways: ["FULL_CREDIT"], deep_research_available: false, latest_intake_id: null },
];
const runs = { "run-live": () => currentLive, "run-research": () => research, "run-invalid": () => invalid, "run-other": () => other };
let streamRequests = 0;
let releaseSecondStream;
const secondStream = new Promise((resolve) => { releaseSecondStream = resolve; });

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, extraHTTPHeaders: process.env.CAOS_EDGE_SECRET ? {
  "x-edge-authorization": process.env.CAOS_EDGE_SECRET,
  "x-forwarded-user": "analyst.qa@local.invalid",
  "x-forwarded-email": "analyst.qa@local.invalid",
  "x-forwarded-groups": "caos-analyst",
} : {} });
const page = await context.newPage();
await page.route("**/api/**", async (route) => {
  const url = new URL(route.request().url());
  const json = (body, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  if (url.pathname === "/api/me") return json({ role: "ANALYST", subject: "analyst.qa@local.invalid", can_bootstrap_approver: false, can_manage_providers: false });
  if (url.pathname === "/api/cases") return json(cases);
  const caseMatch = /^\/api\/cases\/([^/]+)$/.exec(url.pathname);
  if (caseMatch) return json(cases.find((item) => item.id === caseMatch[1]));
  const snapshotMatch = /^\/api\/cases\/([^/]+)\/snapshot$/.exec(url.pathname);
  if (snapshotMatch) return json({ accepted: null, latest_accepted: null, switch_required: false, diff: null });
  const runMatch = /^\/api\/runs\/([^/]+)$/.exec(url.pathname);
  if (runMatch) return json(runs[runMatch[1]]?.() ?? { detail: "not found" }, runs[runMatch[1]] ? 200 : 404);
  const eventsMatch = /^\/api\/runs\/([^/]+)\/events$/.exec(url.pathname);
  if (eventsMatch) {
    streamRequests += 1;
    if (eventsMatch[1] === "run-live" && streamRequests > 1) await secondStream;
    return route.fulfill({ status: 200, headers: { "content-type": "text/event-stream", "cache-control": "no-cache" }, body: `event: node.running\ndata: {}\n\n` });
  }
  return json({ detail: "not found" }, 404);
});

try {
  await page.goto(`${baseURL}/run/?case=case-a&run=run-live`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: "Stage 3" }).waitFor();
  assert.equal(await page.locator('[data-module-id="CP-1A"] .status').textContent(), "running");
  assert.equal(await page.locator('[data-module-id="CP-1B"] .status').textContent(), "running");
  const left = page.locator('[data-run-node-id="node-left"]');
  await left.focus();
  await page.keyboard.press("Enter");
  assert.equal(await left.getAttribute("aria-pressed"), "true");
  await page.getByRole("heading", { name: "Node inspector" }).waitFor();
  assert.match(await page.getByRole("region", { name: "Node inspector" }).textContent(), /Source Readiness.*Fundamental Credit Synthesizer/s);
  await page.screenshot({ path: path.join(resultsDir, "run-graph-branch-merge-inspector-1440.png"), fullPage: true });
  await page.setViewportSize({ width: 720, height: 1000 });
  const validScroller = page.getByRole("region", { name: "Run dependency graph" });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth), false, "the valid graph causes page-level horizontal overflow");
  assert.equal(await validScroller.evaluate((element) => element.scrollWidth > element.clientWidth), true, "the valid graph does not retain local horizontal scrolling");
  await page.screenshot({ path: path.join(resultsDir, "run-graph-branch-merge-inspector-720.png"), fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1000 });

  await page.getByText("Updates reconnecting", { exact: true }).waitFor({ timeout: 5000 });
  await page.waitForFunction(() => performance.now() > 0);
  const reconnectDeadline = Date.now() + 7000;
  while (streamRequests < 2 && Date.now() < reconnectDeadline) await page.waitForTimeout(100);
  assert.ok(streamRequests >= 2, "EventSource did not reconnect after the served stream closed");
  currentLive = failed;
  releaseSecondStream();
  await page.getByText("Execution stopped", { exact: true }).waitFor();
  assert.equal(await page.locator('[data-run-node-id="node-left"]').getAttribute("aria-pressed"), "true", "selection did not survive the RunRecord update");
  assert.equal(await page.locator('[data-run-node-id="node-right"] .status').textContent(), "cancelled");

  const documentMarker = await page.evaluate(() => {
    globalThis.__task4DocumentMarker = crypto.randomUUID();
    return globalThis.__task4DocumentMarker;
  });
  await page.evaluate(() => {
    window.history.pushState(window.history.state, "", "/run/?case=case-a&run=run-research");
    window.dispatchEvent(new PopStateEvent("popstate", { state: window.history.state }));
  });
  await page.waitForURL((url) => url.searchParams.get("run") === "run-research");
  await page.locator('[data-run-node-id="research-node"]').waitFor();
  assert.equal(await page.evaluate(() => globalThis.__task4DocumentMarker), documentMarker, "same-case run switch replaced the document");
  assert.equal(await page.getByRole("heading", { name: "Node inspector" }).count(), 0, "node selection crossed a same-case run boundary");
  assert.equal(await page.getByText("Updates ended", { exact: true }).count(), 0, "old run freshness crossed a same-document run boundary");
  await page.getByText(/Updates (?:live|reconnecting)/).waitFor();
  await page.locator('[data-run-node-id="research-node"]').focus();
  await page.keyboard.press("Enter");
  await page.getByText("Research pause", { exact: true }).waitFor();
  assert.match(await page.getByRole("region", { name: "Node inspector" }).textContent(), /Research pauseawaiting approval/);

  await page.goto(`${baseURL}/run/?case=case-a&run=run-invalid`, { waitUntil: "domcontentloaded" });
  await page.getByText("Dependency graph unavailable.", { exact: true }).waitFor();
  await page.setViewportSize({ width: 720, height: 1000 });
  const duplicateSecond = page.locator('[data-run-node-id="duplicate-second"]');
  await duplicateSecond.focus();
  await page.keyboard.press("Enter");
  assert.equal(await duplicateSecond.getAttribute("aria-pressed"), "true");
  assert.equal(await page.locator('[data-run-node-id="duplicate-first"]').getAttribute("aria-pressed"), "false");
  const invalidInspector = page.getByRole("region", { name: "Node inspector" });
  assert.match(await invalidInspector.textContent(), /Stage1.*Upstream inputsUnavailable.*Downstream consumersUnavailable while the dependency graph is invalid/s);
  await page.screenshot({ path: path.join(resultsDir, "run-graph-invalid-inspector-720.png"), fullPage: true });

  await page.getByLabel("Select case").selectOption("case-b");
  await page.getByText("Restructuring Fulcrum", { exact: true }).waitFor();
  assert.equal(await page.getByRole("heading", { name: "Node inspector" }).count(), 0, "node selection crossed the case/run boundary");
  assert.equal(await page.getByText("Updates ended", { exact: true }).count(), 1, "old stream freshness crossed the case/run boundary");
  console.log(JSON.stringify({ status: "passed", evidence: "route-controlled UI states", streamRequests, screenshots: ["run-graph-branch-merge-inspector-1440.png", "run-graph-branch-merge-inspector-720.png", "run-graph-invalid-inspector-720.png"] }));
} finally {
  await context.close();
  await browser.close();
}
