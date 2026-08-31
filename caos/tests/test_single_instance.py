"""Production entrypoints refuse duplicate app and worker replicas."""

from __future__ import annotations

import os
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa

import run
import worker
from caos.storage import store as store_module
from caos.storage.store import DomainStore


def _postgres_lock_store(tmp_path: Path) -> tuple[DomainStore, set[tuple[int, int]]]:
    """SQLite UDFs model PostgreSQL's two-key session advisory-lock API."""
    held: set[tuple[int, int]] = set()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'locks.db'}", pool_size=4)

    @sa.event.listens_for(engine, "connect")
    def register_locks(connection, _record) -> None:
        def acquire(namespace: int, role: int) -> int:
            key = (namespace, role)
            if key in held:
                return 0
            held.add(key)
            return 1

        def release(namespace: int, role: int) -> int:
            key = (namespace, role)
            if key not in held:
                return 0
            held.remove(key)
            return 1

        connection.create_function("pg_try_advisory_lock", 2, acquire)
        connection.create_function("pg_advisory_unlock", 2, release)

    engine.dialect.name = "postgresql"
    return DomainStore(engine), held


def test_postgres_refuses_duplicate_roles_and_releases_locks_on_exit(tmp_path):
    store, held = _postgres_lock_store(tmp_path)
    lock = getattr(store, "single_instance", None)
    assert callable(lock), "the domain store must expose the production instance guard"

    with lock("app"), lock("worker"):
        with pytest.raises(RuntimeError, match="app instance is already running"):
            with lock("app"):
                pass
        with pytest.raises(RuntimeError, match="worker instance is already running"):
            with lock("worker"):
                pass

    assert not held
    with lock("app"):
        pass


class _ScalarResult:
    def __init__(self, value) -> None:
        self.value = value

    def scalar_one(self):
        return self.value


class _DroppedLockConnection:
    def __init__(self) -> None:
        self.invalidated = False
        self.unlock_called = False
        self.owner_thread: int | None = None

    def __enter__(self):
        self.owner_thread = threading.get_ident()
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, statement, _parameters=None):
        assert threading.get_ident() == self.owner_thread
        sql = str(statement)
        if "pg_try_advisory_lock" in sql:
            return _ScalarResult(True)
        if "pg_advisory_unlock" in sql:
            self.unlock_called = True
            return _ScalarResult(True)
        raise ConnectionError("lock session dropped")

    def commit(self) -> None:
        pass

    def invalidate(self) -> None:
        self.invalidated = True


def test_postgres_lock_session_loss_terminates_instead_of_running_unlocked(monkeypatch):
    terminated = threading.Event()
    connection = _DroppedLockConnection()
    engine = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql"),
        connect=lambda: connection,
    )
    monkeypatch.setattr(store_module, "_INSTANCE_LOCK_HEARTBEAT_SECONDS", 0.01, raising=False)
    monkeypatch.setattr(store_module, "_terminate_process", lambda _role: terminated.set(), raising=False)

    with DomainStore(engine).single_instance("app"):
        assert terminated.wait(0.25), "a lost advisory-lock session must fail the process closed"

    assert connection.invalidated
    assert not connection.unlock_called


def test_postgres_thread_start_failure_refuses_startup_without_taking_lock(monkeypatch, tmp_path):
    store, held = _postgres_lock_store(tmp_path)

    def fail_start(_thread):
        raise RuntimeError("thread unavailable")

    monkeypatch.setattr(store_module.threading.Thread, "start", fail_start)
    with pytest.raises(RuntimeError, match="thread unavailable"):
        with store.single_instance("app"):
            pass

    assert not held


def test_lock_loss_termination_cannot_be_blocked_by_logging(monkeypatch):
    exit_codes = []

    def fail_log(*_args):
        raise RuntimeError("logging failed")

    def exit_process(code):
        exit_codes.append(code)
        raise SystemExit(code)

    monkeypatch.setattr(store_module.logger, "critical", fail_log)
    monkeypatch.setattr(store_module.os, "_exit", exit_process)

    with pytest.raises(SystemExit) as stopped:
        store_module._terminate_process("app")

    assert exit_codes == [1]
    assert stopped.value.code == 1


