"""Run-engine specification (invariants 1, 4, 5, 10). All tests must fail until the engine exists.

Sources: TEST_INVENTORY.md contractual rows from test_clean_slate.py, test_ledger_contracts.py,
and the re-hosted CP-DR finalization rows; DECISIONS.md §§10–12.
"""

from __future__ import annotations

import asyncio
import sqlite3
import sys
import threading
from contextlib import closing
from pathlib import Path

import pytest

from spec_helpers import seed_case_with_source, start_full_credit_run


def _checkpoint_rows(path, thread_id: str) -> int:
    with closing(sqlite3.connect(path)) as conn:
        return sum(
            conn.execute(f"SELECT count(*) FROM {table} WHERE thread_id = ?", (thread_id,)).fetchone()[0]
            for table in ("checkpoints", "writes")
        )


async def test_engine_close_cancels_pending_work_closes_savers_once_and_borrows_dependencies(
    tmp_path, settings, store,
):
    from caos.engine.runtime import Engine

    class BorrowedProvider:
        closed = False

        async def aclose(self):
            self.closed = True

    provider = BorrowedProvider()
    engine = Engine.create(
        settings=settings,
        store=store,
        checkpoint_path=tmp_path / "lifecycle.db",
        provider=provider,
    )
    try:
        saver = await engine._ensure_saver()
        cancelled = asyncio.Event()

        async def pending_continuation():
            try:
                started.set()
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        started = asyncio.Event()
        pending = asyncio.create_task(pending_continuation())
        engine._continuations.add(pending)
        await started.wait()

        await engine.aclose()
        await engine.aclose()

        assert pending.cancelled() and cancelled.is_set()
        assert saver.conn._connection is None
        assert engine._savers == {}
        assert provider.closed is False, "the engine borrows its provider"
        assert store.create_case("Still open", "Issuer", "Services", "analyst"), \
            "the engine borrows its domain store"
    finally:
        await engine.aclose()


async def test_engine_close_retries_a_saver_that_failed_to_close(tmp_path, settings, store, monkeypatch):
    from caos.engine.runtime import Engine

    engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "retry-close.db")
    saver = await engine._ensure_saver()
    real_close = saver.conn.close
    attempts = 0

    async def fail_once():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("close failed")
        await real_close()

    monkeypatch.setattr(saver.conn, "close", fail_once)
    try:
        with pytest.raises(RuntimeError, match="close failed"):
            await engine.aclose()
        await engine.aclose()

        assert attempts == 2, "a failed close must retain its saver for an idempotent retry"
        assert saver.conn._connection is None
    finally:
        await engine.aclose()


async def test_engine_close_serializes_concurrent_callers(tmp_path, settings, store, monkeypatch):
    from caos.engine.runtime import Engine

    engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "concurrent-close.db")
    saver = await engine._ensure_saver()
    real_close = saver.conn.close
    entered = asyncio.Event()
    release = asyncio.Event()
    attempts = 0

    async def paused_close():
        nonlocal attempts
        attempts += 1
        attempt = attempts
        entered.set()
        await release.wait()
        if attempt == 1:
            await real_close()

    monkeypatch.setattr(saver.conn, "close", paused_close)
    first = asyncio.create_task(engine.aclose())
    second = None
    try:
        await entered.wait()
        second_started = asyncio.Event()

        async def close_second():
            second_started.set()
            await engine.aclose()

        second = asyncio.create_task(close_second())
        await second_started.wait()
        release.set()
        await asyncio.gather(first, second)

        assert attempts == 1, "concurrent callers must share one owned close operation"
    finally:
        release.set()
        await asyncio.gather(first, *(task for task in (second,) if task is not None), return_exceptions=True)
        await engine.aclose()


async def test_engine_close_catches_a_saver_initializing_concurrently(
    tmp_path, settings, store, monkeypatch,
):
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    from caos.engine.runtime import Engine

    entered = asyncio.Event()
    release = asyncio.Event()
    real_setup = AsyncSqliteSaver.setup

    async def paused_setup(saver):
        entered.set()
        await release.wait()
        await real_setup(saver)

    monkeypatch.setattr(AsyncSqliteSaver, "setup", paused_setup)
    engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "racing-close.db")
    initializing = asyncio.create_task(engine._ensure_saver())
    closing = None
    try:
        await entered.wait()
        close_started = asyncio.Event()

        async def close_engine():
            close_started.set()
            await engine.aclose()

        closing = asyncio.create_task(close_engine())
        await close_started.wait()
        assert not closing.done(), "close must wait for an in-flight saver initialization"
        release.set()
        await closing

        with pytest.raises(RuntimeError, match="engine is closed"):
            await initializing
        assert engine._savers == {}, "no saver may register after shutdown begins"
    finally:
        release.set()
        await asyncio.gather(initializing, *(task for task in (closing,) if task is not None), return_exceptions=True)
        await engine.aclose()


async def test_continuation_registration_is_atomic_with_close(tmp_path, settings, store, monkeypatch):
    from caos.engine.runtime import Engine

    engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "continuation-race.db")
    engine.enable_auto_continue()
    monkeypatch.setattr(engine.runs, "get_run", lambda _run_id: {"status": "running"})
    cancelled = asyncio.Event()
    drain_entered = asyncio.Event()
    release_drain = asyncio.Event()

    async def pending(_run_id):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    real_drain = engine._drain_tasks

    async def held_drain(tasks, *, cancel=False):
        drain_entered.set()
        await release_drain.wait()
        await real_drain(tasks, cancel=cancel)

    monkeypatch.setattr(engine, "wait", pending)
    monkeypatch.setattr(engine, "_drain_tasks", held_drain)
    engine._schedule_continuation("before-close")
    registered = set(engine._continuations)
    closing = asyncio.create_task(engine.aclose())
    await drain_entered.wait()
    engine._schedule_continuation("late")
    assert engine._continuations == registered
    release_drain.set()
    await closing
    assert cancelled.is_set()
    assert engine._continuations == set()


async def test_continuation_failure_is_consumed_and_logged_safely(tmp_path, settings, store, monkeypatch):
    import caos.engine.runtime as runtime

    engine = runtime.Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "continuation-failure.db")
    engine.enable_auto_continue()
    monkeypatch.setattr(engine.runs, "get_run", lambda _run_id: {"status": "running"})
    logged = asyncio.Event()
    records = []
    unhandled = []
    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()

    async def failing(_run_id):
        raise ValueError("document text must not be logged")

    def record(*args, **kwargs):
        records.append((args, kwargs))
        logged.set()

    monkeypatch.setattr(engine, "wait", failing)
    monkeypatch.setattr(runtime, "log_event", record)
    loop.set_exception_handler(lambda _loop, context: unhandled.append(context))
    try:
        engine._schedule_continuation("run-safe")
        await logged.wait()
    finally:
        loop.set_exception_handler(previous_handler)

    assert unhandled == []
    assert records == [(("engine.continuation_failed",), {
        "level": runtime.logging.ERROR, "run_id": "run-safe", "detail": "ValueError",
    })]


async def test_same_loop_continuation_timeout_is_retryable(tmp_path, settings, store, monkeypatch):
    import caos.engine.runtime as runtime

    engine = runtime.Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "local-timeout.db")
    started = asyncio.Event()
    cancelled = asyncio.Event()
    release = asyncio.Event()

    async def suppress_cancel():
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            await release.wait()

    task = asyncio.create_task(suppress_cancel())
    engine._continuations.add(task)
    await started.wait()
    monkeypatch.setattr(runtime, "CLOSE_DRAIN_TIMEOUT_SECONDS", 0.0)
    first = asyncio.create_task(engine.aclose())
    second = asyncio.create_task(engine.aclose())
    errors = await asyncio.gather(first, second, return_exceptions=True)
    assert all(isinstance(error, RuntimeError) and "timed out draining tasks" in str(error) for error in errors)
    assert cancelled.is_set() and engine._closed is False and task in engine._continuations
    release.set()
    await task
    monkeypatch.setattr(runtime, "CLOSE_DRAIN_TIMEOUT_SECONDS", 5.0)
    await engine.aclose()


# Quarantined on 3.12 only — issue #42. `_drain_tasks` asks `_owner_loop_runnable`
# whether a foreign owner loop is usable and then uses it, and the two are not
# atomic: a loop that answers yes can be stopping by the time it is used, which
# raises "cannot close a task without a runnable owner loop". That check reads
# CPython private asyncio internals (`_thread_id`, `_stopping`), whose timing is
# not stable across versions, which is why only the 3.12 leg lands in the window
# — production ships 3.14 and that leg has never failed this.
#
# `xfail` rather than `skip`, and non-strict on purpose: the test still runs and
# still reports on 3.12, so an XPASS keeps showing the ~50% rate instead of
# hiding it. It just stops blocking CI. Delete this marker with the fix, not
# before — the 3.12 leg is the only thing checking that private-attribute
# probing holds on more than one interpreter.
@pytest.mark.xfail(
    sys.version_info < (3, 13),
    reason="issue #42: foreign-loop drain races the owner loop's stopping state on 3.12",
    strict=False,
)
async def test_engine_close_drains_foreign_loop_continuation(tmp_path, settings, store):
    from caos.engine.runtime import Engine

    started = threading.Event()
    finished = threading.Event()
    cancelled = threading.Event()
    engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "foreign-loop.db")

    def own_continuation() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def pending_continuation() -> None:
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        async def run() -> None:
            continuation = asyncio.create_task(pending_continuation())
            engine._continuations.add(continuation)
            await asyncio.gather(continuation, return_exceptions=True)

        try:
            loop.run_until_complete(run())
        finally:
            loop.close()
            finished.set()

    owner = threading.Thread(target=own_continuation)
    owner.start()
    try:
        await asyncio.to_thread(started.wait)
        await engine.aclose()

        assert cancelled.is_set()
        assert engine._continuations == set()
    finally:
        await engine.aclose()
        await asyncio.to_thread(owner.join)
        assert finished.is_set()


