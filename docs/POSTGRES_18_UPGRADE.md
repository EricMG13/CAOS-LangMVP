# PostgreSQL 17 → 18 upgrade runbook

Dependabot PR #3 bumps `postgres:17-alpine` to `18-alpine`. **It is not a
routine image bump and must not be merged as one.** The `db` service persists
`postgres-data:/var/lib/postgresql/data`; PostgreSQL major versions have
incompatible on-disk formats and the official image does not upgrade a data
directory in place. An 18 container started against a 17 volume refuses to boot:

```
FATAL: database files are incompatible with server
DETAIL: The data directory was initialized by PostgreSQL version 17, which is
        not compatible with this version 18.
```

CI passing on that PR means nothing here — CI never boots this stack against an
existing volume.

## What is and is not in the database

| Lives in PostgreSQL | Lives elsewhere |
|---|---|
| The 25 domain tables: cases, membership, sources, source sets, runs, run nodes/artifacts/events/snapshots/budgets, model builds and revisions, deliverables, audit events | **Vault bytes** — original sources, workbooks, frozen exports |
| | **Run checkpoints** — SQLite `checkpoints.db`, which sits on the SAME `vault-data` volume: `CAOS_DATA_DIR` defaults to `storage_dir`, and Compose sets `CAOS_STORAGE_DIR=/vault` |

Verified on a real deployment — the vault volume holds `sources/…` alongside
`checkpoints.db`, `-wal` and `-shm`.

Three consequences:

- The vault volume is untouched by this upgrade. Do not restore it.
- Because checkpoints ride the vault volume, `backup.sh` captures **both**
  stores, and a dump/vault pair taken at one moment is internally consistent.
- Domain state and checkpoint state still have **no shared transaction**. A run
  parked at an interrupt has rows in PostgreSQL and a checkpoint in SQLite.
  Restoring PostgreSQL to a moment the checkpoints have already moved past
  leaves a run whose checkpoint says "past the gate" while its domain rows say
  otherwise. This upgrade restores only the dump and leaves the live vault in
  place, so what keeps the two consistent is that **nothing advances the
  checkpoints in between** — which is exactly why the app stays stopped for the
  whole window. Never restore an older dump onto newer checkpoints.

## Step 0 — the restore path must actually work (blocking)

Everything below rests on `backup.sh` + `restore_drill.sh`. Two known problems:

1. **`restore_drill.sh` verified the predecessor schema.** It asserted
   `caos_state` and `model_build_jobs` and read `model_builds.record->>…`, none
   of which exist in this store — they belong to the legacy CAOS database. It
   could never pass against a backup of this system. Fixed in the same change
   as this document, and the corrected assertions were exercised against a real
   PostgreSQL 17: they pass on a clean restore, and they fail on a malformed
   `payload_digest`, a malformed export `vault_key`, and a malformed
   `run_artifacts.digest`.
2. **`restore_drill.sh` required the `app` service to be running.** Its model
   payload check used `compose exec -T app`, which fails with
   `service "app" is not running` — precisely when the drill matters most, since
   a rehearsal during a maintenance window happens with the app stopped. Now
   `compose run --rm --no-deps`, which starts a one-off container instead.

Both were found by running the drill rather than reading it. The `age` path has
since been exercised end to end against a seeded stack: `pg_dump` → encrypt →
manifest → decrypt → manifest verify → isolated restore → schema assertions →
payload digest recomputation → vault artifact verification, ending in
`restore drill passed`. A single flipped ciphertext byte fails to decrypt rather
than restoring silently, which is the authenticity property an unkeyed checksum
beside the data could never provide.

**Still do a drill on YOUR data before the window.** The rehearsal above proves
the scripts work; it does not prove anything about your corpus, your key
handling, or your backup destination.

Note: `restore_drill.sh` shells out to `docker compose`, and `compose run`
interpolates the whole compose file. Run it from a shell that has the
deployment's environment loaded, or every `${VAR:?}` will stop you before the
restore starts.

## Why dump/restore, not `pg_upgrade`

- `pg_upgrade` needs both major versions' binaries in one image. `postgres:*-alpine`
  ships one. Doing it properly means building a custom image for a one-off.
- The database is small — the domain store holds metadata and JSON artifacts;
  the bulk (documents, workbooks) is in the vault, not here.
- A logical dump/restore rebuilds every index under the new collation, which
  sidesteps the collation-version mismatch that a physical upgrade forces you to
  reason about.
- It exercises the tooling you should be exercising anyway.

## The window

Numbered so it can be read aloud. `$OUT` is the backup destination;
`$RECIPIENT` is the age public key; `$IDENTITY` is the age private key file,
which must come from wherever it is held off-host.

**1. Prepare.** Confirm the age identity is retrievable and that step 0's drill
passed. Note the current image digest so rollback is copy-paste:

```bash
grep -n 'image: postgres' caos/deploy/docker-compose.yml
```

**2. Stop writers. Leave the database up.**

```bash
docker compose -f caos/deploy/docker-compose.yml stop app worker
```

