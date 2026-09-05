// FE-A0 reproduction probe. Drives the static export served by the host-control
// app at CAOS_URL with route fixtures where the scenario needs a controlled
// server answer. Every scenario prints one JSON line; the process exits 0 so the
// whole set always runs. Nothing here edits the tree.
import { chromium } from "../../../../caos/frontend/node_modules/playwright/index.mjs";

const base = process.env.CAOS_URL || "http://127.0.0.1:8766";
const iterations = Number(process.env.PROBE_FOCUS_ITERATIONS || 8);
const browser = await chromium.launch({ headless: true });
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

// S1 — unknown route: the client title effect overrides the not-found metadata.
try {
  const { context, page } = await newPage();
  await page.goto(`${base}/missing-probe-route/`, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "Page not found" }).waitFor();
  await page.waitForTimeout(300);
  out("S1-unknown-route-title", { h1: await page.locator("h1").first().textContent(), documentTitle: await page.title(), railCurrent: await page.locator('[aria-current="page"]').count() });
  await context.close();
} catch (error) { out("S1-unknown-route-title", { error: String(error) }); }

// S2 — deep link to a case the register does not hold: silent substitution.
try {
  const { context, page } = await newPage();
  await page.goto(`${base}/command-center/?case=case_probe_missing`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => { const s = document.querySelector('[aria-label="Select case"]'); return s instanceof HTMLSelectElement && s.value && s.value !== "case_probe_missing"; });
  const alerts = await page.locator('[role="alert"], [role="status"]').allTextContents();
  out("S2-deep-link-substitution", { requested: "case_probe_missing", selected: await page.locator("#case-select").inputValue(), url: page.url(), strip: (await page.getByRole("region", { name: "Visible authority" }).textContent())?.replace(/\s+/g, " "), liveRegionsMentioningRequest: alerts.filter((text) => text.includes("case_probe_missing")) });
  await context.close();
} catch (error) { out("S2-deep-link-substitution", { error: String(error) }); }

// S3 — network failure: what text reaches the analyst.
try {
  const { context, page } = await newPage();
  await page.unroute((url) => url.pathname === "/api/cases");
  await page.route((url) => url.pathname === "/api/cases", (route) => route.abort("failed"));
  await page.goto(`${base}/cases/`, { waitUntil: "networkidle" });
  await page.locator(".global-error").waitFor({ timeout: 5000 });
  out("S3-offline-text", { globalError: await page.locator(".global-error").textContent() });
  await context.close();
} catch (error) { out("S3-offline-text", { error: String(error) }); }

