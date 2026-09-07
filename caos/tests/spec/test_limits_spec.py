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


def test_the_dataclass_default_is_the_only_default(monkeypatch):
    """W17 (2026-09-06 review): `from_env` used to repeat every default as an
    `os.getenv(NAME, "<literal>")` fallback, so the pinned dataclass figure and
    the figure a deployment actually ran under could drift apart. With nothing
    set, from_env is the dataclass, field for field."""
    import ast
    import inspect

    from caos import config
    from caos.config import Settings

    for name in Settings.ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    from_env = Settings.from_env()
    assert from_env == Settings()
    assert (from_env.max_source_bytes, from_env.max_upload_bytes) == (25 * 1024 * 1024, 32 * 1024 * 1024)
    assert (from_env.rate_limit_per_minute, from_env.max_concurrent_streams, from_env.max_concurrent_previews) == (300, 4, 2)
    assert (from_env.port, from_env.clamav_port, from_env.anthropic_model, from_env.openrouter_model) == (
        Settings.port, Settings.clamav_port, Settings.anthropic_model, Settings.openrouter_model)

    # No second copy of any default: every environment read in config.py is a
    # bare `os.getenv(name)`, never `os.getenv(name, "<literal>")`.
    getenv_calls = [
        node for node in ast.walk(ast.parse(inspect.getsource(config)))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "getenv" and isinstance(node.func.value, ast.Name) and node.func.value.id == "os"
    ]
    assert getenv_calls, "config.py reads the environment through os.getenv"
    assert all(len(call.args) == 1 and not call.keywords for call in getenv_calls), \
        "an os.getenv default is a second copy of a Settings default"


def test_from_env_reads_exactly_the_declared_variables(monkeypatch):
    from types import SimpleNamespace

    from caos import config
    from caos.config import Settings

    read: list[str] = []
    monkeypatch.setattr(config, "os", SimpleNamespace(getenv=lambda name: (read.append(name), None)[1]))
    assert Settings.from_env() == Settings()
    assert set(read) == set(Settings.ENV_NAMES) and len(Settings.ENV_NAMES) == len(set(Settings.ENV_NAMES))


def test_enterprise_provider_settings_survive_environment_projection(monkeypatch, tmp_path):
    from caos.config import Settings

    for name in Settings.ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    values = {
        "OPENAI_API_KEY": ("openai_api_key", "test-key"),
        "OPENAI_MODEL": ("openai_model", "configured-model"),
        "CAOS_PROVIDER_ACCOUNT_POLICY": ("provider_account_policy", "enterprise-policy"),
        "CAOS_DEFAULT_PROVIDER_BINDING": ("default_provider_binding", "chatgpt"),
        "CAOS_BUILD_COMMIT": ("candidate_commit", "a" * 40),
        "CAOS_IMAGE_SET_DIGEST": ("image_set_digest", "b" * 64),
        "CAOS_CORPUS_DIGEST": ("corpus_digest", "c" * 64),
    }
    for name, (_field, value) in values.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("CAOS_PROVIDER_CATALOG_PATH", str(tmp_path / "catalog.json"))
    monkeypatch.setenv("CAOS_ENTERPRISE_OPERATOR_SUBJECTS", " operator-a, ,operator-b ")
    settings = Settings.from_env()
    assert all(getattr(settings, field) == value for field, value in values.values())
    assert settings.provider_catalog_path == tmp_path / "catalog.json"
    assert settings.enterprise_operator_subjects == ("operator-a", "operator-b")
    monkeypatch.setenv("CAOS_PROVIDER_CATALOG_PATH", "")
    assert Settings.from_env().provider_catalog_path is None
    monkeypatch.setenv("PORT", "70000")
    monkeypatch.setenv("CAOS_ENTERPRISE_OPERATOR_SUBJECTS", "invalid subject")
    with pytest.raises(ValueError, match="^PORT must be between 0 and 65535$"):
        Settings.from_env()


