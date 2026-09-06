// Focus-restoration soak for the dirty-draft discard dialog (issue #38; FE-A0 F10).
// Drives the static export served at CAOS_URL with route fixtures for one READY
// model, then, on a fresh page per iteration, opens and dismisses four discard
// prompts in a row — case select, rail link, palette option, browser history —
// and asserts that Escape on the history prompt returns focus to the editor that
// was focused before history.back(). The failure mode this guards was
// order-dependent (two focus-restoration owners), so one pass proves little and
// the script runs CAOS_FOCUS_ITERATIONS (default 8) times and fails on any miss.
//
//   CAOS_URL=http://127.0.0.1:8000 CAOS_BROWSER=chromium node scripts/focus-restoration-smoke.mjs
import assert from "node:assert/strict";
import { chromium, firefox, webkit } from "playwright";

const engines = { chromium, firefox, webkit };
const browserName = process.env.CAOS_BROWSER || "chromium";
if (!engines[browserName]) throw new Error(`CAOS_BROWSER must be one of ${Object.keys(engines).join(", ")}, got ${browserName}`);
const baseURL = process.env.CAOS_URL || "http://127.0.0.1:8000";
const iterations = Number(process.env.CAOS_FOCUS_ITERATIONS || 8);
assert.ok(Number.isInteger(iterations) && iterations > 0, "CAOS_FOCUS_ITERATIONS must be a positive integer");

const json = (body, status = 200) => (route) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
const caseA = { id: "case_focus_a", name: "Focus A", issuer: "Northstar Focus", sector: "Services", current_execution_id: null, accepted_snapshot_id: null, source_count: 1, latest_intake_id: null, available_pathways: ["FULL_CREDIT", "EARNINGS_UPDATE", "COVENANT_REFINANCING", "RELATIVE_VALUE", "DISTRESSED_RESTRUCTURING"], deep_research_available: false, deep_research_unavailable_reason: "fixture" };
const caseB = { ...caseA, id: "case_focus_b", name: "Focus B", issuer: "Second Focus" };
const emptySnapshot = { accepted: null, latest_accepted: null, switch_required: false, diff: null };
const modelBuildId = "model_focus_ready";
const modelBuild = { id: modelBuildId, case_id: caseA.id, accepted_run_id: "run_focus_model", accepted_snapshot_id: "snap_focus_model", source_set_id: "set_focus", input_fingerprint: "a".repeat(64), status: "READY", queued_at: "2026-08-24T00:00:00Z", started_at: "2026-08-24T00:00:01Z", completed_at: "2026-08-24T00:00:02Z", error: null, export: { status: "NOT_REQUESTED", error: null }, qa: { status: "PASS", semantic_check_count: 2, formula_count: 1, worksheet_cell_count: 3 }, payload_digest: "b".repeat(64) };
const modelReadiness = { status: "READY", module_id: "CP-MODEL", accepted_snapshot: { id: "snap_focus_model", run_id: "run_focus_model", digest: "c".repeat(64) }, source_set: { id: "set_focus", version: 1, digest: "d".repeat(64) }, requirements: [], blockers: [], build: modelBuild };
const definition = { assumption_id: "operating.consolidated_revenue_growth", label: "Revenue growth", family: "Operating", description: "Consolidated annual revenue growth.", unit: "PERCENT_DECIMAL", cases: ["BASE", "DOWNSIDE"], sensitivity_default: { range: "0.04", step: "0.01" }, hard_min: "-0.75", hard_max: "2", affected_outputs: ["revenue"] };
const defaults = ["BASE", "DOWNSIDE"].flatMap((caseName) => ["FY2025", "FY2026", "FY2027"].map((periodId) => ({ assumption_id: definition.assumption_id, case: caseName, period_id: periodId, unit: "PERCENT", status: "READY", value: caseName === "BASE" ? "0.03" : "-0.02", gap_code: null, default_value: caseName === "BASE" ? "0.03" : "-0.02", default_status: "READY", default_gap_code: null, source_context: null, source_context_digest: null })));
const worksheetTab = (name) => ({ id: name.toUpperCase().replaceAll(" ", "_"), title: name, max_row: 2, max_column: 2, cells: [{ address: "A1", row: 1, column: 1, value: name, value_type: "text", formula: null, semantic_id: null, owner: null, write_class: null, period_id: null, source_refs: null }, { address: "A2", row: 2, column: 1, value: 100, value_type: "number", formula: null, semantic_id: "account::revenue", owner: "CP-1", write_class: "SOURCE", period_id: "FY2025", source_refs: "SRC-1 | page 1" }] });
const worksheet = { build_id: modelBuildId, input_fingerprint: modelBuild.input_fingerprint, payload_digest: modelBuild.payload_digest, qa: modelBuild.qa, payload: { schema_version: "caos.model.worksheet.v1", identity: { issuer_id: "northstar", issuer_name: "Northstar Focus", analysis_date: "2026-08-24" }, tabs: [worksheetTab("Credit Snapshot"), worksheetTab("Model")] } };

