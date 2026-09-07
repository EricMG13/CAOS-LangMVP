import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { chromium, request } from "playwright";

const baseURL = process.env.CAOS_URL;
assert.ok(baseURL, "CAOS_URL must explicitly name the disposable Task 10 harness");
const harnessURL = new URL(baseURL);
assert.ok(["127.0.0.1", "localhost", "[::1]"].includes(harnessURL.hostname), "CAOS_URL must be loopback-only");
assert.notEqual(harnessURL.port || (harnessURL.protocol === "https:" ? "443" : "80"), "8000", "CAOS_URL must not target the excluded port-8000 legacy app");
const edge = process.env.CAOS_EDGE_SECRET;
assert.ok(edge, "CAOS_EDGE_SECRET is required for the production-identity integration harness");
const suffix = randomUUID().slice(0, 8);
const subject = `task10-graph-${suffix}@local.invalid`;
const headers = {
  "x-edge-authorization": edge,
  "x-forwarded-user": subject,
  "x-forwarded-email": subject,
  "x-forwarded-groups": "caos-analyst",
};
const resultsDir = path.resolve(process.env.CAOS_RESULTS_DIR || "test-results", "task10-graph-matrix");
mkdirSync(resultsDir, { recursive: true });
const pathways = [
  "FULL_CREDIT",
  "EARNINGS_UPDATE",
  "COVENANT_REFINANCING",
  "RELATIVE_VALUE",
  "DISTRESSED_RESTRUCTURING",
  "DEEP_RESEARCH",
];
const depths = ["screen", "full"];
const matrix = {
  schema_version: "caos.task10-graph-matrix.v1",
  fixture_authority: "actual disposable host-control plan responses rendered by the production browser UI; DEEP_RESEARCH/screen is the explicit server/UI negative contract",
  subject,
  case_id: null,
  combinations: [],
};

async function checkedJson(response, expected) {
  const body = await response.text();
  assert.equal(response.status(), expected, `${response.url()} answered ${response.status()}: ${body.slice(0, 800)}`);
  return JSON.parse(body);
}

const api = await request.newContext({ baseURL, extraHTTPHeaders: headers });
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ baseURL, extraHTTPHeaders: headers, viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();