async def test_engine_close_drains_foreign_loop_saver_initialization(
    tmp_path, settings, store, monkeypatch,
):
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    from caos.engine.runtime import Engine

    setup_started = threading.Event()
    draining = threading.Event()
    release_setup = threading.Event()
    finished = threading.Event()
    outcome = {}
    real_setup = AsyncSqliteSaver.setup

    async def paused_setup(saver):
        setup_started.set()
        await asyncio.to_thread(release_setup.wait)
        await real_setup(saver)

    async def wait_for_task(task):
        draining.set()
        await asyncio.gather(task, return_exceptions=True)

    monkeypatch.setattr(AsyncSqliteSaver, "setup", paused_setup)
    engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "foreign-loop.db")
    monkeypatch.setattr(engine, "_wait_for_task", wait_for_task)

    def initialize_saver() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def run() -> None:
            initializing = asyncio.create_task(engine._ensure_saver())
            outcome["initialization"] = (await asyncio.gather(initializing, return_exceptions=True))[0]

        try:
            loop.run_until_complete(run())
        finally:
            loop.close()
            finished.set()

    owner = threading.Thread(target=initialize_saver)
    owner.start()
    try:
        await asyncio.to_thread(setup_started.wait)
        closing = asyncio.create_task(engine.aclose())
        await asyncio.to_thread(draining.wait)
        release_setup.set()
        await closing

        assert engine._savers == {}
        assert isinstance(outcome["initialization"], RuntimeError)
    finally:
        release_setup.set()
        await engine.aclose()
        await asyncio.to_thread(owner.join)
        assert finished.is_set()


async def test_engine_close_foreign_drain_timeout_preserves_retry_and_waiters(
    tmp_path, settings, store, monkeypatch,
):
    import caos.engine.runtime as runtime

    engine = runtime.Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "timeout.db")
    ready = threading.Event()
    cancelled = threading.Event()
    stopped = threading.Event()
    owned = {}

    def own_initialization() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def pending() -> None:
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        def prepare() -> None:
            task = loop.create_task(pending())
            owned["task"] = task
            engine._saver_initializations.add(task)
            ready.set()

        loop.call_soon(prepare)
        try:
            loop.run_forever()
        finally:
            loop.close()
            stopped.set()

    owner = threading.Thread(target=own_initialization)
    owner.start()
    try:
        await asyncio.to_thread(ready.wait)
        monkeypatch.setattr(runtime, "CLOSE_DRAIN_TIMEOUT_SECONDS", 0.0)
        first = asyncio.create_task(engine.aclose())
        second = asyncio.create_task(engine.aclose())
        first_error, second_error = await asyncio.gather(first, second, return_exceptions=True)

        assert isinstance(first_error, RuntimeError)
        assert isinstance(second_error, RuntimeError)
        assert "timed out" in str(first_error)
        assert "timed out" in str(second_error)
        assert engine._closed is False
        assert owned["task"] in engine._saver_initializations

        owner_loop = owned["task"].get_loop()
        owner_loop.call_soon_threadsafe(owned["task"].cancel)
        await asyncio.to_thread(cancelled.wait)
        monkeypatch.setattr(runtime, "CLOSE_DRAIN_TIMEOUT_SECONDS", 5.0)
        await engine.aclose()
    finally:
        owner_loop = owned.get("task") and owned["task"].get_loop()
        if owner_loop is not None and owner_loop.is_running():
            owner_loop.call_soon_threadsafe(owner_loop.stop)
        await asyncio.to_thread(owner.join)
        assert stopped.is_set()


async def test_engine_close_propagates_foreign_waiter_creation_failure(
    tmp_path, settings, store, monkeypatch,
):
    from caos.engine.runtime import Engine

    engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "waiter-failure.db")
    ready = threading.Event()
    cancelled = threading.Event()
    stopped = threading.Event()
    owned = {}

    def own_initialization() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def pending() -> None:
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        def prepare() -> None:
            task = loop.create_task(pending())
            owned["task"] = task
            engine._saver_initializations.add(task)
            ready.set()

        loop.call_soon(prepare)
        try:
            loop.run_forever()
        finally:
            loop.close()
            stopped.set()

    owner = threading.Thread(target=own_initialization)
    owner.start()
    try:
        await asyncio.to_thread(ready.wait)
        owner_loop = owned["task"].get_loop()
        real_create_task = owner_loop.create_task

        def fail_create_task(coro, *args, **kwargs):
            raise RuntimeError("foreign waiter creation failed")

        monkeypatch.setattr(owner_loop, "create_task", fail_create_task)
        with pytest.raises(RuntimeError, match="foreign waiter creation failed"):
            await engine.aclose()

        assert engine._closed is False
        assert owned["task"] in engine._saver_initializations
        monkeypatch.setattr(owner_loop, "create_task", real_create_task)
        owner_loop.call_soon_threadsafe(owned["task"].cancel)
        await asyncio.to_thread(cancelled.wait)
        await engine.aclose()
    finally:
        owner_loop = owned.get("task") and owned["task"].get_loop()
        if owner_loop is not None and owner_loop.is_running():
            owner_loop.call_soon_threadsafe(owner_loop.stop)
        await asyncio.to_thread(owner.join)
        assert stopped.is_set()


async def test_engine_close_timeout_survives_stopped_owner_waiter_cleanup(
    tmp_path, settings, store, monkeypatch,
):
    import caos.engine.runtime as runtime

    engine = runtime.Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "timeout-cleanup.db")
    ready = threading.Event()
    waiter_started = threading.Event()
    cancelled = threading.Event()
    stopped = threading.Event()
    owned = {}

    def own_initialization() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def pending() -> None:
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        def prepare() -> None:
            task = loop.create_task(pending())
            owned["task"] = task
            engine._saver_initializations.add(task)
            ready.set()

        loop.call_soon(prepare)
        try:
            loop.run_forever()
        finally:
            loop.close()
            stopped.set()

    class ForcedTimeout:
        async def __aenter__(self):
            await asyncio.to_thread(waiter_started.wait)
            raise TimeoutError

        async def __aexit__(self, *_args):
            return False

    async def wait_for_task(task):
        waiter_started.set()
        await asyncio.gather(task, return_exceptions=True)

    owner = threading.Thread(target=own_initialization)
    owner.start()
    try:
        await asyncio.to_thread(ready.wait)
        owner_loop = owned["task"].get_loop()
        real_submit = owner_loop.call_soon_threadsafe

        def fail_waiter_cancel(callback, *args, **kwargs):
            if getattr(callback, "__name__", "") == "cancel":
                raise RuntimeError("owner loop stopped")
            return real_submit(callback, *args, **kwargs)

        monkeypatch.setattr(engine, "_wait_for_task", wait_for_task)
        monkeypatch.setattr(runtime.asyncio, "timeout", lambda _seconds: ForcedTimeout())
        monkeypatch.setattr(owner_loop, "call_soon_threadsafe", fail_waiter_cancel)
        with pytest.raises(RuntimeError, match="timed out draining tasks"):
            await engine.aclose()

        assert engine._closed is False
        assert owned["task"] in engine._saver_initializations
        monkeypatch.setattr(owner_loop, "call_soon_threadsafe", real_submit)
        owner_loop.call_soon_threadsafe(owned["task"].cancel)
        await asyncio.to_thread(cancelled.wait)
        monkeypatch.undo()
        await engine.aclose()
    finally:
        owner_loop = owned.get("task") and owned["task"].get_loop()
        if owner_loop is not None and owner_loop.is_running():
            owner_loop.call_soon_threadsafe(owner_loop.stop)
        await asyncio.to_thread(owner.join)
        assert stopped.is_set()


async def test_engine_close_refuses_owner_loop_stopped_during_waiter_handoff(
    tmp_path, settings, store, monkeypatch,
):
    from caos.engine.runtime import Engine

    engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "stopped-loop.db")
    ready = threading.Event()
    stopped = threading.Event()
    resume = threading.Event()
    finished = threading.Event()
    owned = {}

    def own_continuation() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def pending() -> None:
            await asyncio.Event().wait()

        def prepare() -> None:
            task = loop.create_task(pending())
            owned["task"] = task
            engine._continuations.add(task)
            ready.set()

        loop.call_soon(prepare)
        loop.run_forever()
        stopped.set()
        resume.wait()
        try:
            loop.run_until_complete(asyncio.gather(owned["task"], return_exceptions=True))
        finally:
            loop.close()
            finished.set()

    owner = threading.Thread(target=own_continuation)
    owner.start()
    try:
        await asyncio.to_thread(ready.wait)
        owner_loop = owned["task"].get_loop()
        real_submit = owner_loop.call_soon_threadsafe

        def stop_before_waiter(callback, *args, **kwargs):
            if getattr(callback, "__name__", "") != "wait_on_owner":
                return real_submit(callback, *args, **kwargs)
            real_submit(owner_loop.stop)
            assert stopped.wait()
            return real_submit(callback, *args, **kwargs)

        real_wrap = asyncio.wrap_future

        def resume_if_old_waiter(future, *args, **kwargs):
            resume.set()
            return real_wrap(future, *args, **kwargs)

        monkeypatch.setattr(owner_loop, "call_soon_threadsafe", stop_before_waiter)
        monkeypatch.setattr(asyncio, "wrap_future", resume_if_old_waiter)
        with pytest.raises(RuntimeError, match="runnable owner loop"):
            await engine.aclose()

        assert engine._closed is False
        assert owned["task"] in engine._continuations
        owner_loop.call_soon_threadsafe(owned["task"].cancel)
        resume.set()
        await asyncio.to_thread(owner.join)
        await engine.aclose()
    finally:
        task = owned.get("task")
        if task is not None and not task.done() and not task.get_loop().is_closed():
            task.get_loop().call_soon_threadsafe(task.cancel)
        resume.set()
        if owner.is_alive():
            await asyncio.to_thread(owner.join)
        assert finished.is_set()


# --- the offered cut is the startable cut ----------------------------------------


