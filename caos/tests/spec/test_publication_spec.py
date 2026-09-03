"""Opinion ownership, approver separation, worker-side freeze publication and the
detached filing receipt (Task 10; ENTERPRISE_READINESS_PLAN Phase 4 items 1–7,
11–12; ETR ANA-017–020, PUB-005, PUB-013/014, PUB-019–025).

Every gate here is a store CAS or a digest-bound interrupt (invariant 5). The
opinion is signed against the exact draft revision and every authority it
depends on; freeze refuses without a current sign-off; the frozen record exists
only after the worker has published and read back every export; the filing
approver must be independent of the signer and the freeze actor; the approver's
identity lives in a detached receipt, never in the approved bytes.
"""

from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError

from test_deliverables_spec import (
    ANALYST_H,
    APPROVER_H,
    OPINION,
    add_approver,
    bind_default_model_for_tests,
    draft_request,
    file_request,
    freeze_now,
    freeze_request,
    http_seed,
    ingest_second_source,
    make_service,
    required_blocks,
    save_min_draft,
    seed_ready_case,
    sign_min,
    sign_request,
)

ADMIN_H = {"x-caos-role": "ADMIN", "x-forwarded-user": "case-admin"}


@pytest.fixture()
def service(tmp_path, store):
    return make_service(store, tmp_path / "deliverable-vault")


def signed_min_draft(service, store, pathway="FULL_CREDIT", **kwargs):
    case, source, template, revision = save_min_draft(service, store, pathway, **kwargs)
    opinion = sign_min(service, case["id"], revision)
    return case, source, template, revision, opinion


# --- opinion sign-off -------------------------------------------------------------


def test_opinion_signoff_is_an_append_only_expected_head_cas_bound_to_the_exact_revision(service, store):
    from caos.contracts import digest
    from caos.storage.deliverables import deliverable_opinions

    case, source, template, revision = save_min_draft(service, store)
    assert service.head_opinion(case["id"], "FULL_CREDIT") is None

    first = service.sign_opinion(case["id"], "FULL_CREDIT", sign_request(revision), actor="analyst")
    assert first["signed_by"] == "analyst" and first["pathway"] == "FULL_CREDIT"
    assert (first["draft_id"], first["draft_version"], first["draft_digest"]) == (
        revision["draft_id"], revision["version"], revision["digest"],
    )
    assert first["revision_id"] == revision["revision_id"]
    assert {**first, "opinion_digest": None}["opinion_digest"] is None
    preimage = {key: value for key, value in first.items() if key not in {"opinion_digest", "seq"}}
    assert first["opinion_digest"] == digest(preimage), "the opinion digest covers the whole signed record"
    binding = first["binding"]
    assert set(binding) == {"snapshot_id", "source_set_id", "source_set_version", "model_identity_digest", "methodology_build_id"}
    assert binding["model_identity_digest"] == digest(revision["content"]["model_identity"])
    for field in ("opinion", "limitations", "material_overrides", "rationale"):
        assert first[field] == OPINION[field]

    with pytest.raises(Exception, match="OPINION_HEAD_CONFLICT") as conflict:
        service.sign_opinion(case["id"], "FULL_CREDIT", sign_request(revision), actor="analyst")
    assert getattr(conflict.value, "current", None)["opinion_id"] == first["opinion_id"], "the conflict carries the head"

    second = service.sign_opinion(
        case["id"], "FULL_CREDIT",
        sign_request(revision, expected_head_opinion_id=first["opinion_id"], opinion="Reduce: refinancing risk dominates."),
        actor="analyst",
    )
    assert second["opinion_id"] != first["opinion_id"] and second["supersedes_opinion_id"] == first["opinion_id"]
    assert service.head_opinion(case["id"], "FULL_CREDIT")["opinion_id"] == second["opinion_id"]
    history = service.opinion_history(case["id"], "FULL_CREDIT")
    assert [item["opinion_id"] for item in history] == [first["opinion_id"], second["opinion_id"]], "superseded opinions are retained (ANA-020)"

    events = [e for e in service.audit_events_for_tests(case["id"]) if e["action"] == "deliverable.opinion.signed"]
    assert [e["opinion_id"] for e in events] == [second["opinion_id"], first["opinion_id"]]

    with pytest.raises(DBAPIError, match="APPEND_ONLY"), store.engine.begin() as conn:
        conn.execute(sa.update(deliverable_opinions).where(deliverable_opinions.c.opinion_id == first["opinion_id"]).values(opinion="rewritten"))
    with pytest.raises(DBAPIError, match="APPEND_ONLY"), store.engine.begin() as conn:
        conn.execute(sa.delete(deliverable_opinions).where(deliverable_opinions.c.opinion_id == first["opinion_id"]))


