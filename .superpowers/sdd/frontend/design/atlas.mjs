// FE-A2 screenshot atlas + computed-style measurements against the host-control
// server on :8773 (real seeded cases from the workbench smoke; Model Builder READY
// and the paused research plan use the a11y sweep's fixtures because host control
// yields no READY model and no live approval gate on a seeded case). No role
// header is sent: the development identity edge treats a headerless call as
// ANALYST (identity.py), and the one reader capture fixtures /api/me.
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { chromium, request } from "/Users/ericguei/Claude/Projects/CAOS-LangMVP/.claude/worktrees/frontend-design-truth-ca9b32/caos/frontend/node_modules/playwright/index.mjs";

const baseURL = process.env.CAOS_URL || "http://127.0.0.1:8773";
const outDir = process.env.ATLAS_DIR;
mkdirSync(outDir, { recursive: true });
const api = await request.newContext({ baseURL });
const cases = await (await api.get("/api/cases")).json();
const accepted = cases.find((c) => c.accepted_snapshot_id);
const snapshot = await (await api.get(`/api/cases/${accepted.id}/snapshot`)).json();
const artifactId = snapshot.accepted.artifacts.find((a) => a.module_id === "CP-L10")?.id || snapshot.accepted.artifacts[0].id;
let rvCase = null;
const unaccepted = [];
for (const c of cases) {
  if (!rvCase) { const rv = await (await api.get(`/api/cases/${c.id}/rv/loan-universes/active`)).json(); if (rv.status === "ACTIVE") rvCase = c; }
  if (!c.accepted_snapshot_id && c.current_execution_id) {
    const run = await (await api.get(`/api/runs/${c.current_execution_id}`)).json();
    if (run.status === "succeeded") unaccepted.push({ caseId: c.id, runId: run.id, pathway: run.plan.pathway });
  }
}
const log = { cases: { accepted: accepted.id, acceptedRun: accepted.current_execution_id, artifactId, rvCase: rvCase?.id, unaccepted }, shots: [], measurements: {}, fonts: {}, geometry: {}, notes: [] };
const browser = await chromium.launch({ headless: true });
const viewports = [{ tag: "1440", width: 1440, height: 1000 }, { tag: "720", width: 720, height: 900 }];

async function settle(page) { await page.waitForLoadState("networkidle"); await page.waitForTimeout(250); }
async function shot(page, name, opts = {}) {
  const file = path.join(outDir, `${name}.png`);
  await page.screenshot({ path: file, fullPage: opts.fullPage ?? true, animations: "disabled", ...(opts.clip ? { clip: opts.clip } : {}) });
  log.shots.push(name);
}
async function clip(page, selector, name) {
  const el = page.locator(selector).first();
  if (!(await el.count())) { log.notes.push(`missing ${selector} for ${name}`); return; }
  await el.scrollIntoViewIfNeeded().catch(() => {});
  const file = path.join(outDir, `${name}.png`);
  await el.screenshot({ path: file, animations: "disabled" }).then(() => log.shots.push(name)).catch((e) => log.notes.push(`clip ${name}: ${e.message.split("\n")[0]}`));
}
const url = (p, q = {}) => `${baseURL}${p}${Object.keys(q).length ? "?" + new URLSearchParams(q) : ""}`;

