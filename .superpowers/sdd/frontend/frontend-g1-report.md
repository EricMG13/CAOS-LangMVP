# FE-G1 report — land the code-audit fixes without changing the IA

Executed as `FE-G1` (2026-09-05) in `.claude/worktrees/caos-workbench-ia-directions-07795b`
on branch `claude/frontend-a0-repairs-1799f2`, cut from `main` at `af5ae15` (the FE-D1
merge, PR #62). Frontend: Node 24.16.0, `npm ci` (351 packages). Backend interpreter for
the combined app: the primary checkout's `caos/server/.venv` (Python 3.14.6); `dev.py`
runs from this worktree's `caos/server`, so `caos` resolves here. Host-control app on
`:8769` with a worker beside it and a scratch data directory
(`ENVIRONMENT=development CAOS_PROVIDER=host_control AGENT_EXECUTION_ENABLED=true
ANTHROPIC_API_KEY= PORT=8769 CAOS_DATA_DIR=<scratch>/dev-data-g1`), started detached
(`subprocess.Popen(..., start_new_session=True)`) because the Bash tool's background
mode kills long-lived servers. Browsers: Playwright's chromium 151.0.7922.34, firefox
and webkit from the machine cache.

Inputs read before the first change: the standing preamble and the frontend addendum;
`frontend-a0-code-audit.md` (findings F1–F18, §3 contract drift, §4 test vacuity, §5
blast radius, §6 decisions D-A–D-I, §7 commit plan); `## Decisions` in
`frontend-a1-ia-audit.md` (D1–D12; D9 assigns the superseded-acceptance state to
FE-G1); `frontend-a2-design-truth.md` §9 (findings for FE-G1) and §11 (delta tables);
`Workspace.tsx`, `WorkbenchShell.tsx`, `EvidenceChip.tsx`, `ModelBuilder.tsx`,
`ReportStudio.tsx`, `reportRecovery.ts`, `api.ts`, `workspaceAuthority.ts`,
`workbench.ts`, `states.tsx`, `globals.css`, every unit test, `workbench-smoke.mjs`,
`a11y-axe.mjs`, `scratch/vacuity.mjs` and `scratch/probe3.mjs`,
`control-capability-map.md`, the CLAUDE.md frontend entries,
`.superpowers/sdd/loops/focus-race-findings.md`, `.github/workflows/nightly.yml`.

## Status

COMPLETE on the branch. Twenty-one commits in the audit's commit-plan order (sixteen
plan items and five same-finding follow-ups the browser gates and the mutation harness
forced), each carrying its test; every finding the audit ranked high is fixed, every
medium is fixed, the lows are fixed except the two the audit itself sends elsewhere;
the contract-drift and test-vacuity tables are applied; no route, slug, rail label,
kicker, page title or destination changed; `Workspace.tsx` is one file; the reducer
changed only through its unit tests; no server response model changed; the a11y
literal count is untouched. A draft pull request to `main` is open: https://github.com/EricMG13/CAOS-LangMVP/pull/63 (not merged).

## Decisions applied

The decision owner recorded (frontend-a1-ia-audit.md, "## Decisions") that "the
audit's recommendations be applied as the answers". The A0 questions D-A–D-I are
therefore answered by their first (recommended) option; the quotes below are the
audit's own words.

- **D-A** (F2) — "Key the recovery copy by subject, case and pathway, refuse a copy
  whose subject differs, and add a per-tab id so two tabs never share one slot."
  Applied in `d2d117d`.
- **D-B** (F5) — "Render a typed 'Case unavailable' state that names the requested id
  and keeps the URL, and auto-select the first case only when no case was requested."
  Applied in `85f56b9`.
- **D-C** (F4) — "Scope `resumeUnavailable` and `approvalUnavailable` to the run id
  they were observed on (reset on run change) and treat a run-scoped 404 as a typed
  refusal in the console." Applied in `1c06079`; the block on the observed run names
  both readings of the 404.
- **D-D** (F8) — "Replace the static 'Not served' table with an accurate list (audit
  package served, membership served, step-up absent) while the screens stay
  unavailable." Applied in `d37597c`.
- **D-E** (F7) — "Map a fetch `TypeError` to one sentence ('Network unavailable. Check
  the connection and retry.') in `firstErrorMessage` and keep the raw text out of the
  DOM." Applied in `292f4d3`, at the fetch boundary (`networkFetch`) so the mapping
  cannot mislabel a programming `TypeError`; `firstErrorMessage` renders the typed
  error's sentence.
- **D-F** — "Keep tornado as the only sensitivity control and correct the map's
  wording." Applied in `d7f834b`.
