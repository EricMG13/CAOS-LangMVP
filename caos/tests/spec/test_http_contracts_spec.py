"""HTTP response-contract specification (strict wire schemas; invariant: nothing
undeclared is ever served).

Sources: TEST_INVENTORY.md CONTRACTUAL rows for test_http_response_contracts.py
(15 rows, including the reclassified `test_loan_universe_findings_are_strict`).

Spec-first: every import of an unbuilt module (caos.api via the conftest client
fixture, caos.responses, caos.contracts) happens inside a fixture or test body,
so every test in this file FAILS today with ModuleNotFoundError. A passing test
is a defect in this suite until the port exists.
"""

from __future__ import annotations

import json

import pytest


# --- the pinned public key sets (the wire contract, family by family) --------------

FAMILIES = (
    "case",
    "source",
    "source_set",
    "run",
    "snapshot",
    "artifact",
    "model_readiness",
    "model_build",
    "audit",
)

MODEL_NAMES = {
    "case": "CaseResponse",
    "source": "SourceResponse",
    "source_set": "SourceSetResponse",
    "run": "RunResponse",
    "snapshot": "SnapshotResponse",
    "artifact": "ArtifactResponse",
    "model_readiness": "ModelReadinessResponse",
    "model_build": "ModelBuildResponse",
    "audit": "AuditEventResponse",
}

_SOURCE_SET_KEYS = {
    "id": None,
    "case_id": None,
    "version": None,
    "source_ids": None,
    "created_by": None,
    "created_at": None,
}

KEY_SETS = {
    "case": {
        "id": None,
        "name": None,
        "issuer": None,
        "sector": None,
        "created_by": None,
        "created_at": None,
        "members": None,
        "accepted_snapshot_id": None,
        "visible_snapshot_id": None,
        "current_execution_id": None,
        "source_count": None,
        "deep_research_available": None,
        "deep_research_unavailable_reason": None,
    },
    "source": {
        "id": None,
        "case_id": None,
        "filename": None,
        "media_type": None,
        "bytes": None,
        "sha256": None,
        "created_by": None,
        "created_at": None,
        "blocks": [
            {
                "block_id": None,
                "text": None,
                "locator": None,
                "confidence": None,
                "untrusted_data": None,
                "extractor_version": None,
            }
        ],
        "withdrawn": None,
        "source_set": _SOURCE_SET_KEYS,
    },
    "source_set": _SOURCE_SET_KEYS,
    "run": {
        "id": None,
        "case_id": None,
        "status": None,
        "plan": None,
        "node_ids": None,
        "nodes": [
            {
                "id": None,
                "run_id": None,
                "case_id": None,
                "module_id": None,
                "stage": None,
                "dependencies": None,
                "status": None,
                "attempt": None,
                "artifact_id": None,
                "error": None,
            }
        ],
        "events": [{"id": None, "event": None, "at": None, "data": None}],
        "current_node_id": None,
        "accepted_snapshot_id": None,
        "upgraded_from_run_id": None,
        "created_by": None,
        "created_at": None,
        "error": None,
    },
    "snapshot": {
        "id": None,
        "case_id": None,
        "run_id": None,
        "source_set_id": None,
        "source_set_version": None,
        "artifacts": [{"id": None, "module_id": None, "digest": None}],
        "digest": None,
        "previous_snapshot_id": None,
        "accepted_at": None,
    },
    "artifact": {
        "id": None,
        "case_id": None,
        "run_id": None,
        "module_id": None,
        "payload": None,
        "markdown": None,
        "digest": None,
        "input_fingerprint": None,
        "created_by": None,
        "created_at": None,
    },
    "model_readiness": {
        "status": None,
        "module_id": None,
        "accepted_snapshot": None,
        "source_set": None,
        "requirements": [{"module_id": None, "status": None}],
        "calculation_runtime": None,
        "worksheet_schema_version": None,
        "blockers": [{"code": None, "detail": None}],
        "build": None,
    },
    "model_build": {
        "id": None,
        "case_id": None,
        "accepted_run_id": None,
        "accepted_snapshot_id": None,
        "source_set_id": None,
        "input_fingerprint": None,
        "status": None,
        "queued_at": None,
        "started_at": None,
        "completed_at": None,
        "error": None,
        "export": {"status": None, "error": None},
        "worksheet_schema_version": None,
        "calculation_runtime": {
            "name": None,
            "version": None,
            "sha256": None,
            "assumption_registry_version": None,
            "assumption_registry_digest": None,
            "calculation_contract_version": None,
        },
    },
    "audit": {"id": None, "actor": None, "at": None, "action": None, "case_id": None},
}

