# FE-A0 — adversarial code audit of `caos/frontend`

Date: 2026-09-05. Tree: `claude/frontend-adversarial-audit-631726` at `ea42a2d` (identical to `main`; working tree clean apart from this directory). Assessment only: no source, test, style, script or plan file was changed; no commit; no stash. Evidence files, scratch harnesses and the retained browser reports live under `.superpowers/sdd/frontend/evidence/` and `.superpowers/sdd/frontend/scratch/`. The host-control app for the browser gates ran on `:8766` with its own data directory in the session scratchpad and a worker beside it.

## 1. Verdict

The authority core is sound and the browser gates are green. The `workspaceAuthority` reducer and every shell call site that arbitrates case, run and snapshot against stale responses hold up under the smoke's held-response races (stale run re-attach, cross-case run, late Case A acceptance after switching to Case B, late run creation) and under my own review; I found no route replay that changes authority except the deliberate first-case fallback on an unknown deep link (F5). The SSE tail is correct by construction: the server writes `id:` per event and closes only after a terminal run is fully delivered, the client never reads payloads, `refreshRun` keeps only the newest response, so duplicates and out-of-order events cost a refetch and nothing else. Every string that reaches the DOM is a React text node; the tree has no `dangerouslySetInnerHTML`, `innerHTML`, `srcdoc`, `eval` or `javascript:` sink (grep of `src` and `app`), so WEB-012 holds. Status is never colour alone: every `.status` tone draws a distinct glyph shape and the run and node states also carry text. The accept dialog is digest-bound, takes its opener from the click, and the run console is the only surface that compiles or accepts. CI on `main` has all three browser engines green on the last three runs (`33798306565`, `33884057611`, `33957919360`), the focus-return defect from issue #38 was fixed in Task 12b, and an isolated harness reproduced the exact dirty-draft history sequence 8 of 8 times without a failure, so the starting hypothesis that the browser job is red at `workbench-smoke.mjs:1251` is refuted for the current tree.

What must be fixed before any IA change, because an IA change would otherwise inherit and be blamed for it: the Model Builder commits every blur even when nothing changed, which unmounts every forecast input, strands keyboard focus on `<body>` on every Tab and fires a tornado request each time (F1, reproduced); the Report Studio recovery copy is keyed by case and pathway only, so one subject's unsaved draft is offered to the next subject on the same browser profile (F2, reproduced); the shell and the Command Center read the snapshot independently and can show two different accepted snapshot ids on one screen with no warning (F3, reproduced); the observed-404 capability memory treats a run-scoped 404 as "route absent" for the rest of the session (F4, reproduced); a deep link to a case the register does not hold is silently replaced by the first case (F5, reproduced, and pinned by the smoke); the intake panel header carries the previous case's "Last intake" date across a case switch (F6, reproduced); a network failure shows the browser engine's own exception text (F7, reproduced); Admin Studio claims "Not served" for two contracts the server serves (F8, verified with curl); and the compile form can submit with its default purpose outside the served cut (F9, reproduced). All twelve behaviour-removing mutations survive the source-reading unit tests, five of them with no automated catch anywhere, and the a11y route sweep passed 54 route×viewport scans against a backend that answered 404 to every API call, so the unit and sweep layers are pinning text, not behaviour.

What should wait: the a11y sweep's missing states (restricted, stale, failed, succeeded, partial) and missing modes (400 % zoom, forced colours, high contrast), the dead `page.once("dialog")` listener, the per-route presence assertion in the sweep, and the WebKit drawer opener belong with the browser-gate work Task 12b started (ER-G8 has landed; treat them as a gate-hardening follow-up rather than FE-G1 product fixes, except the drawer opener which is a product fix). Everything that renames a route, label, kicker or title waits for FE-G2 and is inventoried in §5. Contract prose (DESIGN.md, `.impeccable.md`, the capability map, the CLAUDE.md polyfill entry) is drift, not defect, and belongs to FE-G4 except the two capability-map rows that describe served routes as absent, which FE-G1 should correct alongside F8.

## 2. Findings, ranked by severity

Each reproduction names its evidence file. `probe.jsonl`, `probe2.jsonl` and `probe-focus.jsonl` are the JSON lines the scratch harnesses printed; `vacuity.log` is the mutation sweep.

### F1 — High. Every blur of a forecast input commits, remounts all inputs, strands focus and posts a tornado

- Where: `caos/frontend/src/components/model/ModelBuilder.tsx:248-250` (`commit` calls `onCommit` whenever the field is non-empty), `:270` (`onBlur={() => commit()}`, Enter blurs), `:549-561` (`editAssumption` → `applyAssumptionValue` → `invalidatePreview`), `:534-547` (`invalidatePreview` bumps `draftGenerationRef` unconditionally), `:750` (every `ForecastScrubber` key embeds `draftGeneration`), `:598-602` (the tornado effect re-runs on every new `draft` array).
- Failure: a keyboard user presses Tab from an untouched input. The blur commits the unchanged value, the generation bump re-keys all scrubbers, the element that just received focus is unmounted, `document.activeElement` falls to `<body>`, and a `POST …/models/tornado` goes out. Twenty-three fieldsets means twenty-three remounts and twenty-three requests to tab through the registry, against a 300/min per-subject ceiling. This remount is also the mechanism behind the focus race in issue #38: the dialog's captured trigger is destroyed while the dialog is open.
- Reproduction (`probe.jsonl`, S5): focus "Revenue growth, FY2025, BASE", press Tab, wait 900 ms → `focusAfterTab: {active: "BODY"}`, `originalStillMounted: false`, tornado POSTs 1 → 2, preview POSTs 0, value unchanged, badge "0 CHANGES". The focus harness (`probe-focus.jsonl`) shows 3 tornado POSTs for 2 value edits per iteration for the same reason.
- Violates: UX-018 (keyboard-only golden journey), WCAG 2.4.3 as DESIGN.md §5 Inputs and `.impeccable.md` "keyboard-reachable with a visible focus ring" require, and the request-ceiling budget the smoke documents (`workbench-smoke.mjs:579-584`).

