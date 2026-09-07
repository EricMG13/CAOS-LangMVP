from __future__ import annotations

import os
import shlex
import signal
import subprocess
import time
from pathlib import Path

import pytest
import yaml

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"


@pytest.mark.parametrize("state", ["Z", "X", "missing"])
def test_supervisor_exits_when_clamd_dies_even_if_initializer_survives(tmp_path, state):
    # Linux's /proc shape is represented here so the process-supervisor check
    # runs on macOS too. The real-image recovery drill separately kills clamd.
    proc = tmp_path / "proc" / "12345"
    proc.mkdir(parents=True)
    status = proc / "stat"
    status.write_text("12345 (clamd) S 1 2 3\n")
    marker = tmp_path / "observed"
    pgrep = tmp_path / "pgrep"
    pgrep.write_text(f"#!/bin/sh\necho probed >> {shlex.quote(str(marker))}\necho 12345\n")
    pgrep.chmod(0o700)
    initializer = tmp_path / "init.sh"
    initializer.write_text("exec /bin/sleep 30\n")
    script = tmp_path / "supervise.sh"
    script.write_text((DEPLOY / "clamav-supervise.sh").read_text()
                      .replace("/bin/sh /init", f"/bin/sh {shlex.quote(str(initializer))}")
                      .replace('"/proc/', f'"{tmp_path}/proc/'))
    process = subprocess.Popen(
        ["/bin/sh", str(script)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"}, start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 3
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert marker.exists(), "the initializer and live daemon were observed"
        if state == "missing":
            status.unlink()
        else:
            status.write_text(f"12345 (clamd) {state} 1 2 3\n")
        _, stderr = process.communicate(timeout=3)
        assert process.returncode == 1
        assert "daemon exited" in stderr
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=3)


def test_compose_preserves_stock_initializer_and_budgets_reload_memory():
    service = yaml.safe_load((DEPLOY / "docker-compose.yml").read_text())["services"]["clamav"]
    assert service["restart"] == "unless-stopped"
    assert service["entrypoint"] == ["/sbin/tini", "-g", "--", "/bin/sh", "/etc/clamav/caos-supervise.sh"]
    assert "./clamav-supervise.sh:/etc/clamav/caos-supervise.sh:ro" in service["volumes"]
    assert service["mem_limit"] == "${CLAMAV_MEMORY_LIMIT:-4g}"
    script = (DEPLOY / "clamav-supervise.sh").read_text()
    assert "/bin/sh /init &" in script
    assert "clamdscan" not in script, "a busy scanner is unready, not a dead daemon"
