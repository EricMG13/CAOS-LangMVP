"""Provider port: the legacy transport shape survives; the gateway does not.

The engine talks to this port only. Production binds it to an adapter built on
langchain-anthropic's pinned client (see anthropic.AnthropicProvider); tests
bind a scripted double. Nothing here is copied from LEGACY workflows/provider.py — the
dataclass port shape is the recorded surviving contract (DECISIONS §5).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Mapping, Protocol

from ..contracts import digest


READ_EVIDENCE_TOOL = {
    "name": "read_evidence",
    "description": "Read exact blocks from the run's pinned supplied evidence set.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "source_id": {"type": "string"},
            "block_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["source_id", "block_ids"],
        "additionalProperties": False,
    },
}


class AgentError(RuntimeError):
    """Typed agent failure; .code carries the legacy taxonomy string verbatim."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {message}" if message else code)


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,159}$")
QUALIFICATION_SCHEMA_VERSION = "caos.provider-qualification.v1"
_QUALIFICATION_FIELDS = frozenset({
    "schema_version", "record_id", "status", "provider_name", "model",
    "provider_version", "adapter_version", "parameter_context_digest",
    "methodology_build_id", "methodology_manifest_digest", "qualified_at",
    "expires_at", "evidence_digest",
})


def _sha256(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise AgentError("AGENT_PROVIDER_UNQUALIFIED", f"malformed qualification {field_name}")
    return value


def _bounded_identifier(value: Any, field_name: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise AgentError("AGENT_PROVIDER_UNQUALIFIED", f"malformed qualification {field_name}")
    return value


def _timestamp(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise AgentError("AGENT_PROVIDER_UNQUALIFIED", f"malformed qualification {field_name}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AgentError("AGENT_PROVIDER_UNQUALIFIED", f"malformed qualification {field_name}") from exc
    if parsed.tzinfo is None or value.count("T") != 1:
        raise AgentError("AGENT_PROVIDER_UNQUALIFIED", f"malformed qualification {field_name}")
    return parsed.astimezone(UTC)


@dataclass(frozen=True)
class ProviderIdentity:
    """One host-built provider binding, with an integrity digest over explicit nulls."""

    provider_name: str
    model: str
    provider_version: str | None
    adapter_version: str
    parameter_context_digest: str
    qualification_record_id: str | None
    qualification_record_digest: str | None
    qualification_status: str
    qualification_expires_at: str | None
    identity_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.provider_name) or not _IDENTIFIER.fullmatch(self.model):
            raise ValueError("provider identity name and model must be bounded identifiers")
        if self.provider_version is not None and not _IDENTIFIER.fullmatch(self.provider_version):
            raise ValueError("provider identity version must be a bounded identifier or null")
        if not _IDENTIFIER.fullmatch(self.adapter_version):
            raise ValueError("provider identity adapter version must be a bounded identifier")
        if not _SHA256.fullmatch(self.parameter_context_digest):
            raise ValueError("provider identity parameter context digest must be SHA-256")
        if self.qualification_status not in {"qualified", "unqualified", "host_control"}:
            raise ValueError("unknown provider qualification status")
        if self.qualification_status == "qualified":
            if not self.qualification_record_id or not self.qualification_record_digest or not self.qualification_expires_at:
                raise ValueError("qualified provider identity requires qualification record fields")
            _timestamp(self.qualification_expires_at, "qualification expiry")
        elif any((self.qualification_record_id, self.qualification_record_digest, self.qualification_expires_at)):
            raise ValueError("unqualified provider identity cannot claim qualification fields")
        if self.qualification_record_id is not None and not _IDENTIFIER.fullmatch(self.qualification_record_id):
            raise ValueError("provider identity qualification record ID must be bounded")
        if self.qualification_record_digest is not None and not _SHA256.fullmatch(self.qualification_record_digest):
            raise ValueError("provider identity qualification record digest must be SHA-256")
        object.__setattr__(self, "identity_digest", digest(self._preimage()))

    def _preimage(self) -> dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "model": self.model,
            "provider_version": self.provider_version,
            "adapter_version": self.adapter_version,
            "parameter_context_digest": self.parameter_context_digest,
            "qualification_record_id": self.qualification_record_id,
            "qualification_record_digest": self.qualification_record_digest,
            "qualification_status": self.qualification_status,
            "qualification_expires_at": self.qualification_expires_at,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self._preimage(), "identity_digest": self.identity_digest}

    def verify(self) -> None:
        if self.identity_digest != digest(self._preimage()):
            raise AgentError("AGENT_IDENTITY_MISMATCH", "provider identity digest changed")


@dataclass(frozen=True)
class ProviderQualification:
    """The strict, read-only v1 qualification record. It never stores its body."""

    record_id: str
    provider_name: str
    model: str
    provider_version: str | None
    adapter_version: str
    parameter_context_digest: str
    methodology_build_id: str
    methodology_manifest_digest: str
    qualified_at: str
    expires_at: str
    evidence_digest: str
    record_digest: str

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "ProviderQualification":
        if not isinstance(record, dict) or set(record) != _QUALIFICATION_FIELDS:
            raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "qualification record fields are not exact")
        if record["schema_version"] != QUALIFICATION_SCHEMA_VERSION or record["status"] != "qualified":
            raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "qualification record is not v1 qualified")
        qualified_at = _timestamp(record["qualified_at"], "qualified_at")
        expires_at = _timestamp(record["expires_at"], "expires_at")
        if expires_at <= qualified_at:
            raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "qualification expiry must follow qualification time")
        return cls(
            record_id=_bounded_identifier(record["record_id"], "record_id"),  # type: ignore[arg-type]
            provider_name=_bounded_identifier(record["provider_name"], "provider_name"),  # type: ignore[arg-type]
            model=_bounded_identifier(record["model"], "model"),  # type: ignore[arg-type]
            provider_version=_bounded_identifier(record["provider_version"], "provider_version", nullable=True),
            adapter_version=_bounded_identifier(record["adapter_version"], "adapter_version"),  # type: ignore[arg-type]
            parameter_context_digest=_sha256(record["parameter_context_digest"], "parameter_context_digest"),
            methodology_build_id=_bounded_identifier(record["methodology_build_id"], "methodology_build_id"),  # type: ignore[arg-type]
            methodology_manifest_digest=_sha256(record["methodology_manifest_digest"], "methodology_manifest_digest"),
            qualified_at=record["qualified_at"],
            expires_at=record["expires_at"],
            evidence_digest=_sha256(record["evidence_digest"], "evidence_digest"),
            record_digest=digest(record),
        )

    @classmethod
    def from_path(cls, path: Path, expected_digest: str) -> "ProviderQualification":
        _sha256(expected_digest, "configured digest")
        try:
            record = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys)
        except (OSError, UnicodeDecodeError) as exc:
            raise AgentError("AGENT_QUALIFICATION_MISSING", "qualification record cannot be read") from exc
        except (json.JSONDecodeError, ValueError) as exc:
            raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "qualification record is malformed") from exc
        qualification = cls.from_record(record)
        if qualification.record_digest != expected_digest:
            raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "qualification record digest does not match")
        return qualification

    def validate_binding(
        self,
        *,
        provider_name: str,
        model: str,
        adapter_version: str,
        parameter_context_digest: str,
        methodology_build_id: str,
        methodology_manifest_digest: str,
        now: datetime | None = None,
    ) -> None:
        now = now or datetime.now(UTC)
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "qualification validation time must be timezone-aware")
        now = now.astimezone(UTC)
        if _timestamp(self.qualified_at, "qualified_at") > now:
            raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "qualification record is from the future")
        if now >= _timestamp(self.expires_at, "expires_at"):
            raise AgentError("AGENT_QUALIFICATION_EXPIRED", "qualification record has expired")
        expected = {
            "provider_name": provider_name,
            "model": model,
            "adapter_version": adapter_version,
            "parameter_context_digest": parameter_context_digest,
            "methodology_build_id": methodology_build_id,
            "methodology_manifest_digest": methodology_manifest_digest,
        }
        actual = {key: getattr(self, key) for key in expected}
        if actual != expected:
            raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "qualification record does not bind this provider")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    if len({key for key, _ in pairs}) != len(pairs):
        raise ValueError("duplicate qualification JSON key")
    return dict(pairs)


