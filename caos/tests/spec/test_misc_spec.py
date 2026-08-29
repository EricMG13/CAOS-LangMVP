"""Remaining contractual rows not owned by another spec file: snapshot switching,
reader authz on upgrade, CP-2G handoff discipline, RV guards, recipes, host confidence,
duplicate-key model output."""

from __future__ import annotations

import json

import pytest

from spec_helpers import seed_case_with_source, start_full_credit_run


async def test_newer_accepted_run_sets_switch_required_until_explicit_switch(engine, store):
    """From test_end_to_end_source_run_snapshot_and_stale_boundary: accepted vs latest-accepted
    divergence surfaces switch_required; only an explicit switch moves the visible snapshot."""
    case, source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.wait(run["id"])
    first = await engine.accept(run["id"], actor="analyst")
    second_run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst")
    await engine.wait(second_run["id"])
    second = await engine.accept(second_run["id"], actor="analyst")
    await engine.switch_visible(case["id"], first["id"], actor="analyst")
    view = engine.snapshot_view(case["id"])
    assert view["switch_required"] is True, "older visible + newer accepted must demand a switch"
    await engine.switch_visible(case["id"], second["id"], actor="analyst")
    assert engine.snapshot_view(case["id"])["switch_required"] is False


async def test_read_only_member_cannot_upgrade_a_run(client, engine, store):
    case, source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.wait(run["id"])
    store.add_member(case["id"], "analyst", "reader-user", "READER", actor_role="ADMIN")
    response = client.post(f"/api/runs/{run['id']}/upgrade", headers={"x-forwarded-user": "reader-user"})
    assert response.status_code == 403


async def test_cp2g_emits_handoff_without_fabricated_workbook_values_or_signing_claims(engine, store, provider):
    """From test_full_credit_model_dependent_node_hands_off_to_model_builder.

    Amended 2026-08-27 with user sign-off (DECISIONS §13.9): CP-2G is
    agent-wired (registry union), so the artifact is the canonical envelope
    produced through the scripted-canonical run seam, not a deterministic host
    payload. The guarantee is unchanged: the stored handoff computes nothing
    Model Builder owns and carries no signing claims (Sign-Off is the author's
    store-CAS self-release, never module output). The original signing check
    was also a vacuous `or`; it is now a plain ban."""
    case, source = seed_case_with_source(store)
    run = await engine.run_scripted_for_tests(case["id"])
    artifact = next(a for a in engine.artifacts_for_run(run["id"]) if a["module_id"] == "CP-2G")
    assert artifact["payload"]["schema_version"] == "caos.canonical.artifact.v1"
    serialized = str(artifact["payload"]) + (artifact.get("markdown") or "")
    assert "signed-off" not in serialized.lower() and "sign-off" not in serialized.lower()
    assert "workbook_value" not in serialized, "the handoff computes nothing Model Builder owns"


def test_financial_guards_and_rv_signal_bands():
    """From test_financial_and_rv_guards: None on NaN/inf/zero-denominator; fixed spread bands."""
    from caos.models.engine import is_finite_number, safe_ratio
    from caos.artifacts.relative_value import signal_for_spread

    assert safe_ratio(10.0, 0.0) is None
    assert safe_ratio(float("nan"), 2.0) is None
    assert is_finite_number(0) and is_finite_number(False)
    assert not is_finite_number(float("inf")) and not is_finite_number(float("nan"))
    assert signal_for_spread(300) == "ATTRACTIVE"
    assert signal_for_spread(500) == "FAIR"
    assert signal_for_spread(700) == "UNATTRACTIVE"


def test_rv_currency_normalized_before_comparability_and_invalid_codes_rejected(client, store):
    case, _ = seed_case_with_source(store)
    saved = client.post(f"/api/cases/{case['id']}/rv", json={"rows": [
        {"issuer": "A", "instrument": "TL-B", "currency": "usd", "price": 99.5, "yield_bps": 500, "spread_bps": 450, "duration": 3.2},
        {"issuer": "B", "instrument": "TL-B", "currency": "USD", "price": 98.0, "yield_bps": 520, "spread_bps": 470, "duration": 3.0},
    ]})
    assert saved.status_code == 201
    body = client.get(f"/api/cases/{case['id']}/rv").json()
    currencies = {row["currency"] for row in body["universe"]["rows"]}
    assert currencies == {"USD"}, "usd normalizes to USD before comparability grouping"
    bad = client.post(f"/api/cases/{case['id']}/rv", json={"rows": [
        {"issuer": "C", "instrument": "TL-B", "currency": "U$", "price": 99.5, "yield_bps": 500, "spread_bps": 450, "duration": 3.2},
    ]})
    assert bad.status_code == 422


