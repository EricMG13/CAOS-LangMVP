// Real browser/API workflow. No route interception and no direct database writes.
// Point at a configured production stack, or label an isolated injected-provider
// assembly explicitly with CAOS_JOURNEY_EVIDENCE=integration-host-control.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium, firefox, webkit } from "playwright";
import { webkitTeardownRejection } from "./webkit-teardown.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const baseURL = process.env.CAOS_URL;
const secret = process.env.CAOS_EDGE_SECRET;
assert.ok(baseURL && secret, "CAOS_URL and CAOS_EDGE_SECRET are required");
const evidenceMode = process.env.CAOS_JOURNEY_EVIDENCE || "live-provider";
assert.ok(["live-provider", "integration-host-control"].includes(evidenceMode));
const browserName = process.env.CAOS_BROWSER || "chromium";
const python = process.env.CAOS_PYTHON || path.join(root, "caos/server/.venv/bin/python");
const out = process.env.CAOS_JOURNEY_OUT || path.join(root, "caos/frontend/test-results/production-journey", `${browserName}-${Date.now()}`);
mkdirSync(out, { recursive: true });
const subjects = { analyst: process.env.CAOS_ANALYST_USER || "journey-analyst", operator: process.env.CAOS_OPERATOR_USER || "journey-operator", approver: process.env.CAOS_APPROVER_USER || "journey-approver", reader: process.env.CAOS_READER_USER || "journey-reader" };
assert.equal(new Set(Object.values(subjects)).size, 4, "journey actors must be distinct");
const group = { analyst: "caos-analyst", operator: "caos-admin", approver: "caos-approver", reader: "caos-reader" };
const headers = (actor) => ({ "x-edge-authorization": secret, "x-forwarded-user": subjects[actor], "x-forwarded-email": subjects[actor], "x-forwarded-groups": group[actor] });
const browser = await ({ chromium, firefox, webkit })[browserName].launch();
const contexts = {};
const pages = {};
const steps = [];
const errors = [];
const observed = [];
const writes = new Map();
const teardownRejections = [];
let currentStep = "initialization";
let result = { status: "FAILED", evidence: evidenceMode, browser: browserName };
const hash = (bytes) => createHash("sha256").update(bytes).digest("hex");
const checked = async (response, expected = 200) => {
  if (response.status() !== expected) assert.fail(`${currentStep}: ${new URL(response.url()).pathname}: expected ${expected}, got ${response.status()}: ${(await response.text()).slice(0, 1200)}`);
  return response.json();
};
const act = async (page, suffix, action, status) => {
  const [response] = await Promise.all([
    page.waitForResponse((value) => new URL(value.url()).pathname.endsWith(suffix) && value.request().method() !== "GET"),
    action(),
  ]);
  return checked(response, status);
};
const step = (name) => { currentStep = name; steps.push({ step: name, at: new Date().toISOString() }); console.log(name); };
const until = async (read, done, label, ms = 180000) => {
  const deadline = Date.now() + ms;
  while (Date.now() < deadline) {
    const value = await read();
    if (done(value)) return value;
    if (["failed", "FAILED"].includes(value.status)) assert.fail(`${label}: ${JSON.stringify(value.error)}`);
    await new Promise((resolve) => setTimeout(resolve, 1500));
  }
  assert.fail(`${label} did not complete within ${ms}ms`);
};
try {
  for (const actor of Object.keys(subjects)) {
    const context = await browser.newContext({ baseURL, extraHTTPHeaders: headers(actor) });
    await context.tracing.start({ screenshots: true, snapshots: true });
    const page = await context.newPage();
    page.setDefaultTimeout(30000);
    const responded = new Map();
    page.on("pageerror", (error) => { const teardown = webkitTeardownRejection(error.message, { browserName, baseURL, responded }); if (teardown) teardownRejections.push({ actor, ...teardown }); else errors.push({ actor, error: error.message }); });
    page.on("request", (request) => { if (["POST", "PUT"].includes(request.method()) && request.headers()["content-type"]?.includes("application/json")) writes.set(`${actor}:${new URL(request.url()).pathname}`, request.postDataJSON()); });
    page.on("response", (response) => { if (response.request().resourceType() !== "document") responded.set(response.url(), response.status()); const url = new URL(response.url()); if (url.pathname.startsWith("/api/")) observed.push({ actor, method: response.request().method(), path: url.pathname, status: response.status() }); });
    contexts[actor] = context; pages[actor] = page;
    const who = await checked(await context.request.get("/api/me"));
    assert.equal(who.subject, subjects[actor]);
  }
  const analyst = pages.analyst;
  step("documents in through the browser");
  let files;
  if (process.env.CAOS_PACK_DIR) files = readdirSync(process.env.CAOS_PACK_DIR).sort().map((name) => ({ name, mimeType: "application/octet-stream", buffer: readFileSync(path.join(process.env.CAOS_PACK_DIR, name)) }));
  else {
    const encoded = execFileSync(python, ["-c", "import sys,json,base64;sys.path.insert(0,'qa');from pathlib import Path;from golden_journeys import packs;print(json.dumps([{'name':n,'mimeType':t,'base64':base64.b64encode(b).decode()} for n,b,t in packs(Path('caos/server'),sys.argv[1])['FULL_CREDIT']]))", `Northstar-${randomUUID().slice(0, 8)}`], { cwd: root, encoding: "utf8" });
    files = JSON.parse(encoded).map(({ base64, ...file }) => ({ ...file, buffer: Buffer.from(base64, "base64") }));
  }
  await analyst.goto("/portfolio/");
  await analyst.locator(".cases-register .panel-meta").filter({ hasText: /^\d+ of \d+$/ }).waitFor();
  await analyst.locator("#intake-files").setInputFiles(files);
  const intake = await act(analyst, "/api/intake", () => analyst.getByRole("button", { name: /^Analyze \d+ documents?$/ }).click(), 201);
  assert.ok(intake.run && intake.case_id);
  const caseId = intake.case_id;
  result.case_id = caseId; result.run_id = intake.run.id;
  await analyst.getByRole("heading", { name: /Intake|Document|Disposition/i }).first().waitFor();
  step("execution and exact acceptance");
  await analyst.goto(`/run/?case=${caseId}&run=${intake.run.id}`);
  const run = await until(async () => checked(await contexts.analyst.request.get(`/api/runs/${intake.run.id}`)), (value) => value.status === "succeeded" || value.status === "paused", "analysis");
  if (run.status === "paused") {
    assert.equal(run.error?.code, "PLAN_APPROVAL_REQUIRED");
    await analyst.getByRole("button", { name: /Approve.*plan/i }).click();
    await until(async () => checked(await contexts.analyst.request.get(`/api/runs/${intake.run.id}`)), (value) => value.status === "succeeded", "research execution");
  }
  assert.ok(run.provider_identity, "run response omitted provider provenance");
  if (evidenceMode === "live-provider") assert.ok(!/host.?control/i.test(run.provider_identity.provider_name), "live journey cannot use host control");
  result.provider_identity = run.provider_identity;
  await analyst.getByRole("button", { name: "Accept analytical snapshot" }).click();
  const snapshot = await act(analyst, `/api/runs/${intake.run.id}/accept`, () => analyst.getByRole("dialog", { name: "Accept analytical snapshot" }).getByRole("button", { name: "Accept analytical snapshot" }).click(), 200);
  assert.equal(snapshot.run_id, intake.run.id);
  step("first independent approver through Admin");
  const operator = pages.operator;
  await operator.goto("/admin/");
  await operator.getByLabel("Case ID", { exact: true }).fill(caseId);
  await operator.getByLabel("Independent approver subject").fill(subjects.approver);
  await operator.getByLabel("Audit rationale").fill("Isolated enterprise workflow acceptance test");
  const grant = await act(operator, `/api/admin/cases/${caseId}/bootstrap-approver`, () => operator.getByRole("button", { name: "Provision first approver" }).click(), 201);
  assert.equal(grant.role, "APPROVER"); assert.equal(grant.subject, subjects.approver);
  const grantReplay = await checked(await contexts.operator.request.post(`/api/admin/cases/${caseId}/bootstrap-approver`, { data: { subject: subjects.approver, rationale: "Isolated enterprise workflow acceptance test" } }), 201);
  assert.deepEqual(grantReplay, grant, "bootstrap replay changed the original receipt");
  assert.equal((await contexts.operator.request.get(`/api/cases/${caseId}`)).status(), 404, "operator gained case read access");
  // Ordinary governed membership grants allow the reader and exercise the
  // signer-independent check beyond the initial analyst authorization gate.
  for (const [subject, role] of [[subjects.reader, "READER"], [subjects.analyst, "APPROVER"]]) await checked(await contexts.approver.request.post(`/api/cases/${caseId}/members`, { data: { subject, role } }), 201);
  step("real model worker and signed analyst revision");
  await analyst.goto(`/model/?case=${caseId}`);
  const readiness = await checked(await contexts.analyst.request.get(`/api/cases/${caseId}/model`));
  assert.ok(["READY_TO_BUILD", "READY"].includes(readiness.status), `model authority refused: ${JSON.stringify(readiness.blockers)}`);
  // Acceptance may already have queued and completed this exact build before
  // the model page opens. Exercise the idempotent HTTP admission in both cases.
  const queued = await checked(await contexts.analyst.request.post(`/api/cases/${caseId}/models`, { data: {} }), 202);
  assert.equal(typeof queued.id, "string");
  const build = await until(async () => checked(await contexts.analyst.request.get(`/api/cases/${caseId}/models/${queued.id}`)), (value) => value.status === "READY", "model worker");
  result.build_id = build.id;
  await analyst.getByRole("button", { name: "Refresh", exact: true }).click();
  const assumption = analyst.locator('input[aria-label*="FY"][aria-label*="BASE"]:enabled').first();
  await assumption.waitFor();
  const value = Number(await assumption.inputValue());
  const stepValue = Number(await assumption.getAttribute("step")) || 0.001;
  const maximum = Number(await assumption.getAttribute("max"));
  await assumption.fill(String(Number.isFinite(maximum) && value + stepValue > maximum ? value - stepValue : value + stepValue));
  await assumption.press("Enter");
  await analyst.getByLabel("Sign-Off Note").fill("Acceptance test: one bounded forecast assumption change, exact preview reviewed.");
  const revision = await act(analyst, `/api/cases/${caseId}/model-revisions/sign-off`, () => analyst.getByRole("button", { name: "Save model version" }).click(), 201);
  result.model_revision_id = revision.id;
  const modelSignPath = `/api/cases/${caseId}/model-revisions/sign-off`;
  await checked(await contexts.analyst.request.post(modelSignPath, { data: writes.get(`analyst:${modelSignPath}`) }), 409);
  step("signed model XLSX export and exact download");
  const revisionExport = await until(async () => {
    const current = await checked(await contexts.reader.request.get(`/api/cases/${caseId}/model-revisions/export-statuses`));
    const entry = current.exports.find((item) => item.revision_id === revision.id);
    assert.ok(entry, "signed revision missing from export statuses");
    return entry.export;
  }, (value) => value.status === "READY", "signed model export");
  const revisionDownload = await contexts.reader.request.get(`/api/cases/${caseId}/model-revisions/${revision.id}/download`);
  assert.equal(revisionDownload.status(), 200);
  const revisionBytes = await revisionDownload.body();
  assert.equal(hash(revisionBytes), revisionExport.sha256);
  assert.equal(revisionDownload.headers()["x-caos-sha256"], revisionExport.sha256);
  assert.equal(revisionBytes.length, revisionExport.size);
  result.model_revision_export = revisionExport;
  writeFileSync(path.join(out, "model-revision.xlsx"), revisionBytes);
  step("browser draft, exact evidence and opinion sign-off");
  await analyst.goto(`/report/?case=${caseId}`);
  const templatePathway = await analyst.getByLabel("Pathway template").inputValue();
  assert.equal(templatePathway, run.plan.pathway);
  const nav = analyst.getByRole("navigation", { name: "Deliverable sections" }).getByRole("button");
  const save = analyst.waitForResponse((response) => response.request().method() === "PUT" && new URL(response.url()).pathname.endsWith(`/deliverables/${templatePathway}/draft`));
  for (let index = 0; index < await nav.count(); index += 1) {
    await nav.nth(index).click();
    const editor = analyst.locator('.report-compose textarea[id^="narrative-"]');
    if (await editor.count()) await editor.fill(`Acceptance test opinion section ${index + 1}: supplied evidence and explicit limitations reviewed.`);
  }
  await checked(await save, 201);
  await nav.first().click();
  await analyst.locator(".evidence-inspector > summary").click();
  await analyst.locator(".evidence-source-list details > summary").first().click();
  const savedDraft = await act(analyst, `/deliverables/${templatePathway}/draft`, () => analyst.getByRole("button", { name: "Cite block", exact: true }).first().click(), 201);
  assert.ok(savedDraft.current.content.blocks.some((block) => block.citations?.length), "exact citation was not persisted");
  const draftPath = `/api/cases/${caseId}/deliverables/${templatePathway}/draft`;
  const staleDraft = await checked(await contexts.analyst.request.put(draftPath, { data: writes.get(`analyst:${draftPath}`) }), 409);
  assert.equal(staleDraft.detail.code, "DELIVERABLE_VERSION_CONFLICT");
  for (const [id, text] of [["opinion-text", "Hold for committee review"], ["opinion-limitations", "Synthetic integration pack; not investment advice"], ["opinion-overrides", "None"], ["opinion-rationale", "Workflow acceptance test on exact source and model authorities"]]) await analyst.locator(`#${id}`).fill(text);
  await act(analyst, `/deliverables/${templatePathway}/opinion`, () => analyst.getByRole("button", { name: /Sign opinion on saved/ }).click(), 201);
  const opinionPath = `/api/cases/${caseId}/deliverables/${templatePathway}/opinion`;
  const staleOpinion = await checked(await contexts.analyst.request.post(opinionPath, { data: writes.get(`analyst:${opinionPath}`) }), 409);
  assert.equal(staleOpinion.detail.code, "OPINION_HEAD_CONFLICT");
  step("asynchronous freeze and independent filing");
  const job = await act(analyst, `/deliverables/${templatePathway}/freeze`, () => analyst.getByRole("button", { name: /Freeze saved/ }).click(), 202);
  await until(async () => checked(await contexts.analyst.request.get(`/api/cases/${caseId}/deliverables/freeze-jobs/${job.job_id}`)), (value) => value.status === "PUBLISHED", "freeze worker");
  await analyst.getByText(/Immutable FROZEN review/).waitFor();
  const ws = await checked(await contexts.analyst.request.get(`/api/cases/${caseId}/deliverables/${templatePathway}/draft`));
  const frozen = ws.frozen_history.find((item) => item.id === job.deliverable_id) || ws.frozen_history.at(-1);
  const fileBody = { preview_digest: frozen.preview_digest, input_fingerprint: frozen.input_fingerprint };
  const filePath = `/api/cases/${caseId}/deliverables/by-id/${frozen.id}/approve`;
  const stalePreview = await checked(await contexts.approver.request.post(filePath, { data: { ...fileBody, preview_digest: "0".repeat(64) } }), 409);
  assert.equal(stalePreview.detail.code, "DELIVERABLE_STALE_PREVIEW");
  const signerRefusal = await contexts.analyst.request.post(`/api/cases/${caseId}/deliverables/by-id/${frozen.id}/approve`, { data: fileBody });
  assert.equal(signerRefusal.status(), 403); // typed independence refusal, after case approver authorization
  assert.equal((await signerRefusal.json()).detail.code, "APPROVER_NOT_INDEPENDENT");
  await checked(await contexts.analyst.request.post(`/api/cases/${caseId}/members`, { data: { subject: subjects.approver, role: "READER" } }), 201);
  assert.equal((await contexts.approver.request.post(filePath, { data: fileBody })).status(), 403, "revoked case standing retained filing permission");
  await checked(await contexts.analyst.request.post(`/api/cases/${caseId}/members`, { data: { subject: subjects.approver, role: "APPROVER" } }), 201);
  const approver = pages.approver;
  await approver.goto(`/report/?case=${caseId}`);
  await approver.getByRole("button", { name: new RegExp(`FROZEN · Draft v${frozen.draft_version}`) }).click();
  const filed = await act(approver, `/deliverables/by-id/${frozen.id}/approve`, () => approver.getByRole("button", { name: "File exact Frozen version" }).click(), 200);
  assert.equal(filed.approved_by, subjects.approver); assert.equal(filed.status, "FILED");
  result.deliverable_id = filed.id;
  await pages.reader.goto(`/report/?case=${caseId}`);
  assert.equal(await pages.reader.getByRole("button", { name: "File exact Frozen version" }).count(), 0);
  assert.equal((await contexts.reader.request.post(`/api/cases/${caseId}/deliverables/by-id/${filed.id}/approve`, { data: fileBody })).status(), 403);
  step("exact exports, detached receipt and offline audit verification");
  const receipt = await checked(await contexts.approver.request.get(`/api/cases/${caseId}/deliverables/by-id/${filed.id}/receipt`));
  const replay = await checked(await contexts.approver.request.post(filePath, { data: fileBody }), 409);
  assert.equal(replay.detail.code, "RESUME_NOT_APPLIED");
  assert.deepEqual(await checked(await contexts.approver.request.get(`/api/cases/${caseId}/deliverables/by-id/${filed.id}/receipt`)), receipt, "file replay changed the detached receipt");
  writeFileSync(path.join(out, "receipt.json"), JSON.stringify(receipt, null, 2));
  for (const format of ["md", "pdf", "xlsx"]) {
    const response = await contexts.reader.request.get(`/api/cases/${caseId}/deliverables/by-id/${filed.id}/export/${format}`);
    assert.equal(response.status(), 200);
    const bytes = await response.body();
    assert.equal(hash(bytes), frozen.exports[format].sha256); assert.equal(response.headers()["x-caos-sha256"], hash(bytes));
    writeFileSync(path.join(out, `filed.${format}`), bytes);
  }
  step("withdrawn source refusal preserves filed bytes");
  const citedSource = savedDraft.current.content.blocks.flatMap((block) => block.citations || [])[0].source_id;
  const withdrawn = await checked(await contexts.analyst.request.post(`/api/cases/${caseId}/sources/${citedSource}/withdraw`));
  assert.equal(withdrawn.withdrawn, true);
  const staleEvidence = await checked(await contexts.analyst.request.put(draftPath, { data: { ...writes.get(`analyst:${draftPath}`), expected_version: savedDraft.current.version } }), 422);
  assert.equal(staleEvidence.detail.code, "EVIDENCE_SOURCE_WITHDRAWN");
  const historicalSource = await checked(await contexts.reader.request.get(`/api/cases/${caseId}/sources/${citedSource}`));
  assert.equal(historicalSource.withdrawn, true);
  const historicalExport = await contexts.reader.request.get(`/api/cases/${caseId}/deliverables/by-id/${filed.id}/export/md`);
  assert.equal(historicalExport.status(), 200);
  assert.equal(hash(await historicalExport.body()), frozen.exports.md.sha256);
  const audit = await contexts.analyst.request.get(`/api/cases/${caseId}/audit-package`);
  assert.equal(audit.status(), 200);
  const auditPath = path.join(out, "audit-package.zip"); writeFileSync(auditPath, await audit.body());
  const verified = execFileSync(python, [path.join(root, "caos/server/caos/audit/verify_package.py"), auditPath, "--json"], { encoding: "utf8" });
  writeFileSync(path.join(out, "audit-verification.json"), verified);
  assert.equal(JSON.parse(verified.trim().split("\n").at(-1)).ok, true);
  assert.deepEqual(errors, []);
  assert.equal(observed.filter((item) => item.status >= 500 || item.status === 429).length, 0, "unexpected server failures or rate refusals");
  result.status = "PASS";
} catch (error) {
  result.error = `${currentStep}: ${error.message}`;
  for (const [actor, page] of Object.entries(pages)) await page.screenshot({ path: path.join(out, `${actor}-failure.png`), fullPage: true }).catch(() => {});
  throw error;
} finally {
  writeFileSync(path.join(out, "result.json"), JSON.stringify({ ...result, steps, errors, requests: observed, webkit_teardown_rejections: teardownRejections }, null, 2));
  for (const [actor, context] of Object.entries(contexts)) { await context.tracing.stop({ path: path.join(out, `${actor}-trace.zip`) }); await context.close(); }
  await browser.close();
  console.log(JSON.stringify({ ...result, out }));
}