- **D-G** — "Record withdraw and notes as 'served, not drawn' and let FE-A1/FE-G3
  decide whether Sources draws withdrawal." Applied in `d7f834b`.
- **D-H** — "Send the sweep's presence assertions, the missing WEB-004 states and
  WEB-006 modes, the dead `page.once('dialog')`, and the timing-budget scope to a
  browser-gate hardening commit run by the FE-L1 loop or a small FE-G1b; keep every
  product fix and the unit-test rewrites in FE-G1." Applied: commit 15 is deferred
  (see "Deferred"), except the dead `page.once("dialog")`, which the test-vacuity table
  names and which the prompt asked to apply; it is replaced in `f1d838a` without
  touching the sweep or its literal.
- **D-I** — "Let FE-G4 delete the View toggle, utility-drawer and five-action toolbar
  rules the product does not implement." Left for FE-G4; the A2 delta wording marks
  them "not implemented" in `d7f834b` rather than deleting them, because FE-D2 has
  not run.
- **A1 D9** — "A previously accepted run whose snapshot has been superseded renders an
  'accepted, superseded' state and never a live 'Accept analytical snapshot' (F-14);
  frontend only, through `acceptedAuthorityMatch` and `RunStatus`, with its unit
  test." Applied in `93a20be` (+ `08700cf`).

## Commits, in the audit's commit-plan order

Every commit was staged by explicit path (or by reconstructed blob for the files several
commits share) and committed with `git commit -F` and the repository trailer; none was
amended. Fast gates (lint, tsc, unit) ran before each commit; the browser evidence per
commit names the tree it ran on.

