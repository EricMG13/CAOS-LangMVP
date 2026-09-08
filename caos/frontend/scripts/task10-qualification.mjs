import assert from "node:assert/strict";
import { createHash, randomUUID } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { chromium, firefox, request, webkit } from "playwright";

const engines = { chromium, firefox, webkit };
const browserName = process.env.CAOS_BROWSER || "chromium";
assert.ok(browserName in engines, `CAOS_BROWSER must be one of ${Object.keys(engines).join(", ")}`);
const baseURL = process.env.CAOS_URL;
assert.ok(baseURL, "CAOS_URL must explicitly name the disposable Task 10 harness");
const harnessURL = new URL(baseURL);
assert.ok(["127.0.0.1", "localhost", "[::1]"].includes(harnessURL.hostname), "CAOS_URL must be loopback-only");
assert.notEqual(harnessURL.port || (harnessURL.protocol === "https:" ? "443" : "80"), "8000", "CAOS_URL must not target the excluded port-8000 legacy app");
const suffix = randomUUID().slice(0, 8);
const subject = `task10-${browserName}-${suffix}@local.invalid`;
const edge = process.env.CAOS_EDGE_SECRET;
assert.ok(edge, "CAOS_EDGE_SECRET is required for the production-identity integration harness");
const headers = {
  "x-edge-authorization": edge,
  "x-forwarded-user": subject,
  "x-forwarded-email": subject,
  "x-forwarded-groups": "caos-analyst",
};
const resultsDir = path.resolve(process.env.CAOS_RESULTS_DIR || "test-results", "task10-qualification", browserName);
mkdirSync(resultsDir, { recursive: true });
const evidence = {
  schema_version: "caos.task10-qualification.v1",
  browser: browserName,
  base_url: baseURL,
  fixture_authority: "development host_control with opt-in canonical report answer keys; not live analytical qualification",
  screenshots: [],
  exports: {},
};