def installed_dependencies(*names: str) -> dict[str, str]:
    """Exact installed runtime versions, without accepting configuration values."""
    versions: dict[str, str] = {}
    for name in names:
        try:
            versions[name] = version(name)
        except PackageNotFoundError:
            versions[name] = "not-installed"
    return versions


def parameter_context_metadata(
    *,
    provider_name: str,
    model: str,
    provider_version: str | None,
    adapter_version: str,
    runtime_dependencies: Mapping[str, str],
    transport: Mapping[str, Any],
    counting: Mapping[str, Any],
) -> dict[str, Any]:
    """The allowlisted, host-only provider-policy preimage; never request data."""
    from ..methodology.canonical import CanonicalModuleOutput
    from ..modules.registry import MODULES
    from .budget import PROVIDER_TIMEOUT_SECONDS, REPAIRS, PROVIDER_RETRIES

    return {
        "provider": {"name": provider_name, "model": model, "version": provider_version},
        "adapter": {"version": adapter_version, "runtime_dependencies": dict(sorted(runtime_dependencies.items()))},
        "transport": dict(transport),
        "counting": dict(counting),
        "loop": {
            "provider_timeout_seconds": PROVIDER_TIMEOUT_SECONDS,
            "provider_retries": PROVIDER_RETRIES,
            "repairs": REPAIRS,
            "cache": False,
            "streaming": False,
            "parallel_tool_calls": False,
        },
        "tool": {"digest": digest(READ_EVIDENCE_TOOL)},
        "schema": {"canonical_output_digest": digest(CanonicalModuleOutput.model_json_schema())},
        "modules": {
            module_id: {
                "mode_full": spec.mode_full,
                "mode_screen": spec.mode_screen,
                "max_output_tokens": spec.max_output_tokens,
                "authority_digest": spec.authority_digest if spec.module_id in MODULES and spec.module_id in {
                    "CP-1", "CP-1A", "CP-1B", "CP-1C", "CP-1D", "CP-2", "CP-2A", "CP-2G", "CP-5"
                } else None,
                "source_mode": spec.source_mode,
            }
            for module_id, spec in sorted(MODULES.items())
        },
    }


