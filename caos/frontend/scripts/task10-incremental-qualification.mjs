import assert from "node:assert/strict";
import { createHash, randomUUID } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { chromium, request } from "playwright";

const baseURL = process.env.CAOS_URL;
assert.ok(baseURL, "CAOS_URL must explicitly name the disposable Task 10 harness");
const harnessURL = new URL(baseURL);
assert.ok(["127.0.0.1", "localhost", "[::1]"].includes(harnessURL.hostname), "CAOS_URL must be loopback-only");
assert.notEqual(harnessURL.port || (harnessURL.protocol === "https:" ? "443" : "80"), "8000", "CAOS_URL must not target the excluded port-8000 legacy app");
const edge = process.env.CAOS_EDGE_SECRET;
assert.ok(edge, "CAOS_EDGE_SECRET is required");
const suffix = randomUUID().slice(0, 8);
const subject = `task10-incremental-${suffix}@local.invalid`;
const headers = {
  "x-edge-authorization": edge,
  "x-forwarded-user": subject,
  "x-forwarded-email": subject,
  "x-forwarded-groups": "caos-analyst",
};
const resultsDir = path.resolve(process.env.CAOS_RESULTS_DIR || "test-results", "task10-incremental");
mkdirSync(resultsDir, { recursive: true });
const evidence = {
  schema_version: "caos.task10-incremental-qualification.v1",
  fixture_authority: "actual disposable accepted Full Credit followed by accepted Earnings Update using host-control report fixtures",
  subject,
  exports: {},
};

async function checkedJson(response, expected = 200) {
  const body = await response.text();
  assert.equal(response.status(), expected, `${response.url()} answered ${response.status()}: ${body.slice(0, 800)}`);
  return JSON.parse(body);
}

async function waitFor(read, done, message, attempts = 360) {
  let value;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    value = await read();
    if (done(value)) return value;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`${message}: ${JSON.stringify(value).slice(0, 1200)}`);
}

async function readyModel(api, caseId) {
  let readiness = await waitFor(
    async () => checkedJson(await api.get(`/api/cases/${caseId}/model`)),
    (value) => ["READY", "READY_TO_BUILD", "FAILED", "NOT_READY"].includes(value.status),
    "model readiness did not settle",
  );
  if (readiness.status === "READY_TO_BUILD") {
    await checkedJson(await api.post(`/api/cases/${caseId}/models`), 202);
    readiness = await waitFor(
      async () => checkedJson(await api.get(`/api/cases/${caseId}/model`)),
      (value) => ["READY", "FAILED"].includes(value.status),
      "model build did not settle",
    );
  }
  assert.equal(readiness.status, "READY", JSON.stringify(readiness.blockers));
  return readiness.build;
}

const api = await request.newContext({ baseURL, extraHTTPHeaders: headers });
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ baseURL, extraHTTPHeaders: headers, viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const errors = [];
page.on("pageerror", (error) => errors.push(String(error)));