| # | Commit | Audit item | What changed | Test carried | Browser evidence |
|---|---|---|---|---|---|
| 1 | `31d2f86` | F1 (high) | `scrubberCommitDecision`; scrubbers no longer keyed on the draft generation | `modelBuilderState.test.ts` +1; smoke Tabs FY2026→FY2027, no tornado, no preview | Chromium smoke passed 134,255 ms on the tree at this commit |
| 1b | `ed8cccf` | F1 follow-up | scrubbers keyed on their committed value (the effect showed the value a render late; one instant read raced it) | same | covered by the final run |
| 2 | `bedf337` | F10 | one focus-restoration owner: dialog retry chain deleted, repair effect runs on dialog close with the recorded trigger, re-finds by id then aria-label; `scripts/focus-restoration-smoke.mjs` + `npm run test:focus` + nightly step | existing smoke assertions at the four prompts; focus soak | Chromium smoke passed 135,903 ms; focus soak chromium 8/8, webkit 8/8 (tree at commits 2+3 uncommitted) |
| 3 | `292f4d3` | F7 (D-E) | `NetworkError`/`networkFetch` for every request helper and both raw fetches | `api.test.ts` +1 (three engines' texts); smoke asserts the sentence after the aborted `/api/me` | as above |
| 4 | `d2d117d` | F2 (high, D-A) | recovery slot per subject, case, pathway, tab; subject refusal; `browserTabId` | `reportRecovery.test.ts` rewritten; smoke: app writes the copy, save clears it, second subject offered nothing | Chromium smoke passed 141,704 ms (tree at commit 9) |
| 5 | `c118ee3` | F6 | intake record cleared on case switch; header fenced to the case | smoke selects the idle case, asserts the idle sentence | as above |
| 6 | `1c06079` | F4 (D-C) | observed-404 memory holds the run id | smoke: 404 on one run, control present on the next | as above |
| 7 | `03e02a7` | F9 | effective pathway from the served cut; empty cut disables | smoke: one-pathway cut, empty cut, no POST | as above |
| 7b | `e923f86` | F9 follow-up | `startRun` refuses an empty pathway itself (a scripted `requestSubmit()` bypasses the disabled button) | smoke asserts the sentence | as above |
| 8 | `85f56b9` | F5 (D-B) | typed "Case unavailable" state; URL kept; first case only when none requested | smoke `:405-412` rewritten | as above |
| 9 | `d37597c` | F8 (D-D) | Admin Studio truth table | smoke reads every row's state | as above |
| 10 | `b8f3a24` | F3 (high) | Credit and Analysis render the shell's snapshot; artifacts only, refetched when the accepted set changes; one loading state for identity and proof | `workbench.test.ts` literal changed in the same commit; smoke answers a different id per read and asserts strip = credit screen | Chromium smoke passed 143,205 ms (tree at commit 10) |
| 11 | `f9fd449` | F11 | `DrawerState.opener` from the click; CLAUDE.md entry updated | smoke: Escape returns focus to the chip | covered by the commit-12 run |
| 12 | `3660edb` | F12, F14, F15, F16 | dead reducer field and event removed through the tests; two dead SSE names; stable `openPalette`; no dialog motion | `workspaceAuthority.test.ts` loses the dead assertion | first run failed on the commit-1 effect race (fixed in 1b); rerun passed 142,592 ms at the docs commit |
| D9 | `93a20be` + `08700cf` | A1 F-14 | `supersededAcceptance`; "Accepted, superseded" branch | `workbench.test.ts` +1; smoke geometry fixture gains the phase | as above |
| A2 | `60fe381` | A2 F-01, F-11, F-12 | `.button.is-active`; `--caos-ink`; `auto` header row | `workbench.test.ts` +3 (every `var()` resolves; toggle rule; header row) | as above |
| 13 | `d7f834b` | §3 drift, A2 §11 | capability map, CLAUDE.md polyfill entry, addendum sentence, DESIGN.md, .impeccable.md | none (docs) | — |
| 14 | `f1d838a` | §4 vacuity | see the table below | unit +2, −5; smoke +2 steps, dialog listener | first final run failed: the "dead" `page.once("dialog")` was accepting Chromium's native beforeunload prompt (fixed in 14b) |
| 14b | `6d96afe` | §4 follow-up | the smoke accepts and counts the native beforeunload prompt (asserted ≥1 on Chromium), fails on any alert/confirm/prompt; the report JSON carries the count | — | every engine raised exactly one |
| 14c | `018df28` | §4 follow-up (mutation run) | the three hand-rolled request barriers race a 30 s deadline that names the missing request (M7 had hung the smoke for thirteen hours instead of failing it); the drawer step adds a scripted-click pass so the focus return depends on the passed opener alone (M10 and M13 survived a real click in Chromium, whose native dialog restoration masks both) | — | final run below |

Also in commit 2: `.github/workflows/nightly.yml` gains one step that runs the focus soak
in every engine after the accessibility sweep (`caos/tests/test_workflow_security.py`:
22 passed).

## Findings, fixed and deferred

| Finding | Severity | Outcome |
|---|---|---|
| F1 blur commits and remounts | High | Fixed (`31d2f86`, `ed8cccf`) |
| F2 recovery copy shared across subjects and tabs | High | Fixed (`d2d117d`) |
| F3 two accepted identities on one screen | High | Fixed (`b8f3a24`), by the audit's second option: no second `/snapshot` read; the shell's snapshot is the one authority |
| F4 session-wide 404 memory | Medium | Fixed (`1c06079`) |
| F5 silent first-case substitution | Medium | Fixed (`85f56b9`) |
| F6 stale intake header | Medium | Fixed (`c118ee3`) |
| F7 engine text on network failure | Medium | Fixed (`292f4d3`) |
| F8 false "Not served" | Medium | Fixed (`d37597c`) |
| F9 compile form outside the cut | Medium | Fixed (`03e02a7`, `e923f86`) |
| F10 two focus owners | Low | Fixed (`bedf337`) |
| F11 drawer opener inferred | Low | Fixed (`f9fd449`) |
| F12 dead reducer state | Low | Fixed (`3660edb`) |
| F13 `q` reflected as "Evidence request" | Low | **Deferred.** Text node only; the audit's own recommendation names no change and FE-G2/FE-G3 own that strip. Recorded as a follow-up. |
| F14 shortcut effect re-subscribes | Low | Fixed (`3660edb`) |
| F15 dead SSE names; `document.title` effect | Low | SSE names fixed (`3660edb`). The title effect is **not dead** — see "Audit claims refuted" — and stays. |
| F16 dialog motion | Low | Fixed (`3660edb`) |
| F17 vacuous unit tests | Test | Fixed (`f1d838a` and the per-commit tests) — table below |
| F18 a11y sweep asserts nothing rendered | Test | **Deferred** to the gate-hardening commit per D-H; it moves the sweep's literal count |
| A1 F-14 superseded acceptance | (D9) | Fixed (`93a20be`, `08700cf`) |
| A2 F-01 `.is-active` toggles | High | Fixed (`60fe381`) |
| A2 F-11 undefined `--caos-paper-ink` | Medium | Fixed (`60fe381`) |
| A2 F-12 32px header row | Medium | Fixed (`60fe381`) |
| A2 F-02, F-03 dead tokens and classes; F-04 disabled primary contrast; F-05 `th[scope=row]`; F-06 9px floor; F-07 720px rail | Low–Medium | **Deferred**: visual-language decisions or FE-G4 doc rules, not code defects; the DESIGN.md wording now records F-04, F-06, F-07 and F-08 as open |

## Audit claims refuted or adjusted while applying them

- **F15 "the `document.title` effect is dead."** Refuted for client-side navigation. A
  Playwright probe on this build (`scratch/title-probe.mjs`) read the static and
  hydrated title as `CAOS — Cases`, then, after clicking Credit and then Model in the
  rail, `CAOS — Current state and what changed` and `CAOS — Assumptions, lineage and
  sign-off` — the effect's `destinationMeta.title`, not Next's route metadata. Removing
  it would change the tab title after every client navigation, which this task must not
  do; FE-G2 unifies the four vocabularies and decides the title. The audit's S11 probe
  measured only the static and hydrated title.
- **A2 F-09 vs A0 F16 on the dialog rise.** A2 recorded the 180 ms dialog entrance as a
  sanctioned animation; A0 F16 called it decorative and the commit plan drops it. The
  decision owner's instruction applies A0's recommendations, so it is removed and the
  A2-derived DESIGN.md/.impeccable.md wording says "no dialog entrance motion".
- **F9 "disable submit when none is enabled" is not enough.** The smoke's scripted
  `form.requestSubmit()` still posted `pathway: ""`; the handler now refuses too
  (`e923f86`).
- **Commit 2's design needed one more fact.** The browser's own close restoration fires
  `focusin` on whatever it lands on (the editor, when the select raised the prompt) and
  the focus tracker overwrote the remembered trigger before the effect ran; the effect
  now reads the prompt's recorded trigger (`discardTriggerRef`). The first run of the
  commit-2 smoke failed at the pathway-select prompt for exactly this reason.

## Test-vacuity table, applied

The audit's twelve mutations (`scratch/vacuity.mjs`) plus one for F11, rerun on the
final tree with `scratch/vacuity-g1.mjs` (unit suite per mutation; for the mutations
only a browser can catch, a rebuild and the Chromium smoke against `:8769`, files
restored from git after each). Results:

every mutation is caught; the per-mutation record is under "Mutation run" below.

| Mutation | Before (audit) | Now catches it | Where |
|---|---|---|---|
| M1 arrow-key handler deleted | survives unit; smoke | smoke | `workbench-smoke.mjs` worksheet ArrowDown/ArrowRight (audit `:1243`) |
| M3 READER edits forecasts | survives unit; smoke | smoke | READER `isDisabled` (audit `:1408`) |
| M4/M4b beforeunload inert | survives all | unit (`protectDirtyDraftUnload` behaviour) + smoke (synthetic beforeunload cancelled while dirty, untouched after discard) | `workbench.test.ts`; smoke |
| M5 identity fails open | survives unit; smoke | smoke | aborted `/api/me` floor (audit `:2285-2294`) |
| M6 recovery never written | survives all | smoke (`localStorage` read after an edit) | smoke, `d2d117d` |
| M7 case authority never refreshed | survives unit; smoke | smoke (the held `/api/cases/{id}` barrier, bounded at 30 s since `018df28` — before that the catch was a hang) | smoke |
| M8 colour-only status | survives all | unit (glyph shapes per tone; `content: none` refused) | `workbench.test.ts` |
| M9 raw-HTML sink in the reader | survives all | unit (sink scan over every shipped file) | `workbench.test.ts` |
| M10 drawer focus never restored | survives all | smoke (scripted-click open, Escape → `awaitFocus(chip)`; a real click in Chromium is masked by native dialog restoration) | smoke, `f9fd449`, `018df28` |
| M11 cross-case run guard removed | survives unit; smoke | smoke (audit `:456`) | smoke |
| M12 no SSE subscription | survives unit; smoke | smoke (intake review wait, audit `:629`) | smoke |
| M13 (new) drawer opener inferred again | — | smoke (the same scripted-click pass; the real-click pass catches it in WebKit only) | smoke, `018df28` |
| `page.once("dialog")` | auto-accepts | persistent listener records and fails the run | smoke |
| `:405-412` pins F5 | pins the substitution | asserts the typed state and the kept URL | smoke |
| `authorityRequests <= 12` | slack for a doubled read | **unchanged** — one snapshot read per screen now, but tightening the bound is gate work (D-H) | — |
| a11y sweep presence / states / modes; timing budget scope | — | **deferred** (D-H, commit 15) | — |

Deleted as vacuous (the smoke drives the behaviour): `ModelBuilder.test.ts` "worksheet
keyboard navigation…", "readers can inspect but cannot change…", "unknown identity roles
fail closed…", the `beforeunload` line in "forecast edits preview…";
`ReportStudio.test.ts` "unsaved report work has a scoped non-authoritative recovery
copy…"; `workspaceAuthority.test.ts` "case authority refresh follows every reducer
generation". Kept: the route-table pin (the IA fence) and every structural pin the audit
did not call vacuous.

## Blast-radius table, re-checked against the final tree

Line numbers moved; no literal was added or removed except where noted. Counts are
occurrences of the `${baseURL}/<route>/` form in the smoke.

| File | Literal(s) | Lines now | Change from the audit |
|---|---|---|---|
| `src/lib/workbench.ts` | `routeDestinations`; `destinationMeta`; `workflows`; `destinationFromSlug` fallback "Cases" | 1–11; 21–31; 98–106; 274 | unchanged (+`supersededAcceptance` helper above `acceptanceSlotSummary`) |
| `src/lib/workbench.test.ts` | route table; `withQuery` samples; "Accept analytical snapshot" | 50–58; 254–256; 283, 400 | +40 lines of new tests above the route pins |
| `src/components/WorkbenchShell.tsx` | `/cases`, `/sources`, `/admin-studio`; "Admin Studio", "Run Console", "Report Studio"; nav names; "Sources & evidence"; "Page not found" | 251–299, 327 | +5 lines (opener comment, `useCallback`) |
| `src/components/Workspace.tsx` | destination switch and `EmptyPanel` `/cases/`; `/command-center`; `/run-console` ×5; `/sources` ×4; `/deep-dive`; "Monitored credits"; "Accepted analysis"; "Deployment capability"; slug read `:53` | 1067–1077 (switch), 1100 (Open Cases), 1120, 1184, 1231, 1516, 1531, 1684, 1691, 1693, 1777, 1795, 1859, 1865, 1886 | file is 1,890 lines (was 1,862); the "Case unavailable" block (`:1098`) and the Admin table (`:1886`) are new literal sites for FE-G2 to keep |
| `src/components/model/ModelBuilder.tsx` | `/run-console` "Open Run Console" | 725 | unchanged |
| `src/components/report/ReportStudio.tsx` | `/model-builder` ×2, `/run-console` | 640–641 | unchanged |
| `src/components/report/ReportStudio.test.ts` | `withQuery("/model-builder"…)`, `withQuery("/run-console"…)` | 82–83 | unchanged |
| `app/[destination]/page.tsx`, `app/not-found.tsx` | route params and title; `/cases/` | 3–17; 8, 15 | unchanged |
| `scripts/workbench-smoke.mjs` | routes: `/cases/` ×7, `/command-center/` ×6, `/deep-dive/` ×2, `/model-builder/` ×4, `/report-studio/` ×8, `/run-console/` ×11, `/rv-screener/` ×1, `/sources/` ×3, **`/admin-studio/` ×1 (new)**; rail labels `:471`; "Monitored credits" `:501`; "Evidence focus" `:513` (two-ancestor depth kept); "Accept analytical snapshot" ×9 (+1, the superseded phase); "Analyze documents" ×5; "Visible authority" ×9; "Select case" ×13; "Open command palette" ×5; **new**: "Case unavailable" `:411`, "Required administrative contracts" `:493`, `pushState` to `/run-console/?case=…&run=…` (F4 step), `fixture=cut` and `fixture=alternating-snapshot` query loads | file is 2,500 lines (was 2,335) | FE-G2 must move the new `/admin-studio/` load and the F4 `pushState` path with the rest |
| `scripts/focus-restoration-smoke.mjs` (**new**) | `/model-builder/` `:67`; "Select case" `:74`; "Sources" link `:79`; "Open command palette" `:84`, `:90` | — | one more script for FE-G2's route rename |
| `scripts/a11y-axe.mjs` | routes array `:18`; `combinations` literal `:336` | unchanged | untouched |
| `docs/control-capability-map.md` | surface names | 12–39 | table grew from 16 to 28 rows; same surface names |
| `DESIGN.md`, `.impeccable.md`, `CLAUDE.md`, `PRODUCT.md`, `CONTEXT.md` | destination names | `.impeccable.md:14–17` now says nine destinations plus the rail's seven workflows; `DESIGN.md` §5 anatomy no longer names destinations | FE-G2 rewrites the destination sentence |

Also route-shaped: the wrapper key `${active}:${caseId}` (`Workspace.tsx:1099`) still
remounts on destination change — D2's forwarding pages must replace history before that
key changes.

## Deferred

- **Commit 15, gate hardening (D-H).** Route sweep presence assertions, READER/stale/
  failed/succeeded/partial states, a 360 px viewport, tornado mocked in the ready-model
  fixture, the `combinations` literal. Quoted decision: "Send the sweep's presence
  assertions, the missing WEB-004 states and WEB-006 modes, the dead `page.once('dialog')`,
  and the timing-budget scope to a browser-gate hardening commit run by the FE-L1 loop or
  a small FE-G1b." The prompt also fixes the a11y literal: "the a11y sweep's literal count
  moves only if a route or viewport moves, which this task does not do."
- **F13** `q` reflection (text node; FE-G2/G3 own the strip).
- **`authorityRequests <= 12`** in the smoke: the bound could tighten now that Credit and
  Analysis read no snapshot of their own; measuring the new ceiling belongs with the gate
  work.
- **A2 F-02/F-03** dead tokens and classes, **F-04** disabled-primary contrast, **F-05**
  `th[scope=row]` styling, **F-06** the 9 px floor, **F-07** the 720 px rail, **F-08**
  the `partial` component: visual-language decisions for FE-G4/FE-D2; recorded as open
  in DESIGN.md.
- **`.impeccable/design.json`** sidecar (A2 §11.3): FE-G4 regenerates or deletes it.
- **D-I** anatomy rules: marked "not implemented", deletion is FE-G4's.
- **Cross-engine smoke in CI** already runs (nightly); the focus soak joins it.

## Gates on the final commit (`018df28`)

Run from `caos/frontend` against the export built from this commit and the host-control
app on `:8769`, with a 70 s pause between browser gates so the per-subject request
ceiling (300/min) refills — the first chain on `6d96afe` had run the a11y sweep straight
into the WebKit smoke and that smoke saw ten 429s on `/api/runs/…` and timed out at an
unrelated wait. The same chain passed on `6d96afe` before the last commit (chromium
144,979 ms, webkit 152,192 ms, firefox 156,198 ms, a11y 75/0, soak 8/8 ×3); the run
below is the one on the final tree.

```
npm run lint                                              → ESLint: No issues found
npx tsc --noEmit                                          → TypeScript: No errors found
npm run test:unit                                         → ℹ tests 131 ℹ pass 131 ℹ fail 0
npm run build                                             → ✓ Generating static pages using 5 workers (12/12) in 309ms
CAOS_URL=http://127.0.0.1:8769 CAOS_BROWSER=chromium node scripts/workbench-smoke.mjs
  → {"browser":"chromium","timing":{"domContentLoaded":62.6,"firstContentfulPaint":144},"budgetEnforced":true,"caseRequests":1}
  → {"browser":"chromium","browser_version":"151.0.7922.34","status":"passed","duration_ms":151615}   console_errors 0, beforeunload_prompts 1
CAOS_URL=http://127.0.0.1:8769 node scripts/a11y-axe.mjs
  → {"routes":9,"viewports":6,"combinations":75,"pendingPlanFixture":true,"readyModelFixture":true,"readyReportFixture":true,"states":["empty","populated","review","filed","loading","error","refusal"],"modelBuilderAxeChecks":12,"modelBuilderKeyboardTabChecks":3,"reportStudioAxeChecks":3,"reportStudioKeyboardTabChecks":3,"violations":0}
CAOS_URL=http://127.0.0.1:8769 CAOS_BROWSER=webkit node scripts/workbench-smoke.mjs
  → first run: {"browser":"webkit","browser_version":"26.5","status":"failed","duration_ms":145351}   console_errors 1: "/127.0.0.1:8769/run-console/__next.$d$destination.__PAGE__.txt?case=…&_rsc=… due to access control checks." — WebKit's rejection of a Next prefetch still in flight at navigation (CLAUDE.md, D-016), kept as an error because the page carried no server evidence for it; webkit_teardown_rejections 0; the assertion is the smoke's final `errors` check at :2363, every journey step had passed
  → rerun after 70 s: {"browser":"webkit","browser_version":"26.5","status":"passed","duration_ms":158650}   console_errors 0, webkit_teardown_rejections 0, beforeunload_prompts 1
CAOS_URL=http://127.0.0.1:8769 CAOS_BROWSER=firefox node scripts/workbench-smoke.mjs
  → {"browser":"firefox","browser_version":"153.0","status":"passed","duration_ms":163220}   console_errors 0, beforeunload_prompts 1
CAOS_URL=http://127.0.0.1:8769 CAOS_BROWSER=<engine> node scripts/focus-restoration-smoke.mjs
  → chromium passes 8 fails 0 harnessErrors 0; webkit 8/0/0; firefox 8/0/0
```

The a11y literal is unchanged: 9 routes, 6 viewports, `combinations: 75` as the audit
recorded. The three-engine smoke and the focus soak are more than the prompt's gate
list asks for (Chromium smoke and a11y); they are quoted because commit 2 and commit 11
are WebKit-motivated fixes and commit 14c's drawer pass is engine-sensitive. The one
WebKit failure is the documented D-016 class (a same-origin prefetch WebKit rejects at
navigation on a loaded runner, here right after the a11y sweep), not a journey step; the
smoke keeps it as an error by design when the page holds no evidence for it, and the
rerun on the same export passed.

## Mutation run

Harness: `.superpowers/sdd/frontend/scratch/vacuity-g1.mjs` (the audit's `vacuity.mjs`
mutations plus M13 for F11; per mutation `npm run test:unit`, then for the mutations only
a browser can catch a `sleep 70`, `npm run build` and the Chromium smoke against the
host-control server on `:8769`, the file restored from git afterwards; every smoke bounded
at 480 s). Log: `.superpowers/sdd/frontend/evidence/vacuity-g1.log`, in the order the
runs happened. M1, M3, M4 and M5 ran first with the harness's earlier unit invocation (a
shell glob that reached 71 of the 131 tests); every later mutation ran the full suite.
The harness does not run the rest of the unit suite in isolation, so "caught by unit"
names the failing test and the count beside it.

