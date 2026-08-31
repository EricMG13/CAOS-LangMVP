# Restore drill — 2026-08-30

**Outcome: RUN END TO END. The restore works; both scripts have defects.**

`backup.sh` and `restore_drill.sh` had never been executed against a real stack.
They have now been, against a purpose-built isolated stack on this machine. The
data path is sound: an encrypted backup of both stores restored to a
byte-identical run corpus, and a run interrupted at a gate resumed from its
checkpoint rather than restarting. **Measured RTO: 89.3 s.**

Two real defects surfaced, both of which the syntax-only CI check could never
have caught. One of them (**F2**) means that after a real disaster recovery,
`backup.sh` silently stops producing backups.

The `CLAUDE.md` known-gap entry — "Backup encryption is **untested here** … Drill
a real backup/restore pair before relying on either" — can now be rewritten, but
not simply deleted: it should be replaced by F1 and F2 until those are fixed.

---

## Pre-flight

### Tooling

```
$ command -v age            -> (absent, exit 1)
$ docker compose version    -> Docker Compose version 5.2.0
```

`age` was **missing** and was installed for this drill:

```bash
brew install age
```

Now `age v1.3.2` / `age-keygen v1.3.2`. Both scripts hard-require the `age`
binary and exit 69 without it (`backup.sh:35`, `restore_drill.sh:16`).

### Existing stacks and volumes — nothing pre-existing was touched

The machine carries more than one generation of this stack. At inventory time:

```
$ docker compose ls -a
NAME                 STATUS         CONFIG FILES
caos-goal-20260824   running(2)     /Users/ericguei/Claude/Projects/CAOS/caos/deploy/docker-compose.yml
newcos               exited(1)      /Users/ericguei/Claude/Projects/New COS/docker-compose.yml
```

`caos-goal-20260824` had been **up for 6 days** against
`caos-goal-20260824_postgres-data` / `_vault-data`, and unattached
prior-generation volumes `caos_pgdata`, `caos_vault`, `caos_caddy_data`,
`caos-l26-backups`, `caos-codex-20260823-vault`, `caos-l25-vault` were present.
56 volumes total.

**None of them was a drill target.** The whole drill ran in a new, isolated
compose project, `caos-drill-20260830`, whose three volumes
(`_postgres-data`, `_vault-data`, `_clamav-data`) were created by step 1 and were
the only volumes ever destroyed. This is enforced structurally, not by care:
`docker compose -p caos-drill-20260830 down -v` removes only volumes carrying
that project label. `docker volume prune` was never run.

Verified before and after:

| Checkpoint | Volume count | Evidence |
|---|---|---|
| Before destroy | 56 | — |
| After destroy | 53 | exactly the 3 `caos-drill-20260830_*` removed; `comm` diff shows nothing else changed |
| After teardown | 53 | `diff` against post-destroy list is empty |

`caos-goal-20260824` was still `running(2)` at the end, and
`caos-goal-20260824_postgres-data`, `caos-goal-20260824_vault-data`,
`caos_pgdata`, `caos_vault` all still present.

---

## Step 1 — stack up and seeded

Built from this worktree (`docker compose build app`) and brought up `db`,
`clamav`, `app` under the drill project. `ENVIRONMENT=production`, Postgres
domain store, real production auth edge.

Authentication used the genuine production path rather than a bypass: production
derives role from OIDC groups only (`identity.py:59-63`), so the drill supplied
the headers oauth2-proxy injects — `x-edge-authorization` (matching
`EDGE_PROXY_SECRET`), `x-forwarded-user`, `x-forwarded-email`,
`x-forwarded-groups: caos-analyst`. Everything below went through the HTTP API of
the serving process, so runs executed on the serving engine's own loop (never a
second loop driving one run).

Seeded:

