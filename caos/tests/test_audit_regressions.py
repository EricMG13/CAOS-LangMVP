"""Regressions from the 2026-08-27 fresh-context adversarial audit. Each test
pins a confirmed finding's fix; the red state was demonstrated by the audit."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parents[1] / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from caos.storage.store import DomainStore  # noqa: E402

from helpers import blank_pdf_bytes  # noqa: E402,F401  (import parity with suite)


def _seed(store):
    import hashlib

    case = store.create_case("Audit", "Issuer", "Services", "analyst")
    body = b"pinned evidence line"
    source = store.ingest({
        "case_id": case["id"], "filename": "doc.txt", "media_type": "text/plain",
        "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "vault_path": None,
        "blocks": [{"block_id": "b00001", "locator": {"line": 1}, "text": body.decode(),
                    "extractor_version": "builtin-v1", "confidence": "MEDIUM", "untrusted_data": True}],
        "withdrawn": False,
    }, "analyst")
    return case, source


def _service(store, tmp_path):
    from caos.deliverables.service import DeliverableService

    return DeliverableService(store=store, vault_dir=tmp_path / "vault")


def _draft(service, store, case, source):
    from caos.contracts import DeliverableDraftRequest

    template = service.templates()["FULL_CREDIT"]
    service.seed_accepted_authority_for_tests(case["id"])
    model = service.seed_signed_revision_for_tests(
        case["id"], outputs={"total_leverage": 4.2},
    )
    return service.save_draft(case["id"], "FULL_CREDIT", DeliverableDraftRequest(
        expected_version=0,
        template_id=template["template_id"],
        template_version=template["template_version"],
        model_selection={
            "kind": "ANALYST_REVISION",
            "build_id": model["build_id"],
            "revision_id": model["revision_id"],
        },
        blocks=[
            {"block_id": item["block_id"], "slot_id": item["slot_id"], "kind": "NARRATIVE", "text": "View.",
             "content_mode": "ANALYST_JUDGMENT", "citations": []}
            if item["kind"] == "NARRATIVE" else
            {"block_id": item["block_id"], "slot_id": item["slot_id"], "kind": "EVIDENCE_REGISTER", "citations": [
                {"source_id": source["id"], "block_ids": ["b00001"], "claim": "Supported."},
            ]}
            for item in template["blocks"]
        ],
    ), actor="analyst")


def _freeze(service, case, revision):
    from caos.contracts import FreezeDeliverableRequest, SignOpinionRequest

    if service.head_opinion(case["id"], "FULL_CREDIT") is None:
        service.sign_opinion(case["id"], "FULL_CREDIT", SignOpinionRequest(
            draft_id=revision["draft_id"], draft_version=revision["version"], draft_digest=revision["digest"],
            opinion="Hold.", limitations="None.", material_overrides="None.", rationale="Cited evidence supports the view.",
        ), actor="analyst")
    job = service.freeze(case["id"], FreezeDeliverableRequest(
        draft_id=revision["draft_id"], draft_version=revision["version"], draft_digest=revision["digest"],
    ), actor="analyst")
    service.run_pending_freezes()
    record = service.frozen_record_for_job(case["id"], job["job_id"])
    assert record is not None, service.freeze_job(case["id"], job["job_id"])
    return record


def test_freeze_refuses_a_citation_whose_source_was_withdrawn_after_save(tmp_path):
    store = DomainStore.from_url(f"sqlite:///{tmp_path / 'a.db'}")
    try:
        case, source = _seed(store)
        service = _service(store, tmp_path)
        revision = _draft(service, store, case, source)
        store.withdraw(case["id"], source["id"], "analyst")
        with pytest.raises(Exception, match="EVIDENCE_SOURCE_WITHDRAWN"):
            _freeze(service, case, revision)
        assert service.workspace(case["id"], "FULL_CREDIT")["frozen"] == []
    finally:
        store.close()


def test_freeze_retry_across_a_second_boundary_converges_on_one_record(tmp_path):
    store = DomainStore.from_url(f"sqlite:///{tmp_path / 'b.db'}")
    try:
        case, source = _seed(store)
        service = _service(store, tmp_path)
        revision = _draft(service, store, case, source)
        first = _freeze(service, case, revision)
        time.sleep(1.1)  # ponytail: the audit's exact repro — renders must be clock-free
        retried = _freeze(service, case, revision)
        assert retried["deliverable_id"] == first["deliverable_id"]
        assert retried["exports"] == first["exports"]
    finally:
        store.close()


async def test_queue_build_shares_the_admission_ceiling(tmp_path):
    from caos.config import Settings
    from caos.engine.budget import MAX_ACTIVE_JOBS
    from caos.engine.provider import host_control_identity
    from caos.engine.runtime import Engine
    from caos.models.service import ModelService
    from types import SimpleNamespace

    store = DomainStore.from_url(f"sqlite:///{tmp_path / 'c.db'}")
    engine = Engine.create(settings=Settings(storage_dir=tmp_path / "vault", agent_execution_enabled=True),
                           store=store, checkpoint_path=tmp_path / "ck.db",
                           provider=SimpleNamespace(identity=host_control_identity()))
    try:
        models = ModelService(store=store, vault_dir=tmp_path / "vault", engine=engine)
        models.fail_next_queue_for_tests()  # suppress the accept-time auto-queue
        case, _source = _seed(store)
        run = await engine.run_scripted_for_tests(case["id"])
        await engine.accept(run["id"], actor="analyst")
        engine.fill_admission_slots_for_tests(MAX_ACTIVE_JOBS)
        with pytest.raises(Exception, match="ADMISSION"):
            models.queue_build(case["id"], "analyst")
        engine.release_admission_slot_for_tests()
        assert models.queue_build(case["id"], "analyst")["created"] is True, "capacity returns"
    finally:
        try:
            await engine.aclose()
        finally:
            store.close()


def test_model_revision_mutation_is_refused_by_the_store_not_by_fiat(tmp_path):
    from caos.storage.models import ModelStore

    from caos.contracts import digest

    store = DomainStore.from_url(f"sqlite:///{tmp_path / 'd.db'}")
    try:
        model_store = ModelStore(store.engine)
        # A record that does not carry its own digests is refused before any
        # row or audit event exists: the store validates, then writes.
        with pytest.raises(ValueError, match="MODEL_REVISION_INTEGRITY_FAILED"):
            model_store.sign_off_revision("case-1", {
                "build_id": "bld-1", "assumptions_digest": "a" * 64,
            }, "analyst", None, store._audit)
        assert model_store.list_revisions("case-1") == []
        assert store.audit_trail() == []

        effective = [{"assumption_id": "growth", "value": 0.02}]
        outputs = {"leverage": 3.1}
        record = {
            "case_id": "case-1", "build_id": "bld-1",
            "effective_assumptions": effective, "assumptions_digest": digest(effective),
            "outputs": outputs, "outputs_digest": digest(outputs),
            "note": "signed by the analyst",
        }
        signed = model_store.sign_off_revision("case-1", record, "analyst", None, store._audit)
        with pytest.raises(ValueError, match="APPEND_ONLY"):
            store.mutate_model_revision_for_tests(signed["id"], {"record": {"note": "rewritten"}})
        assert model_store.get_revision(signed["id"])["assumptions_digest"] == digest(effective)
        model_store.update_revision_export(signed["id"], {"status": "READY"})  # job state stays writable
        assert model_store.get_revision(signed["id"])["export"]["status"] == "READY"
    finally:
        store.close()
