# Enterprise Task 4 — First-party resource lifecycle

## Outcome

Complete. Backend tests now close their owned SQLAlchemy engines, LangGraph/aiosqlite savers, TestClients, multipart upload streams, and direct upload objects on success and exception paths. No warning was suppressed, no dependency or sleep was added, and the final full suite has zero first-party `ResourceWarning`.

Implementation commit: `0cfcc64`.

Deterministic scheduling correction: `c506808` (replaces three zero-duration scheduling yields with event handshakes; no product behavior changed).

Lifecycle follow-up correction: `6550449`. The process entrypoints now close their owned resources on both graceful and exceptional exits, and `Engine.aclose()` drains tasks from their owner loop when shutdown is requested from another loop. This correction has completed its confidence review; independent review remains pending.

The evidence commit contains this report, the Task 4 brief, and the progress ledger; its SHA is reported in the handoff because a commit cannot record its own immutable SHA.

## Warning-visible baseline

All commands used `/private/tmp/caos-enterprise-baseline-20260901/bin/python` and ran from the enterprise-readiness worktree.

| Scope and exact command | Result | Warning signatures |
| --- | --- | --- |
| `/private/tmp/caos-enterprise-baseline-20260901/bin/python -m pytest caos/tests -q -W always` | `660 passed, 2 skipped, 848 warnings in 299.97s (0:04:59)` | 443 unclosed `sqlite3.Connection` messages; 274 aiosqlite deleted-before-close messages; 135 unclosed `SpooledTemporaryFile` upload messages; 1 Starlette deprecation |
| `/private/tmp/caos-enterprise-baseline-20260901/bin/python -m pytest caos/tests/spec -q -W always` | `522 passed, 675 warnings in 127.51s` | 375 sqlite3; 259 aiosqlite; 53 upload; 1 Starlette deprecation |
| `/private/tmp/caos-enterprise-baseline-20260901/bin/python -m pytest caos/tests/test_corpus_pathways.py -q -W always` | `26 passed, 108 warnings in 122.79s` | 23 sqlite3; 2 aiosqlite; 82 upload; 1 Starlette deprecation |

The full and spec signature totals exceed pytest's warning-event totals because a single `PytestUnraisableExceptionWarning` can embed multiple resource messages. Pytest's reported event count is authoritative; the signature counts above are exact occurrences used to trace ownership. Baseline logs are retained at:

- `/private/tmp/enterprise-task-4-backend-baseline.txt`
- `/private/tmp/enterprise-task-4-spec-baseline.txt`
- `/private/tmp/enterprise-task-4-corpus-baseline.txt`

No socket or transport warning appeared.

## Root-cause ownership map

1. `DomainStore.from_url()` created and owned a SQLAlchemy engine but exposed no owner close API. Root/spec/corpus fixtures returned stores without teardown, and several tests directly constructed stores or `RunStore` engines.
2. `Engine._ensure_saver()` opened one aiosqlite/LangGraph saver per event loop and retained it indefinitely. The engine also owned pending continuation tasks, but it borrows its `DomainStore` and provider.
3. The source-upload route called `await request.form()` without closing the resulting Starlette `FormData`, leaving server-owned multipart `UploadFile`/`SpooledTemporaryFile` objects open on success and refusal paths.
4. Direct `make_upload()` helpers owned separate test-created `UploadFile` objects; route cleanup could not own those objects.
5. Direct TestClient, Engine, store, and SQLAlchemy-engine constructions bypassed shared fixture teardown. Delayed collection attributed three local SQLite helper warnings to the later PostgreSQL skip location; tracing proved the real PostgreSQL tests already dispose their engines.

## Red-to-green lifecycle evidence

Product root causes were pinned before implementation:

- `DomainStore.close()` ownership/idempotence regression: initially failed because the method did not exist.
- `Engine.aclose()` pending-task, saver, and borrowed-dependency regression: initially failed because the method did not exist.
- Upload-route success/refusal regression captured the actual multipart objects and initially failed because their files remained open.
- Saver-close retry and close-during-`_ensure_saver()` regressions initially failed because references were cleared before close and initialization could register after shutdown began.
- Concurrent `Engine.aclose()` was adversarially reproduced hanging in `aiosqlite.Connection.close()` after two callers submitted close to the same worker. The deterministic regression failed with `2` close attempts instead of `1`; after serialization, the lifecycle set passed.
- Owned store disposal was forced to fail once. The regression failed because `_closed` was marked before disposal; after moving the mark after successful disposal, retry passed.