| Item | Id | State |
|---|---|---|
| Case A | `case-5f0bbf11d6164d1c941b` | 1 source, source set `set-6eded794dddb4df389bc` v1 |
| Run A (SCREEN) | `run-1603664d0c9646c6a972` | **succeeded**, 9 artifacts, 21 events |
| Run C (FULL) | `run-e1fe5e8ff54743aa967b` | **succeeded**, 17 artifacts, 37 events |
| Case B | `case-1e6d2ce7bf45481a9d91` | deliberately no sources |
| Run B (SCREEN) | `run-36cde203f3f34842aecc` | **paused at the gate**, `SOURCE_SET_EMPTY`, resume ticket issued |

Run B is a real LangGraph interrupt, not a synthetic status: the gate node loops
`while not current or not current.get("source_ids")` and calls
`interrupt({"reason": "SOURCE_SET_EMPTY", "ticket": ticket})`
(`engine/runtime.py:238-240`).

**Budget ledger — a deviation, stated plainly.** `run_budgets` was empty after
seeding, and would have made the step-4 budget assertion vacuous (0 rows vs 0
rows). `init_budget` is only reached on the agent-execution path
(`runtime.py:433`), and deterministic routes make no provider calls. A FULL-depth
run was attempted to force one; it also succeeded without any provider call and
wrote no ledger row. Agent execution needs an API key this drill did not have.
So one ledger row was seeded **through the store's own API**
(`RunStore.init_budget` + `charge_budget`) with non-zero `used` values. The row is
real and written by production code; the *numbers* are host-chosen rather than
produced by a metered provider call. The restore comparison below is therefore a
genuine test that the ledger's JSON survives dump/restore, and **not** a test of
provider metering.

---

## Step 2 — encrypted backup

```
$ CAOS_BACKUP_RECIPIENT=age1v630yy… bash caos/deploy/backup.sh <dest>
encrypted backup written to <dest> (recipient age1v630yy…)
```

**Elapsed: 0.59 s.** Produced `caos.dump.age` (37,919 B), `vault.tgz.age`
(71,988 B), `caos.backup.manifest` (231 B), all mode `0600`.

Every confidentiality claim was checked, not assumed:

| # | Check | Result |
|---|---|---|
| 1 | Ciphertext is age format | `age-encryption.org/v1` header, X25519 stanza |
| 2 | Decrypt **without** the identity | refused — "identities are required" |
| 3 | Known plaintext in ciphertext (`Drill Issuer A`, the case id, the run id, the evidence line, `PGDMP`, `checkpoints`) | **all six absent** from both files |
| 4 | Private key in the backup | absent; no `AGE-SECRET-KEY` string in any backup file |
| 5 | Manifest contents | carries the **public** recipient + two SHA-256s only |
| 6 | Private key in the compose file | absent — no `AGE-SECRET`, `CAOS_BACKUP_IDENTITY`, or `age1…` in `docker-compose.yml` |
| 7 | Private key in the image | absent from image env; no `AGE-SECRET-KEY` under `/app` or `/vault` in the running container |
| 8 | Decrypt **with** the identity | succeeds; dump begins `PGDMP` |
| 9 | Tamper detection — one byte flipped at offset 35,994 | **refused**: "failed to decrypt and authenticate payload chunk" |

Claim 9 is the one that matters most and it holds: age gives authenticity, not
just confidentiality, so a tampered archive fails closed instead of restoring
silently — exactly as `backup.sh`'s header comment argues.

**Both stores are in the backup.** The vault tarball contents:

```
./checkpoints.db          4,096 B
./checkpoints.db-wal    964,112 B
./checkpoints.db-shm     32,768 B
./sources/14/141b5263…       61 B
```

---

## Step 3 — volumes destroyed

`docker compose -p caos-drill-20260830 down -v --remove-orphans` removed all
three drill volumes. Proof the destruction was real, not nominal: on restart the
fresh `caos` database reported **0 tables** in `information_schema`.

---

## Step 4 — restore and run-level verification

Restored both stores: `pg_restore` for the domain database, and the decrypted
tarball into the vault volume. State was captured before the backup and after the
restore and compared file by file.

### Every captured surface is byte-identical