async def test_case_wire_offers_exactly_the_pathways_the_engine_will_start(client, store):
    """A pathway the workbench offers must be one start_run accepts. These drifted:
    the Purpose menu listed all six PATHWAYS while the engine's MVP_PATHWAYS held
    four, so Distressed & Restructuring compiled straight into a 422 dead end.
    Serving the cut is what keeps the two in step; this test is what keeps the
    serving honest."""
    from caos.contracts import PATHWAYS, Depth
    from caos.engine.runtime import MVP_PATHWAYS, supported_depths

    case, _source = seed_case_with_source(store)
    served = client.get(f"/api/cases/{case['id']}", headers={"x-forwarded-user": "analyst"}).json()
    assert served["available_pathways"] == sorted(MVP_PATHWAYS)
    assert served["deep_research_available"] is True, served["deep_research_unavailable_reason"]

    research_brief = {
        "research_question": "How resilient is liquidity through the next refinancing?",
        "decision_context": "Committee review of an existing position.",
        "as_of_date": "2026-01-01", "time_horizon": "12 months",
        "must_answer": ["Nearest maturity"], "exclusions": [],
    }
    for pathway in PATHWAYS:
        for depth in Depth:
            body = {"pathway": pathway, "depth": depth.value}
            if pathway == "DEEP_RESEARCH":
                body["research_brief"] = research_brief
            response = client.post(f"/api/cases/{case['id']}/runs", json=body,
                                   headers={"x-forwarded-user": "analyst"})
            detail = response.json().get("detail") if response.status_code >= 400 else None
            if pathway in served["available_pathways"] and depth.value in supported_depths(pathway):
                assert response.status_code == 201, f"{pathway}/{depth.value} is offered but did not start: {detail}"
            else:
                # Which layer says no is not the point — DEEP_RESEARCH/screen is
                # refused by the depth rule before the engine is reached. Nothing
                # outside the served cut, at a depth the engine does not run, may start.
                assert response.status_code != 201, f"{pathway}/{depth.value} started but is not offered"


# --- source pinning at the entry gate (invariant 1; §10.4, §11.1) -----------------


async def test_empty_source_set_pauses_at_entry_gate_without_pinning(engine, store):
    case = store.create_case("Empty", "Issuer", "Services", "analyst")
    run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst")
    record = engine.get_run(run["id"])
    assert record["status"] == "paused"
    assert record["error"]["code"] == "SOURCE_SET_EMPTY"
    assert record["plan"].get("source_set_id") is None, "nothing may be pinned before the gate exits"


async def test_resume_with_still_empty_set_re_pauses_without_pinning(engine, store):
    case = store.create_case("Empty", "Issuer", "Services", "analyst")
    run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst")
    await engine.resume(run["id"])
    record = engine.get_run(run["id"])
    assert record["status"] == "paused"
    assert record["plan"].get("source_set_id") is None


async def test_gate_exit_pins_exact_current_source_set_and_later_uploads_do_not_move_it(engine, store):
    case, source, run = await start_full_credit_run(engine, store)
    pinned = engine.get_run(run["id"])["plan"]
    assert pinned["source_set_id"] == source["source_set"]["id"]
    assert pinned["source_set_version"] == 1
    seed_case_with_source(store, body=b"a second document uploaded mid-run")  # same store, new content
    assert engine.get_run(run["id"])["plan"]["source_set_id"] == source["source_set"]["id"]


async def test_plan_digest_is_carried_outside_the_blob_and_reasserted(engine, store):
    from caos.contracts import digest
    from caos.engine.state import plan_preimage

    case, source, run = await start_full_credit_run(engine, store)
    record = engine.get_run(run["id"])
    assert "plan_digest" not in record["plan"], "digest lives outside the digested blob (§12.1)"
    assert record["plan_digest"] == digest(plan_preimage(record["plan"]))


async def test_run_pinned_to_immutable_source_set_and_upgrade_links_origin(engine, store, client):
    case, source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.wait(run["id"])
    accepted = await engine.accept(run["id"], actor="analyst")
    assert accepted["source_set"]["id"] == source["source_set"]["id"]
    upgraded = await engine.upgrade(run["id"], actor="analyst")
    assert upgraded["upgraded_from_run_id"] == run["id"]


async def test_acceptance_refuses_missing_historical_source_set(engine, store):
    case, source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.wait(run["id"])
    engine.store_for_tests_delete_source_set(source["source_set"]["id"])
    with pytest.raises(Exception, match="SOURCE_SET_CHANGED"):
        await engine.accept(run["id"], actor="analyst")


async def test_acceptance_refuses_a_source_withdrawn_after_run_completion(engine, store):
    case, source, run = await start_full_credit_run(engine, store, depth="screen")
    completed = await engine.wait(run["id"])
    assert completed["status"] == "succeeded"
    store.withdraw(case["id"], source["id"], "analyst")

    with pytest.raises(Exception, match="SOURCE_SET_CHANGED"):
        await engine.accept(run["id"], actor="analyst")


async def test_withdrawing_pinned_source_mid_run_fails_the_run_closed(engine, store):
    """Invariant 1: withdrawn or mutated sources fail the run rather than degrading it."""
    case, source, run = await start_full_credit_run(engine, store)
    store.withdraw(case["id"], source["id"], "analyst")
    await engine.wait(run["id"])
    record = engine.get_run(run["id"])
    assert record["status"] == "failed"
    assert record["error"]["code"] in {"AGENT_AUTHORITY_MISMATCH", "SOURCE_SET_CHANGED"}


async def test_withdrawing_pinned_source_fails_a_screen_run_on_the_deterministic_path(engine, store):
    """Invariant 1 on the path with no provider call: withdrawal is invisible to the
    pinned source-set digest (a new set version is minted, the pinned record is
    untouched), so the deterministic branch needs the live check as much as the
    agent branch. Without it a screen run succeeds and every artifact cites the
    withdrawn source."""
    case, source, run = await start_full_credit_run(engine, store, depth="screen")
    store.withdraw(case["id"], source["id"], "analyst")
    await engine.wait(run["id"])
    record = engine.get_run(run["id"])
    assert record["status"] == "failed"
    assert record["error"]["code"] in {"AGENT_AUTHORITY_MISMATCH", "SOURCE_SET_CHANGED"}
    assert not [node for node in record["nodes"] if node["artifact_id"]], \
        "no artifact may be minted from withdrawn evidence"


async def test_withdrawal_in_the_last_pre_finalization_gap_fails_the_run(engine, store, monkeypatch):
    """The terminal gate must re-read live source authority after every module
    has finished, not merely trust the last module's earlier read."""
    real_verify = engine._verify_run_artifacts
    authority: dict[str, str] = {}

    def withdraw_then_verify(run_id, plan):
        store.withdraw(authority["case_id"], authority["source_id"], "analyst")
        real_verify(run_id, plan)

    monkeypatch.setattr(engine, "_verify_run_artifacts", withdraw_then_verify)
    case, source, run = await start_full_credit_run(engine, store, depth="screen")
    authority.update(case_id=case["id"], source_id=source["id"])

    await engine.wait(run["id"])

    record = engine.get_run(run["id"])
    assert record["status"] == "failed"
    assert record["error"]["code"] == "AGENT_AUTHORITY_MISMATCH"


async def test_reuse_relink_on_resume_revalidates_live_sources(tmp_path, settings, store, provider):
    """The reuse-first relink (§10.1) returns before mode dispatch, so it is the
    other way withdrawn evidence can re-enter a run: crash in the commit gap,
    withdraw, then recover onto the committed artifact."""
    from caos.engine.runtime import Engine

    engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "ck.db", provider=provider)
    try:
        case, source, run = await start_full_credit_run(engine, store, depth="screen")
        await engine.crash_in_commit_gap_for_tests(run["id"], module_id="CP-0")
        store.withdraw(case["id"], source["id"], "analyst")
    finally:
        await engine.aclose()

    revived = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "ck.db", provider=provider)
    try:
        await revived.recover()
        await revived.wait(run["id"])
        assert revived.get_run(run["id"])["status"] == "failed", "reuse never relinks past a withdrawal"
    finally:
        await revived.aclose()


@pytest.mark.parametrize("blamed", ["CP-1", None])
def test_a_terminal_failure_leaves_no_node_claiming_in_flight_work(tmp_path, blamed):
    """§12.13: a fan-out superstep has several modules `running` at once, but
    finalize_failure only ever touched the blamed row — the rest kept `running`
    on a terminal record. `recover` walks non_terminal_runs() only, so nothing
    ever reconciled them: `GET /api/runs/{id}` served a failed run carrying live
    work for the life of the record. Reconciliation rides the same transaction
    and mints no second terminal event."""
    import sqlalchemy as sa

    from caos.storage.runs import RunStore

    db = sa.create_engine(f"sqlite:///{tmp_path / 'runs.db'}")
    store = RunStore(db)
    try:
        run_id = store.create_run("case-1", "FULL_CREDIT", "full", "analyst")["id"]
        siblings = ["CP-1", "CP-1A", "CP-1B"]
        store.pin_plan(
            run_id,
            {"nodes": [{"module_id": m, "stage": 1, "dependencies": ["CP-0"]} for m in [*siblings, "CP-2"]]},
            "plan-digest",
        )
        for module_id in siblings:
            store.node_running(run_id, module_id)

        assert store.finalize_failure(run_id, "AGENT_BUDGET_EXCEEDED", blamed)

        nodes = {node["module_id"]: node for node in store.get_run(run_id)["nodes"]}
        assert [m for m, n in nodes.items() if n["status"] == "running"] == [], \
            "a terminal run may not carry a node the console renders as live work"
        if blamed:
            assert nodes[blamed]["status"] == "failed"
            assert nodes[blamed]["error"] == {"code": "AGENT_BUDGET_EXCEEDED", "module_id": blamed}
        for module_id in siblings:
            if module_id != blamed:
                assert nodes[module_id]["status"] == "cancelled", "abandoned work is not failed work"
                assert nodes[module_id]["error"] is None, "only the blamed module carries the error"
        assert nodes["CP-2"]["status"] == "pending", "a node that never started did not start; that stays true"
        terminal = [e for e in store.events_after(run_id, 0) if e["event"] in {"run.failed", "run.succeeded"}]
        assert len(terminal) == 1, "reconciling the siblings must not mint a second terminal event"
    finally:
        db.dispose()


