"""Observability specification: three questions at 3am, and one hard ban.

The server logs nothing today. This file pins what it must log — *and*, more
importantly, what it must never log.

The three questions the log has to answer without a debugger:

    which run is stuck   run/node state transitions + the gate interrupt
    what did it refuse   the typed refusal code, never the refused content
    what has it spent    provider token counts, budget reserve + reconcile

The ban is invariant-shaped: **no document-derived text may ever reach a log
line.** Source text, evidence block text, module output, and compiled prompts
are all attacker-controlled (every document CAOS ingests is), and a log sink is
outside every boundary the ten invariants defend. `test_no_document_text…` is
the point of this file: it drives a real ingestion and a real agent module node
over a document carrying a unique sentence, captures every log record any
logger emits, renders each through the real JSON formatter, and asserts the
sentence is nowhere in the output.

Anti-vacuity: each no-leak test also asserts the log is non-empty and that the
document actually reached the model, so a server that logs nothing — or a run
that never read the evidence — cannot pass by doing less.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
from typing import Any

import pytest

from spec_helpers import text_message, tool_call_message

# A sentence that exists nowhere else in this repo. If it turns up in a log
# line, document text escaped the host.
SENTINEL = "ZQXJV-COVENANT-HEADROOM-SENTINEL-8f31"
SECOND_SENTINEL = "ZQXJV-RESTATED-EBITDA-SENTINEL-c07a"

CANONICAL_BODY = "\n\n".join(
    f"## {heading}\n\nnorthwind covenant headroom paragraph"
    for heading in ("Audit Summary", "Analysis", "Evidence Trace", "Source Registry",
                    "Gaps & Conflicts", "QA Validation")
)


# --- capturing every log record, rendered the way production renders it -----------


@pytest.fixture()
def logs():
    """Attach the real JSON formatter to the root logger AND the caos logger, so
    a leak cannot hide behind `propagate = False` or a differently-named logger.
    Rendering through the production formatter is the point: a sentinel smuggled
    in a record attribute rather than the message would still surface here."""
    from caos.observability import LOGGER_NAME, JsonFormatter

    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(JsonFormatter())
    handler.setLevel(logging.DEBUG)

    # The caos logger is opened to DEBUG so no level can hide a leak of ours;
    # the root logger stays at INFO, because dropping every library to DEBUG
    # captures aiosqlite's checkpoint blobs rather than anything CAOS emits.
    targets = [logging.getLogger(), logging.getLogger(LOGGER_NAME)]
    saved = [(logger.level, logger.propagate) for logger in targets]
    for logger, level in zip(targets, (logging.INFO, logging.DEBUG)):
        logger.addHandler(handler)
        logger.setLevel(level)
    try:
        yield buffer
    finally:
        for logger, (level, propagate) in zip(targets, saved):
            logger.removeHandler(handler)
            logger.setLevel(level)
            logger.propagate = propagate


def lines(buffer: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in buffer.getvalue().splitlines() if line.strip()]


def events(buffer: io.StringIO) -> list[str]:
    return [line["event"] for line in lines(buffer)]


def of(buffer: io.StringIO, event: str) -> list[dict[str, Any]]:
    return [line for line in lines(buffer) if line.get("event") == event]


# --- a document carrying the sentinel, and a provider that reads it ----------------


def ingest_sentinel_document(store, case_id: str, *, filename: str = "issuer-filing.txt",
                             body: str | None = None, source_id: str | None = None) -> dict[str, Any]:
    text = body if body is not None else (
        f"Northwind Holdings FY24 filing.\n{SENTINEL}\nNet leverage 3.4x against a 4.0x covenant."
    )
    raw = text.encode("utf-8")
    payload = {
        "case_id": case_id, "filename": filename, "media_type": "text/plain",
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "vault_path": None,
        "blocks": [{"block_id": "b00001", "locator": {"line": 1}, "text": text,
                    "extractor_version": "builtin-v1", "confidence": "MEDIUM", "untrusted_data": True}],
        "withdrawn": False,
    }
    if source_id is not None:
        payload["id"] = source_id
    return store.ingest(payload, "analyst")


def _tool_results(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                rows.extend(json.loads(block["content"]))
    return rows


class ReadingProvider:
    """Reads the pinned document once per module, then answers canonically.

    Deliberately ordinary: the sentinel reaches this double through the real
    `read_evidence` tool, exactly as it would reach a real model.
    """

    def __init__(self, source_id: str, *, count: int = 1_000, read_source_id: str | None = None,
                 read_block_ids: list[str] | None = None, poison: bool = False) -> None:
        self.source_id = source_id
        self.read_source_id = read_source_id or source_id
        self.read_block_ids = read_block_ids or ["b00001"]
        self.poison = poison
        self.echoed: str | None = None
        self.count = count
        self.count_requests: list[Any] = []
        self.create_requests: list[Any] = []
        self.reads = 0

    def count_tokens(self, request) -> int:
        self.count_requests.append(request)
        return self.count

    def create_message(self, request):
        self.create_requests.append(request)
        rows = _tool_results(request.messages)
        if not rows:
            self.reads += 1
            return tool_call_message(self.read_source_id, self.read_block_ids)
        return text_message(json.dumps({
            "markdown": CANONICAL_BODY,
            "evidence_refs": [{"source_id": row["source_id"], "block_id": row["block_id"]} for row in rows],
            "lineage_counts": {"directly_sourced": 1},
            "fields_present": 4,
            "fields_total": 4,
            # A model that echoes the document into a typed field: the
            # validator's own error message then quotes it back.
            "source_gate": (self._echo(rows) if self.poison else "pass"),
            "findings": {},
        }))

    def _echo(self, rows: list[dict[str, Any]]) -> str:
        text = rows[0]["text"]
        # Short enough that the validator renders it in full, so the sentinel is
        # genuinely inside the exception the host then has to keep out of logs.
        self.echoed = next((line for line in text.splitlines() if SENTINEL in line), text[:120])
        return self.echoed

    def saw_the_document(self) -> bool:
        blob = json.dumps([request.messages for request in self.create_requests], default=str)
        return SENTINEL in blob


@pytest.fixture()
def build_engine(tmp_path, settings, store):
    def build(provider):
        from caos.engine.runtime import Engine

        return Engine.create(settings=settings, store=store,
                             checkpoint_path=tmp_path / "checkpoints.db", provider=provider)

    return build


async def _sentinel_agent_run(build_engine, store, **provider_kwargs):
    case = store.create_case("Northwind", "Northwind Holdings", "Services", "analyst")
    pinned = ingest_sentinel_document(store, case["id"])
    provider = ReadingProvider(pinned["id"], **provider_kwargs)
    engine = build_engine(provider)
    run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst")
    await engine.wait(run["id"])
    return engine, provider, case, pinned, engine.get_run(run["id"])


# --- THE test: no document text, ever ---------------------------------------------


async def test_no_document_text_ever_reaches_a_log_line(build_engine, store, logs):
    """Ingestion + a real agent module node over a document carrying a unique
    sentence. Every log record, rendered through the production formatter, is
    searched for it.

    Three anti-vacuity guards: the log must be non-empty, the run must have
    actually succeeded through its agent modules, and the sentinel must have
    genuinely reached the model — a host that never read the evidence would
    pass this test while proving nothing.
    """
    engine, provider, _case, _pinned, record = await _sentinel_agent_run(build_engine, store)

    assert record["status"] == "succeeded", record.get("error")
    assert provider.reads > 0 and provider.saw_the_document(), \
        "the document must have reached the model, or this test proves nothing"

    captured = logs.getvalue()
    assert captured.strip(), "the run logged nothing at all — nothing is being asserted"
    assert SENTINEL not in captured, "document text reached a log line"
    assert "covenant" not in captured.lower(), "document prose reached a log line"
    assert CANONICAL_BODY.splitlines()[0] not in captured, "module output reached a log line"


async def test_a_refused_read_logs_its_typed_code_and_none_of_the_document(build_engine, store, logs):
    """The refusal path is the one that most wants to explain itself. It may
    carry the taxonomy code and the module id; it may not carry one byte of the
    document it refused, nor of the document it was reading from."""
    case = store.create_case("Northwind", "Northwind Holdings", "Services", "analyst")
    pinned = ingest_sentinel_document(store, case["id"])
    provider = ReadingProvider(pinned["id"], read_source_id="src-neverpinned00001")
    engine = build_engine(provider)
    run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst")

    # In the case, outside the pinned set: refused by membership (invariant 1).
    ingest_sentinel_document(store, case["id"], filename="restated.txt",
                             body=f"Restated pack.\n{SECOND_SENTINEL}\n",
                             source_id="src-neverpinned00001")
    await engine.wait(run["id"])

    record = engine.get_run(run["id"])
    assert record["status"] == "failed"
    assert record["error"]["code"] == "AGENT_AUTHORITY_MISMATCH"

    refusals = of(logs, "refusal")
    assert refusals, "a typed refusal must be logged"
    assert any(line["code"] == "AGENT_AUTHORITY_MISMATCH" for line in refusals)
    assert all(line.get("run_id") == record["id"] for line in refusals)

    captured = logs.getvalue()
    assert SENTINEL not in captured and SECOND_SENTINEL not in captured
    assert "restated" not in captured.lower(), "even a filename's prose stays out"


async def test_an_output_validation_failure_never_logs_the_text_it_rejected(build_engine, store, logs):
    """The realistic leak, and the one the taxonomy codes tempt you into.

    Here the module echoes the document into a typed field, so the validator's
    own exception quotes document text — `input_value='ZQXJV-…'`. A refusal line
    that carried `exc_info`, or the `__cause__`'s message, would leak it. This
    is what makes the "code only" rule at that call site a tested rule rather
    than a comment.
    """
    engine, provider, _case, _pinned, record = await _sentinel_agent_run(build_engine, store, poison=True)

    assert record["status"] == "failed"
    assert record["error"]["code"] == "AGENT_OUTPUT_INVALID"
    assert provider.echoed and SENTINEL in provider.echoed, \
        "the rejected field value must carry the sentinel, or this proves nothing"
    assert any(line["code"] == "AGENT_OUTPUT_INVALID" for line in of(logs, "refusal"))
    assert SENTINEL not in logs.getvalue()


def test_the_no_leak_capture_sees_the_fields_it_searches(logs):
    """Guards the guard. Every `SENTINEL not in logs` assertion is worth exactly
    nothing if the capture is blind, so prove it is not: a field carrying the
    sentinel must show up."""
    from caos.observability import log_event

    log_event("run.created", run_id="run-x", pathway=SENTINEL)
    assert SENTINEL in logs.getvalue()


def test_every_logged_string_is_bounded_so_no_field_can_become_a_content_channel():
    """The structural backstop behind the call-site discipline.

    Discipline says "pass codes, never content". This is what holds when
    discipline slips: every string on a log line — a field, an exception
    rendered from `exc_info`, a stack — is truncated, so a mistake costs at
    most MAX_STRING characters instead of a whole document or prompt.
    """
    from caos.observability import MAX_STRING, log_event

    document = "A" * 50 + SENTINEL + "B" * 100_000

    class Payload:
        """Not a str: the bound has to hold on whatever a caller hands over."""

        def __str__(self) -> str:
            return document

    line = json.loads(_capture(lambda: log_event(
        "refusal", code="X", detail=document, payload=Payload(), nested={"markdown": document},
    )))
    assert len(line["detail"]) == MAX_STRING
    assert len(line["payload"]) == MAX_STRING, "the non-string branch bounds too"
    assert len(line["nested"]["markdown"]) == MAX_STRING, "and so does a nested one"

    # Bounded, but not blind: a leak in the first MAX_STRING characters — which
    # is where a leak that matters lands — is still visible to the tests above.
    assert SENTINEL in line["detail"]


# --- the three questions ----------------------------------------------------------


async def test_the_log_answers_which_run_is_stuck(build_engine, store, logs):
    """Run and node state transitions, each carrying the run id."""
    _engine, _provider, _case, _pinned, record = await _sentinel_agent_run(build_engine, store)

    seen = set(events(logs))
    assert {"run.created", "run.running", "node.running", "node.succeeded", "run.succeeded"} <= seen
    for line in lines(logs):
        if line["event"].startswith(("run.", "node.")):
            assert line["run_id"] == record["id"], line
    assert of(logs, "node.running"), "a stuck run is found by its last node.running"
    assert {line.get("module_id") for line in of(logs, "node.running")} >= {"CP-1"}


async def test_the_log_answers_what_it_has_spent(build_engine, store, logs):
    """Provider call start/finish with token counts, and the budget ledger's
    reservation and reconciliation — the two halves of invariant 8."""
    _engine, _provider, _case, _pinned, record = await _sentinel_agent_run(build_engine, store)

    starts, finishes = of(logs, "provider.call.start"), of(logs, "provider.call.finish")
    assert starts and finishes
    assert all(line["run_id"] == record["id"] for line in starts + finishes)
    succeeded = [line for line in finishes if line["outcome"] == "succeeded"]
    assert succeeded and all(
        isinstance(line["input_tokens"], int) and isinstance(line["output_tokens"], int)
        for line in succeeded
    ), "a successful finish line without token counts answers nothing"
    assert {line.get("module_id") for line in starts} >= {"CP-1"}

    reserved, reconciled = of(logs, "budget.reserved"), of(logs, "budget.reconciled")
    assert reserved and reconciled
    assert all(line["run_id"] == record["id"] for line in reserved + reconciled)
    assert all(isinstance(line["used"], dict) for line in reconciled), \
        "reconciliation carries the running totals, or 'what has it spent' needs a database"


async def test_a_retry_closes_every_started_provider_attempt(logs):
    """A completed timeout is not a call that is still in flight. Every start
    gets one finish, including the attempt that triggered the one allowed retry."""
    from caos.engine.loop import ProviderSlots, run_agent_module
    from caos.engine.provider import ProviderBlock, ProviderMessage, ProviderUsage

    class TimeoutThenSuccess:
        attempts = 0

        def count_tokens(self, _request):
            return 1

        def create_message(self, _request):
            self.attempts += 1
            if self.attempts == 1:
                raise TimeoutError("first attempt timed out")
            return ProviderMessage(
                content=[ProviderBlock(type="text", text="{}")],
                stop_reason="end_turn",
                usage=ProviderUsage(input_tokens=1, output_tokens=1),
                request_id="req-retry-success",
            )

    result = await run_agent_module(
        provider=TimeoutThenSuccess(), system="system", user="user", schema={}, max_tokens=1,
        read_evidence=lambda *_args: [], validate=lambda decoded: decoded,
        reserve=lambda *_args: None, reconcile=lambda *_args: None,
        record=lambda *_args, **_kwargs: None, slots=ProviderSlots(1),
    )

    assert result == {}
    starts = of(logs, "provider.call.start")
    finishes = of(logs, "provider.call.finish")
    assert starts and len(starts) == len(finishes)
    assert {line["outcome"] for line in finishes} == {"succeeded", "timeout"}


async def test_a_denied_provider_slot_logs_no_call_that_never_happened(build_engine, store, logs):
    """`start` with no `finish` has to mean one thing: a call that is still out.

    The concurrency slot (§12.19) denies without calling anything. Logging the
    start before acquiring it would put an unfinished call in the log for every
    denial, which is exactly the shape an operator greps for to find a hung run.
    """
    from caos.engine.loop import ProviderSlots

    class NeverReturnsTheSlot(ProviderSlots):
        """One slot, never released: the token count takes it and the create is
        denied by the real `acquire_or_deny`, with the real typed error."""

        def __init__(self) -> None:
            super().__init__(1)

        def release(self) -> None:
            pass

    case = store.create_case("Northwind", "Northwind Holdings", "Services", "analyst")
    pinned = ingest_sentinel_document(store, case["id"])
    provider = ReadingProvider(pinned["id"])
    engine = build_engine(provider)
    engine._slots = NeverReturnsTheSlot()
    run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst")
    await engine.wait(run["id"])

    record = engine.get_run(run["id"])
    assert record["status"] == "failed"
    assert record["error"]["code"] == "AGENT_BUDGET_EXCEEDED"
    assert provider.create_requests == [], "the provider was never called"
    assert not of(logs, "provider.call.start"), "so no call may be reported as started"
    assert any(line["code"] == "AGENT_BUDGET_EXCEEDED" for line in of(logs, "refusal"))


async def test_the_gate_interrupt_is_logged_when_raised_and_when_resolved(build_engine, store, logs):
    """A run parked on an empty source set is the commonest stuck run there is."""
    case = store.create_case("Northwind", "Northwind Holdings", "Services", "analyst")
    engine = build_engine(None)
    run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst")

    assert engine.get_run(run["id"])["status"] == "paused"
    raised = of(logs, "gate.interrupt")
    assert raised and raised[0]["run_id"] == run["id"]
    assert raised[0]["reason"] == "SOURCE_SET_EMPTY"
    assert not of(logs, "gate.resolved"), "nothing has resolved it yet"

    ingest_sentinel_document(store, case["id"])
    await engine.resume(run["id"])
    await engine.wait(run["id"])

    resolved = of(logs, "gate.resolved")
    assert resolved and resolved[0]["run_id"] == run["id"]
    assert SENTINEL not in logs.getvalue()


async def test_startup_recovery_is_logged(build_engine, store, logs):
    """A restart that silently re-admits runs is a restart you cannot audit."""
    case = store.create_case("Northwind", "Northwind Holdings", "Services", "analyst")
    ingest_sentinel_document(store, case["id"])
    engine = build_engine(None)
    run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst")

    logs.truncate(0), logs.seek(0)
    await engine.recover()

    started = of(logs, "recovery.started")
    assert started and isinstance(started[0]["runs"], int)
    assert any(line["run_id"] == run["id"] for line in of(logs, "recovery.run"))


# --- the wire format --------------------------------------------------------------


@pytest.fixture()
def restored_logger():
    """configure_logging() replaces the caos logger's handlers; nothing else in
    the suite should inherit a handler bound to a closed capture buffer."""
    from caos.observability import LOGGER_NAME

    logger = logging.getLogger(LOGGER_NAME)
    saved = (list(logger.handlers), logger.level, logger.propagate)
    try:
        yield logger
    finally:
        logger.handlers[:], logger.level, logger.propagate = saved


def test_every_log_line_is_one_json_object_on_stdout(capsys, restored_logger):
    """Structured JSON on stdout, stdlib logging, no dependency."""
    from caos.observability import configure_logging, log_event

    configure_logging()
    log_event("run.created", run_id="run-1", pathway="FULL_CREDIT")
    log_event("run.succeeded", run_id="run-1")

    captured = capsys.readouterr()
    assert captured.out.strip(), "logs go to stdout"
    rendered = [json.loads(line) for line in captured.out.strip().splitlines()]
    assert [line["event"] for line in rendered] == ["run.created", "run.succeeded"]
    for line in rendered:
        assert line["run_id"] == "run-1"
        assert line["level"] == "INFO" and isinstance(line["ts"], str)


def test_a_field_that_is_absent_is_omitted_rather_than_null():
    """Log lines are grepped, not schema-validated; a null run_id reads as a
    run whose id is null."""
    from caos.observability import log_event

    buffer = _capture(lambda: log_event("recovery.started", runs=0, run_id=None))
    assert "run_id" not in json.loads(buffer)


# --- secret redaction -------------------------------------------------------------


def test_registered_secrets_are_redacted_from_every_string_that_reaches_a_log_line():
    from caos.observability import redact, register_secrets

    register_secrets("sk-ant-notarealkey-abcdefghijklmnop", "s" * 40)
    buffer = _capture(lambda: _log_secret_bearing_failure())
    assert "sk-ant-notarealkey-abcdefghijklmnop" not in buffer
    assert "s" * 40 not in buffer
    assert "***" in buffer

    # The pattern backstop covers a secret nobody registered.
    assert "sk-or-v1-neverregistered0000000" not in redact(
        "401 from https://api/x (Authorization: Bearer sk-or-v1-neverregistered0000000)"
    )
    assert redact("postgresql://caos:hunter2plaintext@db:5432/caos").count("hunter2plaintext") == 0


def test_registered_secrets_are_redacted_from_nested_dictionary_keys():
    from caos.observability import log_event, register_secrets

    secret = "sk-ant-dictionary-key-abcdefghijklmnop"
    register_secrets(secret)
    buffer = _capture(lambda: log_event("probe", nested={secret: "safe"}))

    assert secret not in buffer
    assert "***" in buffer


def test_worker_failure_logs_the_exception_type_but_never_its_message(logs):
    import worker

    class Builds:
        def queued_work(self):
            return {"builds": ["mdl-content-leak"], "exports": []}

        def update_build(self, *_args, **_kwargs):
            return True

    class BrokenService:
        builds = Builds()

        def build(self, _build_id):
            return {"input_fingerprint": "f" * 64}

        def run_build(self, _build_id):
            raise ValueError(SENTINEL)

    assert worker.run_pending(BrokenService()) == 1
    failures = of(logs, "worker.job_failed")
    assert failures and failures[0]["detail"] == "ValueError"
    assert SENTINEL not in logs.getvalue()


def test_configure_logging_registers_the_settings_secrets(restored_logger):
    from caos.config import Settings
    from caos.observability import configure_logging, redact

    settings = Settings(anthropic_api_key="sk-ant-config-registered-key-000",
                        openrouter_api_key="sk-or-config-registered-key-000",
                        edge_proxy_secret="e" * 44, session_secret="z" * 44)
    configure_logging(settings)
    for secret in (settings.anthropic_api_key, settings.openrouter_api_key,
                   settings.edge_proxy_secret, settings.session_secret):
        assert secret not in redact(f"boom: {secret}")


def _log_secret_bearing_failure() -> None:
    from caos.observability import log_event

    log_event(
        "worker.job_failed",
        detail="AuthenticationError: bad key sk-ant-notarealkey-abcdefghijklmnop",
        session=("s" * 40),
    )


def _capture(emit) -> str:
    from caos.observability import LOGGER_NAME, JsonFormatter

    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(LOGGER_NAME)
    logger.addHandler(handler)
    previous = logger.level
    logger.setLevel(logging.DEBUG)
    try:
        emit()
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)
    return buffer.getvalue()


# --- readiness --------------------------------------------------------------------


def test_readiness_actually_checks_store_bundle_and_checkpointer(engine):
    checks = engine.readiness()
    assert checks == {"store": True, "bundle": True, "checkpointer": True}


def test_a_checkpoint_database_with_a_stuck_writer_is_not_ready(engine):
    """Readiness cannot distinguish a healthy brief writer from a wedged one,
    so it waits briefly and fails closed if the lock still cannot be acquired."""
    import sqlite3

    engine.readiness()  # materialise the checkpoint file
    holder = sqlite3.connect(str(engine.checkpoint_path))
    holder.execute("BEGIN IMMEDIATE")
    try:
        engine._readiness = None  # the window's cache would hide the probe
        assert engine.readiness()["checkpointer"] is False
    finally:
        holder.rollback()
        holder.close()


def test_a_malformed_checkpoint_schema_is_not_ready(engine):
    import sqlite3

    conn = sqlite3.connect(str(engine.checkpoint_path))
    conn.execute("CREATE TABLE checkpoints(bad TEXT)")
    conn.commit()
    conn.close()

    assert engine.readiness()["checkpointer"] is False


def test_health_serves_the_readiness_checks_on_the_strict_wire_model(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "store": True, "bundle": True, "checkpointer": True}


def test_readiness_is_rechecked_continuously_but_bounded_for_anonymous_callers(engine):
    """/api/health skips oauth2-proxy auth AND the rate ceiling, so its cost is
    an anonymous caller's to spend. Hashing 307 bundle files per request is a
    lever; one window's worth is not."""
    from caos.engine.runtime import READINESS_TTL_SECONDS

    verified: list[int] = []
    real = engine.bundle.verify

    class Counting:
        build_id = engine.bundle.build_id

        def verify(self):
            verified.append(1)
            return real()

    engine.bundle = Counting()
    with engine.fake_clock_for_tests() as clock:
        assert all(engine.readiness().values())
        for _ in range(20):
            engine.readiness()
        assert verified == [1], "a burst inside the window costs one verification"
        clock.advance(READINESS_TTL_SECONDS + 0.1)
        assert all(engine.readiness().values())
        assert verified == [1, 1], "and the next window re-probes for real"