| Surface | Result |
|---|---|
| `runs` (id, status, plan_digest, error, schema_version) | IDENTICAL |
| `run_artifacts` (digest, input_fingerprint, qa_status) | IDENTICAL |
| artifact bodies (md5 of `payload`, `markdown`) | IDENTICAL |
| artifact payloads dumped to files and SHA-256'd | IDENTICAL |
| `run_events` (run_id, seq, event) | IDENTICAL |
| `audit_events` (seq, action, actor) | IDENTICAL |
| `run_budgets` (limits, used, inflight digest) | IDENTICAL |
| `source_sets`, `sources`, `run_nodes`, `resume_tickets` | IDENTICAL |
| checkpoint store | 24 checkpoints / 157 writes / same 3 threads, before and after |

### 1. Completed run artifacts are byte-identical — verified against the content address

**26 artifacts existed at backup time** (9 on run A, 17 on run C; run B had none,
being parked at the gate). All 26 came back byte-identical by the file-level diff
above.

Stronger than a diff against my own capture: each payload was then re-hashed with
the host's own `digest()` and compared to the stored content address. This ran
after the resume, so it covers 35 artifacts — the 26 restored ones plus the 9 the
resumed run B produced:

```
-> 35 match, 0 mismatch, 35 artifacts total
```

Zero mismatches. Vault source blobs likewise re-hashed against `sources.sha256`:
both MATCH.

### 2. The interrupted run resumed from its checkpoint, not from the start — PASS

After restore, run B was still `paused`. A source was added to case B and
`POST /api/runs/{id}/resume` was called; it reached `succeeded`.

| Evidence | Value | Meaning |
|---|---|---|
| `run.created` events for run B | **1** | a restart would have emitted a second |
| `run.paused` events | 1 | the original pause, not re-entered |
| First post-restore seq | **3** | continues the pre-backup log, which ended at 2 |
| Final seq / contiguity | 1..22, `contiguous-from-1` | no gap, no reset |
| Checkpoints on thread `run-36cde203f3f34842aecc` | **2 → 9**, same `thread_id` | appended, not recreated |
| Resume ticket | `consumed=1` | consumed exactly once |

This is invariant 6 (durable, exactly-once, resume from the last checkpoint)
holding across a full destroy/restore cycle.

### 3. Audit log intact and per-run seq monotonic — PASS

`audit_events` restored contiguous (seq 1..4, no gaps). Per-run `run_events`
after restore *and* after the resume:

```
run-1603664d0c9646c6a972 | succeeded | 21 events | contiguous | created once
run-36cde203f3f34842aecc | succeeded | 22 events | contiguous | created once
run-e1fe5e8ff54743aa967b | succeeded | 37 events | contiguous | created once
```

### 4. Budget ledger totals match — PASS, with the step-1 caveat

`limits` and `used` JSON identical pre and post, including the non-zero
`used` values (`evidence_reads 7`, `evidence_bytes 20480`,
`input_tokens 41230`, `output_tokens 8814`, `active_minutes 1.25`). Read this as
"the ledger survives dump/restore intact", not as a test of provider metering —
see the step-1 deviation.

---

## Step 5 — RTO

Measured on a clean, uninterrupted destroy→restore→serving cycle (the earlier
cycle took 203.9 s, but that included diagnosing the F1 failure, so it is not the
honest number).

| Phase | Time |
|---|---|
| `db` up and accepting connections | 1.5 s |
| `pg_restore` (domain store) | 0.2 s |
| vault volume create + tarball extract | 10.6 s |
| `app` up and healthy | 77.1 s |
| **RTO (destroy → serving restored data)** | **89.3 s** |

Backup itself: 0.59 s.

The restore reproduced the baseline exactly — 3 runs / 35 artifacts / 80 run
events / 4 audit rows, and 24 checkpoints across the same three threads.

**Scale caveat, stated rather than extrapolated:** this corpus is tiny (38 KB
dump, 72 KB vault). 87 of the 89 seconds are fixed container-start cost, which
will not grow, but `pg_restore` and the vault extract will. This RTO is a floor,
not a projection for a production corpus.

---

## Failures found