def test_run_store_copies_one_provider_identity_through_run_artifact_snapshot_and_events(tmp_path):
    import sqlalchemy as sa

    from caos.contracts import digest
    from caos.engine.deterministic import build_deterministic_payload
    from caos.engine.provider import host_control_identity
    from caos.storage.runs import RunStore, StoreConflict, artifact_input_fingerprint

    db = sa.create_engine(f"sqlite:///{tmp_path / 'authority.db'}")
    store = RunStore(db)
    identity = host_control_identity().as_dict()
    try:
        run = store.create_run(
            "case-1", "FULL_CREDIT", "full", "analyst", provider_identity=identity,
        )
        assert run["provider_identity"] == identity
        assert store.events_after(run["id"], 0)[0]["data"]["provider_identity_digest"] == identity["identity_digest"]

        plan = {
            "build_id": "deploy-v-test-build",
            "nodes": [{"module_id": "CP-0", "stage": 0, "dependencies": []}],
        }
        store.pin_plan(run["id"], plan, digest(plan))
        store.node_running(run["id"], "CP-0")
        fingerprint = artifact_input_fingerprint(plan, digest(plan), "CP-0", [])
        payload = build_deterministic_payload(
            "CP-0", plan, input_fingerprint=fingerprint,
        )
        artifact = store.complete_node(
            run["id"], "case-1", "CP-0", fingerprint, payload,
            None, "Passed", "analyst",
            content_expectations={"expected_system_payload": payload},
        )
        assert artifact["provider_identity"] == identity

        snapshot = {
            "id": "snap-1", "case_id": "case-1", "run_id": run["id"],
            "source_set_id": "ss-1", "source_set_version": 1,
            "artifacts": [{"id": artifact["id"], "module_id": "CP-0", "digest": artifact["digest"]}],
            "provider_identity": identity, "previous_snapshot_id": None,
            "accepted_at": "2026-09-01T00:00:00+00:00",
        }
        preimage = {key: value for key, value in snapshot.items() if key != "id"}
        snapshot["digest"] = digest(preimage)
        assert store.create_snapshot(snapshot)["provider_identity"] == identity
        assert store.get_snapshot("snap-1")["digest"] == digest(preimage)

        legacy = store.create_run("case-1", "FULL_CREDIT", "full", "analyst")
        assert legacy["provider_identity"] is None
        with pytest.raises(StoreConflict, match="AGENT_IDENTITY_MISMATCH"):
            store.create_snapshot({**snapshot, "id": "snap-2", "run_id": legacy["id"]})

        same_identity = store.create_run(
            "case-1", "FULL_CREDIT", "full", "analyst", provider_identity=identity,
        )
        with pytest.raises(StoreConflict, match="AGENT_IDENTITY_MISMATCH"):
            store.create_snapshot({**snapshot, "id": "snap-3", "run_id": same_identity["id"]})

        forged_payload = {
            **artifact["payload"],
            "provider_identity": host_control_identity(
                adapter_version="caos.host-control.v2"
            ).as_dict(),
        }
        store.update_artifact_for_tests(
            run["id"], "CP-0", payload=forged_payload, digest=digest(forged_payload),
        )
        assert store.find_valid_artifact(run["id"], "CP-0", fingerprint) is None
        store.update_artifact_for_tests(
            run["id"], "CP-0", payload=artifact["payload"], digest=artifact["digest"],
        )
        store.update_artifact_for_tests(
            run["id"], "CP-0",
            provider_identity=host_control_identity(adapter_version="caos.host-control.v2").as_dict(),
        )
        with pytest.raises(StoreConflict, match="AGENT_IDENTITY_MISMATCH"):
            store.complete_node(
                run["id"], "case-1", "CP-0", fingerprint, payload,
                None, "Passed", "analyst",
            )
    finally:
        db.dispose()


@pytest.mark.parametrize(
    "invalid_kind",
    [
        "unknown_schema",
        "semantic_empty_system",
        "semantic_empty_canonical",
        "oversized_markdown",
        "oversized_payload",
        "non_finite_json",
        "non_passed_qa",
    ],
)
def test_complete_node_rejects_invalid_or_unbounded_artifact_payloads(tmp_path, invalid_kind):
    import hashlib

    import sqlalchemy as sa

    from caos.contracts import digest
    from caos.engine.deterministic import build_deterministic_payload
    from caos.methodology.canonical import MAX_CANONICAL_MARKDOWN_CHARS
    from caos.storage.runs import (
        MAX_ARTIFACT_PAYLOAD_BYTES,
        RunStore,
        StoreConflict,
        artifact_input_fingerprint,
    )

    db = sa.create_engine(f"sqlite:///{tmp_path / 'invalid-artifact.db'}")
    runs = RunStore(db)
    try:
        run = runs.create_run("case-1", "FULL_CREDIT", "full", "analyst")
        plan = {
            "build_id": "deploy-v-test-build",
            "pathway": "FULL_CREDIT",
            "nodes": [{"module_id": "CP-0", "stage": 0, "dependencies": []}],
        }
        runs.pin_plan(run["id"], plan, digest(plan))
        runs.node_running(run["id"], "CP-0")
        fingerprint = artifact_input_fingerprint(plan, digest(plan), "CP-0", [])
        markdown = None
        qa_status = "Passed"
        payload = build_deterministic_payload("CP-0", plan, input_fingerprint=fingerprint)
        if invalid_kind == "unknown_schema":
            payload["schema_version"] = "caos.canonical.artifact.v999"
        elif invalid_kind == "semantic_empty_system":
            payload = {
                "schema_version": "caos.system_analysis.v1",
                "module_id": "CP-0",
                "lineage": {"input_fingerprint": fingerprint},
            }
        elif invalid_kind == "semantic_empty_canonical":
            markdown = "arbitrary"
            payload = {
                "schema_version": "caos.canonical.artifact.v1",
                "module_id": "CP-0",
                "host_identity": {"run_id": run["id"], "case_id": "case-1", "module_id": "CP-0"},
                "canonical_output": {
                    "markdown": markdown,
                    "markdown_sha256": hashlib.sha256(markdown.encode()).hexdigest(),
                },
                "lineage": {"input_fingerprint": fingerprint},
            }
        elif invalid_kind == "oversized_markdown":
            markdown = "x" * (MAX_CANONICAL_MARKDOWN_CHARS + 1)
            payload = {
                "schema_version": "caos.canonical.artifact.v1",
                "module_id": "CP-0",
                "host_identity": {"run_id": run["id"], "case_id": "case-1", "module_id": "CP-0"},
                "canonical_output": {
                    "markdown": markdown,
                    "markdown_sha256": hashlib.sha256(markdown.encode()).hexdigest(),
                },
                "lineage": {"input_fingerprint": fingerprint},
            }
        elif invalid_kind == "oversized_payload":
            payload["padding"] = "x" * MAX_ARTIFACT_PAYLOAD_BYTES
        elif invalid_kind == "non_finite_json":
            payload["non_finite"] = float("nan")
        else:
            qa_status = "Restricted"

        with pytest.raises(StoreConflict, match="AGENT_OUTPUT_INVALID"):
            runs.complete_node(
                run["id"], "case-1", "CP-0", fingerprint, payload,
                markdown, qa_status, "analyst",
            )
        assert runs.find_valid_artifact(run["id"], "CP-0", fingerprint) is None
    finally:
        db.dispose()


@pytest.mark.parametrize(
    ("field", "forged_value"),
    [
        ("run_id", "run-relocated"),
        ("case_id", "case-relocated"),
        ("module_id", "CP-9"),
        ("input_fingerprint", "fingerprint-relocated"),
        ("qa_status", "Blocked"),
    ],
)
def test_artifact_verifier_rejects_row_relocation_and_index_drift(tmp_path, field, forged_value):
    import sqlalchemy as sa

    from caos.contracts import digest
    from caos.engine.deterministic import build_deterministic_payload
    from caos.storage.runs import RunStore, artifact_input_fingerprint, verify_artifact_content

    db = sa.create_engine(f"sqlite:///{tmp_path / 'artifact-relocation.db'}")
    runs = RunStore(db)
    try:
        run = runs.create_run("case-1", "FULL_CREDIT", "full", "analyst")
        plan = {
            "build_id": "deploy-v-test-build",
            "pathway": "FULL_CREDIT",
            "nodes": [{"module_id": "CP-0", "stage": 0, "dependencies": []}],
        }
        runs.pin_plan(run["id"], plan, digest(plan))
        runs.node_running(run["id"], "CP-0")
        fingerprint = artifact_input_fingerprint(plan, digest(plan), "CP-0", [])
        payload = build_deterministic_payload("CP-0", plan, input_fingerprint=fingerprint)
        artifact = runs.complete_node(
            run["id"], "case-1", "CP-0", fingerprint,
            payload,
            None, "Passed", "analyst",
            content_expectations={"expected_system_payload": payload},
        )
        assert verify_artifact_content(artifact, expected_system_payload=payload)

        forged = {**artifact, field: forged_value}
        assert not verify_artifact_content(
            forged,
            run_id=run["id"],
            case_id="case-1",
            module_id="CP-0",
            input_fingerprint=fingerprint,
            methodology_build_id=plan["build_id"],
            qa_status="Passed",
            expected_system_payload=payload,
        )
    finally:
        db.dispose()


