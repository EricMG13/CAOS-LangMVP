# FE-G3 report — the destination surfaces to the approved screens

Executed as `FE-G3` (2026-09-06) in `.claude/worktrees/fe-task-03-surfaces` on branch
`claude/fe-task-03-surfaces`, cut from `origin/main` at `c3b85d0` (the FE-G2 merge, PR #65).
Frontend: Node 24.16.0, `npm ci` (exit 0). Backend interpreter for the combined app: the
primary checkout's `caos/server/.venv` (Python 3.14.6). Playwright browsers from the
machine cache.

Inputs read before the first change: the standing preamble and the frontend addendum; the
FE-G3 prompt; `## Decisions` in `frontend-a1-ia-audit.md` (D7 governance controls to
Admin, D10 the real-pack advanced path, D11 the compile form as a disclosure, D12, D13
FE-D2 skipped) and its §2.7 friction register (F-01…F-20); the Align record in
`docs/design/canvas/workbench-directions/canvas.json` (summary, motivation, trade-off,
"drawn with D11 and D12", the nine must-not lines) and the copy and structure of the three
Align artboards (`Align - Shell 1440.dc.html`, `Align - Shell 720.dc.html`,
`Align - Analysis paused.dc.html`, read as text); `frontend-d1-directions.md`;
`DESIGN.md` 2026-09-06 addendum; `docs/DECISIONS.md` §14.23; UX-011…UX-017 in
`ENTERPRISE_TESTING_READINESS.md`; `Workspace.tsx` (`RunConsole`, `ResearchPlanView`,
`RunStatus`, `IntakePanel`, `CasesView`, `AdminView`, the intake read effect, the governed
write handlers), `ReportStudio.tsx` (`addMember`, `canProvision`, the member form),
`ModelBuilder.tsx` (the blob download pattern), `lib/api.ts` (`IntakeRecord`,
`IntakeRefusal`), `globals.css` (disclosure and Admin rules), `workbench-smoke.mjs` (the
Admin contracts step, the intake refusal step, the compile-form pins, the reader steps,
the download proof), `a11y-axe.mjs` (the `state-refusal` and `pending-plan` fixtures),
`caos/server/caos/api/__init__.py` (`/members`, `/audit-package`), `identity.py` (the dev
default role) and `storage/store.py::create_case` (the creator's standing).

## Status

COMPLETE on the branch; draft pull request opened after the report commit (URL in
`progress.md`). Three commits: the code with its unit tests and browser scripts (every
load-bearing literal moved with the code it pins), the capability map, and this report
with the progress row and the retained evidence. Every frontend gate is green on the code
commit's tree: lint, tsc, unit 138/138 (three tests added, five mutations caught), build
20/20, the workbench smoke in Chromium, Firefox and WebKit with the six document-first
journeys and the new D7, D10 and D11 steps, the accessibility sweep over 125
combinations with 0 violations (twice: on the populated server, where the route loop
tripped the per-subject request ceiling, and on a fresh server, where it did not — §5),
and no server file changed.

## 0. What "the approved screens" are under D13

The FE-G3 prompt names `frontend-d2-screens.md` and "every destination and every decision
state". D13 (2026-09-06) skipped FE-D2: the approval record is the FE-D1 Align canvas,
whose three artboards draw two surfaces — Credit (the shell at 1440 and 720) and Run
paused on `PLAN_APPROVAL_REQUIRED` for an intake-created Deep Research run, drawn with
D11 (the compile form collapsed to "Advanced: compile a route") and D12 (the Run tool on
every surface, landed in FE-G2). The canvas record's own summary says "Nothing merges;
every surface keeps its interior." So the specification this task can implement is:

1. **Run, to the "Analysis paused" artboard (D11).** The execution route first, the
   persisted plan and its one primary ("Approve research plan") inside it, and the compile
   form collapsed at the bottom as `Advanced: compile a route` whenever the selected run
   came from intake. A run compiled by hand keeps the open form (nothing in the canvas
   draws that case, and the smoke's compile steps pin it).
2. **Credit, to the "Shell 1440 / 720" artboards.** Already the shipped surface after
   FE-G1 and FE-G2 (one authority read, "versioned in Report"); verified by screenshot
   beside the export, no change.
3. **The decisions the audit assigned to FE-G3:** D7 (member provisioning leaves Report
   for Admin; Admin gains the audit-package download; unserved rows stay "Not served";
   the filing gate stays on Report) and D10 (the `INTAKE_ISSUER_AMBIGUOUS` next action
   points at the advanced path: create case → Sources uploads → Run).

Everything else in the friction register (F-04 drawer locator copy, F-13 reader notes on
Model and Analysis, F-18 markdown tables in the reader, F-19 Report's pathway scoping) has
no artboard and no decision; each is listed in §6 for FE-G4, not approximated here.

## 1. Changes

All in one code commit (§4 names the literals that moved with it); the capability map
and the report are separate commits.

- **Run (D11, the "Analysis paused" artboard).** `RunConsole` takes `fromIntake`
  (`Workspace.tsx`: `Boolean(run && intake?.case_id === caseId && intake.run?.id === run.id)`).
  The compile form is one JSX fragment with two homes: the `span-4` "Compile route"
  panel beside a `span-8` execution route while the analyst compiles by hand (every
  existing pin — `#pathway`, "Compile and run", the served-cut steps, the reader's
  absence — keeps holding), or a `span-12` execution route followed by
  `<details className="panel run-advanced span-12"><summary>Advanced: compile a route</summary>`
  when the selected run came from intake. Only the intake record can say a run came
  from intake, so the intake read effect now runs on Run as well as Portfolio, still
  gated on the case wire naming an intake (`latest_intake_id`) and never a 404 probe;
  cases created through the API name none, so the smoke's request budget is untouched
  (0 × 429 on the server log after every gate). Two CSS rules give the summary the
  panel-header geometry (`globals.css`). The gate structure the artboard draws —
  execution route, "Acceptance blocked — review and approve the persisted research plan
  below", the plan, "Approve research plan" as the one primary — was already the shipped
  order; the disclosure is the only structural change.
- **Admin (D7).** `AdminView` takes the case, the identity and the workspace's new
  governed write `provisionMember`. It draws a "Case governance" panel: "Download audit
  package" (`GET /api/cases/{id}/audit-package` through `networkFetch`, blob and anchor
  like the model download; the receipt names the filename and the `x-caos-sha256`
  digest as an `IdentityValue`; a 404 renders the `Unavailable` state; any other failure
  a critical note) and the provisioning form moved from Report verbatim (subject,
  APPROVER/ADMIN standing, "Provision member"), rendered only for a current
  APPROVER/ADMIN role with stored APPROVER/ADMIN standing on the case — the filing rule.
  A reader sees "Reader access: member provisioning is an analyst action." and a writer
  without standing sees the rule in one sentence; with no case selected the panel says
  what to do. The contracts table keeps its five rows: the two served rows now say
  "download below" / "provisioned below", the three unserved rows stay "Not served", and
  the intro flag reads PARTIAL with the copy "Most administrative screens are not served
  by this application build… The two contracts this build serves … are drawn below; the
  rest are marked not served." `provisionMember` lives beside the other governed writes
  in `Workspace.tsx`: `pendingAction "member"`, authority-fenced, receipt
  "`<subject> provisioned as case <ROLE>.`", then `refreshCase` so `members` reflects
  the new standing. `ReportStudio.tsx` loses `memberForm`, `addMember`, `canProvision`
  and the form; the filing gate, `canFileFrozen`, the opinion and freeze controls are
  untouched.
- **Portfolio (D10).** Inside the refusal block, only for `INTAKE_ISSUER_AMBIGUOUS`, one
  sentence names the advanced path with links: "create the case" (`#cases-create`, the
  create panel gained that id), "Sources" and "Run" (`withQuery` with the selected case,
  plain words when no case is selected). The intake surface still posts files and nothing
  else (the unit test counts its two inputs).
- **Credit (the "Shell 1440 / 720" artboards).** No change; §2 puts the screenshots
  beside the exports.
- **Documents.** `caos/frontend/docs/control-capability-map.md`: the Admin rows now read
  "Served and drawn on Admin (FE-G3, D7)", the Report provisioning row moved to Admin,
  withdrawal stays "served, not drawn" (no approved artboard draws it), and the header
  paragraph records what FE-G3 drew.
- **Not changed, deliberately.** No server file. No token. No panel interior beyond the
  three decisions. `Workspace.tsx` stays one file; the authority machine and the reducer
  are untouched (the reducer tests are unchanged: 138 unit tests, none weakened).

## 2. Screenshots beside the artboards

Retained under `.superpowers/sdd/frontend/evidence/g3/` with `SHA256SUMS`. The artboards
were rendered from their committed `.dc.html` working files in Chromium (they render
standalone); the app screenshots come from the host-control app on `:8771` driven by a
scratch Playwright script (two document-first intakes through `POST /api/intake`: a
Full Credit pack accepted through `POST /api/runs/{id}/accept`, and a Deep Research pack
paused on `PLAN_APPROVAL_REQUIRED`), then the ambiguous pack dropped through the UI.

| Artboard (export, SHA-256) | App state (screenshot, SHA-256) | Differences, and why |
|---|---|---|
| Align — Shell 1440 (`artboard-align-shell-1440.png`, `a271d279…6bfc4d`) | Credit, accepted Full Credit intake, 1440×1000 (`app-credit-1440.png`, `9a4c04e5…9e6d3`) | None in layout, hierarchy, states or copy: accepted record, conclusion, proof and gaps with the "Binding measure and claim gaps — Not available in this deployment" block, "Read accepted analysis" / "Review latest run", the analyst boundary "versioned in Report". Identities and dates differ (fixture data). |
| Align — Shell 720 (`artboard-align-shell-720.png`, `697b5806…d59`) | Credit at 720×900, full page (`app-credit-720.png`, `3a216d3d…3cac`) | Same reflow: single column, rail band on top. The artboard's rail band is 136 px (FE-D1 §5 measured delta) against the app's 121 px, because the artboard re-emits the 900 px media block at frame width; same CSS, recorded in FE-D1, not a product difference. |
| Align — Analysis paused (`artboard-align-analysis-paused-1440.png`, `5bc66a90…0437`) | Run, intake-created Deep Research run paused on plan approval, 1440 full page (`app-run-paused-1440.png`, `f28d0639…6524`; 720: `app-run-paused-720.png`, `4704e0c7…5fe8`) | Layout, hierarchy, states and copy match: execution route with the three tiles and "Pending approval", "Acceptance blocked — Review and approve the persisted research plan below.", the persisted plan, "Approve research plan" as the one visible primary, "Advanced: compile a route" closed at the bottom. One difference: the artboard's first line "✓ 3 documents admitted. DEEP RESEARCH at full depth selected by host classification. Execution started." is the workspace's mutation receipt, present only in the session that submitted the intake; a document load of the run (this screenshot) carries no receipt, by design (receipts are not persisted). |
| — (no artboard) | Admin with a case, 1440 and 720 (`app-admin-1440.png`, `33df191b…1969`; `app-admin-720.png`, `d869e84a…06d7`) | D7's result: contracts table with the two served rows, the "Case governance" panel with the download and, for this ANALYST-standing identity, the provisioning rule instead of the form. Retained as the record of what D7 drew; no artboard binds it. |
| — (no artboard) | Portfolio, `INTAKE_ISSUER_AMBIGUOUS` refusal, 1440 (`app-portfolio-ambiguous-refusal-1440.png`, `2db8a14c…a3d2`) | D10's result: the typed refusal with the server's next action and the advanced-path sentence with its three links. |

Full digests are in `SHA256SUMS`. Every drawn state is reachable in the running app
under host control (the two intakes above) or by a fixture the sweep drives: the paused
run with the disclosure is the sweep's `pending-plan` fixture (now with
`latest_intake_id` and an intake route, and asserted closed), and the Admin form is the
sweep's new `admin-governance` fixture at 1440 and 720.

## 3. UX-011 to UX-017 map

| Check | Retained proof |
|---|---|
| UX-011 facts, machine analysis, analyst edits, opinion, limitations and approval state as distinct content | Smoke: the accept dialog names run, pathway, source set, slots and the replaced digest (`workbench-smoke.mjs` ~1156–1172); Report's freeze checklist rows "Write access", "Exact saved revision", "Current model selection", "Required model availability", "Current opinion sign-off" and the `opinion-record` (`ReportStudio.test.ts` "freeze remains a reserved approval sequence…"); the frozen payload's `approval_state: "PENDING APPROVAL"` (~2265). New here: on an intake-created run the governed result and its one primary lead and the compile form is a disclosure (D11 step in the intake loop, "an intake-created run still leads with the compile form"). |
| UX-012 no provider picker; signed model selection, scenario, revision and sign-off controls preserved | Unit: `workbench.test.ts` "no shipped frontend file carries an HTML or script sink" plus the compile form offers pathway and depth only (`#pathway`, `#depth`; no provider field — `RunConsole` source). Smoke: model sign-off, revision, scenario and rebase steps (~1327–1500, "Model authority changed"). |
| UX-013 same workflow and controls for every qualified model choice | Smoke: the served-cut steps (`#pathway` outside-cut disabled, one-pathway cut enabled, empty cut disabled, ~928–936) and the Report pathway-template steps (~2085–2167) drive the same controls per pathway. |
| UX-014 unsaved edits protected across navigation, refresh, reconnect and history | Smoke: `beforeunload` armed on a dirty draft and disarmed on discard (~1521–1617), the native prompt on navigation (~1664), the draft-discard dialog on pathway change (~2099–2116), the history fence (~2040). Unit: "draft navigation uses one focus-returning native dialog and preserves beforeunload". Unchanged by this task; the accept dialog and the discard guards keep their synchronous paths (no edit touched them). |
| UX-015 a reader inspects evidence and run history without write controls | Smoke reader leg (~2455–2500): "Reader access" on Portfolio, `absent` for Create case / Analyze documents / Upload and version / Compile and run / Accept analytical snapshot / Upload CP-3 workbook, and new here `absent(readerPage, "Provision member")` on Admin with "Reader access: member provisioning is an analyst action." while the audit-package download (a read) stays. Unit: the Admin test pins the `WriteBlocked` branch. |
| UX-016 an analyst reviews and signs an opinion without approver-only filing controls | Smoke: "Sign opinion on saved v…" (~2230), "the opinion signer was offered File" assertion (~2295). Provisioning is no longer on Report at all (unit: Report "no longer provisions"). |
| UX-017 an approver compares the exact frozen preview before filing | Smoke: approver identity switch, FROZEN record selected, "Request changes" and "File exact Frozen version" gating, the detached receipt `rcpt_frozen_report_2` (~2296–2338). Provisioning of that distinct approver now lives on Admin and is proven on a route-intercepted document (~540–562: the POST body is exactly `{subject, role}`, the receipt names the standing, the form clears). |

Line numbers are from `scripts/workbench-smoke.mjs` at this commit.

## 4. Test literals that moved, with their commit

All in the code commit (§7).

| Test file | Before | After |
|---|---|---|
| `src/components/report/ReportStudio.test.ts` "approver provisioning is one governed mutation available to a case admin" | pinned `/members`, `canProvision ? <form … data-member-form`, the standing rule and the APPROVER/ADMIN options in `ReportStudio.tsx` | replaced by "Report no longer provisions members: the governed mutation lives on Admin (FE-A1 D7)": `doesNotMatch data-member-form|/members`|canProvision|addMember`, and the filing gate still pinned (`canFileFrozen(role, subject`). This was the one red-first test: it failed after the code change and before the move. |
| `src/lib/workbench.test.ts` (new) "the compile form collapses into 'Advanced: compile a route' on an intake-created run (FE-A1 D11)" | — | the intake read gate on Portfolio and Run, the `fromIntake` prop, the two homes of `{compileForm}`, exactly one "Compile and run", the summary CSS, and the smoke pins `details.run-advanced` / "an intake-created run still leads with the compile form" |
| `src/lib/workbench.test.ts` (new) "Admin draws the two served governance contracts and Report no longer provisions (FE-A1 D7)" | — | the five contract rows (two served with "download below" / "provisioned below", three absent), the `networkFetch` download with the `x-caos-sha256` header and the 404 → unavailable branch, `canProvision` with the standing rule, the form and its options, the `WriteBlocked` and no-standing branches, `provisionMember` (POST body, receipt, `refreshCase`), Report's absence of the form, and the smoke pins "Download audit package" / "provisioned as case APPROVER." / `absent(readerPage, "Provision member")` |
| `src/lib/workbench.test.ts` (new) "the ambiguous-issuer refusal points at the advanced path (FE-A1 D10)" | — | the exact refusal sentence with its three links, `id="cases-create"`, two inputs in the intake panel, the smoke pin `INTAKE_ISSUER_AMBIGUOUS` |
| `scripts/workbench-smoke.mjs` Admin step | five-row contracts check only | plus the live audit-package download (200, 64-hex digest, receipt with filename and compacted digest), the no-standing rule, and the route-intercepted provisioning document (`/api/me` ADMIN, case `members` with ADMIN standing, `POST /members` 201) |
| `scripts/workbench-smoke.mjs` intake loop | index 0 only (Full Credit → "Open review" → accept) | index 1 added: Deep Research → "Open Run" → `details.run-advanced` closed, `#pathway` hidden, exactly one visible `main .button.primary`, the summary opens the form |
| `scripts/workbench-smoke.mjs` refusal step | one malformed-PDF refusal | plus a two-issuer pack refused `INTAKE_ISSUER_AMBIGUOUS` with the three links and no case created |
| `scripts/workbench-smoke.mjs` reader leg | six `absent` checks | plus Admin: `absent("Provision member")`, the reader sentence, the download present |
| `scripts/a11y-axe.mjs` `pending-plan` fixture | case without an intake | `latest_intake_id`, an `/intake` route naming the run, and the assertion that `details.run-advanced` is closed before the scan |
| `scripts/a11y-axe.mjs` (new) `admin-governance` fixture | — | Admin with a case on an ADMIN identity with ADMIN standing at 1440 and 720, axe plus the page-overflow check; the combination literal moved from `+ 21` to `+ 23` and the summary gained `adminGovernanceAxeChecks: 2` |

Pinned names that did **not** change: "Accept analytical snapshot", "Approve research
plan", "Compile and run", "Open review", "Provision member" (same name, new home), every
dialog and drawer name, the "Required administrative contracts" region and its five row
headers.

The three new unit tests were written after the code (the Report pin was the red-first
one); their anti-vacuity was checked by mutation in §5.

## 5. Gates

All from `caos/frontend` on the final tree. Combined app: this worktree's
`caos/server/dev.py` and `worker.py` under `ENVIRONMENT=development
CAOS_PROVIDER=host_control AGENT_EXECUTION_ENABLED=true ANTHROPIC_API_KEY=` with a scratch
data directory, started detached from the primary checkout's `.venv` (Python 3.14.6):
`:8771` for the smokes and the first sweep, `:8772` (fresh data) for the second sweep.

| Gate | Command | Result |
|---|---|---|
| Red-first | `npm run test:unit` after the code change, before the test move | 1 fail: `ReportStudio.test.ts` "approver provisioning is one governed mutation available to a case admin" (the form left Report) |
| Lint | `npm run lint` | `ESLint: No issues found` |
| Types | `npx tsc --noEmit` | `TypeScript: No errors found` |
| Unit | `npm run test:unit` | `ℹ tests 138 / ℹ pass 138 / ℹ fail 0` (135 before; three added, one replaced) |
| Anti-vacuity | five mutations of `Workspace.tsx`, one at a time, `npm run test:unit` each, file restored and re-verified | all five CAUGHT by the test that pins them: open form kept beside an intake run (D11), disclosure never rendered (D11), provisioning without stored standing (D7), 404 reported as an error not unavailable (D7), advanced path without its Run link (D10) |
| Build | `npm run build` | `✓ Generating static pages using 5 workers (20/20)` |
| Workbench smoke, Chromium | `CAOS_URL=http://127.0.0.1:8771 CAOS_BROWSER=chromium npm run test:workbench` | first run failed at the new Admin step on a strict-mode locator (the digest matched the visible span and its `sr-only` twin; fixed with `.first()`); second run `{"browser":"chromium","browser_version":"151.0.7922.34","status":"passed","duration_ms":143373}`, timing `domContentLoaded 63.2 / firstContentfulPaint 160`, budget enforced |
| Workbench smoke, Firefox | `CAOS_BROWSER=firefox …` (60 s after the sweep) | `{"browser":"firefox","browser_version":"153.0","status":"passed","duration_ms":153050}` |
| Workbench smoke, WebKit | `CAOS_BROWSER=webkit …` (75 s after Firefox) | `{"browser":"webkit","browser_version":"26.5","status":"passed","duration_ms":153557}`; no D-016 prefetch rejection |
| Accessibility sweep, populated server | `CAOS_URL=http://127.0.0.1:8771 npm run a11y` (60 s after the Chromium smoke) | `{"routes":17,"forwarders":8,"viewports":6,"combinations":125,"pendingPlanFixture":true,"adminGovernanceAxeChecks":2,…,"states":["empty","populated","review","filed","loading","error","refusal"],…,"violations":0}` — but the server log shows **142 × 429** inside the route loop (see below) |
| Accessibility sweep, fresh server | `CAOS_URL=http://127.0.0.1:8772 npm run a11y` (fresh data directory, empty register) | the same summary, `violations: 0`, and **0 × 429** on that server's log |
| Server log after every gate on `:8771` | `grep -c " 429 "`, `grep -c -E " 50[0-9] "`, worker tracebacks, `audit-package` requests | 142 / 0 / 0 / 6 (the six audit-package exports are the three smokes' download step plus the evidence script) |
| Backend suite, Ruff | — | not run: no server file changed |

**The 142 refusals.** They sit entirely inside the populated sweep's route loop (log
lines 5317–6870, before the `admin-governance` fixture marker), not in any smoke. The
register auto-selects its first case, which on a server the smoke has just populated is
an intake-created case with a run; every one of the loop's 102 page loads then fetches
that run and its event tail, and the tail's replay triggers a `GET /api/runs/{id}` per
delivered event — about ten per page — so the loop runs past the per-subject
`rate_limit_per_minute = 300` bucket and the later pages of each minute render 429
states for their panels. The sweep stays green because a refused panel is still an
accessible error state, which is exactly why the Task 8 and 9 reports run the sweep
against a fresh server; this task did both and quotes both. Nothing in this change adds
to that loop's cost except the `/intake` read on Run when the case names an intake (16
of the 142 were that path; the run refetches were 59). The follow-up is recorded in §6.
CI runs the sweep after the smoke on one server and has passed the same way since Task
12b; whether it should use a fresh data directory is an FE-G4 / CI decision.

## 7. Commits

| Commit | Content |
|---|---|
| `d50b997` (was `9353033` before the rebase, below) | `feat(frontend): Run to the Align artboard, governance controls on Admin, the advanced path on refusal` — `Workspace.tsx`, `ReportStudio.tsx`, `globals.css`; `workbench.test.ts`, `ReportStudio.test.ts`; `workbench-smoke.mjs`, `a11y-axe.mjs` |
| `95df2af` (was `dab857e`) | `docs(frontend): capability map — provisioning and the audit package are drawn on Admin` |
| `64dbf6c` (was `e1d1679`) | this file, `progress.md`, `evidence/g3/` (ten PNGs and `SHA256SUMS`) |
| `da79ee1` (was `3c9c636`) | `docs(sdd): record the FE-G3 pull request URL` |
| (fix commit) | `fix(frontend): provisioning clears its form with the receipt; the smoke's Deep Research leg returns to its case` — `Workspace.tsx`, `workbench.test.ts`, `workbench-smoke.mjs`, and this report's §9 |

## 9. After the pull request opened: the rebase and two CI failures

While the first CI run (`34028165311`, head `3c9c636`) was in flight, `main` took PR #70
(the backend suite under pytest-xdist in CI) and PR #71 (`webkit-teardown.mjs`: drop the
D-016 rejections that emit no `requestfailed`), and the branch was rebased onto
`387e6d1` and force-pushed by the pull-request babysit loop, not by this session
(same four commits, new hashes above; `git diff 3c9c636 origin/claude/fe-task-03-surfaces`
is exactly main's two commits). That first run had already failed WebKit on the D-016
class this task's local WebKit run did not hit — the journey's final console-error check
retained
`/admin/__next.$d$destination.__PAGE__.txt?case=…&_rsc=… due to access control checks.`,
a Next prefetch of the Admin payload rejected at a document navigation with no evidence
under the old rule — which is what #71 fixes; the rerun on the rebased branch passed
WebKit.

The rebased run (`34029799042`, head `da79ee1`) failed Chromium and Firefox on the new
FE-G3 steps, both real ordering defects the local runs had passed by luck:

- **Chromium, 13 s in, the provisioning step:** "the form kept the provisioned subject
  after the receipt". `provisionMember` resolved only after `await refreshCase(...)`, so
  the receipt (`setNotice`) rendered while the form still held the subject until the
  case re-read landed. Root cause in the app, not the harness: the write's completion
  was two renders. Fixed: the write resolves on the POST, the receipt and the cleared
  form land in one render, and `void refreshCase(...)` follows on its own; the unit pin
  moved with it; the smoke waits for the cleared field with `waitForFunction`.
- **Firefox, 64 s in, the fenced-intake-header check:** the new Deep Research leg ended
  on a bare `/portfolio/`, whose auto-selected first case has no intake, so
  `getByText(/^Last intake /)` never appeared. Fixed: the leg returns to its own case's
  Portfolio and waits for the manifest, restoring the state the following check expects.

Local proof of the fix (fresh host-control server on `:8773`): unit 139/139 (one test
came with #71), lint and tsc clean, build 20/20, Chromium smoke passed (144844 ms),
Firefox smoke passed (154971 ms).

## 8. Confidence review

Scope: `9353033`. Ranked by likelihood × blast radius.

1. **`fromIntake` on a hard load of Run** — worried the intake record is only read on
   Portfolio, so a document load of `/run/` would never collapse the form. Investigated:
   the read effect's gate now includes Run; the sweep's `pending-plan` fixture is a
   document load of `/run/` with an intake route and asserts the disclosure is closed
   before the scan. → fine (sweep, both servers).
2. **The intake read effect refetching per render** — worried the widened gate loops.
   Investigated: unchanged short-circuit (`intake.case_id === caseId && intake.intake_id
   === latestIntakeId`), deps unchanged; the populated sweep's log shows one `/intake`
   per page load (16 in the loop). → fine.
3. **A stale intake from another case marking a run as intake-created** — investigated:
   `fromIntake` requires `intake.case_id === caseId` and `intake.run?.id === run.id`; a
   case switch clears `intake` (`commitCaseSelection`). → fine.
4. **The closed disclosure hiding "Compile and run" from the reader checks** —
   `absent(readerPage, "Compile and run")` counts visible roles; a reader never gets the
   form (`WriteBlocked`) in either home. → fine (reader leg green in three engines).
5. **The provisioning form's standing rule on Admin drifting from the server's** —
   investigated: same predicate Report used (`role ∈ {APPROVER, ADMIN}` and stored
   `members[subject] ∈ {APPROVER, ADMIN}`), the server's `require_case_approver` plus
   `store.add_member(actor_role=None)`; the smoke identity (ANALYST standing) sees the
   rule, the intercepted ADMIN identity sees the form. → fine; the first standing
   remains BLOCKED (§6).
6. **The audit download on WebKit** — worried the blob anchor is unobservable there.
   Investigated: the smoke asserts the `/audit-package` response (200, 64-hex digest)
   and the on-screen receipt, never the download event; WebKit passed. → fine.
7. **The populated sweep's 429s degrading scanned pages** — CONFIRMED as a harness
   condition, not a product defect; measured on the log, explained in §5, reproduced
   clean on a fresh server, follow-up in §6. patch → none in product; both results
   quoted.
8. **`main .button.primary:visible` counting a rail or dialog primary** — investigated:
   the rail is outside `main`, no dialog is open at that step, Approve is the only
   `.button.primary` rendered while paused. → fine (three engines).
9. **Mutation coverage of the new tests** — five mutations, all caught (§5).

Fixed: the strict-mode digest locator in the new smoke step. Verified fine: 1–6, 8, 9.
By-design: none. Still open: 7 as a harness follow-up (§6).

## 6. Follow-ups and BLOCKED

- **BLOCKED (server): the first APPROVER/ADMIN standing.** No served route creates it
  (F-12); the case creator gets ANALYST standing (`storage/store.py::create_case`), and
  `POST /members` requires stored APPROVER/ADMIN standing plus a current APPROVER/ADMIN
  role. So the provisioning control on Admin is proven live only as "the rule, not the
  control" for the smoke identity, and the control itself on a route-intercepted document.
  Route needed: a bootstrap that grants the first case APPROVER/ADMIN standing under an
  audited policy (a server decision outside this series, as D7 records).
- **No artboard, no decision — deferred to FE-G4:** F-04 (drawer copy "no block locator"
  while chips carry block ids; the `?source` landing does not select the cited block),
  F-13 (Model and Analysis say nothing to a reader about hidden write controls), F-18
  (the reader renders markdown tables as pipe text), F-19 (Report opens on Full Credit
  regardless of the accepted pathway; frozen and filed histories scoped per template),
  the interior headings that still say "Model Builder" / "Report Studio"
  (`ModelBuilder.tsx` panel h2 and load error, `ReportStudio.tsx` load error and
  pathway-change prompt), and withdrawal / notes (served, not drawn; D-G).
- **The intake receipt line on Run.** The artboard shows the intake receipt above the
  route because the canvas was drawn from a session that had just submitted the pack;
  the app shows it in that session too and not on a document load. Persisting the
  receipt would be a new surface state with no decision behind it; not done.
- **F-20 still holds.** Model READY/STALE, the Full Credit freeze and filing remain
  route-mocked on a keyless server; nothing here changes that.
- **The populated sweep trips the request ceiling (§5).** Options for FE-G4 or the CI
  owner: run `npm run a11y` against a fresh data directory in CI (as the Task 8/9 reports
  did locally), make the sweep pass `CAOS_CASE_ID` for a case without a run, or teach
  the sweep to assert that no `/api/*` response in a scanned page was a 429 so a
  degraded scan is red rather than silently green. The run-tail replay cost itself
  (about ten `GET /api/runs/{id}` per page load of a terminal run) is the frontend's
  refetch-per-event rule and is not changed here.