const browser = await engines[browserName].launch({ headless: true });
const api = await request.newContext({ baseURL, extraHTTPHeaders: headers });
const context = await browser.newContext({ baseURL, extraHTTPHeaders: headers, viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const errors = [];
page.on("pageerror", (error) => errors.push(String(error)));

async function json(response, expected = 200) {
  const body = await response.text();
  assert.equal(response.status(), expected, `${response.url()} answered ${response.status()}: ${body.slice(0, 500)}`);
  return JSON.parse(body);
}

async function waitFor(read, done, message, attempts = 240) {
  let value;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    value = await read();
    if (done(value)) return value;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`${message}: ${JSON.stringify(value).slice(0, 1000)}`);
}

async function capture(capability, fullPage = false) {
  for (const [width, height] of [[1440, 1000], [1024, 850], [720, 900]]) {
    await page.setViewportSize({ width, height });
    await page.waitForTimeout(80);
    const overflow = await page.evaluate(() => ({ client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
    assert.ok(overflow.scroll <= overflow.client + 1, `${capability} has page-level horizontal overflow at ${width}px: ${JSON.stringify(overflow)}`);
    const target = path.join(resultsDir, `${capability}-${width}.png`);
    await page.screenshot({ path: target, fullPage });
    evidence.screenshots.push(target);
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
}

async function captureFocused(capability, target) {
  for (const [width, height] of [[1440, 1000], [1024, 850], [720, 900]]) {
    await page.setViewportSize({ width, height });
    await target.scrollIntoViewIfNeeded();
    await page.waitForTimeout(80);
    const output = path.join(resultsDir, `${capability}-${width}.png`);
    await target.screenshot({ path: output });
    evidence.screenshots.push(output);
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
}

async function openReportControls() {
  const control = page.getByRole("button", { name: "Commentary, model and publication" });
  if (await control.getAttribute("aria-expanded") !== "true") await control.click();
  assert.equal(await control.getAttribute("aria-expanded"), "true");
  return control;
}

function intakeDocument(name, text) {
  return { name, mimeType: "text/plain", buffer: Buffer.from(text) };
}

try {
  const issuer = `Task10-${browserName}-${suffix} Holdings`;
  const documents = [
    intakeDocument("annual-report.txt", `${issuer}\nFORM 10-K\nANNUAL REPORT\nFor the fiscal year ended December 31, 2025\nRevenue 1,160\nAdjusted EBITDA 222\nTotal debt 630\nCash 75\n`),
    intakeDocument("quarterly-report.txt", `${issuer}\nFORM 10-Q\nQUARTERLY REPORT\nFor the quarterly period ended June 30, 2026\nRevenue 310\nAdjusted EBITDA 61\nCash 68\n`),
    intakeDocument("credit-agreement.txt", `CREDIT AGREEMENT\namong ${issuer}, the lenders and administrative agent\nTerm Loan B and Revolving Credit Facility\nSection 6.10 Financial Covenants\n`),
  ];
  const form = new FormData();
  for (const document of documents) form.append("files", new Blob([document.buffer], { type: document.mimeType }), document.name);
  const intake = await json(await api.post("/api/intake", { multipart: form }), 201);
  assert.equal(intake.route.pathway, "FULL_CREDIT");
  assert.equal(intake.route.depth, "full");
  assert.equal(intake.documents.length, documents.length, "intake omitted an uploaded document");
  assert.ok(intake.documents.every((document) => document.disposition === "used"));
  const caseId = intake.case.id;
  const runId = intake.run.id;
  const run = await waitFor(
    async () => json(await api.get(`/api/runs/${runId}`)),
    (value) => ["succeeded", "failed", "paused"].includes(value.status),
    "Full Credit intake run did not settle",
  );
  assert.equal(run.status, "succeeded");
  evidence.case_id = caseId;
  evidence.run_id = runId;
  evidence.source_set_id = run.plan.source_set_id;
  evidence.source_set_digest = run.plan.source_set_digest;

  await page.goto(`/run/?case=${caseId}&run=${runId}`, { waitUntil: "networkidle" });
  await page.getByRole("status").getByText("Run status: succeeded", { exact: true }).waitFor();
  const expectedEdges = run.nodes.reduce((count, node) => count + node.dependencies.length, 0);
  assert.equal(await page.locator('[aria-label="Run dependency graph"] svg > path').count(), expectedEdges, "displayed Full Credit edges differ from served dependencies");
  await page.locator("[data-run-node-id]").nth(1).click();
  await page.getByRole("heading", { name: "Node inspector" }).waitFor();
  await capture("run");
  await page.getByRole("button", { name: "Accept analytical snapshot" }).click();
  const acceptDialog = page.getByRole("dialog", { name: "Accept analytical snapshot" });
  await acceptDialog.getByText(runId, { exact: true }).waitFor();
  await acceptDialog.getByRole("button", { name: "Accept analytical snapshot" }).click();
  await page.getByText("Latest accepted authority", { exact: true }).waitFor();
  const authority = await json(await api.get(`/api/cases/${caseId}/snapshot`));
  const accepted = authority.accepted;
  assert.equal(accepted.run_id, runId);
  assert.equal(accepted.source_set_id, run.plan.source_set_id);
  evidence.accepted_snapshot_id = accepted.id;
  evidence.accepted_snapshot_digest = accepted.digest;
  evidence.artifact_ids = accepted.artifacts.map((artifact) => artifact.id);

  await page.goto(`/analysis/?case=${caseId}`, { waitUntil: "networkidle" });
  const cp1 = accepted.artifacts.find((artifact) => artifact.module_id === "CP-1");
  assert.ok(cp1, "accepted snapshot has no CP-1 artifact");
  await page.getByRole("navigation", { name: "Accepted analysis modules" }).getByRole("button").filter({ hasText: "CP-1" }).first().click();
  const chart = page.locator('.chart-exhibit-canvas[data-chart-lifecycle="ready"]').first();
  await chart.waitFor({ timeout: 30_000 });
  const exactTable = page.locator('.chart-exhibit-table[role="region"]').first();
  await exactTable.waitFor();
  assert.ok(await page.getByRole("navigation", { name: /chart sources$/ }).getByRole("link").count(), "canonical chart has no governed source links");
  const analysisAxe = await new AxeBuilder({ page }).include(".module-presentation").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  assert.deepEqual(analysisAxe.violations, []);
  evidence.loaded_chart_axe = true;
  await capture("analysis");
  await captureFocused("analysis-chart-table", page.locator(".module-presentation .chart-exhibit").first());

  let readiness = await waitFor(
    async () => json(await api.get(`/api/cases/${caseId}/model`)),
    (value) => ["READY", "READY_TO_BUILD", "FAILED", "NOT_READY"].includes(value.status),
    "model readiness did not settle",
  );
  if (readiness.status === "READY_TO_BUILD") {
    await json(await api.post(`/api/cases/${caseId}/models`), 202);
    readiness = await waitFor(
      async () => json(await api.get(`/api/cases/${caseId}/model`)),
      (value) => ["READY", "FAILED"].includes(value.status),
      "application model build did not settle",
    );
  }
  assert.equal(readiness.status, "READY");
  const build = readiness.build;
  assert.equal(build.accepted_snapshot_id, accepted.id);
  evidence.model_build_id = build.id;
  evidence.model_payload_digest = build.payload_digest;

  await page.goto(`/model/?case=${caseId}`, { waitUntil: "networkidle" });
  await page.getByRole("tab", { name: "Credit Snapshot" }).waitFor({ timeout: 30_000 });
  await page.getByRole("group", { name: "Forecast case" }).getByRole("button", { name: "Downside" }).click();
  assert.equal(await page.getByRole("button", { name: "Downside" }).getAttribute("aria-pressed"), "true");
  await page.getByRole("group", { name: "Forecast case" }).getByRole("button", { name: "Base" }).click();
  const forecast = page.locator('input[type="number"]:not([disabled])').first();
  const prior = Number(await forecast.inputValue());
  assert.ok(Number.isFinite(prior));
  await forecast.fill(String(prior + 0.01));
  await forecast.press("Enter");
  await page.getByText(/Forecast recalculated\. Historical accounts remain locked/).waitFor({ timeout: 30_000 });
  await page.getByLabel("Sign-Off Note *").fill("Task 10 disposable fixture: changed one forward Base assumption after reviewing accepted sources.");
  await page.getByRole("button", { name: "Save model version" }).click();
  await page.getByText("Application model · R1", { exact: true }).waitFor({ timeout: 30_000 });
  const revisions = await json(await api.get(`/api/cases/${caseId}/model-revisions`));
  const revision = revisions.revisions.find((item) => item.state === "ACTIVE");
  assert.ok(revision, "model sign-off produced no active revision");
  assert.equal(revision.build_id, build.id);
  evidence.model_revision_id = revision.id;
  evidence.model_revision_digest = revision.outputs_digest;
  await capture("model");
  await page.getByRole("button", { name: "Hide assumptions" }).click();
  await page.getByRole("button", { name: "Hide sensitivity" }).click();
  await page.getByRole("tab", { name: "Model", exact: true }).click();
  const periodFamily = page.getByRole("group", { name: "Period family" });
  assert.equal(await periodFamily.count(), 1, "served Model worksheet has no period navigation");
  assert.ok(await periodFamily.getByRole("button").count() > 1, "served Model worksheet has no selectable period family");
  const selectedPeriodFamily = periodFamily.getByRole("button").last();
  await selectedPeriodFamily.click();
  assert.equal(await selectedPeriodFamily.getAttribute("aria-pressed"), "true");
  const worksheetSections = page.getByRole("navigation", { name: "Worksheet sections" });
  assert.equal(await worksheetSections.count(), 1, "served Model worksheet has no section navigation");
  const cashFlowSection = worksheetSections.getByRole("button", { name: /Cash Flow/i });
  assert.equal(await cashFlowSection.count(), 1, "served Model worksheet has no Cash Flow section");
  await cashFlowSection.click();
  const worksheetViewport = page.getByRole("region", { name: /Model worksheet; scroll horizontally and vertically/i });
  await worksheetViewport.waitFor();
  await page.waitForFunction(() => document.querySelector(".worksheet-scroll")?.scrollTop > 0);
  assert.ok(await worksheetViewport.locator("[data-address]").count() > 10, "settled Cash Flow worksheet exposes no calculated cells");
  assert.equal(await page.getByText("RECALCULATING", { exact: true }).count(), 0, "Cash Flow capture retained a pending calculation");
  await captureFocused("model-cash-flow", worksheetViewport);

  const draftPath = `/api/cases/${caseId}/deliverables/FULL_CREDIT/draft`;
  await page.goto(`/report/?case=${caseId}`, { waitUntil: "networkidle" });
  await page.locator(".report-generated").waitFor({ timeout: 30_000 });
  let workspace = await json(await api.get(draftPath));
  assert.equal(workspace.template.template_version, "caos.deliverable-template.v2");
  assert.equal(workspace.model_eligibility.active_revision.revision_id, revision.id);
  assert.ok(workspace.preview.document_sections.length > 0);
  await page.getByRole("button", { name: "Save module-populated draft" }).click();
  await page.locator(".report-save-state").filter({ hasText: "Saved v1" }).waitFor({ timeout: 30_000 });
  await page.getByRole("button", { name: "Add commentary", exact: true }).first().click();
  await page.getByLabel("Analyst commentary", { exact: true }).fill("Retain the fixture-only hold while the next reporting pack is reviewed.");
  await page.getByLabel("Analyst judgment", { exact: true }).check();
  await page.locator(".report-save-state").filter({ hasText: "Saved v2" }).waitFor({ timeout: 30_000 });
  await openReportControls();
  const reportChart = page.locator('.chart-exhibit-canvas[data-chart-lifecycle="ready"]').first();
  await reportChart.waitFor({ timeout: 30_000 });
  await page.locator('.chart-exhibit-table[role="region"]').first().waitFor();
  const reportChartAxe = await new AxeBuilder({ page }).include(".report-proof-stage .chart-exhibit").withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  assert.deepEqual(reportChartAxe.violations, [], "loaded paper chart and exact table have axe violations");
  const paperSources = page.locator(".report-proof-stage .chart-exhibit-sources").first();
  const paperSourceLabel = paperSources.locator(":scope > span");
  const paperSourceLink = paperSources.getByRole("link").first();
  const paperSourceColors = {
    label: await paperSourceLabel.evaluate((element) => getComputedStyle(element).color),
    link: await paperSourceLink.evaluate((element) => getComputedStyle(element).color),
  };
  await paperSourceLink.hover();
  paperSourceColors.link_hover = await paperSourceLink.evaluate((element) => getComputedStyle(element).color);
  assert.deepEqual(paperSourceColors, { label: "rgb(93, 93, 104)", link: "rgb(47, 84, 201)", link_hover: "rgb(47, 84, 201)" });
  evidence.loaded_report_chart_axe = true;
  evidence.paper_source_colors = paperSourceColors;
  await capture("report", true);
  await captureFocused("report-chart-table", page.locator(".report-proof-stage .chart-exhibit").first());
  await page.setViewportSize({ width: 1024, height: 850 });
  await openReportControls();
  const openPaperWidth = (await page.locator(".report-paper").boundingBox())?.width || 0;
  assert.ok(openPaperWidth >= 600, `open Report paper is squeezed at 1024px (${openPaperWidth}px)`);
  const openReportPath = path.join(resultsDir, "report-controls-open-1024.png");
  await page.screenshot({ path: openReportPath, fullPage: true });
  evidence.screenshots.push(openReportPath);
  const reportControls = page.getByRole("button", { name: "Commentary, model and publication" });
  await reportControls.click();
  assert.equal(await reportControls.getAttribute("aria-expanded"), "false");
  const closedPaperWidth = (await page.locator(".report-paper").boundingBox())?.width || 0;
  assert.ok(closedPaperWidth >= 360, `closed Report reading paper is squeezed at 1024px (${closedPaperWidth}px)`);
  const closedReportPath = path.join(resultsDir, "report-reading-closed-1024.png");
  await page.screenshot({ path: closedReportPath, fullPage: true });
  evidence.screenshots.push(closedReportPath);
  evidence.report_1024_paper_widths = { controls_open: openPaperWidth, controls_closed: closedPaperWidth };
  await openReportControls();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await openReportControls();
  await page.locator("#opinion-text").fill("Hold based on the accepted disposable fixture record.");
  await page.locator("#opinion-limitations").fill("Host-control answer keys prove orchestration only, not issuer analysis.");
  await page.locator("#opinion-overrides").fill("None");
  await page.locator("#opinion-rationale").fill("The exact accepted sources, application model and saved analyst revision remain bound.");
  await page.getByRole("button", { name: /Sign opinion on saved v2/ }).click();
  await page.getByText("Opinion signed on saved Draft v2.", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Freeze saved v2" }).click();
  await page.getByRole("button", { name: /FROZEN · Draft v2/ }).waitFor({ timeout: 90_000 });
  workspace = await json(await api.get(draftPath));
  const frozen = workspace.frozen_history.find((item) => item.status === "FROZEN");
  assert.ok(frozen, "worker published no frozen deliverable");
  assert.equal(frozen.payload.authority.accepted_snapshot_id, accepted.id);
  assert.equal(frozen.payload.model.revision_id, revision.id);
  assert.ok(frozen.payload.evidence.some((reference) => reference.source_id === intake.documents[0].source_id));
  evidence.deliverable_id = frozen.id;
  evidence.frozen_preview_digest = frozen.preview_digest;

  const operatorHeaders = { ...headers, "x-forwarded-user": "journey-operator", "x-forwarded-email": "journey-operator", "x-forwarded-groups": "caos-admin" };
  const operator = await request.newContext({ baseURL, extraHTTPHeaders: operatorHeaders });
  const approver = `task10-approver-${browserName}-${suffix}@local.invalid`;
  await json(await operator.post(`/api/admin/cases/${caseId}/bootstrap-approver`, { data: { subject: approver, rationale: "Disposable Task 10 independent filing qualification." } }), 201);
  await operator.dispose();
  const approverHeaders = { ...headers, "x-forwarded-user": approver, "x-forwarded-email": approver };
  const approverApi = await request.newContext({ baseURL, extraHTTPHeaders: approverHeaders });
  const filed = await json(await approverApi.post(`/api/cases/${caseId}/deliverables/by-id/${frozen.id}/approve`, { data: { preview_digest: frozen.preview_digest, input_fingerprint: frozen.input_fingerprint } }));
  assert.equal(filed.status, "FILED");
  assert.equal(filed.approved_by, approver);
  evidence.approved_by = approver;

  for (const format of ["md", "pdf", "xlsx"]) {
    const response = await approverApi.get(`/api/cases/${caseId}/deliverables/by-id/${frozen.id}/export/${format}`);
    assert.equal(response.status(), 200);
    const bytes = await response.body();
    const digest = createHash("sha256").update(bytes).digest("hex");
    assert.equal(response.headers()["x-caos-sha256"], digest);
    const output = path.join(resultsDir, `${frozen.id}.${format}`);
    writeFileSync(output, bytes);
    evidence.exports[format] = { path: output, sha256: digest, size: bytes.length };
  }
  const auditResponse = await approverApi.get(`/api/cases/${caseId}/audit-package`);
  assert.equal(auditResponse.status(), 200);
  const auditBytes = await auditResponse.body();
  const auditDigest = createHash("sha256").update(auditBytes).digest("hex");
  assert.equal(auditResponse.headers()["x-caos-sha256"], auditDigest);
  const auditPath = path.join(resultsDir, `audit-package-${caseId}.zip`);
  writeFileSync(auditPath, auditBytes);
  evidence.audit_package = { path: auditPath, sha256: auditDigest, size: auditBytes.length };
  const receipt = await json(await approverApi.get(`/api/cases/${caseId}/deliverables/by-id/${frozen.id}/receipt`));
  assert.equal(receipt.deliverable_id, frozen.id);
  assert.equal(receipt.approved_by, approver);
  evidence.receipt = receipt;
  await approverApi.dispose();

  evidence.console_errors = errors;
  assert.deepEqual(errors, []);
  evidence.status = "passed";
  console.log(JSON.stringify({ browser: browserName, status: evidence.status, case_id: caseId, deliverable_id: frozen.id, results: resultsDir }));
} catch (error) {
  evidence.status = "failed";
  evidence.error = String(error?.stack || error);
  try { await page.screenshot({ path: path.join(resultsDir, "failure.png"), fullPage: true }); } catch { /* page already closed */ }
  throw error;
} finally {
  writeFileSync(path.join(resultsDir, "qualification.json"), `${JSON.stringify(evidence, null, 2)}\n`);
  await context.close();
  await browser.close();
  await api.dispose();
}