# Every audit action the runtime and its gates emit beyond the representative flow.
AUDIT_ACTION_DETAILS = {
    "case.member_added": {"case_id": "case", "member": "member", "role": "READER"},
    "source.withdrawn": {"case_id": "case", "source_id": "source"},
    "snapshot.visible_switched": {"case_id": "case", "snapshot_id": "snapshot"},
    "model.retried": {"case_id": "case", "build_id": "model"},
    "model.calculate.succeeded": {"case_id": "case", "build_id": "model"},
    "model.export.succeeded": {"case_id": "case", "build_id": "model"},
    "model.export.queued": {"case_id": "case", "build_id": "model"},
    "model.export.failed": {
        "case_id": "case",
        "build_id": "model",
        "code": "MODEL_EXPORT_FAILED",
    },
    "model.export.downloaded": {"case_id": "case", "build_id": "model"},
    "report.approved": {"case_id": "case", "report_id": "report"},
    "research.plan_approved": {"case_id": "case", "run_id": "run", "plan_hash": "a" * 64},
    "note.created": {"case_id": "case", "note_id": "note"},
    "note.promoted": {"case_id": "case", "note_id": "note", "source_id": "source"},
    "assumption.created": {"case_id": "case", "assumption_id": "assumption"},
    "rv.universe_versioned": {"case_id": "case", "version": 1},
}

FULL_RUNTIME = {
    "name": "caos-model-python",
    "version": "1",
    "sha256": "c" * 64,
    "assumption_registry_version": "cp2g-assumptions-v1",
    "assumption_registry_digest": "d" * 64,
    "calculation_contract_version": "caos.model.calc.v1",
}


def _responses():
    import caos.responses

    return caos.responses


def _assert_key_sets(payload, expected) -> None:
    assert set(payload) == set(expected)
    for key, child in expected.items():
        if child is None:
            continue
        value = payload[key]
        if isinstance(child, list):
            assert isinstance(value, list)
            for item in value:
                _assert_key_sets(item, child[0])
        elif value is not None:
            _assert_key_sets(value, child)


def _round_trips(model, payload) -> bool:
    return model.model_validate(payload).model_dump(mode="json") == payload


def _admin_headers(settings) -> dict:
    return {
        "x-forwarded-user": "admin",
        "x-caos-role": "ADMIN",
        "x-oidc-step-up": settings.session_secret,
    }


def _build_spec(case_id: str, run: dict, snapshot: dict, fingerprint: str, runtime: dict | None = None) -> dict:
    return {
        "case_id": case_id,
        "accepted_run_id": run["id"],
        "accepted_snapshot_id": snapshot["id"],
        "source_set_id": snapshot["source_set_id"],
        "input_fingerprint": fingerprint,
        "worksheet_schema_version": "caos.model.worksheet.v1",
        "calculation_runtime": dict(runtime or FULL_RUNTIME),
    }


def _worksheet_result() -> dict:
    from caos.contracts import digest

    payload = {
        "schema_version": "caos.model.worksheet.v1",
        "identity": {"issuer_id": "issuer", "issuer_name": "Issuer", "analysis_date": "2026-08-26"},
        "tabs": [
            {
                "id": "MODEL",
                "name": "Model",
                "max_row": 1,
                "max_column": 1,
                "freeze_panes": "",
                "merged_cells": [],
                "columns": [{"column": 1, "letter": "A", "width": 12.0, "hidden": False}],
                "cells": [],
            }
        ],
    }
    return {
        "payload": payload,
        "payload_digest": digest(payload),
        "qa": {
            "status": "PASS",
            "semantic_checks": [],
            "semantic_check_count": 0,
            "formula_count": 0,
            "worksheet_cell_count": 0,
            "limitation_flags": [],
            "validation_warnings": [],
            "source_manifest": [],
        },
    }


