# Task 5 report — Reduce cognitive load in core workspaces

## Summary

- Cases now leads with the monitored-credit register. Each row has an unmistakable primary **Open credit** action, and the active row uses native `aria-current="true"`; the portfolio-ordering limitation follows the primary work as supporting context.
- RV Screener keeps search and categorical filters visible, moves date and numeric bounds into a native `details` disclosure without unmounting their controlled values, and gives the wide table a real 27-column caption with horizontal-scroll guidance.
- Report Studio keeps the governed paper as its anchor while putting the selected editor first. Optional composition, evidence search/citations, and Scenario insertion are native disclosures. The narrative textarea is shorter (`rows={8}`) and remains vertically resizable; required blocks, autosave/retry, recovery, conflicts, freeze, file, restore, export, and request-changes behavior remain intact.
- One native discard dialog now owns dirty Model Builder and Report Studio navigation for case selection, command-palette cases/workflows, ordinary internal links, Report Studio pathway changes, and browser history. Cancel and Escape preserve edits, repair browser history when required, and return focus; confirm runs one deferred action. The existing `beforeunload` fence remains browser-owned.
- The shared history guard adopts an already-current marker instead of stacking another, and an overlapping `popstate` restores its own traversal while a discard prompt is already open.
- The optional live/paused shell marker was deliberately skipped: the core fixes resolve the Task 5 hierarchy and navigation problems without adding another status element.
- Neither `.dev-data/` nor `caos/server/.dev-data/` was staged or deleted.

## Files committed

- `.superpowers/sdd/task-5-report.md`
- `caos/frontend/app/globals.css`
- `caos/frontend/scripts/workbench-smoke.mjs`
- `caos/frontend/src/components/WorkbenchShell.tsx`
- `caos/frontend/src/components/Workspace.tsx`
- `caos/frontend/src/components/report/ReportStudio.test.ts`
- `caos/frontend/src/components/report/ReportStudio.tsx`
- `caos/frontend/src/lib/workbench.test.ts`
- `caos/frontend/src/lib/workbench.ts`

## TDD and verification

- Initial red: the focused source run produced the four intended failures for Cases hierarchy/selection semantics, RV advanced disclosure/caption, Report Studio editor/disclosure order, and the still-native-browser `window.confirm` discard flow.
- Green: focused source regressions passed after each behavior branch was implemented.
- Tournament red/green: a focused assertion first failed for overlapping browser-history requests, then passed after an existing prompt invoked the incoming history-restoration callback. A second focused assertion first failed for reusing the current native marker, then passed after the guard adopted that marker rather than pushing a duplicate.
- Confidence red/green: `node --check scripts/workbench-smoke.mjs` found a duplicate `palette` declaration in the bounded journey update; the local was renamed and the syntax check passed.
- Full frontend units: `npm run test:unit` — 109/109 passed; existing `MODULE_TYPELESS_PACKAGE_JSON` warnings only.
- Lint: `npm run lint` — passed.
- Local TypeScript: `./node_modules/.bin/tsc --noEmit` — passed.
- Production build: `npm run build` — passed with Next.js 16.3.3; all 12 static pages generated.
- Static journey syntax: `node --check scripts/workbench-smoke.mjs` — passed.
- `git diff --check` — passed.

## Bounded browser result

- The existing process on `:8000` answered `/api/health` but served `/cases` as 404, so it was the API-only process rather than the assembled frontend/backend application.
- Per the parent-task direction, no second stack was started. Task 6 owns combined-app assembly and the complete browser journey.
- The existing bounded Playwright journey source now covers native-dialog case cancel/confirm, internal-link cancel, palette cancel, browser Back/Escape, Report Studio Back cancel, case cancel, disclosure opening, and focus return. Execution against an assembled app remains intentionally deferred to Task 6.

## Rewrite tournament

- **Target**: the shared discard orchestration in `caos/frontend/src/components/Workspace.tsx`, `armOwnedHistoryGuard` and `requestDraftDiscard`/`finishDraftDiscard` (one material symbol group; no second material symbol was opened).
- **Winner**: corrected incumbent, incorporating the readability candidate's existing-marker adoption.
- **Ranking**: corrected incumbent; readability guard adoption; ref-only memory candidate; boolean-state speed candidate.
- **Why it won**:
  - Ref ownership preserves the synchronous `selectCase` boolean contract and prevents competing requests from replacing deferred callbacks.
  - React state carries the same request into the native dialog without a second ref/state protocol or extra render trigger.
  - The two narrow corrections repair overlapping `popstate` and same-page marker reuse without changing callers, `beforeunload`, dialog focus behavior, or Report Studio's prop contract.