**3. Capture row counts as the before-picture.**

```bash
docker compose -f caos/deploy/docker-compose.yml exec -T db psql -Atq -U caos -d caos -c "SELECT relname||' '||n_live_tup FROM pg_stat_user_tables ORDER BY relname" | tee /tmp/rowcounts.before
```

**4. Take the final backup, with nothing writing.**

```bash
CAOS_BACKUP_RECIPIENT="$RECIPIENT" caos/deploy/backup.sh "$OUT"
```

**5. Go / no-go: restore that exact backup.** This is the gate. It restores
into an isolated database and volume, so it is safe to run with the application
stopped and touches nothing live. If it fails, restart `app` and `worker` — you
have lost nothing.

```bash
CAOS_BACKUP_IDENTITY="$IDENTITY" caos/deploy/restore_drill.sh "$OUT/caos.dump.age"
```

**6. Stop everything and preserve the old volume.** Renaming rather than
deleting is what makes rollback a compose edit instead of a restore. Docker
cannot rename a volume, so copy it:

```bash
docker compose -f caos/deploy/docker-compose.yml down
docker volume create deploy_postgres-data-v17-keep
docker run --rm -v deploy_postgres-data:/src:ro -v deploy_postgres-data-v17-keep:/dst alpine sh -c 'cp -a /src/. /dst/'
```

Verify the copy holds a 17 data directory before going further:

```bash
docker run --rm -v deploy_postgres-data-v17-keep:/d:ro alpine cat /d/PG_VERSION
```

**7. Point the compose file at 18** (merge PR #3, or edit the digest by hand),
then remove the live volume so 18 initialises a fresh cluster:

```bash
docker volume rm deploy_postgres-data
docker compose -f caos/deploy/docker-compose.yml up -d db
```

**8. Restore into the fresh 18 cluster.** `pg_restore` creates the tables, so
this must happen before the app starts — the app's `metadata.create_all` is
`checkfirst`, so it is harmless afterwards either way.

```bash
age -d -i "$IDENTITY" "$OUT/caos.dump.age" | docker compose -f caos/deploy/docker-compose.yml exec -T db pg_restore --exit-on-error --no-owner --no-acl -U caos -d caos
```

**9. Compare row counts. This is the acceptance test, not a formality.**

```bash
docker compose -f caos/deploy/docker-compose.yml exec -T db psql -Atq -U caos -d caos -c "ANALYZE; SELECT relname||' '||n_live_tup FROM pg_stat_user_tables ORDER BY relname" > /tmp/rowcounts.after
diff /tmp/rowcounts.before /tmp/rowcounts.after && echo "row counts match"
```

**10. Start the application and check it end to end.**

```bash
docker compose -f caos/deploy/docker-compose.yml up -d
```

Then confirm, in this order — each one exercises a different store:

- `GET /api/health` → 200.
- The case register lists the cases you expect (PostgreSQL).
- A previously accepted run still shows its snapshot and artifacts (PostgreSQL).
- A model build's XLSX still downloads (PostgreSQL metadata **and** vault bytes —
  this is the one that proves the two stores still agree).
- A filed deliverable still renders its frozen proof.
- If a run was mid-flight, that it resumes rather than restarts (SQLite
  checkpoints reconciling with restored domain rows).

## Rollback

Only possible before step 7's `docker volume rm`, and trivial after step 6
because the 17 cluster was copied, not moved:

```bash
docker compose -f caos/deploy/docker-compose.yml down
docker volume create deploy_postgres-data
docker run --rm -v deploy_postgres-data-v17-keep:/src:ro -v deploy_postgres-data:/dst alpine sh -c 'cp -a /src/. /dst/'
git checkout caos/deploy/docker-compose.yml   # back to the 17 digest
docker compose -f caos/deploy/docker-compose.yml up -d
```

Keep `deploy_postgres-data-v17-keep` until the 18 cluster has served real work
for long enough that you would not want to go back. Then delete it — it is a
full copy of the confidential corpus sitting unencrypted on the host, which is
exactly what `backup.sh` refuses to produce.

## Things that will not bite, and one that might

- **No extensions.** Nothing to reinstall on the new cluster.
- **Partial index.** `sources` carries a `postgresql_where=NOT withdrawn`
  partial unique index; `pg_dump` carries it and 18 rebuilds it.
- **JSON columns.** The store uses `sa.JSON` (PostgreSQL `json`, not `jsonb`).
  Format is stable across majors. Note for anyone editing the drill:
  `json_typeof`, not `jsonb_typeof`.
- **Collation — the one to watch.** A logical restore rebuilds indexes under
  18's collation, so there is no mismatch warning to chase. But if 18 ships a
  different default collation, *text ordering can change*. Ordering in this
  store is by `seq` (integer), `version` (integer), or ISO-8601 `created_at`
  strings, all of which order identically under any collation. Nothing here
  orders by user-supplied text in a way that affects correctness. Worth
  re-checking if that ever changes.

## Not covered

Replication, connection poolers, and point-in-time recovery — none are deployed.
Single instance, single database, one volume.