@pytest.mark.parametrize("field", ["opinion", "limitations", "material_overrides", "rationale"])
def test_opinion_requires_every_statement_non_blank(service, store, field):
    from pydantic import ValidationError

    case, source, template, revision = save_min_draft(service, store)
    with pytest.raises(ValidationError):
        sign_request(revision, **{field: "   "})
    with pytest.raises(ValidationError):
        sign_request(revision, **{field: "a‮b"})  # bidirectional override is refused at the boundary


def test_opinion_binds_only_the_head_revision_and_live_evidence(service, store):
    case, source, template, revision = save_min_draft(service, store)
    later = service.save_draft(
        case["id"], "FULL_CREDIT",
        draft_request(template, source, expected_version=revision["version"], blocks=required_blocks(template, source, narrative_text="Revised view.")),
        actor="analyst",
    )
    with pytest.raises(Exception, match="OPINION_REVISION_STALE"):
        service.sign_opinion(case["id"], "FULL_CREDIT", sign_request(revision), actor="analyst")
    assert service.head_opinion(case["id"], "FULL_CREDIT") is None, "a stale sign-off appends nothing"
    forged = sign_request(later, draft_digest="0" * 64)
    with pytest.raises(Exception, match="OPINION_REVISION_STALE"):
        service.sign_opinion(case["id"], "FULL_CREDIT", forged, actor="analyst")
    store.withdraw(case["id"], source["id"], "analyst")
    with pytest.raises(Exception, match="EVIDENCE_SOURCE_WITHDRAWN"):
        service.sign_opinion(case["id"], "FULL_CREDIT", sign_request(later), actor="analyst")


def test_freeze_requires_a_current_opinion_and_refuses_a_stale_one(service, store):
    case, source, template, revision = save_min_draft(service, store)
    with pytest.raises(Exception, match="OPINION_SIGNOFF_REQUIRED"):
        service.freeze(case["id"], freeze_request(revision), actor="analyst")
    assert service.workspace(case["id"], "FULL_CREDIT")["pending_freezes"] == []

    sign_min(service, case["id"], revision)
    later = service.save_draft(
        case["id"], "FULL_CREDIT",
        draft_request(template, source, expected_version=revision["version"], blocks=required_blocks(template, source, narrative_text="Edited after signing.")),
        actor="analyst",
    )
    with pytest.raises(Exception, match="OPINION_SIGNOFF_STALE"):
        service.freeze(case["id"], freeze_request(later), actor="analyst")
    state = service.opinion_state(case["id"], "FULL_CREDIT")
    assert state["head"]["opinion_id"] and state["current"] is False
    assert "DRAFT_REVISION_CHANGED" in state["reasons"]

    sign_min(service, case["id"], later)
    assert service.opinion_state(case["id"], "FULL_CREDIT")["current"] is True
    ingest_second_source(store, case["id"])
    state = service.opinion_state(case["id"], "FULL_CREDIT")
    assert state["current"] is False and "SOURCE_SET_CHANGED" in state["reasons"]
    with pytest.raises(Exception, match="OPINION_SIGNOFF_STALE|SOURCE_SET_CHANGED"):
        service.freeze(case["id"], freeze_request(later), actor="analyst")


def test_superseded_upstream_authority_invalidates_the_signoff(service, store):
    case, source, template, revision = save_min_draft(service, store)
    sign_min(service, case["id"], revision)
    service.supersede_accepted_authority_for_tests(case["id"])
    state = service.opinion_state(case["id"], "FULL_CREDIT")
    assert state["current"] is False and "ACCEPTED_SNAPSHOT_CHANGED" in state["reasons"]
    # The composed document pins the snapshot too, so either typed refusal is
    # correct; what matters is that nothing freezes.
    with pytest.raises(Exception, match="OPINION_SIGNOFF_STALE|DELIVERABLE_COMPOSITION_MISMATCH"):
        service.freeze(case["id"], freeze_request(revision), actor="analyst")
    assert service.workspace(case["id"], "FULL_CREDIT")["pending_freezes"] == []


