"""Wire hardening the 2026-09-06 adversarial review asked for (W13, S9, X4),
each pinned by the smallest test that fails if the defect returns:

- the case wire is a projection of the row, so a new `cases` column never
  reaches an `extra="forbid"` response model and 500s every case route;
- the run-events tail treats a Last-Event-ID that names no position this log
  can hold (negative, unparsable, beyond the SQLite INTEGER range) as the
  start, instead of raising inside the generator after the 200 headers;
- the note-promotion conflict and the run-start refusal serve a typed
  `{"code": ...}` and never the exception text.
"""

from __future__ import annotations

from test_http_contracts_spec import KEY_SETS, _assert_key_sets

ANALYST = {"x-caos-role": "ANALYST", "x-forwarded-user": "analyst"}


# --- W13: the case wire is a projection, never the row ------------------------------


def test_case_wire_projects_the_row_so_a_new_column_never_reaches_the_wire(client, store, monkeypatch):
    case = client.post("/api/cases", json={"name": "Projected", "issuer": "Issuer", "sector": "Services"}, headers=ANALYST).json()
    real_get_case = store.get_case

    def get_case_with_a_new_column(case_id: str):
        row = real_get_case(case_id)
        return None if row is None else {**row, "new_column_added_by_a_migration": "value"}

    monkeypatch.setattr(store, "get_case", get_case_with_a_new_column)
    detail = client.get(f"/api/cases/{case['id']}", headers=ANALYST)
    assert detail.status_code == 200, detail.text
    _assert_key_sets(detail.json(), KEY_SETS["case"])
    listed = client.get("/api/cases", headers=ANALYST)
    assert listed.status_code == 200 and len(listed.json()) == 1
    _assert_key_sets(listed.json()[0], KEY_SETS["case"])
    assert "new_column_added_by_a_migration" not in detail.text


# --- S9: Last-Event-ID names a position or is the start ------------------------------


async def _terminal_run(client, engine) -> str:
    case_id = client.post("/api/cases", json={"name": "SSE", "issuer": "Issuer", "sector": "Services"}, headers=ANALYST).json()["id"]
    client.post(f"/api/cases/{case_id}/sources", files={"file": ("evidence.txt", b"Revenue 1,160\nEBITDA 222", "text/plain")}, headers=ANALYST)
    started = await engine.start_run_for_tests(
        case_id=case_id, pathway="EARNINGS_UPDATE", depth="screen", actor="analyst",
        allow_placeholder_deterministic=True,
    )
    await engine.wait(started["id"])
    return started["id"]


def _frames(client, run_id: str, last_event_id: str | None) -> list[tuple[int, str]]:
    headers = dict(ANALYST)
    if last_event_id is not None:
        headers["Last-Event-ID"] = last_event_id
    with client.stream("GET", f"/api/runs/{run_id}/events", headers=headers) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    frames = []
    for frame in body.split("\n\n"):
        lines = dict(line.split(": ", 1) for line in frame.splitlines() if ": " in line)
        if "event" in lines:
            frames.append((int(lines["id"]), lines["event"]))
    return frames


async def test_events_tail_replays_from_the_start_for_a_cursor_no_log_can_hold(client, engine):
    from caos.api import MAX_EVENT_CURSOR

    run_id = await _terminal_run(client, engine)
    everything = _frames(client, run_id, None)
    assert everything and everything[-1][1] == "run.succeeded"
    # Beyond SQLite's INTEGER: used to raise OverflowError inside the generator
    # after the 200 headers, and an EventSource retried forever.
    assert _frames(client, run_id, "99999999999999999999") == everything
    assert _frames(client, run_id, str(MAX_EVENT_CURSOR + 1)) == everything
    assert _frames(client, run_id, "-1") == everything
    assert _frames(client, run_id, "not-a-number") == everything
    assert _frames(client, run_id, "9" * 5_000) == everything
    # At the ceiling the cursor is a position: nothing follows it, the tail closes.
    assert _frames(client, run_id, str(MAX_EVENT_CURSOR)) == []
    # An ordinary cursor still resumes after itself without replay.
    assert _frames(client, run_id, str(everything[-2][0])) == everything[-1:]


# --- X4: typed refusals, never the exception text ------------------------------------


def test_note_promotion_conflict_is_a_typed_code(client):
    case = client.post("/api/cases", json={"name": "Notes", "issuer": "Issuer", "sector": "Services"}, headers=ANALYST).json()
    first = client.post(f"/api/cases/{case['id']}/notes", json={"body": "Same analyst view"}, headers=ANALYST).json()
    second = client.post(f"/api/cases/{case['id']}/notes", json={"body": "Same analyst view"}, headers=ANALYST).json()
    assert client.post(f"/api/cases/{case['id']}/notes/{first['id']}/promote", headers=ANALYST).status_code == 200
    conflict = client.post(f"/api/cases/{case['id']}/notes/{second['id']}/promote", headers=ANALYST)
    assert conflict.status_code == 409
    assert conflict.json() == {"detail": {"code": "SOURCE_CONTENT_ALREADY_ACTIVE"}}
    assert "already active" not in conflict.text


def test_start_run_value_error_is_a_typed_code(client, engine, monkeypatch):
    case = client.post("/api/cases", json={"name": "Runs", "issuer": "Issuer", "sector": "Services"}, headers=ANALYST).json()

    async def refuse(**kwargs):
        raise ValueError("text contains control characters: <never on the wire>")

    monkeypatch.setattr(engine, "start_run", refuse)
    refused = client.post(f"/api/cases/{case['id']}/runs", json={"pathway": "FULL_CREDIT", "depth": "screen"}, headers=ANALYST)
    assert refused.status_code == 422
    assert refused.json() == {"detail": {"code": "RUN_REQUEST_INVALID"}}
    assert "control characters" not in refused.text and "never on the wire" not in refused.text
