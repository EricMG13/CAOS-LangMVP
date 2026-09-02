# Enterprise Task 6 report — semantic execution and the Distressed pathway, landed

Executed as `ER-G1` (2026-09-02) from the adversarial review in
`enterprise-task-6-adversarial-review.md` and the decisions D1–D9 recorded at
its end. Local interpreter: Python 3.14.6 (decision D3; the venv was rebuilt
with `uv run --python 3.14 --project caos/server --extra dev`).

## Delivered

- **D1 screen depth.** Every module is provider-backed at both depths
  (`modules/registry.py`); `ENTERPRISE_TESTING_READINESS.md` RUN-030,
  `ENTERPRISE_READINESS_PLAN.md` scope decision 4, `CLAUDE.md`,
  `MODULE_GRANULARITY.md`, `SPEC_RECONCILIATION.md` and `docs/DECISIONS.md`
  §14.12 now say the same thing: screen determinism is identical host-validated
  identity for identical pins and build.
- **D2 / D7 bundle.** Deploy V build `237bf4bc…` is recorded in `docs/DECISIONS.md`
  §14.13 (files, route changes per cell, why the seam could not carry them, the
  moved pin, the regenerated authority digests, the 310-check image gate). The
  bond-analytics bound is now host-owned in
  `methodology/execution.py::_enforce_work_factor` (`MAX_BOND_YEARS`,
  `MAX_CALL_SCHEDULE_ITEMS`), refusing as `METHODOLOGY_INPUT_INVALID` before the
  vendor guard runs. Every compiled route cell is pinned by digest
  (`caos/tests/test_bundle.py::ROUTE_GOLDENS`).
- **D6 calculation completeness (review F2/F3).** `engine/runtime.py` answers an
  incomplete calculator with a typed tool result
  (`METHODOLOGY_CALCULATION_INCOMPLETE`), allows one retry that spends the
  module's shared repair allowance (`engine/loop.py` `repair_state`), ends the
  run only for the core calculators (CP-1/CP-2G `credit_metrics`; CP-4C
  `funding_gap`/`recovery_waterfall` in a Distressed run), and otherwise
  completes the module with host-declared `calculation_limitations` and
  `host:calculation_incomplete:<id>` in the handoff limitation flags
  (`storage/runs.py` validates the new field; provenance lists it as
  host-derived). `SOURCE_EVIDENCE_INSUFFICIENT` is once again only the
  provider-declared source gate's code. Recorded as §14.14.
- **D8 development provider (review F6).** `engine/host_control.py` binds an
  answer-keyed provider under `CAOS_PROVIDER=host_control` (`config.py`,
  `run.py`), refused in production; the CI browser job binds it so the keyless
  workbench smoke and accessibility sweep can drive ordinary runs.
- **D9 authority locking (review F21/F22/F23/F27).** Transient model reads no
  longer take the process-wide lock; `Engine.accept` waits for it in a worker
  thread; build completion and every model export publish through a
  compare-and-swap that requires each pinned source to be live in the same
  statement (`storage/models.py` `expected_live_source_ids`), yielding
  `MODEL_AUTHORITY_CHANGED` / `MODEL_EXPORT_AUTHORITY_CHANGED` rather than a READY
  file; `queue_export` validates the build first; Distressed resolution runs
  under one aggregate deadline with a per-request memo of validated snapshot
  artifacts; intermediate ancestry snapshots are validated by identity only.
  Recorded as §14.15.
- **Review findings closed in code:** F1/F2 (no ordinary route completed), F7
  (`test_finalization_metering.py` migrated to the new `ScriptedProvider`; its
  §12.14 bracket check reads the bracket, not the line shape), F8 (artifact-read
  refusals logged), F9 (a header-only model-facing table is a declared absence,
  so an unsegmented issuer builds a model again), F11/F19 (`MODULES.get`,
  `KeyError` → 404), F20 (the replay test compares every payload key except the
  run-identity chain), F24 (the overlay recomputation test forges the real
  value and asserts the CP-4C replay refusal), F25 (the revision store
  validates before it writes; the regression test seeds a service-shaped
  record), F28 (a replaced artifact relinks its succeeded node).
- **Test doubles.** `caos/tests/calculator_fixtures.py` carries the answer-keyed
  calculator inputs; the injection, observability, corpus and wiring doubles
  feed them, so every attacked step is reached again.

