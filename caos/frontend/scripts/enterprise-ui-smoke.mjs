// Focused fixture coverage for operator controls and evidence UX. This is browser
// contract/state proof, never a live-provider or production journey verdict.
import assert from "node:assert/strict";
import AxeBuilder from "@axe-core/playwright";
import { chromium, firefox, webkit } from "playwright";
import { webkitTeardownRejection } from "./webkit-teardown.mjs";

const baseURL = process.env.CAOS_URL || "http://127.0.0.1:8000";
const browserName = process.env.CAOS_BROWSER || "chromium";
const browser = await ({ chromium, firefox, webkit })[browserName].launch();
const context = await browser.newContext();
const page = await context.newPage();
page.setDefaultTimeout(10000);
const navigate = async (url) => { await page.waitForLoadState("networkidle"); await page.goto(url, { waitUntil: "networkidle" }); };
const errors = [];
const responded = new Map();
const teardownRejections = [];
const accessibility = [];
const audit = async (state) => {
  const result = await new AxeBuilder({ page }).analyze();
  assert.deepEqual(result.violations.map(({ id, impact, nodes }) => ({ id, impact, targets: nodes.map((node) => node.target) })), [], `${state} accessibility violations`);
  accessibility.push({ state, violations: 0 });
};
page.on("response", (response) => { if (response.request().resourceType() !== "document") responded.set(response.url(), response.status()); });
page.on("pageerror", (error) => { const teardown = webkitTeardownRejection(error.message, { browserName, baseURL, responded }); if (teardown) teardownRejections.push(teardown); else errors.push(error.message); });
let identity = { subject: "operator", role: "ADMIN", can_bootstrap_approver: true, can_manage_providers: true };
let cases = [];
let grants = [];
let defaultUpdates = [];
let details = [];
let pathway = "EARNINGS_UPDATE";
let providerConflict = false;
let accepted = true;
let authorityFailure = false;
const credit = { id: "case-ui", issuer: "Northstar", name: "Enterprise UI", sector: "Services", source_count: 2, members: { analyst: "APPROVER" }, accepted_snapshot_id: "snapshot-ui", current_execution_id: "run-new" };
const catalog = { bindings: [{ id: "claude", provider_name: "anthropic", model: "configured-claude", available: true, status: "QUALIFIED" }, { id: "gpt", provider_name: "openai", model: "configured-gpt", available: true, status: "QUALIFIED" }, { id: "expired", provider_name: "openai", model: "expired-model", available: false, status: "UNAVAILABLE", unavailable_code: "QUALIFICATION_EXPIRED" }], default_binding_id: "claude", version: 4 };
const sources = ["source-first", "source-second"].map((id, sourceIndex) => ({ id, filename: `evidence-${sourceIndex + 1}.txt`, sha256: "a".repeat(64), withdrawn: false, blocks: Array.from({ length: 55 }, (_, index) => ({ block_id: `b${String(index + 1).padStart(5, "0")}`, locator: { line: index + 1 }, text: `Source ${sourceIndex + 1}, evidence line ${index + 1}` })) }));
const summary = ({ blocks, ...source }) => ({ ...source, block_count: blocks.length });
const snapshot = () => ({ id: "snapshot-ui", run_id: "run-accepted", accepted_at: "2026-09-06T12:00:00Z", digest: "a".repeat(64), source_set_version: 1, artifacts: [{ id: "artifact-ui", module_id: "CP-2", digest: "a".repeat(64) }] });
const workspace = () => ({ template: { template_id: `template-${pathway}`, template_version: "v1", pathway, title: `Report ${pathway}`, model_requirement: "OPTIONAL", allowed_appendices: [], optional_blocks: [], blocks: [{ block_id: "conclusion", slot_id: "conclusion", kind: "NARRATIVE", title: "Conclusion", required: true, order: 1 }] }, current: null, history: [], frozen_history: [], model_eligibility: { active_revision: null, application_build: null, fallback_acknowledgement_required: false, default_model_selection: null }, opinion: { head: null, current: false, reasons: [] }, pending_freezes: [] });
const json = (route, value, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(value) });
await page.route("**/api/**", async (route) => {
  const url = new URL(route.request().url());
  const path = url.pathname;
  if (path === "/api/me") return json(route, identity);
  if (path === "/api/cases") return json(route, cases);
  if (path === `/api/cases/${credit.id}`) return json(route, credit);
  if (path === "/api/admin/providers") return json(route, catalog);
  if (path === "/api/admin/provider-default") { const body = route.request().postDataJSON(); defaultUpdates.push(body); if (providerConflict) { providerConflict = false; catalog.version += 1; return json(route, { detail: { code: "PROVIDER_POLICY_CONFLICT" } }, 409); } catalog.default_binding_id = body.binding_id; catalog.version += 1; return json(route, catalog); }
  if (path.endsWith("/bootstrap-approver")) { grants.push(route.request().postDataJSON()); return json(route, { case_id: "case-outsider", subject: grants.at(-1).subject, role: "APPROVER", actor: "operator", at: "2026-09-06T12:00:00Z" }, 201); }
  if (path.endsWith("/source-summaries")) return json(route, { sources: [summary(sources[url.searchParams.has("cursor") ? 1 : 0])], next_cursor: url.searchParams.has("cursor") ? null : "page-2" });
  if (path.endsWith("/evidence-search")) { const delayed = url.searchParams.get("q") === "slow-first"; if (delayed) await new Promise((resolve) => setTimeout(resolve, 700)); const source = sources[delayed ? 0 : 1]; return json(route, { matches: [{ source_id: source.id, filename: source.filename, ...source.blocks[54] }], next_cursor: null }); }
  const source = sources.find((item) => path.endsWith(`/sources/${item.id}`));
  if (source) { details.push(source.id); return json(route, source); }
  if (path.endsWith("/snapshot")) return authorityFailure ? json(route, { detail: "authority unavailable" }, 503) : json(route, { accepted: accepted ? snapshot() : null, latest_accepted: accepted ? snapshot() : null, switch_required: false, diff: null });
  if (path.endsWith("/artifacts/artifact-ui")) return json(route, { id: "artifact-ui", module_id: "CP-2", digest: "a".repeat(64), markdown: "## Financials\n\n| Measure | Amount |\n| --- | ---: |\n| EBITDA \\| adjusted | <img src=x onerror=alert(1)> |", payload: { evidence_refs: [{ source_id: sources[0].id, block_id: "b00055" }] } });
  if (path.startsWith("/api/runs/")) return json(route, { id: path.endsWith("run-accepted") ? "run-accepted" : "run-new", case_id: credit.id, status: "succeeded", plan: { pathway: path.endsWith("run-accepted") ? pathway : "FULL_CREDIT", depth: "screen" }, nodes: [], provider_identity: { provider_name: "anthropic", model: "pinned-claude" } });
  if (path.includes("/deliverables/") && path.endsWith("/draft")) return json(route, workspace());
  if (path.endsWith("/audit-package")) return route.fulfill({ status: 200, headers: { "x-caos-sha256": "a".repeat(64) }, body: "fixture" });
  return json(route, { detail: "fixture endpoint unavailable" }, 404);
});
try {
  await navigate(`${baseURL}/admin/`);
  await page.getByLabel("Case ID", { exact: true }).fill("case-outsider");
  await page.getByLabel("Independent approver subject").fill("independent");
  await page.getByLabel("Audit rationale").fill("Approved committee assignment");
  await page.getByRole("button", { name: "Provision first approver" }).click();
  await page.getByRole("status").filter({ hasText: "independent provisioned as APPROVER" }).waitFor();
  assert.deepEqual(grants, [{ subject: "independent", rationale: "Approved committee assignment" }]);
  await page.getByLabel("Qualified provider and model").selectOption("gpt");
  await page.getByRole("button", { name: "Set default for new runs" }).click();
  await page.getByRole("status").filter({ hasText: "Existing runs keep their recorded provider" }).waitFor();
  assert.deepEqual(defaultUpdates, [{ binding_id: "gpt", expected_version: 4 }]);
  assert.equal(await page.locator('option[value="expired"]').isDisabled(), true);
  providerConflict = true;
  await page.getByLabel("Qualified provider and model").selectOption("claude");
  await page.getByRole("button", { name: "Set default for new runs" }).click();
  await page.getByRole("alert").filter({ hasText: /provider policy conflict/i }).waitFor();
  await page.waitForFunction(() => document.querySelector("#provider-binding")?.value === "gpt");
  assert.equal(await page.getByRole("button", { name: "Set default for new runs" }).isDisabled(), true);
  await audit("operator bootstrap and provider conflict, desktop");
  await page.setViewportSize({ width: 720, height: 1000 });
  await audit("operator bootstrap and provider conflict, 720px");
  await page.setViewportSize({ width: 1280, height: 720 });

  identity = { subject: "analyst", role: "ANALYST", can_bootstrap_approver: false, can_manage_providers: false }; cases = [credit];
  await navigate(`${baseURL}/admin/?case=${credit.id}`);
  await page.locator("form[data-member-form]").waitFor();
  assert.equal(await page.locator("form[data-bootstrap-form]").count(), 0);
  await navigate(`${baseURL}/sources/?case=${credit.id}`);
  await page.getByRole("button", { name: /evidence-1.txt/ }).waitFor();
  assert.equal(details.length, 0, "inventory eagerly fetched document blocks");
  await page.getByRole("button", { name: "More sources" }).click();
  await page.getByRole("button", { name: /evidence-2.txt/ }).waitFor();
  assert.equal(details.length, 0, "inventory pagination eagerly fetched document blocks");
  await page.getByRole("button", { name: /evidence-1.txt/ }).click();
  await page.locator(".source-document-block").first().waitFor();
  assert.equal(await page.locator(".source-document-block").count(), 40);
  await page.getByRole("button", { name: "Show more blocks" }).click();
  assert.equal(await page.locator(".source-document-block").count(), 55);
  await navigate(`${baseURL}/sources/?case=${credit.id}&source=source-first&block=b00055`);
  await page.waitForFunction(() => document.activeElement?.id === "block-source-first-b00055");
  await page.getByRole("button", { name: "Open evidence context" }).click();
  await page.waitForFunction(() => document.activeElement?.id === "drawer-block-b00055");
  await page.getByRole("link", { name: "Open full source" }).click();
  assert.equal(new URL(page.url()).searchParams.get("block"), "b00055");
  const slowQuery = page.waitForRequest((request) => request.url().includes("q=slow-first"));
  await page.getByLabel("Search documents").fill("slow-first");
  await slowQuery;
  await page.getByLabel("Search documents").fill("unopened-source-term");
  await page.getByRole("button", { name: /evidence-2.txt/ }).click();
  await page.waitForFunction(() => document.activeElement?.id === "block-source-second-b00055");
  await page.waitForTimeout(800);
  assert.equal(await page.locator(".source-register-row").filter({ hasText: "evidence-1.txt" }).count(), 0, "late search overwrote the current query");
  await navigate(`${baseURL}/sources/?case=${credit.id}&source=source-first&block=absent`);
  await page.getByRole("alert").filter({ hasText: "No other block was selected" }).waitFor();
  assert.equal(await page.locator(".source-document-block.is-selected").count(), 0);

  await navigate(`${baseURL}/analysis/?case=${credit.id}`);
  await page.getByRole("table").getByRole("cell", { name: "EBITDA | adjusted" }).waitFor();
  assert.equal(await page.locator(".analysis-copy img").count(), 0);
  await audit("safe artifact table");
  await page.getByRole("link", { name: "b00055", exact: true }).click();
  await page.waitForFunction(() => document.activeElement?.id === "block-source-first-b00055");
  for (pathway of ["FULL_CREDIT", "EARNINGS_UPDATE", "COVENANT_REFINANCING", "RELATIVE_VALUE", "DISTRESSED_RESTRUCTURING", "DEEP_RESEARCH"]) {
    await navigate(`${baseURL}/report/?case=${credit.id}`);
    await page.getByLabel("Pathway template").waitFor();
    assert.equal(await page.getByLabel("Pathway template").inputValue(), pathway, "Report followed unaccepted selected run instead of accepted run");
  }
  identity = { subject: "reader", role: "READER", can_bootstrap_approver: false, can_manage_providers: false };
  accepted = false;
  await navigate(`${baseURL}/analysis/?case=${credit.id}`);
  await page.getByText("Reader access: changing accepted authority is an analyst action.").waitFor();
  authorityFailure = true;
  await navigate(`${baseURL}/report/?case=${credit.id}`);
  await page.getByRole("alert").filter({ hasText: "Accepted case authority is unavailable" }).waitFor();
  authorityFailure = false;
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await page.getByLabel("Pathway template").waitFor();
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ browser: browserName, status: "PASS", evidence: "fixture contract/state coverage", checks: ["outsider operator", "provider CAS conflict", "global analyst with approver standing", "lazy summaries and pagination", "all blocks", "exact deep link/focus", "unopened evidence search", "late search cancellation", "invalid block", "safe tables", "six accepted report pathways", "Reader empty-state explanation", "parent authority retry"], accessibility, webkit_teardown_rejections: teardownRejections }));
} finally { await context.close(); await browser.close(); }