### F1 — `restore_drill.sh` fails on a perfectly good backup (exit 1)

The very first restore attempt:

```
$ bash caos/deploy/restore_drill.sh <dump>
ERROR:  required restored tables are missing
CONTEXT:  PL/pgSQL function inline_code_block line 1 at RAISE
exit=1
```

The backup was **fine** — the same dump restored completely by hand moments
later, and every run-level assertion above passed on it.

**Root cause.** The verification at `restore_drill.sh:138` requires nine tables.
The restored database had seven of them:

```
cases           present     runs           present
sources         present     run_artifacts  present
source_sets     present     run_events     present
audit_events    present
model_builds    *** MISSING ***
model_revisions *** MISSING ***
```

`model_builds` and `model_revisions` live under a **separate** SQLAlchemy
metadata (`storage/models.py:23,52`), created by `ModelStore.__init__` →
`model_metadata.create_all(engine)` (`models.py:102`). `ModelStore` is
constructed **lazily**, only when a model operation happens
(`store.py:599,613,618,631,641`). `DeliverableStore` is the same
(`deliverables.py:98`).

So a CAOS deployment that has **never queued a model build has no
`model_builds` table** — and `restore_drill.sh` reports its backup as unrestorable.
That covers every newly provisioned deployment and any deployment restored before
its first model build.

**Confirmed adversarially, not just diagnosed.** `ModelStore` and
`DeliverableStore` were instantiated (17 → 25 tables), a fresh backup taken, and
the same script re-run against it:

```
exit=0
DO
restore drill passed for isolated database caos_restore_drill
```

The script is correct in every other respect; the table list is the whole defect.

**Impact.** This is the worst kind of monitoring failure: it tells an operator a
good backup is bad. Under the header comment's own policy ("Exercise
restore_drill.sh on a real backup on a schedule"), a scheduled drill on a fresh
deployment fails permanently, and the standing red trains people to ignore it.

**Fix.** Either gate the two model tables on their existence, or have the app
create all four metadatas at startup so the schema does not depend on usage
history. The second is the better fix — a schema that varies by what the
deployment happens to have done is a hazard beyond this script.

### F2 — `backup.sh` silently stops backing up after a restore

Discovered by accident, and it is the more dangerous of the two.

`backup.sh:62-64` locates the vault volume by compose label:

```bash
project_name=${COMPOSE_PROJECT_NAME:-deploy}
vault_volume=$(docker volume ls -q --filter "label=com.docker.compose.project=$project_name" \
                                   --filter "label=com.docker.compose.volume=vault-data" | head -n 1)
test -n "$vault_volume"
```

The trigger is a vault volume created outside compose. `docker volume create`
is the obvious way to restore a volume by hand — it is what this drill did, and
what `restore_drill.sh:117` does for its own drill volume — and such a volume has
**no compose labels**:

```
$ docker volume inspect caos-drill-20260830_vault-data --format '{{json .Labels}}'
null                                   # vs the compose-created postgres volume, which has all four labels
```

The filter therefore returns nothing, `test -n ""` fails, and under `set -e` the
script dies **with no diagnostic whatsoever**:

```
exit=1   stdout_bytes=0   stderr_bytes=0   files produced: 0
```

It even deletes its own partial dump on the way out via `trap cleanup EXIT`.

**Impact.** Restore the vault by hand, and your backups stop — producing no
files, no stdout, and no stderr. Exit 1 is the only signal, so a cron job with
strict status alerting catches it, but a human reading logs sees a clean, silent
run. The failure lands precisely when backups matter most: immediately after a
recovery.

Scoping this honestly: an operator who brings the stack up with `compose up`
*first* and then extracts the tarball into the volume compose created keeps the
labels and is unaffected — that is the workaround this drill used to finish, and
it is not obvious from either script. The defect is that the outcome depends on
an unstated ordering, and gives no diagnostic when it goes the wrong way.

Confirmed both ways — re-homing the vault onto a compose-created (labelled)
volume made the identical `backup.sh` invocation succeed again.

