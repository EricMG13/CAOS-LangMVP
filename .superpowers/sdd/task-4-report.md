# Task 4 report — Humanize status and identity without hiding exact authority

## Summary

- Snapshot diffs now match the served `{module_id, digest}` entry contract; Command Center no longer models or renders nonexistent `before`/`after` fields.
- A shared, tested `compactIdentity` policy presents long workspace identities as `leading…trailing`. The `IdentityValue` presenter preserves the exact value in `title`, hides the visual duplicate from assistive technology, and supplies one semantic text node containing the spoken abbreviation and full value. Human fallback copy is never passed through the formatter.
- Compact presentation is used on visible shell, Sources, Deep Dive, Command Center, Model Builder, and evidence-drawer authority values. Requests, comparisons, download URLs, persistence data, logs, and governed paper output remain exact and unchanged.
- The governed paper retains its full digest and now wraps it more safely. Evidence drawers use the source filename as the heading and list the source ID among the facts.
- Visible server codes use the existing `humanizeCode` helper or existing pathway labels. Canonical codes used as data, comparisons, and request values are unchanged.
- Command Center conclusion selection is pure and deterministic: substantive `CP-2`, then the first substantive artifact other than `CP-PARSE`/`CP-0`, then substantive `CP-PARSE`; `CP-0` is never presented as a conclusion fallback.
- `.dev-data/` was neither staged nor modified.

## Files committed

- `caos/frontend/app/globals.css`
- `caos/frontend/src/components/WorkbenchShell.tsx`
- `caos/frontend/src/components/Workspace.tsx`
- `caos/frontend/src/components/model/ModelBuilder.tsx`
- `caos/frontend/src/components/report/ReportStudio.test.ts`
- `caos/frontend/src/components/report/ReportStudio.tsx`
- `caos/frontend/src/components/states.tsx`
- `caos/frontend/src/lib/workbench.test.ts`
- `caos/frontend/src/lib/workbench.ts`

## Tests and verification

- TDD red: the first focused run produced the four intended failures for the absent compact helper/presenter, invalid snapshot-diff rendering, and conclusion selector. A later ordering fixture correctly failed when `CP-0` preceded `CP-PARSE`, and a presentation assertion correctly failed while fallback prose still flowed through the identity presenter.
- Focused green: `node --test src/lib/workbench.test.ts src/components/report/ReportStudio.test.ts` — 38/38 passed.
- Final identity/model focus: `node --test src/lib/workbench.test.ts src/components/model/ModelBuilder.test.ts` — 37/37 passed.
- Full frontend unit suite: `npm run test:unit` — 105/105 passed; existing `MODULE_TYPELESS_PACKAGE_JSON` warnings only.
- Lint: `npm run lint` — passed.
- Local TypeScript: `npx tsc --noEmit` — passed.
- Production build: `npm run build` — passed with Next.js 16.3.3; all 12 static pages generated.
- Focused server response contracts: `caos/server/.venv/bin/python -m pytest caos/tests/spec/test_http_contracts_spec.py::test_snapshot_diff_entries_are_module_id_and_digest_only caos/tests/spec/test_http_contracts_spec.py::test_snapshot_diff_entries_reject_artifact_and_snapshot_ids -q` — 2/2 passed.
- `git diff --check` and staged-diff checks — passed.
- A self-building bounded Chromium check verifies the actual accessibility snapshot for long and short identities, exact pointer `title`, visible abbreviation, semantic hidden text, single announcement, and absence of new tab stops. Source checks retain caller-scope, governed-paper, and ad hoc-slice guards. Full assembled browser coverage remains assigned to Task 6.

## Rewrite tournament

- **Winner**: Incumbent holds in `caos/frontend/src/lib/workbench.ts`, `selectConclusionArtifact` (lines 151–156).
- **Justification**:
  - The three clauses expose the required priority—`CP-2`, conclusion-bearing modules, then preparation—directly and preserve first-match ordering.
  - The implementation is allocation-free and operates on a bounded accepted-artifact list; a one-pass challenger saved at most two scans while adding mutable candidate state.
  - The generic signature, object identity, purity, and sole Command Center caller remain unchanged and TypeScript-verified.
- **Final code**:

```ts
export function selectConclusionArtifact<T extends ConclusionArtifact>(artifacts: readonly T[]): T | null {
  const substantive = (artifact: T) => Boolean(artifact.payload?.narrative?.takeaway?.trim() || artifact.payload?.summary?.trim() || artifact.markdown?.trim());
  return artifacts.find((artifact) => artifact.module_id === "CP-2" && substantive(artifact))
    ?? artifacts.find((artifact) => artifact.module_id !== "CP-PARSE" && artifact.module_id !== "CP-0" && substantive(artifact))
    ?? artifacts.find((artifact) => artifact.module_id === "CP-PARSE" && substantive(artifact))
    ?? null;
}
```

