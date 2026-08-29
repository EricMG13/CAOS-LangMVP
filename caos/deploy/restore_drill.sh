#!/usr/bin/env bash
# Restores an age-encrypted backup pair into a throwaway database and volume.
# The identity (private key) is supplied by the operator at drill time and must
# not live on the backup host — see backup.sh for the key-handling policy.
# Ciphertext is decrypted straight into pg_restore and tar, so the plaintext
# corpus never lands on this disk.
# bash, not sh: these scripts now pipe through age, and POSIX sh has no
# pipefail. Without it `pg_dump | age` reports age's status — a failed dump
# would still yield a VALID encryption of zero bytes that `test -s` accepts,
# i.e. a "successful" backup of nothing. Same hazard on the restore side.
set -euo pipefail
dump_path="${1:?dump path required}"
identity="${CAOS_BACKUP_IDENTITY:?CAOS_BACKUP_IDENTITY (age identity file) required to decrypt the backup}"
test -s "$dump_path"
test -s "$identity"
command -v age >/dev/null 2>&1 || {
    echo "age is required to decrypt the backup: https://github.com/FiloSottile/age" >&2
    exit 69
}
dump_dir=$(CDPATH= cd -- "$(dirname -- "$dump_path")" && pwd)
vault_archive=${2:-$dump_dir/vault.tgz.age}
test -s "$vault_archive"
standard_pair=0
if [ "$(basename -- "$dump_path")" = "caos.dump.age" ] && [ "$(basename -- "$vault_archive")" = "vault.tgz.age" ] && [ "$(CDPATH= cd -- "$(dirname -- "$vault_archive")" && pwd)" = "$dump_dir" ]; then
    standard_pair=1
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
drill_db=${RESTORE_DRILL_DB:-caos_restore_drill}
drill_volume=${RESTORE_DRILL_VOLUME:-caos_restore_vault}
is_safe_name() {
    case "$1" in
        *[!A-Za-z0-9_-]*) return 1 ;;
        *) return 0 ;;
    esac
}
case "$drill_db" in
    caos_restore_drill|caos_restore_drill_*)
        is_safe_name "$drill_db" || {
            echo "RESTORE_DRILL_DB must contain only safe name characters" >&2
            exit 2
        }
        ;;
    * )
        echo "RESTORE_DRILL_DB must be a safe isolated database name" >&2
        exit 2
        ;;
esac
case "$drill_volume" in
    caos_restore_vault|caos_restore_vault_*)
        is_safe_name "$drill_volume" || {
            echo "RESTORE_DRILL_VOLUME must contain only safe name characters" >&2
            exit 2
        }
        ;;
    * )
        echo "RESTORE_DRILL_VOLUME must be a safe isolated volume name" >&2
        exit 2
        ;;
esac

compose() {
    docker compose -f "$script_dir/docker-compose.yml" "$@"
}

if docker volume inspect "$drill_volume" >/dev/null 2>&1; then
    echo "RESTORE_DRILL_VOLUME must not already exist" >&2
    exit 2
fi
if ! existing_db=$(compose exec -T db psql -Atq -U caos -d postgres -c "SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = '$drill_db');"); then
    echo "could not verify RESTORE_DRILL_DB" >&2
    exit 2
fi
case "$existing_db" in
    f) ;;
    t)
        echo "RESTORE_DRILL_DB must not already exist" >&2
        exit 2
        ;;
    *)
        echo "could not verify RESTORE_DRILL_DB" >&2
        exit 2
        ;;
esac

if [ "$standard_pair" -eq 1 ]; then
    manifest="$dump_dir/caos.backup.manifest"
    if ! test -s "$manifest"; then
        echo "standard backup pair requires caos.backup.manifest" >&2
        exit 2
    fi
    expected_dump=$(sed -n 's/^caos\.dump\.age //p' "$manifest")
    expected_vault=$(sed -n 's/^vault\.tgz\.age //p' "$manifest")
    # A corruption pre-check only. Authenticity comes from age itself: a tampered
    # archive fails to decrypt, which is the check an attacker who can rewrite
    # the manifest beside the data cannot forge.
    if [ "$expected_dump" != "$(sha256sum < "$dump_path" | cut -d ' ' -f 1)" ] \
        || [ "$expected_vault" != "$(sha256sum < "$vault_archive" | cut -d ' ' -f 1)" ]; then
        echo "backup manifest does not match dump and vault pair" >&2
        exit 2
    fi
fi