@pytest.fixture
def postgres_url():
    url = os.getenv("CAOS_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("set CAOS_TEST_POSTGRES_URL to run PostgreSQL advisory-lock integration tests")
    return url


def test_real_postgres_refuses_duplicate_role_and_releases_on_exit(postgres_url):
    first_engine = sa.create_engine(postgres_url)
    second_engine = sa.create_engine(postgres_url)
    try:
        with DomainStore(first_engine).single_instance("app"):
            with DomainStore(second_engine).single_instance("worker"):
                pass
            with pytest.raises(RuntimeError, match="app instance is already running"):
                with DomainStore(second_engine).single_instance("app"):
                    pass

        with DomainStore(second_engine).single_instance("app"):
            pass
    finally:
        first_engine.dispose()
        second_engine.dispose()


def test_real_postgres_backend_loss_fails_closed(postgres_url, monkeypatch):
    terminated = threading.Event()
    application_name = f"caos-lock-test-{uuid4().hex}"
    owner_engine = sa.create_engine(
        postgres_url,
        connect_args={"application_name": application_name},
    )
    observer_engine = sa.create_engine(postgres_url)
    monkeypatch.setattr(store_module, "_INSTANCE_LOCK_HEARTBEAT_SECONDS", 0.01)
    monkeypatch.setattr(store_module, "_terminate_process", lambda _role: terminated.set())
    try:
        with DomainStore(owner_engine).single_instance("app"):
            with observer_engine.begin() as connection:
                owner_pid = connection.execute(
                    sa.text("SELECT pid FROM pg_stat_activity WHERE application_name = :name"),
                    {"name": application_name},
                ).scalar_one()
                assert connection.execute(
                    sa.text("SELECT pg_terminate_backend(:pid)"),
                    {"pid": owner_pid},
                ).scalar_one()

            assert terminated.wait(2), "losing the real PostgreSQL lock session must fail closed"
            with DomainStore(observer_engine).single_instance("app"):
                pass
    finally:
        owner_engine.dispose()
        observer_engine.dispose()


def test_sqlite_development_does_not_take_a_postgres_lock(store):
    lock = getattr(store, "single_instance", None)
    assert callable(lock), "the instance guard must preserve SQLite development"
    with lock("app"), lock("app"):
        pass


class _LockTracker:
    def __init__(self) -> None:
        self.held: list[str] = []

    @contextmanager
    def single_instance(self, role: str):
        self.held.append(role)
        try:
            yield
        finally:
            self.held.remove(role)


def _settings(tmp_path: Path):
    return SimpleNamespace(database_url="", storage_dir=tmp_path, port=8000, validate_runtime=lambda: None)


def test_app_entrypoint_holds_the_app_lock_while_serving(monkeypatch, tmp_path):
    tracker = _LockTracker()
    settings = _settings(tmp_path)
    engine = SimpleNamespace(store=tracker)
    monkeypatch.setattr(run.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(run, "build", lambda _settings, _data: (object(), engine))
    monkeypatch.setattr(run, "serve", lambda *_args, **_kwargs: tracker.held == ["app"] or pytest.fail("app lock not held"))

    run.main()


def test_worker_entrypoint_holds_the_worker_lock_while_polling(monkeypatch, tmp_path):
    tracker = _LockTracker()
    settings = _settings(tmp_path)
    monkeypatch.setattr(worker.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(worker.DomainStore, "from_url", classmethod(lambda cls, _url: tracker))
    monkeypatch.setattr(worker.Engine, "create", classmethod(lambda cls, **_kwargs: object()))
    monkeypatch.setattr(worker, "ModelService", lambda **_kwargs: object())
    monkeypatch.setattr(worker, "run_pending", lambda _service: tracker.held == ["worker"] or pytest.fail("worker lock not held"))
    monkeypatch.setattr(sys, "argv", ["worker.py", "--once"])

    worker.main()