// --- fixtures reused from scripts/a11y-axe.mjs (ready model) and its pending plan ---
const modelBuildId = "model_atlas_ready";
function modelFixtures(caseId) {
  const modelBuild = { id: modelBuildId, case_id: caseId, accepted_run_id: accepted.current_execution_id, accepted_snapshot_id: snapshot.accepted.id, source_set_id: snapshot.accepted.source_set_id, input_fingerprint: "a".repeat(64), status: "READY", queued_at: "2026-08-24T00:00:00Z", started_at: "2026-08-24T00:00:01Z", completed_at: "2026-08-24T00:00:02Z", error: null, export: { status: "NOT_REQUESTED", error: null }, qa: { status: "PASS", semantic_check_count: 2, formula_count: 1, worksheet_cell_count: 3 }, payload_digest: "b".repeat(64) };
  const readiness = { status: "READY", module_id: "CP-MODEL", accepted_snapshot: { id: snapshot.accepted.id, run_id: accepted.current_execution_id, digest: "c".repeat(64) }, source_set: { id: snapshot.accepted.source_set_id, version: 1, digest: "d".repeat(64) }, requirements: ["CP-1", "CP-1A", "CP-1B", "CP-2", "CP-2A", "CP-2B"].map((module_id) => ({ module_id, status: "READY", digest: "e".repeat(64) })), blockers: [], build: modelBuild };
  const cell = (address, row, column, value, value_type, extra = {}) => ({ address, row, column, value, value_type, formula: null, semantic_id: null, owner: null, write_class: null, period_id: null, source_refs: null, number_format: "General", style: { bold: false, italic: false, fill: null, align: "left", wrap: false }, ...extra });
  const tab = (name) => ({ id: name.toUpperCase().replaceAll(" ", "_"), title: name, max_row: 7, max_column: 5, freeze_panes: "B2", merged_cells: [], columns: [1, 2, 3, 4, 5].map((column) => ({ column, letter: "ABCDE"[column - 1], width: column === 1 ? 26 : 12, hidden: false })), cells: [
    cell("A1", 1, 1, name, "text", { style: { bold: true, italic: false, fill: "0A2E63", align: "left", wrap: false } }),
    ...["FY2023A", "FY2024A", "FY2025E", "FY2026E"].map((p, i) => cell(`${"BCDE"[i]}1`, 1, i + 2, p, "text", { style: { bold: true, italic: false, fill: "1F4E78", align: "right", wrap: false } })),
    cell("A2", 2, 1, "Income statement", "text", { style: { bold: true, italic: false, fill: "D9EAF7", align: "left", wrap: false } }),
    cell("A3", 3, 1, "Revenue", "text", { style: { bold: false, italic: false, fill: "EAF3F8", align: "left", wrap: false } }),
    cell("B3", 3, 2, 1820.4, "number", { semantic_id: "account::revenue", owner: "CP-1", write_class: "SOURCE", period_id: "FY2023", source_refs: "SRC-1 | page 12 | 2026-08-24", number_format: "#,##0.0" }),
    cell("C3", 3, 3, 1964.2, "number", { semantic_id: "account::revenue", owner: "CP-1", write_class: "SOURCE", period_id: "FY2024", source_refs: "SRC-1 | page 12 | 2026-08-24", number_format: "#,##0.0" }),
    cell("D3", 3, 4, 2023.1, "formula", { formula: "=C3*(1+D5)", owner: "CP-MODEL", write_class: "FORMULA", period_id: "FY2025", number_format: "#,##0.0" }),
    cell("E3", 3, 5, 2083.8, "formula", { formula: "=D3*(1+E5)", owner: "CP-MODEL", write_class: "FORMULA", period_id: "FY2026", number_format: "#,##0.0" }),
    cell("A4", 4, 1, "EBITDA", "text", { style: { bold: false, italic: false, fill: "EAF3F8", align: "left", wrap: false } }),
    cell("B4", 4, 2, 312.5, "number", { write_class: "SOURCE", period_id: "FY2023", source_refs: "SRC-1 | page 14", number_format: "#,##0.0" }),
    cell("C4", 4, 3, 341.0, "number", { write_class: "SOURCE", period_id: "FY2024", source_refs: "SRC-1 | page 14", number_format: "#,##0.0" }),
    cell("D4", 4, 4, 356.1, "formula", { formula: "=D3*0.176", write_class: "FORMULA", period_id: "FY2025", number_format: "#,##0.0", style: { bold: false, italic: false, fill: "E2F0D9", align: "right", wrap: false } }),
    cell("E4", 4, 5, -12.4, "formula", { formula: "=E3*0.176-380", write_class: "FORMULA", period_id: "FY2026", number_format: "#,##0.0", style: { bold: false, italic: false, fill: "FCE4D6", align: "right", wrap: false } }),
    cell("A5", 5, 1, "Revenue growth", "text", { style: { bold: false, italic: true, fill: "EAF3F8", align: "left", wrap: false } }),
    cell("D5", 5, 4, 0.03, "number", { write_class: "ASSUMPTION", period_id: "FY2025", number_format: "0.0%", style: { bold: false, italic: false, fill: "FFF4CC", align: "right", wrap: false } }),
    cell("E5", 5, 5, 0.03, "number", { write_class: "ASSUMPTION", period_id: "FY2026", number_format: "0.0%", style: { bold: false, italic: false, fill: "FFF4CC", align: "right", wrap: false } }),
    cell("A7", 7, 1, "Net leverage", "text", { style: { bold: true, italic: false, fill: "E7E6E6", align: "left", wrap: false } }),
    cell("C7", 7, 3, 4.2, "formula", { formula: "=C9/C4", write_class: "FORMULA", period_id: "FY2024", number_format: "0.0x", style: { bold: true, italic: false, fill: null, align: "right", wrap: false } }),
  ] });
  const definition = { assumption_id: "operating.consolidated_revenue_growth", label: "Revenue growth", family: "Operating", description: "Consolidated annual revenue growth.", driver_id: "consolidated_revenue_growth", slot_id: null, value_type: "DECIMAL", unit: "PERCENT_DECIMAL", cases: ["BASE", "DOWNSIDE"], periods: ["FY2025", "FY2026", "FY2027"], default: { status: "READY", value: 0.03 }, lineage: { authority_module: "CP-2G" }, sensitivity_default: { range: "0.04", step: "0.01" }, hard_min: "-0.75", hard_max: "2", required: true, allowed_statuses: ["READY"], degradation: null, affected_outputs: ["revenue", "total_leverage"] };
  const defaults = ["BASE", "DOWNSIDE"].flatMap((caseName) => ["FY2025", "FY2026", "FY2027"].map((periodId) => ({ assumption_id: definition.assumption_id, case: caseName, period_id: periodId, unit: "PERCENT", status: "READY", value: caseName === "BASE" ? "0.03" : "-0.02", gap_code: null, default_value: caseName === "BASE" ? "0.03" : "-0.02", default_status: "READY", default_gap_code: null, source_context: { authority_module: "CP-2G", gap_code: "", provenance: [{ source_id: "SRC-1", source_locator: "page 1", as_of: "2026-08-24" }] }, source_context_digest: "f".repeat(64) })));
  const tornado = { output_id: "total_leverage", case: "BASE", output_period_id: "FY2026", baseline: "4.20", bars: [
    { assumption_id: "operating.consolidated_revenue_growth", label: "Revenue growth", low: "4.62", high: "3.81" },
    { assumption_id: "operating.ebitda_margin", label: "EBITDA margin", low: "4.90", high: "3.60" },
    { assumption_id: "capex", label: "Capex intensity", low: "4.05", high: "4.35" },
    { assumption_id: "interest", label: "Interest rate", low: "4.10", high: "4.30" },
  ] };
  return { modelBuild, readiness, tabs: [tab("Credit Snapshot"), tab("Model"), tab("KPIs")], definition, defaults, tornado };
}
async function routeModel(page, caseId) {
  const f = modelFixtures(caseId);
  await page.route((u) => u.pathname === `/api/cases/${caseId}/model`, (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(f.readiness) }));
  await page.route((u) => u.pathname === `/api/cases/${caseId}/models`, (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ builds: [f.modelBuild] }) }));
  await page.route((u) => u.pathname === `/api/cases/${caseId}/models/assumption-registry`, (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ version: "cp-model-assumptions.v1", digest: "f".repeat(64), definitions: [f.definition], build_id: modelBuildId, accepted_snapshot_id: f.modelBuild.accepted_snapshot_id, input_fingerprint: f.modelBuild.input_fingerprint, defaults: f.defaults }) }));
  await page.route((u) => u.pathname === `/api/cases/${caseId}/model-revisions`, (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ revisions: [] }) }));
  await page.route((u) => u.pathname === `/api/cases/${caseId}/models/${modelBuildId}/worksheet`, (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ build_id: modelBuildId, input_fingerprint: f.modelBuild.input_fingerprint, payload_digest: f.modelBuild.payload_digest, qa: f.modelBuild.qa, payload: { schema_version: "caos.model.worksheet.v1", identity: { issuer_id: "northstar", issuer_name: accepted.issuer, analysis_date: "2026-08-24" }, tabs: f.tabs } }) }));
  await page.route((u) => u.pathname === `/api/cases/${caseId}/models/tornado`, (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(f.tornado) }));
}
const planHash = `sha256:${"b".repeat(64)}`;
function pendingPlanFixture(caseId, runId) {
  const caseFixture = { ...accepted, id: caseId, current_execution_id: runId, deep_research_available: true, deep_research_unavailable_reason: null };
  const runFixture = { id: runId, case_id: caseId, status: "paused", plan: { pathway: "DEEP_RESEARCH", depth: "full", profile_id: "DEEP_RESEARCH_FULL", selection_id: "atlas-fixture" }, nodes: [{ id: "node-parse", module_id: "CP-PARSE", status: "succeeded" }, { id: "node-cp0", module_id: "CP-0", status: "succeeded" }, { id: "node-cpdr", module_id: "CP-DR", status: "pending" }, { id: "node-cp5", module_id: "CP-5", status: "pending" }], error: { code: "PLAN_APPROVAL_REQUIRED", message: "Approve the exact deterministic research plan before agent execution." }, research: { phase: "awaiting_approval", proposed_plan_hash: planHash, proposed_plan: { methodology_build_id: "deploy-v-atlas", brief_digest: "sha256:" + "a".repeat(64), source_set: { id: snapshot.accepted.source_set_id, version: 1 }, upstream_artifacts: [{ module_id: "CP-0", artifact_id: artifactId, digest: "c".repeat(64) }], scope: { type: "issuer", key: accepted.issuer.toLowerCase(), source_mode: "supplied_only" }, workstreams: [{ id: "WS-1", kind: "topical", question: "Can the issuer refinance the 2027 notes from supplied sources?", assigned_questions: ["Liquidity runway?", "Maturity wall?"], perspective: "Buy-side credit analyst", hypothesis: "Liquidity supports refinancing.", evidence_needs: ["Debt maturity schedule", "Cash and revolver availability"], source_classes: ["supplied_case_sources"], disconfirming_test: "Find contrary supplied evidence.", completion_test: "Answer with source locators or record the gap.", effort_cap: "Within the fixed standard research budget." }] } } };
  return { caseFixture, runFixture };
}

