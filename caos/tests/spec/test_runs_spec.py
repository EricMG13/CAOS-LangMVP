"""Run-engine specification (invariants 1, 4, 5, 10). All tests must fail until the engine exists.

Sources: TEST_INVENTORY.md contractual rows from test_clean_slate.py, test_ledger_contracts.py,
and the re-hosted CP-DR finalization rows; DECISIONS.md §§10–12.
"""

from __future__ import annotations

import asyncio
import sqlite3
import threading
from contextlib import closing

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
            coro.close()
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
        with pytest.raises(RuntimeError, match="timed out draining foreign-loop tasks"):
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
    from caos.contracts import PATHWAYS
    from caos.engine.runtime import MVP_PATHWAYS

    case, _source = seed_case_with_source(store)
    served = client.get(f"/api/cases/{case['id']}", headers={"x-forwarded-user": "analyst"}).json()
    assert served["available_pathways"] == sorted(MVP_PATHWAYS)

    for pathway in PATHWAYS:
        response = client.post(f"/api/cases/{case['id']}/runs", json={"pathway": pathway, "depth": "screen"},
                               headers={"x-forwarded-user": "analyst"})
        detail = response.json().get("detail") if response.status_code >= 400 else None
        if pathway in served["available_pathways"]:
            assert response.status_code == 201, f"{pathway} is offered but did not start: {detail}"
        else:
            # Which layer says no is not the point — DEEP_RESEARCH is refused by
            # the depth rule before the cut check is reached. Nothing outside the
            # served cut may start.
            assert response.status_code != 201, f"{pathway} started but is not offered"


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

    replay = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst")
    await engine.wait(replay["id"])
    second = engine.get_run(replay["id"])
    assert second["status"] == "succeeded"
    assert [n["module_id"] for n in second["nodes"]] == [n["module_id"] for n in first["nodes"]], "same path"
    assert second["plan_digest"] == first["plan_digest"], "same pin -> same plan identity"
    firsts = {a["module_id"]: a["digest"] for a in engine.artifacts_for_run(first["id"])}
    seconds = {a["module_id"]: a["digest"] for a in engine.artifacts_for_run(second["id"])}
    assert firsts == seconds, "deterministic modules replay to identical artifact digests"


async def test_started_pathways_are_restricted_to_the_mvp_set(engine, store):
    case, _ = seed_case_with_source(store)
    for pathway in ("DEEP_RESEARCH", "DISTRESSED_RESTRUCTURING", "PORTFOLIO_DECISION", "DECISION_LEDGER"):
        with pytest.raises(Exception):
            await engine.start_run(case_id=case["id"], pathway=pathway, depth="full", actor="analyst")


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


async def test_acceptance_is_idempotent_and_updates_case_and_run_together(engine, store):
    case, source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.wait(run["id"])
    first = await engine.accept(run["id"], actor="analyst")
    second = await engine.accept(run["id"], actor="analyst")
    assert first["id"] == second["id"]
    assert store.get_case(case["id"])["accepted_snapshot_id"] == first["id"]


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
