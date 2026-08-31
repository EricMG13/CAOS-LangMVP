# Plan — Port the Modern Committee Terminal and Close the Impeccable Gaps

## Goal

Bring the current Model Builder/frontend WIP on
`codex/opencode-modern-terminal-wip` onto the authored graphite/iris design
system from `GLM/production-saas-polish`, then close the verified usability
gaps from the Impeccable assessment without weakening authority, evidence,
keyboard, or fail-closed behavior.

This is a port-and-remediation plan, not a second redesign. Preserve the
strongest existing decisions: the severity-shape system, persistent authority
strip, Sources three-region workspace, dense institutional register, and light
committee-paper counterpoint.

## Current reality

- The visual source of truth is commit `56496a1` on
  `GLM/production-saas-polish`; it already contains the complete modern dark
  terminal reskin.
- The target branch is `codex/opencode-modern-terminal-wip` at `874b087` plus
  an uncommitted functional WIP. It contains a newer Model Builder, its server
  contracts and tests, and predecessor interaction polish. The branches
  diverge from `54fae6e`, so do **not** blindly cherry-pick the GLM commit.
- The Impeccable assessment audited the GLM surface and scored it 27/40. Its
  five ranked issues remain the primary backlog, but every finding must be
  checked against the newer target code before editing.
- Two minor findings are already stale in the target code:
  `report/DeliverableDocument.tsx:129-138` uses the `.rd-*` paper system, and
  `WorkbenchShell.tsx:362` renders the Tools palette group only when tools
  exist. Verify these; do not reimplement them.

## Phase 0 — Documentation discovery and allowed patterns

### Sources to read before implementation

1. `PRODUCT.md:7-39` and `DESIGN.md:228-381` — users, release standard,
   Committee Terminal register, accessibility, tokens, and component rules.
2. `56496a1:caos/frontend/app/globals.css:1-236` — exact graphite/iris tokens,
   radii, shadows, status shapes, overlay motion, and reduced-motion guards.
3. `56496a1:caos/frontend/app/layout.tsx:2-12` — the existing Space Grotesk
   `next/font` configuration; copy it rather than adding a font package.
4. `56496a1:caos/frontend/src/components/WorkbenchShell.tsx` — SVG brand mark
   and shell chrome, reconciled with the target branch's loading state and
   palette hints.
5. Target WIP:
   - `model/ModelBuilder.tsx:142-718` and `ModelBuilder.module.css`.
   - `Workspace.tsx:921-1000` for the native accept dialog and Run Status.
   - `report/ReportStudio.tsx:433-520` for freeze readiness and filing.
   - `report/DeliverableDocument.tsx:46-140` for live paper markup.
6. Harness contracts:
   - `scripts/a11y-axe.mjs:18-48,118-158,226-254`.
   - `scripts/workbench-smoke.mjs:1585-1699`.
   - `caos/frontend/package.json:5-14` and `.github/workflows/ci.yml:25-34,93-130`.

### Allowed APIs and idioms

- Existing `api`, `firstErrorMessage`, `isUnavailableRoute`, `withQuery`,
  `humanizeCode`, `moduleLabel`, `StateBlock`, `StateNote`, `LoadState`, and
  `Unavailable` helpers.
- Native `<dialog>` with `showModal()`, heading focus, Escape close, and trigger
  focus restoration, copied from `Workspace.tsx:921-966` and the shell.
- Native `<details>` for progressive disclosure, semantic `<table>/<caption>`,
  standard form controls, and existing ARIA listbox/tab patterns.
- Current-color 16px inline SVGs with `aria-hidden="true"`.
- Existing CSS variables, the GLM token/radius/shadow/easing scale, and the
  WIP's feature-scoped `ModelBuilder.module.css`.
- Motion only inside `prefers-reduced-motion: no-preference`; 720 CSS pixels is
  the 200%-zoom desktop contract, not a mobile breakpoint.

### Anti-pattern guards

- Do not cherry-pick `56496a1` over the WIP or replace current components with
  older GLM versions. Copy the visual rules into current behavior.
- Keep the Model Builder UI, API, server, and tests atomic; its tornado,
  worksheet, preview, and sign-off contracts are not decorative frontend code.
- Do not add a dependency, request wrapper, theme mode, mobile project, or new
  backend endpoint for a presentation problem.