def test_concurrent_readiness_requests_share_one_probe_window(engine):
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    verified: list[int] = []
    real = engine.bundle.verify
    start = threading.Barrier(8)

    class SlowCounting:
        build_id = engine.bundle.build_id

        def verify(self):
            verified.append(1)
            time.sleep(0.05)
            return real()

    engine.bundle = SlowCounting()
    engine._readiness = None

    def ready(_index):
        start.wait()
        return engine.readiness()

    with ThreadPoolExecutor(max_workers=8) as workers:
        results = list(workers.map(ready, range(8)))

    assert all(all(result.values()) for result in results)
    assert verified == [1], "one concurrent burst must pay for one probe, not one per thread"


def test_health_reports_degraded_when_the_app_has_no_engine(settings, store):
    """`create_app(..., engine=None)` is a real assembly. The one route that
    answers before authentication must not 500 on it."""
    from fastapi.testclient import TestClient

    from caos.api import create_app

    client = TestClient(create_app(settings=settings, store=store, engine=None),
                        raise_server_exceptions=False)
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "store": False, "bundle": False,
                               "checkpointer": False}


def test_health_fails_closed_when_the_bundle_no_longer_verifies(client, engine):
    """A bundle that does not verify is invariant 4's failure mode. Readiness
    that answers 'ok' anyway is worse than no readiness at all."""
    from caos.methodology.bundle import MethodologyError

    class Tampered:
        build_id = "tampered"

        def verify(self):
            raise MethodologyError("Deploy V integrity mismatch: ['changed:x/y.md']")

    engine.bundle = Tampered()
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "store": True, "bundle": False, "checkpointer": True}


def test_health_fails_closed_when_the_store_is_unreachable(client, engine, store):
    """A probe that raises is a 500, which tells an operator nothing about which
    subsystem died. The check has to catch its own failure and report it."""
    import sqlalchemy as sa

    store.engine.dispose()
    # A database file in a directory that does not exist: SQLite refuses to open
    # it, which is as close to "store unreachable" as SQLite gets.
    store.engine = sa.create_engine("sqlite:////nonexistent-caos-dir-zqxjv/caos.db")

    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "store": False, "bundle": True,
                               "checkpointer": True}