@pytest.fixture()
async def payloads(client, store, engine) -> dict:
    """One representative end-to-end flow; every family payload comes off the wire."""
    case = client.post(
        "/api/cases", json={"name": "Contract case", "issuer": "Issuer", "sector": "Services"}
    ).json()
    case_id = case["id"]
    source = client.post(
        f"/api/cases/{case_id}/sources",
        files={"file": ("evidence.txt", b"Revenue 1,160\nEBITDA 222", "text/plain")},
    ).json()
    assert source["blocks"], "the representative source must carry extracted blocks"
    started = client.post(
        f"/api/cases/{case_id}/runs", json={"pathway": "EARNINGS_UPDATE", "depth": "screen"}
    ).json()
    await engine.wait(started["id"])
    run = client.get(f"/api/runs/{started['id']}").json()
    assert run["status"] == "succeeded" and run["nodes"] and run["events"]
    artifact_id = next(node["artifact_id"] for node in run["nodes"] if node["artifact_id"])
    artifact = client.get(f"/api/cases/{case_id}/artifacts/{artifact_id}").json()
    snapshot = client.post(f"/api/runs/{run['id']}/accept").json()
    assert snapshot["artifacts"]

    build, created = store.queue_model_build(_build_spec(case_id, run, snapshot, "0" * 64), "analyst")
    assert created is True
    model_build = client.get(f"/api/cases/{case_id}/models/{build['id']}").json()
    failed, _ = store.queue_model_build(_build_spec(case_id, run, snapshot, "1" * 64), "analyst")
    store.fail_model_build_for_tests(
        failed["id"], {"code": "MODEL_CALCULATION_FAILED", "detail": "Injected contract failure."}
    )
    failed_model_build = client.get(f"/api/cases/{case_id}/models/{failed['id']}").json()
    ready, _ = store.queue_model_build(_build_spec(case_id, run, snapshot, "2" * 64), "analyst")
    store.complete_model_build_for_tests(ready["id"], _worksheet_result())
    ready_model_build = client.get(f"/api/cases/{case_id}/models/{ready['id']}").json()
    readiness = client.get(f"/api/cases/{case_id}/model").json()

    note = client.post(f"/api/cases/{case_id}/notes", json={"body": "Promoted analyst note"}).json()
    promoted = client.post(f"/api/cases/{case_id}/notes/{note['id']}/promote").json()
    promoted_source_detail = client.get(
        f"/api/cases/{case_id}/sources/{promoted['promoted_source_id']}"
    ).json()
    source_detail = client.get(f"/api/cases/{case_id}/sources/{source['id']}").json()

    audit_events = store.list_audit()
    audit = next(event for event in audit_events if event["action"] == "case.created")
    return {
        "case": client.get(f"/api/cases/{case_id}").json(),
        "source": source,
        "source_detail": source_detail,
        "promoted_source_detail": promoted_source_detail,
        "source_set": source["source_set"],
        "run": run,
        "snapshot": snapshot,
        "artifact": artifact,
        "model_readiness": readiness,
        "model_build": model_build,
        "failed_model_build": failed_model_build,
        "ready_model_build": ready_model_build,
        "audit": audit,
        "audit_events": audit_events,
    }


# --- exact key sets + strict round-trip for every core family ---------------------


@pytest.mark.parametrize("family", FAMILIES)
async def test_representative_response_payloads_preserve_exact_key_sets(payloads, family):
    payload = payloads[family]
    _assert_key_sets(payload, KEY_SETS[family])
    model = getattr(_responses(), MODEL_NAMES[family])
    assert _round_trips(model, payload)


