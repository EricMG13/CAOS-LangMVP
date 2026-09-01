import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { extname, join } from "node:path";
import { chromium } from "playwright";

const workbench = await import("../src/lib/workbench.ts");
for (const name of [
  "beginDraftHistoryTraversal",
  "draftHistoryEntryId",
  "draftHistoryNeedsRearm",
  "observeDraftHistoryPop",
  "protectDirtyDraftUnload",
]) assert.equal(typeof workbench[name], "function", `${name} is not executable`);

const sources = Object.fromEntries([
  "beginDraftHistoryTraversal",
  "draftHistoryEntryId",
  "draftHistoryNeedsRearm",
  "observeDraftHistoryPop",
  "protectDirtyDraftUnload",
].map((name) => [name, workbench[name].toString()]));

const server = createServer((_request, response) => {
  response.writeHead(200, { "content-type": "text/html" });
  response.end("<!doctype html><button id=activate>Activate history test</button>");
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const address = server.address();
assert.ok(address && typeof address === "object");
const origin = `http://127.0.0.1:${address.port}`;

const browser = await chromium.launch({ headless: true });
let workspaceServer = null;

async function installHistoryProbe(page) {
  await page.evaluate((functionSources) => {
    const beginDraftHistoryTraversal = eval(`(${functionSources.beginDraftHistoryTraversal})`);
    const draftHistoryEntryId = eval(`(${functionSources.draftHistoryEntryId})`);
    const draftHistoryNeedsRearm = eval(`(${functionSources.draftHistoryNeedsRearm})`);
    const observeDraftHistoryPop = eval(`(${functionSources.observeDraftHistoryPop})`);
    const protectDirtyDraftUnload = eval(`(${functionSources.protectDirtyDraftUnload})`);
    const probe = {
      active: null,
      dirty: true,
      delayNext: false,
      duplicateNextMatch: false,
      queuedState: null,
      events: [],
      matches: 0,
      unloadsBlocked: 0,
    };
    window.__draftHistoryProbe = probe;
    window.__startDraftTraversal = (token, kind, expectedDestinationId) => {
      const result = beginDraftHistoryTraversal(probe.active, token, kind, expectedDestinationId);
      probe.active = result.active;
      return result.started;
    };
    window.__finishObservedTraversal = () => {
      const completed = probe.active;
      const rearm = completed ? draftHistoryNeedsRearm(completed, probe.dirty) : false;
      probe.active = null;
      return rearm;
    };
    window.__deliverQueuedPop = () => {
      if (!probe.queuedState) return false;
      const queued = probe.queuedState;
      probe.queuedState = null;
      window.dispatchEvent(new PopStateEvent("popstate", { state: queued }));
      return true;
    };
    window.addEventListener("popstate", (event) => {
      if (!probe.delayNext) return;
      probe.delayNext = false;
      probe.queuedState = event.state;
      event.stopImmediatePropagation();
    }, true);
    window.addEventListener("popstate", (event) => {
      const observation = observeDraftHistoryPop(probe.active, event.state);
      probe.active = observation.active;
      probe.events.push({ id: draftHistoryEntryId(event.state), matched: observation.matched });
      if (!observation.matched) return;
      probe.matches += 1;
      if (probe.duplicateNextMatch) {
        probe.duplicateNextMatch = false;
        window.dispatchEvent(new PopStateEvent("popstate", { state: event.state }));
      }
    });
    window.addEventListener("beforeunload", (event) => {
      if (protectDirtyDraftUnload(event, probe.dirty)) probe.unloadsBlocked += 1;
    });
  }, sources);
}

async function waitForEvents(page, count) {
  await page.waitForFunction((expected) => window.__draftHistoryProbe.events.length >= expected, count);
}

async function reservePort() {
  const portServer = createServer();
  await new Promise((resolve) => portServer.listen(0, "127.0.0.1", resolve));
  const portAddress = portServer.address();
  assert.ok(portAddress && typeof portAddress === "object");
  await new Promise((resolve, reject) => portServer.close((error) => error ? reject(error) : resolve()));
  return portAddress.port;
}

async function waitForBuiltApp(url) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  throw new Error(`built app did not start at ${url}`);
}

try {
  const page = await browser.newPage();
  await page.goto(`${origin}/editor`);
  await installHistoryProbe(page);
  await page.evaluate(() => {
    history.replaceState({ caosDraftHistoryEntryId: "prior" }, "", "?entry=prior");
    history.pushState({ caosDraftHistoryEntryId: "base", caosDraftHistoryPreviousId: "prior", caosDraftHistorySentinelId: "sentinel" }, "", "?entry=base");
    history.pushState({ caosDraftHistoryEntryId: "sentinel", caosDraftHistoryBaseId: "base", caosModelDraftGuard: true }, "", "?entry=base");
  });

  await page.evaluate(() => history.back());
  await waitForEvents(page, 1);
  assert.equal(await page.evaluate(() => window.__startDraftTraversal(1, "restore", "sentinel")), true);
  await page.evaluate(() => history.forward());
  await waitForEvents(page, 2);
  assert.deepEqual(await page.evaluate(() => window.__draftHistoryProbe.events.slice(-1)[0]), { id: "sentinel", matched: true });
  assert.equal(await page.evaluate(() => window.__finishObservedTraversal()), false);

  await page.evaluate(() => history.back());
  await waitForEvents(page, 3);
  assert.equal(await page.evaluate(() => window.__startDraftTraversal(2, "confirmed", "prior")), true);
  await page.evaluate(() => { window.__draftHistoryProbe.duplicateNextMatch = true; history.back(); });
  await waitForEvents(page, 5);
  assert.deepEqual(await page.evaluate(() => window.__draftHistoryProbe.events.slice(-2)), [
    { id: "prior", matched: true },
    { id: "prior", matched: false },
  ]);
  assert.equal(await page.evaluate(() => window.__draftHistoryProbe.matches), 2, "duplicate pop settled the confirmed traversal twice");
  assert.equal(await page.evaluate(() => window.__finishObservedTraversal()), true);

  await page.evaluate(() => {
    history.pushState({ caosDraftHistoryEntryId: "old" }, "", "?entry=old");
    history.pushState({ caosDraftHistoryEntryId: "new" }, "", "?entry=new");
    window.__draftHistoryProbe.delayNext = true;
    history.back();
  });
  await page.waitForFunction(() => window.__draftHistoryProbe.queuedState?.caosDraftHistoryEntryId === "old");
  assert.equal(await page.evaluate(() => window.__startDraftTraversal(3, "confirmed", "prior")), true);
  assert.equal(await page.evaluate(() => window.__deliverQueuedPop()), true);
  assert.deepEqual(await page.evaluate(() => window.__draftHistoryProbe.events.slice(-1)[0]), { id: "old", matched: false });
  assert.equal(await page.evaluate(() => window.__draftHistoryProbe.active.expectedDestinationId), "prior", "delayed old pop settled the newer traversal");
  await page.evaluate(() => history.back());
  await page.waitForFunction(() => window.__draftHistoryProbe.events.some((event) => event.id === "prior" && event.matched));

  const boundaryPage = await browser.newPage();
  await boundaryPage.setContent("<!doctype html><button id=activate>Activate history test</button>");
  await installHistoryProbe(boundaryPage);
  await boundaryPage.click("#activate");
  const canGoBack = await boundaryPage.evaluate(() => window.navigation?.canGoBack ?? false);
  assert.equal(canGoBack, false, "boundary fixture unexpectedly had a previous entry");
  await boundaryPage.evaluate(() => {
    history.replaceState({ caosDraftHistoryEntryId: "direct" }, "", "");
    history.pushState({ caosDraftHistoryEntryId: "direct-sentinel", caosDraftHistoryBaseId: "direct", caosModelDraftGuard: true }, "", "#guard");
    history.back();
  });
  await waitForEvents(boundaryPage, 1);
  const boundaryEvents = await boundaryPage.evaluate(() => window.__draftHistoryProbe.events.length);
  await boundaryPage.evaluate(() => history.back());
  await boundaryPage.waitForTimeout(100);
  assert.equal(await boundaryPage.evaluate(() => window.__draftHistoryProbe.events.length), boundaryEvents, "true boundary emitted a popstate");
  let boundaryDialog = false;
  boundaryPage.once("dialog", async (dialog) => { boundaryDialog = true; await dialog.dismiss(); });
  await boundaryPage.evaluate(() => location.reload());
  await boundaryPage.waitForTimeout(100);
  assert.equal(boundaryDialog, true, "unrelated reload bypassed dirty beforeunload after boundary confirm");

  const crossDocumentPage = await browser.newPage();
  await crossDocumentPage.goto(`${origin}/previous`);
  await crossDocumentPage.goto(`${origin}/editor`);
  await installHistoryProbe(crossDocumentPage);
  await crossDocumentPage.click("#activate");
  let crossDocumentDialog = false;
  crossDocumentPage.once("dialog", async (dialog) => { crossDocumentDialog = true; await dialog.dismiss(); });
  await crossDocumentPage.evaluate(() => history.back());
  await crossDocumentPage.waitForTimeout(100);
  assert.equal(crossDocumentDialog, true, "cross-document confirm bypassed the native dirty-draft fallback");
  assert.equal(new URL(crossDocumentPage.url()).pathname, "/editor");

  const workspacePort = await reservePort();
  const workspaceOrigin = `http://127.0.0.1:${workspacePort}`;
  workspaceServer = createServer(async (request, response) => {
    try {
      const pathname = decodeURIComponent(new URL(request.url || "/", workspaceOrigin).pathname);
      const relativePath = pathname.endsWith("/") ? `${pathname.slice(1)}index.html` : pathname.slice(1);
      const body = await readFile(join(process.cwd(), "out", relativePath));
      const contentType = { ".css": "text/css", ".html": "text/html", ".js": "text/javascript", ".svg": "image/svg+xml", ".woff2": "font/woff2" }[extname(relativePath)] || "application/octet-stream";
      response.writeHead(200, { "content-type": contentType });
      response.end(body);
    } catch {
      response.writeHead(404);
      response.end("not found");
    }
  });
  await new Promise((resolve) => workspaceServer.listen(workspacePort, "127.0.0.1", resolve));
  await waitForBuiltApp(`${workspaceOrigin}/report-studio/`);

  const cases = [
    { id: "history-case-a", name: "History A", issuer: "History A", sector: "Services", source_count: 0, accepted_snapshot_id: null },
    { id: "history-case-b", name: "History B", issuer: "History B", sector: "Services", source_count: 0, accepted_snapshot_id: null },
  ];
  const template = {
    template_id: "caos.full-credit.history-smoke.v1",
    template_version: "caos.deliverable-template.v1",
    pathway: "FULL_CREDIT",
    title: "History smoke report",
    model_requirement: "OPTIONAL",
    allowed_appendices: [],
    optional_blocks: [],
    blocks: [
      { block_id: "history.credit-snapshot", slot_id: "section.01", kind: "NARRATIVE", title: "Credit Snapshot", required: true, order: 1 },
      { block_id: "history.evidence-register", slot_id: "appendix.evidence-register", kind: "EVIDENCE_REGISTER", title: "Evidence Register", required: true, order: 2 },
    ],
  };
  const reportWorkspace = {
    template,
    current: null,
    history: [],
    frozen_history: [],
    model_eligibility: {
      active_revision: null,
      application_build: null,
      fallback_acknowledgement_required: false,
      default_model_selection: null,
    },
  };
  let releaseCaseBLoad;
  const caseBLoad = new Promise((resolve) => { releaseCaseBLoad = resolve; });
  const workspacePage = await browser.newPage();
  await workspacePage.addInitScript(() => {
    window.__caosHistoryWrites = [];
    for (const method of ["pushState", "replaceState"]) {
      const original = history[method].bind(history);
      history[method] = (state, title, url) => {
        const result = original(state, title, url);
        window.__caosHistoryWrites.push({ method, state: structuredClone(history.state), href: location.href });
        return result;
      };
    }
  });
  await workspacePage.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/me") return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ role: "ANALYST" }) });
    if (url.pathname === "/api/cases") return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(cases) });
    const caseId = url.pathname.match(/^\/api\/cases\/([^/]+)/)?.[1];
    if (url.pathname.endsWith("/snapshot")) return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ accepted: null, latest_accepted: null, switch_required: false, diff: null }) });
    if (url.pathname.endsWith("/sources")) return route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    if (url.pathname.endsWith("/deliverables/FULL_CREDIT/draft")) {
      if (caseId === "history-case-b" && route.request().method() === "GET") await caseBLoad;
      return route.fulfill({ status: route.request().method() === "PUT" ? 503 : 200, contentType: "application/json", body: route.request().method() === "PUT" ? JSON.stringify({ detail: "held dirty for history smoke" }) : JSON.stringify(reportWorkspace) });
    }
    const selectedCase = cases.find((item) => item.id === caseId);
    if (selectedCase && url.pathname === `/api/cases/${caseId}`) return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(selectedCase) });
    return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "not found" }) });
  });
  await workspacePage.goto(`${workspaceOrigin}/report-studio/?case=history-case-a`, { waitUntil: "networkidle" });
  await workspacePage.evaluate(() => {
    window.__caosWorkspaceReplaceCalls = [];
    const replaceState = history.replaceState.bind(history);
    history.replaceState = (state, title, url) => {
      window.__caosWorkspaceReplaceCalls.push({ state: state === null ? null : structuredClone(state), href: new URL(url || location.href, location.href).href });
      return replaceState(state, title, url);
    };
  });
  const reportEditor = workspacePage.getByLabel("Credit Snapshot");
  await reportEditor.fill("Dirty authority history integration");
  await workspacePage.waitForFunction(() => history.state?.caosReportDraftGuard === true);
  const firstSentinel = await workspacePage.evaluate(() => structuredClone(history.state));
  assert.equal(firstSentinel.caosDraftHistoryPreviousId, firstSentinel.caosDraftHistoryBaseId, "armed sentinel did not point at its real base entry");

  const caseSelect = workspacePage.getByRole("combobox", { name: "Select case" });
  const synchronizedWriteStart = await workspacePage.evaluate(() => window.__caosHistoryWrites.length);
  const synchronizedCallStart = await workspacePage.evaluate(() => window.__caosWorkspaceReplaceCalls.length);
  await caseSelect.selectOption("history-case-b");
  const discardDialog = workspacePage.getByRole("dialog", { name: "Discard draft changes?" });
  await discardDialog.getByRole("button", { name: "Discard changes" }).click();
  await workspacePage.waitForFunction(() => new URL(location.href).searchParams.get("case") === "history-case-b");
  const synchronizedWrites = await workspacePage.evaluate((from) => window.__caosHistoryWrites.slice(from).filter((write) => new URL(write.href).searchParams.get("case") === "history-case-b"), synchronizedWriteStart);
  assert.ok(synchronizedWrites.length > 0, "authority query sync made no observable history write");
  assert.ok(synchronizedWrites.every((write) => write.state?.caosDraftHistoryEntryId === firstSentinel.caosDraftHistoryEntryId), "authority query sync erased the current sentinel entry id");
  assert.ok(synchronizedWrites.every((write) => write.state?.caosDraftHistoryBaseId === firstSentinel.caosDraftHistoryBaseId), "authority query sync erased the sentinel base destination");
  const synchronizedCalls = await workspacePage.evaluate((from) => window.__caosWorkspaceReplaceCalls.slice(from).filter((write) => new URL(write.href).searchParams.get("case") === "history-case-b"), synchronizedCallStart);
  assert.ok(synchronizedCalls.length > 0, "authority query sync did not call replaceState");
  assert.ok(synchronizedCalls.every((write) => write.state?.caosDraftHistoryEntryId === firstSentinel.caosDraftHistoryEntryId), "authority query sync passed metadata-erasing state into replaceState");

  releaseCaseBLoad();
  await reportEditor.waitFor();
  await reportEditor.fill("Dirty rollback history integration");
  await workspacePage.waitForFunction(() => history.state?.caosReportDraftGuard === true);
  const rollbackSentinel = await workspacePage.evaluate(() => structuredClone(history.state));
  const writeCount = await workspacePage.evaluate(() => window.__caosHistoryWrites.length);
  const replaceCallCount = await workspacePage.evaluate(() => window.__caosWorkspaceReplaceCalls.length);
  await workspacePage.evaluate(() => {
    const url = new URL(location.href);
    url.searchParams.set("case", "history-case-a");
    history.replaceState(history.state, "", url);
  });
  await discardDialog.waitFor();
  await workspacePage.waitForFunction(() => new URL(location.href).searchParams.get("case") === "history-case-b");
  const rollbackWrites = await workspacePage.evaluate((from) => window.__caosHistoryWrites.slice(from).filter((write) => new URL(write.href).searchParams.get("case") === "history-case-b"), writeCount);
  assert.ok(rollbackWrites.length > 0, "dirty authority rollback made no observable history write");
  assert.ok(rollbackWrites.every((write) => write.state?.caosDraftHistoryEntryId === rollbackSentinel.caosDraftHistoryEntryId), "dirty authority rollback erased the current sentinel entry id");
  assert.ok(rollbackWrites.every((write) => write.state?.caosDraftHistoryBaseId === rollbackSentinel.caosDraftHistoryBaseId), "dirty authority rollback erased the sentinel base destination");
  const rollbackCalls = await workspacePage.evaluate((from) => window.__caosWorkspaceReplaceCalls.slice(from).filter((write) => new URL(write.href).searchParams.get("case") === "history-case-b"), replaceCallCount);
  assert.ok(rollbackCalls.length > 0, "dirty authority rollback did not call replaceState");
  assert.ok(rollbackCalls.every((write) => write.state?.caosDraftHistoryEntryId === rollbackSentinel.caosDraftHistoryEntryId), "dirty authority rollback passed metadata-erasing state into replaceState");
  await discardDialog.getByRole("button", { name: "Keep editing" }).click();
} finally {
  if (workspaceServer) await new Promise((resolve, reject) => workspaceServer.close((error) => error ? reject(error) : resolve()));
  await browser.close();
  await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
}
