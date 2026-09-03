"""Retained failure simulations SIM-001 to SIM-030 (ENTERPRISE_TESTING_READINESS
"Run failure and concurrency simulations"; ENTERPRISE_READINESS_PLAN Phase 5
items 6, 7, 9; Task 12a). `docs/SIMULATION_LEDGER.csv` maps every SIM id to
the test that carries it — the rows already covered by an older test name that
test; the rows below are the ones no existing seam expressed.

Every simulation here injects its fault through an existing seam — the
engine's kill-after-module, commit-gap and mid-provider-call hooks, the
scripted host-control provider, the worker's identity-bound fallbacks — or
through a monkeypatch at the exact boundary the SIM row names, and then
asserts one valid final state across domain data, checkpoints, files, budget,
events, audit and the user-visible status, before AND after a restart. An
HTTP status alone is never the assertion.
"""

from __future__ import annotations

import contextlib
import errno
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spec_helpers import seed_case_with_source  # noqa: E402

from caos.engine.host_control import HostControlProvider  # noqa: E402
from caos.engine.runtime import Engine, SimulatedCrash  # noqa: E402

TERMINAL_EVENTS = {"run.succeeded", "run.failed"}


# --- seams --------------------------------------------------------------------


class FaultingHostControl:
    """The compliant host-control double with one fault injected at a chosen
    provider call: the fault is raised from inside `create_message`, which is
    what "during the provider call" means to the host."""

    def __init__(self, faults: dict[int, BaseException] | None = None) -> None:
        self._inner = HostControlProvider()
        self.identity = self._inner.identity
        self.faults = dict(faults or {})
        self.create_requests: list[Any] = []

    def count_tokens(self, request: Any) -> int:
        return self._inner.count_tokens(request)

    def create_message(self, request: Any) -> Any:
        self.create_requests.append(request)
        fault = self.faults.pop(len(self.create_requests), None)
        if fault is not None:
            raise fault
        return self._inner.create_message(request)


def _engine(tmp_path: Path, settings, store, provider: Any, name: str = "ck.db") -> Engine:
    return Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / name, provider=provider)


async def _start(engine: Engine, store, *, depth: str = "full") -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    case, source = seed_case_with_source(store)
    run = await engine.start_run_for_tests(
        case_id=case["id"], pathway="FULL_CREDIT", depth=depth, actor="analyst",
        allow_placeholder_deterministic=True,
    )
    return case, source, run


def _checkpoint_rows(path: Path, thread_id: str) -> int:
    if not path.exists():
        return 0
    with closing(sqlite3.connect(path)) as conn:
        return sum(
            conn.execute(f"SELECT count(*) FROM {table} WHERE thread_id = ?", (thread_id,)).fetchone()[0]
            for table in ("checkpoints", "writes")
        )


def _state(engine: Engine, run_id: str, checkpoint_path: Path) -> dict[str, Any]:
    """One valid final state, read from every store the run touches."""
    run = engine.get_run(run_id)
    events = engine.events_after(run_id, 0)
    budget = engine.runs.get_budget(run_id)
    return {
        "status": run["status"],
        "error": run.get("error"),
        "node_status": {node["module_id"]: node["status"] for node in run["nodes"]},
        "artifacts": sorted((a["module_id"], a["digest"]) for a in engine.artifacts_for_run(run_id)),
        "execution_counts": engine.execution_counts_for_tests(run_id),
        "terminal_events": [e["event"] for e in events if e["event"] in TERMINAL_EVENTS],
        "event_ids": [e["id"] for e in events],
        "budget_used": dict(budget["used"]) if budget else None,
        "inflight": budget["inflight_request_digest"] if budget else None,
        "checkpoint_rows": _checkpoint_rows(checkpoint_path, run_id),
        "audit_chain": engine.store.verify_audit_chain(),
    }


