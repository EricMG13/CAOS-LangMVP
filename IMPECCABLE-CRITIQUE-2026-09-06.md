# CAOS workbench — closing Impeccable critique (FE-G4)

Date: 6 September 2026

Target: the combined app (static export served by the FastAPI development server under `CAOS_PROVIDER=host_control`) on branch `claude/enterprise-readiness-frontend-g4-fa7188` from `main` at `bfeda07` plus the FE-G3 second pass; every destination (`/portfolio/ /credit/ /sources/ /analysis/ /run/ /market/ /model/ /report/ /admin/`) in every drawn state at 1440×1000 and 720×900 (the 200 % desktop-zoom target); desktop only.

Method: dual-agent (A: design review sub-agent · B: detector and browser-evidence sub-agent), isolated from each other, plus the `audit` command as a third isolated sub-agent; the parent synthesized after A had finished and only then read B and the audit. 86 page states (A), 20 overlay loads (B) and 36 audited navigations (audit) against one smoke-seeded server; 0 × HTTP 429, 0 page errors. Scores below are quoted from the sub-agent reports, not re-derived. The critique's interactive "Ask the User" step was replaced by the FE-G4 prompt's own rule (fix P0 and P1, record P2) because the run was autonomous.

## Result

**25/40 — Acceptable. AI-slop: PASS. Audit 14/20 — Good. P0: 0. P1: 8 found (7 by the critique, 1 by the audit); 7 fixed in this pass, 1 recorded with what it needs.**

The 31 August critique scored 34/40 on the pre-Align product with two independent assessments and a root-cause correction pass already applied; this pass measured the shipped Align workbench before correcting anything, so the two totals are not the same instrument reading. The 9-point gap is concentrated in heuristics 2, 4, 7 and 10 (vocabulary, consistency of small idioms, accelerators, help) — the areas the earlier pass had already scored 2/4 or 3/4 — plus the Model surface, which the earlier pass could not reach without a READY fixture.

| Nielsen heuristic | Score | Final evidence (Assessment A, quoted) |
|---|---:|---|
| Visibility of system status | 3/4 | Authority strip, progress bar + sr announcer, `Saved v2`, LIVE badge, receipts are strong; but Report shows a warning triangle beside `Ready` (ReportStudio.tsx:607/150), the Credit proof column asserts `0` outputs while loading and during a 503 (Workspace.tsx:1916), and at 720 nothing says the rail scrolls. |
| Match between system and real world | 2/4 | `PERCENT_DECIMAL`, `vUnavailable`, `STORE UNAVAILABLE`, `INTAKE_ADMISSION_REFUSED`, `CP-PARSE`, "visible lens", "authority slots", percentages as `0.03`; Run's empty state still says "Drop documents on **Cases**" (Workspace.tsx:1517). |
| User control and freedom | 3/4 | Esc/Cancel everywhere with focus returned (16/16), draft guard, recovery copy, explicit snapshot switch. Gaps: discard dialog makes **Discard changes** the filled primary (Workspace.tsx:1498); no reset-to-App-value on an assumption. |
| Consistency and standards | 2/4 | Upload primaries disable-until-file on Portfolio/Market but not Sources (Workspace.tsx:1311); identities compacted everywhere except the accept dialog, Report bind panel and filing receipt (64-hex over 3–5 lines); codes humanized on Model/Run, raw on intake; nameless tiles cram the glyph onto the title line (Workspace.tsx:1508–1511); two Model elements render outside `.panel-body`. |
| Error prevention | 3/4 | Digest-bound gates restate what binds; intake disabled until files chosen; hard bounds; separation of duties. Gaps: `Compile and run` enabled on a zero-source case with an overlay default (Workspace.tsx:1626); intake bind checkbox detached from its label (globals.css:155). |
| Recognition rather than recall | 3/4 | Labelled rail, numbered section nav, `App 0.03` beside each input, the dialog restates. Gaps: `Open output` lands on Sources unannounced; `definition.description` fetched, never shown; palette needs a known evidence id. |
| Flexibility and efficiency | 2/4 | ⌘K palette of places (no actions), roving-tabindex worksheet, drag-to-scrub, sortable columns. No action shortcuts, no recents; 22 Tab stops from the authority strip to Accept on a 17-module route. |
| Aesthetic and minimalist design | 3/4 | Dense, organised, restrained; paper counterpoint excellent. Noise: 13 primaries on Portfolio, capability disclaimers on Credit/Sources/Market/Portfolio every visit, duplicate Model blockers, a 133 px acceptance box holding one sentence (globals.css:243), an empty `Deliverable model` fieldset (ReportStudio.tsx:614). |
| Error recognition and recovery | 3/4 | Refusal names file, reason, next action; `Retry`; conflict paths. Gaps: banner shows only `STORE UNAVAILABLE`; refusal has no critical weight (states.tsx:45 → `.empty`); bare `case not found` (ModelBuilder.tsx:729); red sentence with no action (ReportStudio.tsx:640). |
| Help and documentation | 1/4 | No help anywhere; no definitions of "visible snapshot", "source set", "authority slot"; only the dropzone copy, route hint and checklist notes. |
| **Total** | **25/40** | **Acceptable; 0 P0, 8 P1 found, 7 fixed below.** |

