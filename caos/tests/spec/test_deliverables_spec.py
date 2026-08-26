"""Deliverables specification (invariant 5; DECISIONS §2, §10.5/10.7, §12.21-23).

All tests must FAIL today: every unbuilt import (caos.deliverables.*, caos.api via the
client/app fixtures) happens inside test bodies, fixtures, or helpers called from them.
A passing test in this file is a defect.

Sources: TEST_INVENTORY.md contractual rows for test_deliverables.py (21),
test_deliverable_exports.py (8), the two deliverable rows of test_ledger_contracts.py,
and the eight approval-gate rows of test_cp_dr_planning.py re-hosted onto the deliverable
filing interrupt per DECISIONS §11.9. Full row map at the end of the file.

Specification decisions this file pins (beyond the porting briefs):
- DeliverableService(store=..., vault_dir=..., engine=...) with workspace / save_draft /
  freeze / approve_filing / request_changes / export / templates. Freeze parks a
  filing-gate thread (freeze -> render -> interrupt() -> file | request-changes, §2).
- workspace(case_id, pathway) -> {"template", "draft" (current revision | None), "frozen" (list)}.
- Revision record: {draft_id, revision_id, version, digest, content}; frozen record:
  {deliverable_id, thread_id, status, preview_digest, input_fingerprint, build_id,
  payload, exports: {fmt: {sha256, size}}}.
- Typed errors are matched by their code substring in str(exc) (same convention as
  test_runs_spec.py); audit actions: deliverable.draft.saved / .frozen / .filed /
  .changes_requested.
- Required template slots are limited to HEADING / NARRATIVE / EVIDENCE_REGISTER /
  LIMITATIONS; model-dependent kinds are optional-only; optional slot ids are
  f"{slot_stem}-{n}". Every template has at least two required slots.
- service.export works from FROZEN (the gate's own render); the HTTP export route serves
  FILED only (pre-filing 409) and never re-renders (§12.23).
- The gate-level canonical approval hash is "sha256:" + preview_digest and matches
  ^sha256:[0-9a-f]{64}$ (re-hosted planning-gate contract); the HTTP request models keep
  their bare-64-hex fields.
- For-tests hooks invented on the future service (clearly suffixed): _for_tests hooks for
  seeding accepted authority / signed revisions / application builds, scenario previews,
  tampering frozen payloads and stored exports, deleting exports, terminating filing
  threads, reading audit events and thread state, and a renderer_for_tests constructor
  kwarg plus resume_filing_with_hash_for_tests.

Merged/adapted rows are documented in the ROW MAPPING block at the end.
"""

from __future__ import annotations

import copy
import hashlib
import io
import re
from concurrent.futures import ThreadPoolExecutor

import pytest

from spec_helpers import seed_case_with_source

SIX_PATHWAYS = (
    "FULL_CREDIT",
    "EARNINGS_UPDATE",
    "COVENANT_REFINANCING",
    "RELATIVE_VALUE",
    "DISTRESSED_RESTRUCTURING",
    "DEEP_RESEARCH",
)

ANALYST_H = {"x-caos-role": "ANALYST", "x-forwarded-user": "analyst"}
APPROVER_H = {"x-caos-role": "APPROVER", "x-forwarded-user": "approver-user"}

SHOCK = {"assumption_id": "revenue_growth", "case": "DOWNSIDE", "period_id": "FY2026", "value": -0.05}


# --- helpers (unbuilt imports stay inside; called only from test bodies) ----------


def make_service(store, vault_dir, **overrides):
    from caos.deliverables.service import DeliverableService

    return DeliverableService(store=store, vault_dir=vault_dir, engine=overrides.pop("engine", None), **overrides)


@pytest.fixture()
def service(tmp_path, store):
    return make_service(store, tmp_path / "deliverable-vault")


def _never_render(payload, fmt):
    raise AssertionError("filing never re-renders (§12.23)")


def required_blocks(template, source, *, narrative_text="Leverage is manageable."):
    """Blocks satisfying every required template slot, in template order.

    Spec: required slots use only non-model kinds — anything else is a template defect.
    """
    blocks = []
    for slot in template["slots"]:
        base = {"block_id": f"blk-{slot['slot_id']}", "slot_id": slot["slot_id"]}
        kind = slot["kind"]
        if kind == "HEADING":
            blocks.append({**base, "kind": "HEADING", "text": "Credit Opinion"})
        elif kind == "NARRATIVE":
            blocks.append({**base, "kind": "NARRATIVE", "text": narrative_text, "content_mode": "ANALYST_JUDGMENT", "citations": []})
        elif kind == "EVIDENCE_REGISTER":
            blocks.append({**base, "kind": "EVIDENCE_REGISTER", "citations": [
                {"source_id": source["id"], "block_ids": ["b00001"], "claim": "Pinned evidence line supports the opinion."},
            ]})
        elif kind == "LIMITATIONS":
            blocks.append({**base, "kind": "LIMITATIONS", "text": "Scope-limited review.", "citations": []})
        else:
            raise AssertionError(f"required slots must be non-model kinds, got {kind}")
    return blocks


def draft_request(template, source=None, *, blocks=None, expected_version=0, model_selection=None, extra_blocks=()):
    from caos.contracts import DeliverableDraftRequest

    if blocks is None:
        blocks = required_blocks(template, source) + list(extra_blocks)
    return DeliverableDraftRequest(
        expected_version=expected_version,
        template_id=template["template_id"],
        template_version=template["template_version"],
        model_selection=model_selection,
        blocks=blocks,
    )


def freeze_request(revision):
    from caos.contracts import FreezeDeliverableRequest

    return FreezeDeliverableRequest(draft_id=revision["draft_id"], draft_version=revision["version"], draft_digest=revision["digest"])


def file_request(frozen, **overrides):
    from caos.contracts import FileDeliverableRequest

    fields = {"preview_digest": frozen["preview_digest"], "input_fingerprint": frozen["input_fingerprint"]}
    fields.update(overrides)
    return FileDeliverableRequest(**fields)


def optional_slot(template, kind, n=1):
    policy = next(p for p in template["optional_blocks"] if p["kind"] == kind)
    return f"{policy['slot_stem']}-{n}"


def optional_block(template, kind, n=1, **fields):
    slot = optional_slot(template, kind, n)
    base = {"block_id": f"blk-{slot}", "slot_id": slot, "kind": kind}
    defaults = {
        "GENERATED_METRIC": {"metric_ids": ["total_leverage"]},
        "GENERATED_TABLE": {"table_id": "debt_schedule", "field_ids": ["instrument", "amount"]},
        "GENERATED_CHART": {"recipe": {"chart_kind": "line", "fields": ["total_leverage"]}},
        "MODEL_APPENDIX": {},
        "LIMITATIONS": {"text": "Covenant definitions unavailable.", "citations": []},
    }
    base.update(defaults[kind])
    base.update(fields)
    return base


def scenario_exhibit_block(template, preview, n=1, **overrides):
    slot = optional_slot(template, "SCENARIO_EXHIBIT", n)
    block = {
        "block_id": f"blk-{slot}",
        "slot_id": slot,
        "kind": "SCENARIO_EXHIBIT",
        "title": "Downside revenue shock",
        "shocks": preview["shocks"],
        "scenario": preview["scenario"],
        "scenario_digest": preview["scenario_digest"],
    }
    block.update(overrides)
    return block


def revision_selection(model):
    return {"kind": "ANALYST_REVISION", "build_id": model["build_id"], "revision_id": model["revision_id"]}


def seed_ready_case(service, store):
    """Case + source + the pinned upstream accepted authority freeze requires."""
    case, source = seed_case_with_source(store)
    authority = service.seed_accepted_authority_for_tests(case["id"])
    return case, source, authority


def seed_model(service, case, *, outputs=None):
    """Signed analyst revision + its READY application build; returns identity + payloads:
    {build_id, revision_id, outputs, assumptions, build_payload, build_qa}."""
    return service.seed_signed_revision_for_tests(case["id"], outputs=outputs or {"total_leverage": 4.2})