The initial product-root command was:

`/private/tmp/caos-enterprise-baseline-20260901/bin/python -m pytest caos/tests/test_store.py::test_store_close_is_idempotent_and_disposes_only_its_owned_engine caos/tests/spec/test_runs_spec.py::test_engine_close_cancels_pending_work_closes_savers_once_and_borrows_dependencies caos/tests/spec/test_http_contracts_spec.py::test_upload_route_closes_multipart_files_on_success_and_refusal -q -W error::ResourceWarning`

It failed all three node IDs before the owner APIs/context were implemented and passed all three afterward. The concurrent-close confidence regression used:

`/private/tmp/caos-enterprise-baseline-20260901/bin/python -m pytest caos/tests/spec/test_runs_spec.py -q -W error::ResourceWarning -k serializes_concurrent_callers`

It failed with `2` close attempts instead of `1`; the post-fix lifecycle command below passed it.

Focused green commands and results:

- `/private/tmp/caos-enterprise-baseline-20260901/bin/python -m pytest caos/tests/spec/test_runs_spec.py caos/tests/test_store.py -q -W error::ResourceWarning -k 'engine_close or store_close'` — `5 passed, 35 deselected in 0.20s`.
- `/private/tmp/caos-enterprise-baseline-20260901/bin/python -m pytest caos/tests/spec/test_runs_spec.py caos/tests/spec/test_state_spec.py caos/tests/test_finalization_metering.py caos/tests/test_audit_regressions.py caos/tests/test_module_wiring.py caos/tests/test_single_instance.py caos/tests/test_store.py caos/tests/test_worker.py -q -W error::ResourceWarning` — `82 passed, 2 skipped, 1 warning in 8.23s`; the warning was the third-party Starlette deprecation.
- Earlier complete spec strict gate: `/private/tmp/caos-enterprise-baseline-20260901/bin/python -m pytest caos/tests/spec -q -W error::ResourceWarning` — `524 passed, 1 warning in 121.19s`.
- Earlier corpus strict gate: `/private/tmp/caos-enterprise-baseline-20260901/bin/python -m pytest caos/tests/test_corpus_pathways.py -q -W error::ResourceWarning` — `26 passed, 1 warning in 123.97s`.

## Implementation

- `DomainStore.from_url()` now marks its engine as owned, disposes it if schema initialization fails, and exposes retryable, idempotent `close()`. A store constructed around a caller-provided engine remains borrowed and never disposes it.
- `Engine.aclose()` rejects new saver initialization after shutdown starts, waits for in-flight same-loop initialization, cancels owned continuations, closes each saver once, retains failed saver references for retry, serializes concurrent callers, and propagates the leader's result. It never closes its borrowed store or provider.
- The upload route uses the async `FormData` context manager. Direct upload helpers close their own objects separately.
- Shared fixtures yield resources with dependency-ordered teardown: TestClient first, Engine saver/tasks second, DomainStore engine last.
- Direct test owners use context managers or `try/finally`, including revived engines and standalone SQLAlchemy engines. This preserves cleanup when an assertion or awaited operation fails.

## Final verification

- Post-confidence full strict command: `/private/tmp/caos-enterprise-baseline-20260901/bin/python -m pytest caos/tests -q -W error::ResourceWarning`
  - `666 passed, 2 skipped, 1 warning in 299.19s (0:04:59)`.
  - Zero first-party ResourceWarnings or unclosed connection, saver, file, upload, transport, or teardown warnings.
  - The only remaining warning is `StarletteDeprecationWarning` from FastAPI's third-party TestClient import: `Using httpx with starlette.testclient is deprecated; install httpx2 instead.` No dependency was changed for this task.
- `/private/tmp/caos-enterprise-baseline-20260901/bin/python -m ruff check caos` — `All checks passed!`.
- `git diff --check` — passed.
- No warning filter, suppression, dependency, sleep, or garbage-collection proof was added.
- `rewrite-tournament` was not run because the user explicitly prohibited it for this session.

The two skipped cases are the real PostgreSQL advisory-lock integration tests:

- `test_real_postgres_refuses_duplicate_role_and_releases_on_exit`
- `test_real_postgres_backend_loss_fails_closed`

`CAOS_TEST_POSTGRES_URL` was unavailable. These tests were not represented as passing; the SQLite lock-helper tests passed and now dispose their engines on exception paths.

## Confidence review — Task 4 diff

Least confident about, ranked:

1. Concurrent or cross-loop engine close could double-close a saver or deadlock.
   - Investigated by creating a saver on a retained owner loop and closing it from another loop with two simultaneous `aclose()` callers under `-W error::ResourceWarning`.
   - Verdict: confirmed concurrent-close bug in the first implementation; fixed by sharing one close operation and notifying waiters on their own loops. The post-fix probe exited successfully in 0.32 seconds, and the deterministic regression pins one close call.
2. Shutdown could race an awaited `_ensure_saver()` and allow a saver to register after the close snapshot.
   - Investigated with a paused real `AsyncSqliteSaver.setup()`.
   - Verdict: confirmed in the first implementation; fixed by tracking initialization tasks, marking shutdown under the lifecycle lock, waiting for initialization, closing the rejected connection, and refusing the initializer with `engine is closed`.
3. Clearing saver references or marking a resource closed before a close exception could make cleanup impossible to retry.
   - Investigated with fail-once saver and store close doubles.
   - Verdict: confirmed for both initial close implementations; successful savers are now removed individually, failed savers remain registered, and store `_closed` is set only after owned disposal succeeds. Both retry regressions pass.
4. Cross-loop ownership could accidentally close caller-owned dependencies.
   - Investigated with a real saver created on one loop and closed on another, plus explicit borrowed provider/store and borrowed SQLAlchemy-engine assertions.
   - Verdict: verified fine for fully initialized per-loop savers and borrowed boundaries. Active initialization on a foreign loop remains outside the documented one-execution-loop-per-thread contract; shutdown rejects new work and remains retryable, but does not attempt to drive a foreign loop.
5. Exception teardown could still depend on happy-path tail calls.
   - Investigated every touched direct constructor and converted owners to `try/finally` or a yielding fixture. Shared fixture dependency order is client → engine → store; nested direct teardown preserves store disposal even if engine close raises.
   - Verdict: verified fine by code trace, focused strict tests, and the full strict suite.
6. Upload cleanup could conflate route-owned multipart objects with test-owned helper objects.
   - Investigated the two construction paths separately. The route regression captures parser-created objects on success and refusal; `make_upload()` call sites close their own uploads in `finally`.
   - Verdict: verified fine.

Fixed: concurrent engine-close deadlock, close-during-initialization registration, saver/store retry loss after close exceptions, and every reproduced owner leak.

Verified fine: sequential double-close, concurrent close, pending continuation cancellation, cross-loop fully initialized saver close, borrowed store/provider/engine boundaries, upload success/refusal cleanup, exception teardown, and client → engine → store ordering.

By design: a single thread is driven by one execution loop; a foreign loop may own a fully initialized saver at the TestClient boundary, but concurrently driving the same thread or an in-flight initializer from two loops is unsupported.

Still open: the third-party Starlette deprecation and the two unavailable real-PostgreSQL executions. Neither is a first-party resource leak.

## Lifecycle follow-up verification

The original lifecycle work closed resources owned by test fixtures and application routes, but `run.py` and `worker.py` still left the resources they construct open after return or an exception. `run.build()` also needed rollback if provider, engine, app, or static mounting construction failed before `main()` received the owners. The correction keeps `Engine`'s borrowed-store/provider boundary unchanged:

- `run.main()` closes owned resources in dependency order: Engine, provider when it exposes `aclose()`, then DomainStore. `serve(app, engine)` remains an injected/borrowed seam and does not close either argument.
- `worker.main()` closes its owned Engine and then DomainStore, including failure while constructing the engine or model service.
- `run.build()` rolls back its partially constructed provider/engine and store while preserving the original construction exception. A provider-close failure still cannot prevent store closure.
- `Engine.aclose()` waits for saver-initialization tasks and cancels/drains continuation tasks on the loop that owns each live task. It refuses a non-runnable owner loop rather than deadlocking; existing concurrent-close, close-error, and retry semantics remain covered by the original lifecycle regressions.

Focused strict command after the correction:

`/private/tmp/caos-enterprise-baseline-20260901/bin/python -m pytest caos/tests/spec/test_runs_spec.py caos/tests/test_single_instance.py caos/tests/test_worker.py -q -W error::ResourceWarning`

Result: `53 passed, 2 skipped, 1 warning in 4.98s`. The sole warning is the pre-existing third-party Starlette TestClient deprecation; there were zero first-party ResourceWarnings.

The focused additions use separate retained, genuinely running owner-loop regressions for a continuation and an in-flight saver initialization; both fail on the prior local-loop `asyncio.gather()` path and pass with owner-loop drain. Entrypoint regressions cover normal return, service exceptions, construction rollback, and provider-close failure.