### F2 — High. Report Studio recovery copies are shared across subjects and tabs

- Where: `caos/frontend/src/components/report/reportRecovery.ts:80-82` (`caos:report-recovery:<case>:<pathway>`; no subject, no tab), `ReportStudio.tsx:152-165` (read/store/clear), `:259-262` (offered on every load), `:314` (a successful save in any tab clears the shared copy), `:335-337` (last writer wins).
- Failure: on a shared workstation, or after a sign-out and sign-in, the next subject opening the same case and pathway is offered "Restore copy" of the previous subject's unsaved opinion text. Two tabs of one subject overwrite each other's copy, and a save in one tab deletes the other tab's only crash recovery.
- Reproduction (`probe.jsonl`, S9): as `analyst-a` type a thesis with the draft PUT answering 503; localStorage holds `caos:report-recovery:case_probe_a:FULL_CREDIT`; change `/api/me` to `analyst-b` and reload → `bannerOfferedToSecondSubject: 1`, `restoreControl: 1`.
- Violates: WEB-014 (isolation across cases, tabs, users, restarts). The capability map row "Browser recovery copy … scoped to case and pathway" describes the defect as the design.

### F3 — High. One screen can show two accepted-snapshot identities

- Where: `Workspace.tsx:382-388` (shell `refreshCase` reads `/snapshot`), `:1809-1818` (`CommandView` reads `/snapshot` again and then every artifact), `:1613-1617` (`DeepDive` reads it a third time). None compares its id with the shell's `authority`.
- Failure: a switch or acceptance that lands between the two reads (a second tab, the worker, another instance) leaves the authority strip on one id and the credit screen on another, with no "Review required" mark. A slow artifact fetch widens the window: `setSnapshot` runs before the artifacts load (`:1812`), so the identity is shown with an empty proof register until they arrive.
- Reproduction (`probe.jsonl`, S6): `/snapshot` answers `snap_probe_one` on the first read and `snap_probe_two` after → `shellStrip: "snap_probe_two"`, `creditScreen: "snap_probe_one"`, `warningShown: 0`. Cold-load request count (`probe2.jsonl`, S12): `GET …/snapshot` ×2, `…/lens` ×1, `…/{case}` ×1 on one Command Center load.
- Violates: WEB-005 (out-of-order response), the addendum's "authority strip … stays persistent" rule, and the addendum's claim that `workspaceAuthority.ts` is the sole stale-response guard (each surface carries its own `ignore`/generation guard and none reconciles with the shell).

### F4 — Medium. A run-scoped 404 pins "Not available in this deployment" for the whole session

- Where: `Workspace.tsx:98-102` (`resumeUnavailable`, `approvalUnavailable` are workspace state), `:942`, `:966` (set on any `isUnavailableRoute`), `:1006-1010` (renders `Unavailable`). `api.ts:112-132` documents the gate as "route absent on this deployment", but `POST /api/runs/{id}/resume` also answers 404 for an unknown or unauthorized run (CLAUDE.md auth edge: same 404).
- Failure: one paused run the caller may no longer see answers 404; from then on every paused run in every case shows "Run resume — Not available in this deployment." and no button until a full reload.
- Reproduction (`probe2.jsonl`, S4b): resume on `run_probe_p1` → 404; in-app navigate to `run_probe_p2` → `resumeButton: 0`, `unavailableBlock: 1`. (`probe.jsonl` S4 shows a full reload clears it.)
- Violates: the capability-map rule as stated in the addendum: an absent contract is an unavailable state — here a present contract is shown as absent.

### F5 — Medium. An unknown or unauthorized deep link silently opens the first case

- Where: `Workspace.tsx:348-359` (`refreshCases` resolves `requestedCase ?? next[0]`), `:354` (acknowledges the bad route so the route effect will not loop), `:673-684` (rewrites the URL to the substituted case).
- Failure: a retained link to a case whose membership expired, or a mistyped id, renders a different issuer's credit with the URL rewritten and no notice; a reader can act on the wrong credit believing the link resolved.
- Reproduction (`probe.jsonl`, S2): `/command-center/?case=case_probe_missing` → `selected: "case_probe_a"`, URL rewritten, `liveRegionsMentioningRequest: []`. The smoke pins this behaviour as correct at `workbench-smoke.mjs:405-412`.
- Violates: WEB-003 ("expired case context"), UX-020 (a typed outcome, not a silent one).

### F6 — Medium. The intake panel header carries the previous case's "Last intake"

- Where: `Workspace.tsx:812-831` (the intake read returns early when the new case names no intake, leaving `intake` set from the previous case), `:1104` (`meta` reads `intake.created_at` with no case check; the evidence table below it is case-checked at `:1122`).
- Reproduction (`probe.jsonl`, S7): case A shows "Last intake Sep 1, 2026, 11:00 AM"; select case B (no intake) → header still "Last intake Sep 1, 2026, 11:00 AM", evidence table absent.
- Violates: UX-014/WEB-003 cross-case authority; CLAUDE.md "arbitrates case … against … cross-case races".

### F7 — Medium. A network failure surfaces the engine's exception text; there is no offline state