@pytest.mark.parametrize("family", FAMILIES)
async def test_family_models_reject_an_injected_unknown_top_level_key(payloads, family):
    from pydantic import ValidationError

    model = getattr(_responses(), MODEL_NAMES[family])
    with pytest.raises(ValidationError):
        model.model_validate({**payloads[family], "forged_extra_key": True})


# --- calculation-runtime identity (methodology provenance on the wire) ------------


async def test_model_build_rejects_unknown_calculation_runtime_fields(payloads):
    from caos.responses import ModelBuildResponse
    from pydantic import ValidationError

    forged = {**payloads["model_build"], "calculation_runtime": {"engine": "not-a-runtime-contract"}}
    with pytest.raises(ValidationError):
        ModelBuildResponse.model_validate(forged)


async def test_model_route_preserves_legacy_calculation_runtime_identity(payloads, client, store):
    """A 3-field legacy runtime record is served verbatim; absent registry/contract
    fields surface as null — never fabricated defaults."""
    legacy_runtime = {"name": "caos-model-python", "version": "0.9", "sha256": "b" * 64}
    case_id = payloads["case"]["id"]
    build, created = store.queue_model_build(
        _build_spec(case_id, payloads["run"], payloads["snapshot"], "9" * 64, runtime=legacy_runtime),
        "legacy-analyst",
    )
    assert created is True
    response = client.get(f"/api/cases/{case_id}/models/{build['id']}")
    assert response.status_code == 200
    runtime = response.json()["calculation_runtime"]
    assert {key: runtime[key] for key in legacy_runtime} == legacy_runtime
    assert runtime["assumption_registry_version"] is None
    assert runtime["assumption_registry_digest"] is None
    assert runtime["calculation_contract_version"] is None


async def test_model_readiness_uses_the_shared_model_build_shape(payloads):
    """Readiness embeds the one strict build schema — no shape drift between routes."""
    from caos.responses import ModelReadinessResponse

    payload = {**payloads["model_readiness"], "build": payloads["model_build"]}
    assert _round_trips(ModelReadinessResponse, payload)


# --- audit traceability -----------------------------------------------------------


@pytest.mark.parametrize("action", sorted(AUDIT_ACTION_DETAILS))
def test_every_enumerated_audit_action_validates_strictly(action):
    from caos.responses import AuditEventResponse

    payload = {
        "id": "aud-contract-1",
        "actor": "contract-test",
        "at": "2026-08-26T00:00:00+00:00",
        "action": action,
        **AUDIT_ACTION_DETAILS[action],
    }
    assert _round_trips(AuditEventResponse, payload)


async def test_audit_log_from_a_real_flow_validates_strictly(payloads):
    from caos.responses import AuditEventResponse

    assert payloads["audit_events"], "the representative flow must have audited"
    for payload in payloads["audit_events"]:
        assert _round_trips(AuditEventResponse, payload)


# --- lifecycle shapes -------------------------------------------------------------


@pytest.mark.parametrize(
    ("shape", "status"),
    [("model_build", "QUEUED"), ("failed_model_build", "FAILED"), ("ready_model_build", "READY")],
)
async def test_model_build_response_validates_each_lifecycle_shape(payloads, shape, status):
    from caos.responses import ModelBuildResponse

    payload = payloads[shape]
    assert payload["status"] == status
    if status == "FAILED":
        assert payload["error"]["code"] == "MODEL_CALCULATION_FAILED", "structured error codes"
    if status == "READY":
        assert payload["qa"]["status"] == "PASS" and payload["payload_digest"]
    assert _round_trips(ModelBuildResponse, payload)


# test_methodology_draft_response_validates_each_lifecycle_shape: EXCLUDED — methodology
# draft editing is cut from the MVP (DECISIONS §1); bundle verify and audit remain and are
# covered elsewhere. Listed in SPEC_RECONCILIATION.md.


# --- one strict source shape across its three appearances -------------------------


async def test_source_response_validates_upload_and_stored_shapes(payloads):
    from caos.responses import SourceResponse

    for name in ("source", "source_detail"):
        assert _round_trips(SourceResponse, payloads[name])


