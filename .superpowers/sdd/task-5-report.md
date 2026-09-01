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

## Commit

- Subject: `feat(frontend): reduce workspace cognitive load`
- Trailer: `Co-Authored-By: Codex Opus 4.8 <noreply@anthropic.com>`

## Remaining risks

- Task 6 should run the updated combined-app browser journey at its bounded viewports, including native dialog focus return and history sentinel instrumentation.
- Node's existing `MODULE_TYPELESS_PACKAGE_JSON` warning remains unrelated to Task 5 behavior.
- Runtime `.dev-data/` directories remain untracked and intentionally untouched.
