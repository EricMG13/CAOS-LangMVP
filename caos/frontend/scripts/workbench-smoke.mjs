import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { chromium, request } from "playwright";

const baseURL = process.env.CAOS_URL || "http://127.0.0.1:8000";
const fixtureSuffix = randomUUID().slice(0, 8);
const primaryIssuer = `Northstar-${fixtureSuffix}`;
const raceIssuer = `Second-${fixtureSuffix}`;
const primaryLabel = `${primaryIssuer} / Workbench QA`;
const maxDomContentLoadedMs = Number(process.env.CAOS_MAX_DCL_MS || 250);
// Observed FCP on shared CI runners across 8 runs: 188, 200, 212, 224, 232,
// 252, 272, 332ms. Two of those (272 and 332) are the same commit, so ~60ms
// of the spread is runner noise alone. A 300ms budget sat inside that noise
// band and failed on load, not on regression; 400ms clears the worst
// observed sample while still catching anything that adds ~150ms.
const maxFirstContentfulPaintMs = Number(process.env.CAOS_MAX_FCP_MS || 400);
assert.ok(Number.isFinite(maxDomContentLoadedMs) && maxDomContentLoadedMs > 0, "CAOS_MAX_DCL_MS must be a positive finite number");
assert.ok(Number.isFinite(maxFirstContentfulPaintMs) && maxFirstContentfulPaintMs > 0, "CAOS_MAX_FCP_MS must be a positive finite number");
const identityHeaders = process.env.CAOS_EDGE_SECRET ? {
  "x-edge-authorization": process.env.CAOS_EDGE_SECRET,
  "x-forwarded-user": process.env.CAOS_TEST_USER || "analyst.qa@local.invalid",
  "x-forwarded-email": process.env.CAOS_TEST_USER || "analyst.qa@local.invalid",
  "x-forwarded-groups": process.env.CAOS_TEST_GROUPS || "caos-analyst",
} : {};
const api = await request.newContext({ baseURL, extraHTTPHeaders: identityHeaders });
const created = await api.post("/api/cases", {
  data: { name: "Workbench QA", issuer: primaryIssuer, sector: "Services" },
});
assert.equal(created.status(), 201);
const caseRecord = await created.json();
const raceCaseResponse = await api.post("/api/cases", {
  data: { name: "Authority Race", issuer: raceIssuer, sector: "Services" },
});
assert.equal(raceCaseResponse.status(), 201);
const raceCase = await raceCaseResponse.json();
const crossCaseUpload = await api.post(`/api/cases/${raceCase.id}/sources`, {
  multipart: {
    file: {
      name: "second-earnings.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Revenue 820\nEBITDA 140"),
    },
  },
});
assert.equal(crossCaseUpload.status(), 201);
const crossCaseRunResponse = await api.post(`/api/cases/${raceCase.id}/runs`, {
  data: { pathway: "EARNINGS_UPDATE", depth: "screen", focus_questions: [] },
});
assert.equal(crossCaseRunResponse.status(), 201);
const crossCaseRun = await crossCaseRunResponse.json();
let crossCaseRunState;
for (let attempt = 0; attempt < 60; attempt += 1) {
  const response = await api.get(`/api/runs/${crossCaseRun.id}`);
  crossCaseRunState = await response.json();
  if (crossCaseRunState.status === "succeeded") break;
  await new Promise((resolve) => setTimeout(resolve, 50));
}
assert.equal(crossCaseRunState?.status, "succeeded");
const failedCaseResponse = await api.post("/api/cases", {
  data: { name: "Authority Failure", issuer: "Unavailable", sector: "Services" },
});
assert.equal(failedCaseResponse.status(), 201);
const failedCase = await failedCaseResponse.json();
const idleCaseResponse = await api.post("/api/cases", {
  data: { name: "No Run Boundary", issuer: "Idle", sector: "Services" },
});
assert.equal(idleCaseResponse.status(), 201);
const idleCase = await idleCaseResponse.json();
const upload = await api.post(`/api/cases/${caseRecord.id}/sources`, {
  multipart: {
    file: {
      name: "earnings.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Revenue 1,160\nEBITDA 222"),
    },
  },
});
assert.equal(upload.status(), 201);
const source = await upload.json();
const started = await api.post(`/api/cases/${caseRecord.id}/runs`, {
  data: { pathway: "EARNINGS_UPDATE", depth: "screen", focus_questions: [] },
});
assert.equal(started.status(), 201);
const run = await started.json();
let runState;
for (let attempt = 0; attempt < 60; attempt += 1) {
  const response = await api.get(`/api/runs/${run.id}`);
  runState = await response.json();
  if (runState.status === "succeeded") break;
  await new Promise((resolve) => setTimeout(resolve, 50));
}
assert.equal(runState?.status, "succeeded");
const acceptedResponse = await api.post(`/api/runs/${run.id}/accept`);
assert.equal(acceptedResponse.status(), 200);
const accepted = await acceptedResponse.json();
const artifact = accepted.artifacts.find((item) => item.module_id === "CP-0");
assert.ok(artifact);
const researchPlanHash = `sha256:${"a".repeat(64)}`;
const researchPlanLongText = "The supplied evidence must resolve the complete refinancing perimeter without truncating this deliberately long committee-review sentence.";
const proposedResearchPlan = {
  methodology_build_id: "",
  brief_digest: "",
  source_set: { id: "", version: 7 },
  upstream_artifacts: [],
  scope: { type: "", key: "", source_mode: "" },
  workstreams: [
    {
      id: "",
      kind: "topical",
      question: researchPlanLongText,
      assigned_questions: ["Liquidity runway?", "Liquidity runway?", ""],
      perspective: "Buy-side credit analyst",
      hypothesis: "Refinancing is feasible if liquidity remains durable.",
      evidence_needs: ["Debt maturity schedule", "Debt maturity schedule", ""],
      source_classes: ["supplied_case_sources", "supplied_case_sources", ""],
      disconfirming_test: "Identify supplied evidence that contradicts the refinancing case.",
      completion_test: "Answer each assigned question with source locators or record the evidence gap.",
      effort_cap: "Within the fixed standard research budget.",
    },
    {
      id: "",
      kind: "",
      question: "",
      assigned_questions: [],
      perspective: "",
      hypothesis: "",
      evidence_needs: [],
      source_classes: [],
      disconfirming_test: "",
      completion_test: "",
      effort_cap: "",
    },
  ],
};
const pendingResearchRun = {
  id: `run_plan_${fixtureSuffix}`,
  case_id: caseRecord.id,
  status: "paused",
  plan: { pathway: "DEEP_RESEARCH", depth: "full", profile_id: "DEEP_RESEARCH_FULL", selection_id: "fixture-selection" },
  nodes: [
    { id: "node-cp0", module_id: "CP-0", status: "succeeded", artifact_id: artifact.id },
    { id: "node-cpdr", module_id: "CP-DR", status: "pending", artifact_id: null },
  ],
  error: { code: "PLAN_APPROVAL_REQUIRED", message: "Approve the exact deterministic research plan before agent execution." },
  research: { phase: "awaiting_approval", proposed_plan_hash: researchPlanHash, proposed_plan: proposedResearchPlan },
};

