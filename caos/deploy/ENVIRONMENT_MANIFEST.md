---
meta:
  contentType: Reference
  audience: The enterprise test owner and the operator of the enterprise-test stack
---

# Enterprise-test environment manifest

This manifest records what the enterprise-test environment is and what it is
not. It is a declaration the candidate evidence package (Task 13) copies
verbatim; `caos/tests/test_deploy_topology.py` pins the parts that are
checkable from the repository. Anything not listed here is not part of the
declared environment.

## Topology and the single-instance ceiling

| Service | Replicas | Image | Why one |
| --- | --- | --- | --- |
| `app` | exactly 1 | `caos/deploy/Dockerfile` target `app` | Run checkpoints are SQLite on the vault volume; request ceilings count in-process; a second engine over one checkpoint file would corrupt invariant 6 |
| `worker` | exactly 1 | `caos/deploy/Dockerfile` target `worker` | Exports have no claim (two workers would both render one export); build and freeze claims are compare-and-swap, so a duplicate loses cleanly but is still refused |
| `db` | 1 | `postgres:17-alpine` (digest-pinned in Compose) | The domain store; every governed write is one transaction |
| `clamav` | 1 | `clamav/clamav:1.5` (digest-pinned) | Upload scanning; the app fails uploads closed when it is unreachable |
| `oauth2-proxy`, `caddy` | 1 each | digest-pinned | The trusted edge; the app derives identity from OIDC groups only |

The ceiling is **one application instance and one worker instance per
database and vault volume**. It is declared in `caos/deploy/docker-compose.yml`
(`deploy.replicas: 1` on `app` and `worker`) and enforced by the software:

- The app takes an exclusive operating-system lock (`flock`) on
  `checkpoints.db.lock` beside the checkpoint database before startup
  recovery runs or a socket is bound (`caos/server/caos/instance_lock.py`).
  A second app over the same data directory exits with
  `INSTANCE_ALREADY_RUNNING` and never serves; proven by a second process in
  `caos/tests/test_single_instance.py`.
- The app and the worker each hold a PostgreSQL session advisory lock for
  their role (`DomainStore.single_instance`); a duplicate of either is refused
  at startup and a lock lost mid-run terminates the process.

Scaling out is not a configuration change. It requires moving checkpoints to
the PostgreSQL saver, the request ceilings to a shared store and an export
claim — none of which is in the enterprise-test scope.

## Scanner supervision and memory

The scanner uses the pinned image's original `/init` for signature-directory
ownership, first download and FreshClam updates. `clamav-supervise.sh`, under
Tini with process-group signal forwarding, observes the actual clamd process
once per second and exits if it dies, including a zombie left under the image's
`tail` process. The existing `restart: unless-stopped` policy then restarts the
container. A busy or reloading scanner is not treated as a dead process.

Compose budgets 4 GiB for the scanner (`CLAMAV_MEMORY_LIMIT`, default `4g`)
with a 2 GiB soft reservation (`CLAMAV_MEMORY_RESERVATION`, default `2g`). This
includes headroom for the active engine, concurrent database reload and
FreshClam's signature validation. Budget that memory in addition to the app,
worker and PostgreSQL; an 8 GiB Docker host/VM is the starting test profile,
subject to qualification with the actual signature set and workload. Raising a
container limit does not increase the VM's physical memory. The old 4 GiB
shared local VM is not the declared full-signature reload test environment.

The API's scanner status is `ready`, `unavailable` or `not_required` for the
development bypass. A production probe requires an exact clamd PING/PONG
exchange. It has a one-second caller deadline, including DNS, at most one
outstanding probe and a five-second cache. Readiness can therefore lag a
scanner failure by the remaining cache interval plus the probe deadline.
Readiness never permits skipping the real per-upload scan: production still
refuses scanner outages with 503 before admitting source bytes. Dependency
readiness is separate from process supervision and must not restart the app.