async def test_promoted_note_source_carries_source_kind_within_the_same_strict_shape(payloads):
    from caos.responses import SourceResponse

    payload = payloads["promoted_source_detail"]
    assert payload["source_kind"] == "analyst_note"
    assert _round_trips(SourceResponse, payload)


def test_withdrawn_source_detail_remains_retrievable_with_strict_public_shape(client):
    """Withdrawal is a flag, not deletion — evidence never disappears from the record."""
    from caos.responses import SourceResponse

    case = client.post(
        "/api/cases", json={"name": "Withdrawn detail", "issuer": "Issuer", "sector": "Services"}
    ).json()
    source = client.post(
        f"/api/cases/{case['id']}/sources",
        files={"file": ("evidence.txt", b"Debt 100", "text/plain")},
    ).json()
    withdrawn = client.post(f"/api/cases/{case['id']}/sources/{source['id']}/withdraw")
    detail = client.get(f"/api/cases/{case['id']}/sources/{source['id']}")
    assert withdrawn.status_code == 200 and detail.status_code == 200
    assert detail.json() == withdrawn.json()
    assert set(detail.json()) == {
        "id", "case_id", "filename", "media_type", "bytes",
        "sha256", "created_by", "created_at", "blocks", "withdrawn",
    }
    assert detail.json()["withdrawn"] is True
    assert _round_trips(SourceResponse, detail.json())


def test_upload_route_enforces_the_same_admission_as_the_ingestion_helper(client):
    """The hardening in sources.domain.ingest_upload is only real if the live
    route goes through it — an inline second copy is how the route drifted past
    its own tests once already."""
    case = client.post(
        "/api/cases", json={"name": "Admission", "issuer": "Issuer", "sector": "Services"}
    ).json()
    url = f"/api/cases/{case['id']}/sources"
    assert client.post(url, files={"file": ("payload.exe", b"MZ\x00", "application/octet-stream")}
                       ).status_code == 415, "suffix allowlist"
    assert client.post(url, files={"file": ("empty.txt", b"", "text/plain")}
                       ).status_code == 422, "empty source refused"
    assert client.post(url, files={"file": ("../../escape.txt", b"Debt 100", "text/plain")}
                       ).json()["filename"] == "escape.txt", "filename canonicalized"
    assert client.get(url.replace("/sources", "")).status_code == 200
    assert len(client.get(f"/api/cases/{case['id']}/sources").json()) == 1, "only the admitted source landed"


def test_distinct_duplicate_note_promotion_is_a_structured_source_conflict(client):
    case = client.post(
        "/api/cases", json={"name": "Note conflict", "issuer": "Issuer", "sector": "Services"}
    ).json()
    first = client.post(f"/api/cases/{case['id']}/notes", json={"body": "Same analyst view"}).json()
    second = client.post(f"/api/cases/{case['id']}/notes", json={"body": "Same analyst view"}).json()
    promoted = client.post(f"/api/cases/{case['id']}/notes/{first['id']}/promote")
    replay = client.post(f"/api/cases/{case['id']}/notes/{first['id']}/promote")
    conflict = client.post(f"/api/cases/{case['id']}/notes/{second['id']}/promote")
    assert promoted.status_code == 200 and replay.status_code == 200
    assert replay.json()["promoted_source_id"] == promoted.json()["promoted_source_id"]
    assert conflict.status_code == 409
    assert conflict.json() == {"detail": "source content already active"}
    notes = {note["id"]: note for note in client.get(f"/api/cases/{case['id']}/notes").json()}
    assert notes[first["id"]]["promoted"] is True
    assert notes[second["id"]]["promoted"] is False


# --- snapshot diffs are content-addressed -----------------------------------------


def test_snapshot_diff_entries_are_module_id_and_digest_only():
    from caos.responses import SnapshotDiffResponse

    payload = {
        "changed": True,
        "added": [{"module_id": "CP-1", "digest": "added"}],
        "removed": [{"module_id": "CP-0", "digest": "removed"}],
        "modified": [],
        "source_set_changed": False,
    }
    assert _round_trips(SnapshotDiffResponse, payload)


