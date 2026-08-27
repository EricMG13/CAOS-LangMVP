"""Worker loop: polling finds QUEUED work, claims it by CAS, and a broken item
finalizes FAILED without killing the pass."""

from __future__ import annotations

import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1] / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

import worker  # noqa: E402

from caos.engine.runtime import Engine  # noqa: E402
from caos.models.service import ModelService  # noqa: E402


def _service(tmp_path, settings, store) -> ModelService:
    engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "checkpoints.db")
    return ModelService(store=store, vault_dir=settings.storage_dir, engine=engine)


def test_single_pass_is_a_noop_on_an_empty_store(tmp_path, settings, store):
    assert worker.run_pending(_service(tmp_path, settings, store)) == 0


def test_single_pass_claims_a_queued_build_and_finalizes_failed_on_broken_refs(tmp_path, settings, store):
    service = _service(tmp_path, settings, store)
    case = store.create_case("Worker", "Issuer", "Services", "analyst")
    service.builds.insert_build_row({
        "id": "build-worker-test", "case_id": case["id"], "status": "QUEUED",
        "accepted_run_id": "run-missing", "snapshot_id": "snap-missing",
        "input_fingerprint": "f" * 64, "queued_at": "2026-08-27T00:00:00+00:00",
        "created_by": "analyst",
    })
    assert worker.run_pending(service) == 1
    build = service.build("build-worker-test")
    assert build["status"] == "FAILED", "a build with unresolvable inputs must finalize FAILED"
    assert build["error"]["code"] in {"MODEL_INPUT_INVALID", "MODEL_CALCULATION_FAILED"}
    assert worker.run_pending(service) == 0, "a finalized build must not be re-claimed"