async function fixturePage(browser, counters) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  await page.route((url) => url.pathname === "/api/me", json({ role: "ANALYST", subject: "analyst" }));
  await page.route((url) => url.pathname === "/api/cases", json([caseA, caseB]));
  for (const record of [caseA, caseB]) await page.route((url) => url.pathname === `/api/cases/${record.id}`, json(record));
  await page.route((url) => /^\/api\/cases\/[^/]+\/snapshot$/.test(url.pathname), json(emptySnapshot));
  await page.route((url) => /^\/api\/cases\/[^/]+\/lens$/.test(url.pathname), json({ issuer: "Northstar Focus", sector: "Services", accepted_snapshot_id: null, source_set: null }));
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
  return { context, page };
}

const browser = await engines[browserName].launch({ headless: true });
const results = [];
try {
  for (let iteration = 1; iteration <= iterations; iteration += 1) {
    const counters = { previews: 0, tornados: 0 };
    const { context, page } = await fixturePage(browser, counters);
    let step = 0;
    try {
      step = 1; await page.goto(`${baseURL}/model-builder/?case=${caseA.id}`, { waitUntil: "networkidle" });
      const editor = page.getByLabel("Revenue growth, FY2025, BASE", { exact: true });
      step = 2; await page.evaluate(() => { const url = new URL(window.location.href); url.searchParams.set("focus-history", "prior"); window.history.pushState({ focus: "prior" }, "", url); });
      step = 3; await editor.fill("0.04"); await editor.press("Enter");
      step = 4; await page.getByText(/Forecast recalculated/).waitFor();
      step = 5; await editor.fill("0.06"); await editor.press("Enter");
      const dialog = () => page.getByRole("dialog", { name: "Discard draft changes?" });
      const caseSelect = page.getByRole("combobox", { name: "Select case" });
      step = 6; await caseSelect.selectOption(caseB.id);
      step = 7; await dialog().waitFor();
      step = 8; await dialog().getByRole("button", { name: "Keep editing" }).click();
      step = 9; await page.waitForFunction(() => document.activeElement?.id === "case-select");
      const sourcesLink = page.getByRole("link", { name: "Sources", exact: true }).first();
      step = 10; await sourcesLink.click();
      step = 11; await dialog().waitFor();
      step = 12; await dialog().getByRole("button", { name: "Keep editing" }).click();
      step = 13; await page.waitForFunction(() => document.activeElement?.getAttribute("href")?.startsWith("/sources") === true);
      step = 14; await page.getByRole("button", { name: "Open command palette" }).click();
      const palette = page.getByRole("dialog", { name: "Command palette" });
      step = 15; await palette.getByRole("combobox", { name: "Search cases, workflows or evidence IDs" }).fill("Sources");
      step = 16; await palette.getByRole("option", { name: "Open Sources" }).click();
      step = 17; await dialog().waitFor();
      step = 18; await dialog().getByRole("button", { name: "Keep editing" }).click();
      step = 19; await page.waitForFunction(() => document.activeElement?.getAttribute("aria-label") === "Open command palette");
      step = 20; await editor.focus();
      step = 21; await page.waitForFunction(() => { const state = window.history.state; return Boolean(state?.caosModelDraftGuard || state?.caosReportDraftGuard) && Boolean(state.caosDraftHistoryEntryId && state.caosDraftHistoryBaseId) && state.caosDraftHistoryEntryId !== state.caosDraftHistoryBaseId; });
      step = 22; await page.waitForTimeout(2500);
      step = 23; await page.evaluate(() => window.history.back());
      step = 24; await dialog().waitFor();
      step = 25; await page.keyboard.press("Escape");
      step = 26; await dialog().waitFor({ state: "hidden" });
      let outcome = "pass";
      step = 27; await page.waitForFunction(() => document.activeElement?.getAttribute("aria-label") === "Revenue growth, FY2025, BASE", null, { timeout: 5000 }).catch(() => { outcome = "fail"; });
      const finalFocus = await page.evaluate(() => document.activeElement?.getAttribute("aria-label") || document.activeElement?.tagName);
      results.push({ iteration, outcome, finalFocus, tornadoPosts: counters.tornados, previewPosts: counters.previews });
    } catch (error) {
      results.push({ iteration, outcome: "harness-error", step, error: String(error).split("\n")[0] });
    }
    await context.close();
  }
} finally {
  await browser.close();
}
const summary = { browser: browserName, iterations, passes: results.filter((item) => item.outcome === "pass").length, fails: results.filter((item) => item.outcome === "fail").length, harnessErrors: results.filter((item) => item.outcome === "harness-error").length, results };
console.log(JSON.stringify(summary));
assert.equal(summary.passes, iterations, `focus restoration failed on ${iterations - summary.passes} of ${iterations} iterations`);