def test_snapshot_diff_entries_reject_artifact_and_snapshot_ids():
    from caos.responses import SnapshotDiffResponse
    from pydantic import ValidationError

    for forged_key in ("artifact_id", "snapshot_id"):
        payload = {
            "changed": True,
            "added": [{"module_id": "CP-1", "digest": "added", forged_key: "leaked"}],
            "removed": [],
            "modified": [],
            "source_set_changed": False,
        }
        with pytest.raises(ValidationError):
            SnapshotDiffResponse.model_validate(payload)


# --- OpenAPI: the declared contract governs every JSON success --------------------

# SSE and binary-download routes are the only non-JSON exemptions.
OPENAPI_EXEMPT = {
    ("get", "/api/runs/{run_id}/events"),
    ("get", "/api/cases/{case_id}/models/{build_id}/download"),
    ("get", "/api/cases/{case_id}/model-revisions/{revision_id}/download"),
    ("get", "/api/cases/{case_id}/deliverables/by-id/{deliverable_id}/export/{format_name}"),
    ("get", "/api/cases/{case_id}/reports/export/{format_name}"),
}


def test_openapi_refs_a_named_component_schema_for_every_2xx_json_response(client):
    paths = client.app.openapi()["paths"]
    for path, operations in paths.items():
        if not path.startswith("/api/"):
            continue
        for method, operation in operations.items():
            if (method, path) in OPENAPI_EXEMPT or method == "parameters":
                continue
            for status, response in operation["responses"].items():
                if not status.startswith("2"):
                    continue
                schema = response["content"]["application/json"]["schema"]
                assert "#/components/schemas/" in json.dumps(schema), (method, path, status)
    assert paths["/api/me"]["get"]["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/IdentityResponse"
    }
    assert paths["/api/cases"]["get"]["responses"]["200"]["content"]["application/json"]["schema"][
        "items"
    ] == {"$ref": "#/components/schemas/CaseResponse"}


@pytest.mark.parametrize(
    "schema_name",
    [
        "HealthResponse",
        "CaseDetailResponse",
        "CanonicalGenerationResponse",
        "CanonicalGenerationProgressResponse",
        "ThesisResponse",
        "LoanUniverseResponse",
        "LoanUniverseFindingResponse",
        "ModelListResponse",
        "VisualRecipeValidationResponse",
    ],
)
def test_openapi_named_response_schemas_forbid_additional_properties(client, schema_name):
    schemas = client.app.openapi()["components"]["schemas"]
    assert schemas[schema_name]["additionalProperties"] is False


def test_openapi_loan_import_serves_the_strict_universe_schema_on_200_and_201(client):
    responses = client.app.openapi()["paths"]["/api/cases/{case_id}/rv/loan-universes"]["post"][
        "responses"
    ]
    for status in ("200", "201"):
        assert responses[status]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/LoanUniverseResponse"
        }


# --- run events SSE: the graph event log on the wire ------------------------------


async def test_run_events_sse_tails_the_event_log_with_last_event_id_resume(client, engine):
    case_id = client.post(
        "/api/cases", json={"name": "SSE case", "issuer": "Issuer", "sector": "Services"}
    ).json()["id"]
    client.post(
        f"/api/cases/{case_id}/sources",
        files={"file": ("evidence.txt", b"Revenue 1,160\nEBITDA 222", "text/plain")},
    )
    started = client.post(
        f"/api/cases/{case_id}/runs", json={"pathway": "EARNINGS_UPDATE", "depth": "screen"}
    ).json()
    await engine.wait(started["id"])

    def read_frames(headers: dict | None = None) -> list[tuple[int, str]]:
        with client.stream("GET", f"/api/runs/{started['id']}/events", headers=headers) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            body = "".join(response.iter_text())
        frames = []
        for frame in body.split("\n\n"):
            lines = dict(line.split(": ", 1) for line in frame.splitlines() if ": " in line)
            if "event" in lines:
                frames.append((int(lines["id"]), lines["event"]))
        return frames

    frames = read_frames()
    ids = [seq for seq, _ in frames]
    names = [name for _, name in frames]
    assert names[0] == "run.created" and names[-1] == "run.succeeded"
    assert "node.succeeded" in names
    assert ids == sorted(ids) and len(set(ids)) == len(ids), "per-run monotonic sequence"
    # A terminal, fully delivered tail closes the stream (read_frames returned at all).

    resumed = read_frames({"Last-Event-ID": str(ids[-2])})
    assert resumed == frames[-1:], "Last-Event-ID resumes after the cursor without replay"

    assert client.get("/api/runs/rn_missing/events").status_code == 404