Design-specificity verdict (Assessment A, quoted): "Authored for this product in the shell and the ceremonies; category-interchangeable in the worklists; and missing the one thing the brand promises." The authority strip, the digest-bound acceptance dialog, the hash-bound plan approval, the freeze checklist and the paper counterpoint are unmistakably CAOS; the Portfolio register, the Create-case form, the Market filter grid and the Admin table could be any B2B admin tool; outside the worksheet grid no surface shows a credit number, so the product "reads as a very well-made governance console for a credit engine — precise and defensible, not yet alert."

Cognitive load (Assessment A): Model 4 of 8 checklist failures (high), Report 5 of 8 (high), Run 2 of 8 (moderate). The Model failure that mattered — the first assumption edit inserting the sign-off panel above the worksheet — is corrected below.

## Anti-pattern verdict

PASS. The CLI detector (`node ~/.claude/skills/impeccable/scripts/detect.mjs --json caos/frontend/src caos/frontend/app`) exited 2 with two warnings, quoted from Assessment B:

| rule | severity | file:line | snippet | classification |
|---|---|---|---|---|
| `border-accent-on-rounded` | warning | `caos/frontend/app/globals.css:178` | `border-bottom: 8px solid` | false positive — `.status.warning::before` sets `width: 0; height: 0; border-radius: 0` with transparent side borders: the CSS-triangle warning glyph, not a card border |
| `layout-transition` | warning | `caos/frontend/app/globals.css:248` | `transition: width` | confirmed, minor — the 4 px live run-progress fill; sanctioned motion (live state), compositor path `transform: scaleX()` is the upgrade |

In-page overlay (the same detector injected into five pages at both viewports; CSP `script-src 'self' 'unsafe-inline'` blocked the cross-origin `<script src>`, so the bytes were injected inline, and the overlay stylesheet was blocked under strict CSP, so the complete overlay was read in a second `bypassCSP` context): console groups `[impeccable] 27 / 21 / 23 / 18 / 72 anti-patterns found` at 1440 and `26 / 22 / 22 / 17 / 70` at 720 for Portfolio / Credit / Run / Model / Report. Classification, quoted from B: `undersized-ui-text` is the documented 10 px label register (deliberate) plus 8–9 px paper meta on Report (candidate); every `text-occlusion` hit is the overlay measuring itself or hidden content inside a closed `<details>` (false positive); `overused-font` matched "Roboto" as a listed fallback in the native stack (false positive); `em-dash-overuse` is the case selector's `issuer — case name` option labels (false positive); `all-caps-body` is the paper's uppercase section heads and footer stamp (false positive); `gpt-thin-border-wide-shadow` is closed dialogs at 0×0 plus the deliberate paper-on-desk shadow; strict-only `gradient-text` and `marquee` are the detector's own top bar. Confirmed minor: `cramped-padding` on `.report-section-nav button` (7 px for 14 px text), `line-length` on three full-width helper paragraphs (157–166 ch), `body-text-viewport-edge` on five paragraphs at 720. Manual review found no gradient, glass, pill-field, oversized marketing heading, decorative chart, fake confidence score or em-dash prose cadence.

## Audit health score (audit sub-agent, quoted)