def save_min_draft(service, store, pathway="FULL_CREDIT", **kwargs):
    case, source, _ = seed_ready_case(service, store)
    template = service.templates()[pathway]
    revision = service.save_draft(case["id"], pathway, draft_request(template, source, **kwargs), actor="analyst")
    return case, source, template, revision


def freeze_min(service, store, pathway="FULL_CREDIT"):
    case, source, template, revision = save_min_draft(service, store, pathway)
    frozen = service.freeze(case["id"], freeze_request(revision), actor="analyst")
    return case, source, revision, frozen


def add_approver(store, case):
    store.add_member(case["id"], "analyst", "approver-user", "APPROVER", actor_role="ADMIN")


def frozen_deliverable(service, store, pathway="FULL_CREDIT"):
    case, source, revision, frozen = freeze_min(service, store, pathway)
    add_approver(store, case)
    return case, revision, frozen


def http_seed(settings, store, pathway="FULL_CREDIT"):
    """Service twin over the app's own store + vault so seeding hooks feed HTTP routes."""
    svc = make_service(store, settings.storage_dir)
    case, source = seed_case_with_source(store)
    svc.seed_accepted_authority_for_tests(case["id"])
    template = svc.templates()[pathway]
    return svc, case, source, template


def ingest_second_source(store, case_id, body=b"late-arriving evidence"):
    return store.ingest({
        "case_id": case_id,
        "filename": "late.txt",
        "media_type": "text/plain",
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "vault_path": None,
        "blocks": [{"block_id": "b00002", "locator": {"line": 1}, "text": body.decode(), "extractor_version": "builtin-v1", "confidence": "MEDIUM", "untrusted_data": True}],
        "withdrawn": False,
    }, "analyst")


# --- template registry ------------------------------------------------------------


def test_template_registry_serves_six_pathways_with_stable_identity_and_evidence_register(service):
    templates = service.templates()
    assert set(templates) == set(SIX_PATHWAYS)
    assert service.templates() == templates, "registry identity is stable across reads"
    for pathway, template in templates.items():
        assert template["template_id"] and template["template_version"], pathway
        slot_ids = [s["slot_id"] for s in template["slots"]]
        assert len(slot_ids) == len(set(slot_ids)), f"{pathway}: slot ids must be unique"
        assert [s for s in template["slots"] if s["kind"] == "EVIDENCE_REGISTER"], f"{pathway}: mandatory evidence register"


def test_template_owns_optional_block_kind_stem_cap_order_and_model_dependence(service):
    template = service.templates()["RELATIVE_VALUE"]
    policy = template["optional_blocks"]
    for entry in policy:
        assert {"kind", "slot_stem", "max", "order", "model_dependent"} <= set(entry)
    by_kind = {entry["kind"]: entry for entry in policy}
    for kind in ("GENERATED_METRIC", "GENERATED_TABLE", "GENERATED_CHART", "SCENARIO_EXHIBIT", "MODEL_APPENDIX"):
        assert by_kind[kind]["model_dependent"] is True, kind
    assert by_kind["LIMITATIONS"]["model_dependent"] is False
    assert set(template["allowed_appendices"]) == set(by_kind), "allowed appendices derive from the optional policy"


# --- draft save + append-only revisions -------------------------------------------


def test_saved_revision_digest_is_digest_of_content_and_order_violation_appends_nothing(service, store):
    from caos.contracts import digest

    case, source, template, revision = save_min_draft(service, store)
    assert revision["version"] == 1
    assert revision["digest"] == digest(revision["content"]), "revision is content-addressed"
    blocks = required_blocks(template, source)
    assert len(blocks) >= 2, "spec premise: every template has at least two required slots"
    with pytest.raises(Exception, match="DELIVERABLE_TEMPLATE_ORDER_INVALID"):
        service.save_draft(case["id"], "FULL_CREDIT", draft_request(template, blocks=list(reversed(blocks)), expected_version=1), actor="analyst")
    assert service.workspace(case["id"], "FULL_CREDIT")["draft"]["version"] == 1, "nothing appended on order violation"


def test_stale_expected_version_is_atomic_cas_conflict_carrying_current_head(service, store):
    case, source, template, revision = save_min_draft(service, store)

    def racing_save(text):
        blocks = required_blocks(template, source, narrative_text=text)
        try:
            return ("ok", service.save_draft(case["id"], "FULL_CREDIT", draft_request(template, blocks=blocks, expected_version=1), actor="analyst"))
        except Exception as exc:  # noqa: BLE001 — the loser's typed conflict
            return ("conflict", exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(racing_save, ["Racer one narrative.", "Racer two narrative."]))
    assert sorted(kind for kind, _ in outcomes) == ["conflict", "ok"], "exactly one CAS winner"
    conflict = next(value for kind, value in outcomes if kind == "conflict")
    assert "VERSION_CONFLICT" in str(conflict)
    assert conflict.current["version"] == 2, "typed conflict carries the current head for rebase"
    saved_events = [e for e in service.audit_events_for_tests(case["id"]) if e["action"] == "deliverable.draft.saved"]
    assert len(saved_events) == 2, "one audit entry per appended revision, none for the loser"


def test_restore_appends_new_revision_and_history_stays_byte_identical(service, store):
    case, source, template, r1 = save_min_draft(service, store)
    service.save_draft(
        case["id"], "FULL_CREDIT",
        draft_request(template, blocks=required_blocks(template, source, narrative_text="Revised view."), expected_version=1),
        actor="analyst",
    )
    before = copy.deepcopy(service.revision_history(case["id"], "FULL_CREDIT"))
    r3 = service.save_draft(case["id"], "FULL_CREDIT", draft_request(template, blocks=r1["content"]["blocks"], expected_version=2), actor="analyst")
    assert r3["version"] == 3
    assert r3["content"]["blocks"] == r1["content"]["blocks"], "restore carries the old content verbatim"
    after = service.revision_history(case["id"], "FULL_CREDIT")
    assert [r["version"] for r in after] == [1, 2, 3], "versions strictly increase; no rewrites"
    assert after[:2] == before, "prior revisions remain byte-identical"


def test_stored_revisions_are_isolated_from_later_caller_mutation(service, store):
    case, source, template, r1 = save_min_draft(service, store)
    original_digest = r1["digest"]
    r1["content"]["blocks"][0]["text"] = "TAMPERED AFTER APPEND"
    fetched = service.revision_by_id(case["id"], r1["revision_id"])
    assert fetched["content"]["blocks"][0]["text"] != "TAMPERED AFTER APPEND", "store serializes/copies on write"
    assert fetched["digest"] == original_digest


def test_http_stale_draft_put_returns_409_with_current_revision_and_by_id_read_round_trips(client, settings, store):
    svc, case, source, template = http_seed(settings, store)
    url = f"/api/cases/{case['id']}/deliverables/FULL_CREDIT/draft"
    body = draft_request(template, source).model_dump(mode="json")
    first = client.put(url, json=body, headers=ANALYST_H)
    assert first.status_code in (200, 201)
    saved = first.json()
    stale = client.put(url, json=body, headers=ANALYST_H)  # expected_version still 0
    assert stale.status_code == 409
    detail = stale.json()["detail"]
    assert detail["code"], "409 shape carries a typed code"
    assert detail["current"]["version"] == 1, "conflict embeds the full current revision for rebase"
    assert detail["current"]["revision_id"] == saved["revision_id"]
    by_id = client.get(f"/api/cases/{case['id']}/deliverables/revisions/{saved['revision_id']}", headers=ANALYST_H)
    assert by_id.status_code == 200
    assert by_id.json()["content"] == saved["content"], "any revision stays fetchable by stable id"


# --- strict schema and template policy --------------------------------------------


def test_strict_schema_rejects_client_supplied_generated_values(client, settings, store):
    svc, case, source, template = http_seed(settings, store)
    body = draft_request(template, source).model_dump(mode="json")
    forged = optional_block(template, "GENERATED_METRIC")
    forged["values"] = {"total_leverage": 1.0}  # client-computed values are server-authoritative
    body["blocks"].append(forged)
    resp = client.put(f"/api/cases/{case['id']}/deliverables/FULL_CREDIT/draft", json=body, headers=ANALYST_H)
    assert resp.status_code == 422, "extra=forbid rejects client-generated values before any node runs"
    assert svc.workspace(case["id"], "FULL_CREDIT")["draft"] is None