# --- canonical generation progress state ------------------------------------------


def _run_payload(extension: dict) -> dict:
    return {
        "id": "run",
        "case_id": "case",
        "status": "queued",
        "plan": {},
        "node_ids": [],
        "nodes": [],
        "events": [],
        "current_node_id": None,
        "accepted_snapshot_id": None,
        "upgraded_from_run_id": None,
        "created_by": "analyst",
        "created_at": "2026-08-26T00:00:00+00:00",
        "error": None,
        **extension,
    }


def _budgets() -> dict:
    return {
        "turns": 0,
        "evidence_reads": 0,
        "evidence_bytes": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "active_minutes": 0,
        "provider_retries": 0,
        "repairs": 0,
    }


def _generation_payload() -> dict:
    return {
        "phase": "generating",
        "model": "model",
        "reporting_period": "2026-08-26",
        "module_output_tokens": {
            "CP-1": 32_000,
            "CP-1A": 12_000,
            "CP-1B": 12_000,
            "CP-2": 16_000,
            "CP-2A": 16_000,
        },
        "budget_limits": {**_budgets(), "turns": 66, "evidence_reads": 60},
        "budget_used": _budgets(),
        "inflight_request_digest": None,
        "attempts": [],
    }


def test_canonical_generation_round_trips_and_preserves_completed_modules_omission():
    from caos.responses import CanonicalRunResponse

    base = _run_payload({"canonical_generation": _generation_payload()})
    dumped = CanonicalRunResponse.model_validate(base).model_dump(mode="json")
    assert dumped == base
    assert "completed_modules" not in dumped["canonical_generation"], "omission preserved, never fabricated"
    progressed = _run_payload(
        {"canonical_generation": {**_generation_payload(), "completed_modules": ["CP-1"]}}
    )
    assert _round_trips(CanonicalRunResponse, progressed)


def test_canonical_generation_rejects_unknown_keys():
    from caos.responses import CanonicalRunResponse
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CanonicalRunResponse.model_validate(
            _run_payload({"canonical_generation": {**_generation_payload(), "unexpected": True}})
        )


# --- loan-universe import results are strict to the leaf --------------------------


def _loan_universe_payload() -> dict:
    return {
        "id": "rvloan",
        "case_id": "case",
        "source_id": "source",
        "source_filename": "loans.xlsx",
        "source_sha256": "a" * 64,
        "workbook_date": None,
        "template_version": "cp3-sector-rv-v1",
        "importer_version": "loan-rv-importer-v1",
        "universe_digest": None,
        "row_count": 0,
        "status": "REJECTED",
        "findings": [
            {
                "code": "RV_TEMPLATE_MISSING",
                "detail": "Missing template.",
                "sheet": None,
                "row": None,
                "column": None,
            }
        ],
        "created_at": "2026-08-26T00:00:00+00:00",
        "created_by": "analyst",
        "version": None,
        "activated_at": None,
        "superseded_at": None,
        "withdrawn_at": None,
    }


def test_loan_universe_response_round_trips_a_full_rejected_payload():
    from caos.responses import LoanUniverseResponse

    assert _round_trips(LoanUniverseResponse, _loan_universe_payload())