def test_frozen_payload_carries_the_signed_opinion_and_the_signer(service, store):
    case, source, template, revision, opinion = signed_min_draft(service, store)
    frozen = freeze_now(service, case["id"], revision, sign=False)
    assert frozen["signed_by"] == "analyst" and frozen["opinion_id"] == opinion["opinion_id"]
    pinned = frozen["payload"]["opinion"]
    assert pinned["opinion_id"] == opinion["opinion_id"] and pinned["opinion_digest"] == opinion["opinion_digest"]
    for field in ("opinion", "limitations", "material_overrides", "rationale", "signed_by", "signed_at"):
        assert pinned[field] == opinion[field]
    assert frozen["payload"]["publication"]["masthead"]["approval_state"] == "PENDING APPROVAL"
    assert frozen["payload"]["publication"]["masthead"]["opinion_owner"] == "analyst"
    assert "approved_by" not in str(frozen["payload"]), "frozen bytes never name an approver"


# --- ANALYST_JUDGMENT is not a citation bypass -----------------------------------------


@pytest.mark.parametrize("text", [
    "Leverage was 4.2x at FY2025.",
    "Revenue reached £95m in the period.",
    "Margins fell 310 bps year on year, to 18.4%.",
    "Liquidity of USD 1,250 million covers the 2027 maturity.",
    "The Q3 2026 covenant test was passed.",
])
def test_analyst_judgment_cannot_carry_an_uncited_quantitative_fact(service, store, text):
    case, source, _authority = seed_ready_case(service, store)
    template = service.templates()["FULL_CREDIT"]
    bind_default_model_for_tests(service, case, template)
    blocks = required_blocks(template, source, narrative_text=text)
    with pytest.raises(Exception, match="ANALYST_JUDGMENT_UNCITED_FACT"):
        service.save_draft(case["id"], "FULL_CREDIT", draft_request(template, blocks=blocks), actor="analyst")
    assert service.workspace(case["id"], "FULL_CREDIT")["draft"] is None, "a refused draft appends nothing"

    cited = required_blocks(template, source, narrative_text=text)
    for block in cited:
        if block["kind"] == "NARRATIVE":
            block["citations"] = [{"source_id": source["id"], "block_ids": ["b00001"], "claim": text}]
    assert service.save_draft(case["id"], "FULL_CREDIT", draft_request(template, blocks=cited), actor="analyst")["version"] == 1


@pytest.mark.parametrize("text", [
    "We estimate leverage near 4.2x by FY2026 under our base case.",
    "In our judgment the 2027 maturity is refinanceable.",
    "Assumption: revenue growth of 3% a year.",
    "Leverage is manageable and liquidity is adequate.",
])
def test_explicitly_framed_judgment_or_prose_without_figures_is_accepted(service, store, text):
    case, source, _authority = seed_ready_case(service, store)
    template = service.templates()["FULL_CREDIT"]
    bind_default_model_for_tests(service, case, template)
    blocks = required_blocks(template, source, narrative_text=text)
    saved = service.save_draft(case["id"], "FULL_CREDIT", draft_request(template, blocks=blocks), actor="analyst")
    assert saved["version"] == 1


def test_http_uncited_judgment_fact_is_a_typed_422(client, settings, store):
    svc, case, source, template = http_seed(settings, store)
    body = draft_request(template, blocks=required_blocks(template, source, narrative_text="EBITDA was 140m.")).model_dump(mode="json")
    response = client.put(f"/api/cases/{case['id']}/deliverables/FULL_CREDIT/draft", json=body, headers=ANALYST_H)
    assert response.status_code == 422 and response.json()["detail"]["code"] == "ANALYST_JUDGMENT_UNCITED_FACT"


# --- approver provisioning and separation of duties --------------------------------------


