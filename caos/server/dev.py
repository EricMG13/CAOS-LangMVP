"""Local development entrypoint: SQLite store + checkpoints under ./.dev-data,
the dev identity edge (x-caos-role trusted), and agent execution off unless
AGENT_EXECUTION_ENABLED=true with an ANTHROPIC_API_KEY. Deterministic routes
(e.g. EARNINGS_UPDATE at screen depth) run end to end with no key at all.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import uvicorn

from caos.api import create_app
from caos.config import Settings
from caos.engine.runtime import Engine
from caos.storage.store import DomainStore


def main() -> None:
    settings = Settings.from_env()
    data = Path(os.getenv("CAOS_DATA_DIR", ".dev-data")).resolve()
    data.mkdir(parents=True, exist_ok=True)
    store = DomainStore.from_url(settings.database_url or f"sqlite:///{data / 'caos.db'}")
    provider = None
    if settings.anthropic_api_key:
        from caos.engine.anthropic import AnthropicProvider

        provider = AnthropicProvider(settings.anthropic_api_key, settings.anthropic_model)
    engine = Engine.create(
        settings=settings, store=store, checkpoint_path=data / "checkpoints.db", provider=provider
    )
    engine.enable_auto_continue()
    app = create_app(settings=settings, store=store, engine=engine)
    # Combined app when a static export exists (./static in the image,
    # ../frontend/out after `npm run build`); API routes registered above win.
    for static in (Path(__file__).parent / "static", Path(__file__).parent.parent / "frontend" / "out"):
        if static.is_dir():
            from fastapi.staticfiles import StaticFiles

            app.mount("/", StaticFiles(directory=static, html=True), name="static")
            break

    async def serve() -> None:
        # §10.5 startup recovery on the serving loop (engine state is loop-bound):
        # re-admit runs stranded by a dev-server restart.
        await engine.recover()
        await uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=settings.port)).serve()

    asyncio.run(serve())


if __name__ == "__main__":
    main()