def test_loan_universe_finding_rejects_an_unknown_key():
    from caos.responses import LoanUniverseResponse
    from pydantic import ValidationError

    payload = _loan_universe_payload()
    payload["findings"][0]["unexpected"] = True
    with pytest.raises(ValidationError):
        LoanUniverseResponse.model_validate(payload)


# --- server-side response validation fails closed ---------------------------------


def test_response_validation_fails_closed_on_the_idempotent_import_path(client, monkeypatch):
    """An invalid payload can never be served — not even on the already-exists
    fast path (created=False) that skips fresh computation."""
    import caos.api as api_module
    from fastapi.exceptions import ResponseValidationError

    case_id = client.post(
        "/api/cases", json={"name": "Loans", "issuer": "Issuer", "sector": "Services"}
    ).json()["id"]
    invalid = {**_loan_universe_payload(), "case_id": case_id, "unexpected": True}
    monkeypatch.setattr(api_module, "import_loan_source", lambda *args, **kwargs: (invalid, False))
    with pytest.raises(ResponseValidationError):
        client.post(f"/api/cases/{case_id}/rv/loan-universes", json={"source_id": "source"})


# ROW MAPPING (TEST_INVENTORY.md, test_http_response_contracts.py -> this file)
# test_representative_response_payloads_preserve_exact_key_sets -> test_representative_response_payloads_preserve_exact_key_sets (x9 families) + test_family_models_reject_an_injected_unknown_top_level_key (x9); identity/report/methodology_draft families trimmed to the nine in-scope families per the porting instruction (drafts still strict-validated below)
# test_model_build_rejects_unknown_calculation_runtime_fields -> test_model_build_rejects_unknown_calculation_runtime_fields
# test_model_route_preserves_legacy_calculation_runtime_identity -> test_model_route_preserves_legacy_calculation_runtime_identity
# test_model_readiness_uses_the_shared_model_build_shape -> test_model_readiness_uses_the_shared_model_build_shape
# test_audit_event_model_validates_every_captured_event -> test_every_enumerated_audit_action_validates_strictly (x15 actions) + test_audit_log_from_a_real_flow_validates_strictly
# test_model_build_response_validates_each_lifecycle_shape -> test_model_build_response_validates_each_lifecycle_shape (x3 queued/failed/ready)
# test_methodology_draft_response_validates_each_lifecycle_shape -> test_methodology_draft_response_validates_each_lifecycle_shape
# test_source_response_validates_upload_and_stored_source_shapes -> test_source_response_validates_upload_and_stored_shapes + test_promoted_note_source_carries_source_kind_within_the_same_strict_shape
# test_withdrawn_source_detail_remains_retrievable_with_strict_public_shape -> test_withdrawn_source_detail_remains_retrievable_with_strict_public_shape
# test_distinct_duplicate_note_promotion_is_a_structured_source_conflict -> test_distinct_duplicate_note_promotion_is_a_structured_source_conflict
# test_snapshot_diff_accepts_added_artifacts_without_snapshot_ids -> test_snapshot_diff_entries_are_module_id_and_digest_only + test_snapshot_diff_entries_reject_artifact_and_snapshot_ids
# test_openapi_declares_strict_models_for_every_json_success_response -> test_openapi_refs_a_named_component_schema_for_every_2xx_json_response + test_openapi_named_response_schemas_forbid_additional_properties (x9 schemas; ResearchStateResponse/ResearchPlanResponse dropped: CP-DR-only surface, out of MVP scope) + test_openapi_loan_import_serves_the_strict_universe_schema_on_200_and_201
# test_canonical_generation_is_strict_and_preserves_completed_module_omission -> test_canonical_generation_round_trips_and_preserves_completed_modules_omission + test_canonical_generation_rejects_unknown_keys
# test_loan_universe_findings_are_strict -> test_loan_universe_response_round_trips_a_full_rejected_payload + test_loan_universe_finding_rejects_an_unknown_key
# test_idempotent_loan_import_uses_fastapi_response_validation -> test_response_validation_fails_closed_on_the_idempotent_import_path