| Mutation | Unit | Smoke (Chromium) | Verdict |
|---|---|---|---|
| M1 arrow-key handler deleted | 71/71 | `worksheet ArrowDown did not move one row \| 'A1' !== 'A2'` | caught by smoke |
| M3 READER edits forecasts | 71/71 | `READER could edit an assumption \| false !== true` | caught by smoke |
| M4 beforeunload body inert | 71/71 | `a dirty draft did not arm beforeunload \| false !== true` | caught by smoke |
| M5 identity fails open (`useState("ANALYST")`) | 71/71 | `READER was offered "Create case" \| 1 !== 0` | caught by smoke |
| M6 recovery never written | 131/131 | `an edit did not write a subject-scoped recovery copy` | caught by smoke |
| M7 case authority never refreshed | 131/131 | `the command center never requested the selected case's authority` (30 s bound, `c14c`) | caught by smoke |
| M8 success glyph → `content: none` | 130/131, `DAG nodes use neutral containers and shape-coded visible statuses` | — | caught by unit |
| M9 `dangerouslySetInnerHTML` in the artifact reader | 130/131, `no shipped frontend file carries an HTML or script sink` | — | caught by unit |
| M10 drawer focus restore removed | 131/131 | `closing the evidence drawer opened by a scripted click did not return focus to the chip that passed itself as opener (on BODY[])` | caught by smoke (scripted-click pass, `c14c`) |
| M11 cross-case run guard never fires | 131/131 | `Timeout 30000ms exceeded … waiting for getByText('Requested run does not belong to the selected case.')` — the cross-case run rendered instead of the refusal | caught by smoke |
| M12 SSE tail subscribes to nothing | 131/131 | `Timeout 60000ms exceeded … waiting for getByRole('heading', { name: 'Proposed research plan' })` — no event, no refetch, the intake review never appears | caught by smoke |
| M13 opener inferred from `activeElement` | 131/131 | `closing the evidence drawer opened by a scripted click did not return focus to the chip that passed itself as opener (on BODY[])` | caught by smoke |