**Fix.** Two independent changes, both cheap. Give `test -n "$vault_volume"` and
`test -s` real error messages so the failure is never silent. And resolve the
vault volume the way the running container actually mounts it (`docker inspect`
the app's mount for `/vault`) instead of trusting a compose label that a restore
does not reproduce.

### F3 — the two halves of a backup have no common snapshot point

Design risk, verified by inspection and observed in effect.

`backup.sh` captures the domain store (`:60`) and the vault (`:66`) as two
sequential, independent operations, with **no quiescing anywhere** — confirmed by
inspection: no `stop`, `pause`, `freeze`, or `sync` in the script. Anything the
running system writes between the two lands in one half and not the other.

This drill produced a concrete instance of the resulting divergence: a restored
run whose domain row read `succeeded` while the restored checkpoint store held
only its 2 pre-resume checkpoints instead of 9. **Attribution matters here — I
induced that skew by re-extracting an older vault tarball during the F2
investigation, not `backup.sh` itself**, whose two captures were sub-second apart
on this tiny corpus. But the mechanism is real and unguarded, and the window
scales with dump time: on a production corpus `pg_dump` runs for minutes while
runs keep executing and checkpointing.

Related and unresolved: `checkpoints.db` is **4,096 bytes** while
`checkpoints.db-wal` is **964,112 bytes** — SQLite is in WAL mode and essentially
all checkpoint state lives in the WAL. `tar` copies `.db`, `-wal`, and `-shm` at
three different instants from a live database, and `-shm` is shared-memory state
that should be regenerated rather than restored. It restored correctly here (24
checkpoints, 157 writes, exact thread continuity), but that is **one observation
under near-zero write pressure**, not evidence of safety under load.

**Fix.** Give the two halves one snapshot point. The cheap version: run
`PRAGMA wal_checkpoint(TRUNCATE)` against `checkpoints.db` and skip `-shm` in the
tar. The correct version: snapshot the volume (or briefly quiesce the app) so the
domain dump and the checkpoint copy describe the same instant.

---

## What was not covered

- **Provider metering was never exercised.** No agent execution, no API key, so
  no provider call ever reserved or reconciled budget. The ledger row was
  host-seeded (see step 1). Invariant 8's reserve/reconcile path across a restore
  is **untested**.
- **The worker was never run.** `worker.py`, XLSX rendering, and model/deliverable
  export artifacts were not part of the drill, so no exported binary was checked
  for byte-identity across restore.
- **`oauth2-proxy` and `caddy` were not started.** The real OIDC edge and TLS
  termination are untested; the drill supplied the edge headers directly.
- **Single-cycle WAL evidence only.** The checkpoint store restored correctly
  twice, both times with no concurrent run activity. A backup taken mid-execution
  under real write pressure has **not** been tested — see F3.
- **Tiny corpus.** See the RTO scale caveat.

## Reproducing this

```bash
brew install age
age-keygen -o drill.identity                      # recipient printed to stderr
export COMPOSE_PROJECT_NAME=caos-drill-$(date +%Y%m%d)   # isolates every volume
export CAOS_BACKUP_RECIPIENT=age1…  CAOS_BACKUP_IDENTITY=$PWD/drill.identity
```

`COMPOSE_PROJECT_NAME` is the load-bearing part: `backup.sh:62` reads it for the
vault lookup and its `compose` helper inherits it, so one variable keeps the
backup, the restore, and the destroy inside a namespace created for the drill.
Without it, both scripts default to project `deploy`.

## Machine state after the drill

Everything the drill created was removed. Volume count returned to its
pre-drill 53, with a `diff` against the pre-drill list showing no other change;
no `caos-drill-20260830` containers or volumes remain; `caos-goal-20260824` was
still `running(2)` and `caos_pgdata` / `caos_vault` / the goal stack's volumes
were all still present.

One artifact was deliberately left in place: the built image
`caos-drill-20260830-app:latest` (~410 MB), so a rerun does not pay the frontend
and pip build again. Remove it with:

```bash
docker image rm caos-drill-20260830-app:latest
```
