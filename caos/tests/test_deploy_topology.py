"""Deployment topology and the backup/restore repairs (ENTERPRISE_READINESS_PLAN
Phase 5 items 11–12; RESTORE-DRILL-2026-08-30 F1, F2, F3; ETR-B10).

Compose must create exactly one app and one worker and the environment manifest
must record that ceiling; the restore drill and the CI boot check must assert
the schema the store really creates at startup (F1); `backup.sh` must resolve
the vault volume without Compose labels and never fail silently (F2), and must
capture both halves at one snapshot point with the writers paused (F3).

The backup script is exercised against a fake `docker` and a fake `age` on
PATH: every invocation is logged, scenarios are set through environment
variables, and the assertions are about what the script did (order of pause,
dump, tar, unpause; what it wrote; how it failed), not about Docker.
"""

from __future__ import annotations

import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
import yaml

REPO = Path(__file__).resolve().parents[2]
DEPLOY = REPO / "caos" / "deploy"
SERVER = REPO / "caos" / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

LAZY_TABLES_ONCE = {
    "model_builds", "model_revisions", "model_revision_heads", "deliverable_revisions",
    "deliverable_frozen", "deliverable_opinions", "deliverable_freeze_jobs",
    "deliverable_filing_receipts", "deliverable_threads",
}


def _startup_tables(tmp_path: Path) -> set[str]:
    """The tables a booted CAOS creates before it serves anything: the domain
    store (which now constructs the model and deliverable stores) plus the run
    store the Engine constructs."""
    from caos.storage.runs import RunStore
    from caos.storage.store import DomainStore

    store = DomainStore.from_url(f"sqlite:///{tmp_path / 'startup.db'}")
    try:
        RunStore(store.engine)
        return set(sa.inspect(store.engine).get_table_names())
    finally:
        store.close()


# --- F1: the drill and the boot check assert the startup schema ------------------------


def test_restore_drill_asserts_exactly_tables_the_store_creates_at_startup(tmp_path):
    script = (DEPLOY / "restore_drill.sh").read_text()
    required = set(re.findall(r"to_regclass\('public\.([a-z_]+)'\)", script))
    startup = _startup_tables(tmp_path)
    assert required, "the drill asserts a table set"
    assert required <= startup, f"the drill requires tables no fresh deployment has: {sorted(required - startup)}"
    assert LAZY_TABLES_ONCE - {"deliverable_threads"} <= required, \
        "the formerly lazy model and deliverable tables are asserted now that startup creates them"


def test_ci_boot_check_asserts_the_startup_schema(tmp_path):
    workflow = (REPO / ".github" / "workflows" / "ci.yml").read_text()
    match = re.search(r"unnest\(ARRAY\[([^\]]+)\]\)", workflow)
    assert match, "the image job's boot check lists the tables it expects"
    listed = set(re.findall(r"'([a-z_]+)'", match.group(1)))
    startup = _startup_tables(tmp_path)
    assert listed <= startup, sorted(listed - startup)
    assert LAZY_TABLES_ONCE <= listed, "the boot check proves the whole schema, not the eager half"


# --- item 11: one app, one worker, recorded ---------------------------------------------


def test_compose_creates_exactly_one_app_and_one_worker():
    compose = yaml.safe_load((DEPLOY / "docker-compose.yml").read_text())
    services = compose["services"]
    for name in ("app", "worker"):
        assert services[name]["deploy"]["replicas"] == 1, f"{name} must declare exactly one replica"
    builders = [name for name, service in services.items() if "build" in service]
    assert sorted(builders) == ["app", "worker"], "nothing else is built from the application image"
    vault_mounts = [name for name, service in services.items()
                    if any(str(volume).startswith("vault-data:") for volume in service.get("volumes", []))]
    assert sorted(vault_mounts) == ["app", "worker"], "only the two single-instance services touch the vault"
    assert "SINGLE-INSTANCE ONLY" in (DEPLOY / "docker-compose.yml").read_text()


