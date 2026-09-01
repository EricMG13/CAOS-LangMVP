import assert from "node:assert/strict";
import { createServer } from "node:http";
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
} finally {
  await browser.close();
  await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
}