try {
  const issuer = `Task10 Graph ${suffix} Holdings`;
  const form = new FormData();
  form.append("files", new Blob([`${issuer}\nFORM 10-K\nRevenue 1160\nAdjusted EBITDA 222\nTotal debt 630\nCash 75\n`], { type: "text/plain" }), "annual-report.txt");
  form.append("files", new Blob([`${issuer}\nFORM 10-Q\nQuarterly period ended June 30 2026\nRevenue 310\nAdjusted EBITDA 61\n`], { type: "text/plain" }), "quarterly-report.txt");
  form.append("files", new Blob([`CREDIT AGREEMENT\namong ${issuer}, the lenders and administrative agent\nTerm Loan B and Revolving Credit Facility\n`], { type: "text/plain" }), "credit-agreement.txt");
  const intake = await checkedJson(await api.post("/api/intake", { multipart: form }), 201);
  const caseId = intake.case.id;
  matrix.case_id = caseId;
  matrix.source_set_id = intake.run.plan.source_set_id;
  matrix.source_set_digest = intake.run.plan.source_set_digest;

  for (const pathway of pathways) {
    for (const depth of depths) {
      const requestBody = {
        pathway,
        depth,
        focus_questions: [],
        ...(pathway === "DEEP_RESEARCH" ? {
          research_brief: {
            research_question: "Can this disposable issuer refinance its stated debt through 2029?",
            decision_context: "Task 10 graph-contract qualification only.",
            as_of_date: "2026-09-07",
            time_horizon: "Through 2029",
            must_answer: ["What are the binding refinancing constraints?"],
            exclusions: ["Live market recommendations"],
          },
        } : {}),
      };
      const startResponse = await api.post(`/api/cases/${caseId}/runs`, { data: requestBody });
      if (pathway === "DEEP_RESEARCH" && depth === "screen") {
        const refusalText = await startResponse.text();
        assert.equal(startResponse.status(), 422, `DEEP_RESEARCH/screen unexpectedly answered ${startResponse.status()}: ${refusalText.slice(0, 800)}`);
        const refusal = JSON.parse(refusalText);
        assert.match(JSON.stringify(refusal.detail), /DEEP_RESEARCH requires full depth/);
        await page.goto(`/run/?case=${caseId}`, { waitUntil: "domcontentloaded" });
        await page.getByRole("combobox", { name: "Purpose" }).selectOption("DEEP_RESEARCH");
        const depthControl = page.getByRole("combobox", { name: "Depth" });
        assert.equal(await depthControl.inputValue(), "full", "Deep Research did not force full depth in the production UI");
        assert.equal(await depthControl.locator('option[value="screen"]').isDisabled(), true, "Deep Research left Screen selectable in the production UI");
        const screenshot = path.join(resultsDir, "deep-research-screen-refusal.png");
        await page.screenshot({ path: screenshot, fullPage: true });
        matrix.combinations.push({
          pathway,
          depth,
          outcome: "contractually_refused",
          status: 422,
          detail: refusal.detail,
          ui_forced_depth: await depthControl.inputValue(),
          ui_screen_disabled: true,
          screenshot,
        });
        continue;
      }
      const started = await checkedJson(startResponse, 201);
      const served = await checkedJson(await api.get(`/api/runs/${started.id}`), 200);
      assert.equal(served.plan.pathway, pathway);
      assert.equal(served.plan.depth, depth);
      assert.ok(served.nodes.length > 0, `${pathway}/${depth} served no graph nodes`);
      const expectedEdges = served.nodes.reduce((count, node) => count + node.dependencies.length, 0);
      const expectedEdgePairs = served.nodes.flatMap((node) => node.dependencies.map((dependency) => `${dependency}->${node.module_id}`)).sort();
      const expectedNodeIds = served.nodes.map((node) => node.id).sort();
      const expectedModules = served.nodes.map((node) => node.module_id).sort();

      await page.goto(`/run/?case=${caseId}&run=${served.id}`, { waitUntil: "domcontentloaded" });
      await page.getByRole("region", { name: "Run dependency graph" }).waitFor({ timeout: 30_000 });
      await page.waitForFunction((count) => document.querySelectorAll("[data-run-node-id]").length === count, served.nodes.length);
      const displayedNodeIds = (await page.locator("[data-run-node-id]").evaluateAll((elements) => elements.map((element) => element.getAttribute("data-run-node-id")).filter(Boolean))).sort();
      const displayedModules = (await page.locator("[data-run-node-id]").evaluateAll((elements) => elements.map((element) => element.getAttribute("data-module-id")).filter(Boolean))).sort();
      const displayedEdges = await page.locator('[aria-label="Run dependency graph"] svg > path').count();
      const displayedEdgePairs = (await page.locator('[aria-label="Run dependency graph"]').evaluate((graph) => {
        const centers = [...graph.querySelectorAll("[data-module-id]")].map((element) => {
          const bounds = element.getBoundingClientRect();
          return {
            moduleId: element.getAttribute("data-module-id"),
            left: { x: bounds.left, y: bounds.top + bounds.height / 2 },
            right: { x: bounds.right, y: bounds.top + bounds.height / 2 },
          };
        });
        const screenPoint = (pathElement, atEnd) => {
          const point = pathElement.getPointAtLength(atEnd ? pathElement.getTotalLength() : 0);
          const matrix = pathElement.getScreenCTM();
          if (!matrix) throw new Error("rendered dependency path has no screen transform");
          return new DOMPoint(point.x, point.y).matrixTransform(matrix);
        };
        const nearest = (point, side) => centers
          .map((candidate) => ({ moduleId: candidate.moduleId, distance: Math.hypot(point.x - candidate[side].x, point.y - candidate[side].y) }))
          .sort((left, right) => left.distance - right.distance)[0];
        return [...graph.querySelectorAll("svg > path")].map((pathElement) => {
          const source = nearest(screenPoint(pathElement, false), "right");
          const target = nearest(screenPoint(pathElement, true), "left");
          if (!source?.moduleId || !target?.moduleId || source.distance > 2 || target.distance > 2) {
            throw new Error(`dependency path endpoints do not meet rendered nodes: ${JSON.stringify({ source, target })}`);
          }
          return `${source.moduleId}->${target.moduleId}`;
        }).sort();
      }));
      assert.deepEqual(displayedNodeIds, expectedNodeIds, `${pathway}/${depth} displayed node identities differ from the served run`);
      assert.deepEqual(displayedModules, expectedModules, `${pathway}/${depth} displayed module identities differ from the served run`);
      assert.equal(displayedEdges, expectedEdges, `${pathway}/${depth} displayed edge count differs from served dependencies`);
      assert.deepEqual(displayedEdgePairs, expectedEdgePairs, `${pathway}/${depth} displayed dependency pairs differ from the served run`);
      const slug = `${pathway.toLowerCase().replaceAll("_", "-")}-${depth}`;
      const screenshot = path.join(resultsDir, `${slug}.png`);
      await page.screenshot({ path: screenshot, fullPage: true });
      matrix.combinations.push({
        pathway,
        depth,
        run_id: served.id,
        status_at_capture: served.status,
        profile_id: served.plan.profile_id,
        selection_id: served.plan.selection_id,
        source_set_id: served.plan.source_set_id,
        source_set_digest: served.plan.source_set_digest,
        served_nodes: served.nodes.map(({ id, module_id, stage, dependencies }) => ({ id, module_id, stage, dependencies })),
        served_edge_count: expectedEdges,
        served_edge_pairs: expectedEdgePairs,
        displayed_node_ids: displayedNodeIds,
        displayed_modules: displayedModules,
        displayed_edge_count: displayedEdges,
        displayed_edge_pairs: displayedEdgePairs,
        screenshot,
      });
    }
  }
  assert.equal(matrix.combinations.length, 12);
  matrix.status = "passed";
  console.log(JSON.stringify({ status: matrix.status, case_id: matrix.case_id, combinations: matrix.combinations.length, results: resultsDir }));
} catch (error) {
  matrix.status = "failed";
  matrix.error = String(error?.stack || error);
  try { await page.screenshot({ path: path.join(resultsDir, "failure.png"), fullPage: true }); } catch { /* page already closed */ }
  throw error;
} finally {
  writeFileSync(path.join(resultsDir, "graph-matrix.json"), `${JSON.stringify(matrix, null, 2)}\n`);
  await context.close();
  await browser.close();
  await api.dispose();
}