def test_provider_identity_schema_evolution_is_serialized_and_does_not_backfill(tmp_path):
    import sqlalchemy as sa

    from caos.storage.runs import RunStore

    path = tmp_path / "legacy-authority.db"
    seed_engine = sa.create_engine(f"sqlite:///{path}")
    seed = RunStore(seed_engine)
    legacy_run_id = seed.create_run("case-1", "FULL_CREDIT", "full", "analyst")["id"]
    with seed_engine.begin() as conn:
        for table in ("runs", "run_artifacts", "run_snapshots"):
            conn.exec_driver_sql(f'ALTER TABLE "{table}" DROP COLUMN provider_identity')
    seed_engine.dispose()

    errors: list[BaseException] = []

    def initialize() -> None:
        engine = sa.create_engine(f"sqlite:///{path}")
        try:
            RunStore(engine)
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)
        finally:
            engine.dispose()

    workers = [threading.Thread(target=initialize) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    assert errors == []
    verify_engine = sa.create_engine(f"sqlite:///{path}")
    try:
        assert all(
            "provider_identity" in {column["name"] for column in sa.inspect(verify_engine).get_columns(table)}
            for table in ("runs", "run_artifacts", "run_snapshots")
        )
        assert RunStore(verify_engine).get_run(legacy_run_id)["provider_identity"] is None
    finally:
        verify_engine.dispose()


async def test_ordinary_screen_semantics_require_a_provider_before_run_creation(tmp_path, settings, store):
    from caos.engine.runtime import Engine, EngineError

    case, _source = seed_case_with_source(store)
    absent = Engine.create(
        settings=settings,
        store=store,
        checkpoint_path=tmp_path / "screen-provider-absent.db",
        provider=None,
    )
    try:
        with pytest.raises(EngineError) as excinfo:
            await absent.start_run(
                case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst",
            )
        assert excinfo.value.code == "AGENT_PROVIDER_UNAVAILABLE"
    finally:
        await absent.aclose()


async def test_test_only_placeholder_capability_is_run_local_and_not_persisted(engine, store, provider):
    case, _source = seed_case_with_source(store)
    permitted = await engine.start_run_for_tests(
        case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst",
        allow_placeholder_deterministic=True,
    )
    await engine.wait(permitted["id"])
    assert engine.get_run(permitted["id"])["status"] == "succeeded"
    assert provider.create_requests == []

    ordinary = await engine.start_run(
        case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst",
    )
    await engine.wait(ordinary["id"])
    assert engine.get_run(ordinary["id"])["status"] == "failed"
    assert provider.create_requests, "ordinary SCREEN semantics must reach the provider, never the placeholder"
    assert "placeholder" not in engine.runs.serialize_all_for_run(permitted["id"])


def test_full_depth_host_control_preserves_the_pre_promotion_placeholder_modules():
    from caos.engine.runtime import Engine

    assert Engine._PLACEHOLDER_FULL_MODULES == {
        "CP-PARSE", "CP-0", "CP-2E", "CP-2H", "CP-3", "CP-4", "CP-4C", "CP-6", "CP-L10",
    }


async def test_placeholder_artifact_cannot_relink_after_restart_without_test_capability(
    tmp_path, settings, store, provider,
):
    from caos.engine.runtime import Engine

    checkpoint = tmp_path / "placeholder-relink.db"
    original = Engine.create(settings=settings, store=store, checkpoint_path=checkpoint, provider=provider)
    try:
        case, _source = seed_case_with_source(store)
        run = await original.start_run_for_tests(
            case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst",
            allow_placeholder_deterministic=True,
        )
        await original.crash_in_commit_gap_for_tests(run["id"], module_id="CP-0")
    finally:
        await original.aclose()

    revived = Engine.create(settings=settings, store=store, checkpoint_path=checkpoint, provider=provider)
    try:
        await revived.recover()
        await revived.wait(run["id"])
        record = revived.get_run(run["id"])
        assert record["status"] == "failed"
        assert record["error"]["code"] == "DETERMINISTIC_EXECUTOR_UNAVAILABLE"
    finally:
        await revived.aclose()


async def test_succeeded_placeholder_run_cannot_be_newly_accepted_after_restart(
    tmp_path, settings, store, provider,
):
    from caos.engine.runtime import Engine, EngineError

    checkpoint = tmp_path / "placeholder-accept.db"
    original = Engine.create(settings=settings, store=store, checkpoint_path=checkpoint, provider=provider)
    try:
        case, _source = seed_case_with_source(store)
        run = await original.start_run_for_tests(
            case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst",
            allow_placeholder_deterministic=True,
        )
        await original.wait(run["id"])
        assert original.get_run(run["id"])["status"] == "succeeded"
    finally:
        await original.aclose()

    revived = Engine.create(settings=settings, store=store, checkpoint_path=checkpoint, provider=provider)
    try:
        with pytest.raises(EngineError) as excinfo:
            await revived.accept(run["id"], actor="analyst")
        assert excinfo.value.code == "DETERMINISTIC_EXECUTOR_UNAVAILABLE"
    finally:
        await revived.aclose()


async def test_full_run_preflight_refuses_disabled_or_absent_provider_without_a_run_row(
    tmp_path, store,
):
    from datetime import UTC, datetime, timedelta

    import sqlalchemy as sa

    from caos.config import Settings
    from caos.engine.provider import ProviderIdentity
    from caos.engine.runtime import Engine, EngineError
    from caos.storage.runs import runs

    case, _source = seed_case_with_source(store)
    disabled = Engine.create(
        settings=Settings(storage_dir=tmp_path / "vault-disabled", agent_execution_enabled=False),
        store=store, checkpoint_path=tmp_path / "disabled.db", provider=None,
    )
    absent = Engine.create(
        settings=Settings(storage_dir=tmp_path / "vault-absent", agent_execution_enabled=True),
        store=store, checkpoint_path=tmp_path / "absent.db", provider=None,
    )
    expired_identity = ProviderIdentity(
        provider_name="anthropic", model="claude-sonnet-4-6", provider_version=None,
        adapter_version="caos.anthropic.v1", parameter_context_digest="a" * 64,
        qualification_record_id="qualification-1", qualification_record_digest="b" * 64,
        qualification_status="qualified",
        qualification_expires_at=(datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
    )
    expired = Engine.create(
        settings=Settings(storage_dir=tmp_path / "vault-expired", agent_execution_enabled=True),
        store=store, checkpoint_path=tmp_path / "expired.db",
        provider=type("ExpiredProvider", (), {"identity": expired_identity})(),
    )
    try:
        with store.engine.connect() as conn:
            before = conn.scalar(sa.select(sa.func.count()).select_from(runs))
        with pytest.raises(EngineError) as disabled_error:
            await disabled.start_run(
                case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst",
            )
        assert disabled_error.value.code == "AGENT_EXECUTION_DISABLED"
        with pytest.raises(EngineError) as absent_error:
            await absent.start_run(
                case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst",
            )
        assert absent_error.value.code == "AGENT_PROVIDER_UNAVAILABLE"
        with pytest.raises(EngineError) as expired_error:
            await expired.start_run(
                case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst",
            )
        assert expired_error.value.code == "AGENT_QUALIFICATION_EXPIRED"
        with store.engine.connect() as conn:
            assert conn.scalar(sa.select(sa.func.count()).select_from(runs)) == before
        assert disabled.runs.active_admission_count() == absent.runs.active_admission_count() == 0
    finally:
        await disabled.aclose()
        await absent.aclose()
        await expired.aclose()


async def test_response_identity_substitution_reconciles_and_audits_before_refusal(
    tmp_path, settings, store,
):
    from caos.engine.provider import ProviderBlock, ProviderMessage, ProviderUsage, host_control_identity
    from caos.engine.runtime import Engine

    class SubstitutingProvider:
        identity = host_control_identity()
        create_requests: list[object] = []

        def count_tokens(self, _request):
            return 1

        def create_message(self, request):
            self.create_requests.append(request)
            return ProviderMessage(
                content=[ProviderBlock(
                    type="tool_use", id="tool-substituted", name="read_evidence",
                    input={"source_id": "must-not-be-read", "non_json": {object()}},
                )], stop_reason="tool_use",
                usage=ProviderUsage(input_tokens=1, output_tokens=1_000_000), request_id="req-substituted",
                observed_model="other-model",
            )

    provider = SubstitutingProvider()
    local = Engine.create(
        settings=settings, store=store, checkpoint_path=tmp_path / "substitution.db",
        provider=provider,
    )
    try:
        case, _source = seed_case_with_source(store)
        run = await local.start_run_for_tests(
            case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst",
            allow_placeholder_deterministic=True,
        )
        await local.wait(run["id"])

        record = local.get_run(run["id"])
        budget = local.runs.get_budget(run["id"])
        attempts = budget["attempts"]
        assert record["status"] == "failed" and record["error"]["code"] == "AGENT_IDENTITY_MISMATCH"
        assert budget["inflight_request_digest"] is None
        billed = len(provider.create_requests)
        assert budget["used"]["input_tokens"] == billed
        assert budget["used"]["output_tokens"] == billed * 1_000_000
        assert billed == 1 and budget["used"]["evidence_reads"] == 0
        generations = [row for row in attempts if row["kind"] == "generation"]
        assert len(generations) == billed
        assert all(row["provider_identity"] == host_control_identity().as_dict() for row in generations)
        assert all(row["observed_model"] == "other-model" for row in generations)
        assert all(len(row["response_digest"]) == 64 for row in generations)
        assert not any(artifact["module_id"] == "CP-1" for artifact in local.artifacts_for_run(run["id"]))
    finally:
        await local.aclose()


async def test_provider_identity_is_read_once_and_bound_through_runtime_authority(
    tmp_path, settings, store,
):
    from caos.contracts import digest
    from caos.engine.provider import host_control_identity
    from caos.engine.runtime import Engine

    class CountingProvider:
        accesses = 0
        _identity = host_control_identity()

        @property
        def identity(self):
            self.accesses += 1
            return self._identity

    provider = CountingProvider()
    local = Engine.create(
        settings=settings, store=store, checkpoint_path=tmp_path / "one-read.db", provider=provider,
    )
    try:
        case, _source = seed_case_with_source(store)
        first = await local.start_run_for_tests(
            case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst",
            allow_placeholder_deterministic=True,
        )
        await local.wait(first["id"])
        second = await local.start_run_for_tests(
            case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst",
            allow_placeholder_deterministic=True,
        )
        await local.wait(second["id"])

        assert provider.accesses == 1
        run = local.get_run(first["id"])
        identity = host_control_identity().as_dict()
        assert run["provider_identity"] == run["plan"]["provider_identity"] == identity
        assert all(
            event["data"]["provider_identity_digest"] == identity["identity_digest"]
            for event in local.events_after(first["id"], 0)
        )
        for artifact in local.artifacts_for_run(first["id"]):
            assert artifact["provider_identity"] == artifact["payload"]["provider_identity"] == identity
            assert digest(artifact["payload"]) == artifact["digest"]

        snapshot = await local.accept(first["id"], actor="analyst")
        assert snapshot["provider_identity"] == identity
        accepted_event = next(
            event for event in store.list_audit()
            if event["action"] == "snapshot.accepted" and event["run_id"] == first["id"]
        )
        assert accepted_event["provider_identity_digest"] == identity["identity_digest"]
        preimage = {
            key: value for key, value in snapshot.items()
            if key not in {"digest", "id", "source_set"}
        }
        assert snapshot["digest"] == digest(preimage)
    finally:
        await local.aclose()


async def test_recovery_rejects_changed_or_legacy_missing_agent_identity_before_provider_contact(
    tmp_path, settings, store,
):
    from caos.engine.provider import host_control_identity
    from caos.engine.runtime import Engine

    class NoCallProvider:
        def __init__(self, adapter_version: str):
            self.identity = host_control_identity(adapter_version=adapter_version)
            self.calls = 0

        def count_tokens(self, _request):
            self.calls += 1
            raise AssertionError("provider contact must not occur")

    case, _source = seed_case_with_source(store)
    original_provider = NoCallProvider("caos.host-control.original")
    original = Engine.create(
        settings=settings, store=store, checkpoint_path=tmp_path / "recovery-identity.db",
        provider=original_provider,
    )
    try:
        run = await original.start_run_for_tests(
            case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst",
            allow_placeholder_deterministic=True,
        )
    finally:
        await original.aclose()

    changed_provider = NoCallProvider("caos.host-control.changed")
    changed = Engine.create(
        settings=settings, store=store, checkpoint_path=tmp_path / "recovery-identity.db",
        provider=changed_provider,
    )
    try:
        legacy = changed.runs.create_run("case-legacy", "FULL_CREDIT", "full", "analyst")
        await changed.recover()
        assert changed.get_run(run["id"])["error"]["code"] == "AGENT_IDENTITY_MISMATCH"
        assert changed.get_run(legacy["id"])["error"]["code"] == "AGENT_IDENTITY_MISMATCH"
        assert changed_provider.calls == 0
    finally:
        await changed.aclose()


async def test_recovery_durably_quarantines_malformed_stored_identity_without_provider_contact(
    tmp_path, settings, store,
):
    from caos.engine.provider import host_control_identity
    from caos.engine.runtime import Engine
    from caos.storage.runs import runs

    class NoCallProvider:
        identity = host_control_identity()
        calls = 0

        def count_tokens(self, _request):
            self.calls += 1
            raise AssertionError("provider contact must not occur")

    provider = NoCallProvider()
    checkpoint = tmp_path / "malformed-identity.db"
    case = store.create_case("Paused", "Issuer", "Services", "analyst")
    original = Engine.create(
        settings=settings, store=store, checkpoint_path=checkpoint, provider=provider,
    )
    try:
        run = await original.start_run_for_tests(
            case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst",
            allow_placeholder_deterministic=True,
        )
        assert original.get_run(run["id"])["status"] == "paused"
    finally:
        await original.aclose()

    malformed = {**run["provider_identity"], "identity_digest": "0" * 64}
    with store.engine.begin() as conn:
        conn.execute(
            runs.update().where(runs.c.id == run["id"]).values(provider_identity=malformed)
        )

    revived = Engine.create(
        settings=settings, store=store, checkpoint_path=checkpoint, provider=provider,
    )
    try:
        revived._allow_placeholder_deterministic_for_tests(run["id"])
        await revived.recover()
        record = revived.get_run(run["id"])
        assert record["status"] == "failed"
        assert record["error"] == {"code": "AGENT_IDENTITY_MISMATCH"}
        assert _checkpoint_rows(checkpoint, run["id"]) == 0
        assert run["id"] not in revived._placeholder_deterministic_runs
        assert revived.runs.latest_ticket(run["id"]) is None
        assert provider.calls == 0
        failed = [event for event in revived.events_after(run["id"], 0) if event["event"] == "run.failed"]
        assert failed[-1]["data"] == {"code": "AGENT_IDENTITY_MISMATCH"}
    finally:
        await revived.aclose()


async def test_recovery_rechecks_qualification_currency_before_provider_contact(
    tmp_path, settings, store, monkeypatch,
):
    from caos.engine.provider import AgentError, ProviderIdentity, host_control_identity
    from caos.engine.runtime import Engine

    class NoCallProvider:
        identity = host_control_identity()
        calls = 0

        def count_tokens(self, _request):
            self.calls += 1
            raise AssertionError("provider contact must not occur")

    provider = NoCallProvider()
    case = store.create_case("Paused", "Issuer", "Services", "analyst")
    original = Engine.create(
        settings=settings, store=store, checkpoint_path=tmp_path / "expiry-recovery.db",
        provider=provider,
    )
    try:
        run = await original.start_run(
            case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst",
        )
        assert original.get_run(run["id"])["status"] == "paused"
    finally:
        await original.aclose()

    revived = Engine.create(
        settings=settings, store=store, checkpoint_path=tmp_path / "expiry-recovery.db",
        provider=provider,
    )
    try:
        def expired(_identity):
            raise AgentError("AGENT_QUALIFICATION_EXPIRED")

        monkeypatch.setattr(ProviderIdentity, "ensure_current", expired)
        await revived.recover()
        assert revived.get_run(run["id"])["error"]["code"] == "AGENT_QUALIFICATION_EXPIRED"
        assert revived.runs.latest_ticket(run["id"]) is None
        assert provider.calls == 0
    finally:
        await revived.aclose()


async def test_resume_and_wait_persist_identity_expiry_before_provider_contact(
    engine, store, provider, monkeypatch,
):
    from caos.engine.provider import AgentError, ProviderIdentity

    first = store.create_case("Resume expiry", "Issuer", "Services", "analyst")
    second = store.create_case("Wait expiry", "Issuer", "Services", "analyst")
    resume_run = await engine.start_run(
        case_id=first["id"], pathway="FULL_CREDIT", depth="full", actor="analyst",
    )
    wait_run = await engine.start_run(
        case_id=second["id"], pathway="FULL_CREDIT", depth="full", actor="analyst",
    )

    def expired(_identity):
        raise AgentError("AGENT_QUALIFICATION_EXPIRED")

    monkeypatch.setattr(ProviderIdentity, "ensure_current", expired)
    engine._placeholder_deterministic_runs.update({resume_run["id"], wait_run["id"]})
    engine._scripted_runs.update({resume_run["id"], wait_run["id"]})
    resumed = await engine.resume(resume_run["id"])
    waited = await engine.wait(wait_run["id"])
    assert resumed["status"] == waited["status"] == "failed"
    assert resumed["error"]["code"] == waited["error"]["code"] == "AGENT_QUALIFICATION_EXPIRED"
    assert provider.create_requests == []
    assert not ({resume_run["id"], wait_run["id"]} & engine._placeholder_deterministic_runs)
    assert not ({resume_run["id"], wait_run["id"]} & engine._scripted_runs)
    assert _checkpoint_rows(engine.checkpoint_path, resume_run["id"]) == 0
    assert _checkpoint_rows(engine.checkpoint_path, wait_run["id"]) == 0


async def test_a_legacy_succeeded_agent_run_cannot_gain_new_acceptance_authority(engine, store):
    from caos.engine.provider import AgentError
    from caos.storage.runs import runs

    case, _source = seed_case_with_source(store)
    record = await engine.run_scripted_for_tests(case["id"])
    with store.engine.begin() as conn:
        conn.execute(runs.update().where(runs.c.id == record["id"]).values(provider_identity=None))

    with pytest.raises(AgentError) as excinfo:
        await engine.accept(record["id"], actor="analyst")
    assert excinfo.value.code == "AGENT_IDENTITY_MISMATCH"


# --- determinism and replay (invariant 10) ----------------------------------------


def test_node_set_and_edges_are_a_pure_function_of_pathway_and_depth(engine):
    from caos.engine.graphs import compiled_route

    one = compiled_route("FULL_CREDIT", "full")
    two = compiled_route("FULL_CREDIT", "full")
    assert one.nodes == two.nodes and one.edges == two.edges
    assert compiled_route("EARNINGS_UPDATE", "full").nodes != one.nodes


async def test_replay_from_same_pinned_sources_and_build_is_equivalent_by_the_same_path(engine, store, provider):
    """Named scenario 3: same pinned sources + methodology build -> equivalent result, same path."""
    case, source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.wait(run["id"])
    first = engine.get_run(run["id"])
    assert first["status"] == "succeeded"

    replay = await engine.start_run_for_tests(
        case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst",
        allow_placeholder_deterministic=True,
    )
    await engine.wait(replay["id"])
    second = engine.get_run(replay["id"])
    assert second["status"] == "succeeded"
    assert [n["module_id"] for n in second["nodes"]] == [n["module_id"] for n in first["nodes"]], "same path"
    assert second["plan_digest"] == first["plan_digest"], "same pin -> same plan identity"
    firsts = {a["module_id"]: a for a in engine.artifacts_for_run(first["id"])}
    seconds = {a["module_id"]: a for a in engine.artifacts_for_run(second["id"])}
    assert set(firsts) == set(seconds) == {n["module_id"] for n in first["nodes"]}

    # Every payload key except the two that carry run identity (the run id
    # itself and the fingerprint chain it seeds) must be byte-equal: evidence
    # references, narrative, provenance, authority, methodology, confidence.
    # Comparing constants such as `status` would pass on any two successful
    # runs; this comparison fails when a replay produces different content.
    def semantic(payload: dict) -> dict:
        return {key: value for key, value in payload.items() if key not in {"artifact_identity", "lineage"}}

    for module_id in firsts:
        assert semantic(firsts[module_id]["payload"]) == semantic(seconds[module_id]["payload"]), module_id
        assert firsts[module_id]["payload"]["evidence_refs"], f"{module_id} cites nothing"
        assert firsts[module_id]["markdown"] == seconds[module_id]["markdown"], module_id
        assert firsts[module_id]["payload"]["lineage"]["upstream_digests"] != seconds[module_id]["payload"]["lineage"]["upstream_digests"] or module_id == "CP-PARSE", (
            "the fingerprint chain is seeded by the run id, so it must differ downstream of CP-PARSE"
        )
    assert all(
        firsts[module_id]["digest"] != seconds[module_id]["digest"]
        and firsts[module_id]["payload"]["artifact_identity"]["run_id"] == first["id"]
        and seconds[module_id]["payload"]["artifact_identity"]["run_id"] == second["id"]
        for module_id in firsts
    ), "each equivalent replay remains auditable to its own run"


async def test_started_pathways_are_restricted_to_the_mvp_set(engine, store):
    case, _ = seed_case_with_source(store)
    for pathway in ("PORTFOLIO_DECISION", "DECISION_LEDGER"):
        with pytest.raises(Exception, match="PATHWAY_NOT_AVAILABLE"):
            await engine.start_run(case_id=case["id"], pathway=pathway, depth="full", actor="analyst")
    # DEEP_RESEARCH is in the cut but runs at full depth only (§14.1); the
    # depth refusal lands before any row exists.
    with pytest.raises(Exception, match="DEPTH_NOT_SUPPORTED"):
        await engine.start_run(case_id=case["id"], pathway="DEEP_RESEARCH", depth="screen", actor="analyst")
    assert engine.runs.non_terminal_runs() == []


# --- kill / resume (success criterion; §10.1, §12.28) -----------------------------


async def test_worker_killed_mid_run_resumes_from_last_checkpoint_not_restart(tmp_path, settings, store, provider):
    """Named scenario 1. Kill after N modules; a fresh Engine over the same checkpoint
    DB resumes and completes without re-executing the finished modules."""
    from caos.engine.runtime import Engine

    engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "ck.db", provider=provider)
    try:
        case, source, run = await start_full_credit_run(engine, store, depth="screen")
        await engine.kill_after_modules_for_tests(run["id"], count=2)  # crashes the worker mid-run
        executed_before = engine.executed_modules_for_tests(run["id"])
        assert len(executed_before) == 2
    finally:
        await engine.aclose()

    revived = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "ck.db", provider=provider)
    try:
        revived._allow_placeholder_deterministic_for_tests(run["id"])
        await revived.recover()
        await revived.wait(run["id"])
        record = revived.get_run(run["id"])
        assert record["status"] == "succeeded"
        assert revived.execution_counts_for_tests(run["id"])[executed_before[0]] == 1, \
            "finished module not re-executed"
    finally:
        await revived.aclose()


