#!/usr/bin/env bash
# Encrypted backup of the domain database and the vault.
#
# Both artifacts are the complete confidential credit corpus, so neither leaves
# this host in the clear. Encryption is age (ChaCha20-Poly1305): it gives
# confidentiality AND authenticity in one pass — a tampered archive fails to
# decrypt rather than restoring silently, which an unkeyed checksum beside the
# data could never detect, because an attacker who can rewrite one can rewrite
# both. The manifest's SHA-256 is a cheap corruption pre-check, not the
# authenticity control.
#
# Operator requirements (NOT enforceable from this script — treat as policy):
#   * CAOS_BACKUP_RECIPIENT is an age public key. The matching IDENTITY (private
#     key) must be stored somewhere this host cannot read — a password manager,
#     an HSM, or a KMS-wrapped secret. A backup host holding its own restore key
#     protects against disk theft and nothing else.
#   * Rotate the recipient key at least annually and after any operator
#     offboarding. Old backups stay readable by the old identity, so retire
#     ciphertext and identity together.
#   * Retention and destination ACLs belong to the storage layer. Write access
#     to the backup destination is equivalent to a denial-of-restore, so keep it
#     append-only where the destination supports it, and log every read.
#   * Restore authorization is a two-person action: reconstructing the corpus in
#     a new location is the same disclosure as exfiltrating it.
#   * Exercise restore_drill.sh on a real backup on a schedule. An untested
#     backup is a belief, not a control.
# bash, not sh: these scripts now pipe through age, and POSIX sh has no
# pipefail. Without it `pg_dump | age` reports age's status — a failed dump
# would still yield a VALID encryption of zero bytes that `test -s` accepts,
# i.e. a "successful" backup of nothing. Same hazard on the restore side.
set -euo pipefail
umask 077
out="${1:?backup destination required}"
recipient="${CAOS_BACKUP_RECIPIENT:?CAOS_BACKUP_RECIPIENT (age public key) required — backups are never written in the clear}"
command -v age >/dev/null 2>&1 || {
    echo "age is required on the backup host: https://github.com/FiloSottile/age" >&2
    exit 69
}
mkdir -p "$out"
out_path=$(CDPATH= cd -- "$out" && pwd)
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
lock_dir="$out/.caos-backup.lock"
if ! mkdir "$lock_dir"; then
    echo "backup already running or lock requires operator review: $lock_dir" >&2
    exit 75
fi
dump_tmp=""
vault_tmp=""
manifest_tmp=""
cleanup() {
    rm -f -- "$dump_tmp" "$vault_tmp" "$manifest_tmp"
    rmdir "$lock_dir" 2>/dev/null || true
}
trap cleanup EXIT
dump_tmp=$(mktemp "$out/.caos.dump.age.XXXXXX")
compose() {
    docker compose -f "$script_dir/docker-compose.yml" "$@"
}
# Piped straight into age: the plaintext dump is never a file on this disk.
compose exec -T db pg_dump -U caos -d caos --format=custom | age -r "$recipient" -o "$dump_tmp"
test -s "$dump_tmp"
project_name=${COMPOSE_PROJECT_NAME:-deploy}
vault_volume=$(docker volume ls -q --filter "label=com.docker.compose.project=$project_name" --filter "label=com.docker.compose.volume=vault-data" | head -n 1)
test -n "$vault_volume"
vault_tmp=$(mktemp "$out/.vault.tgz.age.XXXXXX")
docker run --rm -v "$vault_volume:/vault:ro" alpine:3.20@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc tar -C /vault -czf - . | age -r "$recipient" -o "$vault_tmp"
test -s "$vault_tmp"
manifest_tmp=$(mktemp "$out/.caos.backup.manifest.XXXXXX")
{
    printf 'recipient %s\n' "$recipient"
    printf 'caos.dump.age %s\n' "$(sha256sum < "$dump_tmp" | cut -d ' ' -f 1)"
    printf 'vault.tgz.age %s\n' "$(sha256sum < "$vault_tmp" | cut -d ' ' -f 1)"
} > "$manifest_tmp"
mv -f -- "$dump_tmp" "$out/caos.dump.age"
mv -f -- "$vault_tmp" "$out/vault.tgz.age"
mv -f -- "$manifest_tmp" "$out/caos.backup.manifest"
echo "encrypted backup written to $out_path (recipient $recipient)"