What the run corrected on the way, all of it kept in the log:

- **Two mutations did not compile as the audit wrote them**, so their first records
  read "build failed", which is not a catch. M6's `if (copy) return true;` narrows `copy`
  to `never` (TS2339 on the next line); the rerun uses `if (Date.now() > 0) return true;`.
  M11's `if (false) {` leaves `context.caseId` unnarrowed at `Workspace.tsx:435` (TS2322);
  the rerun keeps the guard and makes its condition unsatisfiable
  (`&& !next.case_id`). Both variants remove the behaviour and nothing else.
- **M7 was a hang, not a failure.** The first two harness runs sat inside the M7 smoke for
  thirteen and six hours: the smoke awaited its held `/api/cases/{id}` request with no
  bound. `c14c` races the three hand-rolled barriers against a 30 s deadline that names
  the request that never came; M7 now fails in 30 s with that sentence.
- **M10 and M13 survive a real click in Chromium.** A click focuses the chip there, so the
  browser's own `<dialog>` close restoration returns focus whether or not the shell does;
  only the WebKit leg of the CI matrix (where a click focuses nothing) could tell. `c14c`
  adds a scripted-click pass to the drawer step (`element.click()` focuses nothing in any
  engine), so the return depends on the opener the chip passed (F11) alone. M13 was caught
  by that pass on its first run with the new step; M10's first run predates it and was
  rerun.
