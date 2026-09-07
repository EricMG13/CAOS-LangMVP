"""Server-owned provider bindings. Policy selects an ID; runs retain exact identities."""

from __future__ import annotations

import inspect
import json
import os
import re
from pathlib import Path
from types import MappingProxyType
from typing import Any

from ..config import Settings
from ..observability import register_secrets
from .provider import AgentError, ProviderIdentity, ProviderQualification, _reject_duplicate_keys, methodology_binding

CATALOG_SCHEMA = "caos.provider-catalog.v1"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_ACCOUNT_POLICY = re.compile(r"[^\s\x00-\x1f\x7f]{1,160}")
_FIELDS = {"id", "provider", "model", "credential_env", "account_policy", "parameters",
           "qualification_path", "qualification_digest"}


def require_account_policy(value: Any) -> None:
    if not isinstance(value, str) or not _ACCOUNT_POLICY.fullmatch(value):
        raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "production requires an approved account-policy identifier")


def require_production_qualification(provider: Any, settings: Settings, *, identity: ProviderIdentity | None = None) -> None:
    identity = identity if identity is not None else provider.identity
    identity.ensure_current()
    if settings.environment != "production":
        return
    if identity.provider_name not in {"anthropic", "openai"} or identity.qualification_status != "qualified":
        raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "production requires an eligible direct API binding")
    require_account_policy(getattr(provider, "account_policy", None))
    qualification = getattr(provider, "qualification", None)
    if not isinstance(qualification, ProviderQualification):
        raise AgentError("AGENT_QUALIFICATION_MISSING", "provider has no candidate qualification")
    if (qualification.record_digest != identity.qualification_record_digest
            or qualification.record_id != identity.qualification_record_id
            or qualification.expires_at != identity.qualification_expires_at):
        raise AgentError("AGENT_IDENTITY_MISMATCH", "provider qualification changed")
    build, manifest = methodology_binding(settings.deploy_v_root)
    qualification.validate_binding(provider_name=identity.provider_name, model=identity.model,
                                   provider_version=identity.provider_version, adapter_version=identity.adapter_version,
                                   parameter_context_digest=identity.parameter_context_digest,
                                   methodology_build_id=build, methodology_manifest_digest=manifest)
    qualification.validate_candidate(candidate_commit=settings.candidate_commit,
                                     image_set_digest=settings.image_set_digest, corpus_digest=settings.corpus_digest)


class ProviderCatalog:
    def __init__(self, bindings: dict[str, Any], default_binding_id: str, *, settings: Settings,
                 unavailable: dict[str, dict[str, Any]] | None = None) -> None:
        self.bindings = MappingProxyType(dict(bindings))
        self.default_binding_id = default_binding_id
        self.settings = settings
        self.unavailable = dict(unavailable or {})
        self._closed: set[int] = set()
        if default_binding_id not in self.bindings and default_binding_id not in self.unavailable:
            raise AgentError("AGENT_PROVIDER_UNAVAILABLE", "catalog default binding is absent")
        identities = {}
        for binding_id, binding in self.bindings.items():
            identity = binding.identity
            identity = identity if isinstance(identity, ProviderIdentity) else ProviderIdentity.from_dict(identity)
            identity.verify()
            identities[binding_id] = identity
        self.identities = MappingProxyType(identities)

    def resolve(self, binding_id: str) -> Any:
        provider = self.bindings.get(binding_id)
        if provider is None:
            code = self.unavailable.get(binding_id, {}).get("unavailable_code", "AGENT_PROVIDER_UNAVAILABLE")
            raise AgentError(code, "the selected provider binding is unavailable")
        require_production_qualification(provider, self.settings, identity=self.identities[binding_id])
        return provider

    def for_identity(self, identity: ProviderIdentity) -> Any:
        identity.ensure_current()
        for binding_id, captured in self.identities.items():
            if captured == identity:
                return self.resolve(binding_id)
        raise AgentError("AGENT_IDENTITY_MISMATCH", "the run's pinned provider binding is unavailable")

    def view(self) -> list[dict[str, Any]]:
        rows = dict(self.unavailable)
        for binding_id, identity in self.identities.items():
            code = None
            try:
                self.resolve(binding_id)
                if not self.settings.agent_execution_enabled:
                    code = "AGENT_EXECUTION_DISABLED"
            except AgentError as exc:
                code = exc.code
            rows[binding_id] = {"id": binding_id, "provider_name": identity.provider_name, "model": identity.model,
                                "available": code is None, "status": identity.qualification_status,
                                "unavailable_code": code}
        return [rows[key] for key in sorted(rows)]

    async def aclose(self) -> None:
        first_error = None
        for provider in self.bindings.values():
            if id(provider) in self._closed:
                continue
            try:
                close = getattr(provider, "aclose", None)
                if close is not None:
                    result = close()
                    if inspect.isawaitable(result):
                        await result
                self._closed.add(id(provider))
            except BaseException as exc:
                first_error = first_error or exc
        if first_error is not None:
            raise first_error