try {
  const issuer = `Task10 Incremental ${suffix} Holdings`;
  const form = new FormData();
  form.append("files", new Blob([`${issuer}\nFORM 10-K\nAnnual report for FY2025\nRevenue 1160\nAdjusted EBITDA 222\nTotal debt 630\nCash 75\n`], { type: "text/plain" }), "annual-report.txt");
  form.append("files", new Blob([`${issuer}\nFORM 10-Q\nQuarterly report for Q1 2026\nRevenue 300\nAdjusted EBITDA 59\n`], { type: "text/plain" }), "quarterly-q1.txt");
  form.append("files", new Blob([`CREDIT AGREEMENT\namong ${issuer}, the lenders and administrative agent\nTerm Loan B and Revolving Credit Facility\n`], { type: "text/plain" }), "credit-agreement.txt");
  const intake = await checkedJson(await api.post("/api/intake", { multipart: form }), 201);
  assert.equal(intake.route.pathway, "FULL_CREDIT");
  assert.equal(intake.route.depth, "full");
  const caseId = intake.case.id;
  evidence.case_id = caseId;
  const baseRun = await waitFor(
    async () => checkedJson(await api.get(`/api/runs/${intake.run.id}`)),
    (value) => ["succeeded", "failed"].includes(value.status),
    "base Full Credit run did not settle",
  );
  assert.equal(baseRun.status, "succeeded");
  const baseSnapshot = await checkedJson(await api.post(`/api/runs/${baseRun.id}/accept`));
  const baseBuild = await readyModel(api, caseId);
  assert.equal(baseBuild.accepted_snapshot_id, baseSnapshot.id);
  evidence.base = { run_id: baseRun.id, snapshot_id: baseSnapshot.id, build_id: baseBuild.id, build_payload_digest: baseBuild.payload_digest };

  for (const [filename, content] of [
    ["quarterly-q2.txt", `${issuer}\nFORM 10-Q\nQuarterly report for Q2 2026\nRevenue 330\nAdjusted EBITDA 64\nFull-year guidance reaffirmed.\n`],
    ["earnings-release.txt", `${issuer}\nEARNINGS RELEASE\nQ2 2026 results and updated guidance\nRevenue 330\nAdjusted EBITDA 64\n`],
  ]) {
    await checkedJson(await api.post(`/api/cases/${caseId}/sources`, { multipart: { file: { name: filename, mimeType: "text/plain", buffer: Buffer.from(content) } } }), 201);
  }
  const incrementalStart = await checkedJson(await api.post(`/api/cases/${caseId}/runs`, { data: { pathway: "EARNINGS_UPDATE", depth: "full", focus_questions: [] } }), 201);
  const incrementalRun = await waitFor(
    async () => checkedJson(await api.get(`/api/runs/${incrementalStart.id}`)),
    (value) => ["succeeded", "failed"].includes(value.status),
    "incremental Earnings Update run did not settle",
  );
  assert.equal(incrementalRun.status, "succeeded");
  const incrementalSnapshot = await checkedJson(await api.post(`/api/runs/${incrementalRun.id}/accept`));
  assert.equal(incrementalSnapshot.previous_snapshot_id, baseSnapshot.id);
  const overlayBuild = await readyModel(api, caseId);
  assert.equal(overlayBuild.accepted_snapshot_id, incrementalSnapshot.id);
  assert.notEqual(overlayBuild.id, baseBuild.id);
  evidence.incremental = {
    pathway: "EARNINGS_UPDATE",
    run_id: incrementalRun.id,
    snapshot_id: incrementalSnapshot.id,
    previous_snapshot_id: incrementalSnapshot.previous_snapshot_id,
    build_id: overlayBuild.id,
    build_payload_digest: overlayBuild.payload_digest,
  };

  const draftPath = `/api/cases/${caseId}/deliverables/EARNINGS_UPDATE/draft`;
  await page.goto(`/report/?case=${caseId}&run=${incrementalRun.id}`, { waitUntil: "networkidle" });
  await page.locator(".report-generated").waitFor({ timeout: 30_000 });
  let workspace = await checkedJson(await api.get(draftPath));
  assert.equal(workspace.template.template_version, "caos.deliverable-template.v2");
  assert.equal(workspace.model_eligibility.application_build.build_id, overlayBuild.id);
  assert.equal(workspace.model_eligibility.active_revision, null);
  const controls = page.getByRole("button", { name: "Commentary, model and publication" });
  if (await controls.getAttribute("aria-expanded") !== "true") await controls.click();
  const fallback = page.getByLabel(/I acknowledge fallback to the Application Model Build/);
  await fallback.check();
  await page.locator(".report-save-state").filter({ hasText: "Saved v1" }).waitFor({ timeout: 30_000 });
  await page.getByRole("button", { name: "Add commentary", exact: true }).first().click();
  await page.getByLabel("Analyst commentary", { exact: true }).fill("Incremental disposable review: preserve the prior model and bind only the accepted Earnings Update effect.");
  await page.getByLabel("Analyst judgment", { exact: true }).check();
  await page.locator(".report-save-state").filter({ hasText: "Saved v2" }).waitFor({ timeout: 30_000 });
  if (await controls.getAttribute("aria-expanded") !== "true") await controls.click();
  assert.equal(await controls.getAttribute("aria-expanded"), "true");
  await page.locator("#opinion-text").fill("Hold following the accepted disposable Earnings Update.");
  await page.locator("#opinion-limitations").fill("Host-control answer keys prove incremental orchestration only.");
  await page.locator("#opinion-overrides").fill("None");
  await page.locator("#opinion-rationale").fill("The prior Full Credit model remains unchanged and the new accepted effect is separately pinned.");
  await page.getByRole("button", { name: /Sign opinion on saved v2/ }).click();
  await page.getByText("Opinion signed on saved Draft v2.", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Freeze saved v2" }).click();
  await page.getByRole("button", { name: /FROZEN · Draft v2/ }).waitFor({ timeout: 90_000 });
  workspace = await checkedJson(await api.get(draftPath));
  const frozen = workspace.frozen_history.find((item) => item.status === "FROZEN");
  assert.ok(frozen, "incremental v2 worker published no frozen deliverable");
  assert.equal(frozen.payload.authority.accepted_snapshot_id, incrementalSnapshot.id);
  assert.equal(frozen.payload.model.build_id, overlayBuild.id);
  assert.equal(frozen.payload.model.model_authority.relationship, "CURRENT_ACCEPTED_OVERLAY");
  assert.equal(frozen.payload.model.model_authority.snapshot_id, incrementalSnapshot.id);
  assert.equal(frozen.payload.model.pathway_effects.length, 1);
  assert.equal(frozen.payload.model.pathway_effects[0].pathway, "EARNINGS_UPDATE");
  assert.equal(frozen.payload.model.pathway_effects[0].base_model.build_id, baseBuild.id);
  assert.ok(frozen.payload.content.document_sections.some((section) => section.title === "Unchanged prior-model base values"));
  assert.ok(frozen.payload.content.document_sections.some((section) => section.body?.includes("do not recalculate the complete forecast")));
  evidence.incremental.deliverable_id = frozen.id;
  evidence.incremental.frozen_preview_digest = frozen.preview_digest;
  await page.locator(".report-proof-stage").screenshot({ path: path.join(resultsDir, "incremental-v2-report.png") });

  const operator = await request.newContext({ baseURL, extraHTTPHeaders: { ...headers, "x-forwarded-user": "journey-operator", "x-forwarded-email": "journey-operator", "x-forwarded-groups": "caos-admin" } });
  const approver = `task10-incremental-approver-${suffix}@local.invalid`;
  await checkedJson(await operator.post(`/api/admin/cases/${caseId}/bootstrap-approver`, { data: { subject: approver, rationale: "Disposable Task 10 incremental independent filing qualification." } }), 201);
  await operator.dispose();
  const approverApi = await request.newContext({ baseURL, extraHTTPHeaders: { ...headers, "x-forwarded-user": approver, "x-forwarded-email": approver } });
  const filed = await checkedJson(await approverApi.post(`/api/cases/${caseId}/deliverables/by-id/${frozen.id}/approve`, { data: { preview_digest: frozen.preview_digest, input_fingerprint: frozen.input_fingerprint } }));
  assert.equal(filed.status, "FILED");
  assert.equal(filed.approved_by, approver);
  evidence.incremental.approved_by = approver;
  for (const format of ["md", "pdf", "xlsx"]) {
    const response = await approverApi.get(`/api/cases/${caseId}/deliverables/by-id/${frozen.id}/export/${format}`);
    assert.equal(response.status(), 200);
    const bytes = await response.body();
    const sha256 = createHash("sha256").update(bytes).digest("hex");
    assert.equal(response.headers()["x-caos-sha256"], sha256);
    const output = path.join(resultsDir, `${frozen.id}.${format}`);
    writeFileSync(output, bytes);
    evidence.exports[format] = { path: output, sha256, size: bytes.length };
  }
  const auditResponse = await approverApi.get(`/api/cases/${caseId}/audit-package`);
  assert.equal(auditResponse.status(), 200);
  const auditBytes = await auditResponse.body();
  const auditSha256 = createHash("sha256").update(auditBytes).digest("hex");
  assert.equal(auditResponse.headers()["x-caos-sha256"], auditSha256);
  const auditPath = path.join(resultsDir, `audit-package-${caseId}.zip`);
  writeFileSync(auditPath, auditBytes);
  evidence.audit_package = { path: auditPath, sha256: auditSha256, size: auditBytes.length };
  const receipt = await checkedJson(await approverApi.get(`/api/cases/${caseId}/deliverables/by-id/${frozen.id}/receipt`));
  assert.equal(receipt.approved_by, approver);
  assert.equal(receipt.deliverable_id, frozen.id);
  evidence.receipt = receipt;
  await approverApi.dispose();
  evidence.console_errors = errors;
  assert.deepEqual(errors, []);
  evidence.status = "passed";
  console.log(JSON.stringify({ status: evidence.status, case_id: caseId, base_build_id: baseBuild.id, overlay_build_id: overlayBuild.id, deliverable_id: frozen.id, results: resultsDir }));
} catch (error) {
  evidence.status = "failed";
  evidence.error = String(error?.stack || error);
  try { await page.screenshot({ path: path.join(resultsDir, "failure.png"), fullPage: true }); } catch { /* browser already closed */ }
  throw error;
} finally {
  writeFileSync(path.join(resultsDir, "incremental-qualification.json"), `${JSON.stringify(evidence, null, 2)}\n`);
  await context.close();
  await browser.close();
  await api.dispose();
}
