import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { chromium, request } from "playwright";

const baseURL = process.env.CAOS_URL || "http://127.0.0.1:19181";
const resultsDir = process.env.CAOS_RESULTS_DIR || "test-results/run-graph-live";
mkdirSync(resultsDir, { recursive: true });
const identityHeaders = {
  "x-edge-authorization": process.env.CAOS_EDGE_SECRET || "",
  "x-forwarded-user": "analyst.qa@local.invalid",
  "x-forwarded-email": "analyst.qa@local.invalid",
  "x-forwarded-groups": "caos-analyst",
};
const api = await request.newContext({ baseURL, extraHTTPHeaders: identityHeaders });
const suffix = randomUUID().slice(0, 8);

const created = await api.post("/api/cases", { data: { name: "Run graph live QA", issuer: `Full-Credit-${suffix}`, sector: "Services" } });
assert.equal(created.status(), 201);
const caseRecord = await created.json();
const uploaded = await api.post(`/api/cases/${caseRecord.id}/sources`, { multipart: { file: {
  name: "full-credit.txt",
  mimeType: "text/plain",
  buffer: Buffer.from("Revenue 1,160\nEBITDA 222\nDebt 640\nCash 85\nInterest expense 44\nCovenant leverage 4.5x"),
} } });
assert.equal(uploaded.status(), 201);
const started = await api.post(`/api/cases/${caseRecord.id}/runs`, { data: { pathway: "FULL_CREDIT", depth: "full", focus_questions: [] } });
assert.equal(started.status(), 201);
const startedRun = await started.json();
const served = await api.get(`/api/runs/${startedRun.id}`);
assert.equal(served.status(), 200);
const run = await served.json();
assert.equal(run.nodes.length, 17);
assert.equal(new Set(run.nodes.map((node) => node.stage)).size, 17);
const stageByModule = new Map(run.nodes.map((node) => [node.module_id, node.stage]));
const skipEdges = run.nodes.flatMap((node) => node.dependencies.map((dependency) => [dependency, node.module_id]))
  .filter(([source, target]) => Math.abs(stageByModule.get(target) - stageByModule.get(source)) > 1);
assert.equal(skipEdges.length, 44);

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, extraHTTPHeaders: identityHeaders });
const page = await context.newPage();
try {
  await page.goto(`${baseURL}/run/?case=${caseRecord.id}&run=${run.id}`, { waitUntil: "domcontentloaded" });
  await page.locator('[data-module-id="CP-3"]').waitFor();
  const graph = page.getByRole("region", { name: "Run dependency graph" });
  assert.equal(await graph.locator("svg path[marker-end]").count(), run.nodes.reduce((count, node) => count + node.dependencies.length, 0));
  assert.equal(await page.locator("[data-run-node-id]").evaluateAll((buttons) => buttons.every((button) => button.scrollHeight <= button.clientHeight)), true, "an actual module label overflows its fixed-height node");
  const longest = page.locator('[data-module-id="CP-3"]');
  await longest.scrollIntoViewIfNeeded();
  await longest.focus();
  await page.keyboard.press("Enter");
  await page.getByRole("heading", { name: "Node inspector" }).waitFor();
  await page.screenshot({ path: path.join(resultsDir, "actual-full-credit-longest-label-inspector-1440.png"), fullPage: true });
  console.log(JSON.stringify({ status: "passed", evidence: "actual fixture-server Full Credit full", caseId: caseRecord.id, runId: run.id, nodes: run.nodes.length, stages: new Set(run.nodes.map((node) => node.stage)).size, edges: run.nodes.reduce((count, node) => count + node.dependencies.length, 0), skipEdges: skipEdges.length, screenshot: "actual-full-credit-longest-label-inspector-1440.png" }));
} finally {
  await context.close();
  await browser.close();
  await api.dispose();
}
