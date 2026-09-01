# Task 3 report — Unify Accept, Sign-Off, and Freeze commit rituals

## Summary

- Acceptance now reviews local authority-slot changes from `run.nodes` against the currently accepted snapshot, including added, replaced, and removed module slots, source-set identity, and the exact snapshot digest being replaced. It does not infer byte-level artifact changes.
- Every run state owns the same reserved acceptance region: queued/running progress, failed or paused remedy, succeeded-not-accepted action, and accepted identity. Unfinished DAG nodes reserve the completed-output row so the region does not shift when artifact links appear.
- Model Builder now presents one ordered sign-off sequence in the existing approval grammar: what will bind, changed-slot count, exact preview/build/registry/parent authority, conflict/rebase state, required actor note, and the single next action.
- Report Studio now keeps a reserved freeze action area and shows all four independent prerequisites: write access, exact saved revision, current model selection, and required model availability. Unmet model prerequisites retain case context when linking to Model Builder or Run Console.
- Reader surfaces remain fail-closed and non-interactive. Acceptance, sign-off, and freeze request bodies are unchanged, and the server remains authoritative for authorization and digest revalidation.
- The pre-existing Model Builder export polling checkpoint remains intact. No server file was modified, and `.dev-data/` was neither staged nor deleted.

## Files committed

- `caos/frontend/app/globals.css`
- `caos/frontend/scripts/workbench-smoke.mjs`
- `caos/frontend/src/components/Workspace.tsx`
- `caos/frontend/src/components/model/ModelBuilder.test.ts`
- `caos/frontend/src/components/model/ModelBuilder.tsx`
- `caos/frontend/src/components/report/ReportStudio.test.ts`
- `caos/frontend/src/components/report/ReportStudio.tsx`
- `caos/frontend/src/components/report/reportStudioState.test.ts`
- `caos/frontend/src/components/report/reportStudioState.ts`
- `caos/frontend/src/lib/api.ts`
- `caos/frontend/src/lib/workbench.test.ts`
- `caos/frontend/src/lib/workbench.ts`

## Tests and verification

- TDD red: focused Node tests failed as expected before implementation because `acceptanceSlotSummary` and `reportStudioState.ts` did not exist and the Model Builder/freeze approval sequences were absent.
- Focused green: `node --test src/lib/workbench.test.ts src/components/model/ModelBuilder.test.ts src/components/report/ReportStudio.test.ts src/components/report/reportStudioState.test.ts` — 49/49 passed; existing `MODULE_TYPELESS_PACKAGE_JSON` warnings only.
- Full frontend unit suite: `npm run test:unit` — 96/96 passed; existing `MODULE_TYPELESS_PACKAGE_JSON` warnings only.
- Strict lint: `npm run lint -- --max-warnings=0` — passed.
- Local TypeScript: `./node_modules/.bin/tsc --noEmit -p .` — passed.
- Production build: `npm run build` — passed with Next.js 16.3.3; all 12 static pages generated.
- Focused server contracts: `caos/server/.venv/bin/python -m pytest -q` against acceptance tamper/idempotency, preview-to-sign-off identity, all six sign-off build-identity parameters, freeze wire round-trip, and freeze authority-drift cases — 11/11 passed; one upstream Starlette deprecation warning.
- `git diff --check` and staged-diff checks — passed.
- Source contract checks — no server diff; accept remains a bodyless POST, sign-off retains build/parent/registry/assumptions/generation/preview/head/note, and freeze retains `draft_id`, `draft_version`, and `draft_digest`.
- `test:workbench` was extended for run-state geometry, both accept-dialog focus-restoration exits, governed report prerequisite links, and Reader acceptance gating. The combined-app run was stopped after a bounded silent wait; Task 6 owns the full rerun against a stable assembled environment.

## Rewrite tournament

### `RunStatus` acceptance renderer

