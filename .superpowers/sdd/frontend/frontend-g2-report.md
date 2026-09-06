# FE-G2 report — the IA change: destinations, routes, rail, palette, titles, tests and documents

Executed as `FE-G2` (2026-09-06) in `.claude/worktrees/frontend-destination-migration-1f874e`
on branch `claude/frontend-destination-migration-1f874e`, cut from `main` at `b1d485a` (the
FE-G1 merge, PR #63). Frontend: Node 24.16.0, `npm ci` (exit 0). Backend interpreter for
the combined app: the primary checkout's `caos/server/.venv` (Python 3.14.6); no server
file changes in this task (see §6), so the backend suite and Ruff are not required and
were not run. Playwright browsers from the machine cache.

Inputs read before the first change: the standing preamble and the frontend addendum;
`## Decisions` in `frontend-a1-ia-audit.md` (D1 Align, D2 forwarding pages, D3 one file,
D6 both records, D12 Run tool on every surface) and its §5.1 "Align" table and route map;
`frontend-d1-directions.md` (canvas URL, artboard names, export digests; Align chosen, no
changes); `workbench.ts`, `WorkbenchShell.tsx`, `Workspace.tsx`, `ModelBuilder.tsx`,
`ReportStudio.tsx`, `workspaceAuthority.ts`, `app/[destination]/page.tsx`,
`app/not-found.tsx`, `app/layout.tsx`, `next.config.js`, every unit test,
`workbench-smoke.mjs`, `a11y-axe.mjs`, `focus-restoration-smoke.mjs`, `identity-a11y.mjs`,
`production-inventory.mjs`, `CLAUDE.md`, `.impeccable.md`, `README.md`,
`control-capability-map.md`, `DESIGN.md`, `docs/DECISIONS.md` §14, the enterprise reports
that name a frontend route, and `caos/server/caos/contracts.py` and
`intake/service.py` (the two server strings the audit listed).

## Status

COMPLETE on the branch; draft pull request
https://github.com/EricMG13/CAOS-LangMVP/pull/65 (not merged). Three commits plus this
correction: `93af3b8` (the app, its unit tests and the browser scripts, one commit because
every load-bearing literal moves with the code it pins), `709eb37` (the documents and the
two decision records), `c7fcec7` (this report and `progress.md`), and the commit that
records the pull request and the rebase. The branch was rebased onto `origin/main` at
`fff945c` (PR #64, `fix(engine)`: `caos/server/caos/engine/runtime.py` and
`caos/tests/spec/test_runs_spec.py`, no frontend path) before the push, which rewrote the
hashes the first draft of this report and `progress.md` carried (`2d9e914`, `472d4c2`,
`614cb45`); the tree of every frontend file is byte-identical across the rebase. Every
frontend gate is green on that tree: lint, tsc, unit 135/135, build 20/20, the workbench
smoke in Chromium, Firefox and WebKit, the accessibility sweep over 17 routes at six
viewports with 0 violations, and the focus soak 8/8; the Chromium smoke was run a second
time against a server started from the rebased tree (§4). No server file changed in this
task, so the backend suite and Ruff were not run.

## 0. A note on the canvas the task names

The task points at `.superpowers/sdd/frontend/frontend-d2-screens.md` as the approved
canvas. That file does not exist on `main`, on `origin/claude/fe-design-directions`, or
in any branch (`git log --all -- .superpowers/sdd/frontend/frontend-d2-screens.md` is
empty): FE-D2 has not run. The approval record this task can bind is FE-D1
(`frontend-d1-directions.md` §3: "Align, no changes — record it and commit", 2026-09-05),
whose Align artboards draw the shell at 1440 and 720 and the Run surface paused on plan
approval. The `DESIGN.md` addendum and the `docs/DECISIONS.md` entry therefore name the
FE-D1 canvas, its three Align artboards and the retained export digest, and say that the
FE-D2 hi-fi screens, when approved, extend the addendum rather than replace it. Nothing in
this task redraws a surface interior, so the missing hi-fi canvas blocks none of the
structural work.

Resolved 2026-09-06 after the pull request opened: the decision owner instructed "FE-G3
proceeds on the FE-D1 artboards; skip FE-D2". Recorded as D13 in
`frontend-a1-ia-audit.md` `## Decisions`; the DESIGN.md addendum and DECISIONS §14.23 now
say the addendum is the complete approval record.

## 1. Before-and-after route table

| Destination | Before (slug · label · kicker · title · tab) | After (slug · label · kicker · title · tab) | Old slug behaviour |
|---|---|---|---|
| Portfolio | `/cases/` · Cases · Portfolio / Surveillance · Monitored credits · CAOS — Cases | `/portfolio/` · Portfolio · Portfolio / Surveillance · Monitored credits · CAOS — Portfolio | `/cases/` forwards (history replaced, query intact) |
| Credit | `/command-center/` · Command Center · Credit / Current state · Current state and what changed · CAOS — Command Center | `/credit/` · Credit · Credit / Current state · Current state and what changed · CAOS — Credit | `/command-center/` forwards |
| Sources | `/sources/` · Sources · Sources / Evidence · Documents, extraction and coverage · CAOS — Sources | unchanged | — |
| Analysis | `/deep-dive/` · Deep-Dive · Analysis / Reader · Accepted analysis · CAOS — Deep-Dive | `/analysis/` · Analysis · Analysis / Reader · Accepted analysis · CAOS — Analysis | `/deep-dive/` forwards |
| Run (tool of Analysis) | `/run-console/` · Run Console · Analysis / Execution · Run and acceptance · CAOS — Run Console | `/run/` · Run · Analysis / Run · Run and acceptance · CAOS — Run | `/run-console/` forwards |
| Market | `/rv-screener/` · RV Screener · Market / Comparison · Governed loan universe · CAOS — RV Screener | `/market/` · Market · Market / Comparison · Governed loan universe · CAOS — Market | `/rv-screener/` forwards |
| Model | `/model-builder/` · Model Builder · Model / Forecast · Assumptions, lineage and sign-off · CAOS — Model Builder | `/model/` · Model · Model / Forecast · Assumptions, lineage and sign-off · CAOS — Model | `/model-builder/` forwards |
| Report | `/report-studio/` · Report Studio · Report / Publication · Compose, freeze and file · CAOS — Report Studio | `/report/` · Report · Report / Publication · Compose, freeze and file · CAOS — Report | `/report-studio/` forwards |
| Admin | `/admin-studio/` · Admin Studio · Admin / Governance · Deployment capability · CAOS — Admin Studio | `/admin/` · Admin · Admin / Governance · Deployment capability · CAOS — Admin | `/admin-studio/` forwards |

Tab title before the move was two things at once: `CAOS — <destination>` from the route
metadata on a document load and `CAOS — <page title>` from the client title effect after a
client navigation. After the move both write `CAOS — <destination>`.

## 2. Decisions applied

- **D1 Align.** `routeDestinations` in `src/lib/workbench.ts` is the nine-row table in §1;
  `destinationMeta` carries the kickers and page titles; Run's kicker is "Analysis / Run"
  (the audit's Align table), replacing "Analysis / Execution". `workflows` derives every
  href from the table through `routeFor(destination)`; the shell's Governance entry is
  `routeFor("Admin")`; the palette maps `workflows` and their tools and nothing else.
- **D2 forwarding pages.** `forwardedRoutes` is the eight-row map; `routeSlugs` is the
  static route set (`generateStaticParams` emits exactly it: 17 pages plus root and
  not-found, `npm run build` → 20/20). A forwarded slug's page renders
  `RouteForwarder`, which replaces history to the destination with
  `window.location.search` and `hash` intact. `destinationFromSlug` resolves a forwarded
  slug to its destination, so the shell renders the right surface, kicker and tab title
  from the first paint and the forward changes only the address; an unknown slug is
  `null` and still the 404.

  The first implementation used `router.replace`. It forwarded when the URL carried
  `?case=` and silently did not when it carried nothing (probed on `/admin-studio/`,
  `/model-builder/`, `/run-console/`): Next's app router applies `router.replace` in a
  transition, and `Workspace.tsx`'s URL-sync effect — which runs on the same commit,
  after the child forwarder's effect — calls `history.replaceState` with the *current*
  address; Next's patched `replaceState` treats that as an external URL change and
  dispatches its own restore, which lands second and wins. The landed forwarder writes
  through the same external `replaceState` the workspace uses
  (`historyStateForExternalReplace(window.history.state)`): the address changes
  synchronously before the parent effect reads `window.location`, Next syncs
  `usePathname` in place, the entry keeps `__NA` (back and forward stay soft
  traversals; probed: `/report-studio/` → rail Sources → back lands on `/report/` with
  one document load), and nothing is fetched. Verified on all eight forwarders with and
  without a query, with a hash, on a fresh register and with an unknown case id.
- **Authority replay.** `workspaceAuthorityReducer`'s `hydrate` returns the state
  unchanged when the state is already hydrated and the event names the current case and
  run. That is the reducer's statement of "a forwarded route is a route replay": whatever
  re-presents the same authority after the first hydration — the forwarder, a StrictMode
  double effect, a re-run of the mount effect — opens no generation and no pending
  request. `workspaceAuthority.test.ts` proves it once per forwarder (loading and
  resolved states), for the empty route, and proves the negative (a different run is not
  a replay: generation +1, run adopted). The browser proof is in the smoke: the forward
  reads case authority exactly once and replaces rather than pushes.
- **D3 one file.** `Workspace.tsx` changed the route resolution (three lines), the
  destination switch labels, twelve link targets, the title effect and the copy that
  names a destination as a place ("Open Run", "Follow in Run", "versioned in Report",
  "provisioned from Report", the draft-discard detail). Nothing moved out of the file;
  the authority machine and the reducer did not move.
- **D6 both records.** `DESIGN.md` gained the 2026-09-06 addendum (destinations, route
  map, one-home rules, canvas URL, artboards, export digest, re-verified with
  `shasum -a 256`); `docs/DECISIONS.md` gained §14.23.
- **D12 Run tool on every surface.** `WorkbenchShell.tsx` renders every workflow's tool
  group unconditionally (`workflows.filter(w => w.tools?.length)`), so "Analysis tools
  · Run" and its LIVE badge appear on Portfolio, Report and Admin; the aria-current rule
  is unchanged in substance (tool link when one targets the active destination, the
  governance entry on Admin, else the workflow link) and now proven on four routes.
- **Tab title.** Both the route metadata and the client title effect write
  `CAOS — <destination>`; before the move the effect wrote the page title after a client
  navigation while a document load showed the destination.
- **One-home rules.** Unchanged in substance: run progress, compilation, acceptance and
  plan approval render only inside the `Run` case of the destination switch; intake only
  inside `Portfolio`; the reader only inside `Analysis`; `Admin` renders `AdminView` with
  no control for an unserved route. No new control was drawn.

## 3. Test literals that moved, with their commit

All of the below moved in the commit that changed the code they pin (`93af3b8`, the
app-and-scripts commit), never separately.

| Test file | Literal before | Literal after |
|---|---|---|
| `src/lib/workbench.test.ts` "approved workspace labels preserve the existing routes" | `[label, href]` table with `/cases`, `/command-center`, `/deep-dive`, `/rv-screener`, `/model-builder`, `/report-studio` | renamed "the rail's words are the route slugs…": the nine-row `routeDestinations` table, the seven `[label, href]` pairs at the new slugs, every href `=== routeFor(destination)`, the tools list, `routeFor("Admin") === "/admin"`, the nine kickers, and the two tab-title pins (`page.tsx` metadata, `Workspace.tsx` title effect) |
| `src/lib/workbench.test.ts` (new) "every pre-Align slug is a static forwarding page…" | — | the eight-row `forwardedRoutes` map; every target is a destination slug and no forwarder is one; `destinationFromSlug(old) === destinationFromSlug(new)`; `routeSlugs` is destinations then forwarders; unknown slug → `null`; `page.tsx` emits `routeSlugs`, renders `RouteForwarder` for a forwarded slug and 404s the unknown; `not-found.tsx` returns to `/portfolio/`; `RouteForwarder` writes through `historyStateForExternalReplace` and never pushes or uses the router; the a11y sweep imports the tables and derives `routes` from them; no component still targets a forwarded slug |
| `src/lib/workbench.test.ts` (new) "the palette offers every destination once…" | — | the palette derives from `workflows` (source pins) and its eight `["Open <word>", href]` entries |
| `src/lib/workbench.test.ts` (new) "exactly one rail entry is current, and the Run tool renders on every surface" | — | shell source pins: no `activeWorkflow.tools?.length ?` gate, tool groups mapped from `workflows`, `active !== "Admin"`, LIVE badge on `"Run"`, Governance at `routeFor("Admin")`, no `"Admin Studio"`/`"Run Console"`/`"Report Studio"`/`"/admin-studio"`/`"/cases"` literal; smoke pins for the four-route aria-current table and the "Run tool is missing from a non-Analysis surface" assertion |
| `src/lib/workbench.test.ts` "every route path keeps its trailing slash" and "values set, replace, and clear query keys" | `/run-console`, `/cases` | `/run`, `/portfolio` (vocabulary only; `withQuery` is path-agnostic) |
| `src/lib/workspaceAuthority.test.ts` (new) "a forwarded route re-hydrates the same case and run as a route replay" | — | one replay assertion per `forwardedRoutes` row (loading and resolved), the empty route, and the negative case |
| `src/components/model/ModelBuilder.test.ts:20` | `case "Model Builder": return <ModelBuilder …` | `case "Model": return <ModelBuilder …` |
| `src/components/report/ReportStudio.test.ts:14` | `case "Report Studio": return <ReportStudio` | `case "Report": return <ReportStudio` |
| `src/components/report/ReportStudio.test.ts:74–75` | `withQuery("/model-builder", …)`, `withQuery("/run-console", …)` | `withQuery("/model", …)`, `withQuery("/run", …)` |
| `scripts/workbench-smoke.mjs` route literals | `/cases/` ×7, `/command-center/` ×8, `/deep-dive/` ×4, `/run-console/` ×14, `/rv-screener/` ×1, `/model-builder/` ×4, `/report-studio/` ×9, `/admin-studio/` ×1; pathname checks `"/cases"`, `"/run-console"` | `/portfolio/`, `/credit/`, `/analysis/`, `/run/`, `/market/`, `/model/`, `/report/`, `/admin/`; `"/portfolio"`, `"/run"`. One `/run-console/` literal remains by design: the forwarder step that loads it and asserts it lands on `/run/` |
| `scripts/workbench-smoke.mjs` accessible names | `getByRole("link", { name: "Open Model Builder" })`, `getByRole("link", { name: "Open Run Console" })` | `{ name: "Open Model", exact: true }`, `{ name: "Open Run", exact: true }` (exact because the palette also offers "Open Run") |
| `scripts/workbench-smoke.mjs` aria-current table | three routes | four routes (`/admin/`, "Governance", "Admin" added), plus the D12 assertion and the forwarder step (replace not push, query and hash intact, tab title, one authority read, `goBack` lands on the previous entry) |
| `scripts/a11y-axe.mjs` route list and literal | hard-coded nine-route array; Admin special-cased by slug; summary `routes 9 … combinations 75` | `routes` derived from `routeDestinations` and `forwardedRoutes` (17), Admin special-cased by destination, a landing assertion per forwarder, summary `routes 17, forwarders 8, combinations 123` (the count is computed: 17 × 6 + 21) |
| `scripts/a11y-axe.mjs` fixture routes | `/run-console/`, `/model-builder/`, `/report-studio/`, `/command-center/`, `/cases/` | `/run/`, `/model/`, `/report/`, `/credit/`, `/portfolio/` |
| `scripts/focus-restoration-smoke.mjs:67` | `/model-builder/` | `/model/` |
| `scripts/identity-a11y.mjs:85` | `/cases/` | `/portfolio/` |

Not moved, by design: `scripts/production-inventory.mjs` (its slug table and journey; `CLAUDE.md` records it as the inventory for a deployment that serves those routes and not a check on this build — the forwarders keep its URLs resolving), `scripts/webkit-teardown.test.mjs` (its `/cases/` strings are fixture URLs for the rejection parser, not routes), and every retained candidate and evidence file.

Pinned names that did **not** change: "Accept analytical snapshot" (eight smoke sites), the "Evidence focus" heading, the `page.once("dialog")` accept, "Open review", "Open credit", "Read accepted analysis", "Review latest run", "Open selected run", "Open analysis run", "Sources & evidence", "Select case", "Open command palette", "Approve research plan", every dialog and drawer name.

## 4. Gates

All from `caos/frontend` on the final tree unless noted; the combined app is this
worktree's `caos/server/dev.py` under `ENVIRONMENT=development CAOS_PROVIDER=host_control
AGENT_EXECUTION_ENABLED=true ANTHROPIC_API_KEY= PORT=8770 CAOS_DATA_DIR=<scratch>/dev-data-g2`
with `worker.py` beside it, both started detached with `subprocess.Popen(...,
start_new_session=True)` from the primary checkout's `.venv` (Python 3.14.6), as the
FE-G1 report did. `:8000` was free but `:8769` still held a Python listener from an
earlier session, so this task used `:8770` and `CAOS_URL`.

| Gate | Command | Result |
|---|---|---|
| Failing-first | `npm run test:unit` before the app change | `workbench.test.ts` and `workspaceAuthority.test.ts` fail to load (`forwardedRoutes`, `routeFor`, `routeSlugs` not exported); `ModelBuilder.test.ts` "Workspace delegates Model Builder…", `ReportStudio.test.ts` "Workspace delegates Report Studio…" and "freeze remains a reserved approval sequence…" fail on the moved pins |
| Lint | `npm run lint` | `eslint .` — 0 problems (one `no-unused-vars` warning for `destinationMeta` in `Workspace.tsx` appeared mid-task and was removed) |
| Types | `npx tsc --noEmit` | exit 0 (one interim error, the forwarder tuple typed as `readonly string[]` in the test, fixed) |
| Unit | `npm run test:unit` | `ℹ tests 135 / ℹ pass 135 / ℹ fail 0` (131 before the task; four tests added) |
| Build | `npm run build` | `✓ Generating static pages using 5 workers (20/20)`: `/`, `/_not-found`, nine destinations, eight forwarders; `out/` has no `nomodule` script and no polyfill chunk (unchanged from FE-G1) |
| Workbench smoke, Chromium | `CAOS_URL=http://127.0.0.1:8770 CAOS_BROWSER=chromium npm run test:workbench` | `{"browser":"chromium","browser_version":"151.0.7922.34","status":"passed","duration_ms":138525}`; timing `domContentLoaded 51.8 / firstContentfulPaint 144`, budget enforced |
| Accessibility sweep | `CAOS_URL=http://127.0.0.1:8770 npm run a11y` (after the smoke, 45 s later, same server) | `{"routes":17,"forwarders":8,"viewports":6,"combinations":123,…,"states":["empty","populated","review","filed","loading","error","refusal"],…,"violations":0}` — every destination and every forwarder at 1280, 1366, 1440, 1600, 1920 and 720 (200 %), the page-level horizontal-overflow check included in the sweep, and each forwarder asserted to land at its destination with its query intact |
| Quality ledger | `caos/server/.venv/bin/python docs/quality_ledger_coverage.py` | `routes checked: 54 product files: 374 features: 134 — the ledger documents every route and every product file` (`RouteForwarder.tsx` falls under `^caos/frontend/src/`) |
| Workbench smoke, Firefox | `CAOS_URL=http://127.0.0.1:8770 CAOS_BROWSER=firefox npm run test:workbench` (70 s after the sweep) | `{"browser":"firefox","browser_version":"153.0","status":"passed","duration_ms":151941}`; timing recorded, not enforced (`domContentLoaded 186 / firstContentfulPaint 242`) |
| Workbench smoke, WebKit | `CAOS_URL=http://127.0.0.1:8770 CAOS_BROWSER=webkit npm run test:workbench` (75 s after Firefox) | `{"browser":"webkit","browser_version":"26.5","status":"passed","duration_ms":147350}`; timing recorded, not enforced (`domContentLoaded 22 / firstContentfulPaint 112`); no D-016 prefetch rejection this run |
| Focus soak, Chromium | `CAOS_URL=http://127.0.0.1:8770 CAOS_BROWSER=chromium npm run test:focus` (its one route literal moved) | `{"browser":"chromium","iterations":8,"passes":8,"fails":0,"harnessErrors":0,…}` |
| Server 429/5xx after every gate | same greps, plus `grep -ci 'error\|traceback' worker.log` | 0 / 0 / 0 |
| Workbench smoke, Chromium, after the rebase onto `fff945c` | server and worker restarted from the rebased tree on a fresh data directory; `CAOS_URL=http://127.0.0.1:8770 CAOS_BROWSER=chromium npm run test:workbench` | `{"browser":"chromium","browser_version":"151.0.7922.34","status":"passed","duration_ms":139650}` |
| Backend suite, Ruff | — | not run: no server file changed in this task (§6); the rebase brought in PR #64's engine change with its own spec tests, landed on `main` |

## 5. Follow-ups

- **Server strings that still say the old words (not changed; the audit listed them
  under change cost, not as proven necessary).** `caos/server/caos/contracts.py::DESTINATIONS`
  is the old nine-name tuple and is read by nothing (`grep` finds only the definition);
  `caos/server/caos/intake/service.py::_unavailable` falls back to the wire text "The
  documents are admitted; retry execution from the run console." for an engine code
  `_NEXT_ACTIONS` does not name. Both are wire-adjacent server edits with their own spec
  pins and belong to a server change, not this one.
- **Interior copy that still names the old surface (FE-G3).** `ModelBuilder.tsx` panel
  headings and load error ("Model Builder", "Unable to load Model Builder"),
  `ReportStudio.tsx` load error and pathway-change prompt ("Unable to load Report
  Studio", "Discard the unsaved Report Studio changes before changing pathway?"),
  `states.tsx` comment, and `models/service.py` comments. Panel interiors are FE-G3's
  scope; the chrome-level copy that names a destination as a place was moved here.
- **`qa/INVENTORY.md`, `qa/probe.py`, `qa/edge_proxy.py` and `production-inventory.mjs`**
  name the old slugs; they describe or drive a deployment that serves those routes
  (`CLAUDE.md` known gaps) and keep working through the forwarders. Not edited.
- **`.impeccable.md` and `DESIGN.md` CSS class names** (`.cases-intake`,
  `.cases-register`, `.cases-create`, `.cases-fit`, `.model-builder-*`) are unchanged:
  class names are not routes, and `CLAUDE.md` names `.cases-intake` as the intake panel.
- **Node warning.** `node scripts/a11y-axe.mjs` now imports `../src/lib/workbench.ts`
  and Node 24 prints `MODULE_TYPELESS_PACKAGE_JSON` (it re-parses the `.ts` file as ESM).
  Harmless; silencing it means `"type": "module"` in `package.json`, which
  `next.config.js` (CommonJS) forbids, or a `.mjs` re-export of the two tables.
- **FE-D2 is skipped** (§0, D13): the DESIGN.md addendum binds the FE-D1 Align artboards
  and is the complete approval record for FE-G3.

## 6. Server files

None changed. The audit's change-cost line named `contracts.py`'s `DESTINATIONS` tuple
and one intake `next_action` string; neither is a route, the tuple is unread, and the
string is a fallback for engine codes the intake service does not name, so the
"no server change unless the audit proved one necessary" constraint holds and both are
follow-ups (§5).

## 7. Commits

| Commit | Content |
|---|---|
| `93af3b8` | `feat(frontend): serve the Align destination set with a forwarding page per earlier slug` — `workbench.ts` (tables, `routeFor`, `forwardedSlug`, `destinationFromSlug` → `Destination \| null`, `workflows` derived), `workspaceAuthority.ts` (hydrate replay), `RouteForwarder.tsx` (new), `app/[destination]/page.tsx`, `app/not-found.tsx`, `WorkbenchShell.tsx`, `Workspace.tsx`, `ModelBuilder.tsx`, `ReportStudio.tsx`; `workbench.test.ts`, `workspaceAuthority.test.ts`, `ModelBuilder.test.ts`, `ReportStudio.test.ts`; `workbench-smoke.mjs`, `a11y-axe.mjs`, `focus-restoration-smoke.mjs`, `identity-a11y.mjs`, `draft-history-smoke.mjs` |
| `709eb37` | `docs: record the Align IA (DESIGN.md addendum, DECISIONS §14.23) and retire the old route names` — `DESIGN.md`, `docs/DECISIONS.md`, `CLAUDE.md`, `.impeccable.md`, `README.md`, `caos/frontend/docs/control-capability-map.md`, the prompt series' frontend addendum, and one line each in the Task 8, 9 and 13 reports |
| `c7fcec7` | `docs(sdd): FE-G2 report and progress row` — this file and `.superpowers/sdd/frontend/progress.md`, written with the pre-rebase hashes |
| (this commit) | `docs(sdd): record the FE-G2 pull request and the rebase` — the corrected hashes, the rebase note, the PR URL and the post-rebase Chromium smoke |

## 8. Confidence review

Scope: the two code-bearing commits. Ranked by likelihood × blast radius.

1. **The forwarder does nothing on some paths** — worried because a `useEffect` forward is
   invisible to every unit test. Investigated by probing all eight forwarders in
   Chromium with and without `?case=`, with a hash and with an unknown case id.
   → CONFIRMED bug in the first implementation (`router.replace` lost to the workspace's
   URL-sync `replaceState` whenever the URL carried no query; root cause traced in Next's
   patched `history.replaceState`, `node_modules/next/dist/client/components/app-router.js`).
   Patched at the root: the forwarder writes through the same external `replaceState`
   the workspace uses; the entry keeps `__NA`, so back/forward stay soft. Re-probed: all
   eight land with and without a query; `goBack` after a forward lands on the previous
   entry with one document load. The unit test pins the mechanism and bans the router.
2. **`hydrate` idempotency changes a real flow** — worried that some path re-dispatches
   `hydrate` expecting a fresh generation. Investigated: exactly one dispatch site
   (`Workspace.tsx:485`, the mount effect); its re-runs (StrictMode in dev, a callback
   identity change) are followed by `refreshCases`, which dispatches `requestStarted`
   and bumps the generation itself. → fine (single site read; three-engine smoke green,
   including the case-switch, stale-run and history-fence steps).
3. **The smoke's request budget** — worried the added page loads tip the 300/min bucket.
   Investigated: `grep -c " 429 "` on the app log after every gate → 0. → fine.
4. **A forwarded slug reached by raw `pushState`** (test-only) renders the destination but
   keeps the old address, because no page component changes. → by-design: the smoke's
   only raw pushState sites now name the new slugs; nothing in the tree links to an old
   slug (unit test), and a document load of an old slug always forwards.
5. **The a11y sweep's `.ts` import in CI** — worried CI's Node cannot strip types.
   Investigated: `ci.yml` and `nightly.yml` pin `node-version: 24`, the same mechanism
   `npm run test:unit` already relies on. → fine; the `MODULE_TYPELESS_PACKAGE_JSON`
   warning is cosmetic (§5).
6. **The Admin forwarder and the case query** — the sweep must not append `?case=` to
   Admin; it keyed on the slug before. → fine: keyed on `destinationFromSlug(...) === "Admin"`,
   which covers `/admin/` and `/admin-studio/`; verified by the sweep's 0 violations and
   the Admin smoke step.
7. **Residual old-slug strings** — swept `caos/frontend` for every old slug: only CSS class
   names (`.model-builder`, `.report-studio`), a fixture tree segment in a test, the
   smoke's deliberate forwarder step, and `production-inventory.mjs` remain (§5).
8. **The route-metadata title for a forwarded slug** — asserted in the smoke
   (`page.title() === "CAOS — Run"` after loading `/run-console/`). → fine.
9. **Anything reading the edited documents** — no test opens `DESIGN.md`, `DECISIONS.md`,
   `CLAUDE.md` or the README (grep of `caos/tests`, `run_sec_audit.py`,
   `quality_ledger_coverage.py`); the quality ledger covers `RouteForwarder.tsx` under
   `^caos/frontend/src/` (gate output in §4). → fine.

Fixed: 1. Verified fine: 2, 3, 5, 6, 7, 8, 9. By-design: 4. Still open: none.

## 9. Commands run

```
npm ci --no-audit --no-fund                                  → exit 0
npm run test:unit                                            → red first (2 files fail to load, 3 pins fail), then ℹ tests 135 / pass 135 / fail 0
npm run lint                                                 → ESLint: No issues found
npx tsc --noEmit                                             → TypeScript: No errors found
npm run build                                                → ✓ Generating static pages using 5 workers (20/20)
python dev.py / worker.py (host_control, :8770, detached)    → GET /api/health {"status":"ok","store":true,"bundle":true,"checkpointer":true}
node <probe> (8 forwarders × {query, no query, hash})        → every forwarder lands; __NA true; back is a soft traversal
CAOS_URL=… CAOS_BROWSER=chromium npm run test:workbench      → status passed, 138525 ms
CAOS_URL=… npm run a11y                                      → routes 17, forwarders 8, viewports 6, combinations 123, violations 0
CAOS_URL=… CAOS_BROWSER=firefox npm run test:workbench       → status passed, 151941 ms
CAOS_URL=… CAOS_BROWSER=webkit npm run test:workbench        → status passed, 147350 ms
CAOS_URL=… CAOS_BROWSER=chromium npm run test:focus          → iterations 8, passes 8, fails 0
caos/server/.venv/bin/python docs/quality_ledger_coverage.py → routes checked: 54 product files: 374 features: 134
shasum -a 256 .superpowers/sdd/frontend/design/fe-d1-align-shell-1440.png → 45ea2f8f…9cb51e (matches the FE-D1 record)
grep -c " 429 " app.log; grep -c -E " 50[0-9] " app.log      → 0; 0
```