@pytest.mark.parametrize("violation", ["heading_in_optional_slot", "narrative_in_optional_slot", "invented_slot_id"])
def test_client_invented_optional_kind_or_slot_is_rejected(service, store, violation):
    case, source, _ = seed_ready_case(service, store)
    template = service.templates()["FULL_CREDIT"]
    if violation == "heading_in_optional_slot":
        rogue = {"block_id": "blk-rogue", "slot_id": optional_slot(template, "LIMITATIONS"), "kind": "HEADING", "text": "Sneaky heading"}
    elif violation == "narrative_in_optional_slot":
        rogue = {"block_id": "blk-rogue", "slot_id": optional_slot(template, "LIMITATIONS"), "kind": "NARRATIVE",
                 "text": "Sneaky narrative", "content_mode": "ANALYST_JUDGMENT", "citations": []}
    else:
        rogue = optional_block(template, "LIMITATIONS", slot_id="appendix-invented-1")
    with pytest.raises(Exception, match="DELIVERABLE_SLOT_INVALID"):
        service.save_draft(case["id"], "FULL_CREDIT", draft_request(template, source, extra_blocks=[rogue]), actor="analyst")
    assert service.workspace(case["id"], "FULL_CREDIT")["draft"] is None, "no state change on rejection"


def test_optional_blocks_out_of_template_declared_order_are_rejected(service, store):
    case, source, _ = seed_ready_case(service, store)
    template = service.templates()["FULL_CREDIT"]
    model = seed_model(service, case)
    declared = [p["kind"] for p in template["optional_blocks"]]
    assert declared.index("GENERATED_METRIC") < declared.index("GENERATED_TABLE"), "premise: metric declared before table"
    out_of_order = [optional_block(template, "GENERATED_TABLE"), optional_block(template, "GENERATED_METRIC")]
    with pytest.raises(Exception, match="DELIVERABLE_TEMPLATE_ORDER_INVALID"):
        service.save_draft(
            case["id"], "FULL_CREDIT",
            draft_request(template, source, model_selection=revision_selection(model), extra_blocks=out_of_order),
            actor="analyst",
        )


def test_declared_limitations_slot_saves_without_model_identity(service, store):
    case, source, _ = seed_ready_case(service, store)
    template = service.templates()["FULL_CREDIT"]
    revision = service.save_draft(
        case["id"], "FULL_CREDIT",
        draft_request(template, source, extra_blocks=[optional_block(template, "LIMITATIONS")]),
        actor="analyst",
    )
    assert revision["content"]["model_identity"] is None, "non-model slots need no model"
    assert revision["content"]["blocks"][-1]["kind"] == "LIMITATIONS"


# --- evidence citations -----------------------------------------------------------


def test_citations_resolve_same_case_existing_non_withdrawn_blocks(service, store):
    case, source, _ = seed_ready_case(service, store)
    other_case, other_source = seed_case_with_source(store, body=b"foreign case evidence")
    template = service.templates()["FULL_CREDIT"]

    def with_citation(source_id, block_id):
        blocks = required_blocks(template, source)
        register = next(b for b in blocks if b["kind"] == "EVIDENCE_REGISTER")
        register["citations"] = [{"source_id": source_id, "block_ids": [block_id], "claim": "cited claim"}]
        return draft_request(template, blocks=blocks)

    with pytest.raises(Exception, match="EVIDENCE_CASE_MISMATCH"):
        service.save_draft(case["id"], "FULL_CREDIT", with_citation(other_source["id"], "b00001"), actor="analyst")
    with pytest.raises(Exception, match="EVIDENCE_BLOCK_MISMATCH"):
        service.save_draft(case["id"], "FULL_CREDIT", with_citation(source["id"], "b99999"), actor="analyst")
    store.withdraw(case["id"], source["id"], "analyst")
    with pytest.raises(Exception, match="EVIDENCE_SOURCE_WITHDRAWN"):
        service.save_draft(case["id"], "FULL_CREDIT", with_citation(source["id"], "b00001"), actor="analyst")
    assert service.workspace(case["id"], "FULL_CREDIT")["draft"] is None, "every failed save aborts with nothing appended"


# --- model selection and generated blocks -----------------------------------------


def test_model_selection_pins_current_revision_and_fallback_requires_acknowledged_no_revision_state(service, store):
    case, source, _ = seed_ready_case(service, store)
    template = service.templates()["FULL_CREDIT"]
    first = seed_model(service, case)
    second = service.seed_signed_revision_for_tests(case["id"], outputs={"total_leverage": 3.9})  # head advances
    metric = [optional_block(template, "GENERATED_METRIC")]
    with pytest.raises(Exception, match="MODEL_REVISION_STALE"):
        service.save_draft(case["id"], "FULL_CREDIT", draft_request(template, source, model_selection=revision_selection(first), extra_blocks=metric), actor="analyst")
    fallback = {"kind": "APPLICATION_BUILD", "build_id": second["build_id"], "fallback_acknowledged": True}
    with pytest.raises(Exception, match="FALLBACK|REVISION"):
        service.save_draft(case["id"], "FULL_CREDIT", draft_request(template, source, model_selection=fallback, extra_blocks=metric), actor="analyst")

    # eligible fallback: a case whose build has no signed revision, explicitly acknowledged
    bare_case, bare_source, _ = seed_ready_case(service, store)
    build = service.seed_application_build_for_tests(bare_case["id"], outputs={"total_leverage": 4.2})
    eligible = {"kind": "APPLICATION_BUILD", "build_id": build["build_id"], "fallback_acknowledged": True}
    revision = service.save_draft(bare_case["id"], "FULL_CREDIT", draft_request(template, bare_source, model_selection=eligible, extra_blocks=metric), actor="analyst")
    identity = revision["content"]["model_identity"]
    assert identity["kind"] == "APPLICATION_BUILD"
    assert identity["build_id"] == build["build_id"]
    assert {"name", "version", "sha256"} <= set(identity["calculation_runtime"]), "fallback pins the full build identity incl. calculation runtime"


def test_selection_must_resolve_to_exact_stored_revision_and_build_records(service, store):
    case, source, _ = seed_ready_case(service, store)
    template = service.templates()["FULL_CREDIT"]
    model = seed_model(service, case)
    metric = [optional_block(template, "GENERATED_METRIC")]
    ghost_revision = {"kind": "ANALYST_REVISION", "build_id": model["build_id"], "revision_id": "rev-missing"}
    with pytest.raises(Exception, match="MODEL_REVISION_STALE"):
        service.save_draft(case["id"], "FULL_CREDIT", draft_request(template, source, model_selection=ghost_revision, extra_blocks=metric), actor="analyst")

    bare_case, bare_source, _ = seed_ready_case(service, store)
    ghost_build = {"kind": "APPLICATION_BUILD", "build_id": "build-missing", "fallback_acknowledged": True}
    with pytest.raises(Exception, match="MODEL_BUILD_STALE"):
        service.save_draft(bare_case["id"], "FULL_CREDIT", draft_request(template, bare_source, model_selection=ghost_build, extra_blocks=metric), actor="analyst")


@pytest.mark.parametrize("kind", ["GENERATED_METRIC", "GENERATED_TABLE", "GENERATED_CHART", "MODEL_APPENDIX"])
def test_model_dependent_block_kinds_require_selection_and_are_digest_pinned(service, store, kind):
    from caos.contracts import digest

    case, source, _ = seed_ready_case(service, store)
    template = service.templates()["FULL_CREDIT"]
    extra = [optional_block(template, kind)]
    with pytest.raises(Exception, match="MODEL_REQUIRED"):
        service.save_draft(case["id"], "FULL_CREDIT", draft_request(template, source, extra_blocks=extra), actor="analyst")
    model = seed_model(service, case)
    revision = service.save_draft(
        case["id"], "FULL_CREDIT",
        draft_request(template, source, model_selection=revision_selection(model), extra_blocks=extra),
        actor="analyst",
    )
    stored = revision["content"]["blocks"][-1]
    assert stored["kind"] == kind
    assert stored["model_digest"] == digest(revision["content"]["model_identity"]), "generated block pinned to the model identity"


