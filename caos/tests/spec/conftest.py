"""Spec-suite fixtures: the future API surface, pinned before it exists.

Every import of an unbuilt module happens inside a fixture or test body, so each
spec test fails individually (ModuleNotFoundError / AttributeError) instead of
killing collection. These names ARE the specification of the build:

    caos.api.create_app(settings, store=..., engine=...) -> FastAPI
    caos.engine.runtime.Engine        — .create(...), .start_run, .resume,
                                        .approve_filing, .accept, .get_run,
                                        .events_after(run_id, after_seq)
    caos.engine.provider              — ProviderRequest/Message/Block/Usage port
                                        (the legacy port shape survives; the
                                        gateway does not)
    caos.engine.budget                — constants + route_envelope(plan, registry)
    caos.engine.evidence              — the read_evidence host boundary
    caos.engine.state                 — RunState schema, pin helpers
    caos.modules.registry             — MODULES, resolve_alias()
    caos.methodology.canonical        — ported validators + canonicalize
    caos.models  (engine/service)     — CP-MODEL chain
    caos.deliverables (service/graph) — drafts, freeze, filing gate
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parents[2] / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from caos.config import Settings  # noqa: E402  (exists: phase 2)
from caos.storage.store import DomainStore  # noqa: E402  (exists: phase 2)


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(storage_dir=tmp_path / "vault", agent_execution_enabled=True)


@pytest.fixture()
def store(tmp_path: Path) -> DomainStore:
    return DomainStore.from_url(f"sqlite:///{tmp_path / 'caos.db'}")


from spec_helpers import ScriptedProvider, seed_case_with_source  # noqa: E402,F401


@pytest.fixture()
def provider() -> ScriptedProvider:
    return ScriptedProvider()


@pytest.fixture()
def engine(tmp_path: Path, settings: Settings, store: DomainStore, provider: ScriptedProvider):
    from caos.engine.runtime import Engine

    return Engine.create(
        settings=settings,
        store=store,
        checkpoint_path=tmp_path / "checkpoints.db",
        provider=provider,
    )


@pytest.fixture()
def app(settings: Settings, store: DomainStore, engine):
    from caos.api import create_app

    return create_app(settings=settings, store=store, engine=engine)


@pytest.fixture()
def client(app):
    from fastapi.testclient import TestClient

    return TestClient(app)