def parameter_context_digest(**kwargs: Any) -> str:
    return digest(parameter_context_metadata(**kwargs))


def methodology_binding(root: Path) -> tuple[str, str]:
    try:
        integrity = json.loads((root / "DEPLOY_V_INTEGRITY_v1.json").read_text(encoding="utf-8"))
        manifest = json.loads((root / "DEPLOY_V_MANIFEST.json").read_text(encoding="utf-8"))
        build_id = _bounded_identifier(integrity.get("build_id"), "methodology build ID")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, AgentError) as exc:
        raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "methodology binding cannot be read") from exc
    return build_id, digest(manifest)  # type: ignore[return-value]


def host_control_identity(*, adapter_version: str = "caos.host-control.v1") -> ProviderIdentity:
    context = parameter_context_digest(
        provider_name="host_control",
        model="deterministic",
        provider_version=None,
        adapter_version=adapter_version,
        runtime_dependencies={},
        transport={"mode": "host-control"},
        counting={"mode": "not-applicable"},
    )
    return ProviderIdentity(
        provider_name="host_control", model="deterministic", provider_version=None,
        adapter_version=adapter_version, parameter_context_digest=context,
        qualification_record_id=None, qualification_record_digest=None,
        qualification_status="host_control", qualification_expires_at=None,
    )


@dataclass(frozen=True)
class ProviderBlock:
    type: str
    id: str | None = None
    name: str | None = None
    input: dict[str, Any] | None = None
    text: str | None = None


@dataclass(frozen=True)
class ProviderUsage:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class ProviderMessage:
    content: list[ProviderBlock]
    stop_reason: str
    usage: ProviderUsage
    request_id: str | None = None
    observed_model: str | None = None
    observed_provider_version: str | None = None


@dataclass(frozen=True)
class ProviderRequest:
    system: str
    messages: list[dict[str, Any]]
    schema: dict[str, Any]
    tools_enabled: bool
    max_tokens: int | None = None
    timeout: float | None = None


class Provider(Protocol):
    @property
    def identity(self) -> ProviderIdentity: ...

    def count_tokens(self, request: ProviderRequest) -> int: ...

    def create_message(self, request: ProviderRequest) -> ProviderMessage: ...