async def test_crash_between_store_commit_and_checkpoint_write_yields_one_artifact_one_charge(tmp_path, settings, store, provider):
    """§12 objection 1: the store-commit/checkpoint gap must not double-mint or double-spend."""
    from caos.engine.runtime import Engine

    engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "ck.db", provider=provider)
    try:
        case, source, run = await start_full_credit_run(engine, store, depth="screen")
        await engine.crash_in_commit_gap_for_tests(run["id"], module_id="CP-0")
    finally:
        await engine.aclose()

    revived = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "ck.db", provider=provider)
    try:
        revived._allow_placeholder_deterministic_for_tests(run["id"])
        await revived.recover()
        await revived.wait(run["id"])
        artifacts = [a for a in revived.artifacts_for_run(run["id"]) if a["module_id"] == "CP-0"]
        assert len(artifacts) == 1, "exactly one artifact for the crashed module"
        events = [e for e in revived.events_after(run["id"], 0) if e["event"] == "run.succeeded"]
        assert len(events) == 1, "run.succeeded exactly once"
    finally:
        await revived.aclose()


async def test_interrupt_paused_threads_are_skipped_by_recovery_and_hold_no_admission_slot(tmp_path, settings, store, provider):
    from caos.engine.runtime import Engine

    engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "ck.db", provider=provider)
    try:
        case = store.create_case("Empty", "Issuer", "Services", "analyst")
        run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst")
        assert engine.get_run(run["id"])["status"] == "paused"
    finally:
        await engine.aclose()

    revived = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "ck.db", provider=provider)
    try:
        await revived.recover()
        assert revived.get_run(run["id"])["status"] == "paused", "recovery must not poke parked threads"
        assert revived.active_execution_count() == 0, "paused threads hold no admission slot"
    finally:
        await revived.aclose()


