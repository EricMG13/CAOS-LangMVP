# Task 1 report — truthful green development baseline

Base: `ba97a89899440532686b08050127d48db9a509b9`

Planning checkpoint preserved: `7c306d2`

Branch: `codex/enterprise-readiness`

## Preserved failing baseline

`/private/tmp/caos-enterprise-baseline-20260901/bin/python run_sec_audit.py`

- Exit 1: `{'audited_routes': 50, 'case_boundary_routes': 42, 'failures': 10}`.
- Body-probe drift named rebase preview, one-way sensitivity, and tornado.
- Each of those routes returned 422 before the foreign-case 404, membership-boundary observation, and stored-reader 403 checks.

`/usr/bin/env python3 docs/quality_ledger_coverage.py`

- Exit 1: `routes checked: 45   product files: 228   features: 120` with 10 failures.
- Eight served model/model-revision routes were absent from the ledger.
- `caos/frontend/scripts/draft-history-smoke.mjs` and `caos/frontend/scripts/identity-a11y.mjs` mapped to no feature.

## Implementation

- Added schema-valid minimal bodies for rebase preview, one-way sensitivity, and tornado without changing authorization expectations or audit discovery.
- Added all eight served routes to existing `F-MODEL-04`, `F-MODEL-05`, `F-MODEL-08`, `F-MODEL-09`, and `F-MODEL-10` rows.
- Mapped draft-history smoke to `F-UI-09`/`F-UI-11` and identity accessibility to `F-UI-14`; no file was excluded.
- Changed nightly Python 3.11 to 3.14. Node remains 24 and the corpus fetch/regression remains hard-fail.
- Refreshed `CLAUDE.md` and `ENTERPRISE_READINESS_PLAN.md` against `ba97a89`: backend `655 passed, 2 skipped, 864 warnings` and corpus `34 passed, 124 warnings` are development evidence only; the red 10+10 baseline and repair are recorded; served builder routes were removed from stale gap claims; Admin Studio remains explicitly unavailable; governed builder/canonical deliverable implementation does not qualify live analysis; all-six-pathway enterprise qualification remains open.
- The legacy builder plan already recorded Tasks 1–7 as implemented at `ba97a89`, so the immutable planning checkpoint's reconciliation was left unchanged.

## Acceptance results

All commands ran from the task worktree unless a working directory is shown.

1. `/private/tmp/caos-enterprise-baseline-20260901/bin/python run_sec_audit.py`
   - Exit 0: `{'audited_routes': 50, 'case_boundary_routes': 42, 'failures': 0}`.
   - One existing `StarletteDeprecationWarning` from `fastapi.testclient`.
2. `/usr/bin/env python3 docs/quality_ledger_coverage.py`
   - Exit 0: `routes checked: 45   product files: 228   features: 120`; every route and product file documented.
3. `/private/tmp/caos-enterprise-baseline-20260901/bin/python -m ruff check --config ruff.toml caos/server caos/tests --exclude caos/server/caos/methodology/vendor`
   - Exit 0: `All checks passed!`
4. `/private/tmp/caos-enterprise-baseline-20260901/bin/python -m pytest caos/tests/spec/test_model_builder_spec.py caos/tests/spec/test_observability_spec.py -q`
   - Exit 0: `119 passed, 1 warning in 104.45s`; no skips.
5. `cd caos/frontend && npm run test:unit`
   - Exit 0: `113 passed, 0 failed, 0 skipped`; existing module-type warnings only.
6. `/private/tmp/caos-enterprise-baseline-20260901/bin/python -c 'import yaml; data=yaml.safe_load(open(".github/workflows/nightly.yml")); assert data["jobs"]["regression"]["steps"][1]["with"]["python-version"] == "3.14"; assert data["jobs"]["regression"]["steps"][2]["with"]["node-version"] == 24'`
   - Exit 0; workflow YAML loaded and runtime assertions passed.
7. `git diff --check`
   - Exit 0.

No test, route-discovery, file-discovery, probe-drift, skip, or authorization assertion was weakened.

## Post-edit review

`rewrite-tournament` was evaluated in no-argument post-edit mode and skipped: the executable edits are static probe/mapping data with no changed function, branch, loop, parser, or algorithm.

### Confidence review — Task 1 diff

Least confident about (ranked):

1. Probe bodies might validate without reaching the intended authorization seams.
   - Investigated: compared each body to its strict request model and ran the real security audit.
   - Verdict: fine; all 42 case-boundary routes reached the expected 404/403 checks and the audit reported zero failures.
2. Ledger additions might hide drift through an exclusion or duplicate feature.
   - Investigated: inspected the diff and ran automatic route/file discovery.
   - Verdict: fine; no exclusion changed, no feature row was added, and all 45 routes/228 product files map across the existing 120 features.
3. Runtime alignment might weaken the nightly corpus gate or change Node.
   - Investigated: inspected the complete workflow diff and loaded the YAML.
   - Verdict: fine; only Python 3.11→3.14 changed, Node remains 24, and fetch/regression hard-fail steps are intact.
4. Documentation might overstate qualification or retain stale route gaps.
   - Investigated: reconciled the route declarations and `ba97a89` evidence named in the execution brief/plan.
   - Verdict: fine; development evidence is explicitly non-qualifying, served routes are no longer called unavailable, and Admin Studio/all-six qualification remain open.

Fixed: the 10 security-audit and 10 ledger failures; stale runtime/documentation claims.

Verified fine: authorization boundaries, automatic discovery, nightly hard-fail behavior, focused backend/frontend acceptance.

By design: existing deprecation/module-type warnings remain recorded and are not suppressed.

Still open: candidate qualification and warning cleanup belong to later execution-plan tasks.
