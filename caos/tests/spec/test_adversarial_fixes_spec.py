"""Behaviours the 2026-09-06 adversarial review found missing (the Saboteur's
S1, S5, S7, S8, S10 and the Security Auditor's X2 companions), each pinned by
the smallest test that fails if the defect returns:

- startup recovery under the serving entrypoint schedules a stranded run and
  returns, instead of executing it to completion before the socket binds;
- a continuation that dies on an infrastructure fault is retried and then
  failed closed with a typed code, never left `running` with its slot held;
- an API resume on a run whose thread is held is refused, never queued behind
  the rest of the run;
- the visible-lens switch and its audit row commit in one transaction;
- a finalization refusal names the module it blamed.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from sqlalchemy.exc import OperationalError

from spec_helpers import seed_case_with_source, start_full_credit_run

ANALYST_H = {"x-caos-role": "ANALYST", "x-forwarded-user": "analyst"}


class GatedHostControl:
    """The host-control provider behind an asyncio gate: every provider call
    waits until the test opens it, so a run can be held mid-flight on purpose."""

    def __init__(self):
        from caos.engine.host_control import HostControlProvider

        self._inner = HostControlProvider()
        self.gate = asyncio.Event()
        self.calls = 0
        self.identity = self._inner.identity

    def count_tokens(self, request):
        return self._inner.count_tokens(request)

    async def create_message(self, request):
        await self.gate.wait()
        self.calls += 1
        return self._inner.create_message(request)


def make_engine(tmp_path, settings, store, provider):
    from caos.engine.runtime import Engine

    return Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "checkpoints.db", provider=provider)


async def test_recovery_under_auto_continue_schedules_stranded_runs_and_returns(tmp_path, settings, store):
    """S1: the serving entrypoint awaits recover() before binding the socket, so
    recovery must schedule stranded runs as continuations, not replay them."""
    case, _source = seed_case_with_source(store)
    first_provider = GatedHostControl()
    crashed = make_engine(tmp_path, settings, store, first_provider)
    crashed.enable_auto_continue()
    try:
        run = await crashed.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst")
        assert run["status"] == "running"
    finally:
        # The "process death": aclose() cancels the scheduled continuation before
        # its first provider call. (A crash mid-call leaves a charged reservation
        # and fails closed on recovery — invariant 8 — a different, deliberate contract.)
        await crashed.aclose()
    assert store.get_case(case["id"]) is not None
    assert crashed.runs.get_run(run["id"])["status"] == "running", "the stranded run is what recovery must handle"

    revived_provider = GatedHostControl()
    revived = make_engine(tmp_path, settings, store, revived_provider)
    revived.enable_auto_continue()
    try:
        started = time.monotonic()
        await revived.recover()
        elapsed = time.monotonic() - started
        assert elapsed < 2.0, f"recover() blocked for {elapsed:.1f}s on the stranded run"
        assert revived_provider.calls == 0, "recover() must not execute provider calls inline"
        assert revived.runs.get_run(run["id"])["status"] == "running"
        assert len(revived._continuations) == 1, "the stranded run is re-driven as one continuation"
        revived_provider.gate.set()
        record = await revived.wait(run["id"])
        assert record["status"] == "succeeded", record["error"]
        assert revived_provider.calls > 0
    finally:
        revived_provider.gate.set()
        await revived.aclose()


async def test_recovery_without_auto_continue_still_drives_inline(tmp_path, settings, store):
    """Explicit control (tests, tooling) keeps the old contract: recover()
    leaves the run terminal."""
    case, _source = seed_case_with_source(store)
    first_provider = GatedHostControl()
    crashed = make_engine(tmp_path, settings, store, first_provider)
    crashed.enable_auto_continue()
    try:
        run = await crashed.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst")
    finally:
        await crashed.aclose()
    revived_provider = GatedHostControl()
    revived_provider.gate.set()
    revived = make_engine(tmp_path, settings, store, revived_provider)
    try:
        await revived.recover()
        assert revived.runs.get_run(run["id"])["status"] == "succeeded"
        assert revived._continuations == set()
    finally:
        await revived.aclose()


async def test_a_dead_continuation_is_retried_then_failed_closed(tmp_path, settings, store, monkeypatch):
    """S7: one infrastructure exception inside a node used to leave the run
    `running` forever with `error: null` and its admission slot held."""
    case, _source = seed_case_with_source(store)
    provider = GatedHostControl()
    provider.gate.set()
    engine = make_engine(tmp_path, settings, store, provider)
    engine.enable_auto_continue()
    monkeypatch.setattr(engine, "CONTINUATION_RETRY_DELAYS", (0.0, 0.0))
    attempts = []

    async def always_locked(run_id):
        attempts.append(run_id)
        raise OperationalError("UPDATE run_nodes", {}, Exception("database is locked"))

    monkeypatch.setattr(engine, "wait", always_locked)
    try:
        run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst")
        for _ in range(100):
            await asyncio.sleep(0.02)
            if engine.runs.get_run(run["id"])["status"] == "failed":
                break
        record = engine.runs.get_run(run["id"])
        assert record["status"] == "failed"
        assert record["error"] == {"code": "RUN_EXECUTION_FAILED"}
        assert len(attempts) == 3, "one attempt plus the two retries of the shortened schedule"
        assert engine.runs.active_admission_count() == 0, "the admission slot is released with the terminal event"
        assert any(event["event"] == "run.failed" for event in engine.runs.events_after(run["id"], 0))
    finally:
        await engine.aclose()


async def test_a_transient_continuation_fault_recovers_on_retry(tmp_path, settings, store, monkeypatch):
    case, _source = seed_case_with_source(store)
    provider = GatedHostControl()
    provider.gate.set()
    engine = make_engine(tmp_path, settings, store, provider)
    engine.enable_auto_continue()
    monkeypatch.setattr(engine, "CONTINUATION_RETRY_DELAYS", (0.0,))
    real_wait = engine.wait
    faults = {"left": 1}

    async def flaky_wait(run_id):
        if faults["left"]:
            faults["left"] -= 1
            raise OperationalError("UPDATE run_nodes", {}, Exception("database is locked"))
        return await real_wait(run_id)

    monkeypatch.setattr(engine, "wait", flaky_wait)
    try:
        run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst")
        for _ in range(200):
            await asyncio.sleep(0.02)
            if engine.runs.get_run(run["id"])["status"] in {"succeeded", "failed"}:
                break
        assert engine.runs.get_run(run["id"])["status"] == "succeeded"
        assert faults["left"] == 0
    finally:
        await engine.aclose()


async def test_resume_refuses_while_the_thread_is_executing(tmp_path, settings, store):
    """S8: a resume issued while the continuation holds the thread answers at
    once with RESUME_NOT_APPLIED instead of waiting for the whole run."""
    from caos.engine.runtime import EngineError

    case, _source = seed_case_with_source(store)
    provider = GatedHostControl()
    engine = make_engine(tmp_path, settings, store, provider)
    engine.enable_auto_continue()
    try:
        run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst")
        await asyncio.sleep(0.05)  # the continuation now holds the thread lock, parked on the gate
        started = time.monotonic()
        with pytest.raises(EngineError) as refused:
            await engine.resume(run["id"])
        assert refused.value.code == "RESUME_NOT_APPLIED"
        assert time.monotonic() - started < 1.0
        provider.gate.set()
        assert (await engine.wait(run["id"]))["status"] == "succeeded"
    finally:
        provider.gate.set()
        await engine.aclose()


async def test_resume_not_applied_maps_to_409(tmp_path, settings, store, provider):
    """The route serves the engine's refusal as a typed 409, not a 500."""
    from fastapi.testclient import TestClient

    from caos.api import create_app
    from caos.engine.runtime import EngineError

    engine = make_engine(tmp_path, settings, store, provider)
    try:
        _case, _source, run = await start_full_credit_run(engine, store, depth="screen")

        async def executing(_run_id):
            raise EngineError("RESUME_NOT_APPLIED", "run is executing")

        engine.resume = executing  # type: ignore[method-assign]
        app = create_app(settings=settings, store=store, engine=engine)
        with TestClient(app) as client:
            response = client.post(f"/api/runs/{run['id']}/resume", headers=ANALYST_H)
        assert response.status_code == 409
        assert response.json()["detail"] == {"code": "RESUME_NOT_APPLIED"}
    finally:
        await engine.aclose()