- **Final code**:

```ts
const state = window.history.state as { caosModelDraftGuard?: boolean; caosReportDraftGuard?: boolean } | null;
if (state?.caosModelDraftGuard || state?.caosReportDraftGuard) {
  modelHistoryGuardRef.current = true;
  return;
}

const requestDraftDiscard = useCallback<RequestDraftDiscard>((detail, confirm, cancel) => {
  if (!modelDraftDirtyRef.current && !reportDraftDirtyRef.current) {
    confirm();
    return true;
  }
  if (discardPromptRef.current) {
    cancel?.();
    return false;
  }
  const next = { detail, confirm, cancel };
  discardPromptRef.current = next;
  setDiscardPrompt(next);
  return false;
}, []);
```

- **Impact set**: Workspace case/route/link/history callers; Report Studio pathway selection; WorkbenchShell palette ordering; unit/source regressions; bounded smoke journey. No signature or governed-data contract changed.
- **Verification**: targeted red/green source checks, 109/109 full units, TypeScript, lint, build, and smoke syntax all passed. Combined-app browser execution remains Task 6.

`DraftDiscardDialog` was reviewed but skipped as a second tournament target because it deliberately follows the existing `AcceptDialog` native show/focus/close/focus-return pattern.

## Confidence review

Least confident about (ranked):

1. A second browser Back action could occur while the discard dialog was already open.
   investigated → the second `popstate` had already traversed history, but the incumbent rejected its prompt without invoking that request's restoration callback.
   verdict     → CONFIRMED bug.
   patch       → an existing prompt now calls the incoming optional cancel callback; focused red/green source coverage pins the branch.
2. A same-page confirmed discard could leave one current native sentinel and later push another.
   investigated → logical ownership was cleared on confirm while the native marker could remain current for a pathway change.
   verdict     → CONFIRMED bug.
   patch       → arming first adopts either existing CAOS marker. URL-sync case changes may replace state; pathway changes reuse the current marker.
3. The updated bounded browser journey might not parse before Task 6 runs it.
   investigated → `node --check` found a duplicate `const palette` in the script's single module scope.
   verdict     → CONFIRMED bug.
   patch       → renamed the dirty-draft palette locator; syntax check is green.
4. Cancel/Escape might lose focus or nest a modal behind the command palette.
   investigated → the discard dialog matches the established `AcceptDialog` pattern; ordinary triggers are captured before `showModal()`. Internal-link capture closes an open palette before requesting discard, and the palette case action closes first.
   verdict     → fine by source and bounded-journey assertions; assembled browser execution remains Task 6.
5. RV disclosure could reset bounds or misstate the table width.
   investigated → all six bounds remain controlled state inside a non-conditional native `details`; `loanColumns` has 26 fields plus Locator, matching the 27 caption and `7 + 2 + 6 + 11 + 1` column groups.
   verdict     → fine.
6. Report Studio reordering could remove governed authoring/lifecycle behavior.
   investigated → only JSX placement/disclosure and textarea rows changed; the existing block state, autosave queue, recovery, conflict, restore, freeze, file, export, and request-change handlers remain referenced. Full report/unit tests and the production build pass.
   verdict     → fine.
7. Native discard conversion could weaken hard-close protection.
   investigated → `beforeunload` registration, dirty checks, and cleanup remain unchanged; `window.confirm` is absent from Workspace and Report Studio.
   verdict     → fine.

Fixed: overlapping history restoration; duplicate native guard adoption; bounded smoke syntax.

Verified fine: focus-pattern parity, no nested palette dialog, controlled RV disclosure state, 27-column caption, Report Studio governed lifecycle retention, Cases `aria-current`, and unchanged `beforeunload` protection.

Still open: assembled-app execution of the bounded browser journey, intentionally assigned to Task 6.

## Review correction

The follow-up review's five Important findings and one Minor finding are resolved:

1. `finishDraftDiscard` no longer clears either child dirty ref or logical history ownership before invoking a deferred action. The child now retires protection only when it reports clean or unmounts; a same-route link or boundary Back no-op therefore remains protected.
2. Capture-phase internal-link interception now accepts only an unmodified primary same-tab gesture. Middle, Cmd/Ctrl, Shift, Alt, `_blank`, and other browsing-context targets retain native behavior without prompting the dirty original tab. Browsing-context keywords are handled ASCII case-insensitively.
3. Report Studio reports clean on actual unmount. A confirmed same-URL pathway change reports clean before changing pathway, so it retires exactly the one current sentinel rather than clearing ownership early.
4. Cmd/Ctrl+K checks for an already-open native dialog and cannot stack the command palette over discard or another modal.
5. The bounded smoke source now covers dirty case, link, palette, pathway, and history cancel/confirm branches; Escape and focus return; modified-click bypass; same-route protection; one-boundary history confirmation; and nested-palette prevention. Pure unit checks cover gesture disposition and single deferred callback resolution.
6. Cases filtered-empty state now has a primary **Reset filters** action that clears search and restores the all-authority filter.

### Correction TDD and gates

- Focused RED: four intended failures pinned the missing reset action, premature discard ownership clearing, gesture helper, and callback resolver. A tournament edge case then failed for uppercase `_SELF`.
- Focused GREEN: `npm run test:unit -- --test-name-pattern='Cases makes|draft navigation uses|draft link interception|discard resolution|Workspace owns'` — 111 tests discovered, all passed; the direct `_SELF` run passed 27/27.
- Full frontend units after the tournament: `npm run test:unit` — 111/111 passed; existing `MODULE_TYPELESS_PACKAGE_JSON` warnings only.
- Lint: `npm run lint` — passed.
- Local TypeScript: `./node_modules/.bin/tsc --noEmit` — passed.
- Production build: `npm run build` — passed; all 12 static pages generated.
- Static journey syntax: `node --check scripts/workbench-smoke.mjs` — passed.
- `git diff --check` — passed.

### Bounded history trace

A focused standalone Chromium trace pushed a same-URL guard entry, then observed the first Back emit exactly one `popstate` to the prior state. The confirmed second Back crossed the document and destroyed the page execution context. This validates the implementation split: confirmed same-document traversal is consumed by the `popstate` branch; confirmed cross-document traversal is admitted by the one-shot `beforeunload` branch. The existing one-second fence is used only when neither event occurs, where it re-arms a still-dirty owner. The assembled CAOS route remains unavailable because the process on `:8000` is API-only; Task 6 owns the combined-app smoke execution.

### Correction rewrite tournament

- **Target 1**: `Workspace` pending-link release within the draft/history orchestration. **Winner: Snippet B**, replacing the one-property `{ from }` ref with the origin URL string. It preserves the exact ownership side effects while removing one allocation/property lookup and making the comparison direct.
- **Target 2**: `isSameTabPrimaryGesture`. **Winner: Snippet B**, combining the modifier predicate and normalizing the target keyword for ASCII case-insensitive `_self`. It remains allocation-free for the common empty target, preserves every bypass branch, and fixes uppercase `_SELF` under a focused red/green test.
- **Impact-set re-check**: Workspace model/report callbacks, case selection, Next link replay, `popstate`, `beforeunload`, Report Studio pathway selection, unit contracts, TypeScript, and production build all pass without signature changes.
- **Final code**:

```ts
const pendingDraftLinkRef = useRef<string | null>(null);

const releaseCleanDraftGuard = useCallback(() => {
  const from = pendingDraftLinkRef.current;
  pendingDraftLinkRef.current = null;
  if (typeof window !== "undefined" && from !== null && window.location.href !== from) {
    modelHistoryGuardRef.current = false;
    return;
  }
  retireOwnedHistoryGuard();
}, [retireOwnedHistoryGuard]);

export function isSameTabPrimaryGesture(event: DraftLinkGesture, target = "") {
  return event.button === 0
    && !(event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)
    && (!target || target.toLowerCase() === "_self");
}
```

### Correction confidence review

Least confident about (ranked):

1. Confirmed browser Back could either double-traverse or drop protection at a boundary.
   investigated → the Chromium trace proved the sentinel Back emits one same-document `popstate` and the confirmed second Back can cross documents; the code consumes exactly one confirmed event and re-arms only after a no-event fence while the child is still dirty.
   verdict     → fine after event-driven trace and focused source coverage.
   patch       → explicit confirmed-pop/beforeunload branches plus bounded no-event re-arm.
2. A same-route confirmed link could be treated as a completed discard.
   investigated → replay does not mutate dirty refs; without URL change or child cleanup, the owner and `beforeunload` fence remain live. The next case change still prompts in the smoke source.
   verdict     → fine.
   patch       → pending-origin comparison; no optimistic clearing in `finishDraftDiscard`.