def test_environment_manifest_records_the_single_instance_ceiling_and_the_snapshot_point():
    manifest = (DEPLOY / "ENVIRONMENT_MANIFEST.md").read_text()
    for phrase in (
        "| `app` | exactly 1 |", "| `worker` | exactly 1 |",
        "one application instance and one worker instance",
        "INSTANCE_ALREADY_RUNNING", "single_instance",
        "one snapshot point", "pauses the `app` and `worker` containers",
        "checkpoints.db-shm", "CAOS_VAULT_VOLUME", "Compose labels are", "never consulted",
        "docker compose down -v",
    ):
        assert phrase in manifest, f"the environment manifest must record: {phrase!r}"


# --- F2 and F3: backup.sh against a fake docker ---------------------------------------------

FAKE_DOCKER = r'''#!/usr/bin/env bash
printf '%s\n' "$*" >> "$FAKE_LOG"
if [ "$1" = compose ]; then
  shift
  if [ "$1" = -f ]; then shift 2; fi
  case "$1" in
    ps)
      shift; if [ "$1" = -q ]; then shift; fi
      for service in "$@"; do
        case "$service" in
          app) [ -n "${FAKE_APP_ID:-}" ] && echo "$FAKE_APP_ID" ;;
          worker) [ -n "${FAKE_WORKER_ID:-}" ] && echo "$FAKE_WORKER_ID" ;;
        esac
      done
      exit 0 ;;
    exec)
      if [ -n "${FAKE_PGDUMP_FAIL:-}" ]; then echo "pg_dump: could not connect" >&2; exit 1; fi
      printf 'PGDMP-fake-dump-bytes'; exit 0 ;;
  esac
  exit 1
fi
case "$1" in
  volume)
    case " ${FAKE_VOLUMES:-} " in
      *" $3 "*) echo "[]"; exit 0 ;;
      *) echo "Error: No such volume: $3" >&2; exit 1 ;;
    esac ;;
  inspect) printf '%s\n' "${FAKE_VAULT_VOLUME:-}"; exit 0 ;;
  pause|unpause) exit 0 ;;
  run) printf 'fake-tar-bytes'; exit 0 ;;
esac
exit 1
'''

FAKE_AGE = r'''#!/usr/bin/env bash
out=""
while [ $# -gt 0 ]; do
  case "$1" in -o) out="$2"; shift ;; esac
  shift
done
cat > "$out"
'''


@pytest.fixture()
def fake_bin(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("docker", FAKE_DOCKER), ("age", FAKE_AGE)):
        path = bin_dir / name
        path.write_text(body)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return bin_dir


def _run_backup(fake_bin: Path, tmp_path: Path, **scenario: str) -> tuple[subprocess.CompletedProcess, list[str], Path]:
    out = tmp_path / "backup-out"
    log = tmp_path / "docker-calls.log"
    env = {
        **{key: value for key, value in os.environ.items() if key not in {"CAOS_VAULT_VOLUME"}},
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "FAKE_LOG": str(log),
        "CAOS_BACKUP_RECIPIENT": "age1fakerecipientfortests0000000000000000000000000000000000",
        **scenario,
    }
    result = subprocess.run(["bash", str(DEPLOY / "backup.sh"), str(out)], env=env, capture_output=True, text=True)
    calls = log.read_text().splitlines() if log.exists() else []
    return result, calls, out


def _index(calls: list[str], needle: str) -> int:
    return next(index for index, call in enumerate(calls) if needle in call)


