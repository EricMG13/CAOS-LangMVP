# Task 2 brief — user-upload-only methodology

## Context

- Worktree: `/Users/ericguei/Claude/Projects/CAOS-LangMVP/.claude/worktrees/enterprise-readiness`
- Branch: `codex/enterprise-readiness`
- Plan: `docs/superpowers/plans/2026-09-01-enterprise-testing-readiness-execution.md`, Task 2
- Task 1 checkpoint: `1993172`
- The application has no executable external filing-fetch runtime. Four CP-4 vendored methodology files instructed an agent to search, fetch, and vault external filings. Re-review also found a contradictory CP-1C public-web peer-discovery lane in shared canon and the deployed CP-1C authority. Those instructions conflict with the required real-user journey: source bytes enter only through user upload.
- The distributed bundle explicitly says its original `build/build_package.py` is not shipped. Therefore the plan's phrase "existing regeneration command" is inaccurate. Do not hand-maintain integrity hashes. Add one minimal deterministic stdlib regeneration command only if no existing checked-in command can be recovered.

## Owned files

- `caos/server/caos/methodology/vendor/deploy_v/skills/cp-4-legal-covenant-interpreter/SKILL.md`
- `caos/server/caos/methodology/vendor/deploy_v/skills/cp-4-legal-covenant-interpreter/references/CP-4_RUNBOOK.md`
- `caos/server/caos/methodology/vendor/deploy_v/skills/cp-4-legal-covenant-interpreter/references/REF_CP-4B_STEPS.md`
- `caos/server/caos/methodology/vendor/deploy_v/skills/cp-4-legal-covenant-interpreter/references/REF_CP-4_STEPS.md`
- `caos/server/caos/methodology/vendor/deploy_v/CANON_SHARED.md`
- CP-1C peer-benchmark authority files required to remove public-web discovery while preserving supplied-evidence analysis:
  - `caos/server/caos/methodology/vendor/deploy_v/skills/cp-1c-peer-benchmark/SKILL.md`
  - `caos/server/caos/methodology/vendor/deploy_v/skills/cp-1c-peer-benchmark/references/REF_CP-1C_STEPS.md`
  - `caos/server/caos/methodology/vendor/deploy_v/skills/cp-1c-peer-benchmark/references/CP-1C_SCHEMA_REFERENCE.md`
  - `caos/server/caos/methodology/vendor/deploy_v/skills/cp-1c-peer-benchmark/references/CP-1C_SYSTEM_REFERENCE.md`
  - CP-1C script comments that cite the removed shared exception; no executable peer-statistics behavior changes
- Generated bundle integrity/manifest/index/baseline files required by the actual bundle invariants
- `caos/scripts/regenerate_deploy_v_integrity.py` only if the repository truly has no usable regeneration command
- `caos/tests/test_bundle.py`
- `caos/tests/spec/test_modules_spec.py`
- `caos/server/caos/modules/registry.py` only to update CP-1C's strict assembled-authority digest after the deployed authority changes
- The smallest prohibition test beside `caos/tests/test_bundle.py`
- `docs/superpowers/plans/2026-09-01-enterprise-testing-readiness-execution.md` only to correct the nonexistent-generator instruction
- `.superpowers/sdd/enterprise-task-2-report.md`
- `.superpowers/sdd/progress.md`

Do not edit runtime ingestion, engine, API, provider, frontend, model, or deliverable implementation in this task. Preserve every CP-4 analytical/legal rule unrelated to external acquisition.

## Required implementation

1. Add a failing tracked-source prohibition test before the fix. It must scan deployed methodology and tracked product code/text for the forbidden acquisition surface, including the provider name currently present, SEC retrieval hosts/endpoints, `EDGAR_USER_AGENT`, `/api/edgar`, nonexistent retrieval modules, and instructions to search/fetch/vault external filings. Exclude only non-product audit/planning records and immutable ignored issuer PDF bytes; do not broadly exclude vendored methodology.
2. Delete the complete CP-4 external acquisition reference section and all references to it from the four deployed files. Remove the shared-canon and CP-1C public-web peer-discovery exception comprehensively. CP-1C may use analyst-uploaded candidate lists and peers disclosed in supplied evidence only; absent or insufficient peer evidence produces a typed gap and limited or blocked result. Never suggest web search, retrieval, fetching, vaulting, or substitution with an external snippet.
3. Preserve the supplied-document authority hierarchy and legal gate semantics. A user-uploaded executed agreement/indenture remains primary; a missing governing document cannot be treated as passed.
4. Regenerate bundle integrity deterministically. First prove the original generator is absent. If absent, add the smallest stdlib script that derives all affected integrity metadata/build identifiers from the exact tree, runs from repository root, is idempotent, and supports a non-mutating `--check` mode. Reuse the bundle's existing canonicalization and field semantics; no new package/dependency.
5. Update the independent approved-release digest/count assertion only from the regenerated exact tree. Do not weaken or remove the independent pin.
6. Correct the Task 2 plan wording if a small replacement generator had to be added. Write the Task 2 report with the red prohibition baseline, exact changed surface, regeneration outputs, and acceptance results. Keep progress `implemented; awaiting review`.

## Acceptance

Run from the worktree:

```bash
/private/tmp/caos-enterprise-baseline-20260901/bin/python -m pytest caos/tests/test_bundle.py caos/tests/spec/test_modules_spec.py -q
/private/tmp/caos-enterprise-baseline-20260901/bin/python caos/scripts/regenerate_deploy_v_integrity.py --check  # only if added
/usr/bin/env python3 "Modular OS/tools/check_module_consistency.py"
/private/tmp/caos-enterprise-baseline-20260901/bin/python -m ruff check --config ruff.toml caos/server caos/tests --exclude caos/server/caos/methodology/vendor
/usr/bin/env python3 docs/quality_ledger_coverage.py
git diff --check
```

Also run a repository search matching the prohibition test, including a direct deployed-CP-1C authority assertion. Expected: zero forbidden acquisition references in product/runtime/methodology/test-fixture surfaces; no CP-1C discovery/scraping lane; bundle verification and independent byte pin both pass; 26 modules report zero drift; no integrity file changes on a second regeneration.

If a non-trivial regeneration function/module is added, run `rewrite-tournament` in no-argument post-edit mode before commit. In all cases run `confidence-review` against the actual Task 2 diff. Commit the completed task with a focused message; do not amend prior checkpoints.
