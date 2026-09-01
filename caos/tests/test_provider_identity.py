"""Task 5A's small, strict provider-identity boundary."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from caos.contracts import digest
from caos.engine.anthropic import ADAPTER_VERSION as ANTHROPIC_ADAPTER_VERSION, AnthropicProvider
from caos.engine.openrouter import ADAPTER_VERSION as OPENROUTER_ADAPTER_VERSION, OpenRouterProvider
from caos.engine.provider import (
    AgentError,
    ProviderIdentity,
    ProviderQualification,
    host_control_identity,
    parameter_context_metadata,
)


def _record(**overrides):
    now = datetime.now(UTC).replace(microsecond=0)
    record = {
        "schema_version": "caos.provider-qualification.v1",
        "record_id": "qualification-1",
        "status": "qualified",
        "provider_name": "anthropic",
        "model": "claude-sonnet-4-6",
        "provider_version": None,
        "adapter_version": ANTHROPIC_ADAPTER_VERSION,
        "parameter_context_digest": "a" * 64,
        "methodology_build_id": "deploy-v-test",
        "methodology_manifest_digest": "b" * 64,
        "qualified_at": (now - timedelta(days=1)).isoformat(),
        "expires_at": (now + timedelta(days=1)).isoformat(),
        "evidence_digest": "c" * 64,
    }
    record.update(overrides)
    return record


def test_provider_identity_is_frozen_and_detects_self_digest_tampering():
    identity = ProviderIdentity(
        provider_name="anthropic", model="claude-sonnet-4-6", provider_version=None,
        adapter_version=ANTHROPIC_ADAPTER_VERSION, parameter_context_digest="a" * 64,
        qualification_record_id=None, qualification_record_digest=None,
        qualification_status="unqualified", qualification_expires_at=None,
    )
    assert identity.identity_digest == digest({key: value for key, value in identity.as_dict().items() if key != "identity_digest"})
    with pytest.raises(FrozenInstanceError):
        identity.model = "other"  # type: ignore[misc]

    object.__setattr__(identity, "model", "other")
    with pytest.raises(AgentError, match="AGENT_IDENTITY_MISMATCH"):
        identity.verify()


def test_provider_identity_round_trip_rejects_persisted_tampering():
    identity = host_control_identity()
    assert ProviderIdentity.from_dict(identity.as_dict()) == identity

    tampered = {**identity.as_dict(), "model": "other"}
    with pytest.raises(AgentError, match="AGENT_IDENTITY_MISMATCH"):
        ProviderIdentity.from_dict(tampered)

    incomplete = identity.as_dict()
    incomplete.pop("qualification_status")
    with pytest.raises(AgentError, match="AGENT_IDENTITY_MISMATCH"):
        ProviderIdentity.from_dict(incomplete)


def test_parameter_context_has_exactly_host_owned_policy_fields():
    context = parameter_context_metadata(
        provider_name="anthropic", model="claude-sonnet-4-6", provider_version=None,
        adapter_version=ANTHROPIC_ADAPTER_VERSION, runtime_dependencies={"anthropic": "1"},
        transport={"mode": "anthropic-messages"}, counting={"mode": "provider-count-tokens"},
    )

    assert set(context) == {"provider", "adapter", "transport", "counting", "loop", "tool", "schema", "modules"}
    assert "prompt" not in json.dumps(context).lower()
    assert "secret" not in json.dumps(context).lower()


@pytest.mark.parametrize("change", [
    {"extra": "nope"},
    {"schema_version": "caos.provider-qualification.v2"},
    {"provider_version": 1},
    {"evidence_digest": "not-a-digest"},
    {"qualified_at": "not-a-time"},
])
def test_qualification_record_rejects_unknown_or_malformed_values(change):
    with pytest.raises(AgentError, match="AGENT_PROVIDER_UNQUALIFIED"):
        ProviderQualification.from_record(_record(**change))


def test_qualification_record_digest_and_binding_are_strict(tmp_path):
    record = _record()
    path = tmp_path / "qualification.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    qualification = ProviderQualification.from_path(path, digest(record))
    assert qualification.record_digest == digest(record)
    qualification.validate_binding(
        provider_name="anthropic", model="claude-sonnet-4-6", provider_version=None,
        adapter_version=ANTHROPIC_ADAPTER_VERSION,
        parameter_context_digest="a" * 64, methodology_build_id="deploy-v-test",
        methodology_manifest_digest="b" * 64,
    )
    with pytest.raises(AgentError, match="AGENT_PROVIDER_UNQUALIFIED"):
        qualification.validate_binding(
            provider_name="anthropic", model="other", provider_version=None,
            adapter_version=ANTHROPIC_ADAPTER_VERSION,
            parameter_context_digest="a" * 64, methodology_build_id="deploy-v-test",
            methodology_manifest_digest="b" * 64,
        )
    with pytest.raises(AgentError, match="AGENT_PROVIDER_UNQUALIFIED"):
        ProviderQualification.from_path(path, "0" * 64)
    path.write_text('{"schema_version":"duplicate","schema_version":"duplicate"}', encoding="utf-8")
    with pytest.raises(AgentError, match="AGENT_PROVIDER_UNQUALIFIED"):
        ProviderQualification.from_path(path, "0" * 64)


def test_qualification_binding_rechecks_record_integrity_and_provider_version():
    qualification = ProviderQualification.from_record(_record())
    object.__setattr__(qualification, "record_id", "changed-after-load")
    with pytest.raises(AgentError, match="AGENT_PROVIDER_UNQUALIFIED"):
        qualification.validate_binding(
            provider_name="anthropic", model="claude-sonnet-4-6", provider_version=None,
            adapter_version=ANTHROPIC_ADAPTER_VERSION, parameter_context_digest="a" * 64,
            methodology_build_id="deploy-v-test", methodology_manifest_digest="b" * 64,
        )

    versioned = ProviderQualification.from_record(_record(provider_version="provider-build-7"))
    with pytest.raises(AgentError, match="AGENT_PROVIDER_UNQUALIFIED"):
        versioned.validate_binding(
            provider_name="anthropic", model="claude-sonnet-4-6", provider_version=None,
            adapter_version=ANTHROPIC_ADAPTER_VERSION, parameter_context_digest="a" * 64,
            methodology_build_id="deploy-v-test", methodology_manifest_digest="b" * 64,
        )


@pytest.mark.parametrize(("record", "code"), [
    (_record(qualified_at=(datetime.now(UTC) + timedelta(minutes=1)).replace(microsecond=0).isoformat()), "AGENT_PROVIDER_UNQUALIFIED"),
    (_record(expires_at=(datetime.now(UTC) - timedelta(minutes=1)).replace(microsecond=0).isoformat()), "AGENT_QUALIFICATION_EXPIRED"),
])
def test_qualification_record_rejects_future_or_expired_bindings(record, code):
    qualification = ProviderQualification.from_record(record)
    with pytest.raises(AgentError) as excinfo:
        qualification.validate_binding(
            provider_name="anthropic", model="claude-sonnet-4-6", provider_version=None,
            adapter_version=ANTHROPIC_ADAPTER_VERSION,
            parameter_context_digest="a" * 64, methodology_build_id="deploy-v-test",
            methodology_manifest_digest="b" * 64,
        )
    assert excinfo.value.code == code


def test_qualification_rejects_a_naive_validation_clock():
    qualification = ProviderQualification.from_record(_record())
    with pytest.raises(AgentError, match="AGENT_PROVIDER_UNQUALIFIED"):
        qualification.validate_binding(
            provider_name="anthropic", model="claude-sonnet-4-6", provider_version=None,
            adapter_version=ANTHROPIC_ADAPTER_VERSION,
            parameter_context_digest="a" * 64, methodology_build_id="deploy-v-test",
            methodology_manifest_digest="b" * 64, now=datetime.now(),
        )


async def test_adapter_identities_are_truthful_immutable_and_do_not_leak_keys():
    anthropic = AnthropicProvider("anthropic-secret", "claude-sonnet-4-6")
    openrouter = OpenRouterProvider("openrouter-secret", "z-ai/glm-5.3-flash")
    try:
        assert anthropic.identity.provider_name == "anthropic"
        assert anthropic.identity.adapter_version == ANTHROPIC_ADAPTER_VERSION
        assert anthropic.identity.qualification_status == "unqualified"
        assert openrouter.identity.provider_name == "openrouter"
        assert openrouter.identity.adapter_version == OPENROUTER_ADAPTER_VERSION
        assert openrouter.identity.qualification_status == "unqualified"
        assert "secret" not in json.dumps([anthropic.identity.as_dict(), openrouter.identity.as_dict()])
        with pytest.raises(FrozenInstanceError):
            openrouter.identity.model = "other"  # type: ignore[misc]
    finally:
        await anthropic.aclose()
        await openrouter.aclose()


def test_openrouter_refuses_a_qualification_claim_and_host_control_is_explicit():
    qualification = ProviderQualification.from_record(_record())
    with pytest.raises(AgentError, match="AGENT_PROVIDER_UNQUALIFIED"):
        OpenRouterProvider("key", "model", qualification=qualification)
    assert host_control_identity().qualification_status == "host_control"