def load_catalog(settings: Settings) -> ProviderCatalog:
    path = settings.provider_catalog_path
    try:
        if path is None or path.stat().st_size > 128 * 1024:
            raise ValueError("invalid catalog size")
        body = json.loads(path.read_text(), object_pairs_hook=_reject_duplicate_keys)
    except (OSError, UnicodeError, ValueError) as exc:
        raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "provider catalog cannot be read") from exc
    if (not isinstance(body, dict) or body.keys() != {"schema_version", "default_binding_id", "bindings"}
            or body["schema_version"] != CATALOG_SCHEMA or not isinstance(body["bindings"], list)
            or not 1 <= len(body["bindings"]) <= 32):
        raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "invalid provider catalog")
    entries = body["bindings"]
    seen: set[str] = set()
    for entry in entries:
        if (not isinstance(entry, dict) or entry.keys() != _FIELDS or not isinstance(entry["id"], str)
                or not _ID.fullmatch(entry["id"]) or entry["id"] in seen
                or not isinstance(entry["provider"], str) or entry["provider"] not in {"anthropic", "openai", "openrouter", "codex"}
                or not isinstance(entry["model"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:@/-]{0,159}", entry["model"])
                or not isinstance(entry["account_policy"], str)
                or (entry["account_policy"] and not _ACCOUNT_POLICY.fullmatch(entry["account_policy"]))
                or not isinstance(entry["parameters"], dict)
                or (entry["provider"] in {"codex", "openrouter"} and entry["parameters"])
                or not isinstance(entry["credential_env"], str)
                or (entry["provider"] != "codex" and not re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", entry["credential_env"]))
                or not isinstance(entry["qualification_path"], (str, type(None)))
                or not isinstance(entry["qualification_digest"], str)):
            raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "invalid provider catalog entry")
        seen.add(entry["id"])
        if settings.environment == "production" and entry["provider"] not in {"anthropic", "openai"}:
            raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "development adapter in enterprise catalog")
    default = settings.default_provider_binding or body["default_binding_id"]
    if not isinstance(default, str) or default not in seen:
        raise AgentError("AGENT_PROVIDER_UNAVAILABLE", "catalog default binding is absent")

    # Validate every descriptor before allocating any clients. Unavailable credentials/qualification
    # remain visible with a safe reason and can never be selected for generation.
    bindings: dict[str, Any] = {}
    unavailable: dict[str, dict[str, Any]] = {}
    for entry in entries:
        name = entry["provider"]
        try:
            qualification = None
            if bool(entry["qualification_path"]) != bool(entry["qualification_digest"]):
                raise AgentError("AGENT_QUALIFICATION_MISSING", "qualification path and digest are both required")
            if entry["qualification_path"]:
                qualification_path = Path(entry["qualification_path"])
                if not qualification_path.is_absolute():
                    qualification_path = path.parent / qualification_path
                qualification = ProviderQualification.from_path(qualification_path, entry["qualification_digest"])
            if settings.environment == "production":
                if qualification is None or not entry["account_policy"]:
                    raise AgentError("AGENT_QUALIFICATION_MISSING", "enterprise binding requires qualification and account policy")
                qualification.validate_candidate(candidate_commit=settings.candidate_commit,
                                                 image_set_digest=settings.image_set_digest, corpus_digest=settings.corpus_digest)
            kwargs = {"methodology_root": settings.deploy_v_root, "account_policy": entry["account_policy"]}
            if name == "codex":
                from .codex import CodexProvider

                provider = CodexProvider(entry["model"], **kwargs)
            else:
                key = os.getenv(entry["credential_env"], "")
                register_secrets(key)
                if not key.strip():
                    raise AgentError("AGENT_PROVIDER_UNAVAILABLE", "the configured provider credential is empty")
                if name == "anthropic":
                    from .anthropic import AnthropicProvider as Adapter
                elif name == "openai":
                    from .openai import OpenAIProvider as Adapter
                else:
                    from .openrouter import OpenRouterProvider as Adapter

                    kwargs.pop("account_policy")
                provider = Adapter(key, entry["model"], qualification=qualification,
                                   **kwargs, **({"parameters": entry["parameters"]} if name != "openrouter" else {}))
            bindings[entry["id"]] = provider
        except (AgentError, ValueError) as exc:
            unavailable[entry["id"]] = {"id": entry["id"], "provider_name": name, "model": entry["model"],
                                          "available": False, "status": "unavailable",
                                          "unavailable_code": getattr(exc, "code", "AGENT_PROVIDER_UNQUALIFIED")}
    return ProviderCatalog(bindings, default, settings=settings, unavailable=unavailable)