| # | Dimension | Score | Key finding |
|---|---|---:|---|
| 1 | Accessibility | 3 | 0 axe violations in 29 scans; enabled text ≥ 5.71:1; gaps are a dangling `aria-labelledby` in Sources' empty state, run-on accessible names (`h3.rd-h`, wordmark), unnamed complementary landmarks, 8–9 px meaning-bearing text |
| 2 | Performance | 3 | Every route ships the same 801 KB raw / 230 KB gz JS (no route-level split); `WorksheetGrid` re-renders every cell on each arrow key; otherwise lean |
| 3 | Responsive design | 2 | Report's paper column is clipped without any scroll between 901 and ~1283 px; at ≤ 900 px four of ten rail destinations are only reachable by scrolling a thin-scrollbar strip; coarse-pointer 44 px rule is defeated for `.button.small` by specificity |
| 4 | Theming | 3 | One token sheet, 0 undefined `var(--…)`, 1 non-token colour outside `:root` (dialog backdrop), `color-scheme: dark` honoured; spacing drifts (307 px literals vs 261 `--space-*` uses); 3 unused tokens |
| 5 | Implementation integrity | 3 | Coherent, product-specific system (verdict PASS); detector: 1 false positive, 1 minor true positive; drift is 26 dead CSS classes, a duplicated hidden-text idiom, and two misleading identity strings |
| **Total** | | **14/20** | **Good (address weak dimensions).** Issues: P0 0 · P1 1 · P2 6 · P3 12. |

Contrast (audit, from `.superpowers/sdd/frontend/design/contrast.mjs`, 66 pairs): lowest enabled-text pair 5.71:1 (`--caos-paper-warning` on paper); every dark-register text pair ≥ 6.06:1; the only sub-4.5:1 text pair is the disabled primary button at 2.96:1 (exempt, inactive control). No token changed in this pass.

## Corrections completed

Each P1 was fixed in the file the finding named, with its paired test edit named beside it; no test was weakened.

- **Model: the first assumption edit no longer displaces the worksheet.** The sign-off panel renders as its own panel below the worksheet instead of inside the command panel above it (`ModelBuilder.tsx`, `data-model-approval`); `ModelBuilder.test.ts` now pins the panel below `styles.workspace` and its selector `panel span-12` (the old pin named the class string).
- **Model: blank worksheet cells no longer render as selected on first paint.** `cell && selected?.address === cell.address` (`ModelBuilder.tsx`); pinned in `ModelBuilder.test.ts`.
- **Model NOT_READY: the server's typed blockers are the only blockers; the "Open Run" link is the first blocker's action inside the panel body.** The generic "Accepted analysis required" block appears only when the server names no blocker; the floating small button outside `.panel-body` is gone (`ModelBuilder.tsx`).
- **Evidence drawer: the cited block is named and listed first.** `DrawerState.blockIds` carries the citation's block ids from the chip (`WorkbenchShell.tsx`, `Workspace.tsx`); the drawer shows "Cited blocks: …", marks each cited block `Cited` and orders them first; the "no block locator" sentence appears only when the artifact cited the source as a whole. `workbench-smoke.mjs` now waits for `[data-cited-block]` and asserts the old sentence is absent (the old assertion waited for the wrong sentence).
- **Portfolio: the intake "Add to this case" checkbox sits beside its label.** `.field input:not([type="checkbox"])` (`globals.css:155`); pinned in `workbench.test.ts`.
- **Report: the paper column reflows instead of being clipped between 901 and ~1283 px.** `.report-studio` third column `minmax(0, 5.5fr)` (`globals.css:465`); pinned in `workbench.test.ts`.
- **Rail at ≤ 900 px: the strip now draws a scroll thumb in Chromium and WebKit.** A styled `::-webkit-scrollbar` thumb on `.rail` after resetting the inherited `scrollbar-width`/`scrollbar-color` to `auto` (Chromium ignores the pseudo-element while those are set — the first attempt measured no scrollbar for that reason), with the standard pair scoped to Firefox by `@supports (-moz-appearance: none)` (`globals.css`, the 900 px block). Measured with `--hide-scrollbars` disabled: a 6 px classic scrollbar in Chromium and WebKit; Firefox keeps the platform's overlay behaviour and Playwright's headless Firefox reports `scrollbar-width: none` everywhere, so its cue is unverified here. This is the minimum cue the approved "Align — Shell 720" artboard allows, since that artboard draws the strip scrolling (FE-A2 F-07); the fuller remedy (wrapping or a disclosure) is a layout decision the canvas does not make; recorded below.

Also in this pass, outside the critique: DESIGN.md, .impeccable.md, PRODUCT.md, the control-capability map and the `.impeccable/design.json` sidecar regenerated from the CSS, the route tables and OpenAPI (see `.superpowers/sdd/frontend/frontend-g4-report.md` §4).

## Priority issues