const browser = await chromium.launch({ headless: true });
const errors = [];
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, extraHTTPHeaders: identityHeaders });
  const page = await context.newPage();
  await page.addInitScript(() => {
    window.__caosUrlWrites = [];
    for (const method of ["pushState", "replaceState"]) {
      const original = history[method].bind(history);
      history[method] = (...args) => {
        const result = original(...args);
        window.__caosUrlWrites.push(location.search);
        return result;
      };
    }
  });
  let caseRequests = 0;
  let authorityRequests = 0;
  let expectedAuthorityFailureURL = "";
  let expectedAuthorityFailureSeen = false;
  let expectedNotFoundURL = "";
  let expectedPreviewValidationFailures = 0;
  let expectedSignOffConflicts = 0;
  let expectedReportConflicts = 0;
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    if (message.location().url === expectedNotFoundURL
      && message.text() === "Failed to load resource: the server responded with a status of 404 (Not Found)") {
      expectedNotFoundURL = "";
      return;
    }
    if (!expectedAuthorityFailureSeen
      && message.location().url === expectedAuthorityFailureURL
      && message.text() === "Failed to load resource: the server responded with a status of 503 (Service Unavailable)") {
      expectedAuthorityFailureSeen = true;
      return;
    }
    if (expectedPreviewValidationFailures > 0
      && message.location().url.endsWith(`/api/cases/${caseRecord.id}/models/previews`)
      && message.text() === "Failed to load resource: the server responded with a status of 422 (Unprocessable Entity)") {
      expectedPreviewValidationFailures -= 1;
      return;
    }
    if (expectedSignOffConflicts > 0
      && message.location().url.endsWith(`/api/cases/${caseRecord.id}/model-revisions/sign-off`)
      && message.text() === "Failed to load resource: the server responded with a status of 409 (Conflict)") {
      expectedSignOffConflicts -= 1;
      return;
    }
    if (expectedReportConflicts > 0
      && message.location().url.includes(`/api/cases/${caseRecord.id}/deliverables/`)
      && message.text() === "Failed to load resource: the server responded with a status of 409 (Conflict)") {
      expectedReportConflicts -= 1;
      return;
    }
    errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (requestValue) => {
    const pathname = new URL(requestValue.url()).pathname;
    if (pathname === "/api/cases") caseRequests += 1;
    if (/^\/api\/cases\/[^/]+\/(?:lens|snapshot)$/.test(pathname)) authorityRequests += 1;
  });

  let releaseAuthorityDetail;
  const authorityDetailBarrier = new Promise((resolve) => {
    releaseAuthorityDetail = resolve;
  });
  let markAuthorityDetailSeen;
  const authorityDetailSeen = new Promise((resolve) => {
    markAuthorityDetailSeen = resolve;
  });
  const heldAuthorityDetail = (url) => url.pathname === `/api/cases/${caseRecord.id}`;
  const holdAuthorityDetail = async (route) => {
    markAuthorityDetailSeen();
    await authorityDetailBarrier;
    await route.continue();
  };
  await page.route(heldAuthorityDetail, holdAuthorityDetail);
  await page.goto(`${baseURL}/command-center/?case=${caseRecord.id}`, { waitUntil: "domcontentloaded" });
  await authorityDetailSeen;
  const visibleAuthority = page.getByRole("region", { name: "Visible authority" });
  await visibleAuthority.getByText(/Visible snapshot:\s*Loading authority/).waitFor();
  await visibleAuthority.getByText(/Source set:\s*Loading authority/).waitFor();
  releaseAuthorityDetail();
  await visibleAuthority.getByText(/Source set:\s*v1/).waitFor();
  await page.getByRole("combobox", { name: "Select case" }).evaluate((element) => {
    element.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await page.evaluate(() => new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(resolve));
  }));
  await visibleAuthority.getByText(/Source set:\s*v1/).waitFor();
  const timing = await page.evaluate(() => {
    const navigation = performance.getEntriesByType("navigation")[0];
    const paint = performance.getEntriesByName("first-contentful-paint")[0];
    return {
      domContentLoaded: navigation?.domContentLoadedEventEnd ?? null,
      firstContentfulPaint: paint?.startTime ?? null,
    };
  });
  assert.ok(timing.domContentLoaded !== null && timing.domContentLoaded <= maxDomContentLoadedMs, `DCL ${timing.domContentLoaded}ms exceeds ${maxDomContentLoadedMs}ms`);
  assert.ok(timing.firstContentfulPaint !== null && timing.firstContentfulPaint <= maxFirstContentfulPaintMs, `FCP ${timing.firstContentfulPaint}ms exceeds ${maxFirstContentfulPaintMs}ms`);
  console.log(JSON.stringify({ timing, caseRequests }));
  await page.getByRole("link", { name: "Sources & evidence" }).click();
  await page.waitForURL((url) => url.pathname.replace(/\/$/, "") === "/sources" && url.searchParams.get("case") === caseRecord.id);
  await page.unroute(heldAuthorityDetail, holdAuthorityDetail);
  await page.goto(`${baseURL}/command-center/?case=${caseRecord.id}`, { waitUntil: "networkidle" });

  const failedAuthorityDetail = (url) => url.pathname === `/api/cases/${failedCase.id}`;
  const failAuthorityDetail = (route) => route.fulfill({
    status: 503,
    contentType: "application/json",
    body: JSON.stringify({ detail: "authority unavailable" }),
  });
  await page.route(failedAuthorityDetail, failAuthorityDetail);
  expectedAuthorityFailureURL = `${baseURL}/api/cases/${failedCase.id}`;
  expectedAuthorityFailureSeen = false;
  await page.getByRole("combobox", { name: "Select case" }).selectOption(failedCase.id);
  await visibleAuthority.getByText(/Visible snapshot:\s*Authority unavailable/).waitFor();
  await visibleAuthority.getByText(/Source set:\s*Authority unavailable/).waitFor();
  assert.equal(expectedAuthorityFailureSeen, true, "controlled authority 503 did not emit the expected console error");
  await page.unroute(failedAuthorityDetail, failAuthorityDetail);
  expectedAuthorityFailureURL = "";
  await page.getByRole("combobox", { name: "Select case" }).selectOption(caseRecord.id);
  await visibleAuthority.getByText(/Source set:\s*v1/).waitFor();

  const missingCaseId = `case_missing_${fixtureSuffix}`;
  await page.goto(`${baseURL}/run-console/?case=${missingCaseId}&run=${run.id}`, { waitUntil: "domcontentloaded" });
  await page.waitForFunction((invalidCaseId) => {
    const selected = document.querySelector('[aria-label="Select case"]');
    return selected instanceof HTMLSelectElement && selected.value && selected.value !== invalidCaseId;
  }, missingCaseId);
  await page.getByRole("status", { name: "Loading" }).waitFor({ state: "detached" });
  assert.equal(await page.getByRole("status", { name: "Loading" }).count(), 0, "invalid initial case/run authority left the workspace permanently loading");

  let releaseStaleRun;
  const staleRunBarrier = new Promise((resolve) => { releaseStaleRun = resolve; });
  const holdStaleRun = async (route) => {
    await staleRunBarrier;
    await route.continue().catch((caught) => {
      if (!(caught instanceof Error) || !caught.message.includes("Route is already handled")) throw caught;
    });
  };
  const staleRunPath = (url) => url.pathname === `/api/runs/${run.id}`;
  await page.route(staleRunPath, holdStaleRun);
  const staleRunRequest = page.waitForRequest((requestValue) => new URL(requestValue.url()).pathname === `/api/runs/${run.id}`);
  await page.goto(`${baseURL}/run-console/?case=${caseRecord.id}&run=${run.id}`, { waitUntil: "domcontentloaded" });
  await staleRunRequest;
  await page.getByRole("combobox", { name: "Select case" }).selectOption(idleCase.id);
  releaseStaleRun();
  await page.unroute(staleRunPath, holdStaleRun);
  await page.waitForFunction((expectedCaseId) => {
    const url = new URL(window.location.href);
    return url.searchParams.get("case") === expectedCaseId && !url.searchParams.has("run");
  }, idleCase.id);
  await page.getByText("No current execution. Select a purpose and depth to create an immutable plan.", { exact: true }).waitFor();
  // The URL settling correctly is not enough: a stale route replay can re-attach the
  // previous issuer's run and then self-correct, which is still a wrong read.
  const boundaryUrlWrites = await page.evaluate(([boundaryCaseId, staleRunId]) => {
    const writes = window.__caosUrlWrites || [];
    const switchedAt = writes.findIndex((search) => search.includes(`case=${boundaryCaseId}`));
    return { switchedAt, reattached: switchedAt === -1 ? [] : writes.slice(switchedAt + 1).filter((search) => search.includes(`run=${staleRunId}`)) };
  }, [idleCase.id, run.id]);
  assert.notEqual(boundaryUrlWrites.switchedAt, -1, "the case boundary was never written to the URL, so the stale-run check did not run");
  assert.deepEqual(boundaryUrlWrites.reattached, [], "a stale run was re-attached to the URL after the case boundary");
  assert.equal(await page.getByRole("status", { name: "Loading" }).count(), 0, "case switch left the run console permanently loading");
  assert.equal(await page.getByRole("button", { name: "Accept analytical snapshot" }).count(), 0, "stale run data survived the case boundary");
  await page.getByRole("combobox", { name: "Select case" }).selectOption(caseRecord.id);
  await page.getByRole("region", { name: "Visible authority" }).getByText(new RegExp(`Credit:\\s*${primaryIssuer}`)).waitFor();

  let crossCaseAcceptRequests = 0;
  const countCrossCaseAccept = (requestValue) => {
    if (requestValue.method() === "POST"
      && new URL(requestValue.url()).pathname === `/api/runs/${crossCaseRun.id}/accept`) crossCaseAcceptRequests += 1;
  };
  page.on("request", countCrossCaseAccept);
  await page.goto(`${baseURL}/run-console/?case=${caseRecord.id}&run=${crossCaseRun.id}`, { waitUntil: "networkidle" });
  await page.getByText("Requested run does not belong to the selected case.", { exact: true }).waitFor();
  assert.equal(await page.getByRole("button", { name: "Accept analytical snapshot" }).count(), 0, "cross-case run exposed an acceptance action");
  await page.waitForFunction((runId) => new URL(window.location.href).searchParams.get("run") !== runId, crossCaseRun.id);
  assert.equal(crossCaseAcceptRequests, 0, "cross-case run was accepted from the selected case");
  page.off("request", countCrossCaseAccept);

  const workflows = ["Portfolio", "Credit", "Sources", "Analysis", "Market", "Model", "Report"];
  for (const label of workflows) {
    await page.getByRole("navigation", { name: "Workflows" }).getByRole("link", { name: label, exact: true }).waitFor();
  }
  // Exactly one rail entry per page carries aria-current="page": the most specific
  // match — a tool link when one targets the destination, else the workflow link.
  for (const [route, navName, linkLabel] of [
    ["/cases/", "Workflows", "Portfolio"],
    ["/run-console/", "Analysis tools", "Run"],
    ["/report-studio/", "Workflows", "Report"],
  ]) {
    await page.goto(`${baseURL}${route}?case=${caseRecord.id}`, { waitUntil: "networkidle" });
    await page.getByRole("navigation", { name: navName })
      .getByRole("link", { name: linkLabel, exact: true })
      .evaluate((element) => {
        if (element.getAttribute("aria-current") !== "page") throw new Error("the most specific nav link is not current");
      });
    assert.equal(await page.locator('[aria-current="page"]').count(), 1, `${route} rendered more than one aria-current="page" entry`);
  }
  expectedNotFoundURL = `${baseURL}/missing-${fixtureSuffix}`;
  await page.goto(expectedNotFoundURL, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "Page not found" }).waitFor();
  assert.equal(await page.getByRole("heading", { name: "Monitored credits" }).count(), 0, "unknown route rendered the default Portfolio page");
  await page.goto(`${baseURL}/command-center/?case=${caseRecord.id}`, { waitUntil: "networkidle" });
  caseRequests = 0;
  authorityRequests = 0;

  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  const artifactPalette = page.getByRole("dialog", { name: "Command palette" });
  await artifactPalette.getByRole("combobox", { name: "Search cases, workflows or evidence IDs" }).fill(artifact.id);
  await artifactPalette.getByRole("option", { name: "Open artifact ID in this case" }).click();
  await page.waitForURL((url) => url.pathname.replace(/\/$/, "") === "/sources"
    && url.searchParams.get("case") === caseRecord.id
    && url.searchParams.get("artifact") === artifact.id);
  const evidenceFocus = page.getByRole("heading", { name: "Evidence focus" }).locator("../..");
  await evidenceFocus.getByTitle(artifact.digest, { exact: true }).waitFor();

  const deepDiveQuestion = "What changed in refinancing capacity?";
  await page.evaluate(({ caseId, question }) => {
    const query = new URLSearchParams({ case: caseId, q: question });
    window.history.pushState(null, "", `/deep-dive/?${query}`);
  }, { caseId: caseRecord.id, question: deepDiveQuestion });
  await page.waitForURL((url) => url.pathname === "/deep-dive/" && url.searchParams.get("q") === deepDiveQuestion);
  await page.getByText(deepDiveQuestion, { exact: true }).waitFor();

  const rail = page.locator(".analysis-evidence");
  await rail.getByText("Evidence rail", { exact: true }).waitFor();
  await rail.getByTitle(accepted.digest, { exact: true }).waitFor();
  assert.ok(await rail.locator(".analysis-evidence-card").count() > 0, "accepted analysis lists no cited sources");



  const commandQuestion = "Which evidence changes the downside case?";
  await page.evaluate(({ caseId, question }) => {
    const query = new URLSearchParams({ case: caseId, q: question });
    window.history.pushState(null, "", `/command-center/?${query}`);
  }, { caseId: caseRecord.id, question: commandQuestion });
  await page.waitForURL((url) => url.pathname === "/command-center/" && url.searchParams.get("q") === commandQuestion);
  await page.getByText(commandQuestion, { exact: true }).waitFor();

  for (const label of ["Credit", "Sources", "Analysis"]) {
    await page.getByRole("navigation", { name: "Workflows" }).getByRole("link", { name: label, exact: true }).click();
    await page.waitForLoadState("networkidle");
  }
  assert.equal(caseRequests, 0, "same-client query/workflow navigation repeated the case-list request");
  assert.ok(authorityRequests <= 12, `same-client navigation caused an authority refresh loop (${authorityRequests} requests)`);
  await page.getByRole("region", { name: "Visible authority" }).getByText(new RegExp(`Credit:\\s*${primaryIssuer}`)).waitFor();
  await page.getByRole("region", { name: "Visible authority" }).getByText(/Source set:\s*v1/).waitFor();

  const paletteTrigger = page.getByRole("button", { name: /Open command palette/ });
  await paletteTrigger.focus();
  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  const palette = page.getByRole("dialog", { name: "Command palette" });
  await palette.getByRole("combobox", { name: "Search cases, workflows or evidence IDs" }).fill(primaryIssuer);
  await palette.getByRole("option", { name: primaryLabel }).waitFor();
  await palette.getByRole("combobox", { name: "Search cases, workflows or evidence IDs" }).fill("src_deadbeef");
  await palette.getByRole("option", { name: /Open source ID in this case/ }).waitFor();
  await palette.getByRole("combobox", { name: "Search cases, workflows or evidence IDs" }).fill("secret issuer");
  await palette.getByText("No matches").waitFor();
  await page.keyboard.press("Escape");
  await assert.doesNotReject(() => paletteTrigger.evaluate((element) => {
    if (document.activeElement !== element) throw new Error("focus did not return to the palette trigger");
  }));

  await page.goto(`${baseURL}/run-console/?case=${caseRecord.id}`, { waitUntil: "networkidle" });
  const deepResearchOption = page.locator('#pathway option[value="DEEP_RESEARCH"]');
  assert.equal(await deepResearchOption.isDisabled(), true, "Deep Research was enabled before actor-specific availability resolved");
  await page.getByText("Deep Research is disabled for this deployment.", { exact: true }).waitFor();

  let caseDetailFixtureHits = 0;
  let startFixtureHits = 0;
  let runFixtureHits = 0;
  let approvalFixtureHits = 0;
  let approvedResearchPlan = false;
  let researchBriefPayload;
  let approvalPayload;
  const caseDetailFixturePath = (url) => url.pathname === `/api/cases/${caseRecord.id}`;
  const startResearchFixturePath = (url) => url.pathname === `/api/cases/${caseRecord.id}/runs`;
  const researchRunFixturePath = (url) => url.pathname === `/api/runs/${pendingResearchRun.id}`;
  const researchEventsFixturePath = (url) => url.pathname === `/api/runs/${pendingResearchRun.id}/events`;
  const approveResearchFixturePath = (url) => url.pathname === `/api/runs/${pendingResearchRun.id}/research-plan/approve`;
  const caseDetailFixtureResponse = await api.get(`/api/cases/${caseRecord.id}`);
  assert.equal(caseDetailFixtureResponse.status(), 200);
  const caseDetailFixture = await caseDetailFixtureResponse.json();
  await page.route(caseDetailFixturePath, async (route) => {
    caseDetailFixtureHits += 1;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...caseDetailFixture, deep_research_available: true, deep_research_unavailable_reason: null }) });
  });
  await page.route(startResearchFixturePath, async (route) => {
    startFixtureHits += 1;
    researchBriefPayload = route.request().postDataJSON();
    await route.fulfill({ status: 202, contentType: "application/json", body: JSON.stringify(pendingResearchRun) });
  });
  await page.route(researchRunFixturePath, async (route) => {
    runFixtureHits += 1;
    const fixture = approvedResearchPlan
      ? { ...pendingResearchRun, status: "queued", error: null, research: { ...pendingResearchRun.research, phase: "approved", approved_plan_hash: researchPlanHash } }
      : pendingResearchRun;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(fixture) });
  });
  await page.route(researchEventsFixturePath, (route) => route.fulfill({ status: 200, contentType: "text/event-stream", body: "retry: 60000\n\n" }));
  await page.route(approveResearchFixturePath, async (route) => {
    approvalFixtureHits += 1;
    approvalPayload = route.request().postDataJSON();
    approvedResearchPlan = true;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...pendingResearchRun, status: "queued", error: null }) });
  });
  await page.goto(`${baseURL}/run-console/?case=${caseRecord.id}&fixture=pending-plan`, { waitUntil: "networkidle" });
  await page.getByRole("combobox", { name: "Purpose" }).selectOption("DEEP_RESEARCH");
  const depth = page.getByRole("combobox", { name: "Depth" });
  assert.equal(await depth.inputValue(), "full", "Deep Research did not force full depth");
  assert.equal(await depth.locator('option[value="screen"]').isDisabled(), true, "Deep Research left Screen selectable");
  await page.getByRole("textbox", { name: "Research question" }).fill("Can Northstar refinance its 2028 maturities?");
  await page.getByRole("textbox", { name: "Decision context" }).fill("Underwrite a first-lien position.");
  await page.getByLabel("As-of date").fill("2026-08-23");
  await page.getByRole("textbox", { name: "Time horizon" }).fill("Through 2029");
  await page.getByRole("textbox", { name: "Must-answer lines" }).fill(Array.from({ length: 11 }, (_, index) => `Question ${index + 1}`).join("\n"));
  await page.getByRole("button", { name: "Compile and run" }).click();
  await page.getByRole("alert").getByText("Research brief lists allow at most 10 nonblank lines combined, and each line is limited to 200 characters.", { exact: true }).waitFor();
  assert.equal(startFixtureHits, 0, "an over-limit research brief reached the start route");
  await page.getByRole("textbox", { name: "Must-answer lines" }).fill(" Liquidity runway? \n\n Downside breach? ");
  await page.getByRole("textbox", { name: "Exclusion lines" }).fill(" Equity valuation \n");
  await page.getByRole("button", { name: "Compile and run" }).focus();
  await page.keyboard.press("Enter");
  await page.getByRole("heading", { name: "Proposed research plan" }).waitFor();
  // A governed action disables its own control while the request is in flight, and a
  // disabled element hands focus to <body> — which strands the keyboard and throws a
  // screen reader to the top of the document (WCAG 2.4.3). Workspace repairs that
  // once the action settles; these two assertions are what fail if the repair goes.
  await assert.doesNotReject(() => page.getByRole("button", { name: "Compile and run" }).evaluate((element) => {
    if (document.activeElement === document.body) throw new Error("compiling a route left focus on <body>");
    if (document.activeElement !== element) throw new Error(`focus settled on ${document.activeElement?.tagName} instead of the compile control`);
  }), "compile did not restore focus to its own control");
  // WCAG 4.1.3: the outcome of a governed write reaches assistive tech or it reaches
  // nobody — the DOM simply changing is not a status message.
  await page.getByRole("status").getByText("Route compiled. Execution started.", { exact: true }).waitFor();
  assert.deepEqual(researchBriefPayload, {
    pathway: "DEEP_RESEARCH",
    depth: "full",
    focus_questions: [],
    research_brief: {
      research_question: "Can Northstar refinance its 2028 maturities?",
      decision_context: "Underwrite a first-lien position.",
      as_of_date: "2026-08-23",
      time_horizon: "Through 2029",
      must_answer: ["Liquidity runway?", "Downside breach?"],
      exclusions: ["Equity valuation"],
    },
  });
  const researchPlan = page.locator(".research-plan");
  await researchPlan.getByText(researchPlanHash, { exact: true }).waitFor();
  await researchPlan.getByText(researchPlanLongText, { exact: true }).waitFor();
  for (const label of ["Methodology build", "Brief digest", "Source set", "Upstream artifacts", "Scope", "ID", "Kind", "Question", "Assigned questions", "Perspective", "Hypothesis", "Evidence needs", "Source classes", "Disconfirming test", "Completion test", "Effort cap"]) {
    assert.ok(await researchPlan.getByText(label, { exact: true }).count(), `pending plan omitted ${label}`);
  }
  const definitionValue = (container, label) => container.locator("dt").filter({ hasText: new RegExp(`^${label}$`) }).locator("xpath=following-sibling::dd[1]");
  const topLevelFacts = researchPlan.locator(":scope > .research-plan-facts");
  for (const label of ["Methodology build", "Brief digest", "Source set"]) {
    assert.equal(await definitionValue(topLevelFacts, label).getByText("None", { exact: true }).count(), 1, `${label} did not expose its empty scalar`);
  }
  assert.equal(await definitionValue(topLevelFacts, "Upstream artifacts").getByText("Empty", { exact: true }).count(), 1, "empty upstream artifacts were rendered as blank space");
  assert.equal(await definitionValue(topLevelFacts, "Scope").getByText("None", { exact: true }).count(), 3, "empty scope scalars were not explicit");
  const workstreams = researchPlan.locator(".research-workstreams > li");
  assert.equal(await workstreams.count(), 2, "pending plan did not render every repeated-ID workstream");
  for (const [label, value] of [["Assigned questions", "Liquidity runway?"], ["Evidence needs", "Debt maturity schedule"], ["Source classes", "supplied_case_sources"]]) {
    assert.equal(await definitionValue(workstreams.first(), label).getByText(value, { exact: true }).count(), 2, `${label} did not preserve repeated plan values`);
    assert.equal(await definitionValue(workstreams.first(), label).getByText("None", { exact: true }).count(), 1, `${label} rendered an empty list value as blank space`);
  }
  for (const label of ["ID", "Kind", "Question", "Perspective", "Hypothesis", "Disconfirming test", "Completion test", "Effort cap"]) {
    assert.equal(await definitionValue(workstreams.nth(1), label).getByText("None", { exact: true }).count(), 1, `${label} did not expose its empty scalar`);
  }
  for (const label of ["Assigned questions", "Evidence needs", "Source classes"]) {
    assert.equal(await definitionValue(workstreams.nth(1), label).getByText("Empty", { exact: true }).count(), 1, `${label} did not expose its empty list`);
  }
  assert.equal(errors.some((message) => /children with the same key|duplicate key/i.test(message)), false, "repeated exact-plan values emitted a React duplicate-key warning");
  await page.setViewportSize({ width: 720, height: 900 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth), false, "pending research plan causes page overflow at 200% desktop zoom width");
  assert.ok(await researchPlan.evaluate((element) => element.scrollWidth <= element.clientWidth), "pending research plan content overflows its panel");
  const approveResearchPlan = page.getByRole("button", { name: "Approve research plan" });
  await approveResearchPlan.focus();
  await page.keyboard.press("Enter");
  // The badge's accessible text now carries its subject: a polite live region that
  // announced a bare "queued" left a screen reader with a status and nothing to
  // attach it to. The visible chip is still the single word.
  await page.getByRole("status").getByText("Run status: queued", { exact: true }).waitFor();
  assert.equal(await page.locator(".panel-header .status").first().evaluate((element) => element.lastChild?.textContent), "queued", "the visible run status chip is no longer the bare status word");
  await page.getByRole("status").getByText("Research plan approved. Execution resumes against the approved plan hash.", { exact: true }).waitFor();
  assert.equal(await page.evaluate(() => document.activeElement === document.body), false, "approving the research plan left focus on <body>");
  assert.deepEqual(approvalPayload, { plan_hash: researchPlanHash });
  assert.ok(caseDetailFixtureHits > 0, "pending-plan case detail fixture was not exercised");
  assert.ok(startFixtureHits > 0, "pending-plan start fixture was not exercised");
  assert.ok(runFixtureHits > 0, "pending-plan run fixture was not exercised");
  assert.ok(approvalFixtureHits > 0, "pending-plan approval fixture was not exercised");
  await page.unroute(caseDetailFixturePath);
  await page.unroute(startResearchFixturePath);
  await page.unroute(researchRunFixturePath);
  await page.unroute(researchEventsFixturePath);
  await page.unroute(approveResearchFixturePath);
  await page.setViewportSize({ width: 1440, height: 1000 });

  await page.goto(`${baseURL}/run-console/?case=${caseRecord.id}&run=${run.id}`, { waitUntil: "networkidle" });
  let markStartRunIntercepted;
  const startRunIntercepted = new Promise((resolve) => { markStartRunIntercepted = resolve; });
  let releaseStartRun;
  const startRunBarrier = new Promise((resolve) => { releaseStartRun = resolve; });
  const startRunPath = (url) => url.pathname === `/api/cases/${caseRecord.id}/runs`;
  const holdStartRun = async (route) => {
    const heldResponse = await route.fetch();
    markStartRunIntercepted();
    await startRunBarrier;
    await route.fulfill({ response: heldResponse });
  };
  await page.route(startRunPath, holdStartRun);
  const nextRunResponsePromise = page.waitForResponse((response) =>
    response.request().method() === "POST"
      && new URL(response.url()).pathname === `/api/cases/${caseRecord.id}/runs`,
  );
  await page.getByRole("button", { name: "Compile and run" }).click();
  await startRunIntercepted;
  await page.getByRole("combobox", { name: "Select case" }).selectOption(raceCase.id);
  releaseStartRun();
  const nextRunResponse = await nextRunResponsePromise;
  assert.equal(nextRunResponse.status(), 201);
  const nextRun = await nextRunResponse.json();
  await nextRunResponse.finished();
  await page.unroute(startRunPath, holdStartRun);
  await page.waitForFunction(({ expectedCaseId, rejectedRunId }) => {
    const url = new URL(window.location.href);
    return url.searchParams.get("case") === expectedCaseId && url.searchParams.get("run") !== rejectedRunId;
  }, { expectedCaseId: raceCase.id, rejectedRunId: nextRun.id });
  await page.getByRole("region", { name: "Visible authority" }).getByText(new RegExp(`Credit:\\s*${raceIssuer}`)).waitFor();
  assert.equal(new URL(page.url()).searchParams.get("run"), crossCaseRun.id, "late Case A run creation replaced Case B execution authority");
  await page.goto(`${baseURL}/run-console/?case=${caseRecord.id}&run=${nextRun.id}`, { waitUntil: "networkidle" });
  await page.waitForFunction((expectedRunId) => Array.from(document.querySelectorAll('nav[aria-label="Analysis tools"] a'))
    .some((element) => element.textContent?.includes("Run")
      && new URL(element.href).searchParams.get("run") === expectedRunId), nextRun.id);

  let nextRunState;
  for (let attempt = 0; attempt < 60; attempt += 1) {
    const response = await api.get(`/api/runs/${nextRun.id}`);
    nextRunState = await response.json();
    if (nextRunState.status === "succeeded") break;
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  assert.equal(nextRunState?.status, "succeeded");

  // The acceptance ceremony owns one reserved region from queued through accepted.
  // Its box may change contents, but it must not make the execution panel jump as
  // progress crosses the irreversible-action boundary.
  let acceptanceRunPhase = "queued";
  const acceptanceSnapshot = { ...accepted, id: `snap_acceptance_${fixtureSuffix}`, run_id: nextRun.id };
  const acceptanceRunPath = (url) => url.pathname === `/api/runs/${nextRun.id}`;
  const acceptanceEventsPath = (url) => url.pathname === `/api/runs/${nextRun.id}/events`;
  const acceptanceAuthorityPath = (url) => url.pathname === `/api/cases/${caseRecord.id}/snapshot`;
  const acceptanceRunFixture = () => ({
    ...nextRunState,
    status: acceptanceRunPhase === "accepted" ? "succeeded" : acceptanceRunPhase,
    accepted_snapshot_id: acceptanceRunPhase === "accepted" ? acceptanceSnapshot.id : null,
    error: acceptanceRunPhase === "failed"
      ? { code: "GEOMETRY_FAILURE", message: "Controlled fixture failure." }
      : acceptanceRunPhase === "paused"
        ? { code: "SOURCE_SET_EMPTY", message: "Controlled fixture pause." }
        : null,
    nodes: nextRunState.nodes.map((node, index) => ({
      ...node,
      status: acceptanceRunPhase === "succeeded" || acceptanceRunPhase === "accepted" ? "succeeded"
        : acceptanceRunPhase === "failed" ? index === 0 ? "failed" : "pending"
        : acceptanceRunPhase === "running" ? index === 0 ? "succeeded" : index === 1 ? "running" : "pending"
          : "pending",
      artifact_id: acceptanceRunPhase === "succeeded" || acceptanceRunPhase === "accepted" ? node.artifact_id : index === 0 && acceptanceRunPhase === "running" ? node.artifact_id : null,
    })),
  });
  const acceptanceAuthorityFixture = () => {
    const visible = acceptanceRunPhase === "accepted" ? acceptanceSnapshot : accepted;
    return { accepted: visible, latest_accepted: visible, switch_required: false, diff: { changed: false } };
  };
  await page.route(acceptanceRunPath, (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(acceptanceRunFixture()) }));
  await page.route(acceptanceEventsPath, (route) => route.fulfill({ status: 200, contentType: "text/event-stream", body: "retry: 60000\n\n" }));
  await page.route(acceptanceAuthorityPath, (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(acceptanceAuthorityFixture()) }));
  const acceptanceBoxes = [];
  const acceptancePhases = ["queued", "running", "succeeded", "accepted", "failed", "paused"];
  for (const phase of acceptancePhases) {
    acceptanceRunPhase = phase;
    await page.reload({ waitUntil: "networkidle" });
    const region = page.locator("[data-run-acceptance]");
    const expectedState = phase === "accepted" ? "Latest accepted authority"
      : phase === "succeeded" ? "Ready for acceptance"
        : phase === "failed" || phase === "paused" ? "Acceptance blocked"
          : "Acceptance waiting";
    await region.getByText(expectedState, { exact: true }).waitFor();
    acceptanceBoxes.push(await region.boundingBox());
  }
  assert.ok(acceptanceBoxes.every(Boolean), "an execution state omitted the acceptance region");
  assert.deepEqual(
    acceptanceBoxes.map(({ x, y, width, height }) => [Math.round(x), Math.round(y), Math.round(width), Math.round(height)]),
    Array.from({ length: acceptancePhases.length }, () => {
      const { x, y, width, height } = acceptanceBoxes[0];
      return [Math.round(x), Math.round(y), Math.round(width), Math.round(height)];
    }),
    "acceptance-region geometry changed between waiting, ready, accepted, failed, and paused states",
  );
  await page.unroute(acceptanceRunPath);
  await page.unroute(acceptanceEventsPath);
  await page.unroute(acceptanceAuthorityPath);
  await page.reload({ waitUntil: "networkidle" });
  const acceptTrigger = page.getByRole("button", { name: "Accept analytical snapshot" });
  await acceptTrigger.waitFor();
  let markAcceptanceIntercepted;
  const acceptanceIntercepted = new Promise((resolve) => {
    markAcceptanceIntercepted = resolve;
  });
  let releaseAcceptance;
  const acceptanceBarrier = new Promise((resolve) => {
    releaseAcceptance = resolve;
  });
  await page.route(`**/api/runs/${nextRun.id}/accept`, async (route) => {
    const heldAcceptanceResponse = await route.fetch();
    markAcceptanceIntercepted();
    await acceptanceBarrier;
    await route.fulfill({ response: heldAcceptanceResponse });
  });
  const delayedAcceptResponse = page.waitForResponse((response) =>
    response.request().method() === "POST"
      && new URL(response.url()).pathname === `/api/runs/${nextRun.id}/accept`,
  );
  let switchedToRaceCase = false;
  const forbiddenAuthorityRequests = [];
  const trackAuthorityRequest = (requestValue) => {
    if (!switchedToRaceCase) return;
    const pathname = new URL(requestValue.url()).pathname;
    if (pathname === `/api/cases/${caseRecord.id}`
      || pathname === `/api/cases/${caseRecord.id}/snapshot`) {
      forbiddenAuthorityRequests.push(pathname);
    }
  };
  page.on("request", trackAuthorityRequest);
  // The acceptance ceremony is a styled digest-bound dialog, not window.confirm:
  // it must state the run being made authoritative, cancel cleanly on Escape with
  // focus restored, and only its own primary button performs the POST.
  await acceptTrigger.click();
  const acceptDialog = page.getByRole("dialog", { name: "Accept analytical snapshot" });
  await acceptDialog.getByText(nextRun.id, { exact: true }).waitFor();
  assert.equal(await page.evaluate(() => document.activeElement?.id), "accept-dialog-title", "accept dialog did not focus its heading");
  await page.keyboard.press("Escape");
  await acceptDialog.waitFor({ state: "hidden" });
  await assert.doesNotReject(() => acceptTrigger.evaluate((element) => {
    if (document.activeElement !== element) throw new Error("focus did not return to the accept trigger");
  }));
  await acceptTrigger.click();
  await acceptDialog.getByRole("button", { name: "Cancel" }).click();
  await acceptDialog.waitFor({ state: "hidden" });
  await assert.doesNotReject(() => acceptTrigger.evaluate((element) => {
    if (document.activeElement !== element) throw new Error("cancel did not return focus to the accept trigger");
  }));
  await acceptTrigger.click();
  await acceptDialog.getByText(nextRun.id, { exact: true }).waitFor();
  await acceptDialog.getByRole("button", { name: "Accept analytical snapshot" }).click();
  await acceptDialog.waitFor({ state: "hidden" });
  await acceptanceIntercepted;
  await page.getByRole("combobox", { name: "Select case" }).selectOption(raceCase.id);
  switchedToRaceCase = true;
  releaseAcceptance();
  const acceptanceResponse = await delayedAcceptResponse;
  assert.equal(acceptanceResponse.status(), 200);
  await acceptanceResponse.json();
  await acceptanceResponse.finished();
  await page.evaluate(() => new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(resolve));
  }));
  const authority = page.getByRole("region", { name: "Visible authority" });
  await authority.getByText(new RegExp(`Credit:\\s*${raceIssuer}`)).waitFor();
  await authority.getByText("No visible snapshot").waitFor();
  assert.equal(await authority.getByText(/Source set:\s*v1/).count(), 0);
  assert.deepEqual(
    forbiddenAuthorityRequests,
    [],
    "accepted Case A mutation refreshed authority after switching to Case B",
  );
  page.off("request", trackAuthorityRequest);

  // The aftermath: back on the accepted run, acceptance is no longer a live action —
  // the DAG panel renders the accepted state, keyed on run.accepted_snapshot_id
  // matching the case authority, and the accept button must not render.
  await page.goto(`${baseURL}/run-console/?case=${caseRecord.id}&run=${nextRun.id}`, { waitUntil: "networkidle" });
  await page.getByText("Latest accepted authority", { exact: true }).waitFor();
  assert.equal(await page.getByRole("button", { name: "Accept analytical snapshot" }).count(), 0, "an accepted run still offers a live acceptance action");

  // Module progress lives in the DAG tiles, which are not a live region: without this
  // sentence a screen reader learns only that the DOM changed (WCAG 4.1.3).
  await page.getByRole("status").getByText(/^\d+ of \d+ modules? complete\./).waitFor();
  // WCAG 2.4.1: <main> needs tabindex="-1" or the skip link moves the scroll position
  // and the browser's focus starting point while leaving activeElement on <body>.
  await page.evaluate(() => {
    document.body.tabIndex = -1;
    document.body.focus();
    document.body.removeAttribute("tabindex");
  });
  await page.keyboard.press("Tab");
  await assert.doesNotReject(() => page.getByRole("link", { name: "Skip to content" }).evaluate((element) => {
    if (document.activeElement !== element) throw new Error("the skip link is not the first tab stop");
  }));
  await page.keyboard.press("Enter");
  assert.equal(await page.evaluate(() => document.activeElement?.id), "main-content", "the skip link did not move focus into the main landmark");

  const modelBuildId = `model_${fixtureSuffix}`;
  let inventoryModelBuildId = modelBuildId;
  const modelRequirements = ["CP-1", "CP-1A", "CP-1B", "CP-2", "CP-2A", "CP-2B"].map((module_id) => ({ module_id, status: "READY", digest: "a".repeat(64) }));
  let modelState = "READY_TO_BUILD";
  let modelExportState = "NOT_REQUESTED";
  let modelGets = 0;
  let modelPosts = 0;
  let exportPosts = 0;
  let worksheetGets = 0;
  let modelGetDelay = 0;
  let modelGetsInFlight = 0;
  let maxModelGetsInFlight = 0;
  let modelLoadFails = false;
  const modelBuild = () => ({ id: inventoryModelBuildId, case_id: caseRecord.id, accepted_run_id: run.id, accepted_snapshot_id: accepted.id, source_set_id: "set-model", input_fingerprint: "b".repeat(64), status: modelState, queued_at: "2026-08-24T12:00:00Z", started_at: null, completed_at: modelState === "READY" ? "2026-08-24T12:01:00Z" : null, error: modelState === "FAILED" ? { code: "MODEL_CALCULATION_FAILED", detail: "The model calculation did not complete." } : null, export: { status: modelExportState, error: modelExportState === "FAILED" ? { code: "MODEL_EXPORT_FAILED", detail: "The XLSX export did not complete." } : null }, qa: modelState === "READY" ? { status: "PASS", semantic_check_count: 20, formula_count: 4, worksheet_cell_count: 12 } : undefined, payload_digest: modelState === "READY" ? "c".repeat(64) : undefined });
  const modelInventory = () => ({
    readiness: {
      status: modelState,
      module_id: "CP-MODEL",
      accepted_snapshot: modelState === "NOT_READY" ? null : { id: accepted.id, run_id: run.id, digest: accepted.digest },
      source_set: modelState === "NOT_READY" ? null : { id: "set-model", version: 1, digest: "d".repeat(64) },
      requirements: modelState === "NOT_READY" ? modelRequirements.map(({ module_id }) => ({ module_id, status: "MISSING" })) : modelRequirements,
      blockers: modelState === "NOT_READY" ? [{ code: "ACCEPTED_FULL_CREDIT_REQUIRED", detail: "Accept a completed Full Credit run before building a model." }] : [],
      build: ["QUEUED", "BUILDING", "READY", "FAILED"].includes(modelState) ? modelBuild() : null,
    },
    builds: ["QUEUED", "BUILDING", "READY", "FAILED"].includes(modelState) ? [modelBuild(), { ...modelBuild(), id: `model_history_${fixtureSuffix}`, status: "FAILED", input_fingerprint: "e".repeat(64) }] : [],
  });
  const modelWorksheet = {
    build_id: modelBuildId,
    input_fingerprint: "b".repeat(64),
    payload_digest: "c".repeat(64),
    qa: { status: "PASS", semantic_check_count: 20, formula_count: 4, worksheet_cell_count: 12 },
    payload: {
      schema_version: "caos.model.worksheet.v1",
      identity: { issuer_id: "northstar", issuer_name: primaryIssuer, analysis_date: "2026-08-24" },
      tabs: ["Credit Snapshot", "Model", "KPIs"].map((name) => ({
        id: name.toUpperCase().replaceAll(" ", "_"), title: name, max_row: 2, max_column: 2, freeze_panes: "B2", merged_cells: [],
        columns: [{ column: 1, letter: "A", width: 22, hidden: false }, { column: 2, letter: "B", width: 14, hidden: false }],
        cells: [
          { address: "A1", row: 1, column: 1, value: name, value_type: "text", formula: null, semantic_id: null, owner: null, write_class: null, period_id: null, source_refs: null, number_format: "General", style: { bold: true, italic: false, fill: "0A2E63", align: "left", wrap: false } },
          { address: "A2", row: 2, column: 1, value: 1160, value_type: "number", formula: null, semantic_id: "account::revenue::FY2024", owner: "CP-1", write_class: "SOURCE", period_id: "FY2024", source_refs: "SRC-1 | page 42 | 2026-08-24", number_format: "#,##0.0", style: { bold: false, italic: false, fill: "FFF4CC", align: "right", wrap: false } },
          { address: "B2", row: 2, column: 2, value: 4.2, value_type: "formula", formula: "=A2/276", semantic_id: "metric::leverage::FY2024", owner: "CP-MODEL", write_class: "FORMULA", period_id: "FY2024", source_refs: null, number_format: "0.0x", style: { bold: false, italic: false, fill: null, align: "right", wrap: false } },
        ],
      })),
    },
  };
  const registryVersion = "cp-model-assumptions.v1";
  const registryDigest = "f".repeat(64);
  const assumptionDefinitionSpecs = [
    ["operating.revenue_growth.division_1", "Division 1 revenue growth", "OPERATING", "NOT_APPLICABLE", null],
    ["operating.revenue_growth.division_2", "Division 2 revenue growth", "OPERATING", "NOT_APPLICABLE", null],
    ["operating.revenue_growth.division_3", "Division 3 revenue growth", "OPERATING", "NOT_APPLICABLE", null],
    ["operating.consolidated_revenue_growth", "Revenue growth", "OPERATING", "READY", null],
    ["operating.adjusted_ebitda_margin", "Adjusted EBITDA margin", "OPERATING", "READY", null],
    ["operating.identified_addbacks", "Identified add-backs", "OPERATING", "READY", null],
    ["cash_flow.capex_pct_revenue", "Capital expenditure as percent of revenue", "CASH FLOW", "READY", null],
    ["cash_flow.working_capital_pct_revenue", "Working capital change as percent of revenue", "CASH FLOW", "READY", null],
    ["cash_flow.cash_tax_pct_revenue", "Cash taxes as percent of revenue", "CASH FLOW", "READY", null],
    ["cash_flow.lease_cash_pct_revenue", "Lease cash flow as percent of revenue", "CASH FLOW", "READY", null],
    ["rates.base_rate", "Base interest rate", "RATES", "READY", null],
    ["rates.debt_spread", "Debt spread or coupon", "RATES", "READY", null],
    ["capital.contractual_amortization", "Contractual debt amortization", "CAPITAL", "READY", null],
    ["capital.debt_issuance", "Debt issuance", "CAPITAL", "READY", null],
    ["capital.debt_repayment", "Discretionary debt repayment", "CAPITAL", "READY", null],
    ["capital.refinancing_proceeds", "Refinancing proceeds", "CAPITAL", "READY", null],
    ["capital.acquisitions_disposals", "Acquisitions and disposals", "CAPITAL", "READY", null],
    ["capital.net_equity_issue_repay", "Net equity issuance or repurchase", "CAPITAL", "READY", null],
    ["capital.dividends_paid", "Dividends paid", "CAPITAL", "READY", null],
    ["capital.other_investing_financing", "Other investing and financing", "CAPITAL", "READY", null],
    ["liquidity.minimum_operating_cash", "Minimum operating cash", "LIQUIDITY", "UNAVAILABLE", "MINIMUM_CASH_DEFINITION_UNAVAILABLE"],
    ["liquidity.undrawn_revolver", "Accessible undrawn revolver", "LIQUIDITY", "UNAVAILABLE", "ACCESSIBLE_LIQUIDITY_DEFINITION_UNAVAILABLE"],
    ["covenant.max_total_leverage", "Maximum total leverage covenant", "COVENANT", "UNAVAILABLE", "COVENANT_DEFINITION_UNAVAILABLE"],
  ];
  const assumptionDefinitions = assumptionDefinitionSpecs.map(([assumptionId, label, family, status, gapCode]) => ({
    assumption_id: assumptionId,
    label,
    family,
    description: `Canonical ${String(label).toLowerCase()} assumption.`,
    driver_id: assumptionId.split(".").at(-1),
    slot_id: assumptionId.includes("division_") ? assumptionId.split(".").at(-1).toUpperCase() : null,
    value_type: "DECIMAL",
    unit: assumptionId.includes("rate") || assumptionId.includes("growth") || assumptionId.includes("pct_") || assumptionId.includes("margin") ? "PERCENT_DECIMAL" : "CURRENCY_MM",
    cases: ["BASE", "DOWNSIDE"],
    periods: ["FY2025", "FY2026", "FY2027"],
    default: { status, value: status === "READY" ? 0 : null },
    lineage: { authority_module: "CP-2G" },
    sensitivity_default: { range: "0.04", step: "0.01" },
    hard_min: assumptionId === "operating.consolidated_revenue_growth" ? "-0.75" : "-100000",
    hard_max: assumptionId === "operating.consolidated_revenue_growth" ? "2" : "100000",
    required: !["UNAVAILABLE", "NOT_APPLICABLE"].includes(status),
    allowed_statuses: status === "UNAVAILABLE" ? ["READY", "UNAVAILABLE"] : status === "NOT_APPLICABLE" ? ["READY", "NOT_APPLICABLE"] : ["READY"],
    degradation: gapCode ? { behavior: "NULL_WITH_NAMED_GAP", gap_code: gapCode } : null,
    affected_outputs: ["revenue", "total_leverage"],
  }));
  const assumptionDefinition = assumptionDefinitions.find((item) => item.assumption_id === "operating.consolidated_revenue_growth");
  assert.equal(assumptionDefinitions.length, 23, "Model Builder fixture drifted from the methodology-owned full registry");
  const assumptionDefaults = assumptionDefinitions.flatMap((definition) => ["BASE", "DOWNSIDE"].flatMap((caseName) => ["FY2025", "FY2026", "FY2027"].map((periodId) => {
    const spec = assumptionDefinitionSpecs.find(([assumptionId]) => assumptionId === definition.assumption_id);
    const status = spec[3];
    const gapCode = spec[4];
    const value = status === "READY" ? definition.assumption_id === assumptionDefinition.assumption_id ? caseName === "BASE" ? "0.03" : "-0.02" : "0" : null;
    return { assumption_id: definition.assumption_id, case: caseName, period_id: periodId, unit: definition.unit, status, value, gap_code: gapCode, default_value: value, default_status: status, default_gap_code: gapCode, source_context: status === "READY" ? { authority_module: "CP-2G", gap_code: "", provenance: [{ source_id: "SRC-1", source_locator: "page 42", as_of: "2026-08-24" }] } : { authority_module: "CP-2G", gap_code: gapCode || "NOT_APPLICABLE", provenance: [] }, source_context_digest: "9".repeat(64) };
  })));
  const assumptionRegistry = () => ({ version: registryVersion, digest: registryDigest, definitions: assumptionDefinitions, build_id: inventoryModelBuildId, accepted_snapshot_id: accepted.id, input_fingerprint: "b".repeat(64), defaults: assumptionDefaults });
  const signedAssumptions = assumptionDefaults.map((row) => row.assumption_id === assumptionDefinition.assumption_id && row.case === "BASE" && row.period_id === "FY2025" ? { ...row, value: "0.02" } : row);
  let modelRevisions = [{ id: `revision_signed_${fixtureSuffix}`, case_id: caseRecord.id, build_id: modelBuildId, accepted_snapshot_id: accepted.id, build_input_fingerprint: "b".repeat(64), build_payload_digest: "c".repeat(64), registry_version: registryVersion, registry_digest: registryDigest, calculation_contract_version: "cp-model-calculation.v1", effective_assumptions: signedAssumptions, assumptions_digest: "a".repeat(64), outputs: { total_leverage: 4.2, revenue: { FY2025: 1180 } }, outputs_digest: "7".repeat(64), worksheet: modelWorksheet.payload, preview_digest: "8".repeat(64), parent_revision_id: null, note: "Previously signed analyst assumptions.", revision_number: 1, created_by: "approver@example.com", created_at: "2026-08-24T12:00:00Z", export: { status: "READY", error: null, filename: "northstar-r1.xlsx", sha256: "5".repeat(64), size: 4096 }, state: "ACTIVE" }];
  let previewPosts = 0;
  let previewFails = false;
  let signOffPosts = 0;
  let signOffConflicts = false;
  let modelRole = "ANALYST";
  const modelPath = (url) => url.pathname === `/api/cases/${caseRecord.id}/model`;
  const modelsPath = (url) => url.pathname === `/api/cases/${caseRecord.id}/models`;
  const worksheetPath = (url) => url.pathname === `/api/cases/${caseRecord.id}/models/${modelBuildId}/worksheet`;
  const exportPath = (url) => url.pathname === `/api/cases/${caseRecord.id}/models/${modelBuildId}/export`;
  const registryPath = (url) => url.pathname === `/api/cases/${caseRecord.id}/models/assumption-registry`;
  const revisionsPath = (url) => url.pathname === `/api/cases/${caseRecord.id}/model-revisions`;
  const revisionExportStatusesPath = (url) => url.pathname === `/api/cases/${caseRecord.id}/model-revisions/export-statuses`;
  const previewPath = (url) => url.pathname === `/api/cases/${caseRecord.id}/models/previews`;
  const signOffPath = (url) => url.pathname === `/api/cases/${caseRecord.id}/model-revisions/sign-off`;
  const rebasePath = (url) => url.pathname === `/api/cases/${caseRecord.id}/model-revisions/rebase-preview`;
  const tornadoPath = (url) => url.pathname === `/api/cases/${caseRecord.id}/models/tornado`;
  const identityPath = (url) => url.pathname === "/api/me";
  await page.route(identityPath, (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ role: modelRole }) }));
  await page.route(modelPath, (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(modelInventory().readiness) }));
  await page.route(modelsPath, async (route) => {
    if (route.request().method() === "POST") {
      modelPosts += 1; modelState = "QUEUED";
      await route.fulfill({ status: 202, contentType: "application/json", body: JSON.stringify({ build: modelBuild(), created: true }) });
      return;
    }
    modelGets += 1;
    modelGetsInFlight += 1;
    maxModelGetsInFlight = Math.max(maxModelGetsInFlight, modelGetsInFlight);
    if (modelGetDelay) await new Promise((resolve) => setTimeout(resolve, modelGetDelay));
    modelGetsInFlight -= 1;
    if (modelLoadFails) {
      await route.fulfill({ status: 200, contentType: "application/json", body: "not-json" });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ builds: modelInventory().builds }) });
  });
  await page.route(worksheetPath, (route) => {
    worksheetGets += 1;
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(modelWorksheet) });
  });
  await page.route(exportPath, async (route) => {
    exportPosts += 1; modelExportState = "QUEUED";
    await route.fulfill({ status: 202, contentType: "application/json", body: JSON.stringify({ build: modelBuild(), queued: true }) });
  });
  await page.route(registryPath, (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(assumptionRegistry()) }));
  await page.route(revisionsPath, (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ revisions: modelRevisions }) }));
  await page.route(revisionExportStatusesPath, (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ exports: modelRevisions.map((revision) => ({ revision_id: revision.id, export: revision.export })) }) }));
  await page.route(previewPath, async (route) => {
    previewPosts += 1;
    const requestBody = route.request().postDataJSON();
    if (previewFails) {
      expectedPreviewValidationFailures += 1;
      await route.fulfill({ status: 422, contentType: "application/json", body: JSON.stringify({ detail: "MODEL_PREVIEW_CALCULATION_FAILED" }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ case_id: caseRecord.id, build_id: modelBuildId, accepted_snapshot_id: accepted.id, build_input_fingerprint: "b".repeat(64), build_payload_digest: "c".repeat(64), registry_version: registryVersion, registry_digest: registryDigest, calculation_contract_version: "cp-model-calculation.v1", parent_revision_id: requestBody.parent_revision_id, draft_generation: requestBody.draft_generation, effective_assumptions: requestBody.assumptions, assumptions_digest: "1".repeat(64), outputs: { total_leverage: 4.1, revenue: { FY2025: 1194.8 } }, outputs_digest: "2".repeat(64), worksheet: modelWorksheet.payload, deltas: { total_leverage: -0.1 }, preview_digest: "3".repeat(64) }) });
  });
  await page.route(signOffPath, async (route) => {
    signOffPosts += 1;
    const requestBody = route.request().postDataJSON();
    if (signOffConflicts) {
      expectedSignOffConflicts += 1;
      const intervening = { id: `revision_intervening_${fixtureSuffix}`, case_id: caseRecord.id, build_id: modelBuildId, accepted_snapshot_id: accepted.id, build_input_fingerprint: "b".repeat(64), build_payload_digest: "c".repeat(64), registry_version: registryVersion, registry_digest: registryDigest, calculation_contract_version: "cp-model-calculation.v1", effective_assumptions: assumptionDefaults, assumptions_digest: "6".repeat(64), outputs: { total_leverage: 4.2, revenue: { FY2025: 1180 } }, outputs_digest: "7".repeat(64), worksheet: modelWorksheet.payload, preview_digest: "8".repeat(64), parent_revision_id: null, note: "Intervening committee update.", revision_number: 1, created_by: "approver@example.com", created_at: "2026-08-24T13:01:00Z", export: { status: "READY", error: null, filename: "northstar-r1.xlsx", sha256: "5".repeat(64), size: 4096 }, state: "ACTIVE" };
      modelRevisions = [intervening];
      signOffConflicts = false;
      await route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ detail: { current: intervening, current_build: modelBuild() } }) });
      return;
    }
    const revision = { id: `revision_${fixtureSuffix}`, case_id: caseRecord.id, build_id: modelBuildId, accepted_snapshot_id: accepted.id, build_input_fingerprint: "b".repeat(64), build_payload_digest: "c".repeat(64), registry_version: registryVersion, registry_digest: registryDigest, calculation_contract_version: "cp-model-calculation.v1", effective_assumptions: requestBody.assumptions, assumptions_digest: "1".repeat(64), outputs: { total_leverage: 4.1, revenue: { FY2025: 1194.8 } }, outputs_digest: "2".repeat(64), worksheet: modelWorksheet.payload, preview_digest: requestBody.preview_digest, parent_revision_id: requestBody.parent_revision_id, note: requestBody.note, revision_number: modelRevisions.length + 1, created_by: "analyst@example.com", created_at: "2026-08-24T13:02:00Z", export: { status: "READY", error: null, filename: "northstar-r2.xlsx", sha256: "5".repeat(64), size: 4096 }, state: "ACTIVE" };
    modelRevisions = [revision, ...modelRevisions.map((item) => ({ ...item, state: "SUPERSEDED" }))];
    await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(revision) });
  });
  await page.route(rebasePath, async (route) => {
    const requestBody = route.request().postDataJSON();
    const activeRevision = modelRevisions.find((item) => item.state === "ACTIVE");
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ source_revision_id: requestBody.revision_id, source_build_id: modelBuildId, build_id: modelBuildId, draft_generation: requestBody.draft_generation, compatible: [{ assumption_id: assumptionDefinition.assumption_id }], changed: [{ assumption_id: assumptionDefinition.assumption_id, reason: "SOURCE_CONTEXT_CHANGED" }], invalidated: [], candidate_assumptions: activeRevision?.effective_assumptions || assumptionDefaults, preview: null }) });
  });
  await page.route(tornadoPath, async (route) => {
    const requestBody = route.request().postDataJSON();
    assert.equal(requestBody.assumptions.length, assumptionDefaults.length, "tornado did not receive the complete working forecast");
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ build_id: modelBuildId, draft_generation: requestBody.draft_generation, case: requestBody.case, output_period_id: requestBody.output_period_id, output_id: requestBody.output_id, intensity: requestBody.intensity, baseline: "4.2", bars: [
      { assumption_id: "operating.adjusted_ebitda_margin", label: "EBITDA margin", unit: "PERCENT_DECIMAL", swing: "0.015", low: "3.8", high: "4.8" },
      { assumption_id: "operating.consolidated_revenue_growth", label: "Revenue growth", unit: "PERCENT_DECIMAL", swing: "0.025", low: "3.9", high: "4.6" },
      { assumption_id: "rates.base_rate", label: "Interest rate", unit: "PERCENT_DECIMAL", swing: "0.01", low: "4.0", high: "4.4" },
      { assumption_id: "cash_flow.capex_pct_revenue", label: "Capex % revenue", unit: "PERCENT_DECIMAL", swing: "0.01", low: "4.1", high: "4.3" },
    ] }) });
  });
  await page.goto(`${baseURL}/model-builder/?case=${caseRecord.id}`, { waitUntil: "networkidle" });
  const buildButton = page.getByRole("button", { name: "Build model" });
  await buildButton.click();
  await page.getByText("Model build queued.", { exact: true }).waitFor();
  await buildButton.click({ force: true }).catch(() => {});
  assert.equal(modelPosts, 1, "disabled model control submitted a duplicate build");
  modelState = "BUILDING";
  modelGetDelay = 1700;
  await page.getByText("Calculating application model", { exact: true }).waitFor({ timeout: 4000 });
  modelGetDelay = 0;
  assert.equal(maxModelGetsInFlight, 1, "Model Builder overlapped slow poll requests");
  modelState = "READY";
  await page.getByText("Application model · R1", { exact: true }).waitFor({ timeout: 4000 });
  await page.getByRole("tab", { name: "Credit Snapshot" }).waitFor({ timeout: 4000 });
  const historicalWorksheetCell = page.locator('td[data-address="A2"][data-write-class="SOURCE"]');
  const calculatedWorksheetCell = page.locator('td[data-address="B2"][data-write-class="FORMULA"]');
  const historicalWorksheetValue = await historicalWorksheetCell.innerText();
  const calculatedWorksheetValue = await calculatedWorksheetCell.innerText();
  assert.equal(await historicalWorksheetCell.locator("input, textarea, [contenteditable='true']").count(), 0, "historical source cell exposed an edit control");
  assert.equal(await calculatedWorksheetCell.locator("input, textarea, [contenteditable='true']").count(), 0, "calculated historical cell exposed an edit control");
  const terminalGets = modelGets;
  await page.waitForTimeout(1800);
  assert.equal(modelGets, terminalGets, "Model Builder kept polling after READY");
  assert.equal(worksheetGets, 1, "the single model loaded more than one application worksheet");
  assert.equal(exportPosts, 0, "the core model journey unexpectedly queued an operational export");
  const firstGridCell = page.locator('td[data-address="A1"]');
  await firstGridCell.focus();
  await page.keyboard.press("ArrowDown");
  assert.equal(await page.evaluate(() => document.activeElement?.getAttribute("data-address")), "A2", "worksheet ArrowDown did not move one row");
  await page.keyboard.press("ArrowRight");
  assert.equal(await page.evaluate(() => document.activeElement?.getAttribute("data-address")), "B2", "worksheet ArrowRight did not move one column");
  await page.keyboard.press("Enter");
  await page.locator("#model-cell-lineage").getByText("=A2/276", { exact: true }).waitFor();
  const sourceCell = page.getByRole("button", { name: /Show lineage for account::revenue/ });
  await sourceCell.click();
  await page.locator("#model-cell-lineage").getByText(/SRC-1 \| page 42/).waitFor();
  await page.locator("#model-cell-lineage").getByText("FY2024", { exact: true }).waitFor();
  const firstTab = page.getByRole("tab", { name: "Credit Snapshot" });
  await firstTab.focus();
  await page.keyboard.press("ArrowRight");
  assert.equal(await page.getByRole("tablist", { name: "Model worksheets" }).getByRole("tab", { name: "Model" }).getAttribute("aria-selected"), "true");
  const formulaCell = page.getByRole("button", { name: /Show lineage for metric::leverage/ });
  await formulaCell.focus();
  await page.keyboard.press("Enter");
  await page.locator("#model-cell-lineage").getByText("=A2/276", { exact: true }).waitFor();
  await page.getByText("Model versions", { exact: true }).click();
  assert.equal(await page.getByRole("region", { name: "Model versions" }).locator("tbody tr").count(), 2, "application and signed versions were not rendered as one model history");
  assert.equal(await page.locator("fieldset").count(), 23, "Model Builder did not render the full methodology-owned registry");
  const firstAssumption = page.getByLabel("Revenue growth, FY2025, BASE");
  await firstAssumption.fill("0.04");
  await firstAssumption.press("Enter");
  await page.getByText(/Forecast recalculated\. Historical accounts remain locked/).waitFor();
  assert.equal(previewPosts, 1, "forecast edit did not automatically calculate one preview");
  await page.getByRole("group", { name: /Net leverage tornado for BASE/ }).waitFor();
  const secondAssumption = page.getByLabel("Revenue growth, FY2026, BASE");
  await firstAssumption.fill("3");
  await firstAssumption.press("Enter");
  assert.equal(await firstAssumption.inputValue(), "0.04", "rejected out-of-bounds edit did not revert the controlled input");
  await page.getByText(/Enter a finite value from -0.75 to 2/).waitFor();
  const broadcast = page.getByLabel("Revenue growth, all forecast years, BASE");
  await broadcast.fill("0.04");
  await broadcast.press("Enter");
  assert.equal(await secondAssumption.inputValue(), "0.04", "all-year broadcast did not update every registry year");
  assert.equal(await page.getByLabel("Minimum operating cash, all forecast years, BASE").isDisabled(), true, "UNAVAILABLE assumptions remained editable");
  await page.getByText(/MINIMUM_CASH_DEFINITION_UNAVAILABLE/).first().waitFor();
  await page.getByText(/Forecast recalculated\. Historical accounts remain locked/).waitFor();
  const signOffNote = page.getByLabel("Sign-Off Note *");
  await signOffNote.fill("FY2025 growth updated for the accepted quarterly earnings release.");
  signOffConflicts = true;
  await page.getByRole("button", { name: "Save model version" }).click();
  await page.getByText("Model authority changed", { exact: true }).waitFor();
  assert.equal(await firstAssumption.inputValue(), "0.04", "409 authority refresh replaced the dirty local forecast");
  await page.getByRole("button", { name: "Review and rebase local draft" }).click();
  await page.getByText("Rebase candidate calculated. Nothing has been stored.").waitFor();
  await page.getByRole("button", { name: "Apply rebase to local forecast" }).click();
  assert.equal(await firstAssumption.inputValue(), "0.04", "same-build rebase dropped the local forecast change");
  await page.getByText(/Forecast recalculated\. Historical accounts remain locked/).waitFor();
  await page.getByLabel("Sign-Off Note *").fill("Rebased FY2025 growth after an intervening approved revision.");
  await page.getByRole("button", { name: "Save model version" }).click();
  await page.getByText("Application model · R2").waitFor();
  assert.equal(signOffPosts, 2, "conflict and recovered sign-off requests did not both reach the server seam");
  assert.notEqual(modelRevisions[0].outputs.total_leverage, 4.2, "forecast assumption did not change the signed forward output");
  assert.equal(await historicalWorksheetCell.innerText(), historicalWorksheetValue, "forecast assumption changed a historical source cell");
  assert.equal(await calculatedWorksheetCell.innerText(), calculatedWorksheetValue, "forecast assumption changed a calculated historical cell");
  await page.evaluate(() => {
    const url = new URL(window.location.href);
    url.searchParams.set("task5-history", "prior");
    window.history.pushState({ task5History: "prior" }, "", url);
  });
  await firstAssumption.fill("0.06");
  await firstAssumption.press("Enter");
  const discardDraftDialog = () => page.getByRole("dialog", { name: "Discard draft changes?" });
  const caseSelect = page.getByRole("combobox", { name: "Select case" });
  await caseSelect.selectOption(raceCase.id);
  await discardDraftDialog().waitFor();
  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  assert.equal(await page.getByRole("dialog", { name: "Command palette" }).isVisible(), false, "command shortcut opened a nested modal");
  assert.ok(page.url().includes(`case=${caseRecord.id}`), "dismissed dirty-draft warning changed the selected case");
  await discardDraftDialog().getByRole("button", { name: "Keep editing" }).click();
  assert.equal(await caseSelect.evaluate((element) => document.activeElement === element), true, "canceling a case discard did not return focus to the case selector");
  const dirtyURL = page.url();
  const sourcesLink = page.getByRole("link", { name: "Sources", exact: true }).first();
  await sourcesLink.click();
  await discardDraftDialog().waitFor();
  await discardDraftDialog().getByRole("button", { name: "Keep editing" }).click();
  assert.equal(page.url(), dirtyURL, "dismissed dirty-draft warning allowed internal workspace navigation");
  assert.equal(await sourcesLink.evaluate((element) => document.activeElement === element), true, "canceling link navigation did not return focus to its trigger");
  for (const gesture of [{ ctrlKey: true, button: 0 }, { button: 1 }, { button: 0, target: "_blank" }]) {
    const intercepted = await sourcesLink.evaluate((element, candidate) => {
      const originalTarget = element.getAttribute("target");
      if (candidate.target) element.setAttribute("target", candidate.target);
      let preventedBeforeTarget = true;
      element.addEventListener("click", (event) => { preventedBeforeTarget = event.defaultPrevented; event.preventDefault(); }, { once: true });
      element.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, button: candidate.button, ctrlKey: candidate.ctrlKey === true }));
      if (originalTarget === null) element.removeAttribute("target"); else element.setAttribute("target", originalTarget);
      return preventedBeforeTarget;
    }, gesture);
    assert.equal(intercepted, false, `modified dirty link was intercepted: ${JSON.stringify(gesture)}`);
  }
  assert.equal(await discardDraftDialog().isVisible(), false, "modified dirty link opened the discard dialog");
  const commandTrigger = page.getByRole("button", { name: "Open command palette" });
  await commandTrigger.click();
  const dirtyDraftPalette = page.getByRole("dialog", { name: "Command palette" });
  await dirtyDraftPalette.getByRole("combobox", { name: "Search cases, workflows or evidence IDs" }).fill("Sources");
  await dirtyDraftPalette.getByRole("option", { name: "Open Sources" }).click();
  await discardDraftDialog().waitFor();
  await discardDraftDialog().getByRole("button", { name: "Keep editing" }).click();
  assert.equal(page.url(), dirtyURL, "canceling palette navigation changed the URL");
  assert.equal(await commandTrigger.evaluate((element) => document.activeElement === element), true, "canceling palette navigation did not return focus to the palette trigger");
  await firstAssumption.focus();
  await page.evaluate(() => window.history.back());
  await discardDraftDialog().waitFor();
  await page.keyboard.press("Escape");
  await discardDraftDialog().waitFor({ state: "hidden" });
  assert.equal(page.url(), dirtyURL, "dismissed dirty-draft warning allowed browser history navigation");
  assert.equal(await firstAssumption.inputValue(), "0.06", "browser history restoration dropped the dirty local forecast value");
  assert.equal(await firstAssumption.evaluate((element) => document.activeElement === element), true, "Escape did not return focus to the dirty editor after browser history cancelation");
  await page.evaluate(() => window.history.back());
  await discardDraftDialog().waitFor();
  await discardDraftDialog().getByRole("button", { name: "Discard changes" }).click();
  await page.waitForURL((url) => url.searchParams.get("task5-history") === null);
  assert.equal(await firstAssumption.inputValue(), "0.06", "confirming browser history cleared the draft before its owning editor changed state");
  assert.equal(new URL(page.url()).searchParams.has("task5-history"), false, "confirming browser history did not traverse exactly one boundary");
  const sameRouteModelLink = page.getByRole("link", { name: "Model", exact: true }).first();
  await sameRouteModelLink.click();
  await discardDraftDialog().waitFor();
  await discardDraftDialog().getByRole("button", { name: "Discard changes" }).click();
  await discardDraftDialog().waitFor({ state: "hidden" });
  assert.equal(await firstAssumption.inputValue(), "0.06", "dirty same-route confirmation dropped protection");
  await caseSelect.selectOption(raceCase.id);
  await discardDraftDialog().waitFor();
  await discardDraftDialog().getByRole("button", { name: "Discard changes" }).click();
  await page.waitForFunction((caseId) => document.querySelector("#case-select")?.value === caseId, raceCase.id);
  assert.equal(await caseSelect.inputValue(), raceCase.id, "confirming draft discard did not complete the case switch");
  await page.setViewportSize({ width: 720, height: 900 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth), false, "Model Builder causes page-level horizontal overflow at 200% desktop zoom width");
  await page.setViewportSize({ width: 1440, height: 1000 });
  page.once("dialog", (dialog) => void dialog.accept());
  for (const checkedRole of ["READER", "ANALYST"]) {
    const readOnly = checkedRole === "READER";
    modelRole = checkedRole;
    if (readOnly) modelRevisions = modelRevisions.map((item) => ({ ...item, export: { ...item.export, status: "FAILED", error: { code: "MODEL_REVISION_EXPORT_FAILED", detail: "Retry remains a shared write." } } }));
    await page.goto(`${baseURL}/model-builder/?case=${caseRecord.id}&role=${checkedRole.toLowerCase()}`, { waitUntil: "networkidle" });
    const roleInput = page.getByLabel("Revenue growth, FY2025, BASE");
    if (readOnly) {
      assert.equal(await roleInput.isDisabled(), true, `${checkedRole} could edit an assumption`);
      assert.equal(await page.getByLabel("Sign-Off Note *").count(), 0, `${checkedRole} was shown the shared Sign-Off Note control`);
      assert.equal(await page.getByRole("button", { name: "Save model version" }).count(), 0, `${checkedRole} was shown the shared save action`);
      await page.getByText(/Reader mode: the model and forecast assumptions remain readable/).waitFor();
      await page.getByText("Model versions", { exact: true }).click();
      assert.equal(await page.getByRole("button", { name: "Export" }).count(), 0, `${checkedRole} was shown a shared export retry`);
    } else {
      await roleInput.fill("0.071");
      await roleInput.press("Enter");
      await page.getByText(/Forecast recalculated\. Historical accounts remain locked/).waitFor();
      await page.getByLabel("Sign-Off Note *").waitFor();
      await page.getByRole("button", { name: "Save model version" }).waitFor();
      await roleInput.fill("0.05");
      await roleInput.press("Enter");
    }
    if (readOnly) modelRevisions = modelRevisions.map((item) => ({ ...item, export: { ...item.export, status: "READY", error: null } }));
  }
  modelRole = "ANALYST";
  page.once("dialog", (dialog) => void dialog.accept());
  for (const [state, text] of [["FAILED", "MODEL CALCULATION FAILED"], ["NOT_READY", "ACCEPTED FULL CREDIT REQUIRED"]]) {
    modelState = state; modelExportState = "NOT_REQUESTED";
    await page.goto(`${baseURL}/model-builder/?case=${caseRecord.id}&state=${state}`, { waitUntil: "networkidle" });
    await page.getByText(text, { exact: true }).waitFor();
  }
  modelLoadFails = true;
  await page.goto(`${baseURL}/model-builder/?case=${caseRecord.id}&state=load-error`, { waitUntil: "networkidle" });
  await page.getByText("Unavailable", { exact: true }).waitFor();
  modelLoadFails = false;
  await page.unroute(modelPath);
  await page.unroute(modelsPath);
  await page.unroute(worksheetPath);
  await page.unroute(exportPath);
  await page.unroute(registryPath);
  await page.unroute(revisionsPath);
  await page.unroute(previewPath);
  await page.unroute(signOffPath);
  await page.unroute(rebasePath);
  await page.unroute(tornadoPath);
  await page.unroute(identityPath);

  modelState = "READY"; modelExportState = "READY";
  const reportIdentityPath = (url) => url.pathname === "/api/me";
  let reportRole = "ANALYST";
  await page.route(reportIdentityPath, (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ role: reportRole }) }));

  const reportSections = {
    FULL_CREDIT: ["Credit Snapshot", "Recommendation", "Thesis and Variant View", "Business and Industry", "Capital Structure", "Base and Downside Model", "Liquidity and Covenants", "Risks, Catalysts, and Falsifiers", "Monitoring"],
    EARNINGS_UPDATE: ["Credit Snapshot", "What Changed", "Reported Versus Prior Bridge", "Model Impact", "Leverage and Liquidity", "Thesis and Recommendation Impact", "Risks, Catalysts, and Monitoring"],
    COVENANT_REFINANCING: ["Credit Snapshot", "Capital Structure and Maturity Wall", "Covenant Definitions and Headroom", "Liquidity", "Refinancing Options", "Base and Downside Breakpoints", "Actions and Monitoring"],
    RELATIVE_VALUE: ["Credit Snapshot", "Instrument Comparison", "Structure and Seniority", "Relative Compensation", "Catalysts and Risks", "Recommendation and Trade Gates", "Market Freshness"],
    DISTRESSED_RESTRUCTURING: ["Credit Snapshot", "Capital Structure and Priority", "Liquidity Runway", "Base, Downside, and Scenario Exhibits", "Recovery", "Covenant, Default, and Refinancing Milestones", "Catalysts and Process Risks", "Recommendation"],
    DEEP_RESEARCH: ["Research Question and Scope", "Executive Findings", "Evidence Synthesis", "Counterevidence and Gaps", "Implications for Thesis, Model, and Recommendation", "Unresolved Questions"],
  };
  const reportTitles = {
    FULL_CREDIT: "Investment Committee Credit Memo",
    EARNINGS_UPDATE: "Earnings Update",
    COVENANT_REFINANCING: "Covenant and Refinancing Brief",
    RELATIVE_VALUE: "Relative Value Note",
    DISTRESSED_RESTRUCTURING: "Scenario and Recovery Pack",
    DEEP_RESEARCH: "Evidence-Bound Research Memorandum",
  };
  const reportTemplate = (pathway) => {
    const blocks = reportSections[pathway].map((title, index) => ({ block_id: `${pathway.toLowerCase()}.section.${String(index + 1).padStart(2, "0")}`, slot_id: `section.${String(index + 1).padStart(2, "0")}`, kind: "NARRATIVE", title, required: true, order: index + 1 }));
    blocks.push({ block_id: `${pathway.toLowerCase()}.evidence-register`, slot_id: "appendix.evidence-register", kind: "EVIDENCE_REGISTER", title: "Evidence Register", required: true, order: blocks.length + 1 });
    return {
      template_id: `caos.${pathway.toLowerCase().replaceAll("_", "-")}.v1`,
      template_version: "caos.deliverable-template.v1",
      pathway,
      title: reportTitles[pathway],
      model_requirement: ["RELATIVE_VALUE", "DEEP_RESEARCH"].includes(pathway) ? "OPTIONAL" : "REQUIRED",
      allowed_appendices: ["GENERATED_METRIC", "GENERATED_TABLE", "GENERATED_CHART", "SCENARIO_EXHIBIT", "MODEL_APPENDIX", "LIMITATIONS"],
      optional_blocks: [
        ["GENERATED_METRIC", "appendix.generated-metric", 20, 1, true],
        ["GENERATED_TABLE", "appendix.generated-table", 20, 2, true],
        ["GENERATED_CHART", "appendix.generated-chart", 20, 3, true],
        ["SCENARIO_EXHIBIT", "appendix.scenario", 20, 4, true],
        ["MODEL_APPENDIX", "appendix.model-appendix", 1, 5, true],
        ["LIMITATIONS", "appendix.limitations", 1, 6, false],
      ].map(([kind, slot_stem, max_items, order, model_dependent]) => ({ kind, slot_stem, max_items, order, model_dependent })),
      blocks,
    };
  };
  const signedReportRevision = modelRevisions.find((revision) => revision.state === "ACTIVE");
  assert.ok(signedReportRevision, "Report Studio fixture has no signed active model revision");
  const reportSelection = { kind: "ANALYST_REVISION", build_id: modelBuildId, revision_id: signedReportRevision.id };
  const reportEligibility = () => ({
    active_revision: { revision_id: reportSelection.revision_id, build_id: modelBuildId, revision_number: signedReportRevision.revision_number, signed_by: "analyst", signed_at: "2026-08-26T10:00:00Z" },
    application_build: { build_id: modelBuildId, accepted_snapshot_id: accepted.id, input_fingerprint: "b".repeat(64), payload_digest: "c".repeat(64), status: "READY" },
    fallback_acknowledgement_required: false,
    default_model_selection: reportSelection,
  });
  const reportOrigin = (kind, authority_id, block_ids = []) => ({ kind, authority_id, block_ids });
  const analystReportSection = (block, title, page) => ({
    kind: "text", section_id: title.toLowerCase().replaceAll(/[^a-z0-9]+/g, "_").replaceAll(/^_|_$/g, ""),
    title, page, editable: true, origin: reportOrigin("ANALYST", block.block_id, block.citations.flatMap((citation) => citation.block_ids)), body: block.text,
  });
  const reportDocumentSections = (pathway, blocks) => {
    const narratives = blocks.filter((block) => block.kind === "NARRATIVE");
    const evidenceBlock = blocks.find((block) => block.kind === "EVIDENCE_REGISTER");
    const appendices = blocks.filter((block) => block.kind === "SCENARIO_EXHIBIT").map((block) => {
      const accessibleRows = [];
      for (const [caseName, periods] of Object.entries(block.scenario.outputs)) {
        for (const [period, metrics] of Object.entries(periods)) {
          for (const [metric, value] of Object.entries(metrics)) accessibleRows.push([`${caseName} / ${period} / ${metric}`, String(value)]);
        }
      }
      return {
        kind: "chart", section_id: block.block_id, title: block.title, page: "Appendix", editable: false,
        origin: reportOrigin("MODEL", block.scenario_digest), recipe: { chart_kind: "scenario", shocks: block.shocks },
        accessible_columns: ["Scenario / Metric", "Value"], accessible_rows: accessibleRows,
      };
    });
    const evidence = {
      kind: "table", section_id: "evidence_register", title: "Evidence Register", page: "Evidence", editable: false,
      origin: reportOrigin("ARTIFACT", accepted.id, evidenceBlock?.citations.flatMap((citation) => citation.block_ids) || []),
      columns: ["Source", "Blocks", "Claim"],
      rows: (evidenceBlock?.citations || []).map((citation) => [citation.source_id, citation.block_ids.join(", "), citation.claim || "Pinned evidence"]), note: null,
    };
    let sections;
    if (pathway !== "FULL_CREDIT") {
      sections = narratives.map((block, index) => analystReportSection(block, reportSections[pathway][index], "Analysis"));
    } else {
      const analyst = (index, page) => analystReportSection(narratives[index], reportSections[pathway][index], page);
      sections = [
      {
        kind: "columns", section_id: "credit_snapshot", title: "Credit Snapshot", page: "Decision", editable: false,
        origin: reportOrigin("ARTIFACT", accepted.id),
        items: [
          [{ kind: "profile", section_id: "credit_snapshot_authority", title: "Accepted Analysis", page: "Decision", editable: false, origin: reportOrigin("ARTIFACT", accepted.id), rows: [{ label: "CP-1", value: "Revenue 1,160; EBITDA 222" }, { label: "CP-2", value: "Starting model assumptions ready" }] }],
          [{ ...analyst(0, "Decision"), section_id: "credit_snapshot_commentary", title: "Analyst Snapshot" }],
        ],
      },
      analyst(1, "Decision"),
      analyst(2, "Decision"),
      analyst(3, "Business"),
      analyst(4, "Capital"),
      {
        kind: "columns", section_id: "base_downside_model", title: "Base and Downside Model", page: "Financials", editable: false,
        origin: reportOrigin("MODEL", signedReportRevision.id),
        items: [
          [{ ...analyst(5, "Financials"), section_id: "base_downside_commentary", title: "Analyst Model View" }],
          [{
            kind: "table", section_id: "base_downside_model_outputs", title: "Calculated Model Output", page: "Financials", editable: false,
            origin: reportOrigin("MODEL", signedReportRevision.id), columns: ["Case / Period / Metric", "Value"],
            rows: [["BASE / FY2025 / total_leverage", String(signedReportRevision.outputs.total_leverage)], ["BASE / FY2025 / revenue", String(signedReportRevision.outputs.revenue.FY2025)]],
            note: "Generated values are locked to the selected model authority.",
          }],
        ],
      },
      analyst(6, "Financials"),
      analyst(7, "Risk"),
      analyst(8, "Risk"),
      ];
    }
    return [...sections, ...appendices, evidence];
  };
  const reportDraft = (pathway, version = 1, contentOverride = null) => {
    const template = reportTemplate(pathway);
    const blocks = template.blocks.map((block) => block.kind === "NARRATIVE"
      ? { kind: "NARRATIVE", block_id: block.block_id, slot_id: block.slot_id, text: `${block.title} exact analyst conclusion.`, content_mode: "ANALYST_JUDGMENT", citations: [] }
      : { kind: "EVIDENCE_REGISTER", block_id: block.block_id, slot_id: block.slot_id, citations: [] });
    return {
      id: `deliverable_${pathway.toLowerCase()}_${version}`, case_id: caseRecord.id, pathway, version, author: "analyst", created_at: `2026-08-26T10:0${version}:00Z`,
      template_id: template.template_id, template_version: template.template_version, digest: String(version).repeat(64),
      content: contentOverride || {
        template_id: template.template_id, template_version: template.template_version,
        document_schema_version: "caos.deliverable.document.v1", document_sections: reportDocumentSections(pathway, blocks),
        model_selection: reportSelection, model_identity: { ...reportSelection }, blocks, generated_blocks: {},
      },
    };
  };
  const reportWorkspaces = new Map(Object.keys(reportSections).map((pathway) => {
    const draft = reportDraft(pathway);
    return [pathway, { template: reportTemplate(pathway), current: draft, history: [draft], frozen_history: [], model_eligibility: reportEligibility() }];
  }));
  let reportConflict = false;
  let holdReportSave = false;
  let reportLastSave;
  let frozenSequence = 0;
  let heldReportLifecycle = "";
  let releaseHeldReportLifecycle = null;
  const waitForHeldReportLifecycle = async (operation) => {
    if (heldReportLifecycle !== operation) return;
    await new Promise((resolve) => { releaseHeldReportLifecycle = resolve; });
    releaseHeldReportLifecycle = null;
    heldReportLifecycle = "";
  };
  const releaseReportLifecycle = async (operation) => {
    for (let attempt = 0; attempt < 100 && releaseHeldReportLifecycle === null; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
    assert.ok(releaseHeldReportLifecycle, `${operation} did not reach the held lifecycle response seam`);
    releaseHeldReportLifecycle();
  };
  const frozenBaseLeverage = 123456.78;
  const frozenDownsideLeverage = 234567.89;
  const fulfillReportExport = (route, deliverableId, format) => route.fulfill({
    status: 200,
    contentType: { md: "text/markdown", pdf: "application/pdf", xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }[format],
    headers: { "content-disposition": `attachment; filename="${deliverableId}.${format}"` },
    body: format === "pdf" ? "%PDF-1.4\n% governed fixture" : `governed ${format} fixture`,
  });
  const reportApiPath = (url) => url.pathname.startsWith(`/api/cases/${caseRecord.id}/deliverables/`);
  await page.route(reportApiPath, async (route) => {
    const url = new URL(route.request().url());
    const suffix = url.pathname.split("/deliverables/")[1];
    if (suffix.startsWith("by-id/")) {
      const [, deliverableId, action, format] = suffix.split("/");
      const current = [...reportWorkspaces.values()].flatMap((item) => item.frozen_history).find((item) => item.id === deliverableId);
      if (action === "export") return fulfillReportExport(route, deliverableId, format);
      if (action === "approve") {
        await waitForHeldReportLifecycle("file");
        const filed = { ...current, status: "FILED", approved_by: "approver", approved_at: "2026-08-26T12:00:00Z" };
        const workspace = reportWorkspaces.get(filed.pathway);
        workspace.frozen_history = workspace.frozen_history.map((item) => item.id === filed.id ? filed : item.status === "FILED" ? { ...item, status: "SUPERSEDED", superseded_by_id: filed.id } : item);
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(filed) });
      }
      if (action === "request-changes") {
        await waitForHeldReportLifecycle("changes");
        const workspace = reportWorkspaces.get(current.pathway);
        const replacement = reportDraft(current.pathway, workspace.current.version + 1, workspace.current.content);
        const changed = { ...current, status: "CHANGES_REQUESTED", change_request: { comment: route.request().postDataJSON().comment, requested_by: "approver", requested_at: "2026-08-26T11:00:00Z" } };
        workspace.current = replacement; workspace.history.push(replacement); workspace.frozen_history = workspace.frozen_history.map((item) => item.id === changed.id ? changed : item);
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ frozen: changed, draft: replacement }) });
      }
    }
    const [pathway, action] = suffix.split("/");
    const workspace = reportWorkspaces.get(pathway);
    if (!workspace) return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "missing fixture" }) });
    if (route.request().method() === "GET") return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(workspace) });
    if (action === "draft") {
      const payload = route.request().postDataJSON();
      reportLastSave = payload;
      await waitForHeldReportLifecycle("restore");
      if (holdReportSave) await new Promise((resolve) => setTimeout(resolve, 1500));
      if (reportConflict) {
        reportConflict = false;
        expectedReportConflicts += 1;
        const current = { ...workspace.current, id: `deliverable_conflict_${pathway.toLowerCase()}`, version: workspace.current.version + 1, author: "second-writer", created_at: "2026-08-26T10:30:00Z" };
        workspace.current = current; workspace.history.push(current);
        return route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ detail: { code: "DELIVERABLE_VERSION_CONFLICT", current } }) });
      }
      const saved = reportDraft(pathway, workspace.current.version + 1, {
        template_id: workspace.template.template_id, template_version: workspace.template.template_version,
        document_schema_version: "caos.deliverable.document.v1", document_sections: reportDocumentSections(pathway, payload.blocks),
        model_selection: payload.model_selection, model_identity: payload.model_selection, blocks: payload.blocks,
        generated_blocks: Object.fromEntries(payload.blocks.filter((block) => block.kind.startsWith("GENERATED") || block.kind === "SCENARIO_EXHIBIT").map((block) => [block.block_id, { status: "READY", outputs: { BASE: { FY2027: { total_leverage: 4.2 } } } }])),
      });
      workspace.current = saved; workspace.history.push(saved);
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(workspace) });
    }
    if (action === "freeze") {
      await waitForHeldReportLifecycle("freeze");
      frozenSequence += 1;
      const previewDigest = String(frozenSequence + 4).repeat(64);
      const inputFingerprint = "e".repeat(64);
      const frozen = {
        id: `frozen_report_${frozenSequence}`, case_id: caseRecord.id, pathway, draft_version: workspace.current.version, status: "FROZEN", frozen_by: "analyst", frozen_at: "2026-08-26T10:45:00Z", approved_by: null, approved_at: null, approval_comment: null, superseded_by_id: null, change_request: null,
        digest: "d".repeat(64), preview_digest: previewDigest, input_fingerprint: inputFingerprint, authority_identity: {}, model_identity: reportSelection, template_identity: {}, render_identity: {},
        payload: {
          schema_version: "caos.frozen-deliverable.v1", case_id: caseRecord.id, pathway,
          draft: { id: workspace.current.id, version: workspace.current.version, digest: workspace.current.digest },
          template: { title: workspace.template.title, template_id: workspace.template.template_id, template_version: workspace.template.template_version },
          authority: { accepted_snapshot_id: accepted.id, accepted_snapshot_digest: "a".repeat(64), source_set_id: accepted.source_set_id, source_set_digest: "b".repeat(64) },
          model: {
            kind: "ANALYST_REVISION", build_id: modelBuildId, revision_id: reportSelection.revision_id, accepted_snapshot_id: accepted.id,
            build_input_fingerprint: "b".repeat(64), build_payload_digest: "c".repeat(64), registry_version: registryVersion, registry_digest: registryDigest,
            application_build: { payload: { schema_version: "caos.model.worksheet.v1", identity: { issuer_id: caseRecord.id, issuer_name: caseRecord.issuer }, tabs: [] }, qa: { status: "PASS", limitation_flags: ["COVENANT_DATA_UNAVAILABLE"], validation_warnings: ["Covenant headroom cannot be calculated."] }, calculation_runtime: { assumption_registry_version: registryVersion, calculation_contract_version: "calculation-v1" }, export: { sha256: "1".repeat(64), size: 4096, filename: "application-model.xlsx" } },
            model_export: { sha256: "2".repeat(64), size: 4200, filename: "signed-revision.xlsx" },
            effective_assumptions: [{ assumption_id: "operating.consolidated_revenue_growth", case: "BASE", period_id: "FY2027", status: "READY", value: 0.03, unit: "PERCENT" }],
            assumption_gaps: [{ assumption_id: "credit.covenant.limit", case: "DOWNSIDE", period_id: "FY2027", status: "UNAVAILABLE", value: null, unit: "MULTIPLE", gap_code: "COVENANT_NOT_DISCLOSED" }],
            outputs: { BASE: { FY2027: { total_leverage: frozenBaseLeverage, total_debt_reported: 630, net_debt: 590 } }, DOWNSIDE: { FY2027: { total_leverage: frozenDownsideLeverage, total_debt_reported: 630, net_debt: 605 } } },
            debt: { BASE: { FY2027: { total_debt_reported: 630, net_debt: 590 } }, DOWNSIDE: { FY2027: { total_debt_reported: 630, net_debt: 605 } } },
            warnings: { limitation_flags: ["COVENANT_DATA_UNAVAILABLE"], validation_warnings: ["Covenant headroom cannot be calculated."] },
          },
          content: workspace.current.content,
          evidence: [{ source_id: source.id, sha256: source.sha256, block_ids: [source.blocks[0].block_id], withdrawn: false }],
          methodology: { build_id: "deploy-v-workbench" }, renderer: { version: "caos.deliverable-renderer.v2", contract_digest: "3".repeat(64) }, input_fingerprint: inputFingerprint, preview_digest: previewDigest,
        },
        exports: Object.fromEntries(["md", "pdf", "xlsx"].map((format) => [format, { deliverable_id: `frozen_report_${frozenSequence}`, format, vault_key: `vault/${format}`, sha256: format.repeat(64).slice(0, 64), size: 512, renderer_identity: {}, created_at: "2026-08-26T10:45:00Z" }])),
      };
      workspace.frozen_history.push(frozen);
      return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(frozen) });
    }
  });
  await page.route((url) => url.pathname === `/api/cases/${caseRecord.id}/models/assumption-registry`, (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ version: registryVersion, digest: registryDigest, build_id: modelBuildId, definitions: [{ assumption_id: "operating.consolidated_revenue_growth", label: "Revenue growth", periods: ["FY2025", "FY2026", "FY2027"] }], defaults: [{ assumption_id: "operating.consolidated_revenue_growth", case: "BASE", period_id: "FY2027", status: "READY", value: 0.03, unit: "PERCENT" }] }) }));
  await page.route((url) => url.pathname === `/api/cases/${caseRecord.id}/models/scenarios`, async (route) => {
    const payload = route.request().postDataJSON();
    await waitForHeldReportLifecycle("scenario");
    const scenario = { case_id: caseRecord.id, build_id: payload.build_id, base_revision_id: payload.base_revision_id, registry_version: payload.registry_version, registry_digest: payload.registry_digest, draft_generation: payload.draft_generation, effective_assumptions: payload.shocks, assumptions_digest: "7".repeat(64), outputs: { BASE: { FY2027: { total_leverage: 4.2 } }, DOWNSIDE: { FY2027: { total_leverage: 5.8 } } }, outputs_digest: "8".repeat(64), deltas: {} };
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ draft_generation: payload.draft_generation, baseline: {}, scenario, scenario_digest: "9".repeat(64) }) });
  });

  const fullCreditWorkspace = reportWorkspaces.get("FULL_CREDIT");
  const governedReportEligibility = fullCreditWorkspace.model_eligibility;
  const governedReportCurrent = fullCreditWorkspace.current;
  fullCreditWorkspace.model_eligibility = {
    ...governedReportEligibility,
    active_revision: { ...governedReportEligibility.active_revision, revision_id: "revision_new_authority" },
  };
  await page.goto(`${baseURL}/report-studio/?case=${caseRecord.id}&prerequisite=stale-model`, { waitUntil: "networkidle" });
  const staleModelLink = page.getByRole("link", { name: "Open Model Builder" });
  await staleModelLink.waitFor();
  assert.equal(new URL(await staleModelLink.getAttribute("href"), baseURL).searchParams.get("case"), caseRecord.id, "stale-model remedy lost case context");
  fullCreditWorkspace.model_eligibility = { active_revision: null, application_build: null, fallback_acknowledgement_required: false, default_model_selection: null };
  fullCreditWorkspace.current = { ...governedReportCurrent, content: { ...governedReportCurrent.content, model_selection: null, model_identity: null } };
  await page.reload({ waitUntil: "networkidle" });
  const missingModelLink = page.getByRole("link", { name: "Open Run Console" });
  await missingModelLink.waitFor();
  assert.equal(new URL(await missingModelLink.getAttribute("href"), baseURL).searchParams.get("case"), caseRecord.id, "missing-model remedy lost case context");
  fullCreditWorkspace.model_eligibility = governedReportEligibility;
  fullCreditWorkspace.current = governedReportCurrent;

  await page.goto(`${baseURL}/report-studio/?case=${caseRecord.id}`, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "Compose", exact: true }).waitFor();
  await page.getByRole("heading", { name: `${caseRecord.issuer} — ${caseRecord.name}` }).waitFor();
  await page.getByText(signedReportRevision.id, { exact: true }).first().waitFor();
  assert.equal(await page.evaluate(() => Object.keys(sessionStorage).some((key) => key.startsWith("caos-report-draft:"))), false, "Report Studio retained browser-persistent drafts");

  const recoveryPathway = "DEEP_RESEARCH";
  const recoveryTemplate = reportTemplate(recoveryPathway);
  const recoveryBlocks = reportDraft(recoveryPathway).content.blocks.map((block, index) => index === 0 ? { ...block, text: "Recovered from stale server v0." } : block);
  const recoveryCopy = {
    caseId: caseRecord.id, pathway: recoveryPathway, savedAt: Date.now(), expectedVersion: 0,
    templateId: recoveryTemplate.template_id, templateVersion: recoveryTemplate.template_version,
    modelSelection: reportSelection, blocks: recoveryBlocks,
  };
  await page.evaluate(([key, value]) => localStorage.setItem(key, value), [
    `caos:report-recovery:${encodeURIComponent(caseRecord.id)}:${recoveryPathway}`,
    JSON.stringify(recoveryCopy),
  ]);
  await page.getByRole("combobox", { name: "Pathway template" }).selectOption(recoveryPathway);
  await page.getByText(/Unsaved browser copy from/).waitFor();
  await page.getByRole("button", { name: "Retry save now" }).click();
  await page.getByText("Saved v2", { exact: true }).waitFor({ timeout: 5000 });
  assert.equal(reportLastSave.expected_version, 0, "recovery save discarded its original compare-and-swap base");
  assert.equal(reportLastSave.blocks[0].text, "Recovered from stale server v0.", "recovery save did not use the browser copy");

  const reportPaper = () => page.getByRole("article", { name: /Deliverable preview/i });
  const reportTitle = (title) => reportPaper().locator(".rd-subtitle").filter({ hasText: title });
  const openReportTool = async (name) => {
    const details = page.locator("details").filter({ has: page.getByText(name, { exact: true }) }).first();
    if (await details.getAttribute("open") === null) await details.locator(":scope > summary").click();
  };
  for (const [pathway, label] of Object.entries(reportTitles)) {
    await page.getByRole("combobox", { name: "Pathway template" }).selectOption(pathway);
    await reportTitle(label).waitFor();
  }

  await page.getByRole("combobox", { name: "Pathway template" }).selectOption("EARNINGS_UPDATE");
  const earningsHistoryEditor = page.getByRole("textbox", { name: "Credit Snapshot" });
  for (const [value, version] of [["History cycle one", 2], ["History cycle two", 3], ["History cycle three", 4]]) {
    await earningsHistoryEditor.fill(value);
    await page.getByText(`Saved v${version}`, { exact: true }).waitFor({ timeout: 5000 });
  }
  await page.evaluate(() => window.history.back());
  await page.waitForURL((url) => url.pathname.replace(/\/$/, "") !== "/report-studio");
  assert.notEqual(new URL(page.url()).pathname.replace(/\/$/, ""), "/report-studio", "three clean autosave cycles left stacked same-URL history sentinels");

  await page.goto(`${baseURL}/report-studio/?case=${caseRecord.id}`, { waitUntil: "networkidle" });
  await page.getByRole("combobox", { name: "Pathway template" }).selectOption("EARNINGS_UPDATE");
  const pathwaySelect = page.getByRole("combobox", { name: "Pathway template" });
  const dirtyPathwayEditor = page.getByRole("textbox", { name: "Credit Snapshot" });
  await dirtyPathwayEditor.fill("Dirty pathway fence value");
  await page.getByText("Unsaved changes", { exact: true }).waitFor();
  await pathwaySelect.selectOption("FULL_CREDIT");
  await discardDraftDialog().waitFor();
  assert.equal(await pathwaySelect.inputValue(), "EARNINGS_UPDATE", "dirty pathway cancel changed pathway before confirmation");
  await discardDraftDialog().getByRole("button", { name: "Keep editing" }).click();
  assert.equal(await pathwaySelect.evaluate((element) => document.activeElement === element), true, "dirty pathway cancel did not return focus to the pathway selector");
  await pathwaySelect.selectOption("FULL_CREDIT");
  await discardDraftDialog().waitFor();
  await discardDraftDialog().getByRole("button", { name: "Discard changes" }).click();
  await reportTitle("Investment Committee Credit Memo").waitFor();
  assert.equal(await pathwaySelect.inputValue(), "FULL_CREDIT", "dirty pathway confirm did not change pathway");
  await pathwaySelect.selectOption("EARNINGS_UPDATE");
  await reportTitle("Earnings Update").waitFor();
  const dirtyHistoryEditor = page.getByRole("textbox", { name: "Credit Snapshot" });
  await dirtyHistoryEditor.fill("Dirty history fence value");
  await page.getByText("Unsaved changes", { exact: true }).waitFor();
  const dirtyReportURL = page.url();
  await dirtyHistoryEditor.focus();
  await page.evaluate(() => window.history.back());
  await discardDraftDialog().waitFor();
  await discardDraftDialog().getByRole("button", { name: "Keep editing" }).click();
  assert.equal(page.url(), dirtyReportURL, "dismissed Report Studio Back changed the exact URL");
  assert.equal(await dirtyHistoryEditor.inputValue(), "Dirty history fence value", "dismissed Report Studio Back dropped local content");
  assert.equal(await dirtyHistoryEditor.evaluate((element) => document.activeElement === element), true, "canceling Report Studio browser history did not return focus to the editor");
  await page.getByText("Saved v5", { exact: true }).waitFor({ timeout: 5000 });

  await page.getByRole("combobox", { name: "Pathway template" }).selectOption("FULL_CREDIT");
  const thesisEditor = page.getByRole("textbox", { name: "Credit Snapshot" });
  await thesisEditor.fill("First update");
  await thesisEditor.fill("Latest serialized update");
  await page.getByText(/Saved v2/).waitFor({ timeout: 5000 });
  assert.equal(reportLastSave.blocks[0].text, "Latest serialized update", "older autosave generation claimed the latest draft");

  heldReportLifecycle = "restore";
  await page.getByRole("button", { name: "Restore as new revision" }).last().click();
  const heldRestoreValue = await thesisEditor.inputValue();
  assert.equal(await thesisEditor.isDisabled(), true, "narrative remained editable during Restore");
  let heldRestoreEditRejected = false;
  try {
    await thesisEditor.fill("Mutation attempted during held Restore", { timeout: 250 });
  } catch {
    heldRestoreEditRejected = true;
  }
  assert.equal(heldRestoreEditRejected, true, "native disabled Restore lock accepted a narrative edit");
  assert.equal(await thesisEditor.inputValue(), heldRestoreValue, "held Restore changed the narrative before its response");
  await releaseReportLifecycle("restore");
  await page.getByText("Restored v1 as new revision v3.", { exact: true }).waitFor();
  assert.equal(await thesisEditor.inputValue(), "Credit Snapshot exact analyst conclusion.", "saved Restore response was not adopted in its current scope");

  heldReportLifecycle = "restore";
  await page.getByRole("button", { name: "Restore as new revision" }).first().click();
  assert.equal(await page.locator("[data-primary-report-action]").isDisabled(), true, "Freeze remained enabled during Restore");
  await page.getByRole("combobox", { name: "Pathway template" }).selectOption("EARNINGS_UPDATE");
  await reportTitle("Earnings Update").waitFor();
  await releaseReportLifecycle("restore");
  await new Promise((resolve) => setTimeout(resolve, 100));
  assert.equal(await page.getByText(/Restored v1 as new revision/).count(), 0, "late Full Credit Restore adopted status in Earnings Update");
  assert.equal(await reportTitle("Investment Committee Credit Memo").count(), 0, "late Full Credit Restore replaced the Earnings paper");
  await page.getByRole("combobox", { name: "Pathway template" }).selectOption("FULL_CREDIT");

  await openReportTool("Scenario insertion");
  await page.getByLabel("Shock value").fill("0.07");
  heldReportLifecycle = "scenario";
  await page.getByRole("button", { name: "Calculate and insert exact exhibit" }).click();
  assert.equal(await page.locator("[data-primary-report-action]").isDisabled(), true, "Freeze remained enabled during Scenario calculation");
  await page.getByRole("combobox", { name: "Pathway template" }).selectOption("EARNINGS_UPDATE");
  await reportTitle("Earnings Update").waitFor();
  await releaseReportLifecycle("scenario");
  await new Promise((resolve) => setTimeout(resolve, 100));
  assert.equal(await page.getByText("Server-calculated Scenario Exhibit inserted into the Draft.").count(), 0, "late Full Credit Scenario adopted status in Earnings Update");
  assert.equal(await reportTitle("Investment Committee Credit Memo").count(), 0, "late Full Credit Scenario replaced the Earnings paper");
  await page.getByRole("combobox", { name: "Pathway template" }).selectOption("FULL_CREDIT");
  await page.getByRole("button", { name: "Credit SnapshotRequired" }).click().catch(() => {});
  await page.getByRole("radio", { name: "Evidence-bound" }).check();
  await openReportTool("Evidence search and citations");
  await page.locator(".evidence-source-list details").first().locator("summary").click();
  await page.getByRole("button", { name: "Cite block" }).first().click();
  await page.getByText("Evidence-bound", { exact: true }).last().waitFor();
  await openReportTool("Scenario insertion");
  await page.getByLabel("Shock value").fill("0.07");
  await page.getByRole("button", { name: "Calculate and insert exact exhibit" }).click();
  await page.getByText("Server-calculated Scenario Exhibit inserted into the Draft.").waitFor();
  await page.getByText(/Saved v5/).waitFor({ timeout: 5000 });
  await page.getByText("BASE / FY2027 / total_leverage", { exact: true }).waitFor();
  await page.getByText("DOWNSIDE / FY2027 / total_leverage", { exact: true }).waitFor();

  reportConflict = true;
  await thesisEditor.fill("Local conflict value");
  await page.getByText("Conflict", { exact: true }).waitFor({ timeout: 5000 });
  await page.getByText(/Your local content remains unchanged/).waitFor();
  assert.equal(await thesisEditor.inputValue(), "Local conflict value");
  await page.getByRole("button", { name: /Use shared v6/ }).click();
  assert.notEqual(await thesisEditor.inputValue(), "Local conflict value");

  holdReportSave = true;
  await thesisEditor.fill("Unsaved case fence");
  await page.getByText("Unsaved changes", { exact: true }).waitFor();
  const restoreButtons = page.getByRole("button", { name: "Restore as new revision" });
  const restoreState = await restoreButtons.evaluateAll((buttons) => buttons.map((button) => ({ disabled: button.hasAttribute("disabled"), html: button.outerHTML })));
  assert.equal(await restoreButtons.first().isDisabled(), true, `Restore raced a pending autosave: ${JSON.stringify(restoreState)}`);
  await page.waitForTimeout(900);
  holdReportSave = false;
  const reportCaseSelect = page.getByRole("combobox", { name: "Select case" });
  await reportCaseSelect.selectOption(raceCase.id);
  await discardDraftDialog().waitFor();
  assert.equal(await page.getByRole("combobox", { name: "Select case" }).inputValue(), caseRecord.id, "Report Studio dirty case switch was not fenced");
  await discardDraftDialog().getByRole("button", { name: "Keep editing" }).click();
  assert.equal(await reportCaseSelect.evaluate((element) => document.activeElement === element), true, "canceling Report Studio case discard did not return focus to the selector");
  await page.getByText(/Saved v7/).waitFor({ timeout: 5000 });

  heldReportLifecycle = "freeze";
  await page.getByRole("button", { name: /Freeze saved v7/ }).click();
  const heldFreezeValue = await thesisEditor.inputValue();
  assert.equal(await thesisEditor.isDisabled(), true, "narrative remained editable during Freeze");
  assert.equal(await page.getByRole("radio", { name: "Evidence-bound" }).isDisabled(), true, "content mode remained editable during Freeze");
  assert.equal(await page.getByRole("radio", { name: /Active Analyst Model/ }).isDisabled(), true, "model selection remained editable during Freeze");
  assert.equal(await page.getByLabel("Shock value").isDisabled(), true, "scenario input remained editable during Freeze");
  assert.equal(await page.getByRole("button", { name: "Add generated metric" }).isDisabled(), true, "optional composition remained editable during Freeze");
  assert.equal(await page.getByRole("button", { name: "Restore as new revision" }).first().isDisabled(), true, "Restore remained enabled during Freeze");
  assert.equal(await page.getByRole("button", { name: "File exact Frozen version" }).count(), 0, "File action became reachable while Freeze owned the lifecycle");
  assert.equal(await page.getByRole("button", { name: "Request changes" }).count(), 0, "Change action became reachable while Freeze owned the lifecycle");
  assert.equal(await thesisEditor.inputValue(), heldFreezeValue, "held Freeze changed the draft narrative");
  await page.getByRole("combobox", { name: "Pathway template" }).selectOption("EARNINGS_UPDATE");
  await reportTitle("Earnings Update").waitFor();
  await releaseReportLifecycle("freeze");
  await new Promise((resolve) => setTimeout(resolve, 100));
  assert.equal(await page.getByText(/Immutable FROZEN review/).count(), 0, "late Full Credit Freeze made Earnings Update immutable");
  assert.equal(await reportTitle("Investment Committee Credit Memo").count(), 0, "late Full Credit Freeze replaced the Earnings paper");
  assert.equal(await page.getByRole("combobox", { name: "Pathway template" }).inputValue(), "EARNINGS_UPDATE", "late Full Credit Freeze changed the selected pathway");
  await page.getByRole("combobox", { name: "Pathway template" }).selectOption("FULL_CREDIT");
  await page.getByRole("button", { name: /FROZEN · Draft v7/ }).first().click();
  await page.getByText(/Immutable FROZEN review/).waitFor();
  const firstFrozen = reportWorkspaces.get("FULL_CREDIT").frozen_history.at(-1);
  assert.equal(firstFrozen.payload.draft.version, 7, "freeze did not bind the exact saved version");
  assert.equal(firstFrozen.payload.model.revision_id, signedReportRevision.id, "freeze changed the signed model authority");
  assert.deepEqual(firstFrozen.payload.content.document_sections, reportWorkspaces.get("FULL_CREDIT").current.content.document_sections, "freeze changed the canonical document");
  assert.equal(await page.getByRole("link", { name: "PDF" }).count(), 0, "Frozen Deliverable exposed unfiled bytes");
  const frozenPaper = page.getByRole("article", { name: "Frozen Deliverable preview" });
  await frozenPaper.getByRole("heading", { name: "Credit Snapshot" }).waitFor();
  await frozenPaper.getByRole("heading", { name: "Accepted Analysis" }).waitFor();
  await frozenPaper.getByRole("heading", { name: "Analyst Snapshot" }).waitFor();
  await frozenPaper.getByRole("heading", { name: "Recommendation" }).waitFor();
  await frozenPaper.getByRole("heading", { name: "Base and Downside Model" }).waitFor();
  await frozenPaper.getByRole("heading", { name: "Calculated Model Output" }).waitFor();
  await frozenPaper.getByText("4.1", { exact: true }).waitFor();
  await frozenPaper.getByText("1194.8", { exact: true }).waitFor();
  assert.equal(await frozenPaper.getByText("123,456.78", { exact: true }).count(), 0, "Frozen preview bypassed canonical document sections");
  const modelAuthorityLabel = frozenPaper.getByText("Locked · model", { exact: true }).first();
  assert.equal(await modelAuthorityLabel.getAttribute("title"), `Authority ${signedReportRevision.id}`);
  assert.equal(firstFrozen.payload.renderer.version, "caos.deliverable-renderer.v2");

  reportRole = "APPROVER";
  await page.goto(`${baseURL}/report-studio/?case=${caseRecord.id}`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /FROZEN · Draft v7/ }).first().click();
  await page.getByLabel("Required comment to request changes").fill("Clarify the downside bridge.");
  heldReportLifecycle = "changes";
  await page.getByRole("button", { name: "Request changes" }).click();
  assert.equal(await page.getByRole("button", { name: "File exact Frozen version" }).isDisabled(), true, "File remained enabled during Request Changes");
  await page.getByRole("combobox", { name: "Pathway template" }).selectOption("EARNINGS_UPDATE");
  await reportTitle("Earnings Update").waitFor();
  await releaseReportLifecycle("changes");
  await new Promise((resolve) => setTimeout(resolve, 100));
  assert.equal(await page.getByText(/editable Draft v8 created/).count(), 0, "late Full Credit change request adopted status in Earnings Update");
  assert.equal(await page.getByRole("combobox", { name: "Pathway template" }).inputValue(), "EARNINGS_UPDATE", "late change request changed the selected pathway");
  await page.getByRole("combobox", { name: "Pathway template" }).selectOption("FULL_CREDIT");
  await page.getByText("Saved v8", { exact: true }).waitFor();
  assert.equal(reportWorkspaces.get("FULL_CREDIT").frozen_history[0].status, "CHANGES_REQUESTED");

  await page.getByRole("button", { name: /Freeze saved v8/ }).click();
  await page.getByText(/Immutable FROZEN review/).waitFor();
  heldReportLifecycle = "file";
  await page.getByRole("button", { name: "File exact Frozen version" }).click();
  assert.equal(await page.getByRole("button", { name: "Request changes" }).isDisabled(), true, "Request Changes remained enabled during File");
  await page.getByRole("combobox", { name: "Pathway template" }).selectOption("EARNINGS_UPDATE");
  await reportTitle("Earnings Update").waitFor();
  await releaseReportLifecycle("file");
  await new Promise((resolve) => setTimeout(resolve, 100));
  assert.equal(await page.getByText("Exact Frozen Deliverable filed.").count(), 0, "late Full Credit filing adopted status in Earnings Update");
  assert.equal(await page.getByRole("combobox", { name: "Pathway template" }).inputValue(), "EARNINGS_UPDATE", "late filing changed the selected pathway");
  await page.getByRole("combobox", { name: "Pathway template" }).selectOption("FULL_CREDIT");
  await page.getByRole("button", { name: /FILED · Draft v8/ }).first().click();
  await page.getByText(/Immutable FILED review/).waitFor();
  let governedDownloadCount = 0;
  await page.route(`**/api/cases/${caseRecord.id}/deliverables/by-id/*/export/*`, (route) => {
    governedDownloadCount += 1;
    const parts = new URL(route.request().url()).pathname.split("/");
    return fulfillReportExport(route, parts.at(-3), parts.at(-1));
  });
  for (const format of ["MD", "PDF", "XLSX"]) {
    const link = page.getByRole("link", { name: format });
    await link.waitFor();
    assert.match(await link.getAttribute("href"), new RegExp(`/deliverables/by-id/frozen_report_2/export/${format.toLowerCase()}$`));
    assert.equal(await link.getAttribute("download"), "", `${format} export lost its native download hint`);
    await link.evaluate((element) => element.removeAttribute("download"));
    const [download] = await Promise.all([page.waitForEvent("download"), link.click()]);
    assert.equal(download.suggestedFilename(), `frozen_report_2.${format.toLowerCase()}`);
    assert.equal(await download.failure(), null, `${format} export download failed`);
  }
  assert.equal(governedDownloadCount, 3, "filed export clicks bypassed the governed download responses");

  reportRole = "READER";
  await page.goto(`${baseURL}/report-studio/?case=${caseRecord.id}`, { waitUntil: "networkidle" });
  assert.equal(await page.getByRole("textbox", { name: "Credit Snapshot" }).isDisabled(), true, "reader could edit shared Deliverable");
  assert.equal(await page.getByRole("button", { name: "File exact Frozen version" }).count(), 0, "reader was shown approval authority");
  await page.setViewportSize({ width: 720, height: 900 });
  const reportOverflow = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
    offenders: [...document.querySelectorAll("body *")].map((element) => {
      const rect = element.getBoundingClientRect();
      return { tag: element.tagName, className: element.className, left: rect.left, right: rect.right, width: rect.width, scrollWidth: element.scrollWidth, clientWidth: element.clientWidth };
    }).filter((item) => item.right > document.documentElement.clientWidth + 1 || item.left < -1).slice(0, 12),
  }));
  assert.equal(reportOverflow.scrollWidth > reportOverflow.clientWidth, false, `Report Studio causes page-level horizontal overflow at 200% desktop zoom width: ${JSON.stringify(reportOverflow)}`);
  await page.setViewportSize({ width: 1440, height: 1000 });

  await page.goto(`${baseURL}/sources/?case=${caseRecord.id}&artifact=${artifact.id}`, { waitUntil: "networkidle" });
  const matching = page.locator(`[data-evidence-id="${source.id}"]`);
  assert.equal(await matching.count(), 1);
  const chip = matching.first();
  await chip.focus();
  await page.waitForFunction((evidenceId) => {
    const nodes = [...document.querySelectorAll(`[data-evidence-id="${evidenceId}"]`)];
    return nodes.length === 1 && nodes[0].classList.contains("is-linked");
  }, source.id);
  await chip.click();
  const evidence = page.getByRole("dialog", { name: `Evidence ${source.id}` });
  await evidence.getByText("earnings.txt").waitFor();
  await evidence.getByText(/Source-level reference; no block locator supplied/).waitFor();
  await evidence.getByRole("link", { name: "Open full source" }).click();
  await page.waitForURL((url) => url.pathname.replace(/\/$/, "") === "/sources" && url.hash === `#source-${source.id}`);
  await evidence.waitFor({ state: "hidden" });
  await page.locator(`#source-${source.id}`).waitFor();

  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  const sourcePalette = page.getByRole("dialog", { name: "Command palette" });
  await sourcePalette.getByRole("combobox", { name: "Search cases, workflows or evidence IDs" }).fill(source.id);
  await sourcePalette.getByRole("option", { name: "Open source ID in this case" }).click();
  await page.waitForURL((url) => url.pathname.replace(/\/$/, "") === "/sources" && url.searchParams.get("source") === source.id);
  await page.locator(".source-register-row[aria-pressed=true]").getByText(source.id).waitFor();
  await page.evaluate(() => new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(resolve));
  }));
  assert.equal(await evidence.isVisible(), false, "same-route source query reopened after the drawer was closed");

  const sourceListURL = `${baseURL}/api/cases/${caseRecord.id}/sources`;
  const failedSourceList = (url) => url.href === sourceListURL;
  const failSourceList = (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: "not-json",
  });
  await page.route(failedSourceList, failSourceList);
  await page.goto(`${baseURL}/sources/?case=${caseRecord.id}&source=${source.id}`, { waitUntil: "networkidle" });
  await page.getByRole("alert").getByText("Unable to load this view.").waitFor();
  assert.equal(await page.getByRole("alert").getByText("Unable to load this view.").count(), 1, "one source-list failure was announced more than once");
  assert.equal(await page.getByText(/not in the active case source set/).count(), 0);
  assert.equal(await evidence.count(), 0, "failed source authority opened an evidence drawer");
  await page.unroute(failedSourceList, failSourceList);
  await page.reload({ waitUntil: "networkidle" });
  await page.locator(".source-register-row[aria-pressed=true]").getByText(source.id).waitFor();

  await page.setViewportSize({ width: 720, height: 900 });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  assert.equal(overflow, false, "workbench causes page-level horizontal overflow at reflow width");
  assert.deepEqual(errors, []);

  await page.goto(`${baseURL}/cases/?case=${caseRecord.id}`, { waitUntil: "networkidle" });
  const registerMeta = page.locator(".cases-register .panel-meta");
  const caseSearch = page.getByRole("searchbox", { name: "Search credits" });
  await caseSearch.fill("zzzz-no-such-issuer");
  await page.getByText("No credits match this search and filter.", { exact: true }).waitFor();
  assert.ok(
    (await registerMeta.innerText()).startsWith("0 of "),
    "case register count did not follow the search filter",
  );
  await page.getByRole("button", { name: "Reset filters" }).click();
  assert.equal(await caseSearch.inputValue(), "", "case filter recovery did not clear search");
  assert.equal(await page.getByRole("combobox", { name: "Authority" }).inputValue(), "all", "case filter recovery did not restore all authority states");
  await page.locator(".cases-register tbody tr").first().waitFor();
  const snapshotFilter = page.getByRole("combobox", { name: "Authority" });
  await snapshotFilter.selectOption("accepted");
  await page.locator(".cases-register tbody tr").first().waitFor();
  await snapshotFilter.selectOption("all");

  await page.goto(`${baseURL}/deep-dive/?case=${caseRecord.id}`, { waitUntil: "networkidle" });
  await page.setViewportSize({ width: 720, height: 900 });
  await page.getByRole("region", { name: "Visible authority" }).getByText(new RegExp(`Credit:\\s*${primaryIssuer}`)).waitFor();
  await page.getByRole("navigation", { name: "Accepted analysis modules" }).waitFor();
  assert.ok(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    "page overflows horizontally at 200% desktop zoom width",
  );
  await page.setViewportSize({ width: 1280, height: 720 });
  await context.close();

  const reduced = await browser.newContext({
    viewport: { width: 1024, height: 768 },
    reducedMotion: "reduce",
    extraHTTPHeaders: identityHeaders,
  });
  const reducedPage = await reduced.newPage();
  await reducedPage.goto(`${baseURL}/command-center/?case=${caseRecord.id}`, { waitUntil: "networkidle" });
  const reducedStyle = await reducedPage.evaluate(() => {
    const style = getComputedStyle(document.querySelector(".app-shell"));
    return { iterationCount: style.animationIterationCount, playState: style.animationPlayState };
  });
  assert.equal(reducedStyle.iterationCount, "1");
  assert.equal(reducedStyle.playState, "paused");
  await reduced.close();

  const zoomed = await browser.newContext({
    viewport: { width: 720, height: 900 },
    extraHTTPHeaders: identityHeaders,
  });
  const zoomedPage = await zoomed.newPage();
  await zoomedPage.goto(`${baseURL}/deep-dive/?case=${caseRecord.id}`, { waitUntil: "networkidle" });
  // A palette route whose client payload 404s degrades into a full document load, but only
  // after the router has pushed the destination URL. `waitForURL` then resolves on that
  // pushed entry and the following `goto` races the fallback load, which cancels it.
  const zoomedDocumentLoads = [];
  zoomedPage.on("request", (requestValue) => {
    if (requestValue.isNavigationRequest()) zoomedDocumentLoads.push(requestValue.url());
  });
  await zoomedPage.getByRole("button", { name: "Open command palette" }).click();
  const zoomedPalette = zoomedPage.getByRole("dialog", { name: "Command palette" });
  await zoomedPalette.getByRole("combobox", { name: "Search cases, workflows or evidence IDs" }).fill("Portfolio");
  await zoomedPalette.getByRole("option", { name: "Open Portfolio" }).click();
  await zoomedPage.waitForURL((url) => url.pathname.replace(/\/$/, "") === "/cases" && url.searchParams.get("case") === caseRecord.id);
  await zoomedPage.getByRole("button", { name: "Open command palette" }).click();
  await zoomedPalette.getByRole("combobox", { name: "Search cases, workflows or evidence IDs" }).fill("Run");
  await zoomedPalette.getByRole("option", { name: "Open Run", exact: true }).click();
  await zoomedPage.waitForURL((url) => url.pathname.replace(/\/$/, "") === "/run-console"
    && url.searchParams.get("case") === caseRecord.id
    && url.searchParams.get("run") === nextRun.id);
  assert.deepEqual(zoomedDocumentLoads, [], "command palette navigation fell back to a full document load");
  await zoomedPage.goto(`${baseURL}/report-studio/?case=${caseRecord.id}`, { waitUntil: "networkidle" });
  assert.equal(await zoomedPage.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth), false, "Report Studio causes page-level horizontal overflow at 200% desktop zoom width");

  await zoomed.close();

  // Reader mode: same subject, same case standing, READER role. Every shared
  // write the server answers 403 to must be absent from the surface.
  const readerHeaders = process.env.CAOS_EDGE_SECRET
    ? { ...identityHeaders, "x-forwarded-groups": "caos-reader" }
    : { "x-caos-role": "READER" };
  const reader = await browser.newContext({ viewport: { width: 1440, height: 1000 }, extraHTTPHeaders: readerHeaders });
  const readerPage = await reader.newPage();
  const absent = async (page, name) => assert.equal(
    await page.getByRole("button", { name }).count(), 0, `READER was offered "${name}"`);

  await readerPage.goto(`${baseURL}/cases/?case=${caseRecord.id}`, { waitUntil: "networkidle" });
  assert.equal(await readerPage.evaluate(() => document.querySelector("main")?.textContent?.includes("Reader access")), true,
    "Cases did not say why the write panels are absent");
  await absent(readerPage, "Create case");
  assert.ok(await readerPage.getByRole("row").count() > 1, "READER lost read access to the case register");

  await readerPage.goto(`${baseURL}/sources/?case=${caseRecord.id}`, { waitUntil: "networkidle" });
  await absent(readerPage, "Upload and version");
  assert.equal(await readerPage.locator("main input[type=file]").count(), 0, "READER was offered a source file input");

  await readerPage.goto(`${baseURL}/run-console/?case=${raceCase.id}&run=${crossCaseRun.id}`, { waitUntil: "networkidle" });
  await absent(readerPage, "Compile and run");
  await absent(readerPage, "Accept analytical snapshot");
  await readerPage.getByText("Acceptance is an analyst action.", { exact: true }).waitFor();
  assert.equal(await readerPage.locator("#pathway").count(), 0, "READER was offered the compile form");

  await readerPage.goto(`${baseURL}/rv-screener/?case=${caseRecord.id}`, { waitUntil: "networkidle" });
  await absent(readerPage, "Upload CP-3 workbook");

  // The gate must fail closed even when /api/me never answers successfully.
  await readerPage.route((url) => url.pathname === "/api/me", (route) => route.abort("failed"));
  await readerPage.goto(`${baseURL}/cases/?case=${caseRecord.id}`, { waitUntil: "networkidle" });
  await readerPage.waitForTimeout(500);
  await absent(readerPage, "Create case");
  await absent(readerPage, "Upload and version");
  assert.equal(await readerPage.locator("main input[type=file]").count(), 0,
    "an unresolved identity left a write control on the page");
  assert.equal(await readerPage.evaluate(() => document.querySelector("main")?.textContent?.includes("Reader access")), true,
    "a failed identity lookup did not settle on the read-only floor");
  await reader.close();
} finally {
  await browser.close();
  await api.dispose();
}
