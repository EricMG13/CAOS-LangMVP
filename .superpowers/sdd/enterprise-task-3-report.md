# Enterprise Task 3 — Offline-native fonts

## Outcome

Complete. The frontend now uses only OS-native CSS font stacks. It has no shipped `next/font/google`, `fonts.googleapis.com`, or `fonts.gstatic.com` reference, and the production build succeeds inside the restricted sandbox without network escalation.

## Files

- `caos/frontend/app/layout.tsx`
- `caos/frontend/app/globals.css`
- `caos/frontend/src/lib/workbench.test.ts`
- `caos/frontend/scripts/workbench-smoke.mjs`
- `caos/frontend/src/components/model/ModelBuilder.tsx`
- `caos/frontend/src/components/model/ModelBuilder.test.ts`
- `.superpowers/sdd/task-3-brief.md`
- `.superpowers/sdd/enterprise-task-3-report.md`
- `.superpowers/sdd/progress.md`

The two Model Builder files were an authorized root-cause expansion. The complete browser smoke exposed a pre-existing race: the successful queued-build message was set before the immediate MISSING-to-QUEUED authority refresh, whose generation change then cleared it. The fix awaits a current refresh, preserves false returns for stale generations, explicitly releases the pending build state after the authority change, and only then publishes success feedback.

The smoke harness also contains narrowly scoped pre-existing locator repairs discovered while completing the required full smoke: two compacted digest checks now use their exact `title` authority, and four consolidated Revenue-growth labels now require exact matching. These retain the original identity and form-field invariants.

## Strict TDD evidence

1. The new shipped-font assertion failed before implementation with 113 passes and one failure because `app/layout.tsx` imported `next/font/google`.
2. Removing the three Google font initializers and defining the three native CSS variables made the assertion pass.
3. The queued-build regression failed against the old ordering because success feedback preceded `refresh`.
4. The strengthened regression also required pending cleanup after the refresh invalidated the action generation; the implementation then passed the focused test and the full suite.

## Verification

Run from `caos/frontend` unless noted:

- `npm run lint -- --max-warnings=0` — passed with zero warnings.
- `npx tsc --noEmit` — passed.
- `npm run test:unit` — 115 passed, 0 failed.
- `node --check scripts/workbench-smoke.mjs` — passed.
- `npm run build` — passed in the restricted sandbox without network escalation; Next.js 16.3.3 compiled in 232 ms and generated 12/12 static pages.
- Shipped source scan for `next/font/google`, `fonts.googleapis.com`, and `fonts.gstatic.com` — zero matches outside tests.
- `.next` artifact scan for the same references — zero matches.
- `npm run test:workbench` against the established local backend — passed; DCL 48.6 ms (limit 250 ms), FCP 128 ms (limit 400 ms), one `/api/cases` request, and zero external Google font requests.
- `git diff --check` — passed.

The native-font geometry adjustment was measured rather than relaxed generically. Across QUEUED, RUNNING, SUCCEEDED, ACCEPTED, FAILED, and PAUSED, the acceptance region kept x=657 px and width=742 px; height stayed 132–133 px. Vertical positions varied between 366, 476, and 480 px because the preceding execution DAG reflowed under native glyph metrics. The smoke therefore continues to require the region in every state, identical horizontal geometry, and its 132–133 px reserved height, while no longer treating the preceding DAG's variable height as acceptance-region geometry.

## Confidence review

- Traced every `refresh` and `actionGeneration` caller. Only the queued-build flow consumes the new boolean; existing callers safely ignore it. Superseded, aborted, failed, and wrong-generation refreshes return false and cannot publish queued success.
- Adversarially checked the `finally` path. An intended authority transition increments `actionGeneration`, so the successful current-refresh path explicitly clears `pending` before setting the message; the regression pins both operations.
- Verified external font protection at source, build-artifact, and browser-request layers.
- Verified typography roles remain separate through `--font-sans`, `--font-display`, and `--font-mono`; no font-size rule, asset, preload, package, or runtime script was added.
- Verified the locator repairs strengthen exact authority selection and do not change product behavior.

No further defect was found after the pending-cleanup correction.

`rewrite-tournament` was not run because the user explicitly prohibited rewrite tournaments for this session. This override takes precedence over the otherwise applicable post-edit workflow.

## Commits

- Implementation: `92626bf`
- Evidence: this report and the Task 3 progress update are committed separately so the report can record the immutable implementation SHA; the evidence commit SHA is reported in the handoff.
