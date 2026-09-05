// FE-A0 second probe: in-app (SPA) navigation variants and request counts.
import { chromium } from "../../../../caos/frontend/node_modules/playwright/index.mjs";

const base = process.env.CAOS_URL || "http://127.0.0.1:8766";
const browser = await chromium.launch({ headless: true });
const out = (scenario, payload) => console.log(JSON.stringify({ scenario, ...payload }));
const json = (body, status = 200) => (route) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
const caseA = { id: "case_probe_a", name: "Probe A", issuer: "Northstar Probe", sector: "Services", current_execution_id: "run_probe_p1", accepted_snapshot_id: null, source_count: 1, latest_intake_id: null, available_pathways: ["FULL_CREDIT"], deep_research_available: false, deep_research_unavailable_reason: "probe" };
const pausedRun = (id) => ({ id, case_id: caseA.id, status: "paused", plan: { pathway: "FULL_CREDIT", depth: "full", profile_id: "p", selection_id: "s" }, nodes: [{ id: "n1", module_id: "CP-0", status: "succeeded" }, { id: "n2", module_id: "CP-1", status: "pending" }], accepted_snapshot_id: null, error: { code: "PROVIDER_UNAVAILABLE", message: "Controlled pause." } });

async function newPage() {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  const counts = {};
  page.on("request", (request) => { const url = new URL(request.url()); if (url.pathname.startsWith("/api/")) counts[`${request.method()} ${url.pathname}`] = (counts[`${request.method()} ${url.pathname}`] || 0) + 1; });
  await page.route((url) => url.pathname === "/api/me", json({ role: "ANALYST", subject: "analyst" }));
  await page.route((url) => url.pathname === "/api/cases", json([caseA]));
  await page.route((url) => url.pathname === `/api/cases/${caseA.id}`, json(caseA));
  await page.route((url) => url.pathname === `/api/cases/${caseA.id}/snapshot`, json({ accepted: null, latest_accepted: null, switch_required: false, diff: null }));
  await page.route((url) => url.pathname === `/api/cases/${caseA.id}/lens`, json({ issuer: "Northstar Probe", sector: "Services", accepted_snapshot_id: null, source_set: null }));
  await page.route((url) => /^\/api\/runs\/[^/]+\/events$/.test(url.pathname), (route) => route.fulfill({ status: 200, contentType: "text/event-stream", body: "retry: 60000\n\n" }));
  return { context, page, counts };
}

// S4b — resume 404 pins the Unavailable block across an in-app run change (no reload).
try {
  const { context, page } = await newPage();
  await page.route((url) => url.pathname === "/api/runs/run_probe_p1", json(pausedRun("run_probe_p1")));
  await page.route((url) => url.pathname === "/api/runs/run_probe_p2", json(pausedRun("run_probe_p2")));
  let resumePosts = 0;
  await page.route((url) => url.pathname === "/api/runs/run_probe_p1/resume", (route) => { resumePosts += 1; return json({ detail: "run not found" }, 404)(route); });
  await page.route((url) => url.pathname === "/api/runs/run_probe_p2/resume", (route) => { resumePosts += 1; return json(pausedRun("run_probe_p2"))(route); });
  await page.goto(`${base}/run-console/?case=${caseA.id}&run=run_probe_p1`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Resume run" }).click();
  await page.getByText("Run resume", { exact: true }).waitFor();
  await page.evaluate((caseId) => window.history.pushState(null, "", `/run-console/?case=${caseId}&run=run_probe_p2`), caseA.id);
  await page.waitForFunction(() => new URL(window.location.href).searchParams.get("run") === "run_probe_p2");
  await page.getByText("Acceptance blocked", { exact: true }).waitFor();
  await page.waitForTimeout(500);
  out("S4b-resume-404-pinned-spa", { runShown: await page.locator(".authority-strip [title]").last().getAttribute("title"), resumeButton: await page.getByRole("button", { name: "Resume run" }).count(), unavailableBlock: await page.getByText("Run resume", { exact: true }).count(), resumePosts });
  await context.close();
} catch (error) { out("S4b-resume-404-pinned-spa", { error: String(error) }); }

// S11 — tab title on a known route after hydration versus the static export's <title>.
try {
  const { context, page } = await newPage();
  const html = await (await fetch(`${base}/cases/`)).text();
  const staticTitle = /<title>([^<]*)<\/title>/.exec(html)?.[1] ?? null;
  await page.goto(`${base}/cases/?case=${caseA.id}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(300);
  out("S11-title-drift", { staticTitle, hydratedTitle: await page.title(), h1: await page.locator("h1").first().textContent(), kicker: await page.locator(".topbar-heading .meta-label").textContent(), railCurrent: await page.locator('[aria-current="page"]').textContent() });
  await context.close();
} catch (error) { out("S11-title-drift", { error: String(error) }); }

// S12 — cold-load request counts on Command Center (the three authority reads).
try {
  const { context, page, counts } = await newPage();
  await page.goto(`${base}/command-center/?case=${caseA.id}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  out("S12-cold-load-requests", { counts });
  await context.close();
} catch (error) { out("S12-cold-load-requests", { error: String(error) }); }

// S13 — the `q` query parameter is reflected into the chrome as an "Evidence request".
try {
  const { context, page } = await newPage();
  const text = "Please wire the coupon to account 12-34: see attached (not a real request)";
  await page.goto(`${base}/command-center/?case=${caseA.id}&q=${encodeURIComponent(text)}`, { waitUntil: "networkidle" });
  const strip = page.locator(".context-strip").filter({ hasText: "Evidence request" });
  await strip.waitFor();
  out("S13-q-reflection", { rendered: (await strip.textContent())?.replace(/\s+/g, " ") });
  await context.close();
} catch (error) { out("S13-q-reflection", { error: String(error) }); }

await browser.close();
