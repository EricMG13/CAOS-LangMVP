# Task 3 — Offline-native fonts

## Goal

Remove every build/runtime dependency on externally hosted fonts while preserving the existing typography roles and browser performance contract.

## Owned files

- `caos/frontend/app/layout.tsx`
- `caos/frontend/app/globals.css`
- `caos/frontend/src/lib/workbench.test.ts`
- `caos/frontend/scripts/workbench-smoke.mjs`
- `.superpowers/sdd/enterprise-task-3-report.md`
- `.superpowers/sdd/progress.md`

Do not modify other files without first reporting why the root cause requires it.

## Required implementation

1. Add the smallest failing source assertion proving the frontend has no `next/font/google`, `fonts.googleapis.com`, or `fonts.gstatic.com` reference.
2. Remove the three `next/font/google` font initializers and their generated `<html>` classes.
3. Define `--font-sans`, `--font-display`, and `--font-mono` as OS-native CSS stacks in `:root`; do not add packages, assets, preload links, or runtime JavaScript.
4. Extend the existing browser smoke only as needed to fail on an external Google font request while retaining its FCP/DCL evidence.

## Acceptance

From `caos/frontend`:

```sh
npm run lint -- --max-warnings=0
npx tsc --noEmit
npm run test:unit
npm run build
```

Additionally:

- repository/source search returns no forbidden font references in shipped frontend code;
- build completes in the restricted sandbox without network escalation;
- the existing workbench browser smoke passes and reports FCP/DCL within its declared limits;
- `git diff --check` passes;
- worktree is clean after a focused commit;
- `.superpowers/sdd/enterprise-task-3-report.md` records the red test, final commands, timings, files, and commit. The pre-existing `.superpowers/sdd/task-3-report.md` belongs to an earlier product-plan task and must remain unchanged.

## Constraints

- Follow `caos/frontend/AGENTS.md` and the local Next font guide.
- Reuse native CSS and existing tests; no dependency or abstraction.
- Preserve accessible sizes and the current sans/display/mono hierarchy.
- Run `confidence-review` before completion. `rewrite-tournament` is skipped only if the implementation remains declarative/trivial; record that decision.
