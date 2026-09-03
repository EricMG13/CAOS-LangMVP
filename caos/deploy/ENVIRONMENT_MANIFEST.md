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