3. Report pathway confirm might retire zero or two sentinels.
   investigated → `change()` reports clean synchronously once before `setPathway`; later load/cleanup reports are idempotent because retirement is already in flight or ownership is false.
   verdict     → fine.
   patch       → unmount cleanup plus clean-state-owned retirement.
4. Modified gestures or a modal shortcut could create an unwanted same-tab/nested flow.
   investigated → every modifier/button/target branch has a pure check; command opening is guarded by the native `dialog[open]` condition and the bounded smoke asserts both behaviors.
   verdict     → fine.
5. The tournament simplification could desynchronize source coverage.
   investigated → the full unit gate caught the stale `{ from }` regex after the string-ref winner was applied.
   verdict     → CONFIRMED test-contract drift.
   patch       → updated the sentinel ownership assertion; 111/111 now pass.
6. The expanded smoke could be syntactically valid but still race an assembled app.
   investigated → syntax passes and interactions use bounded Playwright waits, but no combined frontend/backend route is currently available.
   verdict     → open by assignment.
   patch       → n/a; Task 6 executes the full combined journey.

Fixed: premature discard clearing, history no-op re-arm, modified-link interception, Report cleanup/retirement, nested palette opening, Cases filtered-empty recovery, and tournament test-contract drift.

Verified fine: one-boundary history event ordering, same-route protection, same-URL pathway retirement, focus/native dialog pattern, `beforeunload`, and all compile/build contracts.

Still open: combined-app execution of the expanded smoke journey, owned by Task 6.

## Final history-race correction

The last confirmed race is resolved with one explicit `DraftHistoryTraversal` owner `{ token, kind }` for `confirmed`, `retire`, and `restore` moves. The former confirmed/suppress/retiring/rearm booleans and shared unbound timer are gone.

- An autosave clean callback during confirmed Back sees the active token and cannot start a second retirement Back.
- `popstate`, confirmed `beforeunload`, and the no-event fence finish only the currently matching token; duplicate and stale completions are inert.
- Only an active `confirmed` token admits `beforeunload`. A true history-boundary timeout first clears that token, so a later unrelated unload remains protected while the editor is dirty.
- Confirmed completion waits one animation frame for child cleanup/unmount, then re-arms only if the same traversal is still current and a child is still dirty.
- Retirement and restoration retain their previous single-move behavior, but rearm now follows current dirty state instead of a stale remembered request.

### Executable interleaving evidence

TDD produced five focused executable checks in `workbench.test.ts`:

1. confirmed token 1 accepts the first traversal and rejects autosave-triggered retire token 2;
2. one pop consumes token 1, a duplicate completion is inert, and token 1 cannot clear newer restore token 2;
3. a no-event completion clears confirmed unload permission before a new traversal can start;
4. confirmed/retire completion re-arms only for current dirty state, while restore never re-arms;
5. Workspace integration uses the single traversal ref and no legacy competing flags.

RED: the first three checks failed because the helpers were absent; the Workspace binding check failed against the legacy refs; the current-dirty rearm check then reproduced a stale rearm for a clean owner.

GREEN: the focused workbench run passed 32/32 and the Report Studio ownership run passed 17/17. The final full suite passed 116/116.

### Final correction rewrite tournament

- **Winner**: Snippet B for both capped targets: `caos/frontend/src/lib/workbench.ts` traversal helpers and `caos/frontend/src/components/Workspace.tsx` token ownership.
- **Justification**:
  - The helper winner removes dead `rearmRequested` state; current child dirty refs are the authoritative settlement input.
  - Workspace makes `onNoEvent` optional, eliminating restore's no-op callback while preserving token/timer side effects.
  - The active-traversal early return leaves less mutable surface without changing any caller or history outcome.
- **Final code**:

```ts
export type DraftHistoryTraversal = {
  token: number;
  kind: "confirmed" | "retire" | "restore";
};

export function beginDraftHistoryTraversal(active: DraftHistoryTraversal | null, token: number, kind: DraftHistoryTraversal["kind"]) {
  if (active) return { active, started: false };
  return { active: { token, kind }, started: true };
}

export function finishDraftHistoryTraversal(active: DraftHistoryTraversal | null, token: number) {
  if (!active || active.token !== token) return { active, completed: null };
  return { active: null, completed: active };
}
```

