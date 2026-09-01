from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


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
    # OpenRouter is an alternative binding for the same provider port. It has no
    # pre-call token-counting endpoint, so its adapter estimates locally — see
    # engine/openrouter.py. Anthropic stays the default and wins when both are
    # configured, because only it can count before it calls.
    openrouter_api_key: str = ""
    openrouter_model: str = "z-ai/glm-5.3-flash"
    provider_qualification_path: Path | None = None
    provider_qualification_digest: str = ""
    # Fail-closed posture: agent (LLM) execution stays off without explicit opt-in.
    agent_execution_enabled: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        port = int(os.getenv("PORT", "8000"))
        max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "32"))
        max_source_mb = int(os.getenv("MAX_SOURCE_MB", "25"))
        clamav_port = int(os.getenv("CLAMAV_PORT", "3310"))
        rate_limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "300"))
        max_streams = int(os.getenv("MAX_CONCURRENT_STREAMS", "4"))
        max_previews = int(os.getenv("MAX_CONCURRENT_PREVIEWS", "2"))
        if not 0 <= port <= 65535:
            raise ValueError("PORT must be between 0 and 65535")
        if max_upload_mb <= 0:
            raise ValueError("MAX_UPLOAD_MB must be greater than 0")
        if not 0 < max_source_mb <= max_upload_mb:
            raise ValueError("MAX_SOURCE_MB must be greater than 0 and no larger than MAX_UPLOAD_MB")
        if not 1 <= clamav_port <= 65535:
            raise ValueError("CLAMAV_PORT must be between 1 and 65535")
        for name, value in (("RATE_LIMIT_PER_MINUTE", rate_limit),
                            ("MAX_CONCURRENT_STREAMS", max_streams),
                            ("MAX_CONCURRENT_PREVIEWS", max_previews)):
            if value <= 0:
                raise ValueError(f"{name} must be greater than 0")
        qualification_path = os.getenv("CAOS_PROVIDER_QUALIFICATION_PATH", "")
        return cls(
            environment=os.getenv("ENVIRONMENT", "development"),
            database_url=os.getenv("DATABASE_URL", ""),
            storage_dir=Path(os.getenv("CAOS_STORAGE_DIR", "/tmp/caos-vault")),
            edge_proxy_secret=os.getenv("EDGE_PROXY_SECRET", "dev-edge-secret"),
            session_secret=os.getenv("SESSION_SECRET", "dev-insecure-session-secret"),
            port=port,
            max_upload_bytes=max_upload_mb * 1024 * 1024,
            max_source_bytes=max_source_mb * 1024 * 1024,
            rate_limit_per_minute=rate_limit,
            max_concurrent_streams=max_streams,
            max_concurrent_previews=max_previews,
            clamav_host=os.getenv("CLAMAV_HOST", ""),
            clamav_port=clamav_port,
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
            openrouter_model=os.getenv("OPENROUTER_MODEL", "z-ai/glm-5.3-flash"),
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            provider_qualification_path=Path(qualification_path) if qualification_path else None,
            provider_qualification_digest=os.getenv("CAOS_PROVIDER_QUALIFICATION_DIGEST", ""),
            agent_execution_enabled=_strict_bool("AGENT_EXECUTION_ENABLED", False),
        )

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

    def validate_runtime(self) -> None:
        if self.environment not in {"development", "production"}:
            raise RuntimeError("ENVIRONMENT must be development or production")
        if self.environment == "production":
            if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
                raise RuntimeError("production requires a PostgreSQL DATABASE_URL")
            self._reject_placeholder("EDGE_PROXY_SECRET", self.edge_proxy_secret)
            self._reject_placeholder("SESSION_SECRET", self.session_secret)
            # POSTGRES_PASSWORD never reaches Settings on its own — Compose
            # interpolates it into DATABASE_URL, which is where we can see it.
            password = urlsplit(self.database_url).password or ""
            if password.strip().lower().startswith(self._PLACEHOLDER_PREFIXES):
                raise RuntimeError("production requires a real POSTGRES_PASSWORD, not the documented placeholder")