def test_approver_is_provisioned_through_the_members_route_without_database_seeding(client, settings, store):
    svc, case, source, template = http_seed(settings, store)
    url = f"/api/cases/{case['id']}/members"
    body = {"subject": "independent-approver", "role": "APPROVER"}
    assert client.post(url, json=body, headers=ANALYST_H).status_code == 403, "a case analyst cannot mint approvers"
    assert client.post(url, json=body, headers={"x-caos-role": "READER", "x-forwarded-user": "analyst"}).status_code == 403
    assert client.post(url, json=body, headers={"x-caos-role": "ADMIN", "x-forwarded-user": "outsider"}).status_code == 404, \
        "a non-member never learns the case exists, whatever the global role"
    store.add_member(case["id"], "analyst", "case-admin", "ADMIN", actor_role="ADMIN")
    created = client.post(url, json=body, headers=ADMIN_H)
    assert created.status_code == 201, created.text
    assert created.json()["members"]["independent-approver"] == "APPROVER"
    assert client.post(url, json={"subject": "x", "role": "OWNER"}, headers=ADMIN_H).status_code == 422
    events = [e for e in svc.audit_events_for_tests(case["id"]) if e["action"] == "case.member_added"]
    assert any(e["member"] == "independent-approver" and e["role"] == "APPROVER" and e["actor"] == "case-admin" for e in events)

    revision = svc.save_draft(case["id"], "FULL_CREDIT", draft_request(template, source), actor="analyst")
    frozen = freeze_now(svc, case["id"], revision)
    approve_url = f"/api/cases/{case['id']}/deliverables/by-id/{frozen['deliverable_id']}/approve"
    filed = client.post(approve_url, json=file_request(frozen).model_dump(mode="json"),
                        headers={"x-caos-role": "APPROVER", "x-forwarded-user": "independent-approver"})
    assert filed.status_code == 200 and filed.json()["status"] == "FILED"
    assert filed.json()["approved_by"] == "independent-approver"


def test_the_opinion_signer_and_the_freeze_actor_cannot_file_their_own_output(client, settings, store):
    svc, case, source, template = http_seed(settings, store)
    revision = svc.save_draft(case["id"], "FULL_CREDIT", draft_request(template, source), actor="analyst")
    # The signer freezes under a different subject so both roles are exercised.
    sign_min(svc, case["id"], revision, actor="signer")
    store.add_member(case["id"], "analyst", "signer", "APPROVER", actor_role="ADMIN")
    store.add_member(case["id"], "analyst", "freezer", "APPROVER", actor_role="ADMIN")
    job = svc.freeze(case["id"], freeze_request(revision), actor="freezer")
    svc.run_pending_freezes()
    frozen = svc.frozen_record_for_job(case["id"], job["job_id"])
    assert frozen["signed_by"] == "signer" and frozen["created_by"] == "freezer"
    url = f"/api/cases/{case['id']}/deliverables/by-id/{frozen['deliverable_id']}/approve"
    body = file_request(frozen).model_dump(mode="json")
    for subject in ("signer", "freezer"):
        refused = client.post(url, json=body, headers={"x-caos-role": "APPROVER", "x-forwarded-user": subject})
        assert refused.status_code == 403 and refused.json()["detail"]["code"] == "APPROVER_NOT_INDEPENDENT", subject
    assert svc.frozen_record(case["id"], frozen["deliverable_id"])["status"] == "FROZEN"
    add_approver(store, case)
    filed = client.post(url, json=body, headers=APPROVER_H)
    assert filed.status_code == 200 and filed.json()["approved_by"] == "approver-user"
    # Once filed the gate is closed: a late signer attempt meets the closed gate
    # (RESUME_NOT_APPLIED), never a second filing.
    with pytest.raises(Exception, match="RESUME_NOT_APPLIED"):
        svc.approve_filing(case["id"], frozen["deliverable_id"], file_request(frozen), actor="signer")


# --- freeze publishes through the worker -------------------------------------------------