def _assert_one_clean_success(state: dict[str, Any], *, modules_once: bool = True) -> None:
    assert state["status"] == "succeeded", state
    assert state["terminal_events"] == ["run.succeeded"], "exactly one terminal event"
    assert state["event_ids"] == list(range(1, len(state["event_ids"]) + 1)), "gap-free event sequence"
    assert all(status == "succeeded" for status in state["node_status"].values()), state["node_status"]
    assert len({module for module, _ in state["artifacts"]}) == len(state["artifacts"]), "one artifact per module"
    if modules_once:
        assert all(count == 1 for count in state["execution_counts"].values()), state["execution_counts"]
    assert state["inflight"] is None, "no reservation left in flight"
    assert state["checkpoint_rows"] == 0, "terminal runs leave no checkpoint"
    assert state["audit_chain"] == {}


async def _restart(tmp_path: Path, settings, store, provider: Any, run_id: str) -> tuple[Engine, dict[str, Any]]:
    revived = _engine(tmp_path, settings, store, provider)
    try:
        revived._allow_placeholder_deterministic_for_tests(run_id)
        await revived.recover()
        await revived.wait(run_id)
        return revived, _state(revived, run_id, tmp_path / "ck.db")
    finally:
        await revived.aclose()


# --- SIM-001: kill before the first provider call ----------------------------------


async def test_sim_001_kill_before_any_provider_call_leaves_no_reservation_and_recovers_once(tmp_path, settings, store):
    provider = FaultingHostControl()
    engine = _engine(tmp_path, settings, store, provider)
    try:
        _case, _source, run = await _start(engine, store)  # parked after the plan gate, before any module
        before = _state(engine, run["id"], tmp_path / "ck.db")
    finally:
        await engine.aclose()  # the process dies here
    assert before["status"] == "running" and before["inflight"] is None
    assert (before["budget_used"] or {}).get("turns", 0) == 0 and provider.create_requests == [], "no reservation, no provider contact"
    assert before["artifacts"] == [] and before["checkpoint_rows"] > 0, "the gate checkpoint is the only durable progress"

    _revived, after = await _restart(tmp_path, settings, store, provider, run["id"])
    _assert_one_clean_success(after)
    assert after["budget_used"]["turns"] == len(provider.create_requests), "every turn on the ledger exactly once"


# --- SIM-003: kill during the provider call ------------------------------------------


async def test_sim_003_kill_during_the_provider_call_never_spends_again_on_resume(tmp_path, settings, store):
    provider = FaultingHostControl({1: SimulatedCrash("process killed while the request was in flight")})
    engine = _engine(tmp_path, settings, store, provider)
    try:
        _case, _source, run = await _start(engine, store)
        # The crash rides a parallel superstep: a sibling module may observe the
        # orphaned reservation and fail the run closed before the crash surfaces,
        # exactly as the restart below would. Either way the ledger shows one
        # in-flight digest whose spend nobody knows.
        with contextlib.suppress(SimulatedCrash):
            await engine.wait(run["id"])
        before = _state(engine, run["id"], tmp_path / "ck.db")
    finally:
        await engine.aclose()
    assert before["inflight"] is not None, "the reservation is in flight, spend unknown"
    assert before["status"] == "running" or before["error"]["code"] == "AGENT_BUDGET_EXCEEDED", before
    calls_before = len(provider.create_requests)

    _revived, after = await _restart(tmp_path, settings, store, provider, run["id"])
    assert after["status"] == "failed" and after["error"]["code"] == "AGENT_BUDGET_EXCEEDED"
    assert after["terminal_events"] == ["run.failed"]
    assert len(provider.create_requests) == calls_before, "unknown spend is never retried (invariant 8)"
    assert after["inflight"] is not None, "the unresolved digest stays on the ledger as the record of the unknown"
    assert after["checkpoint_rows"] == 0 and after["audit_chain"] == {}
    assert set(after["node_status"].values()) <= {"failed", "cancelled", "pending", "succeeded"} and "running" not in after["node_status"].values(), \
        "no node is left running on a terminal run; siblings that finished before the kill keep their artifacts"


# --- SIM-004: kill after the provider response, before the artifact commit -------------