- Do not change harness selectors, IDs, roles, accessible names, exact
  `Compose` text, authority semantics, or fail-closed gates without a matching
  test change that proves the intended behavior.
- No decorative gradients, glow, glass, color-only status, oversized cards,
  or a sixth uppercase eyebrow tier.

Exit: the implementation agent can name the source pattern for every planned
change and can identify report findings that are already resolved.

## Phase 1 — Establish the WIP baseline and port the authored visual system

### What to implement

1. Checkpoint the current branch's coherent WIP before visual edits. Keep the
   Model Builder frontend/server/test cluster together.
2. Copy the token, radius, shadow, status-shape, overlay, and reduced-motion
   rules from `56496a1:globals.css` into the target `app/globals.css`, resolving
   selectors against the current markup rather than restoring removed UI.
3. Copy the Space Grotesk configuration from `56496a1:layout.tsx` and the SVG
   brand/shell treatment from `56496a1:WorkbenchShell.tsx`, while preserving
   the target's `casesLoading`, conditional palette groups, keyboard hints,
   and current authority state.
4. Bring `ModelBuilder.module.css` onto the same radius, surface, focus, and
   status vocabulary. Remove only selectors proven dead by current markup;
   `.model-builder-view-tab` and old sensitivity styles are candidates, not
   assumptions.
5. Copy the superseding reskin notes from `56496a1:DESIGN.md:386-401` and
   `.impeccable.md:138-146` so implementation and documentation agree.

### Verification checklist

- `git diff --check` and grep prove no unresolved GLM conflict markers or
  duplicate token blocks.
- `npm run lint --prefix caos/frontend -- --max-warnings=0`.
- `npx tsc --noEmit -p caos/frontend`.
- `npm run test:unit --prefix caos/frontend`.
- `npm run build --prefix caos/frontend` before judging CSS or font behavior.

### Anti-pattern guards

- Do not copy the old GLM `ModelBuilder` or `ReportStudio` components.
- Do not leave hard-coded square geometry in the CSS module after the shared
  token scale lands.
- Do not use a wide resting shadow plus a decorative border on normal panels.

Exit: all current WIP behavior runs under the same authored visual system that
the assessment actually reviewed.

## Phase 2 — Restore hierarchy and repair shell polish

### What to implement

1. Collapse label usage to four explicit roles:
   - `nav-label`: the sole uppercase tracked navigation-group style;
   - compact uppercase table headers;
   - sentence-case `panel-meta` for one secondary panel-header fact;
   - `meta-label` for field and data captions.
   A panel may have an eyebrow or metadata, never both. Remove decorative
   `.eyebrow` stacking, starting at `globals.css:52,75,99,131,493` and
   `ModelBuilder.tsx:673,686,701,706`.
2. In `WorkbenchShell.tsx:281-290`, remove the redundant `Reading:` element and
   its unused data field/tests. Render the shortcut with a real
   `<kbd aria-hidden="true">⌘K</kbd>` and reuse the `.palette-hint kbd` style so
   `Command` and `⌘K` cannot collide.
3. Preserve report outline numbers because they describe a real ordered
   committee document, not decorative section scaffolding.
4. Replace identical DAG side stripes with the existing shape-coded status
   language; keep selection stripes only where they communicate selection.

### Verification checklist

- Add/adjust unit assertions for shell text and Model Builder headings where
  current tests already inspect them.
- Grep the rendered source for obsolete label classes and dead selectors.
- Keyboard-check command palette open, search, ArrowUp/ArrowDown, Enter,
  Escape, and focus restoration.
- Inspect Model Builder at 1440×1000 and 720×900: one clear page title, one
  primary action, and no label stack before the worksheet.

### Anti-pattern guards

- Do not globally change `text-transform` or capitalize raw identifiers;
  exact accessible copy and module acronyms are harnessed.
- Do not solve hierarchy by enlarging every heading or introducing display
  type into controls.

Exit: uppercase microcopy is a deliberate metadata tool, not the dominant
visual grammar.

## Phase 3 — Give Accept, Sign-Off, and Freeze one commit-ritual grammar

### What to implement

