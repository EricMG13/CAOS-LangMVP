// FE-A0 reproduction probe. Drives the static export served by the host-control
// app at CAOS_URL with route fixtures where the scenario needs a controlled
// server answer. Every scenario prints one JSON line; the process exits 0 so the
// whole set always runs. Nothing here edits the tree.
import { chromium, firefox, webkit } from "../../../../caos/frontend/node_modules/playwright/index.mjs";
const engineName = process.env.CAOS_BROWSER || "chromium";
const engine = { chromium, firefox, webkit }[engineName];
if (!engine) throw new Error(`unknown CAOS_BROWSER ${engineName}`);

const base = process.env.CAOS_URL || "http://127.0.0.1:8766";
const iterations = Number(process.env.PROBE_FOCUS_ITERATIONS || 8);
const browser = await engine.launch({ headless: true });
const out = (scenario, payload) => console.log(JSON.stringify({ scenario, ...payload }));
const json = (body, status = 200) => (route) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
const caseA = { id: "case_probe_a", name: "Probe A", issuer: "Northstar Probe", sector: "Services", current_execution_id: null, accepted_snapshot_id: null, source_count: 1, latest_intake_id: null, available_pathways: ["FULL_CREDIT", "EARNINGS_UPDATE", "COVENANT_REFINANCING", "RELATIVE_VALUE", "DISTRESSED_RESTRUCTURING"], deep_research_available: false, deep_research_unavailable_reason: "probe" };
const caseB = { ...caseA, id: "case_probe_b", name: "Probe B", issuer: "Second Probe" };
const emptySnapshot = { accepted: null, latest_accepted: null, switch_required: false, diff: null };
const snapshotOf = (id) => ({ id, digest: id.padEnd(64, "0"), accepted_at: "2026-09-01T00:00:00Z", source_set_id: "set_probe", source_set_version: 1, artifacts: [] });

async function newPage(mocks = {}) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  await page.route((url) => url.pathname === "/api/me", json(mocks.me ?? { role: "ANALYST", subject: "analyst" }));
  await page.route((url) => url.pathname === "/api/cases", json(mocks.cases ?? [caseA, caseB]));
  for (const record of mocks.cases ?? [caseA, caseB]) await page.route((url) => url.pathname === `/api/cases/${record.id}`, json(record));
  await page.route((url) => /^\/api\/cases\/[^/]+\/snapshot$/.test(url.pathname), mocks.snapshot ?? json(emptySnapshot));
  await page.route((url) => /^\/api\/cases\/[^/]+\/lens$/.test(url.pathname), json({ issuer: "Northstar Probe", sector: "Services", accepted_snapshot_id: null, source_set: null }));
  await page.route((url) => /^\/api\/runs\/[^/]+\/events$/.test(url.pathname), (route) => route.fulfill({ status: 200, contentType: "text/event-stream", body: "retry: 60000\n\n" }));
  return { context, page };
}