async def test_sim_004_kill_after_the_response_before_the_artifact_commit_yields_one_artifact(tmp_path, settings, store, monkeypatch):
    provider = FaultingHostControl()
    engine = _engine(tmp_path, settings, store, provider)
    real_complete = engine.runs.complete_node
    crashed = {"done": False}

    def crash_once(run_id, case_id, module_id, *args, **kwargs):
        if not crashed["done"]:
            crashed["done"] = True
            raise SimulatedCrash(f"killed after the response for {module_id} was reconciled")
        return real_complete(run_id, case_id, module_id, *args, **kwargs)

    monkeypatch.setattr(engine.runs, "complete_node", crash_once)
    try:
        _case, _source, run = await _start(engine, store)
        with pytest.raises(SimulatedCrash):
            await engine.wait(run["id"])
        before = _state(engine, run["id"], tmp_path / "ck.db")
    finally:
        await engine.aclose()
    assert before["artifacts"] == [], "nothing committed for the module whose response was lost"
    assert before["inflight"] is None, "the spend was reconciled — it is known, so a retry is allowed"
    first_module_calls = len(provider.create_requests)

    _revived, after = await _restart(tmp_path, settings, store, provider, run["id"])
    _assert_one_clean_success(after, modules_once=False)
    assert len(provider.create_requests) > first_module_calls, "the lost module is re-executed, once"
    assert after["budget_used"]["turns"] == len(provider.create_requests), "every known spend is on the ledger, none twice"


# --- SIM-006: kill during final validation -----------------------------------------------


async def test_sim_006_kill_during_final_validation_never_commits_success_twice_or_past_the_ceiling(tmp_path, settings, store, monkeypatch):
    provider = FaultingHostControl()
    engine = _engine(tmp_path, settings, store, provider)
    real_verify = engine._verify_run_artifacts
    crashed = {"done": False}

    def crash_once(run_id, plan):
        if not crashed["done"]:
            crashed["done"] = True
            raise SimulatedCrash("killed inside the final re-validation")
        return real_verify(run_id, plan)

    monkeypatch.setattr(engine, "_verify_run_artifacts", crash_once)
    try:
        _case, _source, run = await _start(engine, store)
        with pytest.raises(SimulatedCrash):
            await engine.wait(run["id"])
        before = _state(engine, run["id"], tmp_path / "ck.db")
    finally:
        await engine.aclose()
    assert before["status"] == "running" and before["terminal_events"] == [], "no success committed by a dying validation"
    assert before["checkpoint_rows"] > 0

    _revived, after = await _restart(tmp_path, settings, store, provider, run["id"])
    _assert_one_clean_success(after)
    assert after["budget_used"]["turns"] == len(provider.create_requests), "the validation retry spent nothing"


# --- SIM-008: worker killed mid model build ---------------------------------------------


async def test_sim_008_a_worker_killed_mid_build_leaves_one_retryable_job_that_a_restart_completes(tmp_path, settings, store):
    """A hard kill skips the worker's own FAILED fallback, so the row it claimed
    stays BUILDING with no executor. The next worker start requeues it exactly as
    it requeues a dead freeze render, and the build completes once, never READY
    twice and never from a file the dead executor half-wrote."""
    from dataclasses import replace

    import worker
    from spec_helpers import ScriptedProvider

    from caos.models.service import ModelService

    engine = Engine.create(settings=replace(settings, agent_execution_enabled=True), store=store,
                           checkpoint_path=tmp_path / "ck.db", provider=ScriptedProvider())
    try:
        models = ModelService(store=store, vault_dir=settings.storage_dir, engine=engine)
        case, _source = seed_case_with_source(store)
        run = await engine.run_scripted_for_tests(case["id"])
        await engine.accept(run["id"], actor="analyst")
        queued = models.queue_build(case["id"], "analyst")
        assert models.builds.update_build(queued["id"], expected_status=("QUEUED", "FAILED"), status="BUILDING"), \
            "worker A claims the row, then the process is killed"
        assert worker.run_pending(models) == 0, "a claimed row is never stolen by a live pass"
        assert models.builds.get_build(queued["id"])["status"] == "BUILDING"

        assert models.recover_builds() == 1, "the next worker start requeues the orphaned claim"
        assert models.builds.get_build(queued["id"])["status"] == "QUEUED", "retryable, not lost and not READY"
        assert worker.run_pending(models) >= 1
        build = models.builds.get_build(queued["id"])
        assert build["status"] == "READY", build.get("error")
        assert build["payload"] is not None and build["payload_digest"]
        assert [b["id"] for b in models.builds.list_builds(case["id"]) if b["status"] == "READY"] == [queued["id"]]
        assert models.recover_builds() == 0, "recovery touches only rows a dead executor left behind"
        assert store.verify_audit_chain() == {}
    finally:
        await engine.aclose()


