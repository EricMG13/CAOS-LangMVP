"""Below, exactly at, and above every admission and size ceiling (ENTERPRISE_
TESTING_READINESS PERF-001, PERF-002, PERF-004, SEC-012; Phase 6 item 11).

Above-limit work refuses before it consumes anything: no provider reservation,
no worker capacity, no vault byte, no store row. Below and at the limit are
admitted, so a ceiling that drifted by one is caught in both directions.
Development-scale ceilings are configured where the limit is a setting; the
declared enterprise figures (25 MiB, 32 MiB, 300/min, 4, 2, 20, 40, 2 000) are
pinned where they are constants. The HTTP-scale run of the same checks is
`qa/capacity.py limits` (candidate evidence, never claimed here)."""

from __future__ import annotations

import asyncio
import json

import pytest
import sqlalchemy as sa

from spec_helpers import seed_case_with_source

ANALYST = {"x-caos-role": "ANALYST", "x-forwarded-user": "analyst"}


def _client(tmp_path, store, engine, **overrides):
    from fastapi.testclient import TestClient

    from caos.api import create_app
    from caos.config import Settings

    settings = Settings(storage_dir=tmp_path / "vault", agent_execution_enabled=True, **overrides)
    return TestClient(create_app(settings=settings, store=store, engine=engine), raise_server_exceptions=False)


def test_declared_enterprise_ceilings_are_the_configured_defaults():
    from caos.config import Settings
    from caos.engine.budget import MAX_ACTIVE_JOBS, MAX_MANIFEST_BLOCKS
    from caos.intake.service import MAX_INTAKE_FILES

    settings = Settings()
    assert (settings.max_source_bytes, settings.max_upload_bytes) == (25 * 1024 * 1024, 32 * 1024 * 1024)
    assert (settings.rate_limit_per_minute, settings.max_concurrent_streams, settings.max_concurrent_previews) == (300, 4, 2)
    assert (MAX_ACTIVE_JOBS, MAX_INTAKE_FILES, MAX_MANIFEST_BLOCKS) == (20, 40, 2_000)