- **Verification**: `node --test src/lib/workbench.test.ts --test-name-pattern='confirmed history owns|history pop settles|confirmed boundary timeout|history completion rearms|Workspace binds every history move'` — 32/32 passed. Impact-set re-check via local TypeScript, 116/116 full units, lint, build, and fresh diff passed.

### Final correction confidence review

Least confident about (ranked):

1. Autosave could still trigger clean retirement between confirmed Back and `popstate`.
   investigated → `retireOwnedHistoryGuard` returns while `historyTraversalRef` owns token 1; the executable begin test proves retire token 2 is rejected and the pop test proves token 1 settles once.
   verdict     → fine after token integration.
   patch       → replaced competing refs with the single traversal token.
2. A stale timer could clear a newer traversal or preserve unrelated unload permission.
   investigated → the fence closes over its token and `finishDraftHistoryTraversal` refuses a mismatch; boundary completion returns active state to null, and only `isConfirmedDraftHistoryTraversal(active)` admits unload.
   verdict     → fine under executable stale-token/boundary checks.
   patch       → token-bound fence and confirmed type predicate.
3. Confirmed completion might rearm before child cleanup or after another traversal begins.
   investigated → the animation-frame callback checks both no active traversal and the unchanged completed token before reading current child dirty refs.
   verdict     → fine by direct path trace and current-dirty tests.
   patch       → token-checked deferred rearm.
4. A dirty-then-clean owner during retirement could leave a stale sentinel.
   investigated → the initial `rearmRequested` field remembered transient dirtiness even after autosave returned clean.
   verdict     → CONFIRMED adjacent bug.
   patch       → removed the field; `draftHistoryNeedsRearm` now uses current dirty state only. Focused red/green pins it.
5. The no-event fence still has a bounded window while the requested confirmed move is active.
   investigated → History API exposes no completion event for a boundary no-op; the fence remains necessary, but its permission is now scoped to the active confirmed token and deterministically removed at timeout.
   verdict     → by-design browser boundary.
   patch       → minimal one-second token-bound fence; no additional timer/state machine.

Fixed: double Back/stuck-retirement race, stale timer settlement, confirmed unload leakage after timeout, and stale clean-owner rearm.

Verified fine: one-pop settlement, duplicate/stale completion, autosave-clean interleaving, boundary cleanup, current-dirty rearm, Report Studio sentinel ownership, lint, TypeScript, and production build.

By-design: a bounded no-event fence is required because History API does not signal a boundary no-op; it carries only the active confirmed token.

Still open: assembled-app execution of the full smoke journey remains Task 6.

## Observable destination-state correction

The final review removes the remaining time-window and provenance assumptions. Every CAOS-owned history entry now carries a unique `caosDraftHistoryEntryId`; the base and sentinel cross-reference their exact expected destinations. A traversal changes from `pending` to `observed` only when the real `PopStateEvent.state` names that destination. A mismatched, delayed, or duplicate pop cannot settle the active traversal, and the animation-frame settlement rechecks the browser's current `history.state` before completion.

`beforeunload` no longer exempts any active custom traversal. It always protects a dirty Model Builder or Report Studio draft. A tagged same-document destination is handled by the custom dialog and state match; an untagged cross-document predecessor deliberately retains the browser-native prompt as the safe fallback. At a proven direct-load boundary, `navigation.canGoBack === false` progressively re-arms the sentinel without clearing either child dirty ref. When the API is unavailable, the implementation fails closed through `beforeunload` rather than opening an unload-permission timer.

### Observable-state TDD and browser evidence

- RED: `node scripts/draft-history-smoke.mjs` failed before browser launch because the exact production `draftHistoryEntryId` observer contract did not exist.
- GREEN: the focused Chromium script completed in 5.0 seconds using real `history.replaceState`/`pushState`, `history.back`/`forward`, `PopStateEvent.state`, and browser `beforeunload` dialogs.
- A captured old pop was delivered after a newer traversal began and did not settle it; the later event carrying the expected destination did.
- A synchronous duplicate expected-state pop matched once because the first match moved the traversal into `observed` phase.
- A direct-load base emitted no pop at its true Back boundary, then an unrelated reload still raised the dirty native prompt.
- A cross-document Back raised the native dirty prompt and remained on the editor when dismissed.
- Sentinel Back/Forward restoration and confirmed single-Back settlement used the actual tagged base, sentinel, and prior entry states.

