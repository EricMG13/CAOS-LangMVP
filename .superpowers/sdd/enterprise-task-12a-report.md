# Enterprise Task 12a report — database truth, simulations, single instance, backup

Executed as `ER-G7` (2026-09-03) in
`.claude/worktrees/license-data-retention-audit-36ec68` on branch
`claude/er-task-12a-database-truth` (renamed from the worktree's
`claude/open-session-ec2b00` before the push), cut from `main` at `ca6c33e`
(the Task 11 squash merge, PR #52). Local interpreter: Python 3.14.6 in
`caos/server/.venv314`, built in this worktree from the hashed lock (`uv venv
--python 3.14`, `uv pip install --require-hashes -r
caos/server/requirements-dev.txt`, dependency-less editable install of
`caos/server`; no `uv run`, no `uv.lock`). PostgreSQL: the local QA container
`caos-qa-pg` (postgres:17-alpine, PostgreSQL 17.11, host port 55433,
superuser `postgres`) for every local run, and the digest-pinned
`postgres:17-alpine@sha256:18cfe3ef…` for CI and the image drill.

Inputs read before starting: the standing preamble; Task 12 of
`docs/superpowers/plans/2026-09-01-enterprise-testing-readiness-execution.md`
(steps 1, 2, 5); Phase 5 of `ENTERPRISE_READINESS_PLAN.md` (implement items
1–13, verify list, anti-pattern guards); the SIM-001–SIM-030 table and blockers
ETR-B07/ETR-B10 in `ENTERPRISE_TESTING_READINESS.md`; `SPEC_RECONCILIATION.md`
deferral D3; `caos/deploy/RESTORE-DRILL-2026-08-30.md` findings F1–F3;
`backup.sh`, `restore_drill.sh`, `docker-compose.yml`, the Dockerfile, the CI
and nightly workflows; `storage/store.py`, `storage/runs.py`,
`storage/models.py`, `storage/deliverables.py`, `engine/runtime.py` (crash
seams, recover, finalize, saver), `engine/loop.py`, `engine/host_control.py`,
`run.py`, `worker.py`, `dev.py`; the existing fault-seam tests
(`test_runs_spec.py` kill/commit-gap, `test_budget_spec.py` unresolved spend,
`test_worker.py` stale claims, `test_deliverables_spec.py` and
`test_publication_spec.py` tamper/race/crash, `test_single_instance.py`); the
Task 6 adversarial review item 12 (F21/F22) and the Task 9–11 reports.

## Status

COMPLETE on the branch. Every gate in "Commands and results" is green on the
final code; the enterprise-image drill (backup, restore, paused and in-flight
recovery, second-instance refusal, reset, all under active writes) ran on
images built from this tree and passed; a draft pull request to `main` is
open (URL at the end and in `progress.md`). The eight-hour soak and the
saturated six-pathway workload are candidate-only (Task 13) and were not run.
Live-model runs on the enterprise image remain BLOCKED EXTERNAL (below).

## Findings that shaped the design (before the first test)

- **Where the process locks stand in for database locks.** `DomainStore`
  serialises ingest, withdrawal and acceptance behind one process-wide
  `RLock` (`_AUTHORITY_MUTATION_LOCK`); `ModelStore` and `DeliverableStore`
  each hold a `threading.Lock` around sign-off, opinion, draft append, freeze
  request, publish and filing. A thread lock orders nothing across two
  processes (app and worker) or two connections. The database already
  serialises where a conditional `UPDATE … WHERE status = …` (acceptance,
  build claim, freeze claim, filing) or a unique index (active source content,
  build fingerprint, revision number, draft version, freeze thread) exists;
  the read-then-write paths (event `seq`, budget ledger, withdrawal,
  assumption evidence check, revision head, opinion head, draft head) are
  the ones a second connection can race.
- **Existing seams cover most SIM rows.** `kill_after_modules_for_tests`,
  `crash_in_commit_gap_for_tests`, `crash_mid_provider_call_for_tests` (which
  fires after the reservation and before `create_message`, i.e. SIM-002), the
  worker's identity-bound fallbacks, the freeze job requeue, the renderer
  failure and tamper tests, and the injection fixtures. The host-control
  provider double follows every module's tools, so wrapping it with one
  injected fault gives "during the provider call" (SIM-003) and the provider
  failure matrix (SIM-024) without a new engine hook. New seams were needed
  only for checkpoint-file damage, `ENOSPC`, disconnect-after-ack and the
  restart loop.
- **Restore drill.** F1: `ModelStore`/`DeliverableStore` create their tables
  lazily, so a fresh deployment fails the drill's table assertion. F2:
  `backup.sh` finds the vault volume by Compose label and dies silently when
  the volume was created by hand. F3: `pg_dump` and the vault tar are two
  independent captures with no common snapshot point; the checkpoint store is
  WAL-mode SQLite copied live.
- **Single instance.** `store.single_instance(role)` holds a PostgreSQL
  advisory lock per role and terminates on lock loss; nothing guards the
  durable checkpoint location itself, and SQLite development has no guard.

## Design decisions

- **The PostgreSQL proof is one module and forces its interleavings.**
  `caos/tests/test_postgres_races.py` opens two SQLAlchemy engines over a
  database created per test (`CREATE DATABASE`, dropped `WITH (FORCE)`), so
  every race starts from the schema the store creates and leaves nothing
  behind. A `before_cursor_execute` listener parks one engine at a named
  statement inside its open transaction; the other engine runs to the same
  point; both are then released in a chosen order. That is deterministic
  where a thread race is hopeful, and it lets the same test express "both
  passed their pre-read" and "the second waits behind the first's lock". The
  module is the only thing allowed to be called PostgreSQL proof; SQLite
  thread races and compiled `FOR UPDATE` checks stay as fast mechanism tests.
- **Fix the store only where the module failed, with the smallest database
  primitive.** Row locks where a row exists (`runs` for event sequence and
  every run-table writer, `run_budgets` for the ledger, `sources FOR SHARE`
  for cited evidence, `case_members FOR SHARE` for standing), a conditional
  update where the read was the check (withdrawal), and a transaction-scoped
  case advisory lock (`store.lock_case`, `pg_advisory_xact_lock(hashtext(
  case_id))`) where the head may not exist yet (first sign-off, first
  opinion, first draft, first freeze). The process locks stay as the SQLite
  mechanism; removing them is out of scope and would change SQLite behaviour.
- **Lock order is cycle-free by construction:** cases → runs → nodes/
  artifacts/budget → events → audit lock row. `node_running`, `complete_node`
  and `pause_run` now take the run row first so `_emit`'s lock never inverts
  the order `finalize_failure` already uses.
- **Commit-time standing is a callback inside the transaction**
  (`authorize(conn)` on `file_record` and `request_freeze`), because the only
  place a revocation cannot slip past is the transaction that commits.
- **Startup creates the whole schema** (`DomainStore.from_url` constructs the
  model and deliverable stores). It closes F1 and it is what made the
  PostgreSQL target find that the Task 10 deliverable DDL could not be created
  through psycopg (`%` in PL/pgSQL `RAISE` is a placeholder to the driver):
  on the production image every deliverable route would have been a 500 on
  first use. The DDL now runs through `sa.text`, which escapes it.
- **The instance lock is an OS `flock` on `checkpoints.db.lock`**, taken by
  `run.py` and `dev.py` around `serve` — before recovery runs or a socket is
  bound — nested with the PostgreSQL advisory lock in production. It covers
  SQLite development and the checkpoint volume itself, which the advisory
  lock cannot see, and the kernel releases it however the holder dies.
- **Backup snapshot point = paused writers.** `backup.sh` pauses the `app`
  and `worker` containers for the whole capture and unpauses on every exit
  path; the vault volume comes from the app container's `/vault` mount or
  `CAOS_VAULT_VOLUME`, never a Compose label; `checkpoints.db-shm` is
  excluded. The cost (the application answers nothing during the capture) is
  documented in `caos/deploy/ENVIRONMENT_MANIFEST.md`; measured on the drill
  it was about one second under load with zero failed requests.
- **The SIM ledger is a CSV pinned by a test.** `docs/SIMULATION_LEDGER.csv`
  records seam, tests, injected fault, expected, actual and post-restart state
  for every row; `caos/tests/test_simulation_ledger.py` fails when a row is
  missing, incomplete, not a pass, or names a test that no longer exists.
- **The image drill runs this tree's images under the host-control binding.**
  Production refuses host control and no provider credential exists, so runs
  cannot execute on the production identity edge. The drill therefore runs
  the exact `app` and `worker` images with `ENVIRONMENT=development`,
  `CAOS_PROVIDER=host_control`, the PostgreSQL store and the real vault
  volume through a Compose override, which is what lets runs, checkpoints and
  acceptance exist under active writes. That is orchestration proof on the
  image, never analysis, and the live-credential variant stays external.

## What changed (files)

Product code, each change proven by a failing test first:

- `caos/server/caos/storage/runs.py` — `_emit` locks the run row before
  allocating `seq`; `node_running`, `complete_node`, `pause_run` lock the run
  row first; `node_running` never marks a node on a terminal run;
  `_budget_locked` locks the ledger row.
- `caos/server/caos/storage/store.py` — `lock_case`, `require_standing`,
  conditional `withdraw`, `save_assumption` `FOR SHARE`, whole schema at
  startup.
- `caos/server/caos/storage/models.py` — `lock_case` in `sign_off_revision`;
  `requeue_building_builds`.
- `caos/server/caos/storage/deliverables.py` — `lock_case` in `sign_opinion`,
  `request_freeze`, `publish_frozen`, `append_revision`; `authorize` callbacks
  on `request_freeze` and `file_record`; the append-only DDL through `sa.text`.
- `caos/server/caos/deliverables/service.py` — passes the standing rechecks.
- `caos/server/caos/models/service.py` — `recover_builds`.
- `caos/server/caos/models/engine.py` — `mkdtemp` + explicit finalizer
  instead of `TemporaryDirectory` (the last first-party ResourceWarning).
- `caos/server/caos/api/__init__.py` — `OperationalError` → 503
  `STORE_UNAVAILABLE`; `…REVOKED` codes → 403.
- `caos/server/caos/instance_lock.py` (new), `run.py`, `dev.py`, `worker.py`.
- `caos/deploy/backup.sh`, `restore_drill.sh`, `docker-compose.yml`,
  `ENVIRONMENT_MANIFEST.md` (new).
- `.github/workflows/ci.yml` — `postgres` job; full startup table list in the
  boot check.

Tests: `caos/tests/test_postgres_races.py` (27), `caos/tests/spec/
test_simulations_spec.py` (25), `caos/tests/test_deploy_topology.py` (9),
`caos/tests/test_simulation_ledger.py` (3), additions to
`test_single_instance.py` (3) and `test_store.py` (1). Docs:
`docs/SIMULATION_LEDGER.csv`, `docs/DECISIONS.md` §14.21,
`SPEC_RECONCILIATION.md` (D3 closed; race matrix), `CLAUDE.md`,
`ENTERPRISE_TESTING_READINESS.md` (ETR-B07, ETR-B10), `pytest.ini`.

## Commands and results

Working directory for every command: the worktree root. `PG` below is
`CAOS_TEST_POSTGRES_URL="postgresql+psycopg://postgres:qa-local-only-not-a-secret-0000@127.0.0.1:55433/postgres"`.

```text
# Baseline of the new race module on the store as it stood at ca6c33e
$ PG .venv314/bin/python -m pytest caos/tests/test_postgres_races.py -q -p no:cacheprovider
→ 11 failed, 15 passed in 34.05s
  failures: assumption[withdrawal] (READY citing a withdrawn source);
  event_sequence (KeyError in the test, then raw PK violation on the store);
  budget reserve/reconcile/charge (both writers "ok": lost update);
  opinion (two heads), draft (stale head), freeze_request/claim/publish/filing
  (DeliverableStore could not be constructed on PostgreSQL:
  psycopg.ProgrammingError "incomplete placeholder: '%'" in the append-only DDL)

# After the store changes
$ PG .venv314/bin/python -m pytest caos/tests/test_postgres_races.py -q -p no:cacheprovider
→ 26 passed (then 27 with the SIM-011 disconnect test)
$ PG .venv314/bin/python -m pytest caos/tests/test_postgres_races.py caos/tests/test_single_instance.py -q -p no:cacheprovider -W always -rs
→ 76 passed in 61.77s   (no skips: both real-PostgreSQL advisory-lock tests ran)

# Simulations
$ .venv314/bin/python -m pytest caos/tests/spec/test_simulations_spec.py -q -p no:cacheprovider -W always
→ 25 passed, 1 warning (third-party StarletteDeprecationWarning only)
  Before the fixes the module showed: SIM-008 StopIteration / no requeue path
  (row stuck BUILDING), SIM-010 a bare 500, SIM-020 a 200 FILED after the
  approver's standing was revoked, SIM-003 a node left `running` on a failed
  run after restart, SIM-029 a first-party ResourceWarning from the CP-MODEL
  temporary directory.

# Deployment topology, backup harness, ledger, store, worker, instance locks
$ .venv314/bin/python -m pytest caos/tests/test_deploy_topology.py caos/tests/test_simulation_ledger.py caos/tests/test_store.py caos/tests/test_worker.py caos/tests/test_single_instance.py -q -p no:cacheprovider -W always
→ all pass (9 + 3 + 12 + 6 + 49), no ResourceWarning after the subprocess pipes were closed

# Affected spec files on SQLite
$ .venv314/bin/python -m pytest caos/tests/spec/test_runs_spec.py … test_loan_universe_spec.py -q -W always
→ 438 passed in 577.42s (before the SIM-driven fixes)
$ .venv314/bin/python -m pytest caos/tests/spec/test_model_builder_spec.py test_deliverables_spec.py test_publication_spec.py test_runs_spec.py test_distressed_model_overlay.py test_source_complete_modelling_spec.py -q -W always
→ 361 passed, 1 warning in 783.03s (0 ResourceWarning) — after every store and lifecycle change

# Full backend suite, PostgreSQL target included
$ PG ANTHROPIC_API_KEY= OPENROUTER_API_KEY= GEMINI_API_KEY= .venv314/bin/python -m pytest caos/tests -q -p no:cacheprovider -W always
→ first run on the final product code: 1 failed, 1161 passed, 4 skipped, 2 warnings in 1256.03s
  FAILED test_deliverables_spec.py::test_filing_refuses_export_metadata_substituted_from_another_reviewed_draft
  — CASE_STANDING_REVOKED: the test filed at the service level as "approver-user" without stored case
  standing (every neighbouring service-level filer calls add_approver); the new commit-time recheck
  refused it. The test now provisions the approver; the product code is unchanged by the fix.
  Warnings: the third-party StarletteDeprecationWarning and one first-party ResourceWarning in
  test_qualification_harness.py (an unclosed CSV handle, pre-existing from Task 11) — closed.
$ … same command, -rs, after the two test edits
→ 1162 passed, 4 skipped, 1 warning in 1217.84s (0:20:17)
  skips: three corpus tests (the 30-document Carnival corpus is not fetched in this worktree —
  "corpus incomplete — run: caos/tests/corpus/fetch.sh"; CI and nightly fetch it) and the whole-pack
  harness cell that is nightly-only (CORPUS_FULL=1); the one warning is the third-party
  StarletteDeprecationWarning; no ResourceWarning of any origin

# Release gates and lint (final code)
$ .venv314/bin/python run_sec_audit.py
→ {'audited_routes': 59, 'case_boundary_routes': 48, 'failures': 0}
$ .venv314/bin/python docs/quality_ledger_coverage.py
→ routes checked: 54   product files: 336   features: 131 — the ledger documents every route and every product file
$ .venv314/bin/python -m ruff check --config ruff.toml caos/server caos/tests --exclude caos/server/caos/methodology/vendor
→ All checks passed!
$ bash -n caos/deploy/backup.sh caos/deploy/restore_drill.sh; docker compose -f caos/deploy/docker-compose.yml config -q --no-interpolate
→ both clean
```

Frontend gates were not run: no frontend file changed in this task.

### Enterprise-image drill (2026-09-03, images built from this tree)

Images: `docker build --target app` → `caos-t12a-app` (`sha256:2e9e2eb8fe68…`),
`--target worker` → `caos-t12a-worker` (`sha256:a08f1069cda9…`). Stack: the
shipped `caos/deploy/docker-compose.yml` plus a scratch override that pins
those images, exposes the app on `127.0.0.1:18100`, and runs the app with
`ENVIRONMENT=development`, `CAOS_PROVIDER=host_control`, the PostgreSQL store
(`db` service, pinned image) and the real `vault-data` volume, with the same
`checkpoint_lock` + `single_instance("app")` guards as `run.py`; `clamav`
(pinned `1.5`, amd64 under emulation) became healthy in about a minute.
Active writes: a host-side driver looping create case → three uploads →
FULL_CREDIT screen run → poll → accept, with one extra case left parked at
`SOURCE_SET_EMPTY`.

```text
$ docker compose -p caos-t12a … up -d --no-build db clamav app worker
→ db healthy, app healthy, worker started; GET /api/health {"status":"ok","store":true,"bundle":true,"checkpointer":true}

# Backup under active writes (driver at ~1 cycle/s)
$ COMPOSE_PROJECT_NAME=caos-t12a CAOS_BACKUP_RECIPIENT=age1… bash caos/deploy/backup.sh <out>
→ exit 0 in ~1 s; manifest: vault_volume caos-t12a_vault-data, snapshot_point paused-writers
  driver log across the window: 0 transport errors, every request 201/200 (largest gap 1.1 s = one run cycle)

# Restore drill against that backup
$ CAOS_BACKUP_IDENTITY=key.txt COMPOSE_PROJECT_NAME=caos-t12a bash caos/deploy/restore_drill.sh <out>/caos.dump.age
→ exit 0: "restore drill passed for isolated database caos_restore_drill"

# Snapshot-point check (own script: decrypt both halves into a throwaway DB and volume)
→ sources checked=198 missing=0 mismatched=0; checkpoint files [checkpoints.db, -wal, .lock];
  PRAGMA integrity_check ok; non-terminal runs=2 (1 paused, 1 running) both with checkpoint threads;
  runs by status: paused 1, running 1, succeeded 65

# Second app instance over the same vault volume
$ docker compose -p caos-t12a … run --rm --no-deps -T app
→ exit 1: "InstanceAlreadyRunning: INSTANCE_ALREADY_RUNNING: another CAOS application instance
  holds the checkpoint location /vault/checkpoints.db.lock"; the first app stayed healthy

# SIGKILL app+worker under load, restart
$ docker compose -p caos-t12a kill -s SIGKILL app worker; … up -d --no-build app worker
→ health back in 1 s; app log: recovery.started runs=1, recovery.run action=skipped_interrupt (the parked run)
  driver: 27,628 connection-refused attempts during the ~11 s outage (tight loop), then cycles resumed;
  the driver also hit the 300/min request ceiling (typed 429s) from 12.8 s before the kill — the ceiling working

# Paused recovery
→ parked run status after restart: paused SOURCE_SET_EMPTY; upload one source; POST /resume → running
  → succeeded; events run.paused, run.succeeded

# In-flight recovery: full-depth run SIGKILLed 0.4 s after start
→ at kill: status running, 6 modules succeeded (CP-PARSE, CP-0, CP-1, CP-1A, CP-1B, CP-1C), CP-1D and CP-2E running,
  9 pending; executions 6, events 16, artifacts 6, budget turns 28, inflight none
→ restart: recovery.run action=resumed; final status succeeded; modules executed more than once: none;
  artifacts per module >1: none; terminal events: run.succeeded; event seq contiguous: t; node statuses:
  succeeded; budget turns 81, inflight none, attempts 93; checkpoint rows left for the run: 0; accept → snapshot

# Worker in-flight recovery on the image
→ model readiness for the recovered case: CANONICAL_MODEL_INPUTS_INVALID (host control on three tiny documents
  never reaches READY_TO_BUILD, so no real build was queued during the drill); a dead-worker claim was
  reproduced by stopping the worker and inserting a BUILDING row bound to the accepted run → worker start:
  "worker.builds_recovered count 1", row FAILED MODEL_INPUT_INVALID (typed, the synthetic inputs), 0 rows BUILDING

# Reset under the running stack
$ docker compose -p caos-t12a … down -v; … up -d --no-build db clamav app worker
→ before: cases 325, sources 781, runs 260, audit rows 1364, 326 chain heads, 785 vault files
  after: cases 0, sources 0, runs 0, audit 0; vault holds only checkpoints.db, -shm, -wal, .lock;
  health ok in 1 s; GET /api/cases → []; startup tables missing: none; 31 tables in the fresh schema
```

Driver totals: 323 cases created, 258 runs (all `succeeded`), 257 accepted;
the stack, its volumes and network were removed afterwards (`down -v`); the
two images remain on the machine.

## SIM-001–SIM-030 ledger

`docs/SIMULATION_LEDGER.csv` is the retained record (seam, tests, injected
fault, expected outcome, actual outcome, post-restart state, status, date),
pinned by `caos/tests/test_simulation_ledger.py`. Six rows record a defect the
simulation found and the fix: SIM-008 (BUILDING rows requeued at worker
start), SIM-010 (typed 503 `STORE_UNAVAILABLE`), SIM-012 (case advisory lock;
run-row and budget-row locks), SIM-014 (conditional withdrawal), SIM-016 (case
advisory lock), SIM-020 (commit-time standing recheck). SIM-003 also fixed a
node left `running` on a terminal run after restart. SIM-029 notes that
LibreOffice is installed in the worker image but runtime exports use the
Python renderer and pango-view, so the hang seam is the subprocess renderer.

## BLOCKED EXTERNAL / not run here

- Live-model runs on the production identity edge of the enterprise image
  (provider credential, qualification record): the drill ran this tree's
  images under the host-control binding, which is orchestration proof, not
  analysis.
- Real model builds and freezes on the image under active writes: host
  control on the drill's three-document packs reads
  `CANONICAL_MODEL_INPUTS_INVALID`, so the worker's build and freeze paths on
  the image were exercised through recovery of a dead claim and the unit-level
  simulations, not through a queued build from an accepted run. The Carnival
  pack or a live binding would give real builds.
- The eight-hour soak and the saturated six-pathway workload (candidate only,
  Task 13).
- Scheduled off-host transfer, rotation and retention of backups (deployment
  gates, unchanged).

## Confidence review

Doubts enumerated before declaring done, each investigated:

1. *Does `lock_case`'s one-argument advisory key collide with the instance
   lock's two-argument key?* No: PostgreSQL stores `(bigint)` and `(int, int)`
   advisory keys in different key layouts; the races and the instance-lock
   tests pass together on one database.
2. *Can the new `runs` row lock in `_emit` deadlock with `finalize_failure`?*
   It could have, had `complete_node`/`node_running` kept locking node rows
   before the run row. Both now take the run row first; the order is cases →
   runs → nodes/artifacts/budget → events → audit lock row everywhere I read.
3. *Does `node_running`'s terminal check change single-process behaviour?* It
   only skips a transition the run's terminal state already makes untrue;
   the affected spec files (361 tests) pass unchanged.
4. *Is the disconnect-after-ack test flaky?* It terminates every backend of
   the writing store and retries up to three times; SQLAlchemy invalidates
   the pool on the first disconnect error. It passed on every run (3 of 3);
   noted as the one test with a retry loop.
5. *Does `DomainStore.from_url` creating the sub-stores break any test that
   counts tables or times startup?* No such assertions exist; the full suite
   result is the check (below).
6. *Is the `flock` held across the whole serving lifetime and released on a
   hard kill?* The fd is opened in `main` and closed in the context manager's
   `finally`; the kernel releases it on process death, which the drill proved
   by SIGKILLing the app and restarting it on the same volume with no manual
   cleanup.
7. *Does the standing recheck use the same roles as the route?* Filing:
   `{APPROVER, ADMIN}` = `require_case_approver`; freeze: `{ANALYST,
   APPROVER, ADMIN}` = `require_case(write=True)`.
8. *Does `backup.sh` unpause on failure?* The fake-docker harness asserts
   `unpause` follows `pause` when `pg_dump` fails and that no output file
   remains; the drill's real run unpaused within about a second.
9. *Does the CI `postgres` job actually run the tests?* The URL is set from
   the service, `CAOS_REQUIRE_POSTGRES=1` turns an unset URL into a failure,
   and the local run of the identical command reports `76 passed` with
   `-rs` showing no skips.
10. *Did the SIM module's in-process "kill" match a real kill?* Not for a
    crash inside a parallel superstep: a sibling module can fail the run
    closed before the crash surfaces. SIM-003 asserts the ledger invariant
    (one in-flight digest, no re-spend, no node left running) rather than the
    exception, and the image drill supplied the real SIGKILL.
11. *No first-party ResourceWarning?* The subprocess pipes in the new lock
    tests and the CP-MODEL `TemporaryDirectory` were the two found; both
    fixed; the affected spec run and the PostgreSQL target report none.

## Open items and follow-ups

- The process-wide `_AUTHORITY_MUTATION_LOCK` and the sub-store `_WRITE_LOCK`s
  remain as the SQLite mechanism (DECISIONS §14.21 leaves their removal
  undecided).
- Exports still have no claim (two workers would both render one export);
  a second worker is refused at startup, so this stays a documented gap.
- The active-writes driver spun without back-off during the outage and hit
  the per-subject request ceiling; both are properties of the scratch driver,
  not the product, and the ceiling's typed 429 is the intended behaviour.
- Task 12b owns the full authorization matrix; the commit-time standing
  recheck landed here because SIM-020 proved the defect.

Draft pull request: https://github.com/EricMG13/CAOS-LangMVP/pull/54 (branch `claude/er-task-12a-database-truth`, commit `8afdb67` plus this URL commit).

## CI follow-up (2026-09-03, after the draft PR)

The babysit loop reported both server legs red before pytest ran: `docs/quality_ledger_coverage.py`
refused because `caos/server/caos/instance_lock.py` and `docs/SIMULATION_LEDGER.csv` mapped to no
feature. Cause: the gate walks `git ls-files`, and when it ran green here the two files were still
untracked; they became product files the moment they were committed (the script's own comment
records the same trap for the ledger files). Fix, as author judgment rather than a mapping tweak:
two new ledger features — `F-OPS-13` (single-instance enforcement: the checkpoint-location lock,
its entrypoints, Compose replicas and the manifest, with its tests and the drill result) and
`F-QUAL-04` (the retained SIM-001–030 ledger and the tests that pin it) — plus `FILE_MAP` entries
for the two paths, and the `F-OPS-05` backup row refreshed to describe the F1–F3 repairs and the
2026-09-03 drill. Local gate on the committed tree afterwards:

```text
$ .venv314/bin/python docs/quality_ledger_coverage.py
→ routes checked: 54   product files: 342   features: 133 — the ledger documents every route and every product file
```