def test_source_size_ceiling_below_at_and_above_refuses_before_scan_or_vault(tmp_path, store, engine, monkeypatch):
    from caos.sources import domain

    scanned: list[int] = []
    real_scan = domain.scan_content
    monkeypatch.setattr(domain, "scan_content", lambda content, settings: (scanned.append(len(content)), real_scan(content, settings)))
    ceiling = 64
    with _client(tmp_path, store, engine, max_source_bytes=ceiling) as client:
        case = store.create_case("Limits", "Issuer", "Services", "analyst")
        outcomes = {}
        for size in (ceiling - 1, ceiling, ceiling + 1):
            body = (b"line\n" * (size // 5 + 1))[:size]
            response = client.post(f"/api/cases/{case['id']}/sources",
                                   files={"file": (f"s{size}.txt", body, "text/plain")}, headers=ANALYST)
            outcomes[size] = response.status_code
        assert outcomes == {ceiling - 1: 201, ceiling: 201, ceiling + 1: 413}, outcomes
        assert len(store.list_sources(case["id"])) == 2, "below and at the ceiling are admitted; above is not"
        assert scanned == [ceiling - 1, ceiling], "the over-limit body was refused before the malware scan"
        vault = tmp_path / "vault" / "sources"
        assert sum(1 for path in vault.rglob("*") if path.is_file()) == 2, "no vault byte for the refused source"


def test_request_ceiling_bounds_the_source_ceiling_and_is_enforced_at_the_edge(monkeypatch):
    """The 32 MiB request body is the edge's ceiling (Caddy `max_size`), the app
    only ever reads one source up to its own 25 MiB cap: the configuration
    refuses a source cap above the request cap so no upload can be admitted by
    the app and refused by the edge."""
    from pathlib import Path

    from caos.config import Settings

    monkeypatch.setenv("MAX_UPLOAD_MB", "32")
    monkeypatch.setenv("MAX_SOURCE_MB", "33")
    with pytest.raises(ValueError, match="MAX_SOURCE_MB"):
        Settings.from_env()
    monkeypatch.setenv("MAX_SOURCE_MB", "32")
    assert Settings.from_env().max_source_bytes == Settings.from_env().max_upload_bytes
    caddyfile = (Path(__file__).resolve().parents[3] / "caos" / "deploy" / "Caddyfile").read_text()
    assert "max_size {$MAX_UPLOAD_MB:32}MiB" in caddyfile


def test_intake_file_ceiling_at_and_above_refuses_before_any_admission(tmp_path, store, engine, monkeypatch):
    from caos.intake import service as intake_module
    from caos.sources import domain

    prepared: list[str] = []
    real_prepare = domain.prepare_upload

    async def counting_prepare(vault, upload, max_bytes):
        prepared.append(upload.filename)
        return await real_prepare(vault, upload, max_bytes)

    monkeypatch.setattr(intake_module, "prepare_upload", counting_prepare)
    ceiling = intake_module.MAX_INTAKE_FILES
    with _client(tmp_path, store, engine) as client:
        files = [("files", (f"doc-{index:02d}.txt", b"Annual report FY2025 revenue 1\n", "text/plain")) for index in range(ceiling + 1)]
        above = client.post("/api/intake", files=files, headers=ANALYST)
        assert above.status_code == 422 and above.json()["detail"]["code"] == "INTAKE_TOO_MANY_FILES"
        assert prepared == [] and store.list_cases("analyst") == [], "the 41st file refused the pack before any file was read"
        at = client.post("/api/intake", files=files[:ceiling], headers=ANALYST)
        assert at.status_code in {200, 201, 422}, at.text
        assert len(prepared) == ceiling, "exactly at the ceiling every file is examined"
        assert (at.status_code != 422) or above.json()["detail"]["code"] != at.json()["detail"]["code"]


def test_manifest_block_ceiling_at_and_above_is_refused_before_provider_contact():
    from caos.engine.budget import MAX_MANIFEST_BLOCKS, AgentError, bound_manifest

    def entry(blocks: int) -> dict:
        return {"source_id": "src", "filename": "a.txt", "media_type": "text/plain", "sha256": "a" * 64,
                "blocks": [{"block_id": f"b{index:05d}", "locator": {"line": index + 1}, "extractor_version": "builtin-v1",
                            "confidence": "MEDIUM", "text": "x"} for index in range(blocks)]}

    assert len(bound_manifest([entry(MAX_MANIFEST_BLOCKS - 1)])) == 1  # one source row + 1 999 blocks = at
    with pytest.raises(AgentError) as refused:
        bound_manifest([entry(MAX_MANIFEST_BLOCKS)])              # 2 001 rows
    assert refused.value.code == "AGENT_BUDGET_EXCEEDED"


async def test_manifest_above_the_ceiling_fails_the_run_typed_with_no_provider_call(engine, store, provider):
    import hashlib

    from caos.engine.budget import MAX_MANIFEST_BLOCKS

    case = store.create_case("Wide", "Issuer", "Services", "analyst")
    text = "\n".join(f"line {index}" for index in range(MAX_MANIFEST_BLOCKS))
    store.ingest({
        "case_id": case["id"], "filename": "wide.txt", "media_type": "text/plain", "bytes": len(text),
        "sha256": hashlib.sha256(text.encode()).hexdigest(), "vault_path": None, "withdrawn": False,
        "blocks": [{"block_id": f"b{index:05d}", "locator": {"line": index + 1}, "text": f"line {index}",
                    "extractor_version": "builtin-v1", "confidence": "MEDIUM", "untrusted_data": True}
                   for index in range(MAX_MANIFEST_BLOCKS)],
    }, "analyst")
    # The ordinary provider-backed path: the manifest is bounded inside the first
    # agent module node, before that node's provider call.
    run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst")
    await engine.wait(run["id"])
    final = engine.get_run(run["id"])
    assert final["status"] == "failed" and final["error"]["code"] == "AGENT_BUDGET_EXCEEDED", final["error"]
    assert provider.count_requests == [] and provider.create_requests == [], "refused before any provider contact"


async def test_active_job_ceiling_refuses_the_twenty_first_before_any_reservation(tmp_path, store, engine, provider):
    from caos.engine.budget import MAX_ACTIVE_JOBS
    from caos.storage.runs import run_budgets, runs

    def counts():
        with store.engine.connect() as conn:
            return (conn.execute(sa.select(sa.func.count()).select_from(runs)).scalar(),
                    conn.execute(sa.select(sa.func.count()).select_from(run_budgets)).scalar())

    case, _ = seed_case_with_source(store)
    engine.fill_admission_slots_for_tests(MAX_ACTIVE_JOBS)
    before = counts()
    with _client(tmp_path, store, engine) as client:
        refused = client.post(f"/api/cases/{case['id']}/runs", json={"pathway": "FULL_CREDIT", "depth": "screen"}, headers=ANALYST)
    assert refused.status_code == 409 and refused.json() == {"detail": {"code": "ADMISSION_BUSY"}}
    assert counts() == before, "no run row and no budget ledger row for the refused job"
    assert provider.count_requests == [] and provider.create_requests == []
    engine.release_admission_slot_for_tests()
    with _client(tmp_path, store, engine) as client:
        admitted = client.post(f"/api/cases/{case['id']}/runs", json={"pathway": "FULL_CREDIT", "depth": "screen"}, headers=ANALYST)
    assert admitted.status_code == 201, "capacity returned admits the next job"


async def _drive_slot(path: str, setting: str, ceiling: int, refusal: str, tmp_path):
    """Hold `ceiling` requests open on the slotted route for subject A, then
    prove the next A request is refused, subject B is admitted, and every slot
    is returned. Driven against the middleware directly: TestClient cannot hold
    a response open."""
    from caos.api import RequestCeilings
    from caos.config import Settings

    released = asyncio.Event()
    started = asyncio.Semaphore(0)

    async def stub_app(scope, receive, send):
        started.release()
        await released.wait()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    ceilings = RequestCeilings(stub_app, settings=Settings(storage_dir=tmp_path / "vault", **{setting: ceiling}))

    def scope(subject: str) -> dict:
        return {"type": "http", "method": "POST", "path": path, "headers": [(b"x-forwarded-user", subject.encode())]}

    async def call(subject: str, sink: list):
        async def collect(message):
            sink.append(message)
        await ceilings(scope(subject), None, collect)

    held = [asyncio.create_task(call("subject-a", [])) for _ in range(ceiling)]
    for _ in range(ceiling):
        await started.acquire()
    refused: list[dict] = []
    await call("subject-a", refused)
    assert refused[0]["status"] == 429 and json.loads(bytes(refused[1]["body"]))["detail"] == refusal
    other = asyncio.create_task(call("subject-b", []))
    await started.acquire()                       # subject B holds a slot of its own
    released.set()
    await asyncio.gather(*held, other)
    again: list[dict] = []
    await call("subject-a", again)
    assert again[0]["status"] == 200, "every slot is returned when the request ends"


async def test_preview_ceiling_at_and_above_is_per_subject_and_returned(tmp_path):
    await _drive_slot("/api/cases/c/models/previews", "max_concurrent_previews", 2,
                      "too many model previews in flight", tmp_path)


async def test_stream_ceiling_at_and_above_is_per_subject_and_returned(tmp_path):
    await _drive_slot("/api/runs/r/events", "max_concurrent_streams", 4,
                      "too many open run-event streams", tmp_path)


def test_rate_ceiling_exactly_at_the_limit_is_admitted_and_one_more_is_refused(tmp_path, store, engine):
    ceiling = 5
    with _client(tmp_path, store, engine, rate_limit_per_minute=ceiling) as client:
        codes = [client.get("/api/cases", headers=ANALYST).status_code for _ in range(ceiling + 1)]
        assert codes == [200] * ceiling + [429], codes
        other = client.get("/api/cases", headers={**ANALYST, "x-forwarded-user": "someone-else"})
        assert other.status_code == 200, "a saturated subject does not affect another"