# --- SIM-010: database unavailable before a write ----------------------------------------


async def test_sim_010_database_unavailable_before_a_write_is_typed_and_leaves_no_partial_file(tmp_path, settings, store, monkeypatch):
    import sqlalchemy.exc

    from caos.api import create_app
    from fastapi.testclient import TestClient

    provider = FaultingHostControl()
    engine = _engine(tmp_path, settings, store, provider)
    try:
        app = create_app(settings=settings, store=store, engine=engine)
        with TestClient(app) as client:
            case_id = client.post("/api/cases", json={"name": "Outage", "issuer": "Issuer", "sector": "Services"}).json()["id"]

            def store_is_down(*_args, **_kwargs):
                raise sqlalchemy.exc.OperationalError("INSERT INTO sources", {}, ConnectionRefusedError("db down"))

            monkeypatch.setattr(store, "ingest", store_is_down)
            response = client.post(f"/api/cases/{case_id}/sources",
                                   files={"file": ("doc.txt", b"evidence while the database is down", "text/plain")})
            assert response.status_code == 503, response.text
            assert response.json() == {"detail": {"code": "STORE_UNAVAILABLE"}}
            assert "db down" not in response.text and "INSERT" not in response.text, "the driver's message never reaches the wire"
            monkeypatch.undo()

            vault = Path(settings.storage_dir)
            partial = [p for p in vault.rglob("*") if p.is_file() and p.name.startswith(".")]
            assert partial == [], "no temporary or partial vault object survives"
            assert store.list_sources(case_id) == [] and store.current_source_set(case_id) is None
            assert [row for row in store.audit_trail() if row["action"] == "source.ingested"] == []

            recovered = client.post(f"/api/cases/{case_id}/sources",
                                    files={"file": ("doc.txt", b"evidence while the database is down", "text/plain")})
            assert recovered.status_code == 201, "the same bytes ingest cleanly once the store is back"
            assert store.current_source_set(case_id)["version"] == 1
            assert store.verify_audit_chain() == {}
    finally:
        await engine.aclose()


# --- SIM-022: checkpoint absent, truncated or corrupt ------------------------------------


async def _kill_after_two_modules(tmp_path, settings, store, provider):
    engine = _engine(tmp_path, settings, store, provider)
    try:
        _case, _source, run = await _start(engine, store)
        await engine.kill_after_modules_for_tests(run["id"], count=2)
        return run["id"], _state(engine, run["id"], tmp_path / "ck.db")
    finally:
        await engine.aclose()


async def test_sim_022_absent_checkpoint_recovers_from_domain_truth_without_re_executing_finished_modules(tmp_path, settings, store):
    provider = FaultingHostControl()
    run_id, before = await _kill_after_two_modules(tmp_path, settings, store, provider)
    assert before["checkpoint_rows"] > 0 and len(before["artifacts"]) == 2
    (tmp_path / "ck.db").unlink()
    for sidecar in ("ck.db-wal", "ck.db-shm"):
        (tmp_path / sidecar).unlink(missing_ok=True)
    calls_before = len(provider.create_requests)

    _revived, after = await _restart(tmp_path, settings, store, provider, run_id)
    _assert_one_clean_success(after)
    finished = {module for module, _ in before["artifacts"]}
    assert {module for module, _ in after["artifacts"]} >= finished
    assert all(after["execution_counts"][module] == 1 for module in finished), \
        "reuse-first relink: finished modules are not re-executed, progress is neither lost nor invented"
    assert len(provider.create_requests) > calls_before, "the unfinished modules run"


