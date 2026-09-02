"""The development-only host-control provider binding (DECISIONS §14 D8).

It exists so the browser gates (workbench smoke, accessibility sweep) can drive
an ordinary run without a provider key. It is orchestration proof only: its
identity is `host_control`, production refuses it, and nothing it produces is
live-model qualification (§14.6).
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parents[1] / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from caos.config import Settings  # noqa: E402
from caos.storage.store import DomainStore  # noqa: E402


def _seed(store: DomainStore):
    case = store.create_case("Northwind", "Northwind Holdings", "Services", "analyst")
    body = b"annual report revenue 1,000 adjusted EBITDA 200 total debt 600 cash 100"
    source = store.ingest({
        "case_id": case["id"], "filename": "annual.txt", "media_type": "text/plain",
        "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "vault_path": None,
        "blocks": [{
            "block_id": "b00001", "locator": {"line": 1}, "text": body.decode(),
            "extractor_version": "builtin-v1", "confidence": "MEDIUM", "untrusted_data": True,
        }],
        "withdrawn": False,
    }, "analyst")
    return case, source


def test_build_provider_binds_host_control_in_development_only(monkeypatch):
    sys.path.insert(0, str(SERVER))
    from run import build_provider
    from caos.engine.host_control import HostControlProvider
    from caos.engine.provider import AgentError

    development = Settings(environment="development", agent_execution_enabled=True, provider_binding="host_control")
    provider = build_provider(development)
    assert isinstance(provider, HostControlProvider)
    assert provider.identity.provider_name == "host_control"
    assert provider.identity.qualification_status == "host_control"

    with pytest.raises(AgentError) as refused:
        build_provider(Settings(environment="production", agent_execution_enabled=True,
                                provider_binding="host_control", anthropic_api_key="key"))
    assert refused.value.code == "AGENT_PROVIDER_UNQUALIFIED"
    assert build_provider(Settings(environment="development", agent_execution_enabled=False,
                                   provider_binding="host_control")) is None


def test_settings_reject_host_control_outside_development(monkeypatch):
    monkeypatch.setenv("CAOS_PROVIDER", "host_control")
    assert Settings.from_env().provider_binding == "host_control"
    monkeypatch.setenv("CAOS_PROVIDER", "anything-else")
    with pytest.raises(RuntimeError, match="CAOS_PROVIDER"):
        Settings.from_env()
    with pytest.raises(RuntimeError, match="CAOS_PROVIDER"):
        Settings(environment="production", provider_binding="host_control",
                 database_url="postgresql://caos:real-secret-value@db/caos").validate_worker_runtime()


async def test_host_control_provider_completes_an_ordinary_run_that_can_be_accepted(tmp_path):
    from caos.engine.host_control import HostControlProvider
    from caos.engine.runtime import Engine

    store = DomainStore.from_url(f"sqlite:///{tmp_path / 'caos.db'}")
    engine = None
    try:
        case, source = _seed(store)
        provider = HostControlProvider()
        engine = Engine.create(
            settings=Settings(storage_dir=tmp_path / "vault", agent_execution_enabled=True),
            store=store, checkpoint_path=tmp_path / "checkpoints.db", provider=provider,
        )
        for pathway, depth in (("EARNINGS_UPDATE", "screen"), ("FULL_CREDIT", "full")):
            started = await engine.start_run(case_id=case["id"], pathway=pathway, depth=depth, actor="analyst")
            completed = await engine.wait(started["id"])
            assert completed["status"] == "succeeded", (pathway, depth, completed.get("error"))
            artifacts = engine.artifacts_for_run(started["id"])
            assert {a["module_id"] for a in artifacts} == {n["module_id"] for n in completed["nodes"]}
            for artifact in artifacts:
                refs = artifact["payload"]["evidence_refs"]
                assert refs and all(ref["source_id"] == source["id"] for ref in refs)
                assert artifact["payload"]["provider_identity"]["provider_name"] == "host_control"
                assert artifact["payload"]["calculation_limitations"] == []
            snapshot = await engine.accept(started["id"], actor="analyst")
            assert snapshot["run_id"] == started["id"]
    finally:
        if engine is not None:
            await engine.aclose()
        store.close()