- **Winner**: Snippet B, replacing the nested conditional in `caos/frontend/src/components/Workspace.tsx` (`RunStatus` acceptance-state region).
- **Justification**:
  - Explicit branches make the precedence of accepted, succeeded, failed, paused, and waiting authority states reviewable without changing the component contract.
  - Each state retains the incumbent text, role gate, remedy, and action; no caller, signature, or side effect changes.
  - The longer form is easier to extend safely than a five-arm nested JSX conditional and has no meaningful runtime cost.
- **Final code**:

```tsx
let acceptance: ReactNode;
if (acceptedSnapshotId) {
  acceptance = <>
    <span className="status success">Accepted — visible authority</span>
    <span className="mono muted">{acceptedSnapshotId}</span>
  </>;
} else if (run.status === "succeeded") {
  acceptance = <>
    <span className="status warning">Ready for acceptance</span>
    <p>Review the exact authority change, then accept this analytical snapshot.</p>
    {writeAccess === "yes"
      ? <button className="button primary" disabled={pendingAction === "accept-run"} onClick={acceptRun}>{pendingAction === "accept-run" ? "Accepting…" : "Accept analytical snapshot"}</button>
      : <p className="muted">{writeAccess === "unknown" ? "Confirming access…" : "Acceptance is an analyst action."}</p>}
  </>;
} else if (run.status === "failed") {
  acceptance = <>
    <span className="status critical">Acceptance blocked</span>
    <p>Review the execution failure, then compile a new route.</p>
  </>;
} else if (run.status === "paused") {
  acceptance = <>
    <span className="status warning">Acceptance blocked</span>
    {run.error?.code === "SOURCE_SET_EMPTY" ? <><p>Upload governed source material before execution can continue.</p><Link className="button small" href={withQuery("/sources/", { case: caseId })}>Open Sources</Link></>
      : run.error?.code === "PLAN_APPROVAL_REQUIRED" ? <p>Review and approve the persisted research plan below.</p>
        : <><p>Resolve the paused execution before acceptance.</p>{resumeSlot}</>}
  </>;
} else {
  acceptance = <>
    <span className="status running">Acceptance waiting</span>
    <p>{complete} of {run.nodes.length} module slots complete. Acceptance unlocks only after the route succeeds.</p>
  </>;
}
```

- **Verification**: the focused 49-test command and local TypeScript check passed. Grep impact analysis found only the three existing `RunStatus` call sites through `RunConsole`/inline run surfaces; their prop contract is unchanged.

### `acceptanceSlotSummary`

- **Winner**: Incumbent holds in `caos/frontend/src/lib/workbench.ts`.
- **Justification**:
  - Stable first-seen ordering is explicit for both current and previous slot lists.
  - Set membership keeps the implementation linear and removes duplicate module slots before classification.
  - One-pass challengers saved negligible allocation for a single-digit module set but were longer and easier to get wrong.
- **Final code**:

```ts
export function acceptanceSlotSummary(
  runNodes: readonly { module_id: string }[],
  replacedArtifacts: readonly { module_id: string }[],
) {
  const next = [...new Set(runNodes.map((node) => node.module_id))];
  const previous = [...new Set(replacedArtifacts.map((artifact) => artifact.module_id))];
  const nextSet = new Set(next);
  const previousSet = new Set(previous);
  return {
    added: next.filter((moduleId) => !previousSet.has(moduleId)),
    replaced: next.filter((moduleId) => previousSet.has(moduleId)),
    removed: previous.filter((moduleId) => !nextSet.has(moduleId)),
  };
}
```

- **Verification**: the duplicate-slot concrete case returns added `CP-1`, replaced `CP-0`/`CP-5`, and removed `CP-2`; the focused 49-test command and TypeScript caller check passed.

## Confidence review — Task 3 frontend diff

Least confident about (ranked):