## Assumptions stated

- D6 as recorded says the host "sets the source gate" for a non-core
  limitation. Implemented as: the host does not touch the provider-declared
  gate (so §14.10 keeps its exact scope) and records the limitation on the
  artifact instead. Touching the gate would have re-created review finding F3
  (Full Credit dying on peerless packs as `SOURCE_EVIDENCE_RESTRICTED`).
- D9's "source projection without `blocks`" is delivered as a per-request memo
  (one validation per snapshot per resolution) rather than a schema change:
  `source_authority` needs the blocks digest, and a persisted `blocks_digest`
  column is a migration this task did not take on. Recorded as a follow-up.
- Intermediate commits were built as self-consistent file groups and the
  final commit carries the quoted gates; each intermediate commit was not
  individually re-run through the whole suite.

## Commands and results


Working directory `.claude/worktrees/enterprise-readiness`; interpreter `caos/server/.venv/bin/python` (3.14.6).

```text
uv run --python 3.14 --project caos/server --extra dev python -m pytest --version
  → Creating virtual environment at: caos/server/.venv … pytest 9.1.1 (Python 3.14.6)

python -m pytest caos/tests -q -p no:cacheprovider
  → 945 passed, 2 skipped, 1 warning in 814.13s (0:13:34)     (before this task: 16 failed, 900 passed, 1 collection error)
python -m ruff check --config ruff.toml caos/server caos/tests --exclude caos/server/caos/methodology/vendor
  → All checks passed!
python run_sec_audit.py
  → {'audited_routes': 50, 'case_boundary_routes': 42, 'failures': 0}
python docs/quality_ledger_coverage.py
  → routes checked: 45   product files: 232   features: 120 / the ledger documents every route and every product file
CORPUS_FULL=1 python -m pytest caos/tests/test_corpus_pathways.py -q -p no:cacheprovider
  → 34 passed, 1 warning in 165.92s   (every executable route at both depths through the ordinary start_run path; Distressed included)
python caos/scripts/regenerate_deploy_v_integrity.py --check
  → Deploy V integrity is current

cd caos/frontend && npm run lint → exit 0;  npx tsc --noEmit → exit 0;  npm run test:unit → ℹ pass 116 / fail 0;  npm run build → exit 0
```

Red-first evidence for the behaviours this task added (each test was run and failed before the implementation):
`test_runtime_calculations.py::test_incomplete_non_core_calculation_completes_the_module_as_a_declared_limitation`,
`::test_incomplete_calculation_may_be_retried_once_as_the_module_repair`,
`::test_incomplete_core_calculation_ends_the_run_as_a_model_failure_not_evidence_insufficiency`,
`test_runs_spec.py::test_replacing_an_invalid_artifact_relinks_the_succeeded_node`,
`::test_acceptance_waits_for_the_authority_lock_without_stalling_the_event_loop`,
`test_distressed_model_overlay.py::test_intermediate_snapshot_withdrawal_does_not_revoke_an_intact_full_credit_base`,
`test_model_builder_spec.py::test_revision_export_refuses_to_publish_after_a_withdrawal_between_validation_and_publish`,
`::test_build_does_not_complete_ready_after_a_withdrawal_between_resolution_and_commit`,
`test_methodology_execution.py::test_bond_work_factor_is_bounded_by_the_host_before_vendor_code_runs` → `10 failed, 9 passed` on the first run, all green after.
The host-control provider's tests (`test_host_control_provider.py`) were written together with the module; their red state was the missing module, not a failing assertion.

## After the rebase onto `origin/main` (43 commits ahead, 0 behind)

The rebase stopped only on `run_sec_audit.py`, `CLAUDE.md` and `docs/QUALITY_LEDGER.csv`
(the first replayed commit) and then repeatedly on the ledger CSV, which git
treats as one hunk; every stop was resolved toward the branch's contracts,
because the branch's API is what the audit and the ledger must describe. The
Dockerfile keeps main's newer Python digest and the branch's pango packages;
nightly keeps 3.14; the image gate keeps 310; CI keeps the host-control
binding. Every gate was rerun on the rebased tree:

```text
python -m pytest caos/tests -q -p no:cacheprovider          → 945 passed, 2 skipped, 1 warning in 846.55s (0:14:06)
python -m ruff check … --exclude …/vendor                    → All checks passed!
python run_sec_audit.py                                      → {'audited_routes': 50, 'case_boundary_routes': 42, 'failures': 0}
python docs/quality_ledger_coverage.py                       → routes checked: 45   product files: 242   features: 120 / documents every route and every product file
CORPUS_FULL=1 python -m pytest caos/tests/test_corpus_pathways.py -q → 34 passed, 1 warning in 175.24s (0:02:55)
cd caos/frontend && npm ci && npm run lint && npx tsc --noEmit && npm run test:unit && npm run build → all exit 0; unit: ℹ pass 116 / fail 0
CAOS_DATA_DIR=<scratch> PORT=8765 CAOS_PROVIDER=host_control AGENT_EXECUTION_ENABLED=true ANTHROPIC_API_KEY="" python caos/server/dev.py
  CAOS_URL=http://127.0.0.1:8765 npm run a11y            → exit 0 ({"routes":9,"viewports":6,"combinations":70,…})
  CAOS_URL=http://127.0.0.1:8765 npm run test:workbench  → exit 0 ({"timing":{"domContentLoaded":65.9,"firstContentfulPaint":156},"caseRequests":1})
```

The workbench smoke failed once while the backend suite was saturating the
machine, at `workbench-smoke.mjs:1099` (a focus-restoration wait after the
dirty-draft dialog, an area main's last dozen commits tuned for timing); on a
quiet machine it passes. That flakiness is main's frontend timing, not this
task's change, and is noted for the browser-health loop.

## Confidence review

- `Engine.accept` now waits for the authority lock in a worker thread; the
  route is `async def accept_run` and awaits it, and the model service uses no
  event-loop API, so nothing in the accept path needs the loop thread.
- `storage/models.py` imports the `sources` table from `storage/store.py`; the
  store module does not import the model store, so no cycle.
- The resolution memo is a `ContextVar` scoped to one `_resolve_snapshot` call
  (nested resolutions share it); `sign_off` still resolves three times, so the
  cost drops from 4–12 validations per snapshot to one per resolution, not to
  one per request. Recorded as a follow-up in the plan delta for Task 9.
- The CI browser job runs `run.py` on Python 3.12 with the host-control
  binding; nothing this task added uses 3.13+ syntax, and the suite matrix
  already covered 3.12.
- The D8 provider's tests were written together with the module (their red
  state was the missing module); the behavioural test drives EARNINGS_UPDATE
  screen and FULL_CREDIT full through ordinary `start_run` and `accept`.
- Not exercised here: PostgreSQL (the two optional tests skipped without
  `CAOS_TEST_POSTGRES_URL`), so the `ModelStore` DDL-on-every-boot branch and
  the statement-level residual of the publication CAS remain Task 12's.

## BLOCKED EXTERNAL

- Live-model qualification of any cell (credentials, answer keys, reviewer
  evidence): Tasks 11 and 13.
- The C21 stressed pack, C22 research pack and licensed market marks: Task 11.
- PostgreSQL two-connection evidence for acceptance and publication races:
  Task 12.

## Confidence review, second pass (patched)

- A provider could emit a `host:calculation_incomplete:<id>` limitation flag
  of its own and have it recorded as host provenance. Confirmed by a failing
  test (`test_provider_cannot_forge_a_host_limitation_flag`); fixed at the
  root: the runtime refuses any `host:`-prefixed provider flag as invalid
  output, and the store requires the set of `host:` flags on an artifact to
  equal exactly the host-declared limitations.
- The incomplete tool result did not tell the model whether a retry was still
  allowed, so a model that retried after the allowance was spent would end the
  module with `METHODOLOGY_CALCULATOR_NOT_ALLOWED`. Fixed: the result carries
  `retry_available`; pinned by
  `test_incomplete_tool_result_reports_whether_a_retry_is_still_available`
  (`[True, False]` across two incomplete attempts, module still completes with
  the limitation).
- §14.13's explanation of the 310 image checks named "three top-level
  manifests"; the extra checks are the baseline, manifest and child-schema-
  registry files verified against the integrity source hashes. Wording fixed.
- Verified fine: `queue_export` refusals reach the wire through `model_error`
  (typed, not 500); `sa.exists` live-source condition compiles on SQLite and
  is dialect-neutral; `_valid_calculation_refs` covers assigned = delivered ∪
  limited with the two sets disjoint.