// S4 — a 404 on one run's resume pins "Not available in this deployment" for every later run.
try {
  const pausedRun = (id) => ({ id, case_id: caseA.id, status: "paused", plan: { pathway: "FULL_CREDIT", depth: "full", profile_id: "p", selection_id: "s" }, nodes: [{ id: "n1", module_id: "CP-0", status: "succeeded" }, { id: "n2", module_id: "CP-1", status: "pending" }], accepted_snapshot_id: null, error: { code: "PROVIDER_UNAVAILABLE", message: "Controlled pause." } });
  const withRun = { ...caseA, current_execution_id: "run_probe_p1" };
  const { context, page } = await newPage({ cases: [withRun, caseB] });
  await page.route((url) => url.pathname === "/api/runs/run_probe_p1", json(pausedRun("run_probe_p1")));
  await page.route((url) => url.pathname === "/api/runs/run_probe_p2", json(pausedRun("run_probe_p2")));
  let resumePosts = 0;
  await page.route((url) => url.pathname === "/api/runs/run_probe_p1/resume", (route) => { resumePosts += 1; return json({ detail: "run not found" }, 404)(route); });
  await page.route((url) => url.pathname === "/api/runs/run_probe_p2/resume", (route) => { resumePosts += 1; return json(pausedRun("run_probe_p2"))(route); });
  await page.goto(`${base}/run-console/?case=${caseA.id}&run=run_probe_p1`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Resume run" }).click();
  await page.getByText("Run resume", { exact: true }).waitFor();
  const firstState = { resumeButton: await page.getByRole("button", { name: "Resume run" }).count(), unavailable: await page.getByText("Not available in this deployment.").count() };
  await page.goto(`${base}/run-console/?case=${caseA.id}&run=run_probe_p2`, { waitUntil: "networkidle" });
  await page.getByText("Acceptance blocked", { exact: true }).waitFor();
  await page.waitForTimeout(300);
  out("S4-resume-404-pinned", { afterFirst404: firstState, secondRun: { resumeButton: await page.getByRole("button", { name: "Resume run" }).count(), unavailable: await page.getByText("Not available in this deployment.").count() }, resumePosts });
  await context.close();
} catch (error) { out("S4-resume-404-pinned", { error: String(error) }); }

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

// S5 — Tab through an untouched forecast input: remount, focus loss, network calls.
try {
  const counters = { previews: 0, tornados: 0 };
  const { context, page } = await newPage();
  await mockModel(page, counters);
  await page.goto(`${base}/model-builder/?case=${caseA.id}`, { waitUntil: "networkidle" });
  const first = page.getByLabel("Revenue growth, FY2025, BASE", { exact: true });
  await first.waitFor();
  await page.waitForTimeout(700);
  const before = { ...counters };
  const tagged = await first.evaluate((element) => { element.dataset.probe = "original"; return true; });
  await first.focus();
  await page.keyboard.press("Tab");
  await page.waitForTimeout(900);
  const after = await page.evaluate(() => ({ active: document.activeElement?.tagName, activeLabel: document.activeElement?.getAttribute("aria-label"), originalStillMounted: Boolean(document.querySelector('[data-probe="original"]')) }));
  out("S5-blur-without-change", { tagged, callsBeforeTab: before, callsAfterTab: { ...counters }, focusAfterTab: after, valueUnchanged: (await first.inputValue()) === "0.03", changesBadge: await page.locator(".status").filter({ hasText: /CHANGES/ }).textContent() });
  await context.close();
} catch (error) { out("S5-blur-without-change", { error: String(error) }); }

// S6 — the shell and Command Center each read the snapshot; a switch between the two reads is shown as two identities.
try {
  let snapshotReads = 0;
  const { context, page } = await newPage({ snapshot: (route) => { snapshotReads += 1; const id = snapshotReads === 1 ? "snap_probe_one" : "snap_probe_two"; return json({ accepted: snapshotOf(id), latest_accepted: snapshotOf(id), switch_required: false, diff: { changed: false, added: [], removed: [], modified: [], source_set_changed: false } })(route); } });
  await page.goto(`${base}/command-center/?case=${caseA.id}`, { waitUntil: "networkidle" });
  await page.getByText("Accepted conclusion and exact module authority").waitFor();
  await page.waitForTimeout(300);
  const stripId = await page.getByRole("region", { name: "Visible authority" }).locator("[title]").first().getAttribute("title");
  const creditId = await page.locator(".authority-metrics [title]").first().getAttribute("title");
  out("S6-divergent-snapshot-identity", { snapshotReads, shellStrip: stripId, creditScreen: creditId, agree: stripId === creditId, warningShown: await page.getByText(/differs|Review required/).count() });
  await context.close();
} catch (error) { out("S6-divergent-snapshot-identity", { error: String(error) }); }

// S7 — the intake panel header keeps the previous case's "Last intake" after a case switch.
try {
  const withIntake = { ...caseA, latest_intake_id: "intake_probe_a" };
  const intake = { intake_id: "intake_probe_a", case_id: caseA.id, status: "started", created_at: "2026-09-01T10:00:00Z", case: withIntake, run: null, suggestions: { issuer: "Northstar Probe", label: "Probe A", sector: "Services", issuer_confidence: "high", basis: "cover" }, route: { pathway: "FULL_CREDIT", depth: "full", reason: "annual", selected_by: "host_classification", evidence: [] }, coverage: { fiscal_years: [2024], quarters: [], latest_period: "FY2024", gaps: [] }, documents: [], refusal: null };
  const { context, page } = await newPage({ cases: [withIntake, caseB] });
  await page.route((url) => url.pathname === `/api/cases/${caseA.id}/intake`, json(intake));
  await page.goto(`${base}/cases/?case=${caseA.id}`, { waitUntil: "networkidle" });
  await page.locator(".cases-intake .panel-meta").filter({ hasText: /Last intake/ }).waitFor();
  const metaA = await page.locator(".cases-intake .panel-meta").textContent();
  await page.getByRole("combobox", { name: "Select case" }).selectOption(caseB.id);
  await page.waitForFunction((id) => document.querySelector("#case-select")?.value === id, caseB.id);
  await page.waitForTimeout(500);
  out("S7-stale-intake-meta", { caseAMeta: metaA, caseBMeta: await page.locator(".cases-intake .panel-meta").textContent(), caseBHasEvidenceTable: await page.getByRole("region", { name: "Source disposition manifest" }).count() });
  await context.close();
} catch (error) { out("S7-stale-intake-meta", { error: String(error) }); }

// S8 — the compile form's default pathway can sit outside the served cut and still submit.
try {
  const narrow = { ...caseA, available_pathways: ["FULL_CREDIT"] };
  const { context, page } = await newPage({ cases: [narrow, caseB] });
  let startBody = null;
  await page.route((url) => url.pathname === `/api/cases/${caseA.id}/runs`, (route) => { startBody = route.request().postDataJSON(); return json({ detail: { code: "PATHWAY_NOT_AVAILABLE" } }, 422)(route); });
  await page.goto(`${base}/run-console/?case=${caseA.id}`, { waitUntil: "networkidle" });
  const select = page.locator("#pathway");
  await select.waitFor();
  const state = await select.evaluate((element) => ({ value: element.value, selectedDisabled: element.selectedOptions[0]?.disabled ?? null, selectedText: element.selectedOptions[0]?.textContent ?? null }));
  await page.getByRole("button", { name: "Compile and run" }).click();
  await page.waitForTimeout(500);
  out("S8-pathway-outside-cut", { selectState: state, note: await page.locator("#pathway-availability").textContent().catch(() => null), postedPathway: startBody?.pathway ?? null, submitted: startBody !== null });
  await context.close();
} catch (error) { out("S8-pathway-outside-cut", { error: String(error) }); }

// S9 — a browser recovery copy written under one subject is offered to another subject on the same profile.
try {
  const template = { template_id: "caos.full-credit.v1", template_version: "caos.deliverable-template.v1", pathway: "FULL_CREDIT", title: "Investment Committee Credit Memo", model_requirement: "OPTIONAL", allowed_appendices: [], optional_blocks: [], blocks: [{ block_id: "full-credit.section.01", slot_id: "section.01", kind: "NARRATIVE", title: "Credit Thesis", required: true, order: 1 }, { block_id: "full-credit.evidence-register", slot_id: "appendix.evidence-register", kind: "EVIDENCE_REGISTER", title: "Evidence Register", required: true, order: 2 }] };
  const workspace = { template, current: null, history: [], frozen_history: [], model_eligibility: { active_revision: null, application_build: null, fallback_acknowledgement_required: false, default_model_selection: null }, opinion: { head: null, current: false, reasons: ["OPINION_SIGNOFF_REQUIRED"] }, pending_freezes: [] };
  let subject = "analyst-a";
  const { context, page } = await newPage({ me: { role: "ANALYST", subject: "analyst-a" } });
  await page.unroute((url) => url.pathname === "/api/me");
  await page.route((url) => url.pathname === "/api/me", (route) => json({ role: "ANALYST", subject })(route));
  await page.route((url) => url.pathname === `/api/cases/${caseA.id}/sources`, json([]));
  await page.route((url) => url.pathname === `/api/cases/${caseA.id}/deliverables/FULL_CREDIT/draft`, (route) => route.request().method() === "GET" ? json(workspace)(route) : json({ detail: "store unavailable" }, 503)(route));
  await page.goto(`${base}/report-studio/?case=${caseA.id}`, { waitUntil: "networkidle" });
  await page.getByRole("textbox", { name: "Credit Thesis" }).fill("Analyst A's unsaved thesis.");
  await page.waitForFunction(() => Object.keys(localStorage).some((key) => key.startsWith("caos:report-recovery:")));
  const keys = await page.evaluate(() => Object.keys(localStorage).filter((key) => key.startsWith("caos:report-recovery:")));
  subject = "analyst-b";
  await page.goto(`${base}/report-studio/?case=${caseA.id}`, { waitUntil: "networkidle" });
  const banner = page.getByText(/Unsaved browser copy from/);
  await banner.waitFor({ timeout: 5000 }).catch(() => {});
  out("S9-recovery-across-subjects", { storageKeys: keys, secondSubject: subject, bannerOfferedToSecondSubject: await banner.count(), restoreControl: await page.getByRole("button", { name: "Restore copy" }).count() });
  await context.close();
} catch (error) { out("S9-recovery-across-subjects", { error: String(error) }); }

// S10 — the dirty-draft browser-history focus race, N iterations on fresh pages.
const focusResults = [];
for (let iteration = 1; iteration <= iterations; iteration += 1) {
  const counters = { previews: 0, tornados: 0 };
  const { context, page } = await newPage();
  try {
    await mockModel(page, counters);
    await page.addInitScript(() => {
      window.__focusLog = [];
      document.addEventListener("focusin", (event) => window.__focusLog.push({ t: Math.round(performance.now()), to: `${event.target.tagName}[${event.target.getAttribute?.("aria-label") || event.target.id || ""}]` }), true);
    });
    await page.goto(`${base}/model-builder/?case=${caseA.id}`, { waitUntil: "networkidle" });
    const first = page.getByLabel("Revenue growth, FY2025, BASE", { exact: true });
    await first.fill("0.04"); await first.press("Enter");
    await page.getByText(/Forecast recalculated/).waitFor();
    await page.evaluate(() => { const url = new URL(window.location.href); url.searchParams.set("probe-history", "prior"); window.history.pushState({ probe: "prior" }, "", url); });
    await first.fill("0.06"); await first.press("Enter");
    const dialog = () => page.getByRole("dialog", { name: "Discard draft changes?" });
    const caseSelect = page.getByRole("combobox", { name: "Select case" });
    await caseSelect.selectOption(caseB.id);
    await dialog().waitFor();
    await dialog().getByRole("button", { name: "Keep editing" }).click();
    await page.waitForFunction(() => document.activeElement?.id === "case-select");
    const sourcesLink = page.getByRole("link", { name: "Sources", exact: true }).first();
    await sourcesLink.click();
    await dialog().waitFor();
    await dialog().getByRole("button", { name: "Keep editing" }).click();
    await page.waitForFunction(() => document.activeElement?.getAttribute("href")?.startsWith("/sources") === true);
    await page.getByRole("button", { name: "Open command palette" }).click();
    const palette = page.getByRole("dialog", { name: "Command palette" });
    await palette.getByRole("combobox", { name: "Search cases, workflows or evidence IDs" }).fill("Sources");
    await palette.getByRole("option", { name: "Open Sources" }).click();
    await dialog().waitFor();
    await dialog().getByRole("button", { name: "Keep editing" }).click();
    await page.waitForFunction(() => document.activeElement?.getAttribute("aria-label") === "Open command palette");
    await first.focus();
    await page.waitForFunction(() => { const s = window.history.state; return Boolean(s?.caosModelDraftGuard || s?.caosReportDraftGuard) && Boolean(s.caosDraftHistoryEntryId && s.caosDraftHistoryBaseId) && s.caosDraftHistoryEntryId !== s.caosDraftHistoryBaseId; });
    await page.waitForTimeout(2500);
    const beforeBack = await page.evaluate(() => ({ active: document.activeElement?.getAttribute("aria-label") || document.activeElement?.tagName, t: Math.round(performance.now()) }));
    await page.evaluate(() => window.history.back());
    await dialog().waitFor();
    await page.keyboard.press("Escape");
    await dialog().waitFor({ state: "hidden" });
    let outcome = "pass";
    await page.waitForFunction(() => document.activeElement?.getAttribute("aria-label") === "Revenue growth, FY2025, BASE", null, { timeout: 5000 }).catch(() => { outcome = "fail"; });
    const finalFocus = await page.evaluate(() => document.activeElement?.getAttribute("aria-label") || document.activeElement?.tagName);
    const log = await page.evaluate(() => window.__focusLog.slice(-12));
    focusResults.push({ iteration, outcome, focusBeforeBack: beforeBack.active, finalFocus, tornadoPosts: counters.tornados, previewPosts: counters.previews, tail: log });
  } catch (error) {
    focusResults.push({ iteration, outcome: "harness-error", error: String(error).split("\n")[0] });
  }
  await context.close();
}
out("S10-focus-race", { iterations, passes: focusResults.filter((r) => r.outcome === "pass").length, fails: focusResults.filter((r) => r.outcome === "fail").length, harnessErrors: focusResults.filter((r) => r.outcome === "harness-error").length, results: focusResults });

await browser.close();
