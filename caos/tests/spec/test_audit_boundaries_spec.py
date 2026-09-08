"""Regressions for the validated API and runtime boundary findings."""

import inspect

import pytest


def test_empty_production_edge_secret_never_authenticates(settings):
    from dataclasses import replace
    from fastapi import HTTPException
    from starlette.requests import Request
    from caos.identity import identity_from_request

    request = Request({"type": "http", "headers": [(b"x-forwarded-user", b"forged")]})
    with pytest.raises(HTTPException) as caught:
        identity_from_request(request, replace(settings, environment="production", edge_proxy_secret=""))
    assert caught.value.status_code == 401


def test_pool_exhaustion_is_a_safe_service_unavailable(client, store, monkeypatch):
    from sqlalchemy.exc import TimeoutError

    def unavailable(*args, **kwargs):
        raise TimeoutError("private-database-host")

    monkeypatch.setattr(store, "list_cases", unavailable)
    response = client.get("/api/cases")
    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "STORE_UNAVAILABLE"}}


def test_validation_error_location_cannot_return_controls(client):
    response = client.post("/api/cases", content=br'{"name":"Case","issuer":"Issuer","\u0000":"secret"}',
                           headers={"content-type": "application/json"})
    assert response.status_code == 422
    assert "secret" not in response.text and "\\u0000" not in response.text
    assert response.json()["detail"][0]["loc"][-1] == "<field>"


@pytest.mark.parametrize("last_admin", [False, True])
def test_authorized_invalid_membership_change_has_a_typed_refusal(client, store, last_admin):
    case = store.create_case("Case", "Issuer", "Services", "owner")
    store.add_member(case["id"], "operator", "approver", "APPROVER", actor_role="ADMIN")
    store.add_member(case["id"], "operator", "admin", "ADMIN", actor_role="ADMIN")
    response = client.post(f"/api/cases/{case['id']}/members", json={
        "subject": "admin" if last_admin else "approver", "role": "READER",
    }, headers={"x-forwarded-user": "approver"})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == (
        "MEMBER_LAST_ADMIN_DEMOTION" if last_admin else "MEMBER_SELF_ROLE_CHANGE"
    )


async def test_existing_event_tail_stops_after_membership_revocation(app, engine, store):
    import sqlalchemy as sa
    from starlette.requests import Request
    from caos.storage.store import case_members

    case = store.create_case("Case", "Issuer", "Services", "analyst")
    run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst")
    endpoint = next(route.endpoint for route in app.routes if getattr(route, "path", None) == "/api/runs/{run_id}/events")

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request({"type": "http", "headers": []}, receive)
    response = await endpoint(run["id"], request)
    assert "event:" in await anext(response.body_iterator)
    with store.engine.begin() as conn:
        conn.execute(sa.delete(case_members).where(case_members.c.case_id == case["id"]))
    with pytest.raises(StopAsyncIteration):
        await anext(response.body_iterator)


def test_deliverable_error_does_not_expose_internal_validation_text(app):
    endpoint = next(route.endpoint for route in app.routes if getattr(route, "name", None) == "get_deliverable_draft")
    convert = inspect.getclosurevars(endpoint).nonlocals["deliverable_error"]
    result = convert(ValueError("invalid private-data field /host/path"))
    assert result.detail == {"code": "DELIVERABLE_REQUEST_INVALID"}


def test_upgrade_without_a_provider_identity_is_a_typed_refusal(client, engine, store):
    case = store.create_case("Case", "Issuer", "Services", "analyst")
    run = engine.runs.create_run(case["id"], "FULL_CREDIT", "screen", "analyst")
    response = client.post(f"/api/runs/{run['id']}/upgrade")
    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "AGENT_IDENTITY_MISMATCH"}}


def test_live_calculation_routes_are_covered_by_the_shared_ceiling(app, settings):
    import re
    from caos.api import RequestCeilings

    calls = {"preview", "rebase_preview", "scenario", "tornado", "one_way", "assumption_registry"}
    covered = set()
    limiter = RequestCeilings(None, settings=settings)
    for route in app.routes:
        if not hasattr(route, "endpoint"):
            continue
        methods = set(re.findall(r"models\(\)\.(\w+)\(", inspect.getsource(route.endpoint))) & calls
        if methods:
            assert limiter._slot({"path": route.path}) is not None, route.path
            covered.update(methods)
    assert covered == calls


