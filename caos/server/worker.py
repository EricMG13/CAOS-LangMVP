"""Model build/export worker (Dockerfile `worker` target).

The API image never renders XLSX (no LibreOffice there — enforced by
verify_image_resources.py); builds and exports queue in the store and this
process polls for QUEUED work and executes it. Claiming is the executor's own
CAS on the build row, so a concurrent duplicate worker loses the race cleanly.

`python worker.py --once` runs a single pass and exits (used by tests).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

from caos.config import Settings
from caos.engine.runtime import Engine
from caos.models.service import ModelService
from caos.observability import configure_logging, log_event
from caos.storage.store import DomainStore

EXPORT_FAILED = {"status": "FAILED", "error": {"code": "MODEL_EXPORT_FAILED",
                                               "detail": "The XLSX export did not complete."}}


def _failure(exc: Exception) -> str:
    """Exception class only: messages may quote document-derived model input."""
    return type(exc).__name__


def run_pending(service: ModelService) -> int:
    """One poll pass: execute every QUEUED build, then every QUEUED export.
    A crash in one item finalizes that item FAILED and never kills the loop."""
    work = service.builds.queued_work()
    for build_id in work["builds"]:
        # The identity this pass is dispatching. A re-point can requeue the row
        # under a new one mid-flight; this pass may only fail the row it took.
        dispatched = (service.build(build_id) or {}).get("input_fingerprint")
        try:
            service.run_build(build_id)
        except Exception as exc:
            log_event("worker.job_failed", level=logging.ERROR, kind="build", build_id=build_id,
                      detail=_failure(exc))
            service.builds.update_build(build_id, expected_status=("QUEUED", "BUILDING"),
                                        expected_input_fingerprint=dispatched,
                                        status="FAILED",
                                        error={"code": "MODEL_CALCULATION_FAILED",
                                               "detail": "The model calculation did not complete."})
    for target_id in work["exports"]:
        try:
            service.run_export(target_id)
        except Exception as exc:
            log_event("worker.job_failed", level=logging.ERROR, kind="export", target_id=target_id,
                      detail=_failure(exc))
            # Exports go QUEUED -> READY|FAILED with no intermediate state, so
            # binding to QUEUED means a dead pass can only fail the job it took:
            # never a published export, never one requeued under it.
            if service.builds.get_build(target_id) is not None:
                service.builds.update_build(target_id, expected_export_status="QUEUED", export=EXPORT_FAILED)
            else:
                service.builds.update_revision_export(target_id, EXPORT_FAILED, expected_export_status="QUEUED")
    return len(work["builds"]) + len(work["exports"])


def main() -> None:
    settings = Settings.from_env()
    settings.validate_runtime()
    configure_logging(settings)
    data = Path(os.getenv("CAOS_DATA_DIR", str(settings.storage_dir))).resolve()
    data.mkdir(parents=True, exist_ok=True)
    store = DomainStore.from_url(settings.database_url or f"sqlite:///{data / 'caos.db'}")
    engine = None
    try:
        # The engine here only lends the model service its snapshot/artifact reads
        # and admission accounting; this process never drives run graphs, so the
        # checkpoint file is never opened.
        engine = Engine.create(settings=settings, store=store, checkpoint_path=data / "checkpoints.db")
        service = ModelService(store=store, vault_dir=settings.storage_dir, engine=engine)
        poll_seconds = float(os.getenv("WORKER_POLL_SECONDS", "2"))
        once = "--once" in sys.argv[1:]
        with store.single_instance("worker"):
            while True:
                processed = run_pending(service)
                if once:
                    print({"processed": processed})
                    return
                if not processed:
                    time.sleep(poll_seconds)
    finally:
        try:
            if engine is not None:
                asyncio.run(engine.aclose())
        finally:
            store.close()


if __name__ == "__main__":
    main()