def test_freeze_is_a_worker_job_and_the_frozen_record_exists_only_after_verified_publication(service, store):
    case, source, template, revision, _opinion = signed_min_draft(service, store)
    job = service.freeze(case["id"], freeze_request(revision), actor="analyst")
    assert job["status"] == "QUEUED" and job["pathway"] == "FULL_CREDIT" and job["draft_version"] == revision["version"]
    assert service.workspace(case["id"], "FULL_CREDIT")["frozen"] == [], "nothing is frozen before the worker publishes"
    assert [item["job_id"] for item in service.workspace(case["id"], "FULL_CREDIT")["pending_freezes"]] == [job["job_id"]]
    assert not [e for e in service.audit_events_for_tests(case["id"]) if e["action"] == "deliverable.frozen"]

    assert service.run_pending_freezes() == 1
    frozen = service.frozen_record_for_job(case["id"], job["job_id"])
    assert frozen["status"] == "FROZEN" and set(frozen["exports"]) == {"md", "pdf", "xlsx"}
    for format_name, recorded in frozen["exports"].items():
        content, sha = service.export(frozen["deliverable_id"], format_name)
        assert hashlib.sha256(content).hexdigest() == sha == recorded["sha256"] and len(content) == recorded["size"]
    published = service.freeze_job(case["id"], job["job_id"])
    assert published["status"] == "PUBLISHED" and published["deliverable_id"] == frozen["deliverable_id"]
    assert service.workspace(case["id"], "FULL_CREDIT")["pending_freezes"] == []
    assert service.run_pending_freezes() == 0, "a published job is never re-rendered"
    events = [e for e in service.audit_events_for_tests(case["id"]) if e["action"] in {"deliverable.freeze_queued", "deliverable.frozen"}]
    assert sorted(e["action"] for e in events) == ["deliverable.freeze_queued", "deliverable.frozen"]


def test_a_rendering_failure_leaves_a_typed_failed_job_and_no_frozen_record(tmp_path, store):
    def explode(payload, fmt):
        if fmt == "xlsx":
            raise RuntimeError("workbook renderer crashed")
        return b"%PDF-1.4 stub" if fmt == "pdf" else b"# stub\n"

    service = make_service(store, tmp_path / "vault", renderer_for_tests=explode)
    case, source, template, revision, _opinion = signed_min_draft(service, store)
    job = service.freeze(case["id"], freeze_request(revision), actor="analyst")
    assert service.run_pending_freezes() == 1
    failed = service.freeze_job(case["id"], job["job_id"])
    assert failed["status"] == "FAILED" and failed["error"] == {"code": "DELIVERABLE_RENDER_FAILED"}
    assert "crashed" not in str(failed), "the typed record never carries the renderer's message"
    assert service.workspace(case["id"], "FULL_CREDIT")["frozen"] == []
    assert not [e for e in service.audit_events_for_tests(case["id"]) if e["action"] == "deliverable.frozen"]
    assert [e["code"] for e in service.audit_events_for_tests(case["id"]) if e["action"] == "deliverable.freeze_failed"] == ["DELIVERABLE_RENDER_FAILED"]
    # The vault holds no half-published export set for this identity.
    vault_dir = tmp_path / "vault" / "deliverables"
    assert not any(path.suffix == ".xlsx" for path in vault_dir.rglob("*")) if vault_dir.exists() else True

    healthy = make_service(store, tmp_path / "vault")
    retried = healthy.freeze(case["id"], freeze_request(revision), actor="analyst")
    assert retried["job_id"] == job["job_id"] and retried["status"] == "QUEUED", "a retry requeues the failed identity"
    assert healthy.run_pending_freezes() == 1
    assert healthy.frozen_record_for_job(case["id"], job["job_id"])["status"] == "FROZEN"


def test_freeze_requests_are_idempotent_under_race_and_retry(service, store):
    case, source, template, revision, _opinion = signed_min_draft(service, store)
    with ThreadPoolExecutor(max_workers=2) as pool:
        raced = list(pool.map(lambda _: service.freeze(case["id"], freeze_request(revision), actor="analyst"), range(2)))
    assert len({job["job_id"] for job in raced}) == 1
    service.run_pending_freezes()
    frozen = service.frozen_record_for_job(case["id"], raced[0]["job_id"])
    replay = service.freeze(case["id"], freeze_request(revision), actor="analyst")
    assert replay["status"] == "PUBLISHED" and replay["deliverable_id"] == frozen["deliverable_id"]
    assert len(service.workspace(case["id"], "FULL_CREDIT")["frozen"]) == 1
    assert len([e for e in service.audit_events_for_tests(case["id"]) if e["action"] == "deliverable.frozen"]) == 1