def test_backup_resolves_the_vault_from_the_app_mount_pauses_writers_and_captures_both_halves(fake_bin, tmp_path):
    result, calls, out = _run_backup(fake_bin, tmp_path, FAKE_APP_ID="app-1", FAKE_WORKER_ID="worker-1",
                                     FAKE_VAULT_VOLUME="restored_by_hand_vault")
    assert result.returncode == 0, result.stderr
    assert any("inspect --format" in call and "app-1" in call for call in calls), "the volume comes from the app's /vault mount"
    assert not any("--filter" in call and "label=" in call for call in calls), "Compose labels are never consulted (F2)"
    pause, dump, tar, unpause = (_index(calls, "pause app-1 worker-1"), _index(calls, "pg_dump"),
                                 _index(calls, "run --rm -v restored_by_hand_vault:/vault:ro"), _index(calls, "unpause app-1 worker-1"))
    assert pause < dump < tar < unpause, f"one snapshot point: writers paused around both captures (F3): {calls}"
    assert "--exclude=./checkpoints.db-shm" in calls[tar], "the regenerable shared-memory index is not archived"
    assert (out / "caos.dump.age").read_bytes() == b"PGDMP-fake-dump-bytes"
    assert (out / "vault.tgz.age").read_bytes() == b"fake-tar-bytes"
    manifest = (out / "caos.backup.manifest").read_text()
    assert "vault_volume restored_by_hand_vault" in manifest and "snapshot_point paused-writers" in manifest
    assert not (out / ".caos-backup.lock").exists(), "the lock is released"
    assert "restored_by_hand_vault" in result.stdout


def test_backup_fails_loudly_when_no_vault_volume_can_be_resolved(fake_bin, tmp_path):
    result, calls, out = _run_backup(fake_bin, tmp_path, FAKE_APP_ID="", FAKE_WORKER_ID="")
    assert result.returncode == 1
    assert "cannot resolve the vault volume" in result.stderr, "never a silent exit (F2)"
    assert not any("pause" in call for call in calls) and not any("pg_dump" in call for call in calls)
    assert not out.exists() or list(out.iterdir()) == [], "nothing partial is written"


def test_backup_fails_loudly_when_the_app_mounts_nothing_at_vault(fake_bin, tmp_path):
    result, calls, _out = _run_backup(fake_bin, tmp_path, FAKE_APP_ID="app-1", FAKE_VAULT_VOLUME="")
    assert result.returncode == 1 and "mounts no volume at /vault" in result.stderr
    assert not any("pg_dump" in call for call in calls)


def test_backup_uses_the_explicit_volume_when_the_app_is_down(fake_bin, tmp_path):
    result, calls, out = _run_backup(fake_bin, tmp_path, FAKE_APP_ID="", FAKE_WORKER_ID="",
                                     CAOS_VAULT_VOLUME="deploy_vault-data", FAKE_VOLUMES="deploy_vault-data")
    assert result.returncode == 0, result.stderr
    assert any(call == "volume inspect deploy_vault-data" for call in calls), "the override is verified, not trusted"
    assert not any(call.startswith("pause") for call in calls), "nothing to pause when no writer runs"
    assert (out / "caos.backup.manifest").exists()

    refused, _calls, _out = _run_backup(fake_bin, tmp_path / "second", CAOS_VAULT_VOLUME="missing_vault", FAKE_VOLUMES="")
    assert refused.returncode == 1 and "does not exist: missing_vault" in refused.stderr


def test_backup_unpauses_the_writers_and_leaves_no_files_when_the_dump_fails(fake_bin, tmp_path):
    result, calls, out = _run_backup(fake_bin, tmp_path, FAKE_APP_ID="app-1", FAKE_WORKER_ID="worker-1",
                                     FAKE_VAULT_VOLUME="vault", FAKE_PGDUMP_FAIL="1")
    assert result.returncode != 0
    assert calls.index("pause app-1 worker-1") < calls.index("unpause app-1 worker-1"), "the writers resume on the failure path"
    assert not any(name in {"caos.dump.age", "vault.tgz.age", "caos.backup.manifest"} for name in os.listdir(out)), \
        "a failed capture publishes nothing"
    assert not (out / ".caos-backup.lock").exists()
