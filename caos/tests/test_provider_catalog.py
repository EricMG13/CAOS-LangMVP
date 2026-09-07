"""Catalog switching preserves the provider fixed at admission and candidate authority."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from caos.config import Settings
from caos.contracts import digest
from caos.engine.catalog import ProviderCatalog, load_catalog, require_production_qualification
from caos.engine.host_control import HostControlProvider
from caos.engine.provider import AgentError, ProviderIdentity, ProviderQualification, host_control_identity, methodology_binding
from caos.engine.runtime import Engine, EngineError


def catalog_entry(binding_id, name, model):
    return {"id": binding_id, "provider": name, "model": model, "credential_env": f"TEST_{name.upper()}_KEY",
            "account_policy": "enterprise-policy-v1", "parameters": {}, "qualification_path": None, "qualification_digest": ""}


async def test_explicit_catalog_allows_both_credentials_without_provider_precedence(tmp_path, monkeypatch):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"schema_version": "caos.provider-catalog.v1", "default_binding_id": "claude",
                                "bindings": [catalog_entry("claude", "anthropic", "configured-claude"),
                                             catalog_entry("gpt", "openai", "configured-gpt")]}))
    monkeypatch.setenv("TEST_ANTHROPIC_KEY", "inert-anthropic-key")
    monkeypatch.setenv("TEST_OPENAI_KEY", "inert-openai-key")
    value = load_catalog(Settings(provider_catalog_path=path, agent_execution_enabled=True))
    try:
        assert value.resolve("claude").identity.provider_name == "anthropic"
        assert value.resolve("gpt").identity.provider_name == "openai"
        assert all(row["available"] for row in value.view())
        wire = json.dumps(value.view())
        assert "inert-" not in wire and "credential_env" not in wire and "account_policy" not in wire
    finally:
        await value.aclose()


async def test_whitespace_catalog_credential_is_unavailable_before_client_allocation(tmp_path, monkeypatch):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"schema_version": "caos.provider-catalog.v1", "default_binding_id": "claude",
                                "bindings": [catalog_entry("claude", "anthropic", "configured-claude")]}))
    monkeypatch.setenv("TEST_ANTHROPIC_KEY", "   ")
    catalog = load_catalog(Settings(provider_catalog_path=path, agent_execution_enabled=True))
    assert not catalog.bindings and not catalog.view()[0]["available"]
    assert catalog.view()[0]["unavailable_code"] == "AGENT_PROVIDER_UNAVAILABLE"
    await catalog.aclose()


@pytest.mark.parametrize("entry", [
    {**catalog_entry("a", "openai", "m"), "provider": []},
    {**catalog_entry("a", "openai", "m"), "model": "x" * 161},
    {**catalog_entry("a", "openai", "m"), "id": "../escape"},
    {**catalog_entry("a", "openai", "m"), "extra": "credential"},
])
def test_invalid_catalog_entries_fail_before_adapter_creation(tmp_path, entry):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"schema_version": "caos.provider-catalog.v1", "default_binding_id": "a", "bindings": [entry]}))
    with pytest.raises(AgentError):
        load_catalog(Settings(provider_catalog_path=path))


async def test_switch_and_restart_keep_old_run_and_upgrade_on_original_binding(tmp_path, store):
    from test_host_control_provider import _seed

    settings = Settings(storage_dir=tmp_path / "vault", agent_execution_enabled=True)
    first, second = HostControlProvider(), HostControlProvider()
    first.identity = host_control_identity(adapter_version="test.first")
    second.identity = host_control_identity(adapter_version="test.second")
    catalog = ProviderCatalog({"first": first, "second": second}, "first", settings=settings)
    checkpoint = tmp_path / "checkpoints.db"
    engine = Engine.create(settings=settings, store=store, checkpoint_path=checkpoint, provider=catalog)
    case, _source = _seed(store)
    old = await engine.start_run(case_id=case["id"], pathway="EARNINGS_UPDATE", depth="screen", actor="analyst")
    assert old["provider_identity"] == first.identity.as_dict()
    store.set_provider_default("second", "operator", 0, "first")
    assert engine.provider_catalog()["default_binding_id"] == "second"
    await engine.aclose()
    revived = Engine.create(settings=settings, store=store, checkpoint_path=checkpoint, provider=catalog)
    try:
        await revived.recover()
        complete = await revived.wait(old["id"])
        assert complete["status"] == "succeeded", complete.get("error")
        assert first.calls > 0 and second.calls == 0
        accepted = await revived.accept(old["id"], actor="analyst")
        assert accepted["provider_identity"] == first.identity.as_dict()
        upgraded = await revived.upgrade(old["id"], actor="analyst")
        assert upgraded["provider_identity"] == first.identity.as_dict()
        new = await revived.start_run(case_id=case["id"], pathway="EARNINGS_UPDATE", depth="screen", actor="analyst")
        assert new["provider_identity"] == second.identity.as_dict()
        assert revived._provider_for_identity(first.identity) is first
        assert revived._provider_for_identity(second.identity) is second
        revoked = ProviderCatalog({"second": second}, "second", settings=settings)
        with pytest.raises(AgentError, match="AGENT_IDENTITY_MISMATCH"):
            revoked.for_identity(first.identity)
    finally:
        await revived.aclose()
        await catalog.aclose()


async def test_missing_selected_binding_refuses_before_run_persistence(tmp_path, store):
    from test_host_control_provider import _seed

    settings = Settings(agent_execution_enabled=True)
    unavailable = {"absent": {"id": "absent", "provider_name": "openai", "model": "model",
                                "available": False, "status": "unavailable", "unavailable_code": "AGENT_QUALIFICATION_MISSING"}}
    catalog = ProviderCatalog({}, "absent", settings=settings, unavailable=unavailable)
    engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "empty.db", provider=catalog)
    case, _source = _seed(store)
    try:
        with pytest.raises(EngineError, match="AGENT_QUALIFICATION_MISSING"):
            engine.validate_provider_binding("absent")
        with pytest.raises(EngineError, match="AGENT_PROVIDER_UNAVAILABLE"):
            engine.validate_provider_binding("unknown")
        with pytest.raises(EngineError, match="AGENT_QUALIFICATION_MISSING"):
            await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst")
        assert engine.runs.active_admission_count() == 0
    finally:
        await engine.aclose()


def test_v2_candidate_binding_is_exact_and_v1_is_readable_but_ineligible():
    from test_provider_identity import _record

    legacy = ProviderQualification.from_record(_record())
    record = _record(schema_version="caos.provider-qualification.v2", candidate_commit="a" * 40,
                     image_set_digest="b" * 64, corpus_digest="c" * 64)
    qualified = ProviderQualification.from_record(record)
    expected = {key: record[key] for key in ("candidate_commit", "image_set_digest", "corpus_digest")}
    qualified.validate_candidate(**expected)
    for key in expected:
        with pytest.raises(AgentError, match="AGENT_PROVIDER_UNQUALIFIED"):
            qualified.validate_candidate(**{**expected, key: "d" * len(expected[key])})
    with pytest.raises(AgentError, match="AGENT_PROVIDER_UNQUALIFIED"):
        legacy.validate_candidate(**expected)
    assert qualified.record_digest == digest(record)
    for schema in ([], {}, None):
        with pytest.raises(AgentError, match="AGENT_PROVIDER_UNQUALIFIED"):
            ProviderQualification.from_record({**record, "schema_version": schema})


async def test_catalog_closes_every_owned_port_once_even_after_a_close_failure():
    class Port:
        def __init__(self, fail=False):
            self.identity = host_control_identity(adapter_version=f"test.{fail}")
            self.fail, self.calls = fail, 0

        async def aclose(self):
            self.calls += 1
            if self.fail and self.calls == 1:
                raise RuntimeError("close failed")

    first, second = Port(True), Port()
    catalog = ProviderCatalog({"a": first, "b": second}, "a", settings=Settings())
    with pytest.raises(RuntimeError):
        await catalog.aclose()
    await catalog.aclose()
    await catalog.aclose()
    assert (first.calls, second.calls) == (2, 1)


def test_candidate_authority_and_expiry_are_rechecked_for_selection():
    from test_provider_identity import _record

    build, manifest = methodology_binding(Settings().deploy_v_root)
    record = _record(schema_version="caos.provider-qualification.v2", provider_name="openai", candidate_commit="a" * 40,
                     image_set_digest="b" * 64, corpus_digest="c" * 64,
                     methodology_build_id=build, methodology_manifest_digest=manifest)
    qualification = ProviderQualification.from_record(record)
    identity = ProviderIdentity(provider_name=record["provider_name"], model=record["model"],
                                provider_version=record["provider_version"], adapter_version=record["adapter_version"],
                                parameter_context_digest=record["parameter_context_digest"], qualification_status="qualified",
                                qualification_record_id=qualification.record_id, qualification_record_digest=qualification.record_digest,
                                qualification_expires_at=qualification.expires_at)
    settings = Settings(environment="production", candidate_commit="a" * 40, image_set_digest="b" * 64, corpus_digest="c" * 64)
    port = SimpleNamespace(identity=identity, qualification=qualification, account_policy="enterprise-policy-v1")
    require_production_qualification(port, settings)
    with pytest.raises(AgentError, match="AGENT_PROVIDER_UNQUALIFIED"):
        require_production_qualification(port, replace(settings, candidate_commit="d" * 40))
    with pytest.raises(AgentError, match="approved account-policy"):
        require_production_qualification(SimpleNamespace(identity=identity, qualification=qualification), settings)
    port.identity = replace(identity, model="different-model")
    with pytest.raises(AgentError, match="AGENT_PROVIDER_UNQUALIFIED"):
        require_production_qualification(port, settings)
    port.identity = replace(identity, qualification_expires_at=(datetime.now(UTC) - timedelta(seconds=1)).isoformat())
    with pytest.raises(AgentError, match="AGENT_QUALIFICATION_EXPIRED"):
        require_production_qualification(port, settings)


def test_catalog_captures_port_identity_once_and_freezes_binding_selection():
    class Port:
        accesses = 0

        @property
        def identity(self):
            self.accesses += 1
            return host_control_identity()

    port = Port()
    bindings = {"first": port}
    catalog = ProviderCatalog(bindings, "first", settings=Settings(agent_execution_enabled=True))
    bindings.clear()
    assert catalog.resolve("first") is port
    assert catalog.for_identity(host_control_identity()) is port
    assert catalog.view()[0]["available"]
    assert port.accesses == 1
    with pytest.raises(TypeError):
        catalog.bindings["first"] = object()


async def test_real_engine_provider_policy_api_requires_operator_and_preserves_cas(tmp_path, store):
    from fastapi.testclient import TestClient
    from caos.api import create_app
    from test_provider_identity import _record

    settings = Settings(environment="production", edge_proxy_secret="test-edge", enterprise_operator_subjects=("operator",),
                        agent_execution_enabled=True, candidate_commit="a" * 40, image_set_digest="b" * 64, corpus_digest="c" * 64)
    build, manifest = methodology_binding(settings.deploy_v_root)
    def port(name):
        record = _record(schema_version="caos.provider-qualification.v2", provider_name=name, candidate_commit="a" * 40,
                         image_set_digest="b" * 64, corpus_digest="c" * 64,
                         methodology_build_id=build, methodology_manifest_digest=manifest)
        qualification = ProviderQualification.from_record(record)
        identity = ProviderIdentity(provider_name=name, model=record["model"], provider_version=record["provider_version"],
                                    adapter_version=record["adapter_version"], parameter_context_digest=record["parameter_context_digest"],
                                    qualification_status="qualified", qualification_record_id=qualification.record_id,
                                    qualification_record_digest=qualification.record_digest, qualification_expires_at=qualification.expires_at)
        return SimpleNamespace(identity=identity, qualification=qualification, account_policy="enterprise-policy-v1",
                               api_key="private-provider-credential")
    unavailable = {"missing": {"id": "missing", "provider_name": "openai", "model": "missing-model", "available": False,
                                "status": "unavailable", "unavailable_code": "AGENT_QUALIFICATION_MISSING"}}
    catalog = ProviderCatalog({"claude": port("anthropic"), "gpt": port("openai")}, "claude", settings=settings, unavailable=unavailable)
    engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "api.db", provider=catalog)
    auth = {"x-edge-authorization": "test-edge", "x-forwarded-user": "operator", "x-forwarded-groups": "caos-admin"}
    try:
        with TestClient(create_app(settings=settings, store=store, engine=engine)) as client:
            for headers in ({}, {**auth, "x-forwarded-user": "ordinary-admin"}, {**auth, "x-forwarded-groups": "caos-analyst"}):
                assert client.get("/api/admin/providers", headers=headers).status_code in {401, 403}
                assert client.post("/api/admin/provider-default", headers=headers,
                                   json={"binding_id": "gpt", "expected_version": 0}).status_code in {401, 403}
            response = client.get("/api/admin/providers", headers=auth)
            assert response.status_code == 200, response.text
            assert response.json()["default_binding_id"] == "claude" and response.json()["version"] == 0
            assert "private-provider-credential" not in response.text and "qualification_record_digest" not in response.text
            switched = client.post("/api/admin/provider-default", headers=auth, json={"binding_id": "gpt", "expected_version": 0})
            assert switched.status_code == 200 and switched.json()["default_binding_id"] == "gpt" and switched.json()["version"] == 1
            stale = client.post("/api/admin/provider-default", headers=auth, json={"binding_id": "claude", "expected_version": 0})
            assert stale.status_code == 409 and stale.json()["detail"]["code"] == "PROVIDER_POLICY_STALE"
            refused = client.post("/api/admin/provider-default", headers=auth, json={"binding_id": "missing", "expected_version": 1})
            assert refused.status_code == 503 and refused.json()["detail"]["code"] == "AGENT_QUALIFICATION_MISSING"
            assert engine.provider_catalog()["default_binding_id"] == "gpt"
            assert len([row for row in store.audit_trail() if row["action"] == "provider.default_changed"]) == 1
    finally:
        await engine.aclose()
        await catalog.aclose()