def test_a_worker_crash_mid_render_is_recovered_by_requeue_on_the_next_start(service, store):
    case, source, template, revision, _opinion = signed_min_draft(service, store)
    job = service.freeze(case["id"], freeze_request(revision), actor="analyst")
    assert service.records.claim_freeze_job(job["job_id"]) is not None, "worker A claims the job and dies"
    assert service.freeze_job(case["id"], job["job_id"])["status"] == "RENDERING"
    assert service.run_pending_freezes() == 0, "a claimed job is never stolen mid-pass"
    assert service.recover_freeze_jobs() == 1
    assert service.freeze_job(case["id"], job["job_id"])["status"] == "QUEUED"
    assert service.run_pending_freezes() == 1
    assert service.frozen_record_for_job(case["id"], job["job_id"])["status"] == "FROZEN"


def test_a_divergent_render_for_a_published_identity_is_a_freeze_conflict(tmp_path, store):
    vault = tmp_path / "shared-vault"
    service = make_service(store, vault)
    case, source, template, revision, _opinion = signed_min_draft(service, store)
    frozen = freeze_now(service, case["id"], revision, sign=False)
    divergent = make_service(store, vault, renderer_for_tests=lambda payload, fmt: b"DIFFERENT RENDER BYTES")
    job = divergent.freeze_job(case["id"], service.freeze(case["id"], freeze_request(revision), actor="analyst")["job_id"])
    with pytest.raises(Exception, match="DELIVERABLE_FREEZE_CONFLICT"):
        divergent.rerender_freeze_job_for_tests(job["job_id"])
    assert service.frozen_record(case["id"], frozen["deliverable_id"])["exports"] == frozen["exports"], "the gate's own render is the only render"


def test_http_freeze_returns_the_job_and_the_workspace_tracks_it_to_a_frozen_record(client, settings, store):
    svc, case, source, template = http_seed(settings, store)
    url = f"/api/cases/{case['id']}/deliverables/FULL_CREDIT"
    saved = client.put(f"{url}/draft", json=draft_request(template, source).model_dump(mode="json"), headers=ANALYST_H).json()["current"]
    signed = client.post(f"{url}/opinion", json={
        "draft_id": saved["draft_id"], "draft_version": saved["version"], "draft_digest": saved["digest"],
        "expected_head_opinion_id": None, **OPINION,
    }, headers=ANALYST_H)
    assert signed.status_code == 201, signed.text
    assert signed.json()["signed_by"] == "analyst" and signed.json()["draft_digest"] == saved["digest"]
    workspace = client.get(f"{url}/draft", headers=ANALYST_H).json()
    assert workspace["opinion"]["head"]["opinion_id"] == signed.json()["opinion_id"] and workspace["opinion"]["current"] is True

    queued = client.post(f"{url}/freeze", json={"draft_id": saved["draft_id"], "draft_version": saved["version"], "draft_digest": saved["digest"]}, headers=ANALYST_H)
    assert queued.status_code == 202, queued.text
    job = queued.json()
    assert job["status"] == "QUEUED" and job["deliverable_id"] is None
    workspace = client.get(f"{url}/draft", headers=ANALYST_H).json()
    assert [item["job_id"] for item in workspace["pending_freezes"]] == [job["job_id"]] and workspace["frozen_history"] == []
    assert client.get(f"/api/cases/{case['id']}/deliverables/freeze-jobs/{job['job_id']}", headers=ANALYST_H).json()["status"] == "QUEUED"

    svc.run_pending_freezes()
    workspace = client.get(f"{url}/draft", headers=ANALYST_H).json()
    assert workspace["pending_freezes"] == [] and len(workspace["frozen_history"]) == 1
    frozen = workspace["frozen_history"][0]
    assert frozen["status"] == "FROZEN" and frozen["signed_by"] == "analyst" and frozen["opinion_id"] == signed.json()["opinion_id"]
    tracked = client.get(f"/api/cases/{case['id']}/deliverables/freeze-jobs/{job['job_id']}", headers=ANALYST_H).json()
    assert tracked["status"] == "PUBLISHED" and tracked["deliverable_id"] == frozen["id"]
    assert client.get(f"/api/cases/{case['id']}/deliverables/freeze-jobs/{job['job_id']}", headers={"x-caos-role": "ADMIN", "x-forwarded-user": "outsider"}).status_code == 404