1. Acceptance geometry could still move when completed artifacts gained their link row.
   investigated → the acceptance panel had a fixed minimum height, but unfinished DAG nodes omitted the existing `Open output` row.
   verdict     → CONFIRMED bug.
   patch       → unfinished nodes now retain an `aria-hidden`, visually hidden placeholder row; source regression coverage pins it.
2. Missing source-set versions might render as a malformed label.
   investigated → the initial fallback interpolated the literal text after an unconditional `v`.
   verdict     → CONFIRMED bug.
   patch       → version labels now branch before adding the `v`; a regression assertion rejects `vUnavailable`.
3. Reader or unresolved identity could receive an irreversible action.
   investigated → Workspace initializes as Reader, normalizes unknown served roles to Reader, derives a tri-state write gate, and each new action is absent unless the gate is affirmative. Model sign-off and report freeze remain inside their existing Reader gates.
   verdict     → fine (source tests plus existing role-normalization coverage).
   patch       → n/a.
4. Moving controls could alter digest-bound requests or weaken server validation.
   investigated → staged diff contains no changes to the three request payloads and no server changes. The API still enforces case-write authorization; runtime acceptance re-hashes source/artifact inputs, sign-off reconstructs and compares the preview, and freeze reloads the exact draft and model authority.
   verdict     → fine (source trace plus 11 focused server regressions).
   patch       → n/a.
5. The new browser checks might hide a live integration failure.
   investigated → the run produced no assertion output before the bounded stop, so there is no captured product failure to patch and no completed browser result to claim.
   verdict     → open.
   patch       → n/a; Task 6 should rerun the combined-app suite.

Fixed: malformed unavailable-version copy; DAG-to-acceptance vertical shift.

Verified fine: Reader gating; native dialog focus contract in source and focused checks; exact request bodies; server authorization and digest revalidation; export-polling WIP isolation.

By-design: the client classifies module authority slots only and explicitly leaves artifact-byte verification to the server.

Still open: full combined-app browser execution, owned by Task 6.

## Impeccable focused audit

| Dimension | Score | Key finding |
|---|---:|---|
| Accessibility | 4/4 | Native dialog semantics/focus remain; headings, definitions, status text, and Reader non-actions are explicit. |
| Performance | 3/4 | New local summaries are bounded; the detector noted the pre-existing 240 ms progress-width transition. |
| Responsive design | 4/4 | Existing min-width/overflow rules contain long identities; reserved regions use block minimums rather than fixed widths. |
| Theming | 4/4 | New CSS uses existing tokens and shared approval/status grammar. |
| Anti-patterns | 4/4 | No new color, motion, card, gradient, glass, or side-stripe vocabulary. |
| **Total** | **19/20** | **Excellent** |

Anti-pattern verdict: pass. The detector's `border-accent-on-rounded` warning is a false positive on the existing zero-radius CSS triangle used for non-color-only warning semantics. Its layout-transition warning is pre-existing, bounded, and covered by the global reduced-motion rule. No Task 3 P0-P3 finding remains. Positive findings include semantic native controls, focus restoration, visible non-color status shapes, token reuse, and fail-closed Reader copy.

## Commit

- Task 3 implementation: `df03d8dc27b1a1eb92eece7610423c3000929f91` (`feat(frontend): unify commit rituals`)
- Task 3 authority correction: `7fe186406b9797114fbd7b3ed019a67d93e52d9a` (`fix(frontend): bind acceptance to latest authority`)
- Task 3 terminal-progress correction: `42c4524bc2d45d8cda1265ac7bccd786dd2d0d5b` (`fix(frontend): align terminal run progress`)

## Remaining risks

- The full combined-app browser journey did not finish in this checkpoint; Task 6 should run `npm run test:workbench` in its final assembled environment and inspect both target viewports.
- The browser geometry assertion is intentionally exact. It now reserves both the acceptance panel and DAG output row, but real-browser confirmation remains deferred with the suite.
- `.dev-data/` remains untracked user/runtime state and was intentionally untouched.