def test_generated_metric_outputs_are_rebuilt_server_side_from_pinned_revision(service, store):
    case, source, _ = seed_ready_case(service, store)
    template = service.templates()["FULL_CREDIT"]
    model = seed_model(service, case, outputs={"total_leverage": 4.2})
    revision = service.save_draft(
        case["id"], "FULL_CREDIT",
        draft_request(template, source, model_selection=revision_selection(model), extra_blocks=[optional_block(template, "GENERATED_METRIC")]),
        actor="analyst",
    )
    stored = revision["content"]["blocks"][-1]
    assert stored["values"]["total_leverage"] == 4.2, "server recomputes from the exact pinned revision"


def test_forged_scenario_outputs_raise_calculation_mismatch(service, store):
    from caos.contracts import digest

    case, source, _ = seed_ready_case(service, store)
    template = service.templates()["FULL_CREDIT"]
    model = seed_model(service, case)
    selection = revision_selection(model)
    preview = service.preview_scenario_for_tests(case["id"], build_id=model["build_id"], base_revision_id=model["revision_id"], shocks=[SHOCK])

    # the honest preview saves and pins model identity
    revision = service.save_draft(
        case["id"], "FULL_CREDIT",
        draft_request(template, source, model_selection=selection, extra_blocks=[scenario_exhibit_block(template, preview)]),
        actor="analyst",
    )
    stored = revision["content"]["blocks"][-1]
    assert stored["model_digest"] == digest(revision["content"]["model_identity"])
    assert stored["scenario"]["build_id"] == model["build_id"]

    # forged outputs with self-consistent digests must still fail the server recompute
    forged = copy.deepcopy(preview)
    forged["scenario"]["outputs"]["total_leverage"] = 99.9
    forged["scenario"]["outputs_digest"] = digest(forged["scenario"]["outputs"])
    forged["scenario_digest"] = digest(forged["scenario"])
    with pytest.raises(Exception, match="SCENARIO_EXHIBIT_CALCULATION_MISMATCH"):
        service.save_draft(
            case["id"], "FULL_CREDIT",
            draft_request(template, source, expected_version=1, model_selection=selection, extra_blocks=[scenario_exhibit_block(template, forged)]),
            actor="analyst",
        )


def test_scenario_exhibit_requires_selected_model_before_any_calculation(service, store):
    case, source, _ = seed_ready_case(service, store)
    template = service.templates()["FULL_CREDIT"]
    model = seed_model(service, case)
    preview = service.preview_scenario_for_tests(case["id"], build_id=model["build_id"], base_revision_id=model["revision_id"], shocks=[SHOCK])
    with pytest.raises(Exception, match="MODEL_REQUIRED"):
        service.save_draft(
            case["id"], "FULL_CREDIT",
            draft_request(template, source, extra_blocks=[scenario_exhibit_block(template, preview)]),  # no model_selection
            actor="analyst",
        )


def test_scenario_base_identity_mismatch_fails_before_calculation_with_zero_residue(service, store):
    from caos.contracts import digest

    case, source, _ = seed_ready_case(service, store)
    template = service.templates()["FULL_CREDIT"]
    model = seed_model(service, case)
    preview = service.preview_scenario_for_tests(case["id"], build_id=model["build_id"], base_revision_id=model["revision_id"], shocks=[SHOCK])
    mismatched = copy.deepcopy(preview)
    mismatched["scenario"]["base_revision_id"] = "rev-someone-elses"  # binds to a different model than the selection
    mismatched["scenario_digest"] = digest(mismatched["scenario"])
    service.forbid_scenario_calculation_for_tests()  # any calculator invocation now raises AssertionError
    with pytest.raises(Exception, match="IDENTITY"):
        service.save_draft(
            case["id"], "FULL_CREDIT",
            draft_request(template, source, model_selection=revision_selection(model), extra_blocks=[scenario_exhibit_block(template, mismatched)]),
            actor="analyst",
        )
    assert service.workspace(case["id"], "FULL_CREDIT")["draft"] is None, "no revision persisted"
    saved = [e for e in service.audit_events_for_tests(case["id"]) if e["action"] == "deliverable.draft.saved"]
    assert saved == [], "no audit residue on the failed save"


def test_application_build_fallback_scenario_accepts_null_base_revision(service, store):
    case, source, _ = seed_ready_case(service, store)
    template = service.templates()["FULL_CREDIT"]
    build = service.seed_application_build_for_tests(case["id"], outputs={"total_leverage": 4.2})
    preview = service.preview_scenario_for_tests(case["id"], build_id=build["build_id"], base_revision_id=None, shocks=[SHOCK])
    assert preview["scenario"]["base_revision_id"] is None
    fallback = {"kind": "APPLICATION_BUILD", "build_id": build["build_id"], "fallback_acknowledged": True}
    revision = service.save_draft(
        case["id"], "FULL_CREDIT",
        draft_request(template, source, model_selection=fallback, extra_blocks=[scenario_exhibit_block(template, preview)]),
        actor="analyst",
    )
    assert revision["content"]["model_identity"]["kind"] == "APPLICATION_BUILD"
    assert revision["content"]["blocks"][-1]["scenario"]["base_revision_id"] is None


def test_ungoverned_metric_ids_and_chart_recipe_fields_are_rejected(service, store):
    case, source, _ = seed_ready_case(service, store)
    template = service.templates()["FULL_CREDIT"]
    model = seed_model(service, case)
    selection = revision_selection(model)
    rogue_metric = [optional_block(template, "GENERATED_METRIC", metric_ids=["made_up_metric"])]
    with pytest.raises(Exception, match="GENERATED_FIELD_INVALID"):
        service.save_draft(case["id"], "FULL_CREDIT", draft_request(template, source, model_selection=selection, extra_blocks=rogue_metric), actor="analyst")
    rogue_chart = [optional_block(template, "GENERATED_CHART", recipe={"chart_kind": "line", "fields": ["not_a_governed_field"]})]
    with pytest.raises(Exception, match="GENERATED_FIELD_INVALID|RECIPE"):
        service.save_draft(case["id"], "FULL_CREDIT", draft_request(template, source, model_selection=selection, extra_blocks=rogue_chart), actor="analyst")


def test_scenario_digest_must_equal_server_computed_digest(service, store):
    case, source, _ = seed_ready_case(service, store)
    template = service.templates()["FULL_CREDIT"]
    model = seed_model(service, case)
    preview = service.preview_scenario_for_tests(case["id"], build_id=model["build_id"], base_revision_id=model["revision_id"], shocks=[SHOCK])
    with pytest.raises(Exception, match="SCENARIO_EXHIBIT_DIGEST_INVALID"):
        service.save_draft(
            case["id"], "FULL_CREDIT",
            draft_request(template, source, model_selection=revision_selection(model),
                          extra_blocks=[scenario_exhibit_block(template, preview, scenario_digest="0" * 64)]),
            actor="analyst",
        )


# --- reader authorization ---------------------------------------------------------


def test_case_reader_reads_workspace_but_cannot_write_draft(client, settings, store):
    svc, case, source, template = http_seed(settings, store)
    store.add_member(case["id"], "analyst", "reader-user", "READER", actor_role="ADMIN")
    reader = {"x-caos-role": "ANALYST", "x-forwarded-user": "reader-user"}
    url = f"/api/cases/{case['id']}/deliverables/FULL_CREDIT/draft"
    assert client.get(url, headers=reader).status_code == 200, "reader may read the workspace"
    write = client.put(url, json=draft_request(template, source).model_dump(mode="json"), headers=reader)
    assert write.status_code == 403, "reader never writes drafts"
    assert svc.workspace(case["id"], "FULL_CREDIT")["draft"] is None


# --- freeze and rendered exports --------------------------------------------------