def test_rv_universe_round_trips_through_the_store(client, store):
    case, _ = seed_case_with_source(store)
    saved = client.post(f"/api/cases/{case['id']}/rv", json={"rows": [
        {"issuer": "A", "instrument": "TL-B", "currency": "USD", "price": 99.5, "yield_bps": 500, "spread_bps": 450, "duration": 3.2},
    ]})
    assert saved.status_code == 201
    assert client.get(f"/api/cases/{case['id']}/rv").json()["universe"]["id"] == saved.json()["id"]


def test_visual_recipe_is_declarative_and_fails_closed():
    from caos.publishing.recipes import validate_recipe

    validate_recipe({"kind": "line", "fields": ["total_leverage"]}, available_fields={"total_leverage"})
    with pytest.raises(Exception):
        validate_recipe({"kind": "line", "javascript": "alert(1)"}, available_fields=set())
    with pytest.raises(Exception):
        validate_recipe({"kind": "line", "fields": ["not_available"]}, available_fields={"total_leverage"})


def test_confidence_derives_only_from_host_attested_provenance():
    """Re-hosts test_cpdr_host_provenance_controls_adequacy_and_confidence: the provider's
    self-asserted confidence/authority/lineage values never enter the recomputation."""
    from caos.methodology.canonical import recompute_confidence

    forged = {"confidence_score": 100, "authority_class": "primary", "lineage": "complete"}
    result = recompute_confidence(
        declared_inputs={"lineage_counts": {"directly_sourced": 0}, "fields_present": 0, "fields_total": 10,
                         "source_gate": "fail", "findings": {"MATERIAL": 3}},
        provider_asserted=forged,
    )
    assert result["qa_status"] != "Passed", "host-recomputed confidence ignores provider assertions"


def test_final_model_output_rejects_duplicate_json_keys():
    from caos.engine.loop import parse_final_output

    with pytest.raises(Exception, match="AGENT_OUTPUT_INVALID|duplicate"):
        parse_final_output('{"markdown": "a", "markdown": "b"}')


# --- production edge posture (2026-08-27 OWASP review) ----------------------------


def _prod_app(tmp_path, store, engine):
    from caos.api import create_app
    from caos.config import Settings

    settings = Settings(storage_dir=tmp_path / "vault", environment="production",
                        edge_proxy_secret="e" * 40, session_secret="s" * 40)
    return create_app(settings=settings, store=store, engine=engine)


def test_unauthenticated_requests_are_refused_before_request_shape_validation(tmp_path, store, engine):
    """A body-required route must not answer 422 to a caller it never
    authenticated — that reading is indistinguishable, to a route audit, from a
    route that checks nothing."""
    from fastapi.testclient import TestClient

    client = TestClient(_prod_app(tmp_path, store, engine), raise_server_exceptions=False)
    url = "/api/cases/case-x/deliverables/by-id/dl-x/approve"
    assert client.post(url, json={}).status_code == 401, "no body"
    assert client.post(url, json={"preview_digest": "a" * 64,
                                  "input_fingerprint": "b" * 64}).status_code == 401, "valid body"
    assert client.get("/api/health").status_code == 200, "the public health check stays public"


def test_production_serves_no_framework_documentation_surface(tmp_path, store, engine):
    from fastapi.testclient import TestClient

    app = _prod_app(tmp_path, store, engine)
    client = TestClient(app, raise_server_exceptions=False)
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404, path
    assert app.openapi()["paths"], "the in-process schema the contract tests read still exists"
    assert "strict-transport-security" in client.get("/api/health").headers


