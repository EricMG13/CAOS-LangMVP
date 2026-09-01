# Task 1 brief — truthful green development baseline

## Context

- Worktree: `/Users/ericguei/Claude/Projects/CAOS-LangMVP/.claude/worktrees/enterprise-readiness`
- Branch: `codex/enterprise-readiness`
- Plan: `docs/superpowers/plans/2026-09-01-enterprise-testing-readiness-execution.md`, Task 1
- Base: `ba97a89`; planning checkpoint: `7c306d2`
- Use `/private/tmp/caos-enterprise-baseline-20260901/bin/python` for Python commands.
- Read relevant `AGENTS.md` before editing. The frontend has a Next.js-specific `AGENTS.md`; Task 1 should not require frontend component code.
- Preserve the user-upload-only six-pathway enterprise target. Do not narrow requirements to the current four-pathway cut.

## Owned files

- `run_sec_audit.py`
- `docs/QUALITY_LEDGER.csv`
- `docs/quality_ledger_coverage.py`
- `.github/workflows/nightly.yml`
- `CLAUDE.md`
- `ENTERPRISE_READINESS_PLAN.md`
- `docs/superpowers/plans/2026-08-31-legacy-builder-core-adaptation.md` only if additional reconciliation is still needed
- Targeted tests only when necessary to prove the changes
- `.superpowers/sdd/task-1-report.md`
- `.superpowers/sdd/progress.md`

Do not edit engine, model, deliverable, storage, or frontend component implementation in this task.

## Failing baseline to preserve in the report

`run_sec_audit.py` reports 10 failures:

- body-probe drift for rebase preview, one-way sensitivity, and tornado;
- each route returns 422 before foreign-case 404 and reader-write 403 checks.

`docs/quality_ledger_coverage.py` reports 10 failures:

- eight served model/model-revision routes absent from the ledger;
- `draft-history-smoke.mjs` and `identity-a11y.mjs` map to no feature.

## Required implementation

1. Add valid minimal request bodies to the existing security audit probe map for:
   - `POST /api/cases/{case_id}/model-revisions/rebase-preview`
   - `POST /api/cases/{case_id}/models/sensitivities/one-way`
   - `POST /api/cases/{case_id}/models/tornado`
   The audit must reach authorization/membership boundaries; do not weaken expected 404/403 behavior.
2. Add the eight served routes to appropriate existing `F-MODEL-*` ledger rows. Do not add fake duplicate features.
3. Map both new frontend scripts in `FILE_MAP` to existing UI/operations feature IDs. Do not exclude them.
4. Change nightly Python from 3.11 to 3.14; retain Node 24 and the full corpus hard-fail behavior.
5. Refresh documentation against `ba97a89`:
   - record backend `655 passed, 2 skipped, 864 warnings` and corpus `34 passed, 124 warnings` as development evidence only;
   - record security/ledger red baseline and their Task 1 repair;
   - state the builder/canonical deliverable implementation exists but does not qualify live analysis;
   - remove stale claims that worksheet, one-way/tornado/rebase, and build/revision export routes are unserved after verifying actual routes;
   - keep Admin Studio as an explicit unavailable capability and all-six-pathway enterprise qualification open.
6. Update `.superpowers/sdd/progress.md` and write `.superpowers/sdd/task-1-report.md` with commands and exact results.

## Acceptance

Run from the worktree:

```bash
/private/tmp/caos-enterprise-baseline-20260901/bin/python run_sec_audit.py
/usr/bin/env python3 docs/quality_ledger_coverage.py
/private/tmp/caos-enterprise-baseline-20260901/bin/python -m ruff check --config ruff.toml caos/server caos/tests --exclude caos/server/caos/methodology/vendor
/private/tmp/caos-enterprise-baseline-20260901/bin/python -m pytest caos/tests/spec/test_model_builder_spec.py caos/tests/spec/test_observability_spec.py -q
cd caos/frontend && npm run test:unit
```

Expected: both formerly red gates pass with zero failures; targeted tests and unit tests pass; no new skip or weakened discovery/probe assertions.

Commit the completed task with a focused message. Do not amend the planning checkpoint.
