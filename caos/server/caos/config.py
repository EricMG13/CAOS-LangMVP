from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit


def _provider_binding(value: str) -> str:
    if value not in {"", "host_control", "anthropic", "openai", "codex"}:
        raise RuntimeError("CAOS_PROVIDER must name a supported adapter")
    return value


def _strict_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError(f"{name} must be true or false")


@dataclass(frozen=True)
class Settings:
    environment: str = "development"
    database_url: str = ""
    storage_dir: Path = Path("/tmp/caos-vault")
    edge_proxy_secret: str = "dev-edge-secret"
    session_secret: str = "dev-insecure-session-secret"
    port: int = 8000
    # Two ceilings, deliberately different. max_upload_bytes is the edge's
    # request-body cap (Caddy reads the same MAX_UPLOAD_MB); max_source_bytes is
    # what a governed source may actually be. Business inputs are credit PDFs
    # and workbooks, so the route refuses far below the transport ceiling rather
    # than buffering, scanning, and parsing whatever the edge let through.
    max_upload_bytes: int = 32 * 1024 * 1024
    max_source_bytes: int = 25 * 1024 * 1024
    # Per-subject admission ceilings (see RequestCeilings). Sustained rate is
    # generous for a UI that refetches on every run event; the concurrency caps
    # bound the two shapes that hold a worker for their whole lifetime.
    rate_limit_per_minute: int = 300
    max_concurrent_streams: int = 4
    max_concurrent_previews: int = 2
    clamav_host: str = ""
    clamav_port: int = 3310
    deploy_v_root: Path = Path(__file__).parent / "methodology" / "vendor" / "deploy_v"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    openai_api_key: str = ""
    openai_model: str = ""
    provider_catalog_path: Path | None = None
    provider_account_policy: str = ""
    default_provider_binding: str = ""
    candidate_commit: str = ""
    image_set_digest: str = ""
    corpus_digest: str = ""
    enterprise_operator_subjects: tuple[str, ...] = ()
    # OpenRouter is a development-only binding for the same provider port. It
    # estimates tokens locally. Multiple credentials require an explicit binding
    # or catalog; production accepts qualified direct Anthropic and OpenAI APIs.
    openrouter_api_key: str = ""
    openrouter_model: str = "z-ai/glm-5.3-flash"
    provider_qualification_path: Path | None = None
    provider_qualification_digest: str = ""
    # `host_control` binds the development-only answer-keyed provider so the
    # keyless browser gates can drive an ordinary run (DECISIONS §14 D8). It is
    # refused outside development.
    provider_binding: str = ""
    # Fail-closed posture: agent (LLM) execution stays off without explicit opt-in.
    agent_execution_enabled: bool = False

    # Every environment variable this reads, once each: `from_env` walks this
    # list and the limits spec pins that no read carries a default of its own.
    ENV_NAMES = (
        "ENVIRONMENT", "DATABASE_URL", "CAOS_STORAGE_DIR", "EDGE_PROXY_SECRET", "SESSION_SECRET",
        "PORT", "MAX_UPLOAD_MB", "MAX_SOURCE_MB", "RATE_LIMIT_PER_MINUTE", "MAX_CONCURRENT_STREAMS",
        "MAX_CONCURRENT_PREVIEWS", "CLAMAV_HOST", "CLAMAV_PORT", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL",
        "OPENROUTER_API_KEY", "OPENROUTER_MODEL", "CAOS_PROVIDER_QUALIFICATION_PATH",
        "CAOS_PROVIDER_QUALIFICATION_DIGEST", "CAOS_PROVIDER", "AGENT_EXECUTION_ENABLED",
        "OPENAI_API_KEY", "OPENAI_MODEL", "CAOS_PROVIDER_CATALOG_PATH", "CAOS_PROVIDER_ACCOUNT_POLICY",
        "CAOS_DEFAULT_PROVIDER_BINDING", "CAOS_BUILD_COMMIT", "CAOS_IMAGE_SET_DIGEST",
        "CAOS_CORPUS_DIGEST", "CAOS_ENTERPRISE_OPERATOR_SUBJECTS",
    )

    @classmethod
    def from_env(cls) -> "Settings":
        """The dataclass above is the only place a default is written.

        `from_env` passes on the values a deployment actually set, so the pinned
        figure and the figure a deployment runs under cannot drift apart; the
        range checks run on the effective value — set or defaulted — instead of
        on a second copy of the literal (W17, 2026-09-06 review).
        """
        raw = {name: os.getenv(name) for name in cls.ENV_NAMES if name != "AGENT_EXECUTION_ENABLED"}
        chosen: dict[str, Any] = {}

        def when_set(name: str, field: str, convert: Any = str) -> None:
            if raw[name] is not None:
                chosen[field] = convert(raw[name])

        when_set("ENVIRONMENT", "environment")
        when_set("DATABASE_URL", "database_url")
        when_set("CAOS_STORAGE_DIR", "storage_dir", Path)
        when_set("EDGE_PROXY_SECRET", "edge_proxy_secret")
        when_set("SESSION_SECRET", "session_secret")
        when_set("PORT", "port", int)
        when_set("MAX_UPLOAD_MB", "max_upload_bytes", lambda mb: int(mb) * 1024 * 1024)
        when_set("MAX_SOURCE_MB", "max_source_bytes", lambda mb: int(mb) * 1024 * 1024)
        when_set("RATE_LIMIT_PER_MINUTE", "rate_limit_per_minute", int)
        when_set("MAX_CONCURRENT_STREAMS", "max_concurrent_streams", int)
        when_set("MAX_CONCURRENT_PREVIEWS", "max_concurrent_previews", int)
        when_set("CLAMAV_HOST", "clamav_host")
        when_set("CLAMAV_PORT", "clamav_port", int)
        when_set("ANTHROPIC_API_KEY", "anthropic_api_key")
        when_set("ANTHROPIC_MODEL", "anthropic_model")
        when_set("OPENAI_API_KEY", "openai_api_key")
        when_set("OPENAI_MODEL", "openai_model")
        when_set("CAOS_PROVIDER_ACCOUNT_POLICY", "provider_account_policy")
        when_set("CAOS_DEFAULT_PROVIDER_BINDING", "default_provider_binding")
        when_set("CAOS_BUILD_COMMIT", "candidate_commit")
        when_set("CAOS_IMAGE_SET_DIGEST", "image_set_digest")
        when_set("CAOS_CORPUS_DIGEST", "corpus_digest")
        when_set("CAOS_ENTERPRISE_OPERATOR_SUBJECTS", "enterprise_operator_subjects",
                 lambda subjects: tuple(value.strip() for value in subjects.split(",") if value.strip()))
        if raw["CAOS_PROVIDER_CATALOG_PATH"]:
            chosen["provider_catalog_path"] = Path(raw["CAOS_PROVIDER_CATALOG_PATH"])
        when_set("OPENROUTER_API_KEY", "openrouter_api_key")
        when_set("OPENROUTER_MODEL", "openrouter_model")
        when_set("CAOS_PROVIDER_QUALIFICATION_DIGEST", "provider_qualification_digest")
        when_set("CAOS_PROVIDER", "provider_binding", _provider_binding)
        if raw["CAOS_PROVIDER_QUALIFICATION_PATH"]:
            chosen["provider_qualification_path"] = Path(raw["CAOS_PROVIDER_QUALIFICATION_PATH"])
        settings = cls(
            agent_execution_enabled=_strict_bool("AGENT_EXECUTION_ENABLED", cls.agent_execution_enabled),
            **chosen,
        )
        settings._check_ranges()
        return settings

    def _check_ranges(self) -> None:
        """The admission ceilings, checked on the effective values. The messages
        name the environment variable because that is what an operator sets."""
        upload_mb = self.max_upload_bytes // (1024 * 1024)
        source_mb = self.max_source_bytes // (1024 * 1024)
        if not 0 <= self.port <= 65535:
            raise ValueError("PORT must be between 0 and 65535")
        if upload_mb <= 0:
            raise ValueError("MAX_UPLOAD_MB must be greater than 0")
        if not 0 < source_mb <= upload_mb:
            raise ValueError("MAX_SOURCE_MB must be greater than 0 and no larger than MAX_UPLOAD_MB")
        if not 1 <= self.clamav_port <= 65535:
            raise ValueError("CLAMAV_PORT must be between 1 and 65535")
        for name, value in (("RATE_LIMIT_PER_MINUTE", self.rate_limit_per_minute),
                            ("MAX_CONCURRENT_STREAMS", self.max_concurrent_streams),
                            ("MAX_CONCURRENT_PREVIEWS", self.max_concurrent_previews)):
            if value <= 0:
                raise ValueError(f"{name} must be greater than 0")
        operators = self.enterprise_operator_subjects
        if len(operators) > 100 or any(not re.fullmatch(r"[^\s\x00-\x1f\x7f]{1,160}", value) for value in operators):
            raise ValueError("CAOS_ENTERPRISE_OPERATOR_SUBJECTS contains an invalid subject")

    # Values that exist to be replaced. `.env.example` ships every required
    # secret empty so Compose's `${VAR:?}` fails closed on an uncopied file;
    # these catch the older documented placeholders and the dev literals, which
    # a copied-and-forgotten `.env` would otherwise carry into production.
    _PLACEHOLDER_SECRETS = frozenset({"dev-edge-secret", "dev-insecure-session-secret"})
    _PLACEHOLDER_PREFIXES = ("change-me", "changeme", "replace-me", "example", "password")
    MIN_SECRET_CHARS = 32

    @classmethod
    def _reject_placeholder(cls, name: str, value: str) -> None:
        lowered = value.strip().lower()
        if not lowered:
            raise RuntimeError(f"production requires {name}")
        if lowered in cls._PLACEHOLDER_SECRETS or lowered.startswith(cls._PLACEHOLDER_PREFIXES):
            raise RuntimeError(f"production requires a real {name}, not the documented placeholder")
        if len(value) < cls.MIN_SECRET_CHARS:
            raise RuntimeError(
                f"production requires {name} to be at least {cls.MIN_SECRET_CHARS} characters "
                "(e.g. `openssl rand -hex 32`)"
            )

    def validate_worker_runtime(self) -> None:
        if self.environment not in {"development", "production"}:
            raise RuntimeError("ENVIRONMENT must be development or production")
        _provider_binding(self.provider_binding)
        if self.environment == "production" and self.provider_binding in {"host_control", "codex"}:
            raise RuntimeError("the selected CAOS_PROVIDER binding is development-only")
        if self.environment == "production":
            if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
                raise RuntimeError("production requires a PostgreSQL DATABASE_URL")
            # POSTGRES_PASSWORD never reaches Settings on its own — Compose
            # interpolates it into DATABASE_URL, which is where we can see it.
            password = unquote(urlsplit(self.database_url).password or "")
            if not password.strip():
                raise RuntimeError("production requires POSTGRES_PASSWORD")
            if password.strip().lower().startswith(self._PLACEHOLDER_PREFIXES):
                raise RuntimeError("production requires a real POSTGRES_PASSWORD, not the documented placeholder")

    def validate_runtime(self) -> None:
        self.validate_worker_runtime()
        if self.environment == "production":
            self._reject_placeholder("EDGE_PROXY_SECRET", self.edge_proxy_secret)
            self._reject_placeholder("SESSION_SECRET", self.session_secret)