@pytest.mark.parametrize("pathway", SIX_PATHWAYS)
def test_each_pathway_frozen_payload_renders_substantive_md_pdf_xlsx(service, store, pathway):
    case, source, revision, frozen = freeze_min(service, store, pathway)

    md, md_sha = service.export(frozen["deliverable_id"], "md")
    assert hashlib.sha256(md).hexdigest() == md_sha
    text = md.decode("utf-8")
    assert "Credit Opinion" in text and "Leverage is manageable." in text

    pdf, _ = service.export(frozen["deliverable_id"], "pdf")
    assert pdf[:5] == b"%PDF-", "structurally a PDF"
    assert "Credit Opinion" in service.export_text_for_tests(frozen["deliverable_id"], "pdf")

    xlsx, _ = service.export(frozen["deliverable_id"], "xlsx")
    from openpyxl import load_workbook

    book = load_workbook(io.BytesIO(xlsx))
    assert {"Cover", "Reviewed Deliverable", "Evidence Register", "Revision Record"} <= set(book.sheetnames)


def test_freeze_embeds_selected_revision_outputs_assumptions_and_build_payload_verbatim(service, store):
    case, source, _ = seed_ready_case(service, store)
    template = service.templates()["FULL_CREDIT"]
    model = seed_model(service, case, outputs={"total_leverage": 4.2})
    revision = service.save_draft(
        case["id"], "FULL_CREDIT",
        draft_request(template, source, model_selection=revision_selection(model), extra_blocks=[optional_block(template, "GENERATED_METRIC")]),
        actor="analyst",
    )
    frozen = service.freeze(case["id"], freeze_request(revision), actor="analyst")
    pinned = frozen["payload"]["model"]
    assert pinned["outputs"] == model["outputs"], "signed revision outputs embedded verbatim"
    assert pinned["assumptions"] == model["assumptions"], "effective assumptions embedded verbatim"
    assert pinned["build"]["payload"] == model["build_payload"], "application-build payload embedded verbatim"
    assert pinned["build"]["qa"] == model["build_qa"], "build QA embedded verbatim"
    assert "4.2" in service.export_text_for_tests(frozen["deliverable_id"], "md"), "exports show the exact pinned figures"


def test_freeze_is_idempotent_under_race_with_one_record_one_thread_one_audit_event(service, store):
    case, source, template, revision = save_min_draft(service, store)
    with ThreadPoolExecutor(max_workers=2) as pool:
        raced = list(pool.map(lambda _: service.freeze(case["id"], freeze_request(revision), actor="analyst"), range(2)))
    retried = service.freeze(case["id"], freeze_request(revision), actor="analyst")
    everyone = raced + [retried]
    assert len({r["deliverable_id"] for r in everyone}) == 1, "one content-addressed frozen record"
    assert len({r["thread_id"] for r in everyone}) == 1, "racing freezes converge on one thread (§10.7)"
    frozen_events = [e for e in service.audit_events_for_tests(case["id"]) if e["action"] == "deliverable.frozen"]
    assert len(frozen_events) == 1, "single audit event under race and retry"


def test_divergent_render_for_same_freeze_identity_is_freeze_conflict(tmp_path, store):
    vault = tmp_path / "shared-vault"
    service = make_service(store, vault)
    case, source, template, revision = save_min_draft(service, store)
    service.freeze(case["id"], freeze_request(revision), actor="analyst")
    divergent = make_service(store, vault, renderer_for_tests=lambda payload, fmt: b"DIFFERENT RENDER BYTES")
    with pytest.raises(Exception, match="DELIVERABLE_FREEZE_CONFLICT"):
        divergent.freeze(case["id"], freeze_request(revision), actor="analyst")


def test_filing_thread_id_is_a_deterministic_digest_including_build_id():
    from caos.deliverables.graph import filing_thread_id

    args = dict(case_id="case-1", pathway="FULL_CREDIT", draft_version=3, draft_digest="a" * 64, build_id="build-1")
    assert filing_thread_id(**args) == filing_thread_id(**args), "deterministic"
    baseline = filing_thread_id(**args)
    assert filing_thread_id(**{**args, "build_id": "build-2"}) != baseline, "thread identity includes build_id (§12.23)"
    assert filing_thread_id(**{**args, "draft_version": 4}) != baseline
    assert filing_thread_id(**{**args, "draft_digest": "b" * 64}) != baseline
    assert filing_thread_id(**{**args, "case_id": "case-2"}) != baseline


def test_freeze_fails_closed_without_upstream_accepted_authority(service, store):
    case, source = seed_case_with_source(store)  # deliberately: no accepted authority seeded
    template = service.templates()["FULL_CREDIT"]
    revision = service.save_draft(case["id"], "FULL_CREDIT", draft_request(template, source), actor="analyst")
    with pytest.raises(Exception, match="AUTHORITY|SNAPSHOT|UPSTREAM"):
        service.freeze(case["id"], freeze_request(revision), actor="analyst")
    assert service.workspace(case["id"], "FULL_CREDIT")["frozen"] == [], "no frozen record without pinned upstream identity"


# --- the filing gate --------------------------------------------------------------


def test_concurrent_filers_yield_exactly_one_filed_with_payload_equal_to_frozen(service, store):
    case, revision, frozen = frozen_deliverable(service, store)

    def approve(_):
        try:
            return ("filed", service.approve_filing(case["id"], frozen["deliverable_id"], file_request(frozen), actor="approver-user"))
        except Exception as exc:  # noqa: BLE001 — the losing racer's typed refusal
            return ("refused", exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(approve, range(2)))
    assert sorted(kind for kind, _ in outcomes) == ["filed", "refused"], "resume ticket: exactly one filer wins (§12.21)"
    filed = next(value for kind, value in outcomes if kind == "filed")
    assert filed["status"] == "FILED"
    assert filed["payload"] == frozen["payload"], "filed payload is the frozen payload, bit-identical"
    filed_events = [e for e in service.audit_events_for_tests(case["id"]) if e["action"] == "deliverable.filed"]
    assert len(filed_events) == 1


def test_approval_binds_exact_preview_digest_and_fingerprint_mismatch_leaves_frozen_retryable(service, store):
    case, revision, frozen = frozen_deliverable(service, store)
    with pytest.raises(Exception, match="STALE_PREVIEW|PREVIEW"):
        service.approve_filing(case["id"], frozen["deliverable_id"], file_request(frozen, preview_digest="0" * 64), actor="approver-user")
    with pytest.raises(Exception, match="STALE_PREVIEW|FINGERPRINT"):
        service.approve_filing(case["id"], frozen["deliverable_id"], file_request(frozen, input_fingerprint="1" * 64), actor="approver-user")
    record = service.frozen_record(case["id"], frozen["deliverable_id"])
    assert record["status"] == "FROZEN", "mismatch keeps the gate parked with the record intact"
    filed = service.approve_filing(case["id"], frozen["deliverable_id"], file_request(frozen), actor="approver-user")
    assert filed["status"] == "FILED", "the record stayed retryable: an exact approval still lands"


def test_approval_leaves_frozen_content_bit_identical_and_appends_one_audit_event(service, store):
    case, revision, frozen = frozen_deliverable(service, store)
    before = copy.deepcopy(service.frozen_record(case["id"], frozen["deliverable_id"]))
    assert before["status"] == "FROZEN"
    service.approve_filing(case["id"], frozen["deliverable_id"], file_request(frozen), actor="approver-user")
    after = service.frozen_record(case["id"], frozen["deliverable_id"])
    assert after["payload"] == before["payload"], "approval never edits the reviewed content"
    assert after["preview_digest"] == before["preview_digest"]
    assert after["input_fingerprint"] == before["input_fingerprint"]
    assert after["build_id"] == before["build_id"]
    assert after["status"] == "FILED"
    assert after["filed_by"] == "approver-user" and after["filed_at"]
    changed = {key for key in after if after.get(key) != before.get(key)}
    assert changed <= {"status", "filed_by", "filed_at"}, "only phase and approval fields may change"
    filed_events = [e for e in service.audit_events_for_tests(case["id"]) if e["action"] == "deliverable.filed"]
    assert len(filed_events) == 1