async def test_switch_visible_commits_the_pointer_and_its_audit_row_together(engine, store, monkeypatch):
    """S5: the lens move and the `snapshot.visible_switched` row are one
    transaction — neither lands without the other."""
    case, _source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.wait(run["id"])
    snapshot = await engine.accept(run["id"], actor="analyst")
    before = store.get_case(case["id"])["visible_snapshot_id"]
    real_audit = store._audit

    def audit_fails(conn, action, actor, **details):
        if action == "snapshot.visible_switched":
            raise OperationalError("INSERT audit_events", {}, Exception("connection dropped"))
        return real_audit(conn, action, actor, **details)

    monkeypatch.setattr(store, "_audit", audit_fails)
    with pytest.raises(OperationalError):
        await engine.switch_visible(case["id"], snapshot["id"], actor="analyst")
    assert store.get_case(case["id"])["visible_snapshot_id"] == before, "the pointer moved without its audit row"
    monkeypatch.setattr(store, "_audit", real_audit)
    await engine.switch_visible(case["id"], snapshot["id"], actor="analyst")
    assert store.get_case(case["id"])["visible_snapshot_id"] == snapshot["id"]
    switched = [row for row in store.audit_trail() if row["action"] == "snapshot.visible_switched"]
    assert len(switched) == 1 and switched[0]["snapshot_id"] == snapshot["id"]


async def test_a_finalization_refusal_names_the_module_it_blamed(engine, store, monkeypatch):
    """S10: `_finalize_node` used to drop `ModuleFailure.module_id`, so the run
    record and its `run.failed` event could not say which artifact failed."""
    from caos.engine.runtime import ModuleFailure

    def refuse(run_id, plan):
        raise ModuleFailure("QA_BLOCKED", "CP-5", "final re-verification refused")

    monkeypatch.setattr(engine, "_verify_run_artifacts", refuse)
    _case, _source, run = await start_full_credit_run(engine, store, depth="screen")
    record = await engine.wait(run["id"])
    assert record["status"] == "failed"
    assert record["error"] == {"code": "QA_BLOCKED", "module_id": "CP-5"}
    blamed = [node for node in record["nodes"] if node["module_id"] == "CP-5"]
    assert blamed and blamed[0]["status"] == "failed"


def test_run_error_is_a_named_wire_model():
    """W10: the run failure shape is declared, not `Any` — undeclared keys are refused."""
    from pydantic import ValidationError

    from caos.responses import RunErrorResponse, RunResponse

    error = RunErrorResponse(code="QA_BLOCKED", module_id="CP-5")
    assert (error.code, error.module_id, error.message) == ("QA_BLOCKED", "CP-5", None)
    with pytest.raises(ValidationError):
        RunErrorResponse(code="QA_BLOCKED", detail="document text")
    assert RunResponse.model_fields["error"].annotation == (RunErrorResponse | None)