- **Verification**: `node --test src/lib/workbench.test.ts && npx tsc --noEmit` — 22/22 passed and TypeScript passed. Repository-wide reference search found one production caller in `CommandView` plus focused tests; the caller contract is unchanged.

`compactIdentity` and `IdentityValue` were reviewed but skipped as additional tournament targets because each is below the skill's non-trivial-function materiality threshold.

## Confidence review

Least confident about (ranked):

1. Long non-identity fallback copy could be abbreviated like a digest.
   investigated → the initial shell and Model Builder integration passed `Authority unavailable`, `Recalculation required`, and `Application version` through `IdentityValue`.
   verdict     → CONFIRMED bug.
   patch       → callers now branch between a real ID and plain fallback copy; a source regression rejects long fallback prose inside `IdentityValue`.
2. Preparation fallback could depend on array order and select `CP-0`.
   investigated → the initial final `find(substantive)` selected readiness when `CP-0` preceded `CP-PARSE`.
   verdict     → CONFIRMED bug.
   patch       → the last clause now selects only substantive `CP-PARSE`; the reversed-order fixture is green.
3. The client diff shape could still diverge from the wire response.
   investigated → `responses.py` requires `module_id`/`digest`, `_snapshot_diff` emits exactly those fields, the shared client type matches, and Command Center renders `item.digest` only.
   verdict     → fine (2/2 focused server contracts plus focused source regression).
   patch       → n/a.
4. Compact presentation could leak into governed or machine-consumed values.
   investigated → all helper references are JSX presentation sites; request bodies, equality checks, downloads, persistence, logs, and `DeliverableDocument` keep the original values. The paper digest remains full and wraps through CSS.
   verdict     → fine.
   patch       → n/a.
5. Exact identities might become inaccessible after visual compaction.
   investigated → Chromium ignored `aria-label` on the original generic span and exposed only the compact visible text; `title` was not a reliable assistive path.
   verdict     → CONFIRMED bug during review.
   patch       → the visible abbreviation is now `aria-hidden`, while one visually hidden text node carries the short value once or the long abbreviation plus full exact value. A real Chromium accessibility snapshot pins both cases.

Fixed: readiness outranking preparation fallback; human fallback prose being compacted; exact identities missing from Chromium's accessibility tree.

Verified fine: server/client diff fidelity; exact request/download/persistence values; full governed-paper digest; short and threshold identity behavior; drawer heading/facts structure; scoped status humanization; one accessible announcement with no added tab stop.

Still open: the full assembled browser journey is intentionally deferred to Task 6.

## Review correction — Chromium accessibility tree

### Correction files

- `caos/frontend/package.json`
- `caos/frontend/scripts/identity-a11y.mjs`
- `caos/frontend/src/components/states.tsx`
- `caos/frontend/src/lib/workbench.test.ts`

### TDD and verification

- TDD red: `npm run test:identity-a11y` exercised the built application and timed out looking for semantic hidden identity text because the generic `aria-label` span rendered no such structure.
- Focused green: `node --test src/lib/workbench.test.ts` — 22/22 passed.
- Chromium accessibility tree: `npm run test:identity-a11y` — passed after rebuilding all 12 static pages; both long and short identities were exposed exactly once, exact `title` values were preserved, and neither identity created a tab stop.
- Full frontend units: `npm run test:unit` — 105/105 passed; existing `MODULE_TYPELESS_PACKAGE_JSON` warnings only.
- Lint: `npm run lint` — passed.
- Local TypeScript: `npx tsc --noEmit` — passed.
- Production build: passed both directly and as the first step of the self-building Chromium probe.
- `git diff --check` and staged-diff checks — passed.

The production correction is below the rewrite-tournament materiality threshold, and the remaining change is test-only, so the tournament was skipped.

## Commit

- Task 4 implementation: `9104e51ff99b9081ea9f4aa4c9ed971c333ab6bd` (`feat(frontend): clarify visible identities`)
- Task 4 accessibility correction: `d88b8f4cab0deb1b462520553beb9b9adc29c689` (`fix(frontend): expose exact identity to assistive tech`)

## Remaining risks

- Task 6 should still run the complete assembled combined-app journey at target viewports; Task 4's focused Chromium accessibility snapshot is green.
- Node's existing `MODULE_TYPELESS_PACKAGE_JSON` warning remains; it is unrelated to Task 4 behavior.
- `.dev-data/` remains untracked runtime/user state and was intentionally untouched.