def test_gate_approval_hash_is_canonical_sha256_form(service, store):
    from caos.deliverables.graph import APPROVAL_HASH_PATTERN, canonical_approval_hash

    assert APPROVAL_HASH_PATTERN == r"^sha256:[0-9a-f]{64}$"
    case, revision, frozen = frozen_deliverable(service, store)
    canonical = canonical_approval_hash(frozen)
    assert re.fullmatch(APPROVAL_HASH_PATTERN, canonical)
    assert canonical == f"sha256:{frozen['preview_digest']}", "gate hash binds the exact frozen preview digest"
    for alias in (canonical.upper(), canonical[:-1], "md5:" + "a" * 32, frozen["preview_digest"]):
        with pytest.raises(Exception):
            service.resume_filing_with_hash_for_tests(frozen["thread_id"], alias)
    filed = service.resume_filing_with_hash_for_tests(frozen["thread_id"], canonical)
    assert filed["status"] == "FILED", "only the canonical form resumes the gate"


def test_http_approval_payload_rejects_caller_owned_authority_fields(client, settings, store):
    svc, case, source, template = http_seed(settings, store)
    revision = svc.save_draft(case["id"], "FULL_CREDIT", draft_request(template, source), actor="analyst")
    frozen = svc.freeze(case["id"], freeze_request(revision), actor="analyst")
    store.add_member(case["id"], "analyst", "approver-user", "APPROVER", actor_role="ADMIN")
    url = f"/api/cases/{case['id']}/deliverables/by-id/{frozen['deliverable_id']}/approve"
    base = {"preview_digest": frozen["preview_digest"], "input_fingerprint": frozen["input_fingerprint"]}
    forgeries = (
        ("approved_by", "attacker"),
        ("approved_at", "2026-01-01T00:00:00Z"),
        ("authority_hash", "sha256:" + "a" * 64),
        ("plan_hash", "sha256:" + "b" * 64),
        ("budgets", {"turns": 10_000}),
        ("model", "claude-someone-elses"),
        ("scope", ["*"]),
    )
    for field, value in forgeries:
        resp = client.post(url, json={**base, field: value}, headers=APPROVER_H)
        assert resp.status_code == 422, f"extra=forbid must reject caller-owned field {field!r}"
    assert svc.frozen_record(case["id"], frozen["deliverable_id"])["status"] == "FROZEN", "no forged request may file"


def test_gate_rejects_source_set_drift_between_freeze_and_filing(service, store):
    case, revision, frozen = frozen_deliverable(service, store)
    ingest_second_source(store, case["id"])  # evidence base moves while the gate is parked
    with pytest.raises(Exception, match="SOURCE_SET_CHANGED|FROZEN_AUTHORITY_STALE"):
        service.approve_filing(case["id"], frozen["deliverable_id"], file_request(frozen), actor="approver-user")
    assert service.frozen_record(case["id"], frozen["deliverable_id"])["status"] == "FROZEN"
    assert not [e for e in service.audit_events_for_tests(case["id"]) if e["action"] == "deliverable.filed"]


def test_gate_recomputes_stored_digest_and_refuses_tampered_frozen_content(service, store):
    case, revision, frozen = frozen_deliverable(service, store)
    service.tamper_frozen_payload_for_tests(frozen["deliverable_id"])
    with pytest.raises(Exception, match="PREVIEW|INTEGRITY"):
        service.approve_filing(case["id"], frozen["deliverable_id"], file_request(frozen), actor="approver-user")
    assert not [e for e in service.audit_events_for_tests(case["id"]) if e["action"] == "deliverable.filed"], "tamper-evident: nothing filed"


def test_resume_outside_a_parked_filing_gate_is_refused(service, store):
    case, revision, frozen = frozen_deliverable(service, store)
    service.terminate_filing_thread_for_tests(frozen["thread_id"])  # thread no longer paused at the gate
    with pytest.raises(Exception, match="RESUME_NOT_APPLIED|NOT_PAUSED"):
        service.approve_filing(case["id"], frozen["deliverable_id"], file_request(frozen), actor="approver-user")
    assert not [e for e in service.audit_events_for_tests(case["id"]) if e["action"] == "deliverable.filed"]


def test_approval_revalidates_current_accepted_snapshot_and_stale_leaves_no_residue(service, store):
    case, revision, frozen = frozen_deliverable(service, store)
    service.supersede_accepted_authority_for_tests(case["id"])  # newer accepted snapshot after freeze
    with pytest.raises(Exception, match="FROZEN_AUTHORITY_STALE"):
        service.approve_filing(case["id"], frozen["deliverable_id"], file_request(frozen), actor="approver-user")
    record = service.frozen_record(case["id"], frozen["deliverable_id"])
    assert record["status"] == "FROZEN", "stale rejection leaves the record intact and retryable (after re-freeze)"
    assert not [e for e in service.audit_events_for_tests(case["id"]) if e["action"] == "deliverable.filed"], "no audit residue"


def test_stale_or_duplicate_resume_returns_resume_not_applied_never_success(client, settings, store):
    svc, case, source, template = http_seed(settings, store)
    revision = svc.save_draft(case["id"], "FULL_CREDIT", draft_request(template, source), actor="analyst")
    frozen = svc.freeze(case["id"], freeze_request(revision), actor="analyst")
    store.add_member(case["id"], "analyst", "approver-user", "APPROVER", actor_role="ADMIN")
    url = f"/api/cases/{case['id']}/deliverables/by-id/{frozen['deliverable_id']}/approve"
    body = {"preview_digest": frozen["preview_digest"], "input_fingerprint": frozen["input_fingerprint"]}
    first = client.post(url, json=body, headers=APPROVER_H)
    assert first.status_code == 200 and first.json()["status"] == "FILED"
    second = client.post(url, json=body, headers=APPROVER_H)
    assert second.status_code == 409, "a resume that advances nothing must never surface as success (§12.22)"
    detail = second.json()["detail"]
    assert detail["code"] == "RESUME_NOT_APPLIED"
    assert "current_interrupt_id" in detail
    assert svc.frozen_record(case["id"], frozen["deliverable_id"])["status"] == "FILED", "still exactly one filing"


def test_later_filing_supersedes_prior_with_pointer_and_terminalizes_its_thread(service, store):
    case, source, r1, frozen_a = freeze_min(service, store)  # frozen A parks its gate, never filed
    add_approver(store, case)
    template = service.templates()["FULL_CREDIT"]

    r2 = service.save_draft(
        case["id"], "FULL_CREDIT",
        draft_request(template, blocks=required_blocks(template, source, narrative_text="Updated opinion."), expected_version=r1["version"]),
        actor="analyst",
    )
    frozen_b = service.freeze(case["id"], freeze_request(r2), actor="analyst")
    service.approve_filing(case["id"], frozen_b["deliverable_id"], file_request(frozen_b), actor="approver-user")

    prior = service.frozen_record(case["id"], frozen_a["deliverable_id"])
    assert prior["status"] == "SUPERSEDED", "a parked frozen record is superseded by the later filing"
    assert prior["superseded_by_id"] == frozen_b["deliverable_id"], "supersession carries a pointer"
    thread = service.thread_state_for_tests(frozen_a["thread_id"])
    assert thread["outcome"] == "SUPERSEDED", "prior thread terminalized with the typed outcome — no zombie interrupts (§10.5)"

    r3 = service.save_draft(
        case["id"], "FULL_CREDIT",
        draft_request(template, blocks=required_blocks(template, source, narrative_text="Final opinion."), expected_version=r2["version"]),
        actor="analyst",
    )
    frozen_c = service.freeze(case["id"], freeze_request(r3), actor="analyst")
    service.approve_filing(case["id"], frozen_c["deliverable_id"], file_request(frozen_c), actor="approver-user")
    prior_filed = service.frozen_record(case["id"], frozen_b["deliverable_id"])
    assert prior_filed["status"] == "SUPERSEDED", "a FILED record is likewise superseded by the next filing"
    assert prior_filed["superseded_by_id"] == frozen_c["deliverable_id"]


