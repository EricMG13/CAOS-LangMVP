"""Exclusive operating-system lock over the durable checkpoint location.

Run checkpoints are SQLite on the data volume (run.py), so the checkpoint
file, not the domain database, is the resource a second application instance
would corrupt: two engines driving one thread from one file break invariant 6
in ways no database lock can see. The app entrypoints therefore take an
exclusive `flock` on a sidecar next to the checkpoint file before startup
recovery runs and before any socket is bound; a second instance fails with
`INSTANCE_ALREADY_RUNNING` while the first still holds it, and the kernel
releases the lock when the holder exits however it exits. The PostgreSQL
advisory lock (store.single_instance) stays as the database-side guard for the
app and worker roles; this one also covers SQLite development and the
checkpoint volume itself. Proven by a second process in
caos/tests/test_single_instance.py (ENTERPRISE_READINESS_PLAN Phase 5 item 10).

`flock` is per open file description, so even a second acquisition inside one
process is refused. Not Windows; the deployment is Linux and development is
macOS. A network filesystem that ignores `flock` would silently weaken this —
the checkpoint volume is a local Docker volume by design.
"""

from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class InstanceAlreadyRunning(RuntimeError):
    code = "INSTANCE_ALREADY_RUNNING"

    def __init__(self, lock_path: Path) -> None:
        super().__init__(
            f"{self.code}: another CAOS application instance holds the checkpoint location {lock_path}"
        )
        self.lock_path = lock_path


def lock_path_for(checkpoint_path: Path) -> Path:
    return checkpoint_path.with_name(checkpoint_path.name + ".lock")


@contextmanager
def checkpoint_lock(checkpoint_path: Path) -> Iterator[Path]:
    """Hold the exclusive lock over `checkpoint_path`'s location for the block.

    The sidecar records the holder's PID for an operator; it is informational
    only, the kernel lock is the authority."""
    lock_path = lock_path_for(Path(checkpoint_path))
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise InstanceAlreadyRunning(lock_path) from exc
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()}\n".encode("ascii"))
        yield lock_path
    finally:
        os.close(fd)
