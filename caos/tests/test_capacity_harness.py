"""The capacity harness must survive the declared profile it drives (PERF-013).

Candidate 2026-09-03-c4f0270 showed the harness destroying its own workload
against a correctly refusing application: every job driver died on the first
429 from the per-subject bucket, the stream holders reopened a closed stream
in a tight loop and drained that bucket, the sampler crashed on a 429 body,
and the seeded "100 documents" were 21 distinct files. These tests pin the
repaired behaviour with a fake transport; no server is involved.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from qa import capacity  # noqa: E402

WHO = capacity.headers("capacity-test")


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(capacity.time, "sleep", lambda _seconds: None)


def _client(handler) -> httpx.Client:
    return httpx.Client(base_url="http://harness.invalid", transport=httpx.MockTransport(handler))


def test_wait_terminal_retries_the_bucket_refusal_then_returns_the_terminal_run():
    answers = iter([429, 429, 200])

    def handler(request: httpx.Request) -> httpx.Response:
        status = next(answers)
        body = {"detail": "request rate ceiling reached"} if status == 429 else {"id": "run-1", "status": "succeeded"}
        return httpx.Response(status, json=body)

    run = capacity.wait_terminal(_client(handler), WHO, "run-1", timeout=30.0)
    assert run["status"] == "succeeded"


def test_wait_terminal_survives_a_transport_failure_between_polls():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadError("Bad file descriptor", request=request)
        return httpx.Response(200, json={"id": "run-1", "status": "failed", "error": {"code": "AGENT_BUDGET_EXCEEDED"}})

    run = capacity.wait_terminal(_client(handler), WHO, "run-1", timeout=30.0)
    assert run["status"] == "failed"
    assert calls["n"] == 2


def test_wait_terminal_still_refuses_a_run_the_subject_cannot_read():
    with pytest.raises(RuntimeError, match="unreadable for this subject: 404"):
        capacity.wait_terminal(_client(lambda request: httpx.Response(404, json={"detail": "not found"})), WHO, "run-x", timeout=30.0)


def test_drive_once_records_a_refused_start_and_a_dead_transport_instead_of_raising():
    watch = capacity.Stopwatch()
    refused = _client(lambda request: httpx.Response(429, json={"detail": "request rate ceiling reached"}))
    capacity.drive_once(refused, WHO, "case-1", "FULL_CREDIT", "screen", watch, start_timeout=0.0)
    assert watch.summary()["start_run"]["statuses"] == {"429": 1}
    assert watch.summary()["driver_error"]["statuses"] == {"TimeoutError": 1}

    def dead(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    capacity.drive_once(_client(dead), WHO, "case-1", "FULL_CREDIT", "screen", watch, start_timeout=0.0)
    assert watch.summary()["start_run"]["statuses"]["ConnectError"] >= 1
    assert watch.summary()["driver_error"]["statuses"] == {"TimeoutError": 2}


def test_foreign_cases_ignores_a_refused_listing():
    assert capacity.foreign_cases({"detail": "request rate ceiling reached"}, {"case-1"}) is None
    assert capacity.foreign_cases([{"id": "case-1"}, {"id": "case-2"}], {"case-1"}) == {"case-2"}


def test_every_seeded_document_of_a_case_is_distinct():
    contents = {capacity.seed_document(7, document) for document in range(capacity.DECLARED["documents"])}
    assert len(contents) == capacity.DECLARED["documents"]
