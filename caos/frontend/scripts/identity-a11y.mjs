import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const outDir = fileURLToPath(new URL("../out/", import.meta.url));
const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".txt": "text/plain; charset=utf-8",
  ".woff2": "font/woff2",
};

const server = createServer(async (request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url || "/", "http://localhost").pathname);
    const relative = normalize(pathname.replace(/^\/+/, ""));
    if (relative.startsWith("..")) {
      response.writeHead(400).end();
      return;
    }
    let target = join(outDir, relative || "index.html");
    if ((await stat(target)).isDirectory()) target = join(target, "index.html");
    response.writeHead(200, { "content-type": contentTypes[extname(target)] || "application/octet-stream" });
    response.end(await readFile(target));
  } catch {
    response.writeHead(404).end();
  }
});

await new Promise((resolve, reject) => {
  server.once("error", reject);
  server.listen(0, "127.0.0.1", resolve);
});
const address = server.address();
assert.ok(address && typeof address === "object");

const longIdentity = "snap_0123456789abcdef0123456789abcdef";
const abbreviatedLongIdentity = "snap_0123456…cdef";
const shortIdentity = "run-short";
const caseId = "case_identity_a11y";
const caseFixture = {
  id: caseId,
  name: "Identity accessibility",
  issuer: "Northstar",
  sector: "Services",
  current_execution_id: shortIdentity,
  accepted_snapshot_id: longIdentity,
};
const acceptedFixture = {
  id: longIdentity,
  case_id: caseId,
  run_id: shortIdentity,
  source_set_id: "set_identity_a11y",
  source_set_version: 1,
  artifacts: [],
  digest: "a".repeat(64),
  previous_snapshot_id: null,
  accepted_at: "2026-09-01T00:00:00Z",
};

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.route("**/api/**", async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    let body;
    if (pathname === "/api/me") body = { role: "READER" };
    else if (pathname === "/api/cases") body = [caseFixture];
    else if (pathname === `/api/cases/${caseId}`) body = caseFixture;
    else if (pathname === `/api/cases/${caseId}/snapshot`) body = { accepted: acceptedFixture, latest_accepted: acceptedFixture, switch_required: false, diff: null };
    else if (pathname === `/api/runs/${shortIdentity}`) body = { id: shortIdentity, case_id: caseId, status: "succeeded", plan: { pathway: "FULL_CREDIT", depth: "screen" }, nodes: [], accepted_snapshot_id: longIdentity };
    else {
      await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Not found" }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });

  await page.goto(`http://127.0.0.1:${address.port}/cases/?case=${caseId}&run=${shortIdentity}`, { waitUntil: "domcontentloaded" });
  const longValue = page.locator(`.authority-strip [title="${longIdentity}"]`).first();
  const shortValue = page.locator(`.authority-strip [title="${shortIdentity}"]`).first();
  await longValue.waitFor();
  await shortValue.waitFor();

  assert.equal(await longValue.getAttribute("title"), longIdentity, "long identity lost its exact pointer title");
  assert.equal(await longValue.locator('[aria-hidden="true"]').textContent(), abbreviatedLongIdentity, "long visible identity is not the shared abbreviation");
  assert.equal(await longValue.locator(".sr-only").textContent(), `${abbreviatedLongIdentity}. Full identity: ${longIdentity}`, "long identity lacks one semantic spoken value");
  const longAccessibility = await longValue.ariaSnapshot();
  assert.ok(longAccessibility.includes(`${abbreviatedLongIdentity}. Full identity: ${longIdentity}`), `Chromium did not expose the full long identity:\n${longAccessibility}`);
  assert.equal(longAccessibility.split(longIdentity).length - 1, 1, `Chromium exposed the long identity more than once:\n${longAccessibility}`);

  assert.equal(await shortValue.getAttribute("title"), shortIdentity, "short identity lost its exact pointer title");
  assert.equal(await shortValue.locator('[aria-hidden="true"]').textContent(), shortIdentity, "short visible identity changed");
  assert.equal(await shortValue.locator(".sr-only").textContent(), shortIdentity, "short identity lacks one semantic spoken value");
  const shortAccessibility = await shortValue.ariaSnapshot();
  assert.ok(shortAccessibility.includes(shortIdentity), `Chromium did not expose the short identity:\n${shortAccessibility}`);
  assert.equal(shortAccessibility.split(shortIdentity).length - 1, 1, `Chromium exposed the short identity more than once:\n${shortAccessibility}`);

  assert.equal(await longValue.evaluate((element) => element.tabIndex), -1, "identity presentation must not create a tab stop");
  assert.equal(await shortValue.evaluate((element) => element.tabIndex), -1, "identity presentation must not create a tab stop");
  console.log("Identity accessibility: long and short values exposed exactly once in Chromium.");
} finally {
  await browser.close();
  await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
}