def test_production_refuses_documented_placeholder_secrets():
    from caos.config import Settings

    real = {"environment": "production", "database_url": "postgresql://caos:s3cret-and-long@db/caos",
            "edge_proxy_secret": "e" * 40, "session_secret": "s" * 40}
    Settings(**real).validate_runtime()  # the good case must stay startable

    for field, value, expected in (
        ("edge_proxy_secret", "change-me-edge-secret", "EDGE_PROXY_SECRET"),
        ("session_secret", "change-me-session-secret", "SESSION_SECRET"),
        ("edge_proxy_secret", "dev-edge-secret", "EDGE_PROXY_SECRET"),
        ("session_secret", "", "SESSION_SECRET"),
        ("edge_proxy_secret", "short-but-random", "EDGE_PROXY_SECRET"),
    ):
        with pytest.raises(RuntimeError, match=expected):
            Settings(**{**real, field: value}).validate_runtime()

    with pytest.raises(RuntimeError, match="POSTGRES_PASSWORD"):
        Settings(**{**real, "database_url": "postgresql://caos:change-me-postgres@db/caos"}).validate_runtime()


def test_global_reader_cannot_create_a_case(tmp_path, store, engine):
    """create_case stores its creator as case ANALYST, so a reader creating
    cases mints latent authority that activates on the next IdP promotion."""
    from fastapi.testclient import TestClient

    client = TestClient(_prod_app(tmp_path, store, engine), raise_server_exceptions=False)
    headers = {"x-edge-authorization": "e" * 40, "x-forwarded-user": "reader",
               "x-forwarded-email": "r@example.com", "x-forwarded-groups": "caos-reader"}
    body = {"name": "Reader case", "issuer": "Issuer", "sector": "Services"}
    assert client.post("/api/cases", json=body, headers=headers).status_code == 403
    assert store.list_cases("reader") == []
    assert client.post("/api/cases", json=body,
                       headers={**headers, "x-forwarded-groups": "caos-analyst"}).status_code == 201


def test_per_subject_rate_ceiling_refuses_and_is_not_shared_between_subjects(tmp_path, store, engine):
    from fastapi.testclient import TestClient

    from caos.api import create_app
    from caos.config import Settings

    settings = Settings(storage_dir=tmp_path / "vault", rate_limit_per_minute=3)
    client = TestClient(create_app(settings=settings, store=store, engine=engine),
                        raise_server_exceptions=False)
    a = {"x-caos-role": "ANALYST", "x-forwarded-user": "analyst-a"}
    b = {"x-caos-role": "ANALYST", "x-forwarded-user": "analyst-b"}

    codes = [client.get("/api/cases", headers=a).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and codes[3:] == [429, 429], codes
    refusal = client.get("/api/cases", headers=a)
    assert refusal.headers["retry-after"] == "60"
    assert refusal.json() == {"detail": "request rate ceiling reached"}
    assert client.get("/api/cases", headers=b).status_code == 200, "buckets are per subject"
    assert client.get("/api/health").status_code == 200, "the health check is never throttled"


async def test_concurrent_stream_slots_are_capped_and_always_returned(tmp_path):
    """The run-events tail holds a worker for its whole lifetime, so it costs far
    more than the one token the rate bucket charges it. Driven against the
    middleware directly: TestClient cannot hold an endless SSE body open."""
    import asyncio

    from caos.api import RequestCeilings
    from caos.config import Settings

    released = asyncio.Event()
    started = asyncio.Semaphore(0)

    async def stub_app(scope, receive, send):
        started.release()
        await released.wait()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    settings = Settings(storage_dir=tmp_path / "vault", max_concurrent_streams=1)
    ceilings = RequestCeilings(stub_app, settings=settings)
    scope = {"type": "http", "method": "GET", "path": "/api/runs/run-1/events", "headers": []}
    sent: list[dict] = []

    async def call(sink):
        await ceilings(dict(scope), None, lambda message: _collect(sink, message))

    async def _collect(sink, message):
        sink.append(message)

    held = asyncio.create_task(call(sent))
    await started.acquire()                       # the first request owns the only slot

    refused: list[dict] = []
    await call(refused)
    assert refused[0]["status"] == 429
    assert json.loads(bytes(refused[1]["body"]))["detail"] == "too many open run-event streams"

    released.set()
    await held
    # The slot is returned when the stream finishes, never leaked.
    reopened: list[dict] = []
    await call(reopened)
    assert reopened[0]["status"] == 200