# --- the detached filing receipt ----------------------------------------------------------


def test_filing_writes_an_immutable_detached_receipt_and_leaves_the_approved_bytes_untouched(client, settings, store):
    from caos.contracts import digest
    from caos.storage.deliverables import deliverable_filing_receipts

    svc, case, source, template = http_seed(settings, store)
    revision = svc.save_draft(case["id"], "FULL_CREDIT", draft_request(template, source), actor="analyst")
    frozen = freeze_now(svc, case["id"], revision)
    before = {fmt: svc.export(frozen["deliverable_id"], fmt)[0] for fmt in frozen["exports"]}
    add_approver(store, case)
    receipt_url = f"/api/cases/{case['id']}/deliverables/by-id/{frozen['deliverable_id']}/receipt"
    assert client.get(receipt_url, headers=ANALYST_H).status_code == 404, "no receipt exists before filing"

    filed = client.post(f"/api/cases/{case['id']}/deliverables/by-id/{frozen['deliverable_id']}/approve",
                        json=file_request(frozen).model_dump(mode="json"), headers=APPROVER_H).json()
    receipt = client.get(receipt_url, headers=ANALYST_H)
    assert receipt.status_code == 200, receipt.text
    body = receipt.json()
    assert body["deliverable_id"] == frozen["deliverable_id"] and body["approved_by"] == "approver-user"
    assert body["approved_at"] == filed["approved_at"]
    assert body["opinion_id"] == frozen["opinion_id"] and body["signed_by"] == "analyst"
    assert body["preview_digest"] == frozen["preview_digest"] and body["input_fingerprint"] == frozen["input_fingerprint"]
    assert body["approval_hash"] == f"sha256:{frozen['preview_digest']}"
    assert body["exports"] == {fmt: meta["sha256"] for fmt, meta in frozen["exports"].items()}
    preimage = {key: value for key, value in body.items() if key != "receipt_digest"}
    assert body["receipt_digest"] == digest(preimage)
    for fmt, content in before.items():
        assert svc.export(frozen["deliverable_id"], fmt)[0] == content, "filing never rerenders or touches the approved bytes"
        assert b"approver-user" not in content, "the approver's name is not in the approved bytes"
    assert client.get(receipt_url, headers={"x-caos-role": "ADMIN", "x-forwarded-user": "outsider"}).status_code == 404
    with pytest.raises(DBAPIError, match="APPEND_ONLY"), store.engine.begin() as conn:
        conn.execute(sa.update(deliverable_filing_receipts).values(receipt_digest="f" * 64))
    with pytest.raises(DBAPIError, match="APPEND_ONLY"), store.engine.begin() as conn:
        conn.execute(sa.delete(deliverable_filing_receipts))


def test_concurrent_filers_yield_one_receipt_and_one_typed_loser(service, store):
    case, source, template, revision, _opinion = signed_min_draft(service, store)
    frozen = freeze_now(service, case["id"], revision, sign=False)
    add_approver(store, case)
    store.add_member(case["id"], "analyst", "second-approver", "APPROVER", actor_role="ADMIN")

    def approve(actor):
        try:
            return ("filed", service.approve_filing(case["id"], frozen["deliverable_id"], file_request(frozen), actor=actor))
        except Exception as exc:  # noqa: BLE001 — the losing racer's typed refusal
            return ("refused", exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(approve, ["approver-user", "second-approver"]))
    assert sorted(kind for kind, _ in outcomes) == ["filed", "refused"]
    loser = next(value for kind, value in outcomes if kind == "refused")
    assert "RESUME_NOT_APPLIED" in str(loser)
    receipts = service.filing_receipts_for_tests(case["id"])
    assert len(receipts) == 1 and receipts[0]["deliverable_id"] == frozen["deliverable_id"]
    filed = next(value for kind, value in outcomes if kind == "filed")
    assert receipts[0]["approved_by"] == filed["filed_by"]
    assert len([e for e in service.audit_events_for_tests(case["id"]) if e["action"] == "deliverable.filed"]) == 1