Candidate evidence must kill clamd inside a fresh isolated container, observe
readiness and clean-upload refusal, prove automatic restart and admission
recovery, then repeat after a signature reload. Record image, architecture,
signature set, peak memory and elapsed times. The full-signature recovery
bound remains a candidate gate until measured on the declared host; a tiny
synthetic signature drill proves recovery mechanics only. See the
[ClamAV container guidance](https://docs.clamav.net/manual/Installing/Docker.html)
for signature-loading and memory considerations.

## Data, backup and the snapshot point

- Confidential data lives in exactly two places: the PostgreSQL database
  (domain rows, run events, audit chain, model and deliverable records) and the
  vault volume (source bytes, run checkpoints, published exports). Logs carry
  typed codes and identifiers only, never document text (`observability.py`).
- `caos/deploy/backup.sh` captures both halves at **one snapshot point**: it
  pauses the `app` and `worker` containers for the whole capture, dumps
  PostgreSQL, archives the vault (excluding the regenerable
  `checkpoints.db-shm`), then unpauses on every exit path. The application is
  unavailable for the duration of the capture; that is the documented cost of
  a consistent backup under the single-instance topology.
- The vault volume is resolved from the running app container's `/vault`
  mount, or from `CAOS_VAULT_VOLUME` when the app is down. Compose labels are
  never consulted. Every failure names its cause on stderr.
- `caos/deploy/restore_drill.sh` restores into an isolated database and
  volume and asserts the complete startup schema, which the store now creates
  on first boot regardless of usage history.

## Reset

A candidate-data reset is `docker compose down -v` for the stack's volumes
(`postgres-data`, `vault-data`) followed by `docker compose up`; the store
recreates the whole schema at startup and the app serves an empty
environment. Nothing outside those two volumes holds candidate data. Reset is
owned by the enterprise test owner and is recorded in the evidence package
with the volume names removed.

## Not declared

No high-availability control plane, no shared application fleet, no
distributed checkpointer, no production capacity or availability claim. The
eight-hour soak and the saturated six-pathway workload run only against the
frozen candidate (Task 13).

## Operator bootstrap and provider catalog (2026-09-06)

Set `CAOS_ENTERPRISE_OPERATOR_SUBJECTS` to comma-separated, exact OIDC subject
IDs. A listed subject also needs a current trusted `caos-admin` group. Admin
accepts a known case ID for first-approver provisioning; the operator, creator
and target are independent. This grants no case visibility. The receipt persists
through revocation, so retrying cannot reopen bootstrap. Existing approvers use
the ordinary member controls. Recovery after losing all approvers requires an
explicit audited operator procedure; this endpoint is deliberately one-shot.

Copy `provider-config/catalog.example.json` into an external configuration
directory and replace every placeholder. Set `CAOS_PROVIDER_CONFIG_DIR` to that
host directory and `CAOS_PROVIDER_CATALOG_PATH=/etc/caos/providers/catalog.json`.
The directory is mounted read-only. Set `OPENAI_API_KEY` and
`ANTHROPIC_API_KEY` on the server; catalog entries name credential environment
variables, never contain credential values. Custom credential variable names
must also be explicitly passed to the app container. Configurable model IDs do
not confer qualification. Production accepts direct OpenAI and Anthropic
bindings with current candidate-bound v2 qualification records and an approved
account-policy ID. Set `CAOS_BUILD_COMMIT`, `CAOS_IMAGE_SET_DIGEST` and
`CAOS_CORPUS_DIGEST` to the qualified candidate identities; mount its records
beside the catalog. The example is intentionally not runnable qualification.

An operator changes the default in Admin using a versioned policy update. That
policy is stored and audited in the database. It affects only new runs. Existing
runs retain their provider identity across continuation, recovery, acceptance
and upgrades; removing or invalidating that binding refuses continuation.
Keep prior qualified bindings in the catalog while their runs remain active.
`CAOS_DEFAULT_PROVIDER_BINDING` supplies the initial default; a persisted policy
takes precedence. Two provider calls and twenty active jobs remain aggregate
limits across the catalog. Single-binding legacy configuration remains usable
with `CAOS_PROVIDER_ACCOUNT_POLICY` naming its approved account policy and a
matching current v2 qualification. Multiple credentials require an explicit
catalog.

Startup creates `case_approver_bootstraps` and `provider_policy` on existing
stores. Backup and restore include both tables. Existing cases and run identities
are not rewritten. Legacy qualification records do not establish qualification
for a new candidate or an added model; produce a v2 record before enterprise
admission. Signed-in Codex is a separate development qualification backend and
is rejected by production assembly. Its results do not qualify the direct API
adapters or replace independently approved answer keys.