def test_range_checks_apply_to_the_effective_values(monkeypatch):
    """The checks the old from_env made on its own literals now run on whatever
    value is effective — set or default — with the same messages."""
    from caos.config import Settings

    for name in Settings.ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    for name, value, message in (
        ("PORT", "70000", "PORT must be between 0 and 65535"),
        ("MAX_UPLOAD_MB", "0", "MAX_UPLOAD_MB must be greater than 0"),
        ("MAX_SOURCE_MB", "33", "MAX_SOURCE_MB must be greater than 0 and no larger than MAX_UPLOAD_MB"),
        ("CLAMAV_PORT", "0", "CLAMAV_PORT must be between 1 and 65535"),
        ("RATE_LIMIT_PER_MINUTE", "0", "RATE_LIMIT_PER_MINUTE must be greater than 0"),
        ("MAX_CONCURRENT_STREAMS", "0", "MAX_CONCURRENT_STREAMS must be greater than 0"),
        ("MAX_CONCURRENT_PREVIEWS", "-1", "MAX_CONCURRENT_PREVIEWS must be greater than 0"),
        ("CAOS_ENTERPRISE_OPERATOR_SUBJECTS", "invalid subject", "CAOS_ENTERPRISE_OPERATOR_SUBJECTS contains an invalid subject"),
        ("CAOS_ENTERPRISE_OPERATOR_SUBJECTS", ",".join(["operator"] * 101), "CAOS_ENTERPRISE_OPERATOR_SUBJECTS contains an invalid subject"),
    ):
        monkeypatch.setenv(name, value)
        with pytest.raises(ValueError) as refused:
            Settings.from_env()
        assert str(refused.value) == message, name
        monkeypatch.delenv(name)
    monkeypatch.setenv("MAX_SOURCE_MB", "32")  # at the default request ceiling: admitted
    assert Settings.from_env().max_source_bytes == Settings().max_upload_bytes


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


async def _drive_slot(path: str, setting: str, ceiling: int, refusal: str, tmp_path, *, probe: str | None = None):
    """Hold `ceiling` requests open on the slotted route for subject A, then
    prove the next A request (on `probe`, the same route by default) is
    refused, subject B is admitted, and every slot is returned. Driven against
    the middleware directly: TestClient cannot hold a response open."""
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

    def scope(subject: str, route: str = path) -> dict:
        return {"type": "http", "method": "POST", "path": route, "headers": [(b"x-forwarded-user", subject.encode())]}

    async def call(subject: str, sink: list, route: str = path):
        async def collect(message):
            sink.append(message)
        await ceilings(scope(subject, route), None, collect)

    held = [asyncio.create_task(call("subject-a", [])) for _ in range(ceiling)]
    for _ in range(ceiling):
        await started.acquire()
    refused: list[dict] = []
    await call("subject-a", refused, probe or path)
    assert refused[0]["status"] == 429 and json.loads(bytes(refused[1]["body"]))["detail"] == refusal
    other = asyncio.create_task(call("subject-b", [], probe or path))
    await started.acquire()                       # subject B holds a slot of its own
    released.set()
    await asyncio.gather(*held, other)
    again: list[dict] = []
    await call("subject-a", again, probe or path)
    assert again[0]["status"] == 200, "every slot is returned when the request ends"


# Every synchronous model calculation: each runs the same bounded computation
# (models.service MAX_CALCULATION_SECONDS) on a threadpool worker, so each holds
# a worker for its whole lifetime and each is bounded by the one calculation
# ceiling (W7, 2026-09-06 review).
CALCULATION_PATHS = (
    "/api/cases/c/models/previews",
    "/api/cases/c/models/scenarios",
    "/api/cases/c/models/tornado",
    "/api/cases/c/models/sensitivities/one-way",
    "/api/cases/c/model-revisions/rebase-preview",
)
CALCULATION_REFUSAL = "too many model calculations in flight"


@pytest.mark.parametrize("path", CALCULATION_PATHS)
async def test_calculation_ceiling_at_and_above_is_per_subject_and_returned(tmp_path, path):
    await _drive_slot(path, "max_concurrent_previews", 2, CALCULATION_REFUSAL, tmp_path)


@pytest.mark.parametrize("probe", CALCULATION_PATHS[1:])
async def test_calculation_paths_share_one_counter(tmp_path, probe):
    """Two previews in flight fill the ceiling for a scenario, a tornado, a
    one-way sensitivity and a rebase preview alike: one counter, not five."""
    await _drive_slot(CALCULATION_PATHS[0], "max_concurrent_previews", 2, CALCULATION_REFUSAL, tmp_path, probe=probe)


def test_only_the_calculation_routes_and_the_events_tail_are_slotted(tmp_path):
    from caos.api import RequestCeilings
    from caos.config import Settings

    ceilings = RequestCeilings(None, settings=Settings(storage_dir=tmp_path / "vault"))
    for path in CALCULATION_PATHS:
        assert ceilings._slot({"path": path}) is not None, path
    assert ceilings._slot({"path": "/api/runs/r/events"}) is not None
    for path in ("/api/cases/c/model", "/api/cases/c/models", "/api/cases/c/models/b/download",
                 "/api/cases/c/model-revisions", "/api/cases/c/model-revisions/sign-off",
                 "/api/cases/c/models/previews/extra", "/api/cases"):
        assert ceilings._slot({"path": path}) is None, path


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
