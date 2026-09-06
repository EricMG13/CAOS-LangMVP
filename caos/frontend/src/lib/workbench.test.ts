import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { acceptanceSlotSummary, acceptedAuthorityMatch, destinationFromSlug, destinationMeta, evidenceKind, forwardedRoutes, formatBlockLocator, humanizeCode, moduleLabel, protectDirtyDraftUnload, routeDestinations, routeFor, routeSlugs, supersededAcceptance, withQuery, workflows } from "./workbench.ts";

const workbenchShell = readFileSync(new URL("../components/WorkbenchShell.tsx", import.meta.url), "utf8");
const workspace = readFileSync(new URL("../components/Workspace.tsx", import.meta.url), "utf8");
const states = readFileSync(new URL("../components/states.tsx", import.meta.url), "utf8");
const modelBuilder = readFileSync(new URL("../components/model/ModelBuilder.tsx", import.meta.url), "utf8");
const deliverableDocument = readFileSync(new URL("../components/report/DeliverableDocument.tsx", import.meta.url), "utf8");
const reportStudio = readFileSync(new URL("../components/report/ReportStudio.tsx", import.meta.url), "utf8");
const styles = readFileSync(new URL("../../app/globals.css", import.meta.url), "utf8");
const smoke = readFileSync(new URL("../../scripts/workbench-smoke.mjs", import.meta.url), "utf8");
const destinationPage = readFileSync(new URL("../../app/[destination]/page.tsx", import.meta.url), "utf8");
const notFoundPage = readFileSync(new URL("../../app/not-found.tsx", import.meta.url), "utf8");
const a11y = readFileSync(new URL("../../scripts/a11y-axe.mjs", import.meta.url), "utf8");

function shippedFiles(root: URL): URL[] {
  try {
    return readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
      if (entry.name === ".next" || entry.name === "node_modules") return [];
      const file = new URL(`${entry.name}${entry.isDirectory() ? "/" : ""}`, root);
      if (entry.isDirectory()) return shippedFiles(file);
      return /\.(?:test|spec)\.[^.]+$/.test(entry.name) ? [] : [file];
    });
  } catch (error) {
    if (error && typeof error === "object" && "code" in error && error.code === "ENOENT") return [];
    throw error;
  }
}

test("all shipped frontend files have no Google-hosted font dependency", () => {
  const frontendRoot = new URL("../../", import.meta.url);
  const files = ["app/", "src/", "public/"].flatMap((directory) => shippedFiles(new URL(directory, frontendRoot)));
  files.push(new URL("next.config.js", frontendRoot));
  const forbidden = /next\/font\/google|fonts\.googleapis\.com|fonts\.gstatic\.com/;
  const violations = files.filter((file) => forbidden.test(readFileSync(file, "utf8"))).map((file) => file.pathname.slice(frontendRoot.pathname.length));
  assert.deepEqual(violations, []);
});

