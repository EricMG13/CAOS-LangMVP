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

## Commit

- Subject: `feat(frontend): reduce workspace cognitive load`
- Trailer: `Co-Authored-By: Codex Opus 4.8 <noreply@anthropic.com>`

## Remaining risks

- Task 6 should run the updated combined-app browser journey at its bounded viewports, including native dialog focus return and history sentinel instrumentation.
- Node's existing `MODULE_TYPELESS_PACKAGE_JSON` warning remains unrelated to Task 5 behavior.
- Runtime `.dev-data/` directories remain untracked and intentionally untouched.
