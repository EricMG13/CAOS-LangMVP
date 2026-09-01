# Task 4 report — Humanize status and identity without hiding exact authority

## Summary

- Snapshot diffs now match the served `{module_id, digest}` entry contract; Command Center no longer models or renders nonexistent `before`/`after` fields.
- A shared, tested `compactIdentity` policy presents long workspace identities as `leading…trailing`. The `IdentityValue` presenter preserves the exact value in `title` and announces both the abbreviation and full value through its accessible label. Human fallback copy is never passed through the formatter.
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
- Bounded accessibility/source checks verify the abbreviated spoken label, exact `title`, every required presentation caller, the unchanged full governed-paper identity, and the absence of an ad hoc workspace `slice(0, 12)` identity policy. Full live browser coverage remains assigned to Task 6.

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
   investigated → long values retain their exact `title`, and the accessible label includes the abbreviation followed by the full identity; short values remain unchanged.
   verdict     → fine in static/source checks and production compilation.
   patch       → n/a.

Fixed: readiness outranking preparation fallback; human fallback prose being compacted.

Verified fine: server/client diff fidelity; exact request/download/persistence values; full governed-paper digest; short and threshold identity behavior; drawer heading/facts structure; scoped status humanization.

Still open: the full live screen-reader/browser journey is intentionally deferred to Task 6.

## Commit

- Task 4 implementation: `9104e51ff99b9081ea9f4aa4c9ed971c333ab6bd` (`feat(frontend): clarify visible identities`)

## Remaining risks

- Task 6 should run the assembled combined-app browser journey and perform the live screen-reader spot-check at target viewports.
- Node's existing `MODULE_TYPELESS_PACKAGE_JSON` warning remains; it is unrelated to Task 4 behavior.
- `.dev-data/` remains untracked runtime/user state and was intentionally untouched.