## Review correction — latest acceptance and the visible lens

### Summary

- Acceptance replacement counts, the exact predecessor digest, and accepted-run identity now bind to `SnapshotView.latest_accepted`, which is the same pointer the server replaces. `SnapshotView.accepted` remains the effective visible/pinned reader lens.
- A run matching the latest acceptance always renders as accepted and never re-offers the action. When `switch_required` is true, Run Console names the visible snapshot that remains pinned, while the shell labels its snapshot and source-set values as the visible lens and warns that the latest acceptance differs.
- Accept remains a bodyless POST. No visible snapshot is switched implicitly, and the existing explicit switch route remains the only client action that changes a pinned lens.
- The bounded browser fixture now synthesizes queued, running, succeeded-not-accepted, accepted, failed, and paused acceptance regions. Its accepted phase serves matching run and snapshot authority ids. The full combined-app browser journey remains owned by Task 6.

### Correction files

- `caos/frontend/scripts/workbench-smoke.mjs`
- `caos/frontend/src/components/WorkbenchShell.tsx`
- `caos/frontend/src/components/Workspace.tsx`
- `caos/frontend/src/lib/workbench.test.ts`
- `caos/frontend/src/lib/workbench.ts`

### TDD and verification

- TDD red: `node --test src/lib/workbench.test.ts` — 13/17 passed and the four new latest-authority, switch-required, visible-label, and six-state fixture assertions failed for the intended missing behavior.
- Focused green: `node --test src/lib/workbench.test.ts` — 17/17 passed; existing `MODULE_TYPELESS_PACKAGE_JSON` warning only.
- Full frontend unit suite: `npm run test:unit` — 100/100 passed; existing module-type warnings only.
- Strict lint: `npm run lint` — passed.
- Local TypeScript: `./node_modules/.bin/tsc --noEmit` — passed.
- Production build: `npm run build` — passed; all 12 static pages generated.
- Server acceptance/switch regressions: five focused pytest cases covering missing historical sources, forged artifacts, idempotent acceptance, blocked QA, and newer-accepted/visible-switch divergence — 5/5 passed.
- `git diff --check`, staged-path audit, and trailer audit — passed. No server file or acceptance request body changed.
- Browser execution was not started for this correction; the fixture is source-verified here and Task 6 retains the full assembled-environment run.

### Rewrite tournament — correction

#### `RunStatus` accepted-authority branch

- **Winner**: Incumbent holds in `caos/frontend/src/components/Workspace.tsx` (`RunStatus`, accepted branch).
- **Justification**:
  - The explicit accepted-first branch preserves the required precedence over the succeeded action, so a latest-accepted run cannot fall through to “Ready for acceptance.”
  - Separate `acceptedSnapshotId`, `visibleSnapshotId`, and `switchRequired` inputs mirror the server contract without introducing client authority inference or a new component abstraction.
  - Speed-, allocation-, and terseness-oriented challengers either retained the same branch work or obscured the fail-closed state ordering; none improved verified behavior or maintainability.
- **Final code**:

```tsx
if (acceptedSnapshotId) {
  acceptance = <>
    <span className="status success">Latest accepted authority</span>
    <span className="mono muted">{acceptedSnapshotId}</span>
    {switchRequired
      ? <p>Visible lens remains on <span className="mono">{visibleSnapshotId || "a different snapshot"}</span> until explicitly switched.</p>
      : <p>Visible lens matches the latest accepted authority.</p>}
  </>;
}
```

- **Verification**: `node --test src/lib/workbench.test.ts` — 17/17 passed; `./node_modules/.bin/tsc --noEmit -p .` passed. Impact-set grep found one `RunStatus` definition and one `RunConsole` call; the caller compiles with all three authority inputs.

#### `acceptanceRunFixture`