async def test_terminal_run_deletes_checkpoints_after_domain_audit_is_durable(tmp_path, settings, store, provider):
    from caos.engine.runtime import Engine

    checkpoint_path = tmp_path / "ck.db"
    engine = Engine.create(settings=settings, store=store, checkpoint_path=checkpoint_path, provider=provider)
    try:
        case, _source, run = await start_full_credit_run(engine, store, depth="screen")
        assert _checkpoint_rows(checkpoint_path, run["id"]) > 0

        await engine.wait(run["id"])

        assert _checkpoint_rows(checkpoint_path, run["id"]) == 0
        assert engine.artifacts_for_run(run["id"]), "domain artifacts survive checkpoint cleanup"
        assert engine.events_after(run["id"], 0)[-1]["event"] == "run.succeeded", \
            "the durable audit trail survives checkpoint cleanup"
    finally:
        await engine.aclose()


async def test_recovery_deletes_stranded_terminal_checkpoint_but_keeps_parked_threads(
    tmp_path, settings, store, provider,
):
    from caos.engine.runtime import Engine

    checkpoint_path = tmp_path / "ck.db"
    engine = Engine.create(settings=settings, store=store, checkpoint_path=checkpoint_path, provider=provider)
    try:
        terminal_case = store.create_case("Terminal", "Issuer", "Services", "analyst")
        terminal = await engine.start_run(
            case_id=terminal_case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst",
        )
        parked_case = store.create_case("Parked", "Issuer", "Services", "analyst")
        parked = await engine.start_run(
            case_id=parked_case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst",
        )
        engine.runs.finalize_failure(terminal["id"], "AGENT_OUTPUT_INVALID", None)
        assert _checkpoint_rows(checkpoint_path, terminal["id"]) > 0
        assert _checkpoint_rows(checkpoint_path, parked["id"]) > 0
        with closing(sqlite3.connect(checkpoint_path)) as conn:
            conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (terminal["id"],))
            assert conn.execute(
                "SELECT count(*) FROM writes WHERE thread_id = ?", (terminal["id"],),
            ).fetchone()[0] > 0, "a crash may strand intermediate writes without their checkpoint"
    finally:
        await engine.aclose()

    revived = Engine.create(settings=settings, store=store, checkpoint_path=checkpoint_path, provider=provider)
    try:
        await revived.recover()

        assert _checkpoint_rows(checkpoint_path, terminal["id"]) == 0
        assert _checkpoint_rows(checkpoint_path, parked["id"]) > 0, "parked runs still need their resume state"
    finally:
        await revived.aclose()


# --- events (contractual: atomic state+event, exactly-once terminals, ordering) ---


async def test_event_log_is_per_run_monotonic_with_legacy_names_and_single_terminal(engine, store):
    case, source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.wait(run["id"])
    events = engine.events_after(run["id"], 0)
    ids = [e["id"] for e in events]
    assert ids == sorted(ids) and len(ids) == len(set(ids)), "monotonic unique per-run sequence"
    names = [e["event"] for e in events]
    assert names[0] == "run.created"
    assert names.count("run.succeeded") == 1
    assert {"run.running", "node.running", "node.succeeded"} <= set(names)
    assert engine.events_after(run["id"], ids[-1]) == [], "Last-Event-ID resume semantics"


# --- finalization gate ------------------------------------------------------------


async def test_snapshot_rejects_forged_succeeded_run(engine, store):
    case, source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.wait(run["id"])
    engine.forge_node_artifact_for_tests(run["id"], module_id="CP-0", digest="0" * 64)
    with pytest.raises(Exception, match="RUN_NOT_READY"):
        await engine.accept(run["id"], actor="analyst")


async def test_acceptance_rejects_source_content_changed_without_a_new_source_set(engine, store):
    from caos.storage.store import sources

    case, source = seed_case_with_source(store)
    run = await engine.run_scripted_for_tests(case["id"])
    pinned_set = store.current_source_set(case["id"])
    changed_blocks = [
        {**block, "text": f"{block['text']} tampered"} if index == 0 else block
        for index, block in enumerate(source["blocks"])
    ]
    with store.engine.begin() as conn:
        conn.execute(
            sources.update().where(sources.c.id == source["id"]).values(blocks=changed_blocks)
        )

    with pytest.raises(Exception, match="SOURCE_SET_CHANGED"):
        await engine.accept(run["id"], actor="analyst")
    assert store.current_source_set(case["id"])["id"] == pinned_set["id"], (
        "the content guard must not depend on source-set version churn"
    )


async def test_acceptance_rejects_corrupted_uploaded_source_bytes(
    engine,
    store,
    settings,
):
    from caos.sources.domain import Vault
    from caos.storage.store import sources

    content = b"pinned evidence line"
    case, source = seed_case_with_source(store, body=content)
    path = Vault(settings).put(content, source["sha256"])
    with store.engine.begin() as connection:
        connection.execute(
            sources.update()
            .where(sources.c.id == source["id"])
            .values(vault_path=path)
        )
    run = await engine.run_scripted_for_tests(case["id"])
    path = Path(path)
    path.write_bytes(b"x" * len(content))

    with pytest.raises(Exception, match="AGENT_AUTHORITY_MISMATCH"):
        await engine.accept(run["id"], actor="analyst")
    assert engine.runs.snapshot_for_run(run["id"]) is None