def test_case_pages_are_explicit_complete_and_use_batched_queries(client, store):
    import sqlalchemy as sa

    ids = {store.create_case(f"Case {n}", "Issuer", "Services", "analyst")["id"] for n in range(5)}
    statements = []

    def observed(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    sa.event.listen(store.engine, "before_cursor_execute", observed)
    try:
        first = client.get("/api/cases", params={"limit": 3})
    finally:
        sa.event.remove(store.engine, "before_cursor_execute", observed)
    assert first.status_code == 200 and len(first.json()) == 3
    assert len(statements) <= 5, statements
    second = client.get("/api/cases", params={"limit": 3, "cursor": first.json()[-1]["id"]})
    assert {item["id"] for item in first.json() + second.json()} == ids
    assert len(second.json()) == 2


async def test_run_refresh_can_omit_the_embedded_event_history(client, engine, store, monkeypatch):
    case = store.create_case("Case", "Issuer", "Services", "analyst")
    run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst")

    def unexpected(*args):
        pytest.fail("UI refresh fetched the event history")

    monkeypatch.setattr(engine, "events_after", unexpected)
    response = client.get(f"/api/runs/{run['id']}?include_events=false")
    assert response.status_code == 200 and response.json()["events"] == []


async def test_finished_invocations_do_not_retain_per_run_locks(engine, store):
    import gc
    from spec_helpers import start_full_credit_run

    _, _, run = await start_full_credit_run(engine, store)
    await engine.wait(run["id"])
    gc.collect()  # completed graph tasks can retain exception cycles until GC
    assert not engine._thread_locks and not engine._agent_locks


async def test_event_tail_expires_to_reauthenticate_through_the_edge(app, engine, store, monkeypatch):
    from starlette.requests import Request
    from caos import api

    case = store.create_case("Case", "Issuer", "Services", "analyst")
    run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst")
    endpoint = next(route.endpoint for route in app.routes if getattr(route, "path", None) == "/api/runs/{run_id}/events")
    monkeypatch.setattr(api, "STREAM_LIFETIME_SECONDS", 0)
    response = await endpoint(run["id"], Request({"type": "http", "headers": []}))
    with pytest.raises(StopAsyncIteration):
        await anext(response.body_iterator)


@pytest.mark.parametrize("chunks, expected", [
    ([b"12", b"345"], 200), ([b"123", b"456"], 413), ([b"12", None], None),
])
async def test_transport_body_cap_checks_chunks_and_closes_spool(monkeypatch, chunks, expected):
    from tempfile import SpooledTemporaryFile
    from caos import api

    opened, sent, consumed = [], [], []

    def spool(**kwargs):
        body = SpooledTemporaryFile(**kwargs)
        opened.append(body)
        return body

    async def receive():
        chunk = chunks.pop(0)
        return ({"type": "http.disconnect"} if chunk is None else
                {"type": "http.request", "body": chunk, "more_body": bool(chunks)})

    async def app(scope, receive, send):
        while True:
            message = await receive()
            consumed.append(message["body"])
            if not message["more_body"]:
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})

    async def send(message):
        sent.append(message)

    monkeypatch.setattr(api, "SpooledTemporaryFile", spool)
    await api.RequestBodyLimit(app, max_bytes=5)({"type": "http", "method": "POST"}, receive, send)
    statuses = [message["status"] for message in sent if message["type"] == "http.response.start"]
    assert statuses == ([] if expected is None else [expected])
    assert b"".join(consumed) == (b"12345" if expected == 200 else b"")
    assert opened and all(body.closed for body in opened)


def test_legacy_case_list_refuses_instead_of_truncating(client, store):
    for n in range(101):
        store.create_case(f"Case {n}", "Issuer", "Services", "analyst")
    response = client.get("/api/cases")
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "CASE_LIST_LIMIT_EXCEEDED"


def test_source_list_size_refusal_precedes_block_deserialization(store):
    import sqlalchemy as sa
    from spec_helpers import seed_case_with_source

    case, _ = seed_case_with_source(store)
    statements = []

    def observed(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    sa.event.listen(store.engine, "before_cursor_execute", observed)
    try:
        with pytest.raises(ValueError, match="SOURCE_LIST_LIMIT_EXCEEDED"):
            store.list_sources(case["id"], max_bytes=1, limit=100)
    finally:
        sa.event.remove(store.engine, "before_cursor_execute", observed)
    assert len(statements) == 1 and "sum(" in statements[0].lower()


async def test_stalled_health_shares_one_task_and_leaves_the_request_pool_free(app, engine, monkeypatch):
    import asyncio
    import threading
    import anyio.to_thread
    import httpx

    reached, release = threading.Event(), threading.Event()
    calls = []

    def stalled():
        calls.append(1)
        reached.set()
        release.wait(3)
        return dict.fromkeys(("store", "bundle", "checkpointer"), False)

    monkeypatch.setattr(engine, "readiness", stalled)
    limiter = anyio.to_thread.current_default_thread_limiter()
    previous = limiter.total_tokens
    limiter.total_tokens = 1
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            health = asyncio.create_task(client.get("/api/health"))
            assert await asyncio.to_thread(reached.wait, 1)
            other = asyncio.create_task(client.get("/api/health"))
            try:
                me = await asyncio.wait_for(client.get("/api/me"), 0.5)
                assert me.status_code == 200
                health.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await health
                assert calls == [1]
            finally:
                release.set()
                await asyncio.gather(health, other, return_exceptions=True)
    finally:
        release.set()
        limiter.total_tokens = previous