1. Keep `AcceptDialog`'s native dialog/focus behavior. Add a review summary
   computed locally from `run.nodes` and `replaces.artifacts`: new authority
   slots, existing slots replaced, and slots removed, plus source-set context
   and the exact digest being replaced. `RunRecord` has no artifact digest, so
   do not claim byte-level changes and do not add a preflight endpoint.
2. In `RunStatus`, render a stable acceptance region for every run state:
   waiting progress, failed/paused remedy, succeeded-not-accepted action, and
   accepted identity. Demote duplicate visible `succeeded` labels while
   retaining `RunStatusBadge` and `RunProgressAnnouncer` semantics.
3. In `ModelBuilder.tsx:668-696`, group preview identity, changed-assumption
   count, required sign-off note, conflict state, and `Save model version` into
   the existing `.approval-panel` sequence: what will bind → exact authority →
   actor note → action. Preserve the current POST body and rebase flow.
4. In `ReportStudio.tsx:484-514`, keep the freeze action present and reserve
   its geometry. Replace the single muted blocker sentence with a checklist
   derived from existing booleans: write access, exact saved revision, current
   model selection, and required model availability. Link unmet model
   prerequisites to Model Builder or Run Console with `withQuery`.
5. Reuse `.approval-panel`, `.state-facts`, and `.status`; do not create a new
   React abstraction unless shared behavior, not just styling, emerges.

### Verification checklist

- Unit-test authority-slot counts and all freeze-checklist states.
- Extend `test:workbench` for acceptance-region geometry before/during/after a
  run, dialog focus restoration, and Report Studio prerequisite links.
- Verify Reader mode never receives a write action.
- Verify digest-bound requests and server-side revalidation are unchanged.

### Anti-pattern guards

- Do not make irreversible actions louder with decorative color or motion.
- Do not enable a blocked action merely to show its error.
- Do not duplicate server authority logic in the browser.

Exit: every irreversible act clearly states what changes, the exact authority
being bound, what blocks completion, and the one next action.

## Phase 4 — Humanize status and identity without hiding exact authority

### What to implement

1. Correct the current snapshot-diff contract mismatch first:
   `CommandView` models modified items as `{before, after}` but
   `responses.py:201` serves `{module_id, digest}`. Type and display only the
   fields the server actually returns; do not copy the invalid slice pattern.
2. Add one tested `compactIdentity(value, leading = 12, trailing = 4)` helper
   beside the existing display helpers in `lib/workbench.ts`. Visible workspace
   values use `leading…trailing`, while `title` and an accessible label retain
   the full value. Do not truncate values in requests, comparisons, downloads,
   logs, persistence, or governed paper output.
3. Apply the helper consistently to shell authority, Sources SHA-256,
   Deep-Dive provenance, Command Center diffs/metrics, Model Builder version
   identity, and the evidence drawer. Keep short domain IDs unchanged. Keep the
   full identity on `DeliverableDocument` and improve wrapping there instead.
4. Use existing `humanizeCode` and pathway maps for raw `SCREAMING_SNAKE`
   display text; retain canonical codes only where auditability needs both.
5. In `CommandView:1326-1329`, prefer `CP-2`, then a substantive narrative
   artifact excluding `CP-PARSE`/`CP-0`; fall back to preparation output only
   when no conclusion-bearing artifact exists. Add a pure selection test.
6. In the evidence drawer, use the filename as the heading and move the source
   ID into the facts list.

### Verification checklist

- Unit tests cover short, exact-threshold, long, empty, and non-hex identities.
- Screen-reader spot-check verifies an abbreviated spoken identity plus an
  accessible way to obtain the full value.
- Command Center fixture proves CP-PARSE cannot outrank an available credit
  conclusion and renders the served diff shape honestly.
- No ad hoc `slice(0, 12)` identity policy remains outside the shared helper.

### Anti-pattern guards

- CSS ellipsis alone is insufficient: it must not erase the accessible/full
  value.
- Do not add copy-to-clipboard complexity unless users cannot retrieve the
  exact value through the native title/details already provided.

Exit: analysts can compare identities at human scale while exact bytes remain
available and unchanged.

## Phase 5 — Reduce cognitive load on the three overloaded surfaces

### What to implement

1. Cases: demote the portfolio-ordering limitation to supporting context and
   make `Open credit` the unmistakable row action. Keep search, authority
   filter, register, and create form; do not convert them into cards. Mark the
   selected native row with `aria-current="true"`; do not add `aria-selected`
   unless the table becomes an interactive grid.
