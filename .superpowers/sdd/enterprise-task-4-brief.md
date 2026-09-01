# Enterprise Task 4 — Close first-party resource leaks

## Goal

Eliminate first-party database, SQLite/LangGraph checkpointer, TestClient/application, upload-stream, and file-handle leaks before stress testing. Do not suppress `ResourceWarning` or hide warnings with filters.

## Initial owned files

- `caos/tests/conftest.py`
- `caos/tests/spec/conftest.py`
- tests that directly construct and own engines, clients, uploads, or streams
- `caos/server/caos/storage/store.py` only if the product store lacks a required owner-facing close API
- `caos/server/caos/engine/runtime.py` only if the engine/checkpointer leak reproduces outside a test-owned fixture and lacks a lifecycle API
- `caos/server/caos/api/__init__.py` only if application lifespan owns a reproduced resource
- `.superpowers/sdd/enterprise-task-4-report.md`
- `.superpowers/sdd/progress.md`

Report before expanding beyond these files. Preserve PostgreSQL behavior and runtime authority semantics.

## Required workflow

1. Run the current backend/spec/corpus suites with warnings visible and retain a grouped baseline: SQLAlchemy engine/connection, sqlite3, aiosqlite/LangGraph saver, TestClient/app lifespan, upload/temp stream, first-party deprecation, and third-party-only noise.
2. Trace each first-party warning to the constructor and intended shutdown owner. Add one failing lifecycle regression per distinct product-code root cause; fixture-only ownership changes may use a warning-as-error reproduction instead of new product tests.
3. Fix the highest shared owner first: yielding fixtures/context managers and one explicit close/dispose API are preferred over repeated per-test cleanup.
4. Close direct constructions only in the tests that own them. Use existing close/context APIs. Do not add a general resource manager, dependency, finalizer framework, garbage-collection assertion, sleep, or warning filter.
5. Re-run targeted tests under `-W error::ResourceWarning`, then the complete backend and corpus suites with warnings visible. Separate unavoidable third-party deprecations from first-party leaks in the report.

## Acceptance

- zero first-party `ResourceWarning`, unclosed connection/transport/file, or teardown warnings in targeted, full, and corpus runs;
- no required test skip added and no warning filter added;
- application/runtime resources close idempotently and cannot close a caller-owned shared resource accidentally;
- PostgreSQL-specific tests remain valid when their service is available; unavailable external infrastructure is reported, not represented as passing;
- Ruff and `git diff --check` pass;
- confidence review traces every new close path and adversarially verifies double-close, exception teardown, and ownership boundaries;
- no rewrite tournament is run because the user prohibited it for this session;
- focused implementation and evidence commits leave the worktree clean.

## Evidence report

Write `.superpowers/sdd/enterprise-task-4-report.md` with the exact baseline warning groups/counts, root cause for each first-party class, red/green commands, remaining third-party warnings, files, and commit SHAs. Do not overwrite the pre-existing `.superpowers/sdd/task-4-report.md` if present.