- Where: `caos/frontend/src/lib/api.ts:98-105` (`firstErrorMessage` returns `caught.message` before the caller's fallback), `Workspace.tsx:370`, `:395`, `:555`.
- Failure: Chromium shows "Failed to fetch", Firefox "NetworkError when attempting to fetch resource.", WebKit "Load failed", as the page-level alert; DESIGN.md §5 names `offline` as one of eight distinct decision states and the code has none.
- Reproduction (`probe.jsonl`, S3): abort `/api/cases` → `globalError: "Failed to fetch"`.
- Violates: DESIGN.md §5 decision states; UX-020 (raw engine content).

### F8 — Medium. Admin Studio hard-codes "Not served" for contracts the server serves

- Where: `Workspace.tsx:1850-1862` (`AdminView` table: Audit trail, Membership → "Not served"); server `caos/server/caos/api/__init__.py:1385` (`GET /api/cases/{case_id}/audit-package`), `:1135` (`POST /api/cases/{case_id}/members`).
- Reproduction: `curl …/api/cases/case-0f55cd279faf46a18f34/audit-package` → `200 application/zip 17336B`; `POST …/members` with `{}` → `422` (route present, body refused). Report Studio already draws the member form (`ReportStudio.tsx:651`).
- Violates: the addendum's truthful-unavailability rule and CLAUDE.md's "derived, never a literal" standard for availability. The screens may stay unavailable by decision (CLAUDE.md known gap); the claims in the table are false.

### F9 — Medium. The compile form submits with a purpose outside the served cut

- Where: `Workspace.tsx:1504-1505` (defaults `EARNINGS_UPDATE` / `screen` regardless of `available_pathways`), `:1524-1526` (options disabled, value kept), `:1544` (submit enabled whenever a case is selected).
- Reproduction (`probe.jsonl`, S8): `available_pathways: ["FULL_CREDIT"]` → `#pathway` value `EARNINGS_UPDATE` with `selectedDisabled: true`, the note lists it as outside the cut, "Compile and run" posts `pathway: ""` (a disabled option is not submitted) and the server answers 422.
- Violates: the addendum ("no control is drawn for a route the server does not serve"); UX-020 (the refusal comes from the server for a state the client already knew).

### F10 — Low. Two focus-restoration owners remain; the race is masked, not removed

- Where: `Workspace.tsx:1368-1401` (`DraftDiscardDialog.dismiss` timer chain, 10 × 50 ms, with the Task 12b `settled` guard), `:640-671` (workspace repair effect), `:297` and `:307` (`focusedBeforeRef` seeded from the dialog trigger), and F1's remount.
- Evidence: CI browser jobs green ×3 on `main`; Chromium smoke passed here (133,764 ms); isolated harness 8/8 pass on each engine — Chromium (`probe-focus.jsonl`), Firefox (`probe-focus-firefox.jsonl`) and WebKit (`probe-focus-webkit.jsonl`) — with focus before `history.back()` on the editor every time. Issue #38 is closed. The three refuted fixes (MutationObserver watch, supersession token, target discrimination) are recorded in `.superpowers/sdd/loops/focus-race-findings.md` and must not be re-attempted.
- Design for FE-G1 (one owner): remove the cause first (F1's fix stops the remount); then delete the dialog's retry chain and let the workspace repair effect own every restoration by adding dialog close to its dependencies and re-finding the trigger by `id`/`aria-label` when the captured node is gone. The repair effect already declines under an open dialog and already lands on the landmark as its fallback, so no fourth referee is needed.

### F11 — Low. `closeDrawer` still infers its opener from `document.activeElement`

- Where: `caos/frontend/src/components/WorkbenchShell.tsx:144-148`, `:164`. Under WebKit a click does not focus the chip, so closing the drawer returns focus to whatever was focused before the chip. CLAUDE.md's known-gaps entry (`CLAUDE.md:532-537`) is still accurate. No gate exercises drawer close by Escape; the smoke leaves the drawer through "Open full source" (`workbench-smoke.mjs:2142`).

### F12 — Low. The reducer's `acceptedSnapshotId` is dead state

- Where: `caos/frontend/src/lib/workspaceAuthority.ts:16`, `:41`, `:109-111`; the only readers are the reducer and its test. Components use `authority.latest_accepted` (`Workspace.tsx:992`). The test "accepts a matching snapshot refresh" asserts a field nothing consumes.

### F13 — Low. The `q` query parameter is reflected into the chrome as an "Evidence request"

- Where: `Workspace.tsx:1670`, `:1834`. Text node only (no script), but any link can put arbitrary text under a product heading.
- Reproduction (`probe2.jsonl`, S13): "Please wire the coupon to account 12-34 …" rendered verbatim as the Evidence request strip. WEB-012 adjacent: untrusted URL content presented as product content.

### F14 — Low. The command-palette shortcut effect re-subscribes on every render

- Where: `WorkbenchShell.tsx:171-180` (`useEffect` with no dependency array). Harmless; hygiene.

### F15 — Low. Dead SSE subscriptions and a dead title effect

- `Workspace.tsx:706` subscribes to `node.failed` and `snapshot.accepted`; the run-events log never emits them (`caos/server/caos/storage/runs.py:850-1334` emits `run.created`, `run.paused`, `run.running`, `run.succeeded`, `run.failed`, `node.running`, `node.succeeded`, `research.plan_ready`, `research.plan_approved`). Harmless.
- `Workspace.tsx:612-614` sets `document.title` to the destination title; Next's route metadata wins (`probe2.jsonl`, S11: static and hydrated title both "CAOS — Cases" while the h1 says "Monitored credits", the kicker "Portfolio / Surveillance", the rail "Portfolio"). The effect is dead and each destination carries four names; IA blast radius in §5.

### F16 — Low. Decorative dialog motion

- `caos/frontend/app/globals.css:234-235` animates `dialog[open]` and its backdrop on open. DESIGN.md §1 and §6 allow motion only for live, running, selected or changed state. Reduced motion is honoured (`:637`).

### F17 — Test. The unit tests pin text, not behaviour (see §4)

Twelve behaviour-removing mutations that keep the pinned strings pass the unit suite 123/123 (`vacuity.log`). Six would be caught by the workbench smoke; five (beforeunload inert, recovery never written, colour-only status, an HTML sink in the artifact reader, drawer focus never restored) have no automated catch anywhere.

### F18 — Test. The a11y route sweep asserts nothing about what rendered (see §4)

Against a static server that answered 404 to all 117 API calls, `a11y-axe.mjs` reported no violation on all 54 route×viewport scans and on the pending-plan, ready-model, ready-report, review and filed fixtures, and stopped only at the loading-state assertion (`a11y-axe.mjs:302`) (`a11y-dead-backend.log`, `static-8790.log`). WEB-007's "every destination" is therefore proven only for whatever the empty shell renders.

## 3. Contract-drift table

| Document and clause | Claim | Code truth | Recommended fix |
|---|---|---|---|
| `.impeccable.md:13-16` | "eight destinations: Cases, Sources, Run Console, Deep-Dive, RV Screener, Command Center, Model Builder, Report Studio" | Nine routes (`src/lib/workbench.ts:1-11`, `admin-studio` included); the rail speaks Portfolio/Credit/Sources/Analysis/Market/Model/Report/Admin (`workbench.ts:98-106`) | Rewrite after D1 (FE-G4); until then the sentence is wrong twice |
| `.impeccable.md:66-69, 77` and `DESIGN.md:5-11, 279-281` | `#0a0a0f/#11131d/#1d2030/#34384a` ramp, accent `#63a1ff`, Inter + JetBrains Mono | `app/globals.css:2-16`: `#0a0c10/#101319/#181d28/#242b38`, accent `#8b93f8`, native stacks | Regenerate from the FE-A2 truth sheet (FE-G4) |
| `.impeccable.md:138-146`, `DESIGN.md:386-393` (31 Aug addenda) | Space Grotesk display face | `globals.css:3` `--font-display: "Avenir Next", "Segoe UI", system-ui` (Task 3 removed external fonts; `workbench.test.ts:29-36` forbids Google hosts) | Same |
| `DESIGN.md:350` | eight decision states, "visually and semantically distinct" | Present: loading (`states.tsx:97-99`), observed-empty (`:101-108, 122`), error (`:121`), unavailable (`:128-134`), stale (`ReportStudio.tsx:627`, `ModelBuilder.tsx:732`), partial (`Workspace.tsx:1623, 1818`); absent: `offline` (F7); `ready` has no marker | Add a network/offline state (commit 3) |
| `DESIGN.md:355` | "Always label the presentation preference View: Analyst / PM / QA" | No view control; the rail shows the server role (`WorkbenchShell.tsx:288`) | Decide (D-I) |
| `DESIGN.md:352-353` | worklist toolbar order with batch state and five visible actions; a labelled utility drawer | Cases toolbar is search + one filter (`Workspace.tsx:1065`); no utility drawer | Decide (D-I) |
| `caos/frontend/docs/control-capability-map.md:21` | One-way sensitivity "Route absent in this deployment" | Served: `api/__init__.py:1095` (curl `POST` with `{}` → 422); the UI deliberately draws tornado (`:1087`) and `ModelBuilder.test.ts:110` pins one-way absent | Reword: "served; not drawn — tornado is the sensitivity control" (FE-G1 docs commit) |
| `control-capability-map.md:24` | Admin "Routes absent … requirements only" | Audit package served (`:1385`, 200 zip 17,336 B), membership served (`:1135`), step-up absent | Split the row; fix `AdminView` (F8) |
| `control-capability-map.md:11-13` | Credit rows name snapshot and artifacts only | `/lens` (`:818`) is served and drawn (`Workspace.tsx:1801`) | Add a row |
| `control-capability-map.md:22-23` | Report: draft, autosave, scenario, freeze, filing, export | Also served and drawn: opinion (`:1292`), freeze jobs (`:1316`), receipt (`:1324`), request-changes (`:1346`), members (`:1135`); recovery "scoped to case and pathway" describes F2 | Add rows; after commit 4, "scoped to subject, case and pathway" |
| `control-capability-map.md:14, 16` | Sources: list/read/upload; Analysis: run/events/artifacts | Served, not drawn: withdraw (`:513`), notes (`:528-539`); served and drawn: research-plan (`:753, :760`) | Add "served, not drawn" rows; decide withdrawal (D-G) |
| `CLAUDE.md:187-190` | Next emits a 112,594 B `noModule` polyfill bundle every route references | No `nomodule` attribute in any `out/*/index.html` (grep count 0 ×12); no `polyfills*.js` chunk; the export ships eight chunks per route | Delete the entry |
| `CLAUDE.md:532-537` | `closeDrawer` still infers its opener | True (`WorkbenchShell.tsx:144-148, 164`) | Keep; fix in commit 11 |
| `CLAUDE.md:452-458` | `test:production-inventory` cannot pass | True (`production-inventory.mjs:3-4, 18, 73, 267`) | Keep |
| `CLAUDE.md:191-195` | run console is the one home | True: only `RunConsole` compiles/accepts; intake, Deep-Dive and Command Center link to it (`Workspace.tsx:1129, 1668, 1675, 1836, 1842`) | Keep |
| Frontend addendum | `workspaceAuthority.ts` is the sole stale-response guard | The reducer guards the shell's case/run authority; Sources, Deep-Dive, Command Center, Model Builder, Report Studio and RV each carry a private `ignore`/generation guard and none reconciles with the shell (F3) | Reword to "sole guard for case and run authority; per-surface reads carry their own generation and must bind to the shell's snapshot id" |
| `PRODUCT.md:9`, `.impeccable.md:22, 27` | personas live in "Deep-Dive, Model Builder, Report Studio, Command Center" | Those names survive only as kickers/titles; the rail says Analysis/Model/Report/Credit | FE-A1/FE-G4 |

## 4. Test-vacuity table

| Test or check | What it asserts | What it fails to catch (evidence) |
|---|---|---|
| `ModelBuilder.test.ts:53-60` "worksheet keyboard navigation … remain accessible" | regexes over the component source (`ArrowUp:…ArrowRight:`, `tabIndex=…`) | M1: `onKeyDown` handler deleted → 16/16 pass; the smoke catches it (`workbench-smoke.mjs:1243`) |
| `ModelBuilder.test.ts:135-139` "readers … cannot change forecasts" | `const canWrite = role !== "READER"` present | M3: per-period inputs editable by READER → 16/16 pass; the smoke catches it (`:1408`) |
| `ModelBuilder.test.ts:17-19` "unknown identity roles fail closed" | the `.includes(who.role)` ternary present | M5: initial role `ANALYST` (fail-open until `/api/me`) → 16/16 pass; the smoke catches it (`:2285-2294`) |
| `ModelBuilder.test.ts:79` and `workbench.test.ts:93-109` | `beforeunload` listener text present | M4/M4b: listener body inert → 31/31 and 16/16 pass; nothing else tests unload |
| `ReportStudio.test.ts:45-54` "scoped non-authoritative recovery copy" | `localStorage.setItem`, labels present | M6: copy never written → 21/21 pass; the smoke seeds localStorage itself (`:1799`) and never checks the app writes it |
| `workspaceAuthority.test.ts:13-19` "case authority refresh follows every reducer generation" | the effect's dependency list contains `authorityState.generation` | M7: effect body returns before fetching → 14/14 pass; the smoke catches it (authority strip waits) |
| `workbench.test.ts:172-188` "shape-coded visible statuses" | `.status.running::before {` exists in CSS | M8: success/warning/critical glyphs removed (status colour-only) → 31/31 pass; no gate checks glyphs |
| `ReportStudio.test.ts:33-43` "the structured document is safe" | no `dangerouslySetInnerHTML` in `DeliverableDocument`/`ReportStudio` | M9: raw-HTML sink in the artifact reader (`Workspace.tsx:1254`) → 123/123 pass; no gate covers Workspace or the shell |
| (no test) | drawer focus return | M10: `closeDrawer` restores nothing → 123/123; the smoke leaves the drawer by link, never by close |
| (no unit test) | cross-case run guard | M11: guard removed → 123/123; the smoke catches it (`:456`) |
| (no unit test) | SSE subscriptions | M12: no event subscribed → 123/123; the smoke catches it (intake review wait, `:629`) |
| `workspaceAuthority.test.ts:185-203` | `acceptedSnapshotId` set on matching refresh | asserts a field no component reads (F12) |
| `workbench-smoke.mjs:1426` `page.once("dialog", accept)` | — | a reintroduced `window.confirm`/`alert` would be auto-accepted and never reported |
| `workbench-smoke.mjs:405-412` | select value ≠ the unknown case id | pins F5 as correct behaviour |
| `workbench-smoke.mjs:527` `authorityRequests <= 12` | three navigations make ≤ 12 authority reads | a doubled read per page (F3 is 2 per Command Center load) stays under the bound |
| `workbench-smoke.mjs:27-43, 367-380` timing budget | DCL ≤ 250 ms, FCP ≤ 400 ms on the first Command Center load, Chromium only, API detail held | measured on loopback with the case read held, so API latency and every other route are outside the budget; Firefox/WebKit record only |
| `workbench-smoke.mjs:917` | acceptance region height 132–133 px | brittle to any spacing token change; not vacuous |
| `a11y-axe.mjs:32-50` route loop | axe over 9 routes × 6 desktop viewports after `networkidle` | no presence assertion: 54 scans passed with every API call 404 (F18); `CAOS_CASE_ID` unset means the first case in the register, whatever it holds |
| `a11y-axe.mjs:118-158` ready-model fixture | tab keyboard checks + 12 axe scans | `/models/tornado` is not mocked; the real server 404s (server log) so the tornado is scanned only in its Unavailable state |
| `a11y-axe.mjs` states list `:336` | empty, populated, review, filed, loading, error, refusal | WEB-004 restricted (READER), stale, failed, paused-for-resume, succeeded and partial are never scanned; WEB-006 400 % (360 px), forced colours and high contrast are never scanned; `combinations: 75` is a literal (`:336`) |
| `identity-a11y.mjs` | long/short identity exposure | sound; not in `package.json` gates beyond `test:identity-a11y` |
| `draft-history-smoke.mjs` | the pure history helpers in a real browser | sound; not run by any gate (no script entry) |

## 5. Blast-radius table for the IA change

Every literal an IA rename touches, with line numbers (from `evidence/blast-radius-compact.txt`; counts are occurrences).

| File | Literal(s) | Lines |
|---|---|---|
| `src/lib/workbench.ts` | `routeDestinations` slugs and labels; `destinationMeta` kickers and titles; `workflows` labels/hrefs; `destinationFromSlug` fallback "Cases" | 1-11; 21-31; 98-106; 270 |
| `src/lib/workbench.test.ts` | route table `[label, href]` ×7; `withQuery` samples `/run-console`, `/sources/`, `/cases`; "Accept analytical snapshot" | 48-58; 190-201; 321 |
| `src/components/WorkbenchShell.tsx` | `/cases`, `/sources` ×4, `/admin-studio`; "Admin Studio" ×4, "Run Console" ×2 (tool href logic), "Report Studio" (content class); nav names "Workflows", "Governance", `${label} tools`; "Sources & evidence"; "Page not found" | 246-294; 203, 264-287, 322; 259, 277, 287; 294; 292 |
| `src/components/Workspace.tsx` | destination switch ×9 and `EmptyPanel` "Open Cases" `/cases/`; `/command-center` (register link); `/run-console` ×5; `/sources` ×4; `/deep-dive`; "Monitored credits" h2; "Accepted analysis" title; "Deployment capability" | 1013-1023; 1065; 1129, 1668, 1675, 1836, 1842; 1480, 1495, 1677, 1779; 1842; 1065; 1675; 1858 |
| `src/components/model/ModelBuilder.tsx` | `/run-console` "Open Run Console" | 717 |
| `src/components/report/ReportStudio.tsx` | `/model-builder` "Open Model Builder" ×2, `/run-console` "Open Run Console" | 638-639 |
| `src/components/report/ReportStudio.test.ts` | `withQuery("/model-builder"…)`, `withQuery("/run-console"…)` pins | 80-81 |
| `app/[destination]/page.tsx` | `generateStaticParams` from `routeDestinations`; metadata title from the label | 5-14 |
| `app/not-found.tsx` | `/cases/` "Return to Cases" | 15 |
| `scripts/workbench-smoke.mjs` | `${baseURL}` routes: `/cases/` ×7, `/command-center/` ×4, `/deep-dive/` ×2, `/model-builder/` ×4, `/report-studio/` ×8, `/run-console/` ×9, `/rv-screener/` ×1, `/sources/` ×3; `waitForURL` pathnames `/sources` ×5, `/deep-dive/`, `/command-center/`, `/cases`, `/run-console`; rail labels array; nav names "Workflows" ×4, "Analysis tools" ×2, current-link triples; palette options "Open Sources", "Open Portfolio", "Open Run", "Open artifact/source ID in this case"; headings "Monitored credits", "Page not found", "Evidence focus" (two-ancestor depth); "Accept analytical snapshot" ×8; "Analyze documents" ×4; "Visible authority" ×7; "Select case" ×11; "Open command palette" ×5; "Skip to content" | 353-2286 (routes); 383, 493, 504, 519, 2143, 2151, 2241, 2245; 462; 464, 468-479, 523, 855; 1342, 2240, 2244, 492, 538, 2150; 484, 483, 496; 445-2277; 603-2289; 355-2200; 360-1961; 531-2242; 1018 |
| `scripts/a11y-axe.mjs` | `routes` array ×9; fixture routes `/run-console/`, `/model-builder/`, `/report-studio/`, `/command-center/`, `/cases/`; "Model" tab names; `combinations` literal | 18; 101-325; 135-152; 336 |
| `scripts/production-inventory.mjs` | every route ×17 and destination names ×7 (already non-passing) | 52-58, 302-507 |
| `scripts/workbench-smoke-debug-csp.mjs` | four routes | 10 |
| `scripts/draft-history-smoke.mjs` | `/sources`, "Select case", "Discard draft changes?" | 264, 288, 291 |
| `docs/control-capability-map.md` | surface names Portfolio/Credit/Sources/Analysis/Review/Market/Model/Report/Admin | 9-24 |
| `DESIGN.md`, `.impeccable.md`, `PRODUCT.md`, `CLAUDE.md`, `CONTEXT.md` | destination names as listed in §3 | `.impeccable.md:15-16, 22, 27, 92`; `DESIGN.md:236-373`; `PRODUCT.md:9`; `CLAUDE.md:192, 335` |

Also route-shaped but not named: `Workspace.tsx:53` reads the first path segment as the slug; `workflowFor` (`workbench.ts:275`) and the aria-current rule key on destinations; the `<main>` class keys on "Report Studio" (`WorkbenchShell.tsx:322`); the wrapper key `${active}:${caseId}` (`Workspace.tsx:1046`) remounts on destination change, so any forwarding route (D2) must replace history before that key changes or the draft-discard guard fires twice.

## 6. Decisions only the user can make

Recommendation first in each.

- **D-A Recovery scoping (F2).** Key the recovery copy by subject, case and pathway, refuse a copy whose subject differs, and add a per-tab id so two tabs never share one slot; or keep case+pathway and accept cross-subject exposure on shared profiles. The first is the WEB-014 reading; it changes the capability-map row, not the wire.
- **D-B Unknown deep link (F5).** Render a typed "Case unavailable" state that names the requested id and keeps the URL, and auto-select the first case only when no case was requested; or keep the silent fallback and change the smoke to document it. The first is the WEB-003 reading and a one-line change in `refreshCases` plus a state block.
- **D-C Observed-404 memory (F4).** Scope `resumeUnavailable` and `approvalUnavailable` to the run id they were observed on (reset on run change) and treat a run-scoped 404 as a typed refusal in the console; or keep the session memory and accept the pinning. The first keeps the route-absent semantics for routes that are actually case-independent.
- **D-D Admin Studio truth (F8).** Replace the static "Not served" table with an accurate list (audit package served, membership served, step-up absent) while the screens stay unavailable; or drop the table until the screens exist. Either ends a false claim; the first keeps the honest unavailable state CLAUDE.md wants.
- **D-E Offline state (F7).** Map a fetch `TypeError` to one sentence ("Network unavailable. Check the connection and retry.") in `firstErrorMessage` and keep the raw text out of the DOM; or leave engine text. The first closes DESIGN.md's eighth state with no new component.
- **D-F Sensitivity control.** Keep tornado as the only sensitivity control and correct the map's wording; or draw one-way sensitivity because the route exists. Recommend the first: the unit test pins its absence and the tornado already covers the four legacy drivers.
- **D-G Withdrawal and notes.** Record withdraw and notes as "served, not drawn" and let FE-A1/FE-G3 decide whether Sources draws withdrawal; or draw withdrawal in FE-G1. Recommend the first; it is an IA question.
- **D-H What moves out of FE-G1.** Send the sweep's presence assertions, the missing WEB-004 states and WEB-006 modes, the dead `page.once("dialog")`, and the timing-budget scope to a browser-gate hardening commit run by the FE-L1 loop or a small FE-G1b; keep every product fix and the unit-test rewrites in FE-G1. Alternatively fold the gate work into FE-G2's test change. Recommend the first so FE-G2's diff stays a rename.
- **D-I DESIGN.md anatomy rules.** Let FE-G4 delete the View toggle, utility-drawer and five-action toolbar rules the product does not implement; or keep them as targets for FE-G3. Recommend deletion unless FE-D2 draws them.

## 7. Commit plan for FE-G1, in dependency order

Each commit is isolated and carries its test; none renames a route, label, kicker or title.

1. **Model Builder: no commit without a change, no remount on generation.** `ForecastScrubber.commit` returns without `onCommit` when the trimmed value equals the last committed value; scrubber keys drop `draftGeneration` and reset their local input through an effect on `value`. Test: `modelBuilderState.test.ts` for the pure decision if it moves there, and a smoke step after `:1264` that Tabs from FY2025 to FY2026 and asserts focus on FY2026 and no tornado POST (the fixture already counts them). Closes F1 and removes the remount behind F10.
2. **One owner for focus restoration.** Delete the retry chain in `DraftDiscardDialog.dismiss` (`Workspace.tsx:1380-1400`), keep the synchronous `settled` read, and extend the repair effect (`:640-671`) to run on dialog close and to re-find a gone trigger by `id` then `aria-label`. Test: the existing assertion at `workbench-smoke.mjs:1362-1373` plus `scratch/probe3.mjs`'s loop promoted to `scripts/focus-restoration-smoke.mjs` (8 iterations, fresh page each) as a nightly step. Depends on 1.
3. **Network state.** `firstErrorMessage` maps a fetch `TypeError` to the network sentence; `LoadState`/global error unchanged. Test: `api.test.ts` case; smoke `:2285` extended to assert the sentence after the aborted `/api/me`. Closes F7.
4. **Recovery scoping.** `reportRecoveryKey(caseId, pathway, subject)`, `parseReportRecovery` requires `subject` equality, `ReportStudio` passes `subject`; a `tabId` from `sessionStorage` joins the key. Test: `reportRecovery.test.ts`; smoke recovery fixture (`:1794-1802`) gains `subject` and a second-subject reload asserting no banner. Closes F2 (D-A).
5. **Intake meta case fence.** `meta` at `Workspace.tsx:1104` reads `intake` only when `intake.case_id === caseId`; the effect clears `intake` when the selected case names no intake. Test: smoke intake section selects the idle case and asserts the header text. Closes F6.
6. **Run-scoped 404 memory.** `resumeUnavailable`/`approvalUnavailable` become `{ runId }` and reset on run change. Test: smoke pending-plan section adds a 404 on one run then a second run with the control present. Closes F4 (D-C).
7. **Compile form default from the cut.** Default `pathway` to the first enabled option; disable submit when none is enabled. Test: smoke fixture with `available_pathways: ["FULL_CREDIT"]` asserting the select value and that no POST leaves. Closes F9.
8. **Typed unknown-case state.** `refreshCases` stops substituting when a case was requested; render "Case unavailable" naming the id. Test: rewrite `workbench-smoke.mjs:405-412` to assert the state and that the URL keeps the id. Closes F5 (D-B).
9. **Admin Studio truth table.** Per D-D. Test: smoke `/admin-studio/` asserts the corrected rows. Closes F8.
10. **Snapshot identity binding.** `CommandView` and `DeepDive` take the shell's `authority` and render "Review required" (partial state) when their own snapshot id differs, or drop their own `/snapshot` read and fetch only artifacts from `authority.accepted.artifacts`. Test: smoke step reproducing S6 (two different snapshot answers) asserting the mark. Closes F3. Touches Workspace broadly, so it lands after the small fixes.
11. **Drawer opener passed explicitly.** `SourcesView.openEvidence` and `EvidenceChip` pass the click target to `onOpenEvidence`; `WorkbenchShell` stores it. Test: smoke opens the drawer, presses Escape, `awaitFocus` on the chip, in all three engines. Closes F11.
12. **Hygiene.** Remove the dead `document.title` effect, the reducer's `acceptedSnapshotId`, the two never-emitted event names, add the dependency array to the shortcut effect, drop the dialog entrance animation. Test: existing suites; `workspaceAuthority.test.ts` loses the dead assertion.
13. **Docs.** Delete the CLAUDE.md polyfill entry; correct the capability map rows in §3; reword the addendum's sole-guard sentence. No test.
14. **Test rewrites (unit).** Replace the twelve vacuous source pins with behaviour tests where a pure function exists (commit decision, recovery key, error mapping, unavailable scoping) and delete the rest; keep the route-table pin (it is the IA fence). Test: the mutation harness (`scratch/vacuity.mjs`) rerun must show every mutation caught by unit or smoke.
15. **Gate hardening (per D-H, may be a separate branch).** Route sweep asserts the destination h1 and no global error before axe; adds READER, stale, failed, succeeded and partial states and a 360 px viewport; mocks tornado in the ready-model fixture; removes `page.once("dialog")`; updates the `combinations` literal in the same commit.

## 8. Commands run and results

Fast gates (`caos/frontend`; `evidence/gates-fast.log`):

```
npm run lint            → eslint . — no output, exit 0
npx tsc --noEmit        → no output (clean)
npm run test:unit       → ℹ tests 130 ℹ pass 130 ℹ fail 0 (duration_ms 354)
npm run build           → ✓ Compiled successfully in 274ms … ✓ Generating static pages (12/12); exit=0
```

Host-control app and worker (own port, scratch data dir):

```
ENVIRONMENT=development CAOS_PROVIDER=host_control AGENT_EXECUTION_ENABLED=true ANTHROPIC_API_KEY= PORT=8766 CAOS_DATA_DIR=<scratchpad>/dev-data-audit caos/server/.venv314/bin/python caos/server/dev.py
ENVIRONMENT=development CAOS_PROVIDER=host_control CAOS_DATA_DIR=<scratchpad>/dev-data-audit caos/server/.venv314/bin/python caos/server/worker.py
curl -s http://127.0.0.1:8766/api/health → {"status":"ok","store":true,"bundle":true,"checkpointer":true}
```

Browser gates against `:8766` (`evidence/gates-browser-8766.log`; results dir `evidence/test-results/chromium/workbench-report.json`):

```
CAOS_URL=http://127.0.0.1:8766 CAOS_BROWSER=chromium node scripts/workbench-smoke.mjs
→ {"browser":"chromium","timing":{"domContentLoaded":60.3,"firstContentfulPaint":148},"budgetEnforced":true,"caseRequests":1}
→ {"browser":"chromium","browser_version":"151.0.7922.34","status":"passed","duration_ms":133764}
CAOS_URL=http://127.0.0.1:8766 node scripts/a11y-axe.mjs
→ {"routes":9,"viewports":6,"combinations":75,"pendingPlanFixture":true,"readyModelFixture":true,"readyReportFixture":true,"states":["empty","populated","review","filed","loading","error","refusal"],"modelBuilderAxeChecks":12,"modelBuilderKeyboardTabChecks":3,"reportStudioAxeChecks":3,"reportStudioKeyboardTabChecks":3,"violations":0}
```

Firefox and WebKit were not run here; the three-engine matrix is green on `main` (`gh run view 33957919360` → success for chromium, firefox, webkit; likewise `33884057611`, `33798306565`).

Mutation sweep (`node .superpowers/sdd/frontend/scratch/vacuity.mjs`; `evidence/vacuity.log`): M1, M3, M4, M4b, M5, M6, M7, M8, M9, M10, M11, M12 all "SURVIVES (vacuous)"; unit totals 16/16, 31/31, 21/21, 14/14 or 123/123 with 0 failures per mutation.

Reproduction probes (`evidence/probe.jsonl`, `probe2.jsonl`, `probe-focus.jsonl`):

```
S1 unknown route: h1 "Page not found", document.title "CAOS — Page not found"   → hypothesis refuted
S2 deep link: requested case_probe_missing → selected case_probe_a, URL rewritten, no live region names the request
S3 offline: globalError "Failed to fetch"
S4 / S4b resume 404: first run → Unavailable; in-app second run → resumeButton 0, unavailableBlock 1 (full reload clears it)
S5 blur without change: activeElement BODY, original input unmounted, tornado POSTs 1→2, preview 0, value unchanged, "0 CHANGES"
S6 divergent identity: strip snap_probe_two, credit screen snap_probe_one, warningShown 0, snapshotReads 2
S7 stale intake meta: case B header "Last intake Sep 1, 2026, 11:00 AM" from case A
S8 pathway outside cut: select EARNINGS_UPDATE (selected option disabled), note lists it outside the cut, POST pathway "" sent
S9 recovery across subjects: key caos:report-recovery:case_probe_a:FULL_CREDIT; banner and Restore offered to analyst-b
S10 focus race (probe3, pushState before the first edit): chromium 8/8, firefox 8/8 (firefox-1538), webkit 8/8 (webkit-2336); focus before history.back() on the editor every time; 3 tornado POSTs per 2 edits on every engine
S11 title drift: static and hydrated title "CAOS — Cases"; h1 "Monitored credits"; kicker "Portfolio / Surveillance"; rail "Portfolio"
S12 cold-load Command Center: GET /me 1, /cases 1, /cases/{id} 1, /snapshot 2, /lens 1, /runs/{id} 1
S13 q reflection: "Evidence request Please wire the coupon to account 12-34 …" rendered verbatim
```

Dead-backend a11y (`node scratch/static-out.mjs 8790` serving `out/` with every `/api/*` → 404; `CAOS_URL=http://127.0.0.1:8790 node scripts/a11y-axe.mjs`; `evidence/a11y-dead-backend.log`, `static-8790.log`): 54 route×viewport scans and the pending-plan, ready-model, ready-report, review and filed fixtures produced no violation; the run ended with `AssertionError: loading state was not on screen when scanned` at `a11y-axe.mjs:302`; the static server counted `{"apiHits":117}`.

Served-route checks (`curl`, case `case-0f55cd279faf46a18f34`): `GET …/audit-package` → 200 `application/zip` 17,336 B; `POST …/members {}` → 422; `POST …/models/sensitivities/one-way {}` → 422; `GET …/notes` → 200; `POST …/sources/src-none/withdraw` → 404.

Bundle (`out/`, 1.3 MB): route HTML references eight chunks (223.8 K, 200.1 K, 161.2 K, 110.0 K, 28.2 K, 22.6 K, 14.0 K, 9.5 K, 5.2 K raw; the largest four gzip to 71,658 + 54,399 + 45,029 + 39,490 B); JS total 793,584 B raw; CSS 62,534 B; no `nomodule` script and no polyfill chunk. Every route shares the same bundle, so Cases downloads Model Builder and Report Studio too; the smoke's DCL/FCP budgets (250/400 ms) are measured only on the first Command Center load, on Chromium, with the case read held.

Other read-only commands: `gh issue view 38` (CLOSED, with the Task 12b root-cause comments), `gh run list --workflow ci.yml --branch main --limit 8`, `git status --short` before and after (only `?? .superpowers/sdd/frontend/`), route inventory grep over `caos/server/caos/api/__init__.py`, `_emit(` grep over `storage/runs.py`, identity header read of `caos/server/caos/identity.py:46-84`, and the blast-radius greps in `evidence/blast-radius-compact.txt`.