def test_http_request_changes_requires_approver_and_nonblank_comment_and_appends_commented_draft(client, settings, store):
    svc, case, source, template = http_seed(settings, store)
    revision = svc.save_draft(case["id"], "FULL_CREDIT", draft_request(template, source), actor="analyst")
    frozen = svc.freeze(case["id"], freeze_request(revision), actor="analyst")
    store.add_member(case["id"], "analyst", "approver-user", "APPROVER", actor_role="ADMIN")
    url = f"/api/cases/{case['id']}/deliverables/by-id/{frozen['deliverable_id']}/request-changes"
    base = {"preview_digest": frozen["preview_digest"], "input_fingerprint": frozen["input_fingerprint"]}
    assert client.post(url, json={**base, "comment": "   "}, headers=APPROVER_H).status_code == 422, "blank comment refused"
    good = {**base, "comment": "Tighten the covenant discussion."}
    assert client.post(url, json=good, headers=ANALYST_H).status_code == 403, "request-changes is approver-only"
    resp = client.post(url, json=good, headers=APPROVER_H)
    assert resp.status_code == 200
    assert resp.json()["status"] == "CHANGES_REQUESTED"
    draft = svc.workspace(case["id"], "FULL_CREDIT")["draft"]
    assert draft["version"] == revision["version"] + 1, "a traceable replacement draft is appended"
    assert "Tighten the covenant discussion." in str(draft["content"]), "the replacement draft carries the comment"


def test_http_filing_gate_denies_outsiders_404_readers_403_analysts_403_for_every_global_role(client, settings, store):
    svc, case, source, template = http_seed(settings, store)
    revision = svc.save_draft(case["id"], "FULL_CREDIT", draft_request(template, source), actor="analyst")
    frozen = svc.freeze(case["id"], freeze_request(revision), actor="analyst")
    store.add_member(case["id"], "analyst", "stored-reader", "READER", actor_role="ADMIN")
    store.add_member(case["id"], "analyst", "stored-analyst", "ANALYST", actor_role="ADMIN")
    url = f"/api/cases/{case['id']}/deliverables/by-id/{frozen['deliverable_id']}/approve"
    body = {"preview_digest": frozen["preview_digest"], "input_fingerprint": frozen["input_fingerprint"]}
    for global_role in ("READER", "ANALYST", "APPROVER", "ADMIN"):
        outsider = client.post(url, json=body, headers={"x-caos-role": global_role, "x-forwarded-user": "outsider"})
        assert outsider.status_code == 404, f"non-member with global {global_role} must not learn the case exists"
        reader = client.post(url, json=body, headers={"x-caos-role": global_role, "x-forwarded-user": "stored-reader"})
        assert reader.status_code == 403, f"case READER never approves — global {global_role} does not escalate"
    analyst_member = client.post(url, json=body, headers={"x-caos-role": "APPROVER", "x-forwarded-user": "stored-analyst"})
    assert analyst_member.status_code == 403, "filing is approver-gated: case ANALYST standing is insufficient (DECISIONS §2)"
    assert svc.frozen_record(case["id"], frozen["deliverable_id"])["status"] == "FROZEN"


def test_case_approver_standing_suffices_across_all_global_writer_roles(client, settings, store):
    """Positive half of the gate authz matrix, adapted to the approver-gated filing
    interrupt: every approver-capable stored case role (APPROVER, ADMIN) crossed with
    every global writer role can approve — case standing governs, global role is inert."""
    for case_role in ("APPROVER", "ADMIN"):
        for global_role in ("ANALYST", "APPROVER", "ADMIN"):
            svc, case, source, template = http_seed(settings, store)
            revision = svc.save_draft(case["id"], "FULL_CREDIT", draft_request(template, source), actor="analyst")
            frozen = svc.freeze(case["id"], freeze_request(revision), actor="analyst")
            subject = f"{case_role.lower()}-{global_role.lower()}"
            store.add_member(case["id"], "analyst", subject, case_role, actor_role="ADMIN")
            url = f"/api/cases/{case['id']}/deliverables/by-id/{frozen['deliverable_id']}/approve"
            body = {"preview_digest": frozen["preview_digest"], "input_fingerprint": frozen["input_fingerprint"]}
            resp = client.post(url, json=body, headers={"x-caos-role": global_role, "x-forwarded-user": subject})
            assert resp.status_code == 200, f"case {case_role} + global {global_role} must be able to approve"
            assert resp.json()["status"] == "FILED"


# --- filed exports ----------------------------------------------------------------


def test_filed_exports_are_byte_exact_sha_verified_and_never_rerendered(client, settings, store):
    svc, case, source, template = http_seed(settings, store)
    revision = svc.save_draft(case["id"], "FULL_CREDIT", draft_request(template, source), actor="analyst")
    frozen = svc.freeze(case["id"], freeze_request(revision), actor="analyst")
    store.add_member(case["id"], "analyst", "approver-user", "APPROVER", actor_role="ADMIN")
    export_url = f"/api/cases/{case['id']}/deliverables/by-id/{frozen['deliverable_id']}/export/md"
    assert client.get(export_url, headers=ANALYST_H).status_code == 409, "pre-filing downloads are refused"

    approve_url = f"/api/cases/{case['id']}/deliverables/by-id/{frozen['deliverable_id']}/approve"
    body = {"preview_digest": frozen["preview_digest"], "input_fingerprint": frozen["input_fingerprint"]}
    assert client.post(approve_url, json=body, headers=APPROVER_H).status_code == 200

    resp = client.get(export_url, headers=ANALYST_H)
    assert resp.status_code == 200
    recorded = frozen["exports"]["md"]
    assert hashlib.sha256(resp.content).hexdigest() == recorded["sha256"], "served bytes match the frozen record"
    assert len(resp.content) == recorded["size"]

    # never re-rendered: a fresh instance whose renderer explodes still serves identical bytes
    exploding = make_service(store, settings.storage_dir, renderer_for_tests=_never_render)
    data, sha = exploding.export(frozen["deliverable_id"], "md")
    assert data == resp.content and sha == recorded["sha256"]


def test_tampered_or_missing_stored_export_fails_closed_with_no_audit_residue(service, store):
    case, revision, frozen = frozen_deliverable(service, store)
    service.approve_filing(case["id"], frozen["deliverable_id"], file_request(frozen), actor="approver-user")
    before = service.audit_events_for_tests(case["id"])
    service.tamper_export_for_tests(frozen["deliverable_id"], "md")
    with pytest.raises(Exception, match="EXPORT_INTEGRITY_FAILED"):
        service.export(frozen["deliverable_id"], "md")
    service.delete_export_for_tests(frozen["deliverable_id"], "pdf")
    with pytest.raises(Exception, match="EXPORT_UNAVAILABLE"):
        service.export(frozen["deliverable_id"], "pdf")
    assert service.audit_events_for_tests(case["id"]) == before, "failed downloads mutate nothing and leave no audit residue"


def test_xlsx_export_neutralizes_formula_text_and_preserves_typed_model_values(service, store):
    case, source, _ = seed_ready_case(service, store)
    template = service.templates()["FULL_CREDIT"]
    model = seed_model(service, case, outputs={"total_leverage": 4.2})
    blocks = required_blocks(template, source, narrative_text='=HYPERLINK("http://evil.example","click me") injected narrative')
    revision = service.save_draft(
        case["id"], "FULL_CREDIT",
        draft_request(template, blocks=blocks + [optional_block(template, "GENERATED_METRIC")], model_selection=revision_selection(model)),
        actor="analyst",
    )
    frozen = service.freeze(case["id"], freeze_request(revision), actor="analyst")
    data, _ = service.export(frozen["deliverable_id"], "xlsx")
    from openpyxl import load_workbook

    book = load_workbook(io.BytesIO(data))
    injected = None
    numeric = None
    for sheet in book.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                assert cell.data_type != "f", f"live formula in {sheet.title}!{cell.coordinate}"
                if isinstance(cell.value, str) and "HYPERLINK" in cell.value:
                    injected = cell
                if cell.value == 4.2:
                    numeric = cell
    assert injected is not None and injected.data_type == "s", "=-prefixed analyst text is an escaped literal string"
    assert numeric is not None and isinstance(numeric.value, float), "generated model numbers stay typed numbers"


