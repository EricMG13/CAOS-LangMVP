"""Bounded, cached scanner readiness; uploads still scan every byte themselves."""

from __future__ import annotations

import socket
import threading
import time
from concurrent.futures import Future, TimeoutError
from typing import Literal

from ..config import Settings

ScannerStatus = Literal["ready", "unavailable", "not_required"]
SCANNER_PROBE_SECONDS = 1.0
SCANNER_TTL_SECONDS = 5.0


class ScannerReadiness:
    def __init__(self, settings: Settings) -> None:
        self._required = settings.environment == "production"
        self._address = (settings.clamav_host, settings.clamav_port)
        self._lock = threading.Lock()
        self._pending: Future[ScannerStatus] | None = None
        self._expires = 0.0
        self._status: ScannerStatus = "unavailable"

    def status(self) -> ScannerStatus:
        if not self._required:
            return "not_required"
        if not self._address[0]:
            return "unavailable"
        with self._lock:
            if time.monotonic() < self._expires:
                return self._status
            # socket timeouts do not bound DNS. One outstanding daemon thread
            # bounds the caller and resource use even while name resolution hangs.
            if self._pending is None or self._pending.done():
                self._pending = Future()
                threading.Thread(target=self._probe, args=(self._pending,), daemon=True).start()
            try:
                self._status = self._pending.result(timeout=SCANNER_PROBE_SECONDS)
            except TimeoutError:
                self._status = "unavailable"
            self._expires = time.monotonic() + SCANNER_TTL_SECONDS
            return self._status

    def _probe(self, result: Future[ScannerStatus]) -> None:
        status: ScannerStatus = "unavailable"
        deadline = time.monotonic() + SCANNER_PROBE_SECONDS
        try:
            with socket.create_connection(self._address, timeout=SCANNER_PROBE_SECONDS) as connection:
                connection.sendall(b"zPING\0")
                response = b""
                while len(response) < len(b"PONG\0"):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    connection.settimeout(remaining)
                    chunk = connection.recv(len(b"PONG\0") - len(response))
                    if not chunk:
                        break
                    response += chunk
                if response == b"PONG\0":
                    status = "ready"
        except OSError:
            pass
        result.set_result(status)