- **Winner**: Incumbent holds in `caos/frontend/scripts/workbench-smoke.mjs` (`acceptanceRunFixture`).
- **Justification**:
  - The fixture keeps the accepted snapshot-id assignment directly visible beside its phase condition, which is the source-verifiable contract requested for this bounded checkpoint.
  - A readability challenger cached phase booleans, but the focused source test rejected it (16/17 passed); it was restored with `apply_patch` rather than weakening the regression.
  - The six-state list is tiny, so alternate lookup tables or helpers add allocation or indirection without a meaningful runtime gain.
- **Final code**:

```js
const acceptanceRunFixture = () => ({
  ...nextRunState,
  status: acceptanceRunPhase === "accepted" ? "succeeded" : acceptanceRunPhase,
  accepted_snapshot_id: acceptanceRunPhase === "accepted" ? acceptanceSnapshot.id : null,
  error: acceptanceRunPhase === "failed"
    ? { code: "GEOMETRY_FAILURE", message: "Controlled fixture failure." }
    : acceptanceRunPhase === "paused"
      ? { code: "SOURCE_SET_EMPTY", message: "Controlled fixture pause." }
      : null,
  nodes: nextRunState.nodes.map((node, index) => ({
    ...node,
    status: acceptanceRunPhase === "succeeded" || acceptanceRunPhase === "accepted" ? "succeeded"
      : acceptanceRunPhase === "failed" ? index === 0 ? "failed" : "pending"
      : acceptanceRunPhase === "running" ? index === 0 ? "succeeded" : index === 1 ? "running" : "pending"
        : "pending",
    artifact_id: acceptanceRunPhase === "succeeded" || acceptanceRunPhase === "accepted" ? node.artifact_id : index === 0 && acceptanceRunPhase === "running" ? node.artifact_id : null,
  })),
});
```

- **Verification**: the readability challenger failed the exact accepted-id source contract at 16/17; restoring the incumbent returned the focused result to 17/17. The only runtime caller is the scoped run-route fulfiller, and the subsequent TypeScript/build checks stayed green.

### Confidence review — authority correction

Least confident about (ranked):

1. A pinned visible snapshot could still be mistaken for the acceptance predecessor.
   investigated → traced `/api/cases/{case_id}/snapshot`, runtime acceptance, `SnapshotView`, every `accepted`/`latest_accepted` caller, and the dialog/aftermath wiring. The server advances `accepted_snapshot_id`; the API exposes that record as `latest_accepted` while `accepted` resolves `visible_snapshot_id` first.
   verdict     → CONFIRMED bug in the reviewed Task 3 implementation.
   patch       → replacement slots/digest and accepted-run matching now use `latest_accepted`; visible-lens labels and switch-required disclosure remain separate.
2. A latest-accepted run might still expose the irreversible action when the visible lens trails it.
   investigated → constructed `snap_visible`/`snap_latest` divergence in the focused test, verified the match against latest succeeds and the match against visible fails, and pinned the accepted branch to contain neither the Ready label nor the action.
   verdict     → fine after correction (focused regression plus accepted-first branch inspection).
   patch       → accepted identity now receives latest, visible, and switch-required inputs independently.
3. The smoke fixture might claim accepted coverage without serving matching authority.
   investigated → the accepted phase now sets `run.accepted_snapshot_id` to `acceptanceSnapshot.id` and serves that same object as both visible and latest snapshot authority; failed and paused phases carry controlled error codes that select their real UI branches.
   verdict     → fine (source-verifiable fixture contract).
   patch       → added the scoped snapshot route and all six phases.
4. The correction could have altered acceptance transport or weakened server revalidation.
   investigated → zero changed server paths; the staged Workspace diff contains no request change; the accept call remains `POST` with no body. Runtime still verifies the pinned source set, artifact ownership/digests, and QA before advancing the accepted pointer. Five focused server regressions passed.
   verdict     → fine.
   patch       → n/a.