@pytest.mark.parametrize("damage", ["truncated", "corrupt"])
async def test_sim_022_truncated_or_corrupt_checkpoint_refuses_startup_without_inventing_progress(tmp_path, settings, store, damage):
    provider = FaultingHostControl()
    run_id, before = await _kill_after_two_modules(tmp_path, settings, store, provider)
    checkpoint = tmp_path / "ck.db"
    if damage == "truncated":
        with checkpoint.open("r+b") as handle:
            handle.truncate(512)
    else:
        checkpoint.write_bytes(os.urandom(4096))
    for sidecar in ("ck.db-wal", "ck.db-shm"):
        (tmp_path / sidecar).unlink(missing_ok=True)
    calls_before = len(provider.create_requests)

    revived = _engine(tmp_path, settings, store, provider)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            await revived.recover()
        assert revived.readiness()["checkpointer"] is False, "health reports the checkpointer down"
        run = revived.get_run(run_id)
        assert run["status"] == before["status"] == "running", "no status was invented"
        assert [e["id"] for e in revived.events_after(run_id, 0)] == before["event_ids"], "no event was appended"
        assert sorted((a["module_id"], a["digest"]) for a in revived.artifacts_for_run(run_id)) == before["artifacts"]
        assert len(provider.create_requests) == calls_before, "no provider contact from a refused startup"
        assert store.verify_audit_chain() == {}
    finally:
        await revived.aclose()


# --- SIM-023: disk full during a vault or export write ---------------------------------------


def _disk_full(*_args, **_kwargs):
    raise OSError(errno.ENOSPC, "No space left on device")


async def test_sim_023_disk_full_during_the_vault_write_leaves_no_source_and_no_partial_file(tmp_path, settings, store, monkeypatch):
    from caos.sources.domain import Vault, ingest_upload

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from helpers import make_upload

    vault = Vault(settings)
    case = store.create_case("Full disk", "Issuer", "Services", "analyst")
    monkeypatch.setattr(os, "fsync", _disk_full)
    with pytest.raises(OSError) as failure:
        await ingest_upload(store, vault, case["id"], "analyst", make_upload("doc.txt", b"evidence that cannot land"), 1_000_000)
    assert failure.value.errno == errno.ENOSPC
    monkeypatch.undo()
    files = [p for p in Path(settings.storage_dir).rglob("*") if p.is_file()]
    assert files == [], f"no partial or complete object without a record: {files}"
    assert store.list_sources(case["id"]) == [] and store.current_source_set(case["id"]) is None

    recovered = await ingest_upload(store, vault, case["id"], "analyst", make_upload("doc.txt", b"evidence that cannot land"), 1_000_000)
    assert recovered["source_set"]["version"] == 1
    assert store.verify_audit_chain() == {}


def test_sim_023_disk_full_during_the_export_write_finalizes_the_job_failed_with_no_frozen_record(tmp_path, store, monkeypatch):
    from test_deliverables_spec import freeze_request, make_service, save_min_draft, sign_min

    service = make_service(store, tmp_path / "vault")
    case, _source, _template, revision = save_min_draft(service, store)
    sign_min(service, case["id"], revision)
    job = service.freeze(case["id"], freeze_request(revision), actor="analyst")
    monkeypatch.setattr(os, "fsync", _disk_full)
    assert service.run_pending_freezes() == 1
    monkeypatch.undo()
    failed = service.freeze_job(case["id"], job["job_id"])
    assert failed["status"] == "FAILED" and failed["error"] == {"code": "DELIVERABLE_RENDER_FAILED"}
    assert "No space" not in str(failed)
    assert service.workspace(case["id"], "FULL_CREDIT")["frozen"] == [], "no frozen record"
    exports = [p for p in (tmp_path / "vault").rglob("*") if p.is_file()]
    assert exports == [], f"no export published, complete or partial: {exports}"
    assert [e["code"] for e in service.audit_events_for_tests(case["id"]) if e["action"] == "deliverable.freeze_failed"] == ["DELIVERABLE_RENDER_FAILED"]

    retried = service.freeze(case["id"], freeze_request(revision), actor="analyst")
    assert retried["job_id"] == job["job_id"] and retried["status"] == "QUEUED"
    assert service.run_pending_freezes() == 1
    assert service.frozen_record_for_job(case["id"], job["job_id"])["status"] == "FROZEN"
    assert store.verify_audit_chain() == {}


