"""Worker loop: polling finds QUEUED work, claims it by CAS, and a broken item
finalizes FAILED without killing the pass — plus the two authority properties a
single-worker test cannot see: a lost claim never computes, and a calculation
never publishes under an identity it was not computed from."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1] / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

import worker  # noqa: E402

from caos.engine.runtime import Engine  # noqa: E402
from caos.models.service import ModelService  # noqa: E402

import pytest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent / "spec"))
from spec_helpers import ScriptedProvider, seed_case_with_source  # noqa: E402


def _service(tmp_path, settings, store) -> ModelService:
    engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "checkpoints.db")
    return ModelService(store=store, vault_dir=settings.storage_dir, engine=engine)


async def test_single_pass_is_a_noop_on_an_empty_store(tmp_path, settings, store):
    service = _service(tmp_path, settings, store)
    try:
        assert worker.run_pending(service) == 0
    finally:
        await service.engine.aclose()


async def test_single_pass_claims_a_queued_build_and_finalizes_failed_on_broken_refs(tmp_path, settings, store):
    service = _service(tmp_path, settings, store)
    try:
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
    finally:
        await service.engine.aclose()


async def _queued_build(models, engine, store):
    case, _source = seed_case_with_source(store)
    run = await engine.run_scripted_for_tests(case["id"])
    await engine.accept(run["id"], actor="analyst")
    return models.queue_build(case["id"], "analyst")


def _service_on(engine, settings, store) -> ModelService:
    return ModelService(store=store, vault_dir=settings.storage_dir, engine=engine)


def _engine_for_scripted_model(tmp_path, settings, store) -> Engine:
    return Engine.create(
        settings=replace(settings, agent_execution_enabled=True), store=store,
        checkpoint_path=tmp_path / "ck.db", provider=ScriptedProvider(),
    )


async def test_a_lost_claim_never_computes_and_never_touches_the_winner(tmp_path, settings, store):
    engine = _engine_for_scripted_model(tmp_path, settings, store)
    try:
        models = _service_on(engine, settings, store)
        queued = await _queued_build(models, engine, store)

        assert models.builds.update_build(queued["id"], expected_status=("QUEUED", "FAILED"),
                                          status="BUILDING"), "worker A wins the claim"
        # Worker B polls the same row. Losing the CAS is not a failure and not a
        # licence to compute: the row is left exactly as the winner holds it.
        loser = models.run_build(queued["id"])
        assert loser["status"] == "BUILDING", "the loser leaves the winner's row untouched"
        assert loser.get("payload") is None, "the loser published nothing"
    finally:
        await engine.aclose()


async def test_a_repointed_build_never_publishes_the_abandoned_calculation(tmp_path, settings, store):
    engine = _engine_for_scripted_model(tmp_path, settings, store)
    try:
        models = _service_on(engine, settings, store)
        queued = await _queued_build(models, engine, store)
        build_id = queued["id"]

        claimed = models.builds.get_build(build_id)
        models.builds.update_build(build_id, expected_status=("QUEUED", "FAILED"), status="BUILDING")
        result, identity = models._compute_build_result(claimed)   # worker A is mid-calculation

        # A newer accepted snapshot re-points the standing job under it.
        repointed = models.builds.update_build(build_id, expected_status=("QUEUED", "BUILDING"),
                                               status="QUEUED", input_fingerprint="e" * 64)
        assert repointed, "a re-point requeues the row rather than mutating an executing identity"

        with pytest.raises(ValueError, match="MODEL_RESULT_INVALID"):
            models._complete(build_id, result, identity,
                             expected_fingerprint=claimed["input_fingerprint"])
        after = models.builds.get_build(build_id)
        assert after["status"] == "QUEUED", "the requeued row survives the abandoned executor"
        assert after["payload"] is None and after["input_fingerprint"] == "e" * 64
    finally:
        await engine.aclose()


async def test_a_crashing_pass_never_fails_a_row_that_was_repointed_under_it(tmp_path, settings, store):
    """The loop's own fallback is an identity-bound write too: a calculation that
    dies after a re-point must not drag the requeued build down with it."""
    engine = _engine_for_scripted_model(tmp_path, settings, store)
    try:
        models = _service_on(engine, settings, store)
        queued = await _queued_build(models, engine, store)
        build_id = queued["id"]

        def explode_after_repoint(_build_id: str) -> None:
            models.builds.update_build(build_id, expected_status=("QUEUED", "BUILDING"),
                                       status="QUEUED", input_fingerprint="e" * 64)
            raise RuntimeError("the calculation died")

        models.run_build = explode_after_repoint  # type: ignore[method-assign]
        assert worker.run_pending(models) == 1

        after = models.builds.get_build(build_id)
        assert after["status"] == "QUEUED", "the requeued build survives the dead pass"
        assert after["error"] is None and after["input_fingerprint"] == "e" * 64
    finally:
        await engine.aclose()


async def test_a_crashing_export_pass_never_clobbers_an_export_published_under_it(tmp_path, settings, store):
    """Same rule on the export half: the fallback writes the whole export blob,
    so without a CAS a dead pass overwrites a READY export with FAILED."""
    engine = _engine_for_scripted_model(tmp_path, settings, store)
    try:
        models = _service_on(engine, settings, store)
        queued = await _queued_build(models, engine, store)
        build_id = queued["id"]
        models.run_build(build_id)  # only the export is outstanding
        models.builds.update_build(build_id, export={"status": "QUEUED"})

        def explode_after_publish(_target_id: str) -> None:
            models.builds.update_build(build_id, export={"status": "READY", "sha256": "a" * 64})
            raise RuntimeError("the export died")

        models.run_export = explode_after_publish  # type: ignore[method-assign]
        assert worker.run_pending(models) == 1

        export = models.builds.get_build(build_id)["export"]
        assert export["status"] == "READY", "a published export survives the dead pass"
        assert export.get("error") is None
    finally:
        await engine.aclose()