def test_filed_download_is_audited_and_tampering_is_detected_on_download(client, settings, store):
    svc, case, source, template = http_seed(settings, store)
    revision = svc.save_draft(case["id"], "FULL_CREDIT", draft_request(template, source), actor="analyst")
    frozen = freeze_now(svc, case["id"], revision)
    add_approver(store, case)
    client.post(f"/api/cases/{case['id']}/deliverables/by-id/{frozen['deliverable_id']}/approve",
                json=file_request(frozen).model_dump(mode="json"), headers=APPROVER_H)
    export_url = f"/api/cases/{case['id']}/deliverables/by-id/{frozen['deliverable_id']}/export/pdf"
    served = client.get(export_url, headers=ANALYST_H)
    assert served.status_code == 200 and served.headers["x-caos-sha256"] == frozen["exports"]["pdf"]["sha256"]
    downloads = [e for e in svc.audit_events_for_tests(case["id"]) if e["action"] == "deliverable.exported"]
    assert len(downloads) == 1 and downloads[0]["deliverable_id"] == frozen["deliverable_id"] and downloads[0]["actor"] == "analyst"
    svc.tamper_export_for_tests(frozen["deliverable_id"], "pdf")
    tampered = client.get(export_url, headers=ANALYST_H)
    assert tampered.status_code == 409 and tampered.json()["detail"]["code"] == "DELIVERABLE_EXPORT_INTEGRITY_FAILED"
    assert len([e for e in svc.audit_events_for_tests(case["id"]) if e["action"] == "deliverable.exported"]) == 1, \
        "a refused download leaves no audit residue"


# --- The font pin (CI follow-up, 2026-09-03) -------------------------------------
# Two CI hosts paginated the same frozen payload differently because pango-view
# resolved "sans" and "monospace" through each host's fontconfig (Verdana and
# Andale Mono on a developer Mac, DejaVu on Ubuntu, Noto CJK's Latin in the
# image). The renderer now ships its own DejaVu bundle, verified on the bytes at
# use, through a hermetic fontconfig; these two tests pin that seam directly and
# the cross-format goldens pin its page counts.

_LATIN_PAYLOAD = {
    "pathway": "FULL_CREDIT",
    "content": {"blocks": [{"block_id": "b", "slot_id": "s", "kind": "NARRATIVE", "text": "Pinned narrative body. Leverage is manageable."}]},
    "template": {"block_titles": {}}, "draft": {"version": 1, "digest": "d"}, "preview_digest": "p",
    "input_fingerprint": "f", "methodology": {"build_id": "b"},
}


def test_pdf_glyphs_come_from_the_vendored_font_bundle_alone():
    import io

    from pypdf import PdfReader

    from caos.publishing import renderers

    for filename, expected in renderers.FONT_BUNDLE.items():
        assert hashlib.sha256((renderers.FONT_DIR / filename).read_bytes()).hexdigest() == expected, filename
    reader = PdfReader(io.BytesIO(renderers.render_frozen_pdf(_LATIN_PAYLOAD)))
    embedded = {
        str(font.get("/BaseFont")).split("+")[-1]
        for page in reader.pages for font in page["/Resources"]["/Font"].values()
    }
    assert embedded <= {"DejaVuSans", "DejaVuSans-Bold", "DejaVuSansMono", "DejaVuSansMono-Bold"}, embedded
    text = "".join(page.extract_text() or "" for page in reader.pages)
    assert "Pinned narrative body. Leverage is manageable." in text, "kerned pairs extract without a rounding gap"


def test_a_font_bundle_that_fails_verification_refuses_to_render(monkeypatch):
    from caos.publishing import renderers

    monkeypatch.setitem(renderers.FONT_BUNDLE, "DejaVuSans.ttf", "0" * 64)
    with pytest.raises(ValueError, match="PDF_FONT_BUNDLE_INVALID"):
        renderers.render_frozen_pdf(_LATIN_PAYLOAD)