// --- computed-style measurement ---
const measureSelectors = {
  "body": "body", ".wordmark": ".wordmark", ".wordmark small": ".wordmark small", ".brand-mark": ".brand-mark", ".nav-label": ".nav-label", ".nav-link": ".rail .nav-link", ".nav-link .shortcut": ".nav-link .shortcut", ".rail-meta": ".rail-meta",
  ".topbar h1": ".topbar-heading h1", ".meta-label": ".meta-label", ".authority-strip": ".authority-strip", ".authority-strip b": ".authority-strip b",
  ".panel-header h2": ".panel-header h2", ".panel-meta": ".panel-meta", ".button": ".content .button:not(.primary):not(.small)", ".button.primary": ".button.primary", ".button.small": ".button.small", ".top-actions kbd": ".top-actions kbd",
  ".field label": ".field label", ".field input": ".field input", "th": "th", "td": "td", "caption": "caption", ".status": ".status", ".mono": ".content .mono", ".num": ".num", ".muted": ".content .muted",
  ".evidence-chip": ".evidence-chip", ".flag": ".flag", ".section-heading h3": ".section-heading h3", ".callout": ".callout", ".empty": ".empty", ".state-block": ".state-block", ".dag-edge": ".dag-edge", ".dag-node": ".dag-node", ".dag-node-open": ".dag-node-open",
  ".standing-answer h2": ".standing-answer > h2", ".authority-metrics strong": ".authority-metrics strong", ".proof-register strong": ".proof-register strong", ".credit-authority-head h2": ".credit-authority-head h2", ".credit-proof h2": ".credit-proof > h2",
  ".analysis-reader h2": ".analysis-reader > h2", ".analysis-lead": ".analysis-lead", ".analysis-copy p": ".analysis-copy p", ".analysis-copy h3": ".analysis-copy h3", ".analysis-toc button": ".analysis-toc button", ".analysis-evidence h2": ".analysis-evidence > h2",
  ".source-reader h2": ".source-reader > h2", ".source-region-head h2": ".source-region-head h2", ".source-document-block button": ".source-document-block button",
  ".worksheet-tab": ".worksheet-tab", ".worksheet-grid": ".worksheet-grid", ".worksheet-grid td": ".worksheet-cell", ".worksheet-authority-note": ".worksheet-authority-note", ".lineage-code": ".lineage-code",
  ".loan-table": ".loan-table", ".loan-table th": ".loan-table thead th", ".loan-groups th": ".loan-groups th",
  ".admin-intro h2": ".admin-intro h2", ".drawer-header h2": ".drawer-header h2", "dialog": "dialog[open]", ".palette-hint": ".palette-hint", ".palette-hint kbd": ".palette-hint kbd",
  ".report-section-nav button": ".report-section-nav button", ".report-section-nav small": ".report-section-nav small", ".report-history h3": ".report-history h3", ".report-optional summary": ".report-optional summary",
  ".rd-mast-brand": ".rd-mast-brand", ".rd-mark": ".rd-mark", ".rd-mast-meta": ".rd-mast-meta", ".rd-title": ".rd-title", ".rd-subtitle": ".rd-subtitle", ".rd-identity": ".rd-identity", ".rd-band": ".rd-band", ".rd-masthead-facts": ".rd-masthead-facts", ".rd-h": ".rd-h", ".rd-h-sub": ".rd-h-sub", ".rd-body": ".rd-body", ".rd-table th": ".rd-table thead th", ".rd-table td": ".rd-table tbody td", ".rd-prow": ".rd-prow", ".rd-list li": ".rd-list li", ".rd-note": ".rd-note", ".rd-foot": ".rd-foot", ".rd-empty": ".rd-empty", ".rd-wm span": ".rd-wm span", ".deliverable-document": ".deliverable-document",
  ".mutation-receipt": ".mutation-receipt", ".mutation-receipt > :first-child": ".mutation-receipt > :first-child", ".run-progress-track": ".run-progress-track", ".dropzone": ".dropzone", ".dropzone label span": ".dropzone label span", ".source-register-row": ".source-register-row", ".history-entry > span": ".history-entry > span",
  ".research-brief legend": ".research-brief legend", ".research-workstreams h5": ".research-workstreams h5", ".run-summary-modules li": ".run-summary-modules li", ".model-builder-command-body p": ".model-builder-command-body p",
};
const props = ["fontFamily", "fontSize", "fontWeight", "lineHeight", "letterSpacing", "textTransform", "color", "backgroundColor", "borderColor", "borderRadius", "boxShadow", "minHeight", "padding", "fontVariantNumeric", "outlineColor"];
async function measure(page, keys) {
  const result = await page.evaluate(({ sel, props }) => {
    const out = {};
    for (const [key, s] of Object.entries(sel)) {
      const el = document.querySelector(s);
      if (!el) continue;
      const cs = getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      out[key] = Object.fromEntries(props.map((p) => [p, cs[p]]));
      out[key].box = { w: Math.round(rect.width), h: Math.round(rect.height) };
      out[key].text = (el.textContent || "").trim().slice(0, 40);
    }
    return out;
  }, { sel: Object.fromEntries(keys.map((k) => [k, measureSelectors[k]])), props });
  for (const [k, v] of Object.entries(result)) if (!log.measurements[k]) log.measurements[k] = v;
}
async function platformFonts(page, selectors) {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("DOM.enable"); await cdp.send("CSS.enable");
  const { root } = await cdp.send("DOM.getDocument", { depth: -1 });
  for (const s of selectors) {
    try {
      const { nodeId } = await cdp.send("DOM.querySelector", { nodeId: root.nodeId, selector: s });
      if (!nodeId) continue;
      const { fonts } = await cdp.send("CSS.getPlatformFontsForNode", { nodeId });
      log.fonts[s] = fonts.map((f) => `${f.familyName}${f.postScriptName ? ` (${f.postScriptName})` : ""} ×${f.glyphCount}`);
    } catch (e) { log.notes.push(`fonts ${s}: ${e.message.split("\n")[0]}`); }
  }
  await cdp.detach();
}
async function geometry(page, tag, selectors) {
  const g = await page.evaluate((sels) => Object.fromEntries(sels.map((s) => { const el = document.querySelector(s); if (!el) return [s, null]; const r = el.getBoundingClientRect(); return [s, { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }]; })), selectors);
  log.geometry[tag] = { ...(log.geometry[tag] || {}), ...g };
}

