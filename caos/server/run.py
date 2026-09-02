"""Combined-app entrypoint (Dockerfile `app` target; CI browser job).

Serves the API plus the static frontend export, enables run auto-continue,
and runs §10.5 startup recovery on the serving loop. Production configuration
is validated up front (PostgreSQL DATABASE_URL, real edge/session secrets);
development defaults fall back to SQLite under the data directory.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from caos.api import create_app
from caos.config import Settings
from caos.engine.runtime import Engine
from caos.observability import configure_logging
from caos.storage.store import DomainStore


def build_provider(settings: Settings):
    """Build one explicit provider binding; production requires qualified Anthropic."""
    from caos.engine.provider import AgentError, ProviderQualification

    anthropic_configured = bool(settings.anthropic_api_key.strip())
    openrouter_configured = bool(settings.openrouter_api_key.strip())
    if anthropic_configured and openrouter_configured:
        raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "multiple provider credentials are configured")
    qualification_configured = (
        settings.provider_qualification_path is not None
        or bool(settings.provider_qualification_digest)
    )
    if qualification_configured and (
        settings.provider_qualification_path is None
        or not settings.provider_qualification_digest
    ):
        raise AgentError("AGENT_QUALIFICATION_MISSING", "qualification path and digest are both required")
    if settings.environment == "production" and openrouter_configured:
        raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "OpenRouter is development-only")
    if settings.environment == "production" and settings.provider_binding:
        raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "the host-control binding is development-only")
    if not settings.agent_execution_enabled:
        return None
    if settings.provider_binding == "host_control":
        if anthropic_configured or openrouter_configured:
            raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "the host-control binding excludes provider credentials")
        from caos.engine.host_control import HostControlProvider

        return HostControlProvider()
    if settings.environment == "production" and not anthropic_configured:
        raise AgentError("AGENT_PROVIDER_UNAVAILABLE", "ANTHROPIC_API_KEY is not configured")

    qualification = None
    if qualification_configured:
        qualification = ProviderQualification.from_path(
            settings.provider_qualification_path,
            settings.provider_qualification_digest,
        )
    if settings.environment == "production" and qualification is None:
        raise AgentError("AGENT_QUALIFICATION_MISSING", "production agent execution requires qualification")

    if anthropic_configured:
        from caos.engine.anthropic import AnthropicProvider

        return AnthropicProvider(
            settings.anthropic_api_key,
            settings.anthropic_model,
            qualification=qualification,
            methodology_root=settings.deploy_v_root,
        )
    if openrouter_configured:
        from caos.engine.openrouter import OpenRouterProvider

        return OpenRouterProvider(
            settings.openrouter_api_key,
            settings.openrouter_model,
            qualification=qualification,
        )
    return None


def build(settings: Settings, data: Path) -> tuple[FastAPI, Engine]:
    """Assemble the combined app: store, engine (auto-continue on), API, and the
    static export when one is present (./static in the image, ../frontend/out
    after `npm run build`). API routes are registered first, so they win."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError("run.build must be called outside an active event loop")
    settings.validate_runtime()
    configure_logging(settings)  # JSON on stdout; registers the secrets to redact
    data.mkdir(parents=True, exist_ok=True)
    store = DomainStore.from_url(settings.database_url or f"sqlite:///{data / 'caos.db'}")
    provider = None
    engine = None
    try:
        provider = build_provider(settings)
        # ponytail: run checkpoints ride SQLite on the durable data volume even under
        # a Postgres domain store — the postgres checkpoint saver is pinned in
        # requirements but not yet wired in the engine. Single app instance only.
        engine = Engine.create(
            settings=settings, store=store, checkpoint_path=data / "checkpoints.db", provider=provider
        )
        engine.enable_auto_continue()
        app = create_app(settings=settings, store=store, engine=engine)
        for static in (Path(__file__).parent / "static", Path(__file__).parent.parent / "frontend" / "out"):
            if static.is_dir():
                from fastapi.staticfiles import StaticFiles

                app.mount("/", StaticFiles(directory=static, html=True), name="static")
                break
        return app, engine
    except BaseException:
        try:
            asyncio.run(_close_owned(engine, provider))
        except BaseException:
            pass
        try:
            store.close()
        except BaseException:
            pass
        raise


def serve(app: FastAPI, engine: Engine, *, host: str, port: int) -> None:
    async def _serve() -> None:
        try:
            # §10.5 startup recovery on the serving loop (engine state is loop-bound):
            # re-admit runs stranded by a restart before accepting traffic.
            await engine.recover()
            await uvicorn.Server(uvicorn.Config(app, host=host, port=port)).serve()
        except BaseException:
            try:
                await _close_owned(engine)
            except BaseException:
                pass
            raise
        await _close_owned(engine)

    asyncio.run(_serve())


async def _close_owned(engine: Engine | None, provider: object | None = None) -> None:
    resource_provider = provider if provider is not None else getattr(engine, "provider", None)
    close_provider = getattr(resource_provider, "aclose", None)
    try:
        if engine is not None:
            await engine.aclose()
    except BaseException:
        if callable(close_provider):
            try:
                await close_provider()
            except BaseException:
                pass
        raise
    if callable(close_provider):
        await close_provider()


def main() -> None:
    settings = Settings.from_env()
    if settings.environment != "production":
        raise RuntimeError("run.py requires ENVIRONMENT=production; use dev.py for development")
    data = Path(os.getenv("CAOS_DATA_DIR", str(settings.storage_dir))).resolve()
    app, engine = build(settings, data)
    serve_owns_async_resources = False
    try:
        with engine.store.single_instance("app"):
            serve_owns_async_resources = True
            serve(app, engine, host=os.getenv("HOST", "0.0.0.0"), port=settings.port)
    except BaseException:
        if not serve_owns_async_resources:
            try:
                asyncio.run(_close_owned(engine))
            except BaseException:
                pass
        try:
            engine.store.close()
        except BaseException:
            pass
        raise
    engine.store.close()


if __name__ == "__main__":
    main()