2. RV Screener: keep the common search/core filters visible and move advanced
   date/numeric bounds into native `<details>`. Add a real table caption that
   states the column count and horizontal-scroll behavior for assistive tech.
3. Report Studio: preserve the paper as the visual anchor. Show the selected
   narrative editor first; progressively disclose evidence search, scenario
   insertion, and optional composition. Reduce the default textarea height
   while keeping user resize, required blocks, autosave, and recovery.
4. Replace `window.confirm` draft-discard paths only after Phases 1-4 are
   green. Copy the existing native dialog/focus-return pattern into one
   explicit discard flow; preserve `beforeunload` as the browser-owned
   last-resort guard.
5. If still useful after the core fixes, replace the shell's `runIsLive`
   boolean with `"live" | "paused" | null` and render a shape-coded PAUSED
   marker. Do not add motion to the paused state.

### Verification checklist

- Cases first-time, populated, filtered-empty, selected, and Reader states
  retain one clear primary route.
- RV filters retain values across disclosure toggles; keyboard and screen
  reader users receive the table's size/scroll context.
- Report Studio autosave, recovery, conflict, freeze, file, and request-change
  harnesses remain green.
- Draft discard tests cover case switch, palette navigation, browser history,
  cancel, confirm, Escape, and focus return.

### Anti-pattern guards

- Do not call 720px a mobile layout or invent a mobile-only information
  architecture.
- Do not hide core filters or required report blocks behind mystery controls.
- Do not replace native controls with bespoke widgets for visual novelty.

Exit: each surface presents one dominant task while preserving expert depth.

## Phase 6 — Remove verified residue and complete the audit

### What to implement

1. Prove `.rd-*` paper selectors are live; remove only genuinely dead legacy
   `report-paper-*`, old Model Builder tab/sensitivity, or superseded selectors.
2. Keep conditional palette-group rendering; add a regression assertion rather
   than changing already-correct markup.
3. Verify the warning triangle at 1×, authority-metric dividers, report counter
   emphasis, paused-run rail status, and drawer heading. Fix only defects still
   visible after Phases 1-5.
4. Re-run the Impeccable slop, Nielsen, cognitive-load, emotional-journey, and
   Alex/Sam/Priya walks against the final target branch.

### Verification checklist

- `rg` proves every deleted selector has no live markup or harness use.
- Visual inspection covers all nine routes at 1440×1000 and 720×900, the
  command palette, evidence drawer, accept/discard dialogs, and Report Studio
  paper at two scroll positions.
- Record residual findings as evidence; do not turn speculative polish into
  code.

Exit: every report item is fixed, explicitly retained with rationale, already
resolved, or rejected with current-code evidence.

## Final verification

Run from the repository root in this order:

```bash
npm ci --prefix caos/frontend
npm run lint --prefix caos/frontend -- --max-warnings=0
npx tsc --noEmit -p caos/frontend
npm run test:unit --prefix caos/frontend
npm run build --prefix caos/frontend
python -m pytest caos/tests -q
ruff check --config ruff.toml caos/server caos/tests --exclude caos/server/caos/methodology/vendor
```

Run browser checks against the combined FastAPI/static-export app, never
against `next dev`:

```bash
PORT=8010 python caos/server/dev.py
curl -sf http://127.0.0.1:8010/api/health
CAOS_URL=http://127.0.0.1:8010 npm --prefix caos/frontend run a11y
CAOS_URL=http://127.0.0.1:8010 npm --prefix caos/frontend run test:workbench
```

Do not substitute nonexistent `npm test`, `npm run typecheck`,
`npm run test:e2e`, or `npx playwright test` commands. Do not run the known
non-gating `test:production-inventory` script.

## Completion criteria

- The current Model Builder/server WIP remains behaviorally intact and atomic.
- The target branch uses the authored `56496a1` visual system without copying
  obsolete component implementations.
- All five ranked Impeccable issues are closed with automated coverage where
  behavior changed.
- The three commit moments share a clear visual grammar and retain server
  authority enforcement.
- No raw long identity is forced into normal reading flow; exact values remain
  accessible and byte-identical.
- The complete static, server, accessibility, workbench, 1440px, and 200%-zoom
  gates pass without waivers.
