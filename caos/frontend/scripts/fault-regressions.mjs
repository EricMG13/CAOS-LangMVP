// Regression proof for the 2026-09-07 confidence findings. Run against
// qa/serve_browser_integration.py; the provider/scanner are explicit fixtures.
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { chromium, firefox, webkit } from "playwright";

const baseURL = process.env.CAOS_URL || "http://127.0.0.1:19189";
const engine = process.env.CAOS_BROWSER || "chromium";
const browser = await ({ chromium, firefox, webkit })[engine].launch();
const context = await browser.newContext({ baseURL, viewport: { width: 1440, height: 1000 }, extraHTTPHeaders: {
  "x-edge-authorization": process.env.CAOS_EDGE_SECRET || "review-fixture-only-secret",
  "x-forwarded-user": `fault-fixes-${randomUUID()}`,
  "x-forwarded-groups": "caos-analyst",
} });
const api = context.request;
const checked = async (response, status = 200) => {
  assert.equal(response.status(), status, await response.text());
  return response.json();
};
const poll = async (path, expected) => {
  for (let attempt = 0; attempt < 120; attempt++) {
    const record = await checked(await api.get(path));
    if (record.status === expected) return record;
    assert.ok(!["failed", "FAILED"].includes(record.status), JSON.stringify(record));
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  assert.fail(`Timed out: ${path}`);
};

try {
  const record = await checked(await api.post("/api/cases", { data: {
    name: "Fault regression", issuer: "Regression Holdings", sector: "Services",
  } }), 201);
  const caseId = record.id;
  const page = await context.newPage();
  const errors = [];
  context.on("page", (opened) => opened.on("pageerror", (error) => errors.push(error.message)));
  page.on("pageerror", (error) => errors.push(error.message));
  const openPublicationControls = async (target) => {
    const toggle = target.getByRole("button", { name: "Commentary, model and publication" });
    if (await toggle.getAttribute("aria-expanded") !== "true") await toggle.click();
    assert.equal(await toggle.getAttribute("aria-expanded"), "true");
  };
  const reportURL = `/report/?case=${caseId}`;
  await page.goto(reportURL);
  await openPublicationControls(page);
  await page.locator("#opinion-text").fill("PARENT UNSIGNED OPINION");
  await page.getByRole("link", { name: "Portfolio", exact: true }).click();
  const discard = page.getByRole("dialog").filter({ hasText: "Discard changes" });
  await discard.waitFor();
  await discard.getByRole("button", { name: "Keep editing" }).click();
  assert.equal(await page.locator("#opinion-text").inputValue(), "PARENT UNSIGNED OPINION");
  const parentId = await page.evaluate(() => sessionStorage.getItem("caos:tab-id"));
  assert.ok(parentId);

  const [child] = await Promise.all([page.waitForEvent("popup"), page.evaluate(() => window.open(location.href))]);
  await openPublicationControls(child);
  await child.locator("#opinion-text").fill("CHILD UNSIGNED OPINION");
  const childId = await child.evaluate(() => sessionStorage.getItem("caos:tab-id"));
  assert.notEqual(childId, parentId, "a cloned tab reused live recovery ownership");
  const copies = await page.evaluate(() => Object.entries(localStorage).filter(([key]) => key.startsWith("caos:report-recovery:")));
  assert.equal(copies.length, 2);
  assert.ok(copies.some(([, raw]) => raw.includes("PARENT UNSIGNED OPINION")));
  assert.ok(copies.some(([, raw]) => raw.includes("CHILD UNSIGNED OPINION")));
  await child.close();

  // A reload must reclaim the old document's slot, not strand its recovery.
  page.on("dialog", (dialog) => dialog.accept());
  await page.reload();
  await openPublicationControls(page);
  await page.getByRole("button", { name: "Restore copy", exact: true }).click();
  assert.equal(await page.locator("#opinion-text").inputValue(), "PARENT UNSIGNED OPINION");
  assert.equal(await page.evaluate(() => sessionStorage.getItem("caos:tab-id")), parentId);
  console.log("PASS F6/F7: unsigned opinion guarded, recovered after reload, and isolated from cloned tabs");

  // Controlled response ordering with real UI and case context, not fabricated filing authority.
  const workspace = await checked(await api.get(`/api/cases/${caseId}/deliverables/FULL_CREDIT/draft`));
  const frozen = (id, version) => ({ id, case_id: caseId, pathway: "FULL_CREDIT", draft_version: version,
    status: "FILED", frozen_by: "fixture-signer", frozen_at: "2026-09-07T00:00:00Z", approved_by: "fixture-approver",
    approved_at: "2026-09-07T01:00:00Z", signed_by: "fixture-signer", digest: "a".repeat(64),
    payload: { template: workspace.template, content: { blocks: [] }, evidence: [] }, exports: {},
  });
  const first = frozen("receipt-order-a", 91), second = frozen("receipt-order-b", 92);
  const receiptPage = await context.newPage();
  await receiptPage.route(`**/api/cases/${caseId}/deliverables/FULL_CREDIT/draft`, (route) => route.fulfill({ json: {
    ...workspace, frozen_history: [first, second],
  } }));
  let releaseA, startedA, requestA;
  const receiptRequests = [];
  const heldA = new Promise((resolve) => { releaseA = resolve; });
  const waitingA = new Promise((resolve) => { startedA = resolve; });
  await receiptPage.route((url) => url.pathname.startsWith(`/api/cases/${caseId}/deliverables/by-id/`) && url.pathname.endsWith("/receipt"), async (route) => {
    receiptRequests.push(route.request().url());
    const isA = route.request().url().includes(first.id);
    if (isA) { requestA = route.request(); startedA(); await heldA; }
    await route.fulfill({ json: { case_id: caseId, deliverable_id: isA ? first.id : second.id,
      receipt_id: isA ? "RECEIPT_A" : "RECEIPT_B", receipt_digest: "b".repeat(64) } });
  });
  await receiptPage.goto(reportURL);
  await openPublicationControls(receiptPage);
  const historyLabels = await receiptPage.locator(".report-history button").allInnerTexts();
  assert.ok(historyLabels.some((label) => label.includes("Draft v91")) && historyLabels.some((label) => label.includes("Draft v92")),
    `receipt-race fixture did not render both governed versions: ${historyLabels.join(" | ")}`);
  await receiptPage.getByRole("button", { name: /Draft v91/i }).click();
  const selectedV91 = receiptPage.locator(".status.warning").filter({ hasText: "Draft v91" });
  try { await selectedV91.waitFor({ timeout: 10_000 }); }
  catch {
    const receiptStatuses = await receiptPage.locator(".status").allInnerTexts();
    assert.fail(`selecting governed v91 failed before the receipt request; statuses: ${receiptStatuses.join(" | ") || "none"}; page errors: ${errors.join(" | ") || "none"}`);
  }
  await Promise.race([waitingA, new Promise((_, reject) => setTimeout(() => reject(new Error(`Draft v91 did not request its filing receipt; observed: ${receiptRequests.join(", ") || "none"}`)), 10_000))]);
  assert.ok(requestA, "the held v91 receipt request identity was not retained");
  // Install the exact request's browser-settlement waiter before selecting B:
  // React's AbortController may cancel A during that click, before the held
  // route is released. Either a browser-level cancellation or a fully-finished
  // response is a settled stale request; a route-handler return is not.
  const aSettled = new Promise((resolve, reject) => {
    const timeout = setTimeout(() => { cleanup(); reject(new Error("held Draft v91 receipt did not settle in the browser")); }, 10_000);
    const cleanup = () => {
      clearTimeout(timeout);
      receiptPage.off("requestfailed", onFailed);
      receiptPage.off("response", onResponse);
    };
    const onFailed = (request) => {
      if (request !== requestA) return;
      cleanup(); resolve("requestfailed");
    };
    const onResponse = async (response) => {
      if (response.request() !== requestA) return;
      try { await response.finished(); cleanup(); resolve("response-finished"); }
      catch (error) { cleanup(); reject(error); }
    };
    receiptPage.on("requestfailed", onFailed);
    receiptPage.on("response", onResponse);
  });
  await receiptPage.getByRole("button", { name: /Draft v92/i }).click();
  await receiptPage.locator("[data-filing-receipt]").filter({ hasText: "RECEIPT_B" }).waitFor();
  releaseA();
  const aSettlement = await aSettled;
  assert.match(await receiptPage.locator("[data-filing-receipt]").innerText(), /RECEIPT_B/);
  await receiptPage.close();
  console.log(`PASS F14: delayed receipt cannot replace the selected frozen output's receipt (${aSettlement})`);
  await page.close();

  const buildFor = async (generation) => {
    await checked(await api.post(`/api/cases/${caseId}/sources`, { multipart: { file: {
      name: `annual-${generation}.txt`, mimeType: "text/plain",
      buffer: Buffer.from(`Regression Holdings\nANNUAL REPORT\nFiscal year ended November 30, 2025\nRevenue 1160\nEBITDA 222\nGeneration ${generation}`),
    } } }), 201);
    const run = await checked(await api.post(`/api/cases/${caseId}/runs`, { data: {
      pathway: "FULL_CREDIT", depth: "full", focus_questions: [],
    } }), 201);
    await poll(`/api/runs/${run.id}`, "succeeded");
    await checked(await api.post(`/api/runs/${run.id}/accept`));
    const queued = await checked(await api.post(`/api/cases/${caseId}/models`, { data: {} }), 202);
    return poll(`/api/cases/${caseId}/models/${queued.id}`, "READY");
  };
  const firstBuild = await buildFor(1);
  const registry = await checked(await api.get(`/api/cases/${caseId}/models/assumption-registry?build_id=${firstBuild.id}`));
  const draft = { build_id: firstBuild.id, parent_revision_id: null, registry_version: registry.version,
    registry_digest: registry.digest, assumptions: registry.defaults, draft_generation: 0 };
  const preview = await checked(await api.post(`/api/cases/${caseId}/models/previews`, { data: draft }));
  const previousHead = await checked(await api.post(`/api/cases/${caseId}/model-revisions/sign-off`, { data: {
    ...draft, preview_digest: preview.preview_digest, expected_head_revision_id: null, note: "First regression model",
  } }), 201);
  const secondBuild = await buildFor(2);
  const worksheet = await checked(await api.get(`/api/cases/${caseId}/models/${secondBuild.id}/worksheet`));
  const snapshot = worksheet.payload.tabs.find((tab) => tab.title === "Credit Snapshot");
  const model = worksheet.payload.tabs.find((tab) => tab.title === "Model");
  const revenue = snapshot.cells.find((cell) => cell.address === "B35");
  assert.equal(typeof revenue.value, "number");
  assert.equal(revenue.value, model.cells.find((cell) => cell.address === "K9").value);
  for (const tab of worksheet.payload.tabs) for (const cell of tab.cells) {
    assert.ok(!cell.formula || typeof cell.value !== "string" || !cell.value.startsWith("="), `${tab.title}!${cell.address}`);
  }
  console.log("PASS F10: worksheet formulas display Python-calculated values");

  const modelPage = await context.newPage();
  let releaseTornado, startedTornado;
  const heldTornado = new Promise((resolve) => { releaseTornado = resolve; });
  const waitingTornado = new Promise((resolve) => { startedTornado = resolve; });
  let calculations = 0, maxCalculations = 0, firstTornado = true;
  const calculationStatuses = [];
  await modelPage.route(/\/models\/(tornado|previews)$/, async (route) => {
    calculations++;
    maxCalculations = Math.max(maxCalculations, calculations);
    if (firstTornado && route.request().url().endsWith("/tornado")) {
      firstTornado = false;
      startedTornado();
      await heldTornado;
    }
    try {
      const response = await route.fetch();
      calculationStatuses.push(response.status());
      await route.fulfill({ response });
    } finally { calculations--; }
  });
  await modelPage.goto(`/model/?case=${caseId}`);
  await waitingTornado;
  const input = modelPage.locator('input[aria-label*="FY"][aria-label*="BASE"]:enabled').first();
  const original = Number(await input.inputValue());
  const step = Number(await input.getAttribute("step")) || 0.001;
  await input.fill(String(original + step));
  await input.press("Enter");
  await modelPage.waitForTimeout(400);
  await input.fill(String(original + 2 * step));
  await input.press("Enter");
  await modelPage.waitForTimeout(400);
  assert.equal(maxCalculations, 1, "UI started overlapping server calculations");
  releaseTornado();
  await modelPage.getByRole("button", { name: "Save model version", exact: true }).waitFor({ timeout: 30000 });
  await modelPage.getByLabel("Sign-Off Note").fill("New build signs against the prior case head");
  const [signed] = await Promise.all([
    modelPage.waitForResponse((response) => response.url().endsWith("/model-revisions/sign-off")),
    modelPage.getByRole("button", { name: "Save model version", exact: true }).click(),
  ]);
  const signedDraft = signed.request().postDataJSON();
  assert.equal(signedDraft.parent_revision_id, null);
  assert.equal(signedDraft.expected_head_revision_id, previousHead.id);
  assert.equal(signed.status(), 201, await signed.text());
  assert.ok(calculationStatuses.every((status) => status === 200), JSON.stringify(calculationStatuses));
  assert.equal(maxCalculations, 1);
  console.log("PASS F8/F9: fresh-build sign-off succeeds; latest preview survives rapid edits without 429");

  await modelPage.getByRole("button", { name: "Refresh", exact: true }).waitFor();
  const tabs = modelPage.getByRole("tablist", { name: "Model worksheets" });
  const longTab = worksheet.payload.tabs.reduce((longest, tab) => tab.max_row > longest.max_row ? tab : longest);
  await tabs.getByRole("tab", { name: longTab.title, exact: true }).click();
  await modelPage.locator(".worksheet-grid td").last().focus();
  await tabs.getByRole("tab", { name: "Credit Snapshot", exact: true }).click();
  assert.equal(await modelPage.locator('.worksheet-grid td[tabindex="0"]').count(), 1);
  await modelPage.locator('.worksheet-grid td[tabindex="0"]').focus();
  await modelPage.keyboard.press("ArrowDown");
  assert.equal(await modelPage.evaluate(() => document.activeElement?.getAttribute("data-address")), "A2");
  console.log("PASS F11: worksheet switching preserves keyboard entry and navigation");

  const savedReport = await context.newPage();
  await savedReport.goto(reportURL);
  const draftResponse = () => savedReport.waitForResponse((response) => response.request().method() === "PUT"
    && response.url().endsWith("/deliverables/FULL_CREDIT/draft"));
  const initialSave = draftResponse();
  await savedReport.getByRole("button", { name: "Save module-populated draft", exact: true }).click();
  await checked(await initialSave, 201);
  await savedReport.locator(".report-save-state").filter({ hasText: "Saved v1" }).waitFor();
  await openPublicationControls(savedReport);
  await savedReport.getByRole("button", { name: "Add commentary", exact: true }).first().click();
  const commentary = savedReport.getByLabel("Analyst commentary", { exact: true });
  const baselineCommentarySave = draftResponse();
  await commentary.fill("Saved recovery section.");
  await savedReport.getByLabel("Analyst judgment", { exact: true }).check();
  await checked(await baselineCommentarySave, 201);
  await savedReport.locator(".report-save-state").filter({ hasText: "Saved v2" }).waitFor();
  const recoveryCopy = () => savedReport.evaluate(() => {
    const tab = sessionStorage.getItem("caos:tab-id");
    return Object.entries(localStorage).filter(([key]) => key.startsWith("caos:report-recovery:") && key.includes(tab))
      .map(([, value]) => JSON.parse(value))[0];
  });
  let releaseSave, startedSave;
  const heldSave = new Promise((resolve) => { releaseSave = resolve; });
  const waitingSave = new Promise((resolve) => { startedSave = resolve; });
  await savedReport.route(`**/api/cases/${caseId}/deliverables/FULL_CREDIT/draft`, async (route) => {
    if (route.request().method() === "PUT") { startedSave(); await heldSave; }
    await route.continue();
  });
  const secondSave = draftResponse();
  await commentary.fill("Updated recovery section.");
  await waitingSave;
  await savedReport.locator("#opinion-text").fill("UNSIGNED DURING AUTOSAVE");
  releaseSave();
  const savedWorkspace = await checked(await secondSave, 201);
  await savedReport.getByRole("button", { name: "Restore as new revision" }).first().waitFor();
  await savedReport.waitForFunction((version) => Object.values(localStorage).some((raw) => {
    try { const copy = JSON.parse(raw); return copy.expectedVersion === version && copy.opinionForm?.opinion === "UNSIGNED DURING AUTOSAVE"; }
    catch { return false; }
  }), savedWorkspace.current.version);
  assert.equal((await recoveryCopy()).opinionForm.opinion, "UNSIGNED DURING AUTOSAVE");
  const restoredResponse = draftResponse();
  await savedReport.getByRole("button", { name: "Restore as new revision" }).last().click();
  const restored = await checked(await restoredResponse, 201);
  await savedReport.getByText(`Restored v1 as new revision v${restored.current.version}.`, { exact: true }).waitFor();
  assert.equal((await recoveryCopy()).expectedVersion, restored.current.version, "restoring a report stranded its unsigned opinion on an obsolete revision");
  assert.deepEqual((await recoveryCopy()).blocks, restored.current.content.blocks);
  await savedReport.getByRole("link", { name: "Portfolio", exact: true }).click();
  await savedReport.getByRole("dialog").filter({ hasText: "Discard changes" }).waitFor();
  console.log("PASS F6: autosave and revision restoration retain unsigned opinion recovery and navigation protection");
  assert.deepEqual(errors, []);
} finally {
  await context.close();
  await browser.close();
}