5. The larger accepted disclosure could break the exact browser geometry invariant.
   investigated → the existing acceptance panel retains its 132px reserved block size and shared approval grammar; the fixture now asserts all six boxes, but the combined browser environment was intentionally not started in this checkpoint.
   verdict     → open.
   patch       → n/a; Task 6 must run the full workbench smoke.

Fixed: latest-versus-visible authority conflation; incomplete smoke state coverage.

Verified fine: Reader fail-closed gating; bodyless acceptance request; server digest/source/QA revalidation; explicit-only visible switch; export-polling checkpoint isolation.

By-design: `accepted` remains the server wire name for the visible lens; semantic comments and UI labels prevent treating it as the acceptance ledger.

Still open: real-browser six-state geometry in the final assembled environment, owned by Task 6.

### Impeccable correction audit

The correction reuses `.approval-panel`, `.state-facts`, `.status`, native dialog behavior, existing tokens, and the current focus contract. It adds no CSS, color, motion, card, gradient, or decorative vocabulary. Visible/latest authority is now stated in plain text rather than communicated by color alone. No new accessibility, responsive, theming, or anti-pattern finding was introduced.

## Final review correction — terminal run progress

### Summary

- `RunStatus` now selects a running or pending current module only while the run itself is queued or running.
- Failed and paused runs retain their served pending nodes for DAG inspection, but the progress heading now says `Execution stopped` or `Execution paused`, and `aria-valuetext` no longer appends a contradictory pending-module suffix.
- The change does not alter run polling, acceptance state, requests, server code, or the existing progress announcer.

### TDD and verification

- TDD red: `node --test src/lib/workbench.test.ts` — 17/18 passed; the new terminal-progress contract failed against the unconditional pending-node selection.
- Focused green: `node --test src/lib/workbench.test.ts` — 18/18 passed; existing `MODULE_TYPELESS_PACKAGE_JSON` warning only.
- Full frontend unit suite: `npm run test:unit` — 101/101 passed; existing module-type warnings only.
- Strict lint: `npm run lint` — passed.
- Local TypeScript: `./node_modules/.bin/tsc --noEmit -p .` — passed.
- `git diff --check` and explicit staged-path/trailer checks — passed.

### Rewrite tournament

Skipped under the skill's trivial-edit rule: the production change is a three-line status guard with no new loop, parser, signature, side effect, or abstraction. The existing `RunStatus` tournament and its state-ordering rationale remain applicable.

### Confidence review — terminal progress

Least confident about (ranked):

1. The gate might omit a real non-terminal server status.
   investigated → traced the server `RunStatus` enum: queued, running, paused, succeeded, and failed are the complete set. Only queued and running can truthfully name a current module.
   verdict     → fine (server contract trace plus TypeScript/build checks).
   patch       → n/a.
2. The visible heading could be corrected while assistive text remained contradictory.
   investigated → both `progressLabel` and the progressbar's `aria-valuetext` derive their optional module detail from the same gated `current` value; the focused regression pins both consumers.
   verdict     → fine after correction.
   patch       → gated `current` before either consumer.
3. Removing terminal current-node selection could hide useful failure detail.
   investigated → terminal node statuses and links remain visible in the DAG, while failed/paused error details remain in their existing `StateNote` and acceptance-remedy regions. Only the false “current pending module” claim is removed.
   verdict     → by-design.
   patch       → n/a.
4. The change could interfere with progress announcements during live execution.
   investigated → queued/running selection is unchanged, and `RunProgressAnnouncer` independently announces only an actually running node. Full frontend units, lint, and TypeScript passed.
   verdict     → fine.
   patch       → n/a.

Fixed: terminal progress and accessibility text contradicting failed/paused state.

Verified fine: live queued/running progress; terminal DAG/error detail; acceptance behavior; polling and request contracts.

By-design: terminal runs may retain pending nodes in the immutable route, but none is presented as currently executing.

Still open: only the previously documented full combined-app browser run, owned by Task 6.