// Model Builder fixture (the a11y sweep's ready model: one definition, three periods).
const modelBuildId = "model_probe_ready";
const modelBuild = { id: modelBuildId, case_id: caseA.id, accepted_run_id: "run_probe_model", accepted_snapshot_id: "snap_probe_model", source_set_id: "set_probe", input_fingerprint: "a".repeat(64), status: "READY", queued_at: "2026-08-24T00:00:00Z", started_at: "2026-08-24T00:00:01Z", completed_at: "2026-08-24T00:00:02Z", error: null, export: { status: "NOT_REQUESTED", error: null }, qa: { status: "PASS", semantic_check_count: 2, formula_count: 1, worksheet_cell_count: 3 }, payload_digest: "b".repeat(64) };
const modelReadiness = { status: "READY", module_id: "CP-MODEL", accepted_snapshot: { id: "snap_probe_model", run_id: "run_probe_model", digest: "c".repeat(64) }, source_set: { id: "set_probe", version: 1, digest: "d".repeat(64) }, requirements: [], blockers: [], build: modelBuild };
const definition = { assumption_id: "operating.consolidated_revenue_growth", label: "Revenue growth", family: "Operating", description: "Consolidated annual revenue growth.", unit: "PERCENT_DECIMAL", cases: ["BASE", "DOWNSIDE"], sensitivity_default: { range: "0.04", step: "0.01" }, hard_min: "-0.75", hard_max: "2", affected_outputs: ["revenue"] };
const defaults = ["BASE", "DOWNSIDE"].flatMap((caseName) => ["FY2025", "FY2026", "FY2027"].map((periodId) => ({ assumption_id: definition.assumption_id, case: caseName, period_id: periodId, unit: "PERCENT", status: "READY", value: caseName === "BASE" ? "0.03" : "-0.02", gap_code: null, default_value: caseName === "BASE" ? "0.03" : "-0.02", default_status: "READY", default_gap_code: null, source_context: null, source_context_digest: null })));
const worksheetTab = (name) => ({ id: name.toUpperCase().replaceAll(" ", "_"), title: name, max_row: 2, max_column: 2, cells: [{ address: "A1", row: 1, column: 1, value: name, value_type: "text", formula: null, semantic_id: null, owner: null, write_class: null, period_id: null, source_refs: null }, { address: "A2", row: 2, column: 1, value: 100, value_type: "number", formula: null, semantic_id: "account::revenue", owner: "CP-1", write_class: "SOURCE", period_id: "FY2025", source_refs: "SRC-1 | page 1" }] });
const worksheet = { build_id: modelBuildId, input_fingerprint: modelBuild.input_fingerprint, payload_digest: modelBuild.payload_digest, qa: modelBuild.qa, payload: { schema_version: "caos.model.worksheet.v1", identity: { issuer_id: "northstar", issuer_name: "Northstar Probe", analysis_date: "2026-08-24" }, tabs: [worksheetTab("Credit Snapshot"), worksheetTab("Model")] } };
async function mockModel(page, counters) {
  await page.route((url) => url.pathname === `/api/cases/${caseA.id}/model`, json(modelReadiness));
  await page.route((url) => url.pathname === `/api/cases/${caseA.id}/models`, json({ builds: [modelBuild] }));
  await page.route((url) => url.pathname === `/api/cases/${caseA.id}/models/assumption-registry`, json({ version: "cp-model-assumptions.v1", digest: "f".repeat(64), definitions: [definition], build_id: modelBuildId, accepted_snapshot_id: modelBuild.accepted_snapshot_id, input_fingerprint: modelBuild.input_fingerprint, defaults }));
  await page.route((url) => url.pathname === `/api/cases/${caseA.id}/model-revisions`, json({ revisions: [] }));
  await page.route((url) => url.pathname === `/api/cases/${caseA.id}/models/${modelBuildId}/worksheet`, json(worksheet));
  await page.route((url) => url.pathname === `/api/cases/${caseA.id}/models/previews`, async (route) => {
    counters.previews += 1;
    const body = route.request().postDataJSON();
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ case_id: caseA.id, build_id: modelBuildId, accepted_snapshot_id: modelBuild.accepted_snapshot_id, build_input_fingerprint: modelBuild.input_fingerprint, build_payload_digest: modelBuild.payload_digest, registry_version: "cp-model-assumptions.v1", registry_digest: "f".repeat(64), calculation_contract_version: "v1", parent_revision_id: body.parent_revision_id, draft_generation: body.draft_generation, effective_assumptions: body.assumptions, assumptions_digest: "1".repeat(64), outputs: {}, outputs_digest: "2".repeat(64), worksheet: worksheet.payload, deltas: {}, preview_digest: "3".repeat(64) }) });
  });
  await page.route((url) => url.pathname === `/api/cases/${caseA.id}/models/tornado`, async (route) => {
    counters.tornados += 1;
    const body = route.request().postDataJSON();
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ build_id: modelBuildId, draft_generation: body.draft_generation, case: body.case, output_period_id: body.output_period_id, output_id: body.output_id, intensity: body.intensity, baseline: "4.2", bars: [{ assumption_id: definition.assumption_id, label: "Revenue growth", unit: "PERCENT_DECIMAL", swing: "0.025", low: "3.9", high: "4.6" }] }) });
  });
}

