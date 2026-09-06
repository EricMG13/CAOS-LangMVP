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

## 10. Second pass on main (2026-09-06, branch `claude/frontend-surfaces-approved-ia-98bf71`)

Executed in `.claude/worktrees/frontend-destination-migration-1f874e` from `main` at
`bfeda07` (the FE-G3 merge, PR #72). The FE-G3 prompt was re-issued verbatim after #72
had merged, so this pass takes the residual of its goal, not a redraw: (1) the interior
copy FE-G2 §6 handed to FE-G3 ("Panel interiors are FE-G3's scope") and §6 above
deferred, which is the one place a surface still rendered its pre-IA interior name;
(2) the evidence the prompt's "done means" asks for and §2 retained only for the three
artboards — a screenshot of every destination in every reachable drawn state at 1440 and
720; (3) a drifted row in the capability map that #72's own documentation commit left.
Assumption stated: everything the Align record binds is in scope, nothing it does not
draw is approximated (§10.5). Frontend: Node 24.16.0; backend for the combined app: the
primary checkout's `caos/server/.venv` (Python 3.14.6) running this tree's `dev.py` and
`worker.py`.

### 10.1 Changes

- **Interior copy names the destination, not the old surface.** `ModelBuilder.tsx`: the
  three panel headings `<h2>Model Builder</h2>` read `<h2>Model</h2>` and the load
  fallback reads `Unable to load Model.`; `ReportStudio.tsx`: the load fallback and the
  `LoadState` title read `Unable to load Report.`, and the pathway-change prompt reads
  `Discard the unsaved draft before changing pathway?` (the dialog is already headed
  "Discard draft changes?", so the body no longer names a surface); `states.tsx`: the
  comment that named the three surfaces. DECISIONS §14.23 binds one word in the URL, the
  rail, the palette, the kicker and the tab; the Align record's summary is "one vocabulary
  end to end", and a panel headed "Model Builder" under the kicker "Model / Forecast" was
  the last seam. No layout, hierarchy or state changed.
- **Unit pin.** `workbench.test.ts` "no surface interior names the old destination as a
  place (FE-G3, one vocabulary end to end)": for `ModelBuilder.tsx`, `ReportStudio.tsx`,
  `WorkbenchShell.tsx` and `Workspace.tsx`, no non-comment line matches
  `Model Builder|Report Studio|Run Console|Command Center|Deep[- ]Dive|RV Screener|Admin Studio`
  (the assertion names the offending line), and the four new strings are pinned. Red
  first: 1 fail on the tree before the rename (`assert.equal(offending, undefined)` on
  the `<h2>Model Builder</h2>` line), 140/140 after.
- **Load-bearing literal moved with the code.** `scripts/production-inventory.mjs:507`
  `errorText: "Unable to load Report Studio."` → `"Unable to load Report."`. That script
  is not in CI and cannot pass against this build (`CLAUDE.md` known gaps); the pair is
  named here because it was the only file pinning the old copy. No smoke, sweep or unit
  literal pinned any of the renamed strings (`grep` over `scripts/` and `src/`: the hits
  were assertion *messages* and test names, not page text).
- **Capability map.** `docs/control-capability-map.md`: the row
  "Admin | Membership | POST …/members | Served; drawn in Report Studio (see above)"
  contradicted the row two lines above it ("Served and drawn on Admin (FE-G3, D7)") and
  is deleted; the Admin provisioning row already carries the served route and its rule.
- **Not changed.** No server file, no token, no route, no test weakened; the reducer
  tests are untouched (`workspaceAuthority.test.ts` unchanged, 140 unit tests). The
  Credit and Run artboards were re-verified on this tree (§10.2), not redrawn.

### 10.2 Every destination in every drawn state

Retained under `.superpowers/sdd/frontend/evidence/g3/pass2/` (57 PNGs, `SHA256SUMS`).
Live states come from a fresh host-control server on `:8783` populated only through
`POST /api/intake` (a Full Credit pack accepted through `POST /api/runs/{id}/accept`, a
Deep Research pack paused on `PLAN_APPROVAL_REQUIRED`, a Relative Value pack with the
CP-3 workbook, accepted) and one ambiguous pack dropped through the surface; fixture
states are the accessibility sweep's own route fixtures, captured by a scratch fork of
`scripts/a11y-axe.mjs` that screenshots at each scan point (20 captures, 0 axe
violations). 1440 captures are the viewport (1440×1000, the artboard frame); 720
captures are full page at 720×900 (200 % desktop zoom). Every capture reported
`overflow: false` (no page-level horizontal scroll) and no page error.

| Destination / state | Artboard | App captures (`SHA-256`) | Differences, and why |
|---|---|---|---|
| Portfolio | none | `empty-portfolio-1440.png` `e3f9131b…f5d4`, `empty-portfolio-720.png` `fa0c905d…98f0`, `populated-portfolio-1440.png` `a38c004f…3c61`, `populated-portfolio-720.png` `07180b1e…8996` | No artboard. Empty: the register says no credits and the intake panel is the one primary ("Analyze documents"); populated: the register, the case's last intake manifest with the labelled host classification and the "Analysis complete — review it" block whose one primary is "Open review". Refusal (D10) below. |
| Credit | Align — Shell 1440 / 720 (`artboard-align-shell-1440.png` `a271d279…bfc4d`, `artboard-align-shell-720.png` `697b5806…dd59`) | `empty-credit-1440.png` `1d1c654b…0ece`, `empty-credit-720.png` `bf811485…0c61`, `populated-credit-1440.png` `231c971f…2995`, `populated-credit-720.png` `c1702486…c01d` | Matches the artboard in layout, hierarchy, states and copy (accepted record, conclusion, proof and gaps with the "Binding measure and claim gaps — Not available in this deployment" block, "Read accepted analysis" primary, "Review latest run", the analyst boundary "versioned in Report"). Identities and dates are fixture data. Empty: the route-level empty with "Open Portfolio". |
| Sources | none | `empty-sources-1440.png` `6199d138…e083`, `empty-sources-720.png` `bba9611e…31f4`, `populated-sources-1440.png` `3d5b22df…82b7`, `populated-sources-720.png` `35ef6342…b42e` | No artboard. Empty: route-level empty. Populated: register, immutable source reader, evidence support with the "Claim coverage — Not available in this deployment" block; the upload form is the one write. |
| Analysis | none | `empty-analysis-1440.png` `70cde895…29a2`, `empty-analysis-720.png` `6aa85452…290e`, `populated-analysis-1440.png` `401e178a…1bec`, `populated-analysis-720.png` `4f795e0b…0679` | No artboard. Populated: the accepted-module list, the reader on the deterministic payload (sections, artifact identity), the evidence rail with three cited sources. The QA table renders as pipe text (F-18, deferred, no decision). |
| Run | Align — Analysis paused (`artboard-align-analysis-paused-1440.png` `5bc66a90…0437`) for the paused state; no artboard for the empty or accepted state | `empty-run-1440.png` `30f5d1a2…bc5b`, `empty-run-720.png` `3c878fe1…4680`, `populated-run-1440.png` `3355b76d…35da`, `populated-run-720.png` `463fc065…3843` | Accepted state (no artboard): the execution route with 17 succeeded tiles, "Latest accepted authority" with the snapshot id, and the compile form collapsed to "Advanced: compile a route" because the run came from intake (D11). Paused state: matches the artboard — three tiles, "Pending approval", "Acceptance blocked — Review and approve the persisted research plan below.", the persisted plan, "Approve research plan" as the one primary, the disclosure closed at the bottom; the artboard's receipt line is the submitting session's mutation receipt and is absent on a document load (as #72 recorded). |
| Market | none | `empty-market-1440.png` `142a8e32…2910`, `empty-market-720.png` `aba8b68a…ddc7`, `populated-market-1440.png` `5cdfba9a…3014`, `populated-market-720.png` `ce2e1a8e…b959` | No artboard. Empty: route-level empty. Populated (the Relative Value intake's case): the workbook upload, "Active authority — ACTIVE · v1" with the source link and digest, the loan screener, and "Relative percentile unavailable" stated in words. |
| Model | none | `empty-model-1440.png` `267eef3d…778c`, `empty-model-720.png` `b021d985…8f67`, `populated-model-1440.png` `89822311…32ea`, `populated-model-720.png` `1c1034c6…f2ce` | No artboard. Populated under host control: the panel now headed "Model" (this pass) with status "CANONICAL MODEL INPUTS INVALID" and its typed blocker; a READY model is a fixture state (below), never live on a keyless server (F-20). |
| Report | none | `empty-report-1440.png` `b34849df…118d`, `empty-report-720.png` `5def21ff…b04c`, `populated-report-1440.png` `93d9a51f…2836`, `populated-report-720.png` `00067642…9b5f` | No artboard. Populated: structure, compose and the paper preview on the dark workspace; "What will bind" names the exact saved revision. Follow-up noticed, not changed: "Draft authority vUnavailable" concatenates a version prefix onto the unavailable marker (§10.6). |
| Admin | none | `empty-admin-1440.png` `f96139c2…5cfb`, `empty-admin-720.png` `2e6f3099…8efd`, `populated-admin-1440.png` `b4a3cd0f…602e`, `populated-admin-720.png` `353d814e…08ad` | No artboard (D7 record from #72). Populated with a case: PARTIAL flag, the five-row contracts table with the two served rows, the "Case governance" panel with "Download audit package" and, for this ANALYST-standing identity, the provisioning rule instead of the form. |
| Run, paused on `PLAN_APPROVAL_REQUIRED` (Deep Research intake) | Align — Analysis paused | `paused-run-1440.png` `b1413007…4694`, `paused-run-720.png` `124cb913…9339` | See the Run row; the one drawn state beyond the shell. |
| Portfolio, `INTAKE_ISSUER_AMBIGUOUS` refusal (D10) | none | `refusal-ambiguous-portfolio-1440.png` `b45805d9…be77` | Typed refusal, the server's next action, and the advanced-path sentence with its three links ("create the case", Sources, Run); no case created. |
| Reader (UX-015) on Portfolio, Run, Model, Admin | none | `reader-portfolio-1440.png` `e13c61c2…602a`, `reader-run-1440.png` `b379def0…4906`, `reader-model-1440.png` `6a3bd7a6…c303`, `reader-admin-1440.png` `976c2f8c…4056` | No write control on any of the four; Portfolio and Admin say why in a sentence; Model and Run say nothing to the reader (F-13, deferred, no decision). |
| Run, pending plan at 720 (sweep fixture) | Align — Analysis paused | `pending-plan-desktop-200-percent.png` `d1ffb10b…d749` | The sweep's `pending-plan` fixture: single column, disclosure closed, the plan's explicit empty markers. |
| Admin governance (sweep fixture, ADMIN standing) | none | `admin-governance-desktop-1440.png` `20a019cd…bd7e`, `admin-governance-desktop-200-percent.png` `4ff2993a…f254` | The provisioning form itself (subject, standing, "Provision member") beside the download; the state the smoke's route-intercepted document proves. |
| Model READY (sweep fixture) | none | `ready-model-desktop-1440-credit-snapshot.png` `fc34e76f…2c3c`, `ready-model-desktop-200-percent-credit-snapshot.png` `f44403a5…eb37` | Worksheet tabs, the assumptions and tornado panels, the sign-off control; the panel heading reads "Model". |
| Report ready (sweep fixture) | none | `ready-report-desktop-1440.png` `63573057…956d`, `ready-report-desktop-200-percent.png` `68d6f1d4…6d6b` | The paper preview on a signed active revision; freeze checklist rows. |
| Report review and filed (sweep fixtures) | none | `state-review.png` `ba2a6dc3…02de`, `state-filed.png` `19730a84…cd9e` | "Immutable FROZEN review" with "Pending approval · the frozen bytes never name an approver"; the FILED record with its detached receipt. |
| Credit loading and error (sweep fixtures) | none | `state-loading.png` `68994266…4080`, `state-error.png` `118155ea…5b15` | The skeleton (`role=status` "Loading"); the typed 503 as "STORE UNAVAILABLE" over "Unable to load this view." with Retry, the proof column degrading to its own unavailable blocks. |
| Portfolio refusal (sweep fixture) | none | `state-refusal.png` `6a1342ef…6f36` | "Documents not admitted" with the per-file finding. |

The three artboard exports and their digests are unchanged from §2 (`artboard-align-*.png`
in `evidence/g3/`). States the canvas names that this app has no surface for — "stale",
"partial" and "offline" as page-level states — exist only where the server serves them:
Model's `STALE` revision state and Admin's `PARTIAL` flag are drawn (the fixture and the
populated Admin capture); an offline state is the typed network failure rendered as the
error block (`state-error.png`) and is not a separate design; none is approximated.

### 10.3 UX-011 to UX-017 on this tree

The §3 map holds; line numbers moved with #71 and the #72 fix commit. Current
`scripts/workbench-smoke.mjs`: UX-011 accept dialog 1124–1175, `approval_state` 1845/2268,
D11 disclosure 756; UX-012 `#pathway`/`#depth` only (no provider field; unit "no shipped
frontend file carries an HTML or script sink"); UX-013 served-cut steps and the
per-pathway Report template steps; UX-014 `beforeunload` 1667, the history fence
2124–2135, the discard dialog 1529 — the accept dialog and both discard guards keep
their synchronous paths (untouched by this pass); UX-015 reader leg 2542–2559 plus the
four reader captures in §10.2; UX-016 2233 and 2298; UX-017 2252–2341 (the receipt
`rcpt_frozen_report_2`), provisioning 540–558.

### 10.4 Gates

All from `caos/frontend` on the final tree. Servers: `:8781` (smokes), `:8782` (fresh
data, the sweep), `:8783` (fresh data, the evidence script), each `dev.py` + `worker.py`
under `ENVIRONMENT=development CAOS_PROVIDER=host_control AGENT_EXECUTION_ENABLED=true
ANTHROPIC_API_KEY=` with a scratch `CAOS_DATA_DIR`.

| Gate | Command | Result |
|---|---|---|
| Red-first | `npm run test:unit` with the new pin, before the rename | `ℹ fail 1` — "no surface interior names the old destination as a place" (`<h2>Model Builder</h2>`) |
| Lint | `npm run lint` | `ESLint: No issues found` |
| Types | `npx tsc --noEmit` | `TypeScript: No errors found` |
| Unit | `npm run test:unit` | `ℹ tests 140 / ℹ pass 140 / ℹ fail 0` |
| Build | `npm run build` | `✓ Generating static pages using 5 workers (20/20)` |
| Smoke, Chromium | `CAOS_URL=http://127.0.0.1:8781 CAOS_BROWSER=chromium npm run test:workbench` | `{"browser":"chromium","browser_version":"151.0.7922.34","status":"passed","duration_ms":142981}`; timing `domContentLoaded 75.8 / firstContentfulPaint 200`, budget enforced |
| Smoke, Firefox | `CAOS_BROWSER=firefox …` | `{"browser":"firefox","browser_version":"153.0","status":"passed","duration_ms":152860}` |
| Smoke, WebKit | `CAOS_BROWSER=webkit …` (70 s after Firefox) | `{"browser":"webkit","browser_version":"26.5","status":"passed","duration_ms":150589}` |
| Server log `:8781` after the three smokes | `grep -c " 429 "`, `grep -c -E " 50[0-9] "`, worker tracebacks, `audit-package` | 0 / 0 / 0 / 4 |
| Accessibility sweep, fresh server | `CAOS_URL=http://127.0.0.1:8782 npm run a11y` | `{"routes":17,"forwarders":8,"viewports":6,"combinations":125,"pendingPlanFixture":true,"adminGovernanceAxeChecks":2,"readyModelFixture":true,"readyReportFixture":true,"states":["empty","populated","review","filed","loading","error","refusal"],"modelBuilderAxeChecks":12,"modelBuilderKeyboardTabChecks":3,"reportStudioAxeChecks":3,"reportStudioKeyboardTabChecks":3,"violations":0}`; 0 × 429 on that server's log |
| Backend suite, Ruff | — | not run: no server file changed |

### 10.5 Not approximated, and BLOCKED

- Unchanged from §6: the first APPROVER/ADMIN standing stays **BLOCKED (server)** — route
  needed: an audited bootstrap for the first case admin; the provisioning control is
  proven on the sweep's fixture and the smoke's route-intercepted document.
- No artboard, no decision, therefore not drawn here: F-04, F-13 (Model and Run say
  nothing to a reader — visible in `reader-model-1440.png` and `reader-run-1440.png`),
  F-18 (pipe-text tables in the reader — visible in `populated-analysis-1440.png`),
  F-19, withdrawal and notes (served, not drawn).
- The intake receipt line on Run (the artboard's first line) remains a session
  receipt, not persisted state.

### 10.6 Follow-ups noticed, not changed

- Report's "What will bind" renders `Draft authority vUnavailable` on a case with no
  saved draft (`populated-report-1440.png`): the version prefix is concatenated onto
  the unavailable marker. Copy defect in `ReportStudio.tsx`, outside this pass.
- The ambiguous-pack capture scrolled to the alert, so the register above it is cut
  off; the state is the alert, so the capture stands.

### 10.7 Confidence review (this pass)

1. **A hidden pin on the renamed copy** — worried a smoke `getByRole("heading", { name:
   "Model Builder" })` or the sweep's model fixture would break. Investigated: grep over
   `scripts/` and `src/` finds the phrases only in assertion messages, test names and
   comments, plus the one inventory `errorText` moved above; three smokes and the sweep
   green. → fine.
2. **`firstErrorMessage` fallbacks read by a `.includes("Unable")`** — investigated:
   that check is on `message` (action receipts), not `loadError`; unchanged. → fine.
3. **The new pin passing vacuously** — the regex excludes comment lines only; a JSX
   heading, a string literal or a template is checked; red-first proved it fires on
   the heading, and the four `assert.match` lines fire if the new copy drifts. → fine.
4. **Duplicated title and body on the Report load failure** (`title="Unable to load
   Report."` and the fallback message identical) — pre-existing shape (the two strings
   differed only by a period before); only the case where the server returns no detail.
   → by design, unchanged.
5. **The evidence server's "populated" Model state** — worried it would read as a defect.
   It is `CANONICAL_MODEL_INPUTS_INVALID`, the host-control ceiling (F-20), stated in the
   table. → fine.

Fixed: none needed. Verified fine: 1–3, 5. By-design: 4.

### 10.8 Commits (this pass)

| Commit | Content |
|---|---|
| `d29d716` | `feat(frontend): surface interiors name the destination, not the old surface (FE-G3 second pass)` — `ModelBuilder.tsx`, `ReportStudio.tsx`, `states.tsx`, `workbench.test.ts`, `production-inventory.mjs`, `control-capability-map.md` |
| (report commit) | this section, the `progress.md` row, `evidence/g3/pass2/` (57 PNGs and `SHA256SUMS`) |
| (PR commit) | `progress.md` gains the pull-request URL |