# ROW MAPPING
# <legacy test> -> <spec test(s) in this file>
#
# test_deliverables.py:
#   test_six_pathway_templates_have_stable_identity_and_evidence_register -> test_template_registry_serves_six_pathways_with_stable_identity_and_evidence_register
#   test_deliverable_revisions_are_append_only_and_conflict_atomically -> test_stale_expected_version_is_atomic_cas_conflict_carrying_current_head
#   test_strict_draft_contract_rejects_client_generated_values -> test_strict_schema_rejects_client_supplied_generated_values
#   test_domain_validates_template_order_and_saves_complete_shared_draft -> test_saved_revision_digest_is_digest_of_content_and_order_violation_appends_nothing
#   test_restore_creates_a_new_revision_without_mutating_history -> test_restore_appends_new_revision_and_history_stays_byte_identical
#   test_evidence_citations_reject_cross_case_withdrawn_and_unknown_blocks -> test_citations_resolve_same_case_existing_non_withdrawn_blocks
#   test_active_revision_and_acknowledged_fallback_model_eligibility -> test_model_selection_pins_current_revision_and_fallback_requires_acknowledged_no_revision_state
#   test_selected_model_must_resolve_to_exact_pinned_record -> test_selection_must_resolve_to_exact_stored_revision_and_build_records
#   test_all_model_dependent_optional_blocks_require_and_pin_selected_model -> test_model_dependent_block_kinds_require_selection_and_are_digest_pinned (parametrized x4)
#   test_template_owns_exact_optional_slot_kind_and_order_policy -> test_template_owns_optional_block_kind_stem_cap_order_and_model_dependence
#   test_template_rejects_client_invented_optional_kind_or_slot -> test_client_invented_optional_kind_or_slot_is_rejected (parametrized x3)
#   test_template_rejects_invalid_optional_order -> test_optional_blocks_out_of_template_declared_order_are_rejected
#   test_template_accepts_declared_non_model_limitations_slot -> test_declared_limitations_slot_saves_without_model_identity
#   test_generated_metric_and_scenario_are_rebuilt_from_exact_current_model -> test_generated_metric_outputs_are_rebuilt_server_side_from_pinned_revision + test_forged_scenario_outputs_raise_calculation_mismatch (split: metric rebuild vs scenario forgery)
#   test_scenario_exhibit_requires_selected_model_before_calculation -> test_scenario_exhibit_requires_selected_model_before_any_calculation
#   test_scenario_base_binds_exactly_to_selected_model_without_persistence -> test_scenario_base_identity_mismatch_fails_before_calculation_with_zero_residue
#   test_application_build_scenario_accepts_null_base_revision -> test_application_build_fallback_scenario_accepts_null_base_revision
#   test_generated_blocks_reject_ungoverned_metric_and_recipe_fields -> test_ungoverned_metric_ids_and_chart_recipe_fields_are_rejected
#   test_scenario_exhibit_requires_exact_server_calculation_digest -> test_scenario_digest_must_equal_server_computed_digest
#   test_http_deliverable_current_history_by_id_and_recoverable_conflict -> test_http_stale_draft_put_returns_409_with_current_revision_and_by_id_read_round_trips
#   test_http_case_reader_can_read_but_cannot_write_deliverable -> test_case_reader_reads_workspace_but_cannot_write_draft
#
# test_deliverable_exports.py:
#   test_all_six_pathways_render_substantive_semantic_exports -> test_each_pathway_frozen_payload_renders_substantive_md_pdf_xlsx (parametrized x6)
#   test_freeze_pins_and_renders_exact_active_revision_model_authority -> test_freeze_embeds_selected_revision_outputs_assumptions_and_build_payload_verbatim
#   test_frozen_filed_history_and_request_changes_are_atomic -> test_concurrent_filers_yield_exactly_one_filed_with_payload_equal_to_frozen + test_later_filing_supersedes_prior_with_pointer_and_terminalizes_its_thread + test_http_request_changes_requires_approver_and_nonblank_comment_and_appends_commented_draft (split: race, supersession, change-request)
#   test_exact_draft_freeze_is_one_idempotent_record_under_race -> test_freeze_is_idempotent_under_race_with_one_record_one_thread_one_audit_event + test_divergent_render_for_same_freeze_identity_is_freeze_conflict (split: idempotency vs conflict)
#   test_http_freeze_file_and_download_exact_stored_bytes -> test_filed_exports_are_byte_exact_sha_verified_and_never_rerendered + test_tampered_or_missing_stored_export_fails_closed_with_no_audit_residue (approver gating of the filing itself is asserted in test_http_filing_gate_denies_outsiders_404_readers_403_analysts_403_for_every_global_role)
#   test_approval_revalidates_current_accepted_authority_without_residue -> test_approval_revalidates_current_accepted_snapshot_and_stale_leaves_no_residue
#   test_http_request_changes_requires_approver_comment_and_appends_draft -> test_http_request_changes_requires_approver_and_nonblank_comment_and_appends_commented_draft
#   test_xlsx_neutralizes_formula_text_and_preserves_typed_model_values -> test_xlsx_export_neutralizes_formula_text_and_preserves_typed_model_values
#
# test_ledger_contracts.py (deliverable rows):
#   test_deliverable_revision_lookup_preserves_immutable_history -> test_stored_revisions_are_isolated_from_later_caller_mutation
#   test_report_freeze_and_approval_require_exact_preview -> test_approval_binds_exact_preview_digest_and_fingerprint_mismatch_leaves_frozen_retryable (re-hosted from the cut report era onto the deliverable filing gate per DECISIONS §1/§10.10; bit-identical + audit halves also in test_approval_leaves_frozen_content_bit_identical_and_appends_one_audit_event)
#
# test_cp_dr_planning.py (eight approval-gate rows re-hosted onto the filing interrupt per DECISIONS §11.9):
#   test_research_brief_rejects_caller_owned_authority_fields -> test_http_approval_payload_rejects_caller_owned_authority_fields
#   test_plan_approval_request_requires_exact_canonical_hash -> test_gate_approval_hash_is_canonical_sha256_form
#   test_exact_plan_approval_preserves_identity_and_phase4_fails_closed -> test_approval_leaves_frozen_content_bit_identical_and_appends_one_audit_event
#   test_plan_approval_rejects_wrong_double_wrong_phase_and_changed_source_set -> test_approval_binds_exact_preview_digest_and_fingerprint_mismatch_leaves_frozen_retryable (wrong hash) + test_gate_rejects_source_set_drift_between_freeze_and_filing (changed source set) + test_resume_outside_a_parked_filing_gate_is_refused (wrong phase)
#   test_plan_approval_rejects_a_post_hash_plan_change_and_missing_pause -> test_gate_recomputes_stored_digest_and_refuses_tampered_frozen_content (post-hash change) + test_resume_outside_a_parked_filing_gate_is_refused (missing pause)
#   test_research_planning_requires_upstream_artifact_identity -> test_freeze_fails_closed_without_upstream_accepted_authority
#   test_research_plan_route_denies_cross_case_outsider_and_stored_reader -> test_http_filing_gate_denies_outsiders_404_readers_403_analysts_403_for_every_global_role
#   test_all_case_writer_role_combinations_can_approve_research_plan -> test_case_approver_standing_suffices_across_all_global_writer_roles
#       ADAPTATION: the filing gate is approver-gated (DECISIONS §2), so the approver-capable case-writer set is {APPROVER, ADMIN} x all global writer roles; the legacy matrix's case-ANALYST-can-approve third is deliberately inverted and asserted as 403 in the denial test above. Not inexpressible — re-scoped.
#
# DECISIONS-only guarantees carried by this file (no single legacy row):
#   §12.23 deliverable thread identity includes build_id; filing never re-renders -> test_filing_thread_id_is_a_deterministic_digest_including_build_id + test_filed_exports_are_byte_exact_sha_verified_and_never_rerendered
#   §12.21 resume ticket single-effect -> test_concurrent_filers_yield_exactly_one_filed_with_payload_equal_to_frozen
#   §12.22 RESUME_NOT_APPLIED on stale/duplicate resume -> test_stale_or_duplicate_resume_returns_resume_not_applied_never_success
#   §10.5 supersession terminalizes the parked thread (typed SUPERSEDED) -> test_later_filing_supersedes_prior_with_pointer_and_terminalizes_its_thread
#
# Inexpressible rows: none.