// S10 — the dirty-draft browser-history focus race, N iterations on fresh pages.
const focusResults = [];
let lastStep = 0;
for (let iteration = 1; iteration <= iterations; iteration += 1) {
  const counters = { previews: 0, tornados: 0 };
  const { context, page } = await newPage();
  try {
    lastStep = 1; await mockModel(page, counters);
    await page.addInitScript(() => {
      window.__focusLog = [];
      document.addEventListener("focusin", (event) => window.__focusLog.push({ t: Math.round(performance.now()), to: `${event.target.tagName}[${event.target.getAttribute?.("aria-label") || event.target.id || ""}]` }), true);
    });
    lastStep = 2; await page.goto(`${base}/model-builder/?case=${caseA.id}`, { waitUntil: "networkidle" });
    const first = page.getByLabel("Revenue growth, FY2025, BASE", { exact: true });
    lastStep = 3; await page.evaluate(() => { const url = new URL(window.location.href); url.searchParams.set("probe-history", "prior"); window.history.pushState({ probe: "prior" }, "", url); });
    lastStep = 3; await first.fill("0.04"); await first.press("Enter");
    lastStep = 4; await page.getByText(/Forecast recalculated/).waitFor();
    lastStep = 6; await first.fill("0.06"); await first.press("Enter");
    const dialog = () => page.getByRole("dialog", { name: "Discard draft changes?" });
    const caseSelect = page.getByRole("combobox", { name: "Select case" });
    lastStep = 7; await caseSelect.selectOption(caseB.id);
    lastStep = 8; await dialog().waitFor();
    lastStep = 9; await dialog().getByRole("button", { name: "Keep editing" }).click();
    lastStep = 10; await page.waitForFunction(() => document.activeElement?.id === "case-select");
    const sourcesLink = page.getByRole("link", { name: "Sources", exact: true }).first();
    lastStep = 11; await sourcesLink.click();
    lastStep = 12; await dialog().waitFor();
    lastStep = 13; await dialog().getByRole("button", { name: "Keep editing" }).click();
    lastStep = 14; await page.waitForFunction(() => document.activeElement?.getAttribute("href")?.startsWith("/sources") === true);
    lastStep = 15; await page.getByRole("button", { name: "Open command palette" }).click();
    const palette = page.getByRole("dialog", { name: "Command palette" });
    lastStep = 16; await palette.getByRole("combobox", { name: "Search cases, workflows or evidence IDs" }).fill("Sources");
    lastStep = 17; await palette.getByRole("option", { name: "Open Sources" }).click();
    lastStep = 18; await dialog().waitFor();
    lastStep = 19; await dialog().getByRole("button", { name: "Keep editing" }).click();
    lastStep = 20; await page.waitForFunction(() => document.activeElement?.getAttribute("aria-label") === "Open command palette");
    lastStep = 21; await first.focus();
    lastStep = 22; await page.waitForFunction(() => { const s = window.history.state; return Boolean(s?.caosModelDraftGuard || s?.caosReportDraftGuard) && Boolean(s.caosDraftHistoryEntryId && s.caosDraftHistoryBaseId) && s.caosDraftHistoryEntryId !== s.caosDraftHistoryBaseId; });
    lastStep = 23; await page.waitForTimeout(2500);
    const beforeBack = await page.evaluate(() => ({ active: document.activeElement?.getAttribute("aria-label") || document.activeElement?.tagName, t: Math.round(performance.now()) }));
    lastStep = 24; await page.evaluate(() => window.history.back());
    lastStep = 25; await dialog().waitFor();
    lastStep = 26; await page.keyboard.press("Escape");
    lastStep = 27; await dialog().waitFor({ state: "hidden" });
    let outcome = "pass";
    lastStep = 28; await page.waitForFunction(() => document.activeElement?.getAttribute("aria-label") === "Revenue growth, FY2025, BASE", null, { timeout: 5000 }).catch(() => { outcome = "fail"; });
    const finalFocus = await page.evaluate(() => document.activeElement?.getAttribute("aria-label") || document.activeElement?.tagName);
    const log = await page.evaluate(() => window.__focusLog.slice(-12));
    focusResults.push({ iteration, outcome, focusBeforeBack: beforeBack.active, finalFocus, tornadoPosts: counters.tornados, previewPosts: counters.previews, tail: log });
  } catch (error) {
    focusResults.push({ iteration, outcome: "harness-error", lastStep, error: String(error).split("\n")[0], activeNow: await page.evaluate(() => `${document.activeElement?.tagName}[${document.activeElement?.getAttribute?.("aria-label") || document.activeElement?.id || ""}]`).catch(() => null), dialogs: await page.evaluate(() => [...document.querySelectorAll("dialog[open]")].map((d) => d.getAttribute("aria-labelledby"))).catch(() => null) });
  }
  await context.close();
}
out("S10-focus-race", { engine: engineName, iterations, passes: focusResults.filter((r) => r.outcome === "pass").length, fails: focusResults.filter((r) => r.outcome === "fail").length, harnessErrors: focusResults.filter((r) => r.outcome === "harness-error").length, results: focusResults });

await browser.close();