for (const vp of viewports) {
  const t = vp.tag;
  const context = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
  const page = await context.newPage();

  // 1 Cases (Portfolio) — intake, register, create, fit
  await page.goto(url("/cases/", { case: accepted.id })); await settle(page);
  await shot(page, `${t}-01-cases`);
  await geometry(page, t, [".rail", ".wordmark", ".brand-mark", ".topbar", ".topbar h1", ".authority-strip", ".content", ".panel-header", ".cases-intake", ".cases-register", ".cases-create", ".button.primary", "#case-select", "#command-palette-trigger", ".dropzone", ".worklist-toolbar", ".nav-link", ".rail-meta"]);
  if (t === "1440") {
    await measure(page, ["body", ".wordmark", ".wordmark small", ".brand-mark", ".nav-label", ".nav-link", ".rail-meta", ".topbar h1", ".meta-label", ".authority-strip", ".authority-strip b", ".panel-header h2", ".panel-meta", ".button.primary", ".button.small", ".top-actions kbd", ".field label", ".field input", "th", "td", ".status", ".mono", ".muted", ".dropzone", ".dropzone label span", ".button"]);
    await platformFonts(page, [".wordmark > span", ".topbar-heading h1", ".panel-body p", ".authority-strip", ".rail-meta span", ".panel-header h2"]);
    await clip(page, ".rail", `${t}-c-rail`);
    await clip(page, ".wordmark", `${t}-c-wordmark`);
    await clip(page, ".topbar", `${t}-c-topbar`);
    await clip(page, ".authority-strip", `${t}-c-authority-strip`);
    await clip(page, ".cases-register", `${t}-c-panel-register-table`);
    await clip(page, ".cases-create", `${t}-c-panel-create-form-inputs`);
    await clip(page, ".cases-intake", `${t}-c-intake-dropzone`);
    await clip(page, ".cases-fit", `${t}-c-panel-fit-status`);
    await clip(page, ".context-strip", `${t}-c-context-strip`);
    // hover + focus states on a button and a nav link
    await page.locator(".rail .nav-link").nth(2).hover(); await page.waitForTimeout(200); await clip(page, ".rail nav.nav-group", `${t}-c-nav-hover`);
    await page.locator("#case-search").focus(); await page.waitForTimeout(200); await clip(page, ".worklist-toolbar", `${t}-c-input-focus`);
    await page.keyboard.press("Tab"); await page.waitForTimeout(150);
    await page.locator("#command-palette-trigger").focus(); await page.waitForTimeout(150); await clip(page, ".top-actions", `${t}-c-button-focus-ring`);
  } else {
    await clip(page, ".rail", `${t}-c-rail`);
    await clip(page, ".topbar", `${t}-c-topbar`);
    await clip(page, ".authority-strip", `${t}-c-authority-strip`);
  }
  // intake refusal (real typed refusal: an unsupported file)
  try {
    await page.setInputFiles("#intake-files", { name: "scan.exe", mimeType: "application/octet-stream", buffer: Buffer.from("MZ  not a document") });
    await page.getByRole("button", { name: /Analyze 1 document/ }).click();
    await page.locator(".empty.error-state, .callout.warning, .action-state").first().waitFor({ timeout: 15000 });
    await settle(page);
    await shot(page, `${t}-02-cases-intake-refusal`);
    await clip(page, ".cases-intake", `${t}-c-state-critical-intake-refusal`);
  } catch (e) { log.notes.push(`intake refusal ${t}: ${e.message.split("\n")[0]}`); await shot(page, `${t}-02-cases-intake-attempt`); }

  // 2 Sources with evidence focus
  await page.goto(url("/sources/", { case: accepted.id, artifact: artifactId })); await settle(page);
  await page.locator(".source-register-row").first().click().catch(() => {}); await page.waitForTimeout(300);
  await page.locator(".source-document-block button").first().click().catch(() => {}); await page.waitForTimeout(300);
  await shot(page, `${t}-03-sources-evidence-focus`);
  if (t === "1440") {
    await measure(page, [".evidence-chip", ".source-reader h2", ".source-region-head h2", ".source-document-block button", ".section-heading h3", ".state-block"]);
    await clip(page, ".evidence-focus", `${t}-c-panel-artifact-reader-chips`);
    await clip(page, ".evidence-list", `${t}-c-evidence-chips`);
    await clip(page, ".source-workspace", `${t}-c-source-workspace`);
    await clip(page, ".source-support", `${t}-c-state-unavailable-coverage`);
    await page.locator(".evidence-chip").first().hover(); await page.waitForTimeout(200); await clip(page, ".evidence-list", `${t}-c-evidence-chip-hover-linked`);
  }
  // evidence drawer
  const chip = page.locator(".evidence-chip").first();
  if (await chip.count()) {
    await chip.click(); await page.locator("#context-drawer[open]").waitFor(); await page.waitForTimeout(300);
    await shot(page, `${t}-04-evidence-drawer`, { fullPage: false });
    if (t === "1440") { await measure(page, [".drawer-header h2", "dialog"]); await clip(page, "#context-drawer", `${t}-c-drawer`); }
    await page.keyboard.press("Escape"); await page.waitForTimeout(200);
  } else log.notes.push(`no evidence chip on sources ${t}`);

  // 3 Run console — accepted run
  await page.goto(url("/run-console/", { case: accepted.id, run: accepted.current_execution_id })); await settle(page);
  await shot(page, `${t}-05-run-console-accepted`);
  if (t === "1440") {
    await measure(page, [".dag-edge", ".dag-node", ".dag-node-open", ".callout", ".run-progress-track", ".research-brief legend", ".run-summary-modules li"]);
    await clip(page, ".panel.span-8", `${t}-c-panel-execution-route-dag`);
    await clip(page, ".dag", `${t}-c-dag-tiles`);
    await clip(page, ".run-progress", `${t}-c-run-progress`);
    await clip(page, ".panel.span-4", `${t}-c-panel-compile-form-selects`);
    await clip(page, ".callout", `${t}-c-callout-neutral`);
    await clip(page, ".run-acceptance", `${t}-c-approval-panel-accepted`);
    // Deep Research brief fieldset
    await page.selectOption("#pathway", "DEEP_RESEARCH").catch(() => {}); await page.waitForTimeout(200);
    await clip(page, ".research-brief", `${t}-c-research-brief-fieldset`).catch(() => {});
  }

  // 4 Run console — succeeded, unaccepted → accept dialog → receipt
  const target = unaccepted[t === "1440" ? 0 : 1] || unaccepted[0];
  if (target) {
    await page.goto(url("/run-console/", { case: target.caseId, run: target.runId })); await settle(page);
    await shot(page, `${t}-06-run-console-ready-for-acceptance`);
    if (t === "1440") await clip(page, ".run-acceptance", `${t}-c-approval-panel-ready`);
    const acceptButton = page.getByRole("button", { name: "Accept analytical snapshot" }).first();
    if (await acceptButton.count()) {
      await acceptButton.click(); await page.locator("dialog[open][aria-labelledby=accept-dialog-title]").waitFor(); await page.waitForTimeout(300);
      await shot(page, `${t}-07-accept-dialog`, { fullPage: false });
      if (t === "1440") await clip(page, "dialog[open]", `${t}-c-dialog-accept`);
      await page.locator("dialog[open]").getByRole("button", { name: "Accept analytical snapshot" }).click();
      await page.locator(".mutation-receipt").waitFor({ timeout: 15000 }).catch((e) => log.notes.push(`receipt ${t}: ${e.message.split("\n")[0]}`));
      await settle(page);
      await shot(page, `${t}-08-run-console-receipt`);
      if (t === "1440") { await measure(page, [".mutation-receipt", ".mutation-receipt > :first-child"]); await clip(page, ".mutation-receipt", `${t}-c-mutation-receipt`); }
    } else log.notes.push(`no accept button for ${target.caseId} at ${t}`);
  }

  // 5 Run console — paused for research-plan approval (a11y fixture shapes)
  {
    const fx = pendingPlanFixture(accepted.id, "run_atlas_pending_plan");
    const ctx2 = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
    const p2 = await ctx2.newPage();
    await p2.route((u) => u.pathname === `/api/cases/${accepted.id}`, (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(fx.caseFixture) }));
    await p2.route((u) => u.pathname === `/api/runs/${fx.runFixture.id}`, (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(fx.runFixture) }));
    await p2.route((u) => u.pathname === `/api/runs/${fx.runFixture.id}/events`, (r) => r.fulfill({ status: 200, contentType: "text/event-stream", body: "retry: 60000\n\n" }));
    await p2.goto(url("/run-console/", { case: accepted.id, run: fx.runFixture.id })); await settle(p2);
    await p2.getByRole("heading", { name: "Proposed research plan" }).waitFor({ timeout: 10000 }).catch((e) => log.notes.push(`pending plan ${t}: ${e.message.split("\n")[0]}`));
    await shot(p2, `${t}-09-run-console-paused-plan-approval`);
    if (t === "1440") { await measure(p2, [".research-workstreams h5"]); await clip(p2, ".research-plan", `${t}-c-research-plan`); await clip(p2, ".run-acceptance", `${t}-c-approval-panel-blocked`); }
    await ctx2.close();
  }

  // 6 Deep-Dive reader
  await page.goto(url("/deep-dive/", { case: accepted.id })); await settle(page);
  await shot(page, `${t}-10-deep-dive`);
  if (t === "1440") {
    await measure(page, [".analysis-reader h2", ".analysis-lead", ".analysis-copy p", ".analysis-copy h3", ".analysis-toc button", ".analysis-evidence h2"]);
    await clip(page, ".analysis-toc", `${t}-c-analysis-toc`);
    await clip(page, ".analysis-evidence", `${t}-c-analysis-evidence-rail`);
  }

  // 7 RV screener — loan table
  if (rvCase) {
    await page.goto(url("/rv-screener/", { case: rvCase.id })); await settle(page);
    await shot(page, `${t}-11-rv-screener`);
    if (t === "1440") {
      await measure(page, [".loan-table", ".loan-table th", ".loan-groups th", ".flag"]);
      await clip(page, ".loan-table-wrap", `${t}-c-loan-table`);
      await clip(page, ".loan-filters", `${t}-c-loan-filters`);
      await clip(page, ".loan-authority", `${t}-c-loan-authority`);
    }
  } else log.notes.push("no active loan universe found");

  // 8 Command Center — standing answer
  await page.goto(url("/command-center/", { case: accepted.id })); await settle(page);
  await shot(page, `${t}-12-command-center`);
  if (t === "1440") {
    await measure(page, [".standing-answer h2", ".authority-metrics strong", ".proof-register strong", ".credit-authority-head h2", ".credit-proof h2"]);
    await platformFonts(page, [".standing-answer > h2", ".authority-metrics strong", ".standing-answer > p"]);
    await clip(page, ".standing-answer", `${t}-c-standing-answer`);
    await clip(page, ".authority-metrics", `${t}-c-authority-metrics`);
    await clip(page, ".credit-proof", `${t}-c-credit-proof`);
    await clip(page, ".credit-actions", `${t}-c-buttons-primary-secondary`);
  }

  // 9 Model Builder READY (fixture)
  {
    const ctx3 = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
    const p3 = await ctx3.newPage();
    await routeModel(p3, accepted.id);
    await p3.goto(url("/model-builder/", { case: accepted.id })); await settle(p3);
    await p3.getByRole("tab", { name: "Credit Snapshot" }).waitFor({ timeout: 10000 }).catch((e) => log.notes.push(`model ${t}: ${e.message.split("\n")[0]}`));
    await p3.locator(".worksheet-cell[data-address=D3]").click().catch(() => {}); await p3.waitForTimeout(200);
    await shot(p3, `${t}-13-model-builder-ready`);
    if (t === "1440") {
      await measure(p3, [".worksheet-tab", ".worksheet-grid", ".worksheet-grid td", ".worksheet-authority-note", ".lineage-code", ".model-builder-command-body p"]);
      await clip(p3, ".worksheet-scroll", `${t}-c-worksheet-grid`);
      await clip(p3, ".worksheet-tabs", `${t}-c-worksheet-tabs`);
      await clip(p3, "#model-cell-lineage", `${t}-c-cell-lineage`);
      await clip(p3, "[aria-labelledby=forecast-assumptions-heading]", `${t}-c-forecast-assumptions-scrubber`);
      await clip(p3, "[aria-labelledby=tornado-heading]", `${t}-c-tornado`);
      // dirty draft → approval panel (what will bind)
      const scrubber = p3.locator("input[type=text], input:not([type])").filter({ has: p3.locator(":scope") }).first();
      const first = p3.locator("[aria-labelledby=forecast-assumptions-heading] input").nth(1);
      if (await first.count()) { await first.fill("0.05"); await first.press("Tab"); await p3.waitForTimeout(400); await clip(p3, "[data-model-approval]", `${t}-c-approval-panel-model-dirty`).catch(() => {}); await shot(p3, `${t}-14-model-builder-dirty`); }
      void scrubber;
    }
    await ctx3.close();
  }

  // 10 Report Studio — draft paper
  await page.goto(url("/report-studio/", { case: accepted.id })); await settle(page);
  await shot(page, `${t}-15-report-studio`);
  if (t === "1440") {
    await measure(page, [".report-section-nav button", ".report-section-nav small", ".report-history h3", ".report-optional summary", ".rd-mast-brand", ".rd-mark", ".rd-mast-meta", ".rd-title", ".rd-subtitle", ".rd-identity", ".rd-h", ".rd-h-sub", ".rd-body", ".rd-list li", ".rd-foot", ".rd-empty", ".deliverable-document", ".history-entry > span", ".rd-prow", ".rd-note"]);
    await platformFonts(page, [".rd-title", ".rd-body", ".rd-mast-brand", ".rd-h"]);
    await clip(page, ".report-outline", `${t}-c-report-outline`);
    await clip(page, ".report-compose", `${t}-c-report-compose`);
    await clip(page, ".report-paper", `${t}-c-paper-draft`);
    await clip(page, ".rd-mast", `${t}-c-paper-masthead`);
    await clip(page, ".approval-panel", `${t}-c-approval-panel-freeze`);
    await clip(page, ".report-authority-strip", `${t}-c-report-authority-strip`);
  }
  // discard dialog: type, then switch pathway
  try {
    const textarea = page.locator(".report-editor-scroll textarea").first();
    await textarea.fill("Atlas draft text — not saved."); await page.waitForTimeout(200);
    await page.selectOption("#report-pathway", "EARNINGS_UPDATE");
    await page.locator("dialog[open][aria-labelledby=discard-dialog-title]").waitFor({ timeout: 5000 });
    await page.waitForTimeout(300);
    await shot(page, `${t}-16-discard-dialog`, { fullPage: false });
    if (t === "1440") await clip(page, "dialog[open]", `${t}-c-dialog-discard`);
    await page.locator("dialog[open]").getByRole("button", { name: "Keep editing" }).click();
  } catch (e) { log.notes.push(`discard dialog ${t}: ${e.message.split("\n")[0]}`); }

  // 11 Admin Studio — unavailable capability
  await page.goto(url("/admin-studio/"), { waitUntil: "networkidle" }); await page.waitForTimeout(250);
  await shot(page, `${t}-17-admin-studio`);
  if (t === "1440") { await measure(page, [".admin-intro h2", ".flag"]); await clip(page, ".admin-intro", `${t}-c-admin-intro-flag`); await clip(page, ".admin-capability .panel", `${t}-c-admin-contracts-table`); }

  // 12 Not found
  await page.goto(url("/nope/"), { waitUntil: "networkidle" }); await page.waitForTimeout(250);
  await shot(page, `${t}-18-not-found`);

  // 13 Command palette
  await page.goto(url("/cases/", { case: accepted.id })); await settle(page);
  await page.locator("#command-palette-trigger").click(); await page.locator("dialog[open][aria-labelledby=palette-title]").waitFor(); await page.waitForTimeout(300);
  await shot(page, `${t}-19-command-palette`, { fullPage: false });
  if (t === "1440") { await measure(page, [".palette-hint", ".palette-hint kbd"]); await clip(page, "dialog[open]", `${t}-c-dialog-palette`); }
  await page.keyboard.type("north"); await page.waitForTimeout(300); await shot(page, `${t}-20-command-palette-query`, { fullPage: false });
  await page.keyboard.press("Escape");

  // 14 States: skeleton (held snapshot), error (500), empty panel (no cases), stale (switch_required)
  {
    const ctx4 = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
    const p4 = await ctx4.newPage();
    let release;
    const held = new Promise((resolve) => { release = resolve; });
    await p4.route((u) => u.pathname === `/api/cases/${accepted.id}/snapshot`, async (r) => { await held; await r.continue(); });
    await p4.goto(url("/deep-dive/", { case: accepted.id }), { waitUntil: "domcontentloaded" });
    await p4.locator(".state-skeleton").first().waitFor({ timeout: 10000 }).catch((e) => log.notes.push(`skeleton ${t}: ${e.message.split("\n")[0]}`));
    await p4.waitForTimeout(300);
    await shot(p4, `${t}-21-state-loading-skeleton`, { fullPage: false });
    if (t === "1440") { await measure(p4, [".authority-strip"]); await clip(p4, ".state-skeleton", `${t}-c-state-skeleton`); await clip(p4, ".authority-strip", `${t}-c-authority-strip-loading`); }
    release();
    await p4.unroute((u) => u.pathname === `/api/cases/${accepted.id}/snapshot`);
    // error
    await p4.route((u) => u.pathname === `/api/cases/${accepted.id}/snapshot`, (r) => r.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: { code: "STORE_UNAVAILABLE" } }) }));
    await p4.goto(url("/command-center/", { case: accepted.id })); await settle(p4);
    await shot(p4, `${t}-22-state-error`);
    if (t === "1440") { await measure(p4, [".empty"]); await clip(p4, ".empty.error-state", `${t}-c-state-critical-error-retry`); await clip(p4, ".authority-strip", `${t}-c-authority-strip-error`); }
    await p4.unroute((u) => u.pathname === `/api/cases/${accepted.id}/snapshot`);
    // stale: switch_required + diff
    const staleView = { ...snapshot, latest_accepted: { ...snapshot.accepted, id: "snap-atlas-newer", digest: "1".repeat(64) }, switch_required: true, diff: { changed: true, source_set_changed: true, added: [{ module_id: "CP-2", digest: "2".repeat(64) }], modified: [{ module_id: "CP-L10", digest: "3".repeat(64) }], removed: [] } };
    await p4.route((u) => u.pathname === `/api/cases/${accepted.id}/snapshot`, (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(staleView) }));
    await p4.goto(url("/deep-dive/", { case: accepted.id })); await settle(p4);
    await shot(p4, `${t}-23-state-stale-switch-required`);
    if (t === "1440") { await clip(p4, ".analysis-switch", `${t}-c-callout-warning-stale`); await clip(p4, ".authority-strip", `${t}-c-authority-strip-stale`); }
    await p4.goto(url("/command-center/", { case: accepted.id })); await settle(p4);
    await shot(p4, `${t}-24-command-center-what-changed`);
    if (t === "1440") await clip(p4, ".credit-change-section", `${t}-c-what-changed-list`);
    await p4.unroute((u) => u.pathname === `/api/cases/${accepted.id}/snapshot`);
    // empty: no cases at all
    await p4.route((u) => u.pathname === "/api/cases", (r) => r.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
    await p4.goto(url("/deep-dive/")); await settle(p4);
    await shot(p4, `${t}-25-state-empty-no-case`);
    if (t === "1440") await clip(p4, ".panel .empty", `${t}-c-state-empty-panel`);
    await p4.goto(url("/cases/")); await settle(p4);
    await shot(p4, `${t}-26-cases-empty-register`);
    await ctx4.close();
  }

  // 15 Reader role — WriteBlocked and reader-mode idle status
  {
    // The reader state is fixtured on the identity read the workspace makes
    // (/api/me), not by sending the development role header: that header is
    // read only by identity.py and the recorded review blocks it elsewhere.
    const ctx5 = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
    const p5 = await ctx5.newPage();
    await p5.route((u) => u.pathname === "/api/me", (r) => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ role: "READER", subject: "atlas.reader" }) }));
    await p5.goto(url("/run-console/", { case: accepted.id, run: accepted.current_execution_id })); await settle(p5);
    await shot(p5, `${t}-27-run-console-reader`);
    if (t === "1440") await clip(p5, ".panel.span-4", `${t}-c-state-write-blocked`);
    await ctx5.close();
  }

  // 16 Reduced motion + coarse pointer probe (computed values only)
  if (t === "1440") {
    const ctx6 = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, reducedMotion: "reduce", hasTouch: true });
    const p6 = await ctx6.newPage();
    await p6.goto(url("/cases/", { case: accepted.id })); await settle(p6);
    log.measurements["reduced-motion"] = await p6.evaluate(() => {
      const sk = document.querySelector(".state-skeleton span");
      const btn = document.querySelector(".button");
      const nav = document.querySelector(".nav-link");
      const cs = (el) => el ? { animationDuration: getComputedStyle(el).animationDuration, animationIterationCount: getComputedStyle(el).animationIterationCount, animationPlayState: getComputedStyle(el).animationPlayState, transitionDuration: getComputedStyle(el).transitionDuration, minHeight: getComputedStyle(el).minHeight, backgroundImage: getComputedStyle(el).backgroundImage } : null;
      return { skeleton: cs(sk), button: cs(btn), navLink: cs(nav), coarsePointer: matchMedia("(pointer: coarse)").matches, reduced: matchMedia("(prefers-reduced-motion: reduce)").matches };
    });
    await ctx6.close();
  }

  await context.close();
}
await browser.close();
writeFileSync(path.join(outDir, "..", "atlas-measurements.json"), JSON.stringify(log, null, 2));
console.log(JSON.stringify({ shots: log.shots.length, notes: log.notes }, null, 2));