volume_created=0
db_created=0
drill_token="$(date +%s)-$$"
cleanup() {
    if [ "$db_created" -eq 1 ]; then
        compose exec -T db dropdb -U caos --if-exists "$drill_db" >/dev/null 2>&1 || true
    fi
    if [ "$volume_created" -eq 1 ]; then
        docker volume rm "$drill_volume" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

docker volume create "$drill_volume" >/dev/null
docker run --rm -v "$drill_volume:/vault" alpine:3.20@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc sh -c 'set -C; printf "%s\\n" "$1" > /vault/.caos-restore-drill-owner' sh "$drill_token"
volume_created=1
age -d -i "$identity" "$vault_archive" | docker run --rm -i -v "$drill_volume:/vault" alpine:3.20@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc tar -xzf - -C /vault
docker run --rm -v "$drill_volume:/vault:ro" alpine:3.20@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc sh -c 'test -n "$(find /vault -mindepth 1 -maxdepth 1 -print -quit)"'
compose exec -T db createdb -U caos "$drill_db"
db_created=1
age -d -i "$identity" "$dump_path" | compose exec -T db pg_restore --exit-on-error --no-owner --no-acl -U caos -d "$drill_db"
# Schema note: these assertions verify the CURRENT store. They previously named
# caos_state and model_build_jobs, which belong to the PREDECESSOR schema — the
# drill was never updated when the store migrated, so it could not pass against
# a backup of this system.
#
# The deliverable tables are deliberately NOT asserted. DeliverableService is
# constructed lazily inside a request handler, so a live database that has never
# served that surface simply does not have them, and requiring one rejects a
# perfectly good backup — observed on a real deployment: 20 tables, no
# deliverable_frozen. Checking them conditionally is not worth it either:
# PL/pgSQL plans the whole IF expression, so even a guarded reference to an
# absent table fails at parse time, and the dynamic SQL that would avoid that
# does not belong inside a shell-embedded one-liner.
compose exec -T db psql -v ON_ERROR_STOP=1 -U caos -d "$drill_db" -c "DO \$\$ BEGIN IF to_regclass('public.cases') IS NULL OR to_regclass('public.sources') IS NULL OR to_regclass('public.source_sets') IS NULL OR to_regclass('public.audit_events') IS NULL OR to_regclass('public.runs') IS NULL OR to_regclass('public.run_artifacts') IS NULL OR to_regclass('public.run_events') IS NULL OR to_regclass('public.model_builds') IS NULL OR to_regclass('public.model_revisions') IS NULL THEN RAISE EXCEPTION 'required restored tables are missing'; END IF; IF EXISTS (SELECT 1 FROM model_builds WHERE status = 'READY' AND (json_typeof(payload) IS DISTINCT FROM 'object' OR payload_digest IS NULL OR payload_digest !~ '^[0-9a-f]{64}\$')) THEN RAISE EXCEPTION 'restored model build metadata is invalid'; END IF; IF EXISTS (SELECT 1 FROM model_builds WHERE export #>> '{status}' = 'READY' AND (export #>> '{vault_key}' IS NULL OR export #>> '{vault_key}' !~ '^models/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/[0-9a-f]{64}\\.xlsx\$' OR export #>> '{sha256}' !~ '^[0-9a-f]{64}\$' OR export #>> '{size}' !~ '^[0-9]+\$')) THEN RAISE EXCEPTION 'restored model export metadata is invalid'; END IF; IF EXISTS (SELECT 1 FROM run_artifacts WHERE digest !~ '^[0-9a-f]{64}\$') THEN RAISE EXCEPTION 'restored run artifact digests are malformed'; END IF; END \$\$;"
model_payloads=$(compose exec -T db psql -Atq -F '|' -v ON_ERROR_STOP=1 -U caos -d "$drill_db" -c "SELECT payload_digest, payload FROM model_builds WHERE status='READY' ORDER BY id;")
# `run --rm`, not `exec`: the drill must work when the app service is STOPPED,
# which is exactly when it is most needed — a restore rehearsal during a
# maintenance window, or a real restore after an outage. `exec` requires a
# running container and fails with "service app is not running".
printf '%s\n' "$model_payloads" | compose run --rm -T --no-deps --entrypoint python app -c '
import hashlib, json, sys
for line in sys.stdin:
    if not line.strip():
        continue
    expected, raw = line.rstrip("\n").split("|", 1)
    canonical = json.dumps(json.loads(raw), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != expected:
        raise SystemExit("restored model payload digest mismatch")
'
model_exports=$(compose exec -T db psql -Atq -F '|' -v ON_ERROR_STOP=1 -U caos -d "$drill_db" -c "SELECT id, export #>> '{vault_key}', export #>> '{sha256}', export #>> '{size}' FROM model_builds WHERE export #>> '{status}' = 'READY' ORDER BY id;")
printf '%s\n' "$model_exports" | docker run --rm -i -v "$drill_volume:/vault:ro" alpine:3.20@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc sh -c '
set -eu
while IFS="|" read -r build_id vault_key expected_sha expected_size; do
    [ -n "$build_id" ] || continue
    case "$vault_key" in
        models/*/*/"$expected_sha".xlsx) ;;
        *) echo "invalid restored model export key for $build_id" >&2; exit 1 ;;
    esac
    path="/vault/$vault_key"
    test -f "$path"
    actual_size=$(wc -c < "$path" | tr -d "[:space:]")
    [ "$actual_size" = "$expected_size" ]
    actual_sha=$(sha256sum "$path" | cut -d " " -f 1)
    [ "$actual_sha" = "$expected_sha" ]
done
'
echo "restore drill passed for isolated database $drill_db"