- **M12's first record is void**: its mutation was overwritten from this session while the
  harness was between its unit run and its build (an unrelated `git checkout` of the same
  file), so that smoke ran on a clean tree and "passed". The rerun is the record.

## Commands run and results

Baseline (`caos/frontend`, tree at `af5ae15`):

```
npm ci --no-audit --no-fund       → added 351 packages
npm run lint                      → ESLint: No issues found
npx tsc --noEmit                  → TypeScript: No errors found
npm run test:unit                 → ℹ tests 130 ℹ pass 130 ℹ fail 0
npm run build                     → 12/12 static pages; grep -c nomodule out/cases/index.html → 0; ls out/_next/static/chunks | grep polyfill → (none)
curl :8769/api/health             → {"status":"ok","store":true,"bundle":true,"checkpointer":true}
```

Per-commit browser runs (all `CAOS_URL=http://127.0.0.1:8769 CAOS_BROWSER=chromium node scripts/workbench-smoke.mjs` after `npm run build`):

```
tree at 31d2f86 (+ uncommitted commit-2 edits made after the build)   → status passed, 134,255 ms
tree at bedf337+292f4d3 (uncommitted), first attempt                    → failed at :1872 "dirty pathway cancel did not return focus to the pathway selector" (fixed: discardTriggerRef)
same, second attempt                                                     → passed 135,903 ms; focus soak chromium 8/8 0 fail, webkit 8/8 0 fail
tree at 03e02a7                                                          → failed at :873 "the compile form posted a pathway outside the served cut" (fixed: e923f86)
tree at d37597c                                                          → passed 141,704 ms
tree at b8f3a24                                                          → passed 143,205 ms
tree at 3660edb                                                          → failed at :1386 "all-year broadcast did not update every registry year" (commit-1 effect race; fixed: ed8cccf)
tree at 60fe381 (build raced a concurrent globals.css edit: exit 254; the smoke ran on the stale export and failed at :1018 "acceptance region did not preserve its reserved height" — the D9 sentence wrapped; fixed: 08700cf)
tree at d7f834b                                                          → passed 142,592 ms
```