# --- SIM-024: provider failure matrix -----------------------------------------------------


@pytest.mark.parametrize(
    ("fault", "expected_code", "max_calls"),
    [
        (TimeoutError("read timed out"), "AGENT_PROVIDER_TIMEOUT", 2),
        (ConnectionResetError("connection reset by peer"), "CANONICAL_GENERATION_FAILED", 1),
        (RuntimeError("HTTP 429 rate_limit_error: secret-token-abc"), "CANONICAL_GENERATION_FAILED", 1),
        (RuntimeError("HTTP 500 api_error"), "CANONICAL_GENERATION_FAILED", 1),
        (PermissionError("HTTP 401 authentication_error"), "CANONICAL_GENERATION_FAILED", 1),
        (PermissionError("HTTP 403 permission_error"), "CANONICAL_GENERATION_FAILED", 1),
        (ValueError("HTTP 422 invalid_request_error"), "CANONICAL_GENERATION_FAILED", 1),
        (RuntimeError("HTTP 307 redirect to https://evil.example"), "CANONICAL_GENERATION_FAILED", 1),
    ],
    ids=["timeout", "disconnect", "429", "500", "401", "403", "422", "redirect"],
)
async def test_sim_024_provider_failures_end_typed_sanitized_and_bounded(tmp_path, settings, store, fault, expected_code, max_calls):
    faults = {1: fault, 2: TimeoutError("second timeout")} if isinstance(fault, TimeoutError) else {1: fault}
    provider = FaultingHostControl(faults)
    engine = _engine(tmp_path, settings, store, provider)
    try:
        _case, _source, run = await _start(engine, store)
        await engine.wait(run["id"])
        state = _state(engine, run["id"], tmp_path / "ck.db")
        assert state["status"] == "failed" and state["error"]["code"] == expected_code, state["error"]
        assert state["terminal_events"] == ["run.failed"]
        assert len(provider.create_requests) == max_calls, "bounded retry policy: one byte-identical retry for a timeout, none otherwise"
        assert state["checkpoint_rows"] == 0 and state["audit_chain"] == {}
        record = engine.runs.serialize_all_for_run(run["id"])
        assert str(fault) not in record and "secret-token-abc" not in record and "evil.example" not in record, \
            "the provider's error body is never persisted"
        attempts = engine.runs.get_budget(run["id"])["attempts"]
        assert attempts and attempts[-1]["kind"] == "terminal" and attempts[-1]["terminal_code"] == expected_code
    finally:
        await engine.aclose()


# --- SIM-027: wall clock moves backward or forward ------------------------------------------


async def test_sim_027_a_wall_clock_jump_never_reorders_events_or_charges_time_twice(tmp_path, settings, store, monkeypatch):
    from caos.storage import runs as runs_module

    stamps = iter(["2026-09-03T12:00:00+00:00", "2020-01-01T00:00:00+00:00", "2030-12-31T23:59:59+00:00"] * 50)
    monkeypatch.setattr(runs_module, "now_iso", lambda: next(stamps))
    provider = FaultingHostControl()
    engine = _engine(tmp_path, settings, store, provider)
    try:
        _case, _source, run = await _start(engine, store)
        await engine.wait(run["id"])
        state = _state(engine, run["id"], tmp_path / "ck.db")
        _assert_one_clean_success(state)
        events = engine.events_after(run["id"], 0)
        assert [e["id"] for e in events] == list(range(1, len(events) + 1)), "ordering is the sequence, never the clock"
        assert events[0]["event"] == "run.created" and events[-1]["event"] == "run.succeeded"
        assert len({e["at"] for e in events}) > 1 and sorted(e["at"] for e in events) != [e["at"] for e in events], \
            "the injected clock really did jump around"
        assert state["budget_used"]["active_minutes"] >= 0, "time is charged from the monotonic clock, never negative"
    finally:
        await engine.aclose()


# --- SIM-028: malware scanner unavailable ---------------------------------------------------