def build_provider(settings: Settings):
    """Assemble an explicit catalog, or preserve a single legacy development binding."""
    if settings.provider_catalog_path is not None:
        if settings.provider_binding == "host_control":
            raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "host control cannot select an external catalog")
        return load_catalog(settings)
    configured = {
        "anthropic": bool(settings.anthropic_api_key.strip()),
        "openai": bool(settings.openai_api_key.strip()),
        "openrouter": bool(settings.openrouter_api_key.strip()),
    }
    selected = settings.provider_binding
    if not selected:
        names = [name for name, present in configured.items() if present]
        if len(names) > 1:
            raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "multiple provider credentials require explicit selection")
        selected = names[0] if names else ""
    qualification_configured = settings.provider_qualification_path is not None or bool(settings.provider_qualification_digest)
    if qualification_configured and (settings.provider_qualification_path is None or not settings.provider_qualification_digest):
        raise AgentError("AGENT_QUALIFICATION_MISSING", "qualification path and digest are both required")
    if settings.environment == "production" and (selected in {"openrouter", "host_control", "codex"} or configured["openrouter"]):
        raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "the selected adapter is development-only")
    if not settings.agent_execution_enabled:
        return None
    if selected == "host_control":
        if any(configured.values()):
            raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "the host-control binding excludes provider credentials")
        from .host_control import HostControlProvider

        return HostControlProvider()
    if selected == "codex":
        from .codex import CodexProvider

        return CodexProvider(settings.openai_model, methodology_root=settings.deploy_v_root,
                             account_policy=settings.provider_account_policy)
    if not selected or not configured.get(selected):
        if settings.environment == "production" or selected:
            raise AgentError("AGENT_PROVIDER_UNAVAILABLE", "the selected provider credential is not configured")
        return None
    qualification = None
    if qualification_configured:
        qualification = ProviderQualification.from_path(settings.provider_qualification_path, settings.provider_qualification_digest)
    if settings.environment == "production":
        if qualification is None:
            raise AgentError("AGENT_QUALIFICATION_MISSING", "production agent execution requires qualification")
        qualification.validate_candidate(candidate_commit=settings.candidate_commit,
                                         image_set_digest=settings.image_set_digest, corpus_digest=settings.corpus_digest)
        require_account_policy(settings.provider_account_policy)
    if selected == "anthropic":
        from .anthropic import AnthropicProvider

        return AnthropicProvider(settings.anthropic_api_key, settings.anthropic_model, qualification=qualification,
                                 methodology_root=settings.deploy_v_root, account_policy=settings.provider_account_policy)
    if selected == "openai":
        from .openai import OpenAIProvider

        return OpenAIProvider(settings.openai_api_key, settings.openai_model, qualification=qualification,
                              methodology_root=settings.deploy_v_root, account_policy=settings.provider_account_policy)
    from .openrouter import OpenRouterProvider

    return OpenRouterProvider(settings.openrouter_api_key, settings.openrouter_model, qualification=qualification)
