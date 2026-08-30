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
from caos.storage.store import DomainStore


def build_provider(settings: Settings):
    """Anthropic first: it is the only binding that can count tokens before it
    calls, which is what the budget reserves against. OpenRouter is used when it
    is the only key configured, and its reservation is a local estimate."""
    if settings.anthropic_api_key:
        from caos.engine.anthropic import AnthropicProvider

        return AnthropicProvider(settings.anthropic_api_key, settings.anthropic_model)
    if settings.openrouter_api_key:
        from caos.engine.openrouter import OpenRouterProvider

        return OpenRouterProvider(settings.openrouter_api_key, settings.openrouter_model)
    return None


def build(settings: Settings, data: Path) -> tuple[FastAPI, Engine]:
    """Assemble the combined app: store, engine (auto-continue on), API, and the
    static export when one is present (./static in the image, ../frontend/out
    after `npm run build`). API routes are registered first, so they win."""
    data.mkdir(parents=True, exist_ok=True)
    store = DomainStore.from_url(settings.database_url or f"sqlite:///{data / 'caos.db'}")
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


def serve(app: FastAPI, engine: Engine, *, host: str, port: int) -> None:
    async def _serve() -> None:
        # §10.5 startup recovery on the serving loop (engine state is loop-bound):
        # re-admit runs stranded by a restart before accepting traffic.
        await engine.recover()
        await uvicorn.Server(uvicorn.Config(app, host=host, port=port)).serve()

    asyncio.run(_serve())


def main() -> None:
    settings = Settings.from_env()
    settings.validate_runtime()
    data = Path(os.getenv("CAOS_DATA_DIR", str(settings.storage_dir))).resolve()
    app, engine = build(settings, data)
    serve(app, engine, host=os.getenv("HOST", "0.0.0.0"), port=settings.port)


if __name__ == "__main__":
    main()