async def test_sim_028_an_unreachable_malware_scanner_refuses_the_upload_with_an_actionable_status(tmp_path, store):
    import socket
    from dataclasses import replace

    from fastapi import HTTPException

    from caos.config import Settings
    from caos.sources.domain import Vault, ingest_upload

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from helpers import make_upload

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        closed_port = sock.getsockname()[1]
    # Development skips the scanner by design; the outage matters in production.
    settings = replace(Settings(storage_dir=tmp_path / "vault"), environment="production",
                       clamav_host="127.0.0.1", clamav_port=closed_port)
    vault = Vault(settings)
    case = store.create_case("Scanner down", "Issuer", "Services", "analyst")
    with pytest.raises(HTTPException) as refusal:
        await ingest_upload(store, vault, case["id"], "analyst", make_upload("doc.txt", b"unscanned evidence"), 1_000_000)
    assert refusal.value.status_code == 503, "fail closed with a status the operator can act on"
    assert "scanner" in str(refusal.value.detail).lower()
    assert store.list_sources(case["id"]) == [], "protected work did not proceed"
    assert [p for p in (tmp_path / "vault").rglob("*") if p.is_file()] == [], "nothing unscanned reaches the vault"


# --- SIM-029: renderer hang -------------------------------------------------------------------


def test_sim_029_a_hanging_pdf_renderer_finalizes_the_freeze_failed_without_a_published_digest(tmp_path, store, monkeypatch):
    import subprocess

    from caos.publishing import renderers
    from test_deliverables_spec import freeze_request, make_service, save_min_draft, sign_min

    def hang(command, *args, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs.get("timeout", 60))

    monkeypatch.setattr(renderers.subprocess, "run", hang)
    service = make_service(store, tmp_path / "vault")
    case, _source, _template, revision = save_min_draft(service, store)
    sign_min(service, case["id"], revision)
    job = service.freeze(case["id"], freeze_request(revision), actor="analyst")
    assert service.run_pending_freezes() == 1
    failed = service.freeze_job(case["id"], job["job_id"])
    assert failed["status"] == "FAILED" and failed["error"] == {"code": "DELIVERABLE_RENDER_FAILED"}
    assert failed["deliverable_id"] is None, "no published digest"
    assert service.workspace(case["id"], "FULL_CREDIT")["frozen"] == []
    assert [p for p in (tmp_path / "vault").rglob("*.pdf")] == []
    monkeypatch.undo()
    retried = service.freeze(case["id"], freeze_request(revision), actor="analyst")
    assert retried["status"] == "QUEUED" and service.run_pending_freezes() == 1
    assert service.frozen_record_for_job(case["id"], job["job_id"])["status"] == "FROZEN"


# --- SIM-030: repeated restart loop during active work --------------------------------------------


async def test_sim_030_a_restart_loop_during_active_work_recovers_idempotently_and_bounded(tmp_path, settings, store):
    from caos.engine.graphs import compiled_route

    provider = FaultingHostControl()
    engine = _engine(tmp_path, settings, store, provider)
    try:
        _case, _source, run = await _start(engine, store)
        module_count = len(compiled_route("FULL_CREDIT", "full", settings.deploy_v_root).nodes)
        await engine.kill_after_modules_for_tests(run["id"], count=1)
    finally:
        await engine.aclose()
    for restart in range(2, module_count + 1):
        engine = _engine(tmp_path, settings, store, provider)
        try:
            engine._allow_placeholder_deterministic_for_tests(run["id"])
            await engine.recover()
            if engine.get_run(run["id"])["status"] == "running":
                await engine.kill_after_modules_for_tests(run["id"], count=restart)
            state = _state(engine, run["id"], tmp_path / "ck.db")
            assert state["terminal_events"] in ([], ["run.succeeded"])
            assert all(count == 1 for count in state["execution_counts"].values()), state["execution_counts"]
        finally:
            await engine.aclose()

    _revived, after = await _restart(tmp_path, settings, store, provider, run["id"])
    _assert_one_clean_success(after)
    assert set(after["execution_counts"]) == {module for module, _ in after["artifacts"]}
    assert after["budget_used"]["turns"] == len(provider.create_requests), "every restart's spend is on the ledger exactly once"


# --- SIM-020: membership changes during freeze or filing ------------------------------------


