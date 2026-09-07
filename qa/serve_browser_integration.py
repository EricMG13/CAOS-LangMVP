#!/usr/bin/env python3
"""Isolated browser integration fixture, never production qualification.

Production API identity + shipped static frontend; injected development host
control and SQLite. A real clamd may be supplied; --scanner-fixture explicitly
uses the development scanner and leaves production scanner proof unmet. No
fixture mode is added to the shipped application or production entrypoint.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
import os
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "caos" / "server"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=19181)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--scanner-fixture", action="store_true")
    parser.add_argument("--report-fixtures", action="store_true", help="Use disposable canonical report answer keys; not analytical qualification")
    parser.add_argument("--clamav-host", default="")
    parser.add_argument("--clamav-port", type=int, default=3310)
    args = parser.parse_args()
    if not args.scanner_fixture and not args.clamav_host:
        parser.error("supply real --clamav-host or explicitly select --scanner-fixture")
    secret = os.environ["CAOS_EDGE_SECRET"]
    operator = os.environ.get("CAOS_OPERATOR_USER", "journey-operator")
    if args.data_dir.exists():
        parser.error("--data-dir must be new: this fixture never reuses an existing database")
    args.data_dir.mkdir(parents=True)

    from fastapi.staticfiles import StaticFiles
    import uvicorn
    from caos.api import create_app
    from caos.config import Settings
    from caos.deliverables.service import DeliverableService
    from caos.engine.runtime import Engine
    from caos.models.service import ModelService
    from caos.sources import domain
    from caos.storage.store import DomainStore
    from browser_fixture_provider import BrowserFixtureProvider
    from worker import run_pending

    settings = Settings(environment="development", storage_dir=args.data_dir / "vault",
                        agent_execution_enabled=True, provider_binding="host_control")
    store = DomainStore.from_url(f"sqlite:///{args.data_dir / 'caos.db'}")
    provider = BrowserFixtureProvider(report_fixtures=args.report_fixtures)
    engine = Engine.create(settings=settings, store=store,
                           checkpoint_path=args.data_dir / "checkpoints.db", provider=provider)
    engine.enable_auto_continue()
    api_settings = replace(settings, environment="production", edge_proxy_secret=secret,
                           enterprise_operator_subjects=(operator,), clamav_host=args.clamav_host,
                           clamav_port=args.clamav_port)
    if args.scanner_fixture:
        real_scan = domain.scan_content
        domain.scan_content = lambda content, _settings: real_scan(content, settings)
    app = create_app(settings=api_settings, store=store, engine=engine)
    app.mount("/", StaticFiles(directory=ROOT / "caos" / "frontend" / "out", html=True), name="static")
    models = ModelService(store=store, vault_dir=settings.storage_dir, engine=engine)
    deliverables = DeliverableService(store=store, vault_dir=settings.storage_dir, engine=engine, models=models)
    stopped = threading.Event()
    errors: list[BaseException] = []
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="warning"))

    def work() -> None:
        try:
            while not stopped.is_set():
                if not run_pending(models, deliverables):
                    stopped.wait(0.2)
        except BaseException as exc:
            errors.append(exc)
            stopped.set()
            server.should_exit = True

    worker = threading.Thread(target=work, name="integration-worker", daemon=True)
    worker.start()
    print({"evidence": "integration only", "identity": "production trusted edge", "provider": "development host_control with canonical model answer key",
           "store": "isolated SQLite", "scanner": "explicit test double" if args.scanner_fixture else "real clamd"}, flush=True)
    async def drain() -> None:
        stopped.set()
        await asyncio.to_thread(worker.join, 30)
        if worker.is_alive():
            raise RuntimeError("integration worker failed to drain")
        await engine.aclose()
        close = getattr(provider, "aclose", None)
        if close:
            await close()

    async def serve() -> None:
        try:
            await engine.recover()
            await server.serve()
        finally:
            # Uvicorn replays SIGINT to asyncio after graceful server shutdown.
            # Keep ownership cleanup alive across that main-task cancellation.
            cleanup = asyncio.create_task(drain())
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                await cleanup

    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass
    finally:
        store.close()
    if errors:
        raise RuntimeError("integration worker failed") from errors[0]


if __name__ == "__main__":
    main()