test("browser proof watches every context for Google font requests through final cleanup", () => {
  const contexts = smoke.match(/browser\.newContext\(/g)?.length || 0;
  const watchedContexts = smoke.match(/watchExternalGoogleFonts\(await browser\.newContext\(/g)?.length || 0;
  assert.equal(watchedContexts, contexts);
  assert.equal(smoke.match(/assert\.deepEqual\(externalGoogleFontRequests, \[\]/g)?.length, 1);
  // The font assertion is the last check of the journey; only the structured
  // report (WEB-002) may follow it before the failure handler and the cleanup.
  assert.match(smoke, /await reader\.close\(\);\s*assert\.deepEqual\(externalGoogleFontRequests, \[\], "workbench requested an external Google font"\);\s*report\(\{ status: "passed" \}\);\s*} catch \(error\) \{[\s\S]*?} finally/);
});

test("the rail's words are the route slugs, and every rail href is derived from the destination table", () => {
  // Align (FE-A1 D1): one vocabulary in URL, rail, kicker, page title and tab title.
  assert.deepEqual(routeDestinations.map(([slug, destination]) => [slug, destination]), [
    ["portfolio", "Portfolio"],
    ["credit", "Credit"],
    ["sources", "Sources"],
    ["analysis", "Analysis"],
    ["run", "Run"],
    ["market", "Market"],
    ["model", "Model"],
    ["report", "Report"],
    ["admin", "Admin"],
  ]);
  assert.deepEqual(workflows.map(({ label, href }) => [label, href]), [
    ["Portfolio", "/portfolio"],
    ["Credit", "/credit"],
    ["Sources", "/sources"],
    ["Analysis", "/analysis"],
    ["Market", "/market"],
    ["Model", "/model"],
    ["Report", "/report"],
  ]);
  // The route set is a pure function of the destination table: a rail entry and a
  // tool link carry the slug of the destination they open, never a second literal.
  for (const workflow of workflows) {
    assert.equal(workflow.href, routeFor(workflow.destinations[0]));
    for (const tool of workflow.tools ?? []) assert.equal(tool.href, routeFor(tool.destination));
  }
  assert.deepEqual(workflows.flatMap((workflow) => workflow.tools ?? []), [{ label: "Run", href: "/run", destination: "Run" }]);
  assert.equal(routeFor("Admin"), "/admin");
  assert.deepEqual(Object.entries(destinationMeta).map(([destination, meta]) => [destination, meta.kicker]), [
    ["Portfolio", "Portfolio / Surveillance"],
    ["Credit", "Credit / Current state"],
    ["Sources", "Sources / Evidence"],
    ["Analysis", "Analysis / Reader"],
    ["Run", "Analysis / Run"],
    ["Market", "Market / Comparison"],
    ["Model", "Model / Forecast"],
    ["Report", "Report / Publication"],
    ["Admin", "Admin / Governance"],
  ]);
  // The tab title is the destination word on a document load and after a client
  // navigation alike; before the move the two disagreed.
  assert.match(destinationPage, /title: known \? `CAOS — \$\{destinationFromSlug\(destination\)\}`/);
  assert.match(workspace, /document\.title = `CAOS — \$\{active\}`;/);
});

test("every pre-Align slug is a static forwarding page to its destination, and the static route set is one declaration", () => {
  // FE-A1 D2: a static export cannot serve redirects, so each old slug stays a page
  // that replaces history to its new home with the query string intact.
  assert.deepEqual(forwardedRoutes.map(([from, to]) => [from, to]), [
    ["cases", "portfolio"],
    ["command-center", "credit"],
    ["deep-dive", "analysis"],
    ["run-console", "run"],
    ["rv-screener", "market"],
    ["model-builder", "model"],
    ["report-studio", "report"],
    ["admin-studio", "admin"],
  ]);
  const destinationSlugs: readonly string[] = routeDestinations.map(([slug]) => slug);
  for (const [from, to] of forwardedRoutes) {
    assert.ok(destinationSlugs.includes(to), `${from} forwards to ${to}, which is not a destination`);
    assert.ok(!destinationSlugs.includes(from), `${from} is both a forwarder and a destination`);
    assert.equal(destinationFromSlug(from), destinationFromSlug(to));
  }
  assert.deepEqual(routeSlugs, [...destinationSlugs, ...forwardedRoutes.map(([from]) => from)]);
  assert.equal(destinationFromSlug("nowhere"), null);
  // generateStaticParams emits exactly routeSlugs; a forwarded slug renders the
  // forwarder and nothing else, and an unknown slug is still the 404.
  assert.match(destinationPage, /return routeSlugs\.map\(\(destination\) => \(\{ destination \}\)\);/);
  assert.match(destinationPage, /const forward = forwardedSlug\(destination\);[\s\S]*if \(forward\) return <RouteForwarder to=\{`\/\$\{forward\}\/`\} \/>;/);
  assert.match(destinationPage, /if \(destinationFromSlug\(destination\) === null\) notFound\(\);/);
  assert.match(notFoundPage, /href="\/portfolio\/">Return to Portfolio</);
  // The forwarder replaces history (never pushes) and carries the query and hash.
  const forwarder = readFileSync(new URL("../components/RouteForwarder.tsx", import.meta.url), "utf8");
  assert.match(forwarder, /window\.history\.replaceState\(historyStateForExternalReplace\(window\.history\.state\), "", `\$\{to\}\$\{window\.location\.search\}\$\{window\.location\.hash\}`\)/);
  assert.doesNotMatch(forwarder, /router\.(?:push|replace)\(|history\.pushState\(/);
  // The accessibility sweep and the smoke walk the same declaration: every destination
  // and every forwarder is swept, and the sweep asserts where each forwarder lands.
  assert.match(a11y, /import \{ destinationFromSlug, forwardedRoutes, routeDestinations \} from "\.\.\/src\/lib\/workbench\.ts";/);
  assert.match(a11y, /const routes = \[\.\.\.routeDestinations, \.\.\.forwardedRoutes\]\.map\(\(\[slug\]\) => `\/\$\{slug\}\/`\);/);
  for (const [from] of forwardedRoutes) assert.doesNotMatch(workspace + workbenchShell + modelBuilder + reportStudio, new RegExp(`"/${from}[/"?]`), `a link still targets the forwarded slug /${from}/`);
});

test("the compile form collapses into 'Advanced: compile a route' on an intake-created run (FE-A1 D11)", () => {
  // The "Align — Analysis paused" artboard: the execution route and its one primary
  // lead; the compile form is a closed disclosure at the bottom. Only the intake
  // record can say a run came from intake, so Run reads it too.
  assert.match(workspace, /if \(!hydrated \|\| !caseId \|\| \(active !== "Portfolio" && active !== "Run"\) \|\| !latestIntakeId\) return;/);
  assert.match(workspace, /<RunConsole fromIntake=\{Boolean\(run && intake\?\.case_id === caseId && intake\.run\?\.id === run\.id\)\}/);
  const runConsole = workspace.slice(workspace.indexOf("function RunConsole("), workspace.indexOf("function ResearchPlanView("));
  assert.match(runConsole, /\{!fromIntake \? <section className="panel span-4">\s*<div className="panel-header"><h2>Compile route<\/h2>/);
  assert.match(runConsole, /<section className=\{`panel \$\{fromIntake \? "span-12" : "span-8"\}`\}>\s*<div className="panel-header"><h2>Execution route<\/h2>/);
  assert.match(runConsole, /\{fromIntake \? <details className="panel run-advanced span-12">\s*<summary>Advanced: compile a route<\/summary>\s*<div className="panel-body flow">\{compileForm\}<\/div>\s*<\/details> : null\}/);
  // One form in both homes: the disclosure carries the same form and the same
  // "Compile and run" action, so the compile pins keep holding on a hand-compiled run.
  assert.equal(runConsole.match(/\{compileForm\}/g)?.length, 2);
  assert.equal(runConsole.match(/"Compile and run"/g)?.length, 1);
  assert.match(styles, /\.run-advanced > summary \{[^}]*cursor: pointer/);
  // Browser proof: the intake-created Deep Research run pauses on plan approval with
  // the form closed and exactly one visible primary.
  assert.match(smoke, /details\.run-advanced/);
  assert.match(smoke, /an intake-created run still leads with the compile form/);
});

test("Admin draws the two served governance contracts and Report no longer provisions (FE-A1 D7)", () => {
  const admin = workspace.slice(workspace.indexOf("function AdminView("), workspace.indexOf("function AdminView(") + 9000);
  assert.match(admin, /\["Audit package", "Hash-chained case audit package \(GET \/api\/cases\/\{case_id\}\/audit-package\); download below", "served"\]/);
  assert.match(admin, /\["Membership", "Identity-to-case role assignments \(POST \/api\/cases\/\{case_id\}\/members\); provisioned below", "served"\]/);
  for (const row of ["Bundle integrity", "Audit rows", "Step-up"]) assert.match(admin, new RegExp(`\\["${row}", "[^"]+", "absent"\\]`));
  assert.match(admin, /networkFetch\(`\/api\/cases\/\$\{caseId\}\/audit-package`\)/);
  assert.match(admin, /response\.headers\.get\("x-caos-sha256"\)/);
  assert.match(admin, /if \(response\.status === 404\) \{ if \(action === downloadGeneration\.current\) setDownload\(\{ state: "unavailable" \}\); return; \}/);
  // Provisioning keeps the filing rule: current APPROVER/ADMIN role and stored case standing.
  assert.match(admin, /const canProvision = \(role === "APPROVER" \|\| role === "ADMIN"\) && \["APPROVER", "ADMIN"\]\.includes\(selectedCase\?\.members\?\.\[subject\] \?\? ""\);/);
  assert.match(admin, /: canProvision \? <form className="opinion-form" data-member-form/);
  assert.match(admin, /<option value="APPROVER">APPROVER<\/option><option value="ADMIN">ADMIN<\/option>/);
  // A reader sees the reason, never the control (UX-015); a writer without standing sees the rule.
  assert.match(admin, /\{writeAccess !== "yes" \? <WriteBlocked access=\{writeAccess\} action="member provisioning" \/>/);
  assert.match(admin, /Provisioning a member needs a current APPROVER or ADMIN role and stored APPROVER or ADMIN standing on this case\./);
  // The mutation is the workspace's governed write with its receipt and a case re-read.
  assert.match(workspace, /const provisionMember = async \(member: \{ subject: string; role: string \}\) => \{/);
  assert.match(workspace, /await request\(`\/api\/cases\/\$\{expectedCaseId\}\/members`, \{ method: "POST", body: JSON\.stringify\(\{ subject: memberSubject, role: member\.role \}\) \}\);/);
  assert.match(workspace, /setNotice\(`\$\{memberSubject\} provisioned as case \$\{member\.role\}\.`\);[\s\S]{0,400}?void refreshCase\(expectedCaseId\);\s*return true;/);
  assert.doesNotMatch(reportStudio, /data-member-form|\/members`/);
  // Browser proof: the audit package is driven live with its digest; provisioning is
  // proven on a route-intercepted page (no served route grants the first standing, F-12).
  assert.match(smoke, /"Download audit package"/);
  assert.match(smoke, /provisioned as case APPROVER\./);
  assert.match(smoke, /READER was offered "Provision member"|absent\(readerPage, "Provision member"\)/);
});

test("the ambiguous-issuer refusal points at the advanced path (FE-A1 D10)", () => {
  const intake = workspace.slice(workspace.indexOf("function IntakePanel("), workspace.indexOf("function IntakeEvidence("));
  assert.match(intake, /\{refusal\.code === "INTAKE_ISSUER_AMBIGUOUS" \? <p>Advanced path for a pack whose documents name one issuer differently: <a href="#cases-create">create the case<\/a>, upload each document on \{selectedCase \? <Link href=\{withQuery\("\/sources", \{ case: selectedCase\.id \}\)\}>Sources<\/Link> : "Sources"\}, then compile from \{selectedCase \? <Link href=\{withQuery\("\/run", \{ case: selectedCase\.id \}\)\}>Run<\/Link> : "Run"\}\.<\/p> : null\}/);
  assert.match(workspace, /<section className="panel cases-create" id="cases-create">/);
  // The intake surface still posts files and nothing else: no new field.
  assert.equal(intake.match(/<input /g)?.length, 2);
  assert.match(smoke, /INTAKE_ISSUER_AMBIGUOUS/);
});

test("the palette offers every destination once, under its rail word, at its route", () => {
  // The palette derives from `workflows`: one "Open <word>" per rail entry plus one
  // per tool, and nothing else — no entry for a route the table does not declare.
  assert.match(workbenchShell, /const workflowItems = useMemo\(\(\) => workflows\.filter\(/);
  assert.match(workbenchShell, /const toolItems = useMemo\(\(\) => workflows\.flatMap\(\(workflow\) => workflow\.tools \?\? \[\]\)/);
  assert.deepEqual([
    ...workflows.map((workflow) => [`Open ${workflow.label}`, workflow.href]),
    ...workflows.flatMap((workflow) => workflow.tools ?? []).map((tool) => [`Open ${tool.label}`, tool.href]),
  ], [
    ["Open Portfolio", "/portfolio"],
    ["Open Credit", "/credit"],
    ["Open Sources", "/sources"],
    ["Open Analysis", "/analysis"],
    ["Open Market", "/market"],
    ["Open Model", "/model"],
    ["Open Report", "/report"],
    ["Open Run", "/run"],
  ]);
});

test("exactly one rail entry is current, and the Run tool renders on every surface", () => {
  // FE-A1 D12 (F-15): the tool group is no longer gated on the active workflow. The
  // aria-current rule keys on destinations: a tool link when one targets the active
  // destination, the governance entry on Admin, else the workflow link.
  assert.doesNotMatch(workbenchShell, /activeWorkflow\.tools\?\.length \?/);
  assert.match(workbenchShell, /\{workflows\.filter\(\(workflow\) => workflow\.tools\?\.length\)\.map\(\(workflow\) => <nav aria-label=\{`\$\{workflow\.label\} tools`\}/);
  assert.match(workbenchShell, /&& !activeWorkflow\.tools\?\.some\(\(tool\) => tool\.destination === active\)\s*&& active !== "Admin";/);
  assert.match(workbenchShell, /aria-current=\{active === tool\.destination \? "page" : undefined\}/);
  assert.match(workbenchShell, /aria-current=\{active === "Admin" \? "page" : undefined\} href=\{workflowHref\(routeFor\("Admin"\)\)\}/);
  assert.match(workbenchShell, /tool\.destination === "Run" && runIsLive && <span className="shortcut">LIVE/);
  assert.doesNotMatch(workbenchShell, /"Admin Studio"|"Run Console"|"Report Studio"|"\/admin-studio"|"\/cases"/);
  // The browser proof: one aria-current per page on a workflow route, the tool route
  // and the governance route, and the Run tool present on a non-Analysis surface.
  assert.match(smoke, /\["\/portfolio\/", "Workflows", "Portfolio"\],\s*\["\/run\/", "Analysis tools", "Run"\],\s*\["\/report\/", "Workflows", "Report"\],\s*\["\/admin\/", "Governance", "Admin"\],/);
  assert.match(smoke, /the Run tool is missing from a non-Analysis surface/);
});

test("no surface interior names the old destination as a place (FE-G3, one vocabulary end to end)", () => {
  // DECISIONS §14.23 / the Align record: one word in the URL, the rail, the palette,
  // the kicker and the tab. FE-G2 aligned the chrome and handed the panel interiors
  // to FE-G3: a heading, a load error or a discard prompt that still says "Model
  // Builder" or "Report Studio" is the pre-IA interior on a surface whose kicker
  // says Model or Report.
  const oldNames = /Model Builder|Report Studio|Run Console|Command Center|Deep[- ]Dive|RV Screener|Admin Studio/;
  for (const source of [modelBuilder, reportStudio, workbenchShell, workspace]) {
    const offending = source.split("\n").find((line) => !/^\s*(\/\/|\*|\/\*)/.test(line) && oldNames.test(line));
    assert.equal(offending, undefined);
  }
  assert.match(modelBuilder, /<h2>Model<\/h2>/);
  assert.match(modelBuilder, /"Unable to load Model\."/);
  assert.match(reportStudio, /title="Unable to load Report\."/);
  assert.match(reportStudio, /"Discard the unsaved draft before changing pathway\?"/);
});

test("the shell omits the redundant reading taxonomy and renders its command shortcut as a key", () => {
  assert.ok(Object.values(destinationMeta).every((meta) => !("reading" in meta)));
  assert.doesNotMatch(workbenchShell, /Reading:/);
  assert.match(workbenchShell, /Command <kbd aria-hidden="true">⌘K<\/kbd>/);
});

test("navigation and data captions use the four-role label taxonomy", () => {
  assert.equal(workbenchShell.match(/className="nav-label palette-group-label"/g)?.length, 3);
  assert.doesNotMatch(styles, /\.palette-group-label\s*\{[^}]*text-transform/);
  assert.match(workbenchShell, /<dt className="meta-label">Source ID<\/dt>/);
  assert.doesNotMatch(styles, /\.state-block dt\s*\{/);
  assert.match(reportStudio, /report-authority-strip"><div><span className="meta-label">Model authority<\/span>/);
  assert.doesNotMatch(styles, /\.report-authority-strip div > span\s*\{/);
  assert.match(workspace, /analysis-provenance"><dt className="meta-label">Artifact<\/dt>/);
  assert.match(workspace, /loan-authority"><dl><dt className="meta-label">Workbook date<\/dt>/);
  assert.doesNotMatch(styles, /[^{}]*\bdt\b[^{}]*\{[^{}]*(?:letter-spacing|text-transform)/);
});

test("Cases makes opening the selected credit primary and keeps portfolio limits secondary", () => {
  const register = workspace.slice(workspace.indexOf('className="panel cases-register"'), workspace.indexOf('className="panel cases-create"'));
  assert.match(register, /<tr aria-current=\{caseId === item\.id \? "true" : undefined\}/);
  assert.match(register, /className="button small primary"[^>]*>Open credit/);
  assert.match(register, /className="button primary"[^>]*>Reset filters/);
  assert.ok(workspace.indexOf('id="portfolio-contract-title"') > workspace.indexOf('className="panel cases-fit"'), "portfolio limitation did not follow the primary work");
});

test("RV keeps core filters visible and discloses retained advanced bounds", () => {
  const screener = workspace.slice(workspace.indexOf('className="panel span-12"><div className="panel-header"><h2>Loan screener'));
  const advanced = screener.slice(screener.indexOf('<details className="loan-advanced-filters">'), screener.indexOf('</details>'));
  for (const id of ["loan-maturity-from", "loan-maturity-to", "loan-margin-min", "loan-margin-max", "loan-dm-min", "loan-dm-max"]) assert.match(advanced, new RegExp(id));
  assert.match(screener, /<caption className="sr-only">27 columns\. Scroll horizontally to review all workbook fields; column labels state source units\.<\/caption>/);
});

test("draft navigation uses one focus-returning native dialog and preserves beforeunload", () => {
  assert.doesNotMatch(workspace, /window\.confirm/);
  assert.doesNotMatch(reportStudio, /window\.confirm/);
  assert.match(workspace, /function DraftDiscardDialog/);
  assert.match(workspace, /dialog\.addEventListener\("cancel", cancel\)/);
  // The unload guard's behaviour, not its presence: a dirty draft cancels the
  // event and sets the legacy returnValue; a clean one touches nothing. The
  // wiring is driven in the smoke with a synthetic beforeunload on the window.
  const dirtyEvent = { prevented: false, preventDefault() { this.prevented = true; }, returnValue: "unchanged" };
  assert.equal(protectDirtyDraftUnload(dirtyEvent, true), true);
  assert.deepEqual({ prevented: dirtyEvent.prevented, returnValue: dirtyEvent.returnValue }, { prevented: true, returnValue: "" });
  const cleanEvent = { prevented: false, preventDefault() { this.prevented = true; }, returnValue: "unchanged" };
  assert.equal(protectDirtyDraftUnload(cleanEvent, false), false);
  assert.deepEqual({ prevented: cleanEvent.prevented, returnValue: cleanEvent.returnValue }, { prevented: false, returnValue: "unchanged" });
  assert.doesNotMatch(workspace, /history\.replaceState\(null/);
  assert.equal(workspace.match(/historyStateForExternalReplace\(window\.history\.state\)/g)?.length, 2);
  assert.match(workspace, /requestDraftDiscard/);
  assert.match(workspace, /if \(discardPromptRef\.current\) \{ cancel\?\.\(\); return false; \}/);
  assert.match(workspace, /if \(state\?\.caosModelDraftGuard \|\| state\?\.caosReportDraftGuard\) \{ modelHistoryGuardRef\.current = true; return; \}/);
  const finish = workspace.slice(workspace.indexOf("const finishDraftDiscard"), workspace.indexOf("const commitCaseSelection"));
  assert.doesNotMatch(finish, /(?:model|report)DraftDirtyRef\.current = false|modelHistoryGuardRef\.current = false/);
  assert.match(reportStudio, /useEffect\(\(\) => \(\) => onDraftStateChange\(false\), \[onDraftStateChange\]\)/);
  assert.match(workbenchShell, /document\.querySelector\("dialog\[open\]"\)/);
  for (const proof of ["modified dirty link was intercepted", "dirty same-route confirmation dropped protection", "command shortcut opened a nested modal", "dirty pathway cancel changed pathway", "dirty pathway confirm did not change pathway", "confirming browser history did not traverse exactly one boundary"]) assert.match(smoke, new RegExp(proof));
});

test("draft link interception accepts only an unmodified primary same-tab gesture", async () => {
  const workbenchModule = await import("./workbench.ts") as unknown as { isSameTabPrimaryGesture?: (event: { button: number; metaKey: boolean; ctrlKey: boolean; shiftKey: boolean; altKey: boolean }, target?: string) => boolean };
  assert.equal(typeof workbenchModule.isSameTabPrimaryGesture, "function");
  const gesture = { button: 0, metaKey: false, ctrlKey: false, shiftKey: false, altKey: false };
  assert.equal(workbenchModule.isSameTabPrimaryGesture?.(gesture), true);
  for (const change of [
    { button: 1 },
    { metaKey: true },
    { ctrlKey: true },
    { shiftKey: true },
    { altKey: true },
  ]) assert.equal(workbenchModule.isSameTabPrimaryGesture?.({ ...gesture, ...change }), false, JSON.stringify(change));
  assert.equal(workbenchModule.isSameTabPrimaryGesture?.(gesture, "_blank"), false);
  assert.equal(workbenchModule.isSameTabPrimaryGesture?.(gesture, "_self"), true);
  assert.equal(workbenchModule.isSameTabPrimaryGesture?.(gesture, "_SELF"), true);
});

test("discard resolution invokes one deferred callback without changing caller-owned protection", async () => {
  const workbenchModule = await import("./workbench.ts") as unknown as { resolveDraftDiscard?: (request: { confirm: () => void; cancel?: () => void }, confirmed: boolean) => void };
  assert.equal(typeof workbenchModule.resolveDraftDiscard, "function");
  const protectedDraft = true;
  let confirms = 0;
  let cancels = 0;
  const request = { confirm: () => { confirms += 1; }, cancel: () => { cancels += 1; } };
  workbenchModule.resolveDraftDiscard?.(request, true);
  assert.deepEqual({ protectedDraft, confirms, cancels }, { protectedDraft: true, confirms: 1, cancels: 0 });
  workbenchModule.resolveDraftDiscard?.(request, false);
  assert.deepEqual({ protectedDraft, confirms, cancels }, { protectedDraft: true, confirms: 1, cancels: 1 });
});

test("external history writes preserve application state without bypassing Next URL restore", async () => {
  const workbenchModule = await import("./workbench.ts") as unknown as { historyStateForExternalReplace?: (state: unknown) => Record<string, unknown> };
  assert.equal(typeof workbenchModule.historyStateForExternalReplace, "function");
  if (!workbenchModule.historyStateForExternalReplace) return;
  const tree = { segment: "report-studio" };
  const state = workbenchModule.historyStateForExternalReplace({
    __NA: true,
    _N: true,
    __PRIVATE_NEXTJS_INTERNALS_TREE: tree,
    caosDraftHistoryEntryId: "sentinel",
    caosDraftHistoryBaseId: "base",
  });
  assert.deepEqual(state, {
    __PRIVATE_NEXTJS_INTERNALS_TREE: tree,
    caosDraftHistoryEntryId: "sentinel",
    caosDraftHistoryBaseId: "base",
  });
  assert.deepEqual(workbenchModule.historyStateForExternalReplace(null), {});
});

test("Workspace settles history moves only at their tagged destination entry", () => {
  assert.match(workspace, /historyTraversalRef/);
  assert.match(workspace, /beginDraftHistoryTraversal/);
  assert.match(workspace, /observeDraftHistoryPop\(activeTraversal, event\.state\)/);
  assert.match(workspace, /draftHistoryEntryId\(window\.history\.state\) !== activeTraversal\.expectedDestinationId/);
  assert.match(workspace, /caosDraftHistorySentinelId/);
  assert.match(workspace, /protectDirtyDraftUnload\(event, modelDraftDirtyRef\.current \|\| reportDraftDirtyRef\.current\)/);
  assert.doesNotMatch(workspace, /isConfirmedDraftHistoryTraversal/);
  assert.doesNotMatch(workspace, /historyGuardRetiringRef|historyGuardRearmRef|suppressNextModelHistoryPopRef|confirmedHistoryPopRef/);
});

test("DAG nodes use neutral containers and shape-coded visible statuses", async () => {
  const workbench = await import("./workbench.ts") as unknown as { nodeStatusTone?: (status: string) => string };
  for (const [status, tone] of [
    ["pending", "idle"],
    ["ready", "idle"],
    ["running", "running"],
    ["blocked", "warning"],
    ["cancelled", "warning"],
    ["failed", "critical"],
    ["succeeded", "success"],
  ]) assert.equal(workbench.nodeStatusTone?.(status), tone, status);
  assert.doesNotMatch(styles, /\.dag-node\.(?:succeeded|running|failed)\s*\{/);
  assert.doesNotMatch(workspace, /className=\{`dag-node \$\{node\.status\}`\}/);
  assert.match(workspace, /className=\{`status \$\{nodeStatusTone\(node\.status\)\}`\}>\{node\.status\}<\/div>/);
  assert.match(workspace, /dag-node-open dag-node-placeholder" aria-hidden="true">Open output/, "unfinished DAG nodes must reserve the completed-output row");
  // Severity is shape plus hue, never hue alone: every tone's glyph rule draws a
  // distinct shape, so removing one (colour-only status) fails here rather than
  // passing on the presence of a selector (FE-A0 §4, M8).
  const glyph = (tone: string) => {
    const rule = new RegExp(`\\.status\\.${tone}::before\\s*\\{([^}]*)\\}`).exec(styles);
    assert.ok(rule, `no glyph rule for .status.${tone}`);
    assert.doesNotMatch(rule[1], /content:\s*none/, `${tone} glyph removed`);
    return rule[1];
  };
  assert.match(glyph("success"), /border-radius:\s*50%/);
  assert.match(glyph("success"), /background:\s*var\(--caos-success\)/);
  assert.match(glyph("running"), /border-radius:\s*50%/);
  assert.match(glyph("running"), /background:\s*var\(--caos-accent\)/);
  assert.match(glyph("warning"), /border-bottom:\s*8px solid var\(--caos-warning\)/);
  assert.match(glyph("critical"), /border-radius:\s*2px/);
  assert.match(glyph("critical"), /background:\s*var\(--caos-critical\)/);
  assert.match(styles, /\.status::before, \.status\.idle::before\s*\{[^}]*width: 8px; height: 3px/);
});

test("no shipped frontend file carries an HTML or script sink", () => {
  // WEB-012. The per-component pins covered DeliverableDocument and Report Studio
  // only; a raw-HTML sink in the artifact reader or the shell passed every test
  // (FE-A0 §4, M9). Every shipped file under app/ and src/ is scanned.
  const frontendRoot = new URL("../../", import.meta.url);
  const files = ["app/", "src/"].flatMap((directory) => shippedFiles(new URL(directory, frontendRoot)));
  const forbidden = /dangerouslySetInnerHTML|\.innerHTML\s*=|\.outerHTML\s*=|insertAdjacentHTML|srcdoc|\beval\(|new Function\(|javascript:/;
  const violations = files.filter((file) => forbidden.test(readFileSync(file, "utf8"))).map((file) => file.pathname.slice(frontendRoot.pathname.length));
  assert.deepEqual(violations, []);
});

test("every custom property the stylesheets read is declared on :root", () => {
  // An undefined var() is invalid at computed-value time and the declaration
  // silently inherits: masthead fact values rendered in label grey because the
  // rule read `--caos-paper-ink` where the token is `--caos-ink` (FE-A2 F-11).
  const moduleStyles = readFileSync(new URL("../components/model/ModelBuilder.module.css", import.meta.url), "utf8");
  const declared = new Set([...styles.matchAll(/^\s*(--[a-z0-9-]+)\s*:/gm)].map((match) => match[1]));
  const read = new Set([...`${styles}\n${moduleStyles}`.matchAll(/var\((--[a-z0-9-]+)/g)].map((match) => match[1]));
  assert.deepEqual([...read].filter((token) => !declared.has(token)), []);
});

test("a pressed toggle button is visibly distinct from its siblings", () => {
  // Base/Downside and the tornado swing set aria-pressed and `is-active` on
  // `.button.small`; without this rule the pressed toggle looked identical to the
  // others (FE-A2 F-01).
  const rule = /\.button\.is-active\s*\{([^}]*)\}/.exec(styles);
  assert.ok(rule, "no .button.is-active rule");
  assert.match(rule[1], /border-color:/);
  assert.match(rule[1], /background:/);
  assert.match(modelBuilder, /"button small is-active"/);
});

test("the report panels' header row takes the header's own height", () => {
  // A fixed 32px row under a 46px min-height header overlapped the body by 14px (FE-A2 F-12).
  const rule = /\.report-outline, \.report-compose\s*\{([^}]*)\}/.exec(styles);
  assert.ok(rule, "no .report-outline/.report-compose rule");
  assert.match(rule[1], /grid-template-rows:\s*auto minmax\(0, 1fr\)/);
});

test("every route path keeps its trailing slash", () => {
  assert.equal(withQuery("/run", { case: "case_1" }), "/run/?case=case_1");
  assert.equal(withQuery("/sources/", { case: "case_1" }), "/sources/?case=case_1");
  assert.equal(withQuery("/portfolio", {}), "/portfolio/");
  assert.equal(withQuery("/", {}), "/");
});

test("values set, replace, and clear query keys", () => {
  assert.equal(withQuery("/run?run=run_old", { run: "run_new" }), "/run/?run=run_new");
  assert.equal(withQuery("/run?run=run_old", { run: undefined }), "/run/");
  assert.equal(withQuery("/run?case=case_1", { run: "run_1" }), "/run/?case=case_1&run=run_1");
});

test("acceptance stays live until the run's snapshot is the case authority", () => {
  assert.equal(acceptedAuthorityMatch(null, "", "snap_a"), "", "an unaccepted run offers the action");
  assert.equal(acceptedAuthorityMatch(undefined, undefined, undefined), "", "no authority, no aftermath");
  assert.equal(acceptedAuthorityMatch("snap_a", "", null), "", "authority not yet loaded keeps the action live");
  assert.equal(acceptedAuthorityMatch("snap_a", "", "snap_b"), "", "acceptedAuthorityMatch names only the latest accepted id; a superseded acceptance is supersededAcceptance's to name");
});

test("a run accepted earlier and superseded since is named as superseded, never re-offered", () => {
  assert.equal(supersededAcceptance("snap_a", "snap_b"), "snap_a", "the run's own accepted snapshot is named");
  assert.equal(supersededAcceptance("snap_a", "snap_a"), "", "the latest acceptance is not superseded");
  assert.equal(supersededAcceptance(null, "snap_b"), "", "a run never accepted is not superseded");
  assert.equal(supersededAcceptance("", "snap_b"), "");
  assert.equal(supersededAcceptance("snap_a", undefined), "", "unknown authority claims nothing");
  assert.equal(supersededAcceptance("snap_a", null), "");
  const runStatus = workspace.slice(workspace.indexOf("function RunStatus("), workspace.indexOf("function RunConsole("));
  const superseded = runStatus.slice(runStatus.indexOf("else if (supersededSnapshotId)"), runStatus.indexOf('else if (run.status === "succeeded")'));
  assert.match(superseded, /Accepted, superseded/);
  assert.doesNotMatch(superseded, /Accept analytical snapshot|Ready for acceptance/, "a superseded run must never re-offer acceptance");
});

test("a positional block locator reads as English and every other shape keeps its JSON", () => {
  assert.equal(formatBlockLocator({ line: 4 }), "line 4");
  assert.equal(formatBlockLocator({ LINE: 4 }), "line 4");
  assert.equal(formatBlockLocator({ page: 12 }), "page 12");
  assert.equal(formatBlockLocator({ PAGE: "12" }), "page 12");
  // builtin-v2 groups lines once a document is large, which is every real filing.
  assert.equal(formatBlockLocator({ lines: [1, 95] }), "lines 1\u201395");
  assert.equal(formatBlockLocator({ LINES: ["96", "179"] }), "lines 96\u2013179");
  assert.equal(formatBlockLocator({ lines: [7, 7] }), "line 7");
  assert.equal(formatBlockLocator({ pages: [2, 5] }), "pages 2\u20135");
  // A range that is not a well-formed pair keeps its JSON rather than inventing one.
  assert.equal(formatBlockLocator({ lines: [1] }), '{"lines":[1]}');
  assert.equal(formatBlockLocator({ lines: [1, 2, 3] }), '{"lines":[1,2,3]}');
  assert.equal(formatBlockLocator({ lines: [1, null] }), '{"lines":[1,null]}');
  // Unknown shapes are shown exactly as they were before, never dropped.
  assert.equal(formatBlockLocator({ sheet: "Summary", row: 4 }), '{"sheet":"Summary","row":4}');
  assert.equal(formatBlockLocator({ offset: 4 }), '{"offset":4}');
  assert.equal(formatBlockLocator({ line: null }), '{"line":null}');
  assert.equal(formatBlockLocator({ line: "" }), '{"line":""}');
  assert.equal(formatBlockLocator([{ line: 4 }]), '[{"line":4}]');
  assert.equal(formatBlockLocator({}), "{}");
  assert.equal(formatBlockLocator(undefined), "");
});

test("module ids carry their registry name, and an unknown id stays the id", () => {
  assert.equal(moduleLabel("CP-1"), "Canonical Data Foundation");
  assert.equal(moduleLabel("CP-2A"), "Downside Pathway");
  assert.equal(moduleLabel("CP-L10"), "Financial Change Screen");
  // No registry slug, or not a registry module: never a name this client invented.
  assert.equal(moduleLabel("CP-PARSE"), "CP-PARSE");
  assert.equal(moduleLabel("CP-MODEL"), "CP-MODEL");
  assert.equal(moduleLabel("CP-DR"), "CP-DR");
  // Superseded ids are not aliased onto their absorbers.
  assert.equal(moduleLabel("CP-2B"), "CP-2B");
});

test("a server code is never presented as a raw identifier", () => {
  assert.equal(humanizeCode("MODEL_EXPORT_FAILED"), "MODEL EXPORT FAILED");
  assert.equal(humanizeCode("PAUSED"), "PAUSED");
});

test("workspace identities compact only beyond the exact display threshold", async () => {
  const workbench = await import("./workbench.ts") as unknown as {
    compactIdentity?: (value: string, leading?: number, trailing?: number) => string;
  };
  assert.equal(typeof workbench.compactIdentity, "function");
  assert.equal(workbench.compactIdentity?.(""), "");
  assert.equal(workbench.compactIdentity?.("short-id"), "short-id");
  assert.equal(workbench.compactIdentity?.("1234567890123456"), "1234567890123456");
  assert.equal(workbench.compactIdentity?.("0123456789abcdef0123456789abcdef"), "0123456789ab…cdef");
  assert.equal(workbench.compactIdentity?.("model-version-identity", 5, 3), "model…ity");
});

test("the identity presenter retains exact pointer text and stays scoped to display values", () => {
  assert.match(states, /export function IdentityValue/);
  assert.match(states, /title=\{value\}/);
  assert.match(workbenchShell, /visibleSnapshotId \? <IdentityValue value=\{visibleSnapshotId\}/);
  assert.doesNotMatch(workbenchShell, /<IdentityValue value=\{visibleSnapshotIdentity\}/);
  assert.match(workspace, /<IdentityValue value=\{selectedSource\.sha256\}/);
  assert.match(workspace, /<IdentityValue value=\{selectedArtifact\.digest\}/);
  assert.match(modelBuilder, /<IdentityValue value=\{revision\.id\}/);
  assert.doesNotMatch(modelBuilder, /<IdentityValue[^>]*(?:Recalculation required|Application version)/);
  assert.match(deliverableDocument, /Exact identity · \{digest\}/, "governed paper keeps its exact identity");
  assert.match(styles, /\.rd-identity\s*\{[^}]*overflow-wrap:\s*anywhere;[^}]*word-break:/);
});

test("command center selects a credit conclusion before preparation output", async () => {
  const workbench = await import("./workbench.ts") as unknown as {
    selectConclusionArtifact?: <T extends { module_id: string }>(artifacts: readonly T[]) => T | null;
  };
  assert.equal(typeof workbench.selectConclusionArtifact, "function");
  const preparation = { module_id: "CP-PARSE", payload: { summary: "Sources prepared" } };
  const readiness = { module_id: "CP-0", payload: { summary: "Ready" } };
  const credit = { module_id: "CP-1", payload: { narrative: { takeaway: "Credit conclusion" } } };
  const synthesis = { module_id: "CP-2", payload: { summary: "Preferred synthesis" } };
  assert.equal(workbench.selectConclusionArtifact?.([preparation, readiness, credit]), credit);
  assert.equal(workbench.selectConclusionArtifact?.([credit, synthesis]), synthesis);
  assert.equal(workbench.selectConclusionArtifact?.([readiness, preparation]), preparation);
});

test("command center renders the served snapshot diff shape honestly", () => {
  const commandView = workspace.slice(workspace.indexOf("function CommandView("), workspace.indexOf("function AdminView("));
  // One authority per screen: the credit screen renders the shell's snapshot and
  // never reads /snapshot itself (FE-A0 F3).
  assert.match(commandView, /authority: SnapshotView \| null/);
  assert.doesNotMatch(commandView, /\/snapshot`/);
  assert.match(commandView, /selectConclusionArtifact\(artifacts\)/);
  assert.match(commandView, /diff\.modified(?:\?\.|\.)map\(\(item\)[\s\S]*?<IdentityValue value=\{item\.digest\}/);
  assert.doesNotMatch(commandView, /item\.(?:before|after)/);
  assert.doesNotMatch(workspace, /slice\(0,\s*12\)/);
});

test("acceptance aftermath binds to the matching snapshot id", () => {
  assert.equal(acceptedAuthorityMatch("snap_a", "", "snap_a"), "snap_a", "the served run field matches the authority");
  assert.equal(acceptedAuthorityMatch(null, "snap_a", "snap_a"), "snap_a", "the locally returned snapshot covers a server without the run field");
  assert.equal(acceptedAuthorityMatch("snap_a", "snap_b", "snap_a"), "snap_a", "the served run field wins over local state");
  assert.equal(acceptedAuthorityMatch("snap_a", "snap_b", "snap_b"), "", "local state never overrides a served mismatch");
});

test("acceptance replacement and aftermath use the latest accepted authority", () => {
  assert.match(workspace, /authority\?\.latest_accepted\?\.id/);
  assert.match(workspace, /replaces=\{authority\?\.latest_accepted \?\? null\}/);
  assert.doesNotMatch(workspace, /replaces=\{authority\?\.accepted \?\? null\}/);
});

test("a switch-required accepted run stays accepted while the visible lens is disclosed separately", () => {
  const visibleSnapshotId = "snap_visible";
  const latestAcceptedId = "snap_latest";
  assert.equal(acceptedAuthorityMatch(latestAcceptedId, "", latestAcceptedId), latestAcceptedId);
  assert.equal(acceptedAuthorityMatch(latestAcceptedId, "", visibleSnapshotId), "", "the visible lens is not the acceptance ledger");
  assert.match(workspace, /switchRequired=\{authority\?\.switch_required === true\}/);
  const acceptedBranch = workspace.slice(workspace.indexOf("if (acceptedSnapshotId)"), workspace.indexOf("else if (run.status === \"succeeded\")"));
  assert.match(acceptedBranch, /Latest accepted authority/);
  assert.match(acceptedBranch, /Visible lens remains/);
  assert.doesNotMatch(acceptedBranch, /Ready for acceptance|Accept analytical snapshot/);
});

test("the shell names the visible lens instead of conflating it with latest acceptance", () => {
  assert.match(workbenchShell, /<b>Visible snapshot:<\/b>/);
  assert.doesNotMatch(workbenchShell, /<b>Accepted:<\/b>/);
});

test("the browser geometry fixture covers every acceptance-region state", () => {
  assert.match(smoke, /\["queued", "running", "succeeded", "accepted", "superseded", "failed", "paused"\]/);
  assert.match(smoke, /accepted_snapshot_id: acceptanceRunPhase === "accepted" \? acceptanceSnapshot\.id : acceptanceRunPhase === "superseded" \? supersededSnapshotId : null/);
  for (const state of ["Accepted", "Accepted, superseded", "Acceptance blocked", "Ready for acceptance", "Acceptance waiting"]) {
    assert.match(smoke, new RegExp(state));
  }
});

test("failed and paused runs never announce a pending module as current progress", () => {
  const runStatus = workspace.slice(workspace.indexOf("function RunStatus("), workspace.indexOf("function RunConsole("));
  assert.match(runStatus, /const current = \(run\.status === "queued" \|\| run\.status === "running"\)[\s\S]*?\? run\.nodes\.find\(\(node\) => node\.status === "running"\) \|\| run\.nodes\.find\(\(node\) => node\.status === "pending"\)[\s\S]*?: undefined;/);
  assert.match(runStatus, /run\.status === "failed" \? "Execution stopped" : "Execution paused"/);
  assert.match(runStatus, /aria-valuetext=\{`\$\{complete\} of \$\{run\.nodes\.length\} modules complete\$\{current \?/);
});

test("acceptance review classifies authority slots without claiming artifact byte changes", () => {
  const summary = acceptanceSlotSummary(
    [{ module_id: "CP-0" }, { module_id: "CP-1" }, { module_id: "CP-5" }, { module_id: "CP-5" }],
    [{ module_id: "CP-0" }, { module_id: "CP-2" }, { module_id: "CP-5" }],
  );

  assert.deepEqual(summary, {
    added: ["CP-1"],
    replaced: ["CP-0", "CP-5"],
    removed: ["CP-2"],
  });
  assert.doesNotMatch(workspace, /v\{(?:run\.plan|replaces)\.source_set_version \?\? "Unavailable"\}/, "missing versions must not render as vUnavailable");
});

test("an evidence id resolves whatever this store minted", () => {
  assert.equal(evidenceKind("src-6b1f2a"), "source");
  assert.equal(evidenceKind("art-6b1f2a"), "artifact");
  // A promoted analyst note is `src-note-<hex>`: the tail is itself hyphenated.
  assert.equal(evidenceKind("src-note-6b1f2a"), "source");
  assert.equal(evidenceKind("  src_6b1f2a  "), "source", "the legacy underscore form still resolves");
  assert.equal(evidenceKind("case-6b1f2a"), null);
  assert.equal(evidenceKind("src-"), null);
});