Post-review checks:

- `/private/tmp/caos-enterprise-baseline-20260901/bin/python -m ruff check caos/server/run.py caos/server/worker.py caos/server/caos/engine/runtime.py caos/tests/spec/test_runs_spec.py caos/tests/test_single_instance.py` — `All checks passed!`.
- `git diff --check` — passed before the implementation commit.
- No warning filter, suppression, dependency, sleep, or garbage-collection proof was added. `rewrite-tournament` was not run because it was explicitly prohibited for this session.

## Confidence review — lifecycle follow-up

Least confident about, ranked:

1. Foreign-loop close could hang if the owner loop was not actually running, or if both loops shared one thread.
   - Investigated with retained owner-loop tests running on a separate live thread, plus the `asyncio` loop state contract.
   - Verdict: fixed. Foreign work is only submitted to a running, distinct owner loop; non-runnable ownership fails deterministically and leaves the task registered for retry.
2. Saver initialization and continuation cancellation could appear to share a root but exercise different shutdown order.
   - Investigated with separate regressions: a paused real `AsyncSqliteSaver.setup()` and a live continuation task.
   - Verdict: fixed. Initialization drains without cancellation and rejects after close begins; continuation cancellation is dispatched and drained on its owner loop.
3. Construction or shutdown exceptions could skip a lower-level resource.
   - Investigated with entrypoint doubles for normal return, serving/worker failure, engine construction failure, and provider-close failure.
   - Verdict: fixed. Nested `finally` paths reach the store in every case; build rollback preserves the primary construction exception.
4. The correction could regress existing close serialization and retry behavior.
   - Investigated by rerunning the complete run lifecycle specification, including concurrent close and fail-once saver cases.
   - Verdict: verified fine (`53 passed, 2 skipped` in the focused strict suite).

Fixed: entrypoint ownership leaks, construction rollback leaks, and foreign-loop task draining.

Verified fine: injected `serve` ownership boundary, borrowed store/provider behavior in `Engine`, normal and exceptional resource order, cross-loop continuation cancellation, in-flight saver initialization rejection, close retry, and concurrent close serialization.

Still open: real PostgreSQL integration remains unavailable without `CAOS_TEST_POSTGRES_URL`; the unrelated third-party Starlette deprecation remains. Independent approval is not claimed here.

## Lifecycle hardening correction

Implementation commit: `209b2df`. This correction addresses the independent review findings against `6550449`; independent approval remains pending.

- `AnthropicProvider.aclose()` now closes the real `ChatAnthropic._async_client` through its documented async `close()` API. It marks itself closed only after success, so a failure is retryable and a successful double-close is a no-op. `run` still calls only the provider adapter lifecycle API.
- App, worker, and development entrypoints preserve the primary serve/poll exception while attempting every owned cleanup. With no primary exception, Engine cleanup remains the observable first failure even if provider or store cleanup also fails. `worker --once` now reaches its normal cleanup path rather than returning from inside it.
- Foreign-loop task draining has an explicit operational safety bound: `CLOSE_DRAIN_TIMEOUT_SECONDS = 5.0`. A thread-safe bridge tracks the owner-loop waiter. On expiry, bridge and waiter cancellation are best effort, a typed `RuntimeError` is raised, `_closed` remains false, and the source task stays registered for retry. A stopped-loop handoff is rejected immediately; owner-loop waiter creation errors are propagated rather than swallowed by `gather(return_exceptions=True)`.

The bound is product behavior, not a test-only timeout: a stopped event loop cannot complete its queued task waiter, so shutdown must fail retryably rather than wait indefinitely. The zero-bound regression injects the named product constant and uses event handshakes; it does not sleep or use a test timeout as proof.

Final strict lifecycle command:

`/private/tmp/caos-enterprise-baseline-20260901/bin/python -m pytest caos/tests/test_anthropic_provider.py caos/tests/spec/test_runs_spec.py caos/tests/test_single_instance.py caos/tests/test_worker.py -q -W error::ResourceWarning`

Result: `61 passed, 2 skipped, 1 warning in 5.25s`. The sole warning is the existing third-party Starlette TestClient deprecation. There were zero first-party ResourceWarnings.

Bridge-only strict regressions:

`/private/tmp/caos-enterprise-baseline-20260901/bin/python -m pytest caos/tests/spec/test_runs_spec.py::test_engine_close_propagates_foreign_waiter_creation_failure caos/tests/spec/test_runs_spec.py::test_engine_close_timeout_survives_stopped_owner_waiter_cleanup caos/tests/spec/test_runs_spec.py::test_engine_close_foreign_drain_timeout_preserves_retry_and_waiters caos/tests/spec/test_runs_spec.py::test_engine_close_refuses_owner_loop_stopped_during_waiter_handoff -q -W error::ResourceWarning`

Result: `4 passed in 0.17s`.

Post-review checks:

- Ruff on each changed Python file — `All checks passed!`.
- `git diff --check` — passed before the implementation commit.
- No warning suppression, dependency, sleep, garbage-collection proof, or rewrite tournament was added. Rewrite tournament remains explicitly prohibited for this session.

## Confidence review — lifecycle hardening correction

Least confident about, ranked:

1. The Anthropic adapter could call the wrong lifecycle API or make a close failure permanent.
   - Investigated the installed SDK: `AsyncAnthropic.close()` is awaitable and `aclose` does not exist. A production-shaped `chat._async_client` double fails once, then verifies retry and idempotent success.
   - Verdict: fixed.
2. Nested cleanup could still mask the primary operation failure, or a cleanup failure could mask an earlier cleanup failure when no operation failed.
   - Investigated with combined serve/poll, engine, provider, and store failures. Each cleanup ran; serve/poll errors won when present, and engine close won when it was the first failure.
   - Verdict: fixed.
3. A foreign bridge could remain pending when the owner stopped after the initial liveness check.
   - Investigated with a deterministic owner-loop stop between cancellation submission and waiter handoff, plus a zero-bound operational-drain injection. Both preserve `_closed == False` and the registered task for retry; retry succeeds after owner cleanup.
   - Verdict: fixed with the named five-second product bound.
4. `return_exceptions=True` could swallow a failed owner-loop waiter creation or timeout cancellation bookkeeping could replace the intended error.
   - Investigated with injected owner `create_task` failure and a stopped-loop `call_soon_threadsafe(waiter.cancel)` failure. The first bridge error now propagates; the timeout remains the typed drain error while bookkeeping is best effort.
   - Verdict: fixed.
5. The new normal worker path could bypass cleanup on `--once`.
   - Investigated from the actual `return` control flow; it bypassed `try`/`except` normal shutdown in the first draft.
   - Verdict: confirmed bug and fixed by breaking to the common shutdown path. Final strict suite exercises it.

Fixed: real Anthropic provider close, primary-error precedence, worker `--once` cleanup, foreign waiter failure propagation, and bounded foreign-loop drain timeout/stop handoff behavior.

Verified fine: borrowed `serve` seam, construction rollback primary error preservation, provider retry/double-close, normal entrypoint resource order, concurrent close error propagation, retry after foreign drain failure, and retained running-owner-loop success.

Still open: PostgreSQL advisory-lock integration is blocked externally by absent `CAOS_TEST_POSTGRES_URL`; the third-party Starlette deprecation remains. No independent approval is claimed.

## Files

Product lifecycle:

- `caos/server/caos/storage/store.py`
- `caos/server/caos/engine/runtime.py`
- `caos/server/caos/api/__init__.py`

Shared owners and direct-owner regressions/cleanup:

- `caos/tests/conftest.py`
- `caos/tests/spec/conftest.py`
- `caos/tests/test_corpus_pathways.py`
- `caos/tests/test_source_ingestion.py`
- `caos/tests/test_store.py`
- `caos/tests/test_audit_regressions.py`
- `caos/tests/test_finalization_metering.py`
- `caos/tests/test_module_wiring.py`
- `caos/tests/test_single_instance.py`
- `caos/tests/test_worker.py`
- `caos/tests/spec/test_budget_spec.py`
- `caos/tests/spec/test_evidence_spec.py`
- `caos/tests/spec/test_http_contracts_spec.py`
- `caos/tests/spec/test_injection_spec.py`
- `caos/tests/spec/test_misc_spec.py`
- `caos/tests/spec/test_observability_spec.py`
- `caos/tests/spec/test_runs_spec.py`
- `caos/tests/spec/test_state_spec.py`

Evidence:

- `.superpowers/sdd/enterprise-task-4-brief.md`
- `.superpowers/sdd/enterprise-task-4-report.md`
- `.superpowers/sdd/progress.md`

The progress file also carries the parent coordinator's already-verified Task 3 reviewer-approval update; Task 4 implementation did not alter that prior task's evidence.
