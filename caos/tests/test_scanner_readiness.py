from __future__ import annotations

import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from caos.config import Settings
from caos.sources import health


@pytest.mark.parametrize("response, expected", [
    (b"PONG\0", "ready"), (b"PONG\n", "unavailable"),
    (b"PONG", "unavailable"), (b"ERROR", "unavailable"), (b"", "unavailable"),
])
def test_scanner_checks_the_real_ping_protocol(response, expected):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(2)
        commands = []

        def serve():
            with listener.accept()[0] as connection:
                connection.settimeout(2)
                commands.append(connection.recv(32))
                for byte in response:
                    connection.sendall(bytes([byte]))

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        readiness = health.ScannerReadiness(Settings(
            environment="production", clamav_host="127.0.0.1", clamav_port=listener.getsockname()[1],
        ))
        assert readiness.status() == expected
        thread.join(timeout=2)
        assert not thread.is_alive()
        assert commands == [b"zPING\0"]


def test_no_network_probe_for_development_or_unconfigured_production(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected scanner connection")

    monkeypatch.setattr(health.socket, "create_connection", forbidden)
    assert health.ScannerReadiness(Settings()).status() == "not_required"
    assert health.ScannerReadiness(Settings(environment="production")).status() == "unavailable"


def test_shared_ttl_caches_failures_and_rechecks_after_expiry(monkeypatch):
    now = [100.0]
    calls = []
    monkeypatch.setattr(health, "time", SimpleNamespace(monotonic=lambda: now[0]))

    def unreachable(*args, **kwargs):
        calls.append(args)
        raise OSError("private scanner hostname or network detail")

    monkeypatch.setattr(health.socket, "create_connection", unreachable)
    readiness = health.ScannerReadiness(Settings(environment="production", clamav_host="scanner"))
    with ThreadPoolExecutor(max_workers=12) as pool:
        assert list(pool.map(lambda _: readiness.status(), range(24))) == ["unavailable"] * 24
    assert len(calls) == 1
    now[0] += health.SCANNER_TTL_SECONDS
    assert readiness.status() == "unavailable"
    assert len(calls) == 2


def test_hung_dns_has_a_caller_deadline_without_spawning_more_probes(monkeypatch):
    release = threading.Event()
    calls = []
    monkeypatch.setattr(health, "SCANNER_PROBE_SECONDS", 0.025)
    monkeypatch.setattr(health, "SCANNER_TTL_SECONDS", 0)

    def hung_dns(*args, **kwargs):
        calls.append(args)
        release.wait(2)
        raise OSError("name resolution failed")

    monkeypatch.setattr(health.socket, "create_connection", hung_dns)
    readiness = health.ScannerReadiness(Settings(environment="production", clamav_host="scanner"))
    started = time.monotonic()
    try:
        assert [readiness.status() for _ in range(3)] == ["unavailable"] * 3
        assert time.monotonic() - started < 0.5
        assert len(calls) == 1
    finally:
        release.set()
        assert readiness._pending is not None
        readiness._pending.result(timeout=2)
