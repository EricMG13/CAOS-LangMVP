"""Production entrypoints refuse duplicate app and worker replicas."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa

import dev
import run
import worker
from caos.storage import store as store_module
from caos.storage.store import DomainStore


def _qualified_anthropic_settings(tmp_path: Path, **record_overrides):
    from caos.config import Settings
    from caos.contracts import digest
    from caos.engine.anthropic import ADAPTER_VERSION
    from caos.engine.provider import (
        installed_dependencies,
        methodology_binding,
        parameter_context_digest,
    )

    settings = Settings(
        environment="production",
        database_url="postgresql://caos:real-password@db/caos",
        storage_dir=tmp_path,
        edge_proxy_secret="edge-secret-that-is-long-enough-000000",
        session_secret="session-secret-that-is-long-enough-000",
        anthropic_api_key="inert-anthropic-key",
        agent_execution_enabled=True,
    )
    context_digest = parameter_context_digest(
        provider_name="anthropic", model=settings.anthropic_model, provider_version=None,
        adapter_version=ADAPTER_VERSION,
        runtime_dependencies=installed_dependencies("langchain-anthropic", "anthropic"),
        transport={"mode": "anthropic-messages"},
        counting={"mode": "provider-count-tokens"},
    )
    build_id, manifest_digest = methodology_binding(settings.deploy_v_root)
    now = datetime.now(UTC).replace(microsecond=0)
    record = {
        "schema_version": "caos.provider-qualification.v1",
        "record_id": "qualification-startup-1",
        "status": "qualified",
        "provider_name": "anthropic",
        "model": settings.anthropic_model,
        "provider_version": None,
        "adapter_version": ADAPTER_VERSION,
        "parameter_context_digest": context_digest,
        "methodology_build_id": build_id,
        "methodology_manifest_digest": manifest_digest,
        "qualified_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(days=1)).isoformat(),
        "evidence_digest": "e" * 64,
    }
    record.update(record_overrides)
    path = tmp_path / "provider-qualification.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    return replace(
        settings,
        provider_qualification_path=path,
        provider_qualification_digest=digest(record),
    )


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
    try:
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
    finally:
        store.engine.dispose()


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

    try:
        monkeypatch.setattr(store_module.threading.Thread, "start", fail_start)
        with pytest.raises(RuntimeError, match="thread unavailable"):
            with store.single_instance("app"):
                pass

        assert not held
    finally:
        store.engine.dispose()


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

    def close(self) -> None:
        pass


def _settings(tmp_path: Path):
    return SimpleNamespace(
        environment="production", database_url="", storage_dir=tmp_path, port=8000,
        validate_runtime=lambda: None,
        validate_worker_runtime=lambda: None,
    )


async def _noop() -> None:
    pass


def test_provider_assembly_is_inert_when_agent_execution_is_disabled():
    from caos.config import Settings

    settings = Settings(
        environment="production",
        anthropic_api_key="anthropic-key",
        agent_execution_enabled=False,
    )

    assert run.build_provider(settings) is None


@pytest.mark.parametrize(
    ("settings_overrides", "code"),
    [
        ({"openrouter_api_key": "openrouter-key"}, "AGENT_PROVIDER_UNQUALIFIED"),
        ({"anthropic_api_key": "anthropic-key", "openrouter_api_key": "openrouter-key"},
         "AGENT_PROVIDER_UNQUALIFIED"),
        ({"provider_qualification_path": Path("qualification.json")},
         "AGENT_QUALIFICATION_MISSING"),
        ({"provider_qualification_digest": "a" * 64}, "AGENT_QUALIFICATION_MISSING"),
    ],
)
def test_disabled_production_still_rejects_unsafe_provider_configuration(
    settings_overrides, code,
):
    from caos.config import Settings
    from caos.engine.provider import AgentError

    settings = replace(Settings(environment="production"), **settings_overrides)
    with pytest.raises(AgentError) as excinfo:
        run.build_provider(settings)
    assert excinfo.value.code == code


def test_enabled_provider_assembly_rejects_ambiguous_credentials():
    from caos.config import Settings
    from caos.engine.provider import AgentError

    settings = Settings(
        anthropic_api_key="anthropic-key",
        openrouter_api_key="openrouter-key",
        agent_execution_enabled=True,
    )
    with pytest.raises(AgentError) as excinfo:
        run.build_provider(settings)
    assert excinfo.value.code == "AGENT_PROVIDER_UNQUALIFIED"


@pytest.mark.parametrize(
    ("settings_overrides", "code"),
    [
        ({}, "AGENT_PROVIDER_UNAVAILABLE"),
        ({"openrouter_api_key": "openrouter-key"}, "AGENT_PROVIDER_UNQUALIFIED"),
        ({"anthropic_api_key": "   "}, "AGENT_PROVIDER_UNAVAILABLE"),
        ({"openrouter_api_key": "   "}, "AGENT_PROVIDER_UNAVAILABLE"),
        ({"anthropic_api_key": "   ", "openrouter_api_key": "   "},
         "AGENT_PROVIDER_UNAVAILABLE"),
    ],
)
def test_production_enabled_provider_accepts_no_fallback(settings_overrides, code):
    from caos.config import Settings
    from caos.engine.provider import AgentError

    settings = replace(
        Settings(environment="production", agent_execution_enabled=True),
        **settings_overrides,
    )
    with pytest.raises(AgentError) as excinfo:
        run.build_provider(settings)
    assert excinfo.value.code == code


@pytest.mark.parametrize(
    ("path", "record_digest"),
    [(None, ""), (Path("qualification.json"), ""), (None, "a" * 64)],
)
def test_production_anthropic_requires_the_complete_qualification_pair(path, record_digest):
    from caos.config import Settings
    from caos.engine.provider import AgentError

    settings = Settings(
        environment="production",
        anthropic_api_key="anthropic-key",
        agent_execution_enabled=True,
        provider_qualification_path=path,
        provider_qualification_digest=record_digest,
    )
    with pytest.raises(AgentError) as excinfo:
        run.build_provider(settings)
    assert excinfo.value.code == "AGENT_QUALIFICATION_MISSING"


@pytest.mark.parametrize(
    ("record_overrides", "code"),
    [
        ({"model": "different-model"}, "AGENT_PROVIDER_UNQUALIFIED"),
        ({
            "qualified_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "expires_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        },
         "AGENT_QUALIFICATION_EXPIRED"),
    ],
)
def test_production_anthropic_rejects_unbound_or_expired_qualification(
    tmp_path, record_overrides, code,
):
    from caos.engine.provider import AgentError

    settings = _qualified_anthropic_settings(tmp_path, **record_overrides)
    with pytest.raises(AgentError) as excinfo:
        run.build_provider(settings)
    assert excinfo.value.code == code


async def test_production_builds_only_the_exact_qualified_anthropic_binding(tmp_path):
    settings = _qualified_anthropic_settings(tmp_path)
    provider = run.build_provider(settings)
    try:
        assert provider.identity.provider_name == "anthropic"
        assert provider.identity.model == settings.anthropic_model
        assert provider.identity.qualification_status == "qualified"
        assert provider.identity.qualification_record_digest == settings.provider_qualification_digest
    finally:
        await provider.aclose()


@pytest.mark.parametrize(
    ("settings_overrides", "provider_name"),
    [
        ({"anthropic_api_key": "anthropic-key"}, "anthropic"),
        ({"openrouter_api_key": "openrouter-key"}, "openrouter"),
    ],
)
async def test_development_allows_one_explicit_unqualified_binding(
    settings_overrides, provider_name,
):
    from caos.config import Settings

    provider = run.build_provider(replace(
        Settings(agent_execution_enabled=True), **settings_overrides,
    ))
    try:
        assert provider.identity.provider_name == provider_name
        assert provider.identity.qualification_status == "unqualified"
    finally:
        await provider.aclose()


async def test_engine_rejects_unqualified_production_bindings_but_allows_qualified_anthropic(
    tmp_path, settings, store,
):
    from caos.engine.provider import ProviderIdentity
    from caos.engine.runtime import Engine, EngineError

    production = replace(settings, environment="production")

    def identity(provider_name, status, *, expires_at=None):
        return ProviderIdentity(
            provider_name=provider_name,
            model="model-1",
            provider_version=None,
            adapter_version="adapter-1",
            parameter_context_digest="a" * 64,
            qualification_record_id="qualification-1" if status == "qualified" else None,
            qualification_record_digest="b" * 64 if status == "qualified" else None,
            qualification_status=status,
            qualification_expires_at=expires_at,
        )

    for invalid in (
        identity("openrouter", "unqualified"),
        identity("anthropic", "unqualified"),
    ):
        with pytest.raises(EngineError) as excinfo:
            Engine.create(
                settings=production,
                store=store,
                checkpoint_path=tmp_path / "production-authority.db",
                provider=SimpleNamespace(identity=invalid),
            )
        assert excinfo.value.code == "AGENT_PROVIDER_UNQUALIFIED"

    qualified_settings = _qualified_anthropic_settings(tmp_path)
    qualified_provider = run.build_provider(qualified_settings)
    engine = Engine.create(
        settings=qualified_settings, store=store,
        checkpoint_path=tmp_path / "production-authority.db",
        provider=qualified_provider,
    )
    try:
        with pytest.raises(EngineError) as excinfo:
            await engine.start_run_for_tests(
                case_id="case-never-created", pathway="FULL_CREDIT", depth="screen",
                actor="analyst", allow_placeholder_deterministic=True,
            )
        assert excinfo.value.code == "DETERMINISTIC_EXECUTOR_UNAVAILABLE"
    finally:
        await engine.aclose()
        await qualified_provider.aclose()


async def test_host_control_test_capabilities_reject_a_real_development_provider(tmp_path, store):
    from caos.config import Settings
    from caos.engine.runtime import Engine, EngineError

    settings = Settings(anthropic_api_key="inert-key", agent_execution_enabled=True)
    provider = run.build_provider(settings)
    engine = Engine.create(
        settings=settings, store=store, checkpoint_path=tmp_path / "development-provider.db",
        provider=provider,
    )
    try:
        with pytest.raises(EngineError, match="DETERMINISTIC_EXECUTOR_UNAVAILABLE"):
            await engine.start_run_for_tests(
                case_id="case-never-created", pathway="FULL_CREDIT", depth="screen",
                actor="analyst", allow_placeholder_deterministic=True,
            )
        with pytest.raises(EngineError, match="DETERMINISTIC_EXECUTOR_UNAVAILABLE"):
            await engine.run_scripted_for_tests("case-never-created")
        with pytest.raises(EngineError, match="DETERMINISTIC_EXECUTOR_UNAVAILABLE"):
            engine._allow_placeholder_deterministic_for_tests("run-never-created")
    finally:
        await engine.aclose()
        await provider.aclose()


def test_shared_app_build_validates_before_files_or_owned_resources(monkeypatch, tmp_path):
    from caos.config import Settings

    data = tmp_path / "must-not-exist"
    monkeypatch.setattr(
        run.DomainStore,
        "from_url",
        classmethod(lambda cls, _url: pytest.fail("store opened before validation")),
    )

    with pytest.raises(RuntimeError, match="ENVIRONMENT"):
        run.build(Settings(environment="invalid"), data)

    assert not data.exists()


async def test_shared_app_build_refuses_an_active_event_loop_before_owning_resources(
    monkeypatch, tmp_path,
):
    from caos.config import Settings

    data = tmp_path / "loop-must-not-exist"
    monkeypatch.setattr(
        run.DomainStore,
        "from_url",
        classmethod(lambda cls, _url: pytest.fail("store opened inside an active loop")),
    )

    with pytest.raises(RuntimeError, match="outside an active event loop"):
        run.build(Settings(), data)

    assert not data.exists()


def test_dev_entrypoint_cannot_bypass_production_validation(monkeypatch, tmp_path):
    from caos.config import Settings

    data = tmp_path / "dev-must-not-exist"
    monkeypatch.setattr(
        dev.Settings,
        "from_env",
        classmethod(lambda cls: Settings(environment="production")),
    )
    monkeypatch.setenv("CAOS_DATA_DIR", str(data))
    monkeypatch.setattr(dev, "serve", lambda *_args, **_kwargs: pytest.fail("invalid app served"))

    with pytest.raises(RuntimeError, match="ENVIRONMENT=development"):
        dev.main()

    assert not data.exists()


def test_production_entrypoint_cannot_boot_development_defaults(monkeypatch, tmp_path):
    from caos.config import Settings

    data = tmp_path / "production-must-not-exist"
    monkeypatch.setattr(run.Settings, "from_env", classmethod(lambda cls: Settings()))
    monkeypatch.setenv("CAOS_DATA_DIR", str(data))
    monkeypatch.setattr(run, "serve", lambda *_args, **_kwargs: pytest.fail("development app served"))

    with pytest.raises(RuntimeError, match="ENVIRONMENT=production"):
        run.main()

    assert not data.exists()


def test_app_entrypoint_holds_the_app_lock_while_serving(monkeypatch, tmp_path):
    tracker = _LockTracker()
    settings = _settings(tmp_path)
    engine = SimpleNamespace(store=tracker, provider=None)

    async def close_engine():
        pass

    engine.aclose = close_engine
    monkeypatch.setattr(run.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(run, "build", lambda _settings, _data: (object(), engine))
    monkeypatch.setattr(run, "serve", lambda *_args, **_kwargs: tracker.held == ["app"] or pytest.fail("app lock not held"))

    run.main()


def test_app_entrypoint_closes_unserved_resources_when_lock_acquisition_fails(monkeypatch, tmp_path):
    events = []

    class Store(_LockTracker):
        @contextmanager
        def single_instance(self, _role: str):
            raise RuntimeError("app lock refused")
            yield

        def close(self) -> None:
            events.append("store.close")

    class Provider:
        async def aclose(self) -> None:
            events.append("provider.close")

    class Engine:
        def __init__(self) -> None:
            self.store = Store()
            self.provider = Provider()

        async def aclose(self) -> None:
            events.append("engine.close")

    settings = _settings(tmp_path)
    engine = Engine()
    monkeypatch.setattr(run.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(run, "build", lambda _settings, _data: (object(), engine))
    monkeypatch.setattr(run, "serve", lambda *_args, **_kwargs: pytest.fail("app served without lock"))

    with pytest.raises(RuntimeError, match="app lock refused"):
        run.main()

    assert events == ["engine.close", "provider.close", "store.close"]


def test_worker_entrypoint_holds_the_worker_lock_while_polling(monkeypatch, tmp_path):
    tracker = _LockTracker()
    settings = _settings(tmp_path)
    validated = []
    settings.validate_worker_runtime = lambda: validated.append("worker")
    settings.validate_runtime = lambda: pytest.fail("worker used app validation")
    monkeypatch.setattr(worker.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(worker, "configure_logging", lambda _settings: None, raising=False)
    monkeypatch.setattr(worker.DomainStore, "from_url", classmethod(lambda cls, _url: tracker))
    async def close_engine():
        pass

    monkeypatch.setattr(worker.Engine, "create", classmethod(
        lambda cls, **_kwargs: SimpleNamespace(aclose=close_engine),
    ))
    monkeypatch.setattr(worker, "ModelService", lambda **_kwargs: object())
    monkeypatch.setattr(worker, "DeliverableService", lambda **_kwargs: SimpleNamespace(recover_freeze_jobs=lambda: 0))
    monkeypatch.setattr(worker, "run_pending", lambda *_services: tracker.held == ["worker"] or pytest.fail("worker lock not held"))
    monkeypatch.setattr(sys, "argv", ["worker.py", "--once"])

    worker.main()
    assert validated == ["worker"]


@pytest.mark.parametrize("raises", (False, True))
def test_app_entrypoint_closes_owned_resources_in_reverse_order(monkeypatch, tmp_path, raises):
    events = []
    loops = []

    class Store(_LockTracker):
        def close(self) -> None:
            events.append("store.close")

    class Provider:
        async def aclose(self) -> None:
            events.append("provider.close")
            loops.append(asyncio.get_running_loop())

    class Engine:
        def __init__(self) -> None:
            self.store = Store()
            self.provider = Provider()

        async def recover(self) -> None:
            pass

        async def aclose(self) -> None:
            events.append("engine.close")
            loops.append(asyncio.get_running_loop())

    settings = _settings(tmp_path)
    engine = Engine()
    monkeypatch.setattr(run.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(run, "build", lambda _settings, _data: (object(), engine))

    async def serve() -> None:
        events.append("serve")
        loops.append(asyncio.get_running_loop())
        if raises:
            raise RuntimeError("serve failed")

    monkeypatch.setattr(run.uvicorn, "Config", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(run.uvicorn, "Server", lambda _config: SimpleNamespace(serve=serve))
    if raises:
        with pytest.raises(RuntimeError, match="serve failed"):
            run.main()
    else:
        run.main()

    assert events[-3:] == ["engine.close", "provider.close", "store.close"]
    assert loops[0] is loops[1] is loops[2]


@pytest.mark.parametrize("raises", (False, True))
def test_worker_entrypoint_closes_owned_resources_in_reverse_order(monkeypatch, tmp_path, raises):
    events = []

    class Store(_LockTracker):
        def close(self) -> None:
            events.append("store.close")

    class Engine:
        async def aclose(self) -> None:
            events.append("engine.close")

    settings = _settings(tmp_path)
    store = Store()
    monkeypatch.setattr(worker.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(worker, "configure_logging", lambda _settings: None)
    monkeypatch.setattr(worker.DomainStore, "from_url", classmethod(lambda cls, _url: store))
    monkeypatch.setattr(worker.Engine, "create", classmethod(lambda cls, **_kwargs: Engine()))
    monkeypatch.setattr(worker, "ModelService", lambda **_kwargs: object())
    monkeypatch.setattr(worker, "DeliverableService", lambda **_kwargs: SimpleNamespace(recover_freeze_jobs=lambda: 0))
    monkeypatch.setattr(sys, "argv", ["worker.py", "--once"])

    def run_once(*_services) -> int:
        events.append("run")
        if raises:
            raise RuntimeError("worker failed")
        return 0

    monkeypatch.setattr(worker, "run_pending", run_once)
    if raises:
        with pytest.raises(RuntimeError, match="worker failed"):
            worker.main()
    else:
        worker.main()

    assert events[-2:] == ["engine.close", "store.close"]


def test_app_entrypoint_closes_store_when_provider_shutdown_fails(monkeypatch, tmp_path):
    events = []

    class Store(_LockTracker):
        def close(self) -> None:
            events.append("store.close")

    class Provider:
        async def aclose(self) -> None:
            events.append("provider.close")
            raise RuntimeError("provider close failed")

    class Engine:
        def __init__(self) -> None:
            self.store = Store()
            self.provider = Provider()

        async def recover(self) -> None:
            pass

        async def aclose(self) -> None:
            events.append("engine.close")

    settings = _settings(tmp_path)
    engine = Engine()
    monkeypatch.setattr(run.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(run, "build", lambda _settings, _data: (object(), engine))
    monkeypatch.setattr(run.uvicorn, "Config", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(run.uvicorn, "Server", lambda _config: SimpleNamespace(serve=_noop))

    with pytest.raises(RuntimeError, match="provider close failed"):
        run.main()

    assert events[-2:] == ["provider.close", "store.close"]


def test_app_entrypoint_preserves_service_failure_through_all_cleanup_failures(monkeypatch, tmp_path):
    events = []

    class Store(_LockTracker):
        def close(self) -> None:
            events.append("store.close")
            raise RuntimeError("store close failed")

    class Provider:
        async def aclose(self) -> None:
            events.append("provider.close")
            raise RuntimeError("provider close failed")

    class Engine:
        def __init__(self) -> None:
            self.store = Store()
            self.provider = Provider()

        async def recover(self) -> None:
            pass

        async def aclose(self) -> None:
            events.append("engine.close")
            raise RuntimeError("engine close failed")

    settings = _settings(tmp_path)
    engine = Engine()
    monkeypatch.setattr(run.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(run, "build", lambda _settings, _data: (object(), engine))

    async def fail_serve() -> None:
        raise RuntimeError("serve failed")

    monkeypatch.setattr(run.uvicorn, "Config", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(run.uvicorn, "Server", lambda _config: SimpleNamespace(serve=fail_serve))

    with pytest.raises(RuntimeError, match="serve failed"):
        run.main()

    assert events[-3:] == ["engine.close", "provider.close", "store.close"]


def test_app_entrypoint_preserves_engine_shutdown_failure(monkeypatch, tmp_path):
    events = []

    class Store(_LockTracker):
        def close(self) -> None:
            events.append("store.close")
            raise RuntimeError("store close failed")

    class Provider:
        async def aclose(self) -> None:
            events.append("provider.close")
            raise RuntimeError("provider close failed")

    class Engine:
        def __init__(self) -> None:
            self.store = Store()
            self.provider = Provider()

        async def recover(self) -> None:
            pass

        async def aclose(self) -> None:
            events.append("engine.close")
            raise RuntimeError("engine close failed")

    settings = _settings(tmp_path)
    engine = Engine()
    monkeypatch.setattr(run.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(run, "build", lambda _settings, _data: (object(), engine))
    monkeypatch.setattr(run.uvicorn, "Config", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(run.uvicorn, "Server", lambda _config: SimpleNamespace(serve=_noop))

    with pytest.raises(RuntimeError, match="engine close failed"):
        run.main()

    assert events[-3:] == ["engine.close", "provider.close", "store.close"]


def test_worker_entrypoint_preserves_poll_failure_through_cleanup_failures(monkeypatch, tmp_path):
    events = []

    class Store(_LockTracker):
        def close(self) -> None:
            events.append("store.close")
            raise RuntimeError("store close failed")

    class Engine:
        async def aclose(self) -> None:
            events.append("engine.close")
            raise RuntimeError("engine close failed")

    settings = _settings(tmp_path)
    store = Store()
    monkeypatch.setattr(worker.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(worker, "configure_logging", lambda _settings: None)
    monkeypatch.setattr(worker.DomainStore, "from_url", classmethod(lambda cls, _url: store))
    monkeypatch.setattr(worker.Engine, "create", classmethod(lambda cls, **_kwargs: Engine()))
    monkeypatch.setattr(worker, "ModelService", lambda **_kwargs: object())
    monkeypatch.setattr(worker, "DeliverableService", lambda **_kwargs: SimpleNamespace(recover_freeze_jobs=lambda: 0))
    monkeypatch.setattr(worker, "run_pending", lambda *_services: (_ for _ in ()).throw(RuntimeError("poll failed")))
    monkeypatch.setattr(sys, "argv", ["worker.py", "--once"])

    with pytest.raises(RuntimeError, match="poll failed"):
        worker.main()

    assert events[-2:] == ["engine.close", "store.close"]


def test_app_build_rolls_back_owned_store_and_provider_on_construction_failure(monkeypatch, tmp_path):
    events = []

    class Store:
        def close(self) -> None:
            events.append("store.close")

    class Provider:
        async def aclose(self) -> None:
            events.append("provider.close")

    settings = _settings(tmp_path)
    monkeypatch.setattr(run, "configure_logging", lambda _settings: None)
    monkeypatch.setattr(run.DomainStore, "from_url", classmethod(lambda cls, _url: Store()))
    monkeypatch.setattr(run, "build_provider", lambda _settings: Provider())
    monkeypatch.setattr(run.Engine, "create", classmethod(
        lambda cls, **_kwargs: (_ for _ in ()).throw(RuntimeError("engine construction failed")),
    ))

    with pytest.raises(RuntimeError, match="engine construction failed"):
        run.build(settings, tmp_path)

    assert events == ["provider.close", "store.close"]


def test_app_build_closes_owned_store_when_provider_qualification_fails(monkeypatch, tmp_path):
    from caos.config import Settings
    from caos.engine.provider import AgentError

    events = []

    class Store:
        def close(self) -> None:
            events.append("store.close")

    settings = Settings(
        storage_dir=tmp_path,
        database_url="postgresql://caos:real-password@db/caos",
        edge_proxy_secret="edge-secret-that-is-long-enough-000000",
        session_secret="session-secret-that-is-long-enough-000",
        anthropic_api_key="anthropic-key",
        agent_execution_enabled=True,
        environment="production",
    )
    monkeypatch.setattr(run, "configure_logging", lambda _settings: None)
    monkeypatch.setattr(run.DomainStore, "from_url", classmethod(lambda cls, _url: Store()))

    with pytest.raises(AgentError) as excinfo:
        run.build(settings, tmp_path)

    assert excinfo.value.code == "AGENT_QUALIFICATION_MISSING"
    assert events == ["store.close"]


def test_worker_construction_failure_closes_its_owned_store(monkeypatch, tmp_path):
    events = []

    class Store:
        def close(self) -> None:
            events.append("store.close")

    settings = _settings(tmp_path)
    monkeypatch.setattr(worker.Settings, "from_env", classmethod(lambda cls: settings))
    monkeypatch.setattr(worker, "configure_logging", lambda _settings: None)
    monkeypatch.setattr(worker.DomainStore, "from_url", classmethod(lambda cls, _url: Store()))
    monkeypatch.setattr(worker.Engine, "create", classmethod(
        lambda cls, **_kwargs: (_ for _ in ()).throw(RuntimeError("engine construction failed")),
    ))

    with pytest.raises(RuntimeError, match="engine construction failed"):
        worker.main()

    assert events == ["store.close"]