Title probe (`scratch/title-probe.mjs`, Chromium, served export at `d37597c`):

```
{"staticTitle":"CAOS — Cases","hydrated":"CAOS — Cases","afterClientNavigation":"CAOS — Current state and what changed","afterSecondNavigation":"CAOS — Assumptions, lineage and sign-off"}
```

Backend (no server file changed; the nightly workflow gained a step):

```
caos/server/.venv/bin/python -m pytest caos/tests/test_workflow_security.py -q -p no:cacheprovider → 22 passed in 0.12s
caos/server/.venv/bin/python -m ruff check --config ruff.toml caos/server caos/tests --exclude caos/server/caos/methodology/vendor → All checks passed!
git diff --stat af5ae15..HEAD -- caos/server → (empty)
```

Mutation harness (`caos/frontend`, host-control app on `:8769`; every run's JSON lines in `evidence/vacuity-g1.log`):

```
CAOS_URL=http://127.0.0.1:8769 node ../../.superpowers/sdd/frontend/scratch/vacuity-g1.mjs            → run 1 (tree at 6d96afe): M1, M3, M4, M5 CAUGHT by smoke; M6 "build failed" (did not compile); killed at M7 (hang)
CAOS_URL=http://127.0.0.1:8769 node ../../.superpowers/sdd/frontend/scratch/vacuity-g1.mjs M6 … M13   → run 3 (tree at 6d96afe + the c14c smoke edits, uncommitted): M6, M7, M13 CAUGHT by smoke; M8, M9 CAUGHT by unit; M11 "build failed" (did not compile); M10 SURVIVES (real click, Chromium); M12 void
CAOS_URL=http://127.0.0.1:8769 node ../../.superpowers/sdd/frontend/scratch/vacuity-g1.mjs M10 M11 M12 → run 4 (tree at 018df28): M10, M11 CAUGHT by smoke; the harness died with the session during M12
CAOS_URL=http://127.0.0.1:8769 node ../../.superpowers/sdd/frontend/scratch/vacuity-g1.mjs M12         → run 5 (tree at 018df28): M12 CAUGHT by smoke
SUMMARY over the last record of each mutation: M1 M3 M4 M5 M6 M7 M10 M11 M12 M13 caught by smoke; M8 M9 caught by unit; nothing survives
```