- P0: none.
- P1 fixed: the seven above.
- P1 recorded, not fixed: **Portfolio hierarchy** — twelve filled `Open credit` primaries per screen while the post-intake `Open review` is a small button (`Workspace.tsx:1155`, `states.tsx:61`). Not changed because `workbench.test.ts` ("Cases makes opening the selected credit primary and keeps portfolio limits secondary") pins the row primary as a product decision; overturning it is the decision owner's call, and the fix is one class string plus that test's pin.
- P2 recorded (file, what it needs):
  - Report copy `Draft authority vUnavailable`, `Sign opinion on saved v—`, `Freeze saved v—` (`ReportStudio.tsx:621, 633, 637`) — branch the copy on "no saved revision"; also FE-G3 §10.6.
  - `▲ Ready` and `▲ Immutable FILED review` pair a warning glyph with non-warning words (`ReportStudio.tsx:607, 609`) — a success/idle status tone for those two states.
  - Empty `Deliverable model` fieldset and `1 sources` (`ReportStudio.tsx:614, 615`).
  - Nameless module tiles cram the glyph onto the title line (`Workspace.tsx:1508–1511`).
  - Discard dialog makes the destructive path the filled primary (`Workspace.tsx:1498`).
  - `Compile and run` enabled on a zero-source case with the Earnings Update default (`Workspace.tsx:1579, 1626`).
  - Refusal block carries no critical weight and shows the raw code (`states.tsx:45`, `Workspace.tsx:1208`).
  - Assumptions read `0.03` under `PERCENT_DECIMAL` while the grid says `3.0%`; `definition.description` never rendered (`ModelBuilder.tsx:758`).
  - Sign-off note requested before the recalculation it describes (`ModelBuilder.tsx`, the approval panel) — reveal the note when `previewCurrent`; the smoke fills the note after recalculating, so the change is safe but is a ceremony-order decision.
  - Analysis defaults to `CP-PARSE`, lists it twice; markdown tables render as pipes (`Workspace.tsx:1728, 1739`; `lib/artifactReader.ts:27`; FE-G3 F-18).
  - "Drop documents on **Cases**" (`Workspace.tsx:1517`).
  - Dangling `aria-labelledby="source-reader-title"` when no source is selected (`Workspace.tsx:1314`; axe needs-review `aria-valid-attr-value`).
  - No route-level code splitting: every page loads 801 KB raw / 230 KB gz (`Workspace.tsx:7–8` static imports) — `next/dynamic` for Model, Report and Market.
  - `WorksheetGrid` re-renders every cell per keystroke (`ModelBuilder.tsx:145–202`) — memoised rows, `activeCell` out of the render path.
  - Rail at ≤ 900 px: the fuller remedy (wrap into two rows or a disclosure, pinned wordmark) — needs a canvas decision (F-07).
  - `ModelBuilder.module.css .workspace` has the same clip shape as the Report grid (minima 1010 px, hidden overflow, reflow at ≤ 1180) — a ~1181–1222 px band; the same `minmax(0, …)` fix once measured.
  - Detector-confirmed minors: `.report-section-nav button` 7 px padding (`globals.css:480`); three 157–166 ch helper paragraphs (Portfolio `#intake-hint`, the portfolio contract notice, Credit's context strip); five 12 px-gutter paragraphs at 720; 8–9 px paper meta and the 8 px `.rd-h-sub` authority marker (`globals.css:543, 547`).
  - The 31 August P2s, restated below.

## Persona red flags

- Analyst (primary): Model was where the golden journey broke (NOT_READY contradiction and floating link, blank-cell selection, edit displacement) — the three code defects are fixed; `0.03` vs `3.0%`, the drawer-to-block landing (fixed), Report's ten "Not yet drafted" sections defaulting to `Analyst judgment`, and undefined vocabulary ("visible lens", "authority slots", `input_fingerprint`) remain the learning cost.
- Alex (power user): ⌘K lists places, not actions; no keyboard path to accept, approve, sign or freeze; 22 Tab stops through the route tiles before Accept; the register cannot be sorted.
- Sam (screen reader, keyboard, 200 %): rail overflow now has a visible thumb but is still not announced; the bind checkbox is fixed; refusal is announced (`role=alert`) but visually weightless; `▲ Ready` pairs a warning shape with non-warning words; 8–10 px text is unreadable at 100 %. Protected: skip link to a real target, heading focus on open, focus return (16/16), `aria-sort`, named scroll regions, the progress announcer.
- PM / CIO: a third of Credit is disclaimer; Portfolio has no freshness, material-change or threshold column; every Credit metric is a count or an identity.
- Head of Research / QA: CP-5 is one tile among 17 with no QA summary; claim coverage "Not available"; Admin is honest (`PARTIAL`, 2 of 5 served) with a one-click audit package but no chain head shown; `Download audit package` is still offered to a READER (server-enforced, UI-silent).

## Minor observations

- `/portfolio/` auto-selects the first case; the top bar and rail meta then claim a credit never picked.
- Tornado draws `Output` and swing controls above "Not available in this deployment".
- The 720 authority strip overflows with no visible scrollbar; `Selected run` is cut mid-token.
- Report opens on Full Credit for a Deep Research case (FE-G3 F-19).
- `Sources & evidence` in the top bar duplicates the rail on every surface but Sources.
- Palette rows read `Idle / No Run BoundaryServices` (no separator before the sector).
- Market shows the 64-hex universe digest in full; identity compaction is inconsistent across the accept dialog, the Report bind panel and the receipt.
- 26 CSS classes (about 35 rules) have no consumer; `.sr-only` and `.visually-hidden` do the same job; `--caos-paper-soft`, `--shadow-pop` and `--space-2xl` are declared and unused; the coarse-pointer 44 px rule loses to `.button.small` on specificity; `content-visibility: auto` on table rows is inert.
- `CONTEXT.md` lists "Snapshot" as an avoid-term while the run domain says "analytical snapshot" everywhere.

## The three P2s of 31 August

- **Reduce dense Model/Report control groups.** Partly closed with evidence: FE-G3 moved member provisioning off Report to Admin and collapsed Run's compile form; this pass moves the Model sign-off panel below the worksheet. Still open on Assessment A's checklist (Model 4/8, Report 5/8 failures): the Report compose column still stacks narrative, claim authority, model authority, evidence inspector, scenario insert, the six-row bind checklist, four opinion fields and freeze. Needs: a progressive-disclosure design for the compose column (a canvas decision, FE-D2 was skipped).
- **Define task-oriented help.** Open; restated. No help surface exists (heuristic 10 scored 1/4); the palette searches places only. Needs: a product decision on where help lives (a definitions drawer for the authority vocabulary would answer the concrete gaps A listed) and an owner for the content; no served contract is required.
- **Add saved views and recent credits only with served contracts.** Open; restated with evidence: `GET /openapi.json` on this build serves no saved-view, recent-credit or portfolio-summary route (the capability map's "Attention ordering" row stays Unavailable), so nothing can be drawn. Needs: server routes plus a DECISIONS §14 entry before any control is drawn.

## Questions

No blocking questions. The two decisions this pass surfaces for the decision owner: whether the Portfolio register keeps its per-row primary (pinned today), and whether the 720 px rail wraps or discloses (the approved artboard draws a strip).

## Verification

- Frontend gates on the final tree (`caos/frontend`): `npm run lint` — ESLint: No issues found; `npx tsc --noEmit` — TypeScript: No errors found; `npm run test:unit` — 141 tests, 141 pass, 0 fail; `npm run build` — Next.js 16.3.3, 20/20 static pages.
- Against a fresh-data host-control server on `:8792` built from this tree: `npm run a11y` — `{"routes":17,"forwarders":8,"viewports":6,"combinations":125, … "violations":0}` (0 × 429 in the server log); `npm run test:workbench` — `chromium 151.0.7922.34 passed 141,939 ms / firefox 153.0 passed 151,011 ms / webkit 26.5 passed 150,039 ms` on the final tree (the a11y sweep ran first on the fresh data directory; the server log shows 0 × 429 across the sweep and the three smokes).
- Detector: `detect.mjs --json caos/frontend/src caos/frontend/app` exit 2 — 2 warnings, one false positive, one minor (quoted above).
- Evidence set for WEB-015: 270 PNGs over 45 labels at six viewports (≈ 43 MB), captured on the final build, no page-level overflow and no page error in any capture, 0 × 429 on the seeded server under `.superpowers/sdd/frontend/evidence/g4/` with `SHA256SUMS` and `manifest.json` (label, viewport, URL, digest, page-level overflow, page errors per capture).
- Sub-agent reports retained in the session scratchpad (`agents/a/report.md`, `agents/b/report.md`, `agents/c/report.md`) and summarised in `.superpowers/sdd/frontend/frontend-g4-report.md` §2.