Final gates: `npm run test:unit` passed 112/112; `npm run lint`, `npx tsc --noEmit`, `npm run build`, `node --check scripts/draft-history-smoke.mjs`, `node --check scripts/workbench-smoke.mjs`, and `git diff --check` all passed. The build generated all 12 static pages. Existing `MODULE_TYPELESS_PACKAGE_JSON` warnings remain unchanged.

### Observable-state rewrite tournament

- **Winner**: Incumbent holds for `caos/frontend/src/lib/workbench.ts:179-190` and `caos/frontend/src/components/Workspace.tsx:401-418`.
- **Justification**:
  - Speed challengers could inline entry parsing, but duplicated the trust-boundary check and did not improve the event-dominated path measurably.
  - Memory challengers could mutate the active traversal to avoid one small object, but that weakens caller-visible phase transitions and makes duplicate handling harder to audit.
  - Readability challengers extracted more predicates, increasing the history orchestration surface without reducing branches or preserving a clearer impact set.
- **Final code**:

```ts
export function observeDraftHistoryPop(active: DraftHistoryTraversal | null, state: unknown) {
  if (!active || active.phase !== "pending" || draftHistoryEntryId(state) !== active.expectedDestinationId) {
    return { active, matched: false };
  }
  return { active: { ...active, phase: "observed" as const }, matched: true };
}
```

- **Verification**: `node scripts/draft-history-smoke.mjs` passed the real-entry Chromium interleavings; the impact set (`Workspace` caller, smoke injection, unit source contract) passed 112 units, TypeScript, lint, and the production build with no signature drift.

### Observable-state confidence review

Least confident about (ranked):

1. Next App Router could overwrite or copy a CAOS entry ID during navigation.
   investigated → Next 16.3.3's installed `HistoryUpdater` spreads custom state when requested and writes navigation state before Workspace effects. The route-tagging effect detects a copied current ID at a changed URL, removes only CAOS metadata, assigns a new ID, and preserves Next's `__NA`/router tree.
   verdict     → fine by installed-source trace, TypeScript, and build.
   patch       → route-specific ID normalization.
2. Autosave clean between confirmed Back and pop could start another retirement.
   investigated → retirement returns while one traversal is active; matching completion reads the current child dirty refs only after the browser-state/rAF check. The focused delayed-pop trace kept the newer owner intact.
   verdict     → fine.
   patch       → expected-destination phase owner replaces unload permission.
3. A delayed or duplicate pop could settle the wrong move.
   investigated → the observer compares `event.state` to the active expected ID and accepts only `pending`; the focused Chromium trace exercised both an old delayed state and a synchronous duplicate.
   verdict     → fine.
   patch       → observable state match plus `observed` duplicate fence.
4. A direct-load or cross-document boundary could lose the draft after custom confirmation.
   investigated → no custom traversal bypasses `beforeunload`; direct-load no-op and cross-document Back both raised later/native protection in Chromium.
   verdict     → fine, with browser-native cross-document confirmation by design.
   patch       → removed the one-second unload exemption entirely.
5. Settlement could run after the browser moved again between pop and animation frame.
   investigated → settlement re-reads `window.history.state` and refuses a different destination; the token-bound no-event fence then reconciles current sentinel/dirty state safely.
   verdict     → fine by path trace and full gates.

Fixed: unobservable pop provenance, duplicate settlement, direct-boundary unload window, cross-document unsafe exemption, and stale autosave retirement.

Verified fine: Next custom-state coexistence, exact base/sentinel/prior matching, no-event dirty protection, source/unit contracts, lint, TypeScript, build, and smoke syntax.

By-design: cross-document history confirmation may show the browser-native prompt after the custom dialog because native protection is the only causally safe fallback.

Still open: Task 6 owns the full combined-app journey; the focused real-history Chromium trace is complete.

## Commit

- Subject: `feat(frontend): reduce workspace cognitive load`
- Correction subjects: `fix(frontend): preserve dirty draft navigation`; `fix(frontend): serialize draft history traversal`
- Observable-state correction subject: `fix(frontend): match draft history destinations`
- Trailer: `Co-Authored-By: Codex Opus 4.8 <noreply@anthropic.com>`

## Remaining risks

- Task 6 should run the updated combined-app browser journey at its bounded viewports, including native dialog focus return and history sentinel instrumentation.
- Node's existing `MODULE_TYPELESS_PACKAGE_JSON` warning remains unrelated to Task 5 behavior.
- Runtime `.dev-data/` directories remain untracked and intentionally untouched.