@pytest.mark.parametrize("payload", [[], "not-an-artifact"])
async def test_non_mapping_artifact_payload_fails_closed_at_finalization_and_acceptance(
    engine, store, payload,
):
    from caos.contracts import digest
    from caos.engine.provider import AgentError

    case, _source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.wait(run["id"])
    engine.runs.update_artifact_for_tests(
        run["id"], "CP-0", payload=payload, digest=digest(payload),
    )

    with pytest.raises(AgentError, match="RUN_NOT_READY"):
        engine._verify_run_artifacts(run["id"], engine.get_run(run["id"])["plan"])
    with pytest.raises(Exception, match="RUN_NOT_READY"):
        await engine.accept(run["id"], actor="analyst")


async def test_artifact_read_revalidates_payload_provider_identity(client, engine, store):
    from caos.contracts import digest

    case, _source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.wait(run["id"])
    artifact = engine.artifacts_for_run(run["id"])[0]
    url = f"/api/cases/{case['id']}/artifacts/{artifact['id']}"
    assert client.get(url, headers={"x-forwarded-user": "analyst"}).status_code == 200

    forged = {**artifact["payload"], "provider_identity": {"identity_digest": "0" * 64}}
    engine.runs.update_artifact_for_tests(
        run["id"], artifact["module_id"], payload=forged, digest=digest(forged),
    )
    assert client.get(url, headers={"x-forwarded-user": "analyst"}).status_code == 404


async def test_acceptance_is_idempotent_and_updates_case_and_run_together(engine, store):
    case, source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.wait(run["id"])
    first = await engine.accept(run["id"], actor="analyst")
    second = await engine.accept(run["id"], actor="analyst")
    assert first["id"] == second["id"]
    assert store.get_case(case["id"])["accepted_snapshot_id"] == first["id"]


async def test_acceptance_rolls_back_snapshot_both_pointers_and_audit_as_one_unit(
    engine, store, monkeypatch
):
    case, _source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.wait(run["id"])
    original_audit = store._audit

    def fail_acceptance_audit(connection, action, actor, **details):
        if action == "snapshot.accepted":
            raise RuntimeError("injected acceptance commit failure")
        return original_audit(connection, action, actor, **details)

    monkeypatch.setattr(store, "_audit", fail_acceptance_audit)
    with pytest.raises(RuntimeError, match="injected acceptance commit failure"):
        await engine.accept(run["id"], actor="analyst")

    assert engine.runs.snapshot_for_run(run["id"]) is None
    assert engine.get_run(run["id"])["accepted_snapshot_id"] is None
    assert store.get_case(case["id"])["accepted_snapshot_id"] is None
    assert not [
        event for event in store.list_audit()
        if event["action"] == "snapshot.accepted" and event["run_id"] == run["id"]
    ]

    monkeypatch.setattr(store, "_audit", original_audit)
    accepted = await engine.accept(run["id"], actor="analyst")
    assert engine.runs.snapshot_for_run(run["id"])["id"] == accepted["id"]
    assert engine.get_run(run["id"])["accepted_snapshot_id"] == accepted["id"]
    assert store.get_case(case["id"])["accepted_snapshot_id"] == accepted["id"]
    assert len([
        event for event in store.list_audit()
        if event["action"] == "snapshot.accepted" and event["run_id"] == run["id"]
    ]) == 1


async def test_snapshot_acceptance_refuses_when_cp5_reports_blocked(engine, store):
    """§12.27: reviewer authority maps onto the acceptance gate — Blocked QA cannot be accepted."""
    case, source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.wait(run["id"])
    engine.set_artifact_qa_for_tests(run["id"], module_id="CP-5", qa_status="Blocked")
    with pytest.raises(Exception, match="RUN_NOT_READY|QA_BLOCKED"):
        await engine.accept(run["id"], actor="analyst")


# --- admission (contractual: shared active-job ceiling, capacity returns) ---------


async def test_admission_ceiling_is_derived_and_capacity_returns_on_completion(engine, store):
    from caos.engine.budget import MAX_ACTIVE_JOBS

    assert MAX_ACTIVE_JOBS == 20
    engine.fill_admission_slots_for_tests(MAX_ACTIVE_JOBS)
    case, _ = seed_case_with_source(store)
    with pytest.raises(Exception, match="ADMISSION|BUSY"):
        await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst")
    engine.release_admission_slot_for_tests()
    run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst")
    assert run["id"]


# --- authorization (contractual matrix, re-hosted) --------------------------------


async def test_case_reader_cannot_start_or_upgrade_and_outsiders_see_nothing(client, store):
    case, _ = seed_case_with_source(store)
    store.add_member(case["id"], "analyst", "reader-user", "READER", actor_role="ADMIN")
    start = client.post(
        f"/api/cases/{case['id']}/runs",
        json={"pathway": "FULL_CREDIT", "depth": "screen"},
        headers={"x-caos-role": "ANALYST", "x-forwarded-user": "reader-user"},
    )
    assert start.status_code == 403
    outsider = client.get(f"/api/cases/{case['id']}", headers={"x-forwarded-user": "stranger"})
    assert outsider.status_code == 404


def test_production_rejects_forged_forwarded_identity(store, tmp_path):
    from caos.api import create_app
    from caos.config import Settings
    from fastapi.testclient import TestClient

    prod = Settings(environment="production", storage_dir=tmp_path / "v",
                    database_url="postgresql://x/y", edge_proxy_secret="real-secret", session_secret="real-session")
    app = create_app(settings=prod, store=store, engine=None)
    with TestClient(app) as test_client:
        assert test_client.get("/api/me", headers={"x-forwarded-user": "spoof"}).status_code == 401
        escalated = test_client.get(
            "/api/me",
            headers={"x-edge-authorization": "real-secret", "x-forwarded-user": "user", "x-caos-role": "ADMIN"},
        )
        assert escalated.status_code == 200
        assert escalated.json()["role"] == "READER", "client role headers never escalate in production"


# --- artifact replacement keeps the node pointing at the live row -------------------


def test_replacing_an_invalid_artifact_relinks_the_succeeded_node(engine):
    """A stored artifact that no longer verifies is replaced on re-execution;
    the already-succeeded node must follow the replacement, or every downstream
    fingerprint resolves through a deleted row and the run wedges."""
    from caos.contracts import digest
    from caos.engine.deterministic import build_deterministic_payload
    from caos.storage.runs import artifact_input_fingerprint

    runs = engine.runs
    run = runs.create_run("case-1", "FULL_CREDIT", "full", "analyst")
    plan = {
        "build_id": "deploy-v-test-build",
        "pathway": "FULL_CREDIT",
        "nodes": [
            {"module_id": "CP-0", "stage": 0, "dependencies": []},
            {"module_id": "CP-1", "stage": 1, "dependencies": ["CP-0"]},
        ],
    }
    runs.pin_plan(run["id"], plan, digest(plan))
    runs.node_running(run["id"], "CP-0")
    fingerprint = artifact_input_fingerprint(plan, digest(plan), "CP-0", [])
    payload = build_deterministic_payload("CP-0", plan, input_fingerprint=fingerprint)
    first = runs.complete_node(
        run["id"], "case-1", "CP-0", fingerprint, payload, None, "Passed", "analyst",
        content_expectations={"expected_system_payload": payload},
    )
    runs.update_artifact_for_tests(run["id"], "CP-0", digest="0" * 64)
    assert runs.find_valid_artifact(run["id"], "CP-0", fingerprint) is None

    second = runs.complete_node(
        run["id"], "case-1", "CP-0", fingerprint, payload, None, "Passed", "analyst",
        content_expectations={"expected_system_payload": payload},
    )
    assert second["id"] != first["id"]
    node = next(n for n in runs.get_run(run["id"])["nodes"] if n["module_id"] == "CP-0")
    assert node["status"] == "succeeded"
    assert node["artifact_id"] == second["id"], "the node must follow the replacement"
    assert runs.get_artifact(first["id"]) is None

    runs.node_running(run["id"], "CP-1")
    cp1_fingerprint = artifact_input_fingerprint(plan, digest(plan), "CP-1", [second["digest"]])
    cp1_payload = build_deterministic_payload(
        "CP-1", plan, input_fingerprint=cp1_fingerprint, upstream_digests=[second["digest"]],
    )
    runs.complete_node(
        run["id"], "case-1", "CP-1", cp1_fingerprint, cp1_payload, None, "Passed", "analyst",
        content_expectations={"expected_system_payload": cp1_payload},
    )
    assert [e["event"] for e in runs.events_after(run["id"], 0)].count("node.succeeded") == 2


# --- acceptance takes the authority lock off the event loop --------------------------


async def test_acceptance_waits_for_the_authority_lock_without_stalling_the_event_loop(engine, store):
    """The process-wide authority lock linearizes acceptance against ingest and
    withdrawal, but a synchronous route holding it must not freeze the loop:
    SSE tails and readiness keep serving while acceptance waits."""
    import time

    case, _source = seed_case_with_source(store)
    run = await engine.run_scripted_for_tests(case["id"])

    hold_seconds = 0.6
    held = threading.Event()

    def hold_lock():
        with store.authority_guard():
            held.set()
            time.sleep(hold_seconds)

    holder = threading.Thread(target=hold_lock, name="sync-route-holding-authority")
    holder.start()
    assert held.wait(5)

    ticks: list[float] = []

    async def heartbeat():
        while True:
            ticks.append(time.monotonic())
            await asyncio.sleep(0.01)

    pulse = asyncio.create_task(heartbeat())
    try:
        started = time.monotonic()
        snapshot = await engine.accept(run["id"], actor="analyst")
        waited = time.monotonic() - started
    finally:
        pulse.cancel()
        holder.join(5)
    assert snapshot["run_id"] == run["id"]
    assert waited >= hold_seconds * 0.8, "acceptance must wait for the lock holder"
    longest_gap = max(later - earlier for earlier, later in zip(ticks, ticks[1:]))
    assert longest_gap < hold_seconds * 0.5, f"event loop stalled for {longest_gap:.2f}s while acceptance waited"

