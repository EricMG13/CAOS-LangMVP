"""Combined-app entrypoint (Dockerfile `app` target; CI browser job).

Serves the API plus the static frontend export, enables run auto-continue,
and runs §10.5 startup recovery on the serving loop. Production configuration
is validated up front (PostgreSQL DATABASE_URL, real edge/session secrets);
development defaults fall back to SQLite under the data directory.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import suppress
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from caos.api import create_app
from caos.config import Settings
from caos.engine.catalog import build_provider
from caos.engine.runtime import Engine
from caos.instance_lock import checkpoint_lock
from caos.observability import configure_logging
from caos.storage.store import DomainStore


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
    store = DomainStore.from_url(
        settings.database_url or f"sqlite:///{data / 'caos.db'}",
        role="app",
    )
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
    resource_provider = provider if provider is not None else (getattr(engine, "_provider_catalog", None) or getattr(engine, "provider", None))
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


def run_app(settings: Settings, data: Path, *, host: str) -> None:
    """Own the app from assembly through locked serving and ordered shutdown."""
    settings.validate_runtime()
    with checkpoint_lock(data / "checkpoints.db"):
        app, engine = build(settings, data)
        serve_owns_async_resources = False
        try:
            # The store already owns the PostgreSQL app-role lock acquired
            # before schema initialization. This nested guard also preserves
            # explicit ownership for injected/test stores.
            with engine.store.single_instance("app"):
                serve_owns_async_resources = True
                serve(app, engine, host=host, port=settings.port)
        except BaseException:
            if not serve_owns_async_resources:
                with suppress(BaseException):
                    asyncio.run(_close_owned(engine))
            with suppress(BaseException):
                engine.store.close()
            raise
        engine.store.close()


def main() -> None:
    settings = Settings.from_env()
    if settings.environment != "production":
        raise RuntimeError("run.py requires ENVIRONMENT=production; use dev.py for development")
    data = Path(os.getenv("CAOS_DATA_DIR", str(settings.storage_dir))).resolve()
    run_app(settings, data, host=os.getenv("HOST", "0.0.0.0"))


if __name__ == "__main__":
    main()