def test_sim_020_membership_revoked_between_authorization_and_commit_is_rejected_at_commit_time(tmp_path, settings, store, monkeypatch):
    """The route authorizes the approver, then their standing is revoked before
    the filing transaction commits. Commit-time authorization rejects the stale
    authority: nothing is filed, no receipt, no `deliverable.filed` audit row."""
    import sqlalchemy as sa

    from caos.api import create_app
    from caos.storage.store import case_members
    from fastapi.testclient import TestClient
    from test_deliverables_spec import draft_request, freeze_now, http_seed

    svc, case, source, template = http_seed(settings, store)
    revision = svc.save_draft(case["id"], "FULL_CREDIT", draft_request(template, source), actor="analyst")
    frozen = freeze_now(svc, case["id"], revision)
    store.add_member(case["id"], "analyst", "approver-user", "APPROVER", actor_role="ADMIN")
    approver = {"x-caos-role": "APPROVER", "x-forwarded-user": "approver-user"}
    body = {"preview_digest": frozen["preview_digest"], "input_fingerprint": frozen["input_fingerprint"]}

    from caos.deliverables import service as service_module

    real_file_record = service_module.DeliverableStore.file_record

    def revoke_then_file(self, deliverable_id, actor, audit, authorize=None):
        # The revocation lands after the route's check and before the CAS.
        with store.engine.begin() as conn:
            conn.execute(sa.delete(case_members).where(case_members.c.case_id == case["id"],
                                                       case_members.c.subject == actor))
        return real_file_record(self, deliverable_id, actor, audit, authorize)

    monkeypatch.setattr(service_module.DeliverableStore, "file_record", revoke_then_file)
    engine = _engine(tmp_path, settings, store, FaultingHostControl())
    try:
        app = create_app(settings=settings, store=store, engine=engine)
        with TestClient(app) as client:
            response = client.post(f"/api/cases/{case['id']}/deliverables/by-id/{frozen['deliverable_id']}/approve",
                                   json=body, headers=approver)
    finally:
        import asyncio

        asyncio.run(engine.aclose())
    assert response.status_code == 403, response.text
    assert response.json() == {"detail": {"code": "CASE_STANDING_REVOKED"}}
    record = svc.frozen_record(case["id"], frozen["deliverable_id"])
    assert record["status"] == "FROZEN" and record["filed_by"] is None, "nothing was filed with stale authority"
    assert svc.filing_receipts_for_tests(case["id"]) == []
    assert [e for e in svc.audit_events_for_tests(case["id"]) if e["action"] == "deliverable.filed"] == []
    assert store.verify_audit_chain() == {}


def test_sim_020_membership_revoked_between_authorization_and_freeze_commit_is_rejected(tmp_path, store, monkeypatch):
    """The freeze half of SIM-020: the analyst's standing is revoked after the
    route's check and before the freeze request commits; no job is queued."""
    import sqlalchemy as sa

    from caos.deliverables import service as service_module
    from caos.storage.store import case_members
    from test_deliverables_spec import freeze_request, make_service, save_min_draft, sign_min

    service = make_service(store, tmp_path / "vault")
    case, _source, _template, revision = save_min_draft(service, store)
    sign_min(service, case["id"], revision)
    real_request_freeze = service_module.DeliverableStore.request_freeze

    def revoke_then_request(self, frozen_record, actor, audit, authorize=None):
        with store.engine.begin() as conn:
            conn.execute(sa.delete(case_members).where(case_members.c.case_id == case["id"],
                                                       case_members.c.subject == actor))
        return real_request_freeze(self, frozen_record, actor, audit, authorize)

    monkeypatch.setattr(service_module.DeliverableStore, "request_freeze", revoke_then_request)
    with pytest.raises(ValueError, match="CASE_STANDING_REVOKED"):
        service.freeze(case["id"], freeze_request(revision), actor="analyst")
    assert service.records.pending_freeze_jobs(case["id"]) == [], "no job was queued with stale authority"
    assert [e for e in service.audit_events_for_tests(case["id"]) if e["action"] == "deliverable.freeze_queued"] == []
    assert store.verify_audit_chain() == {}
