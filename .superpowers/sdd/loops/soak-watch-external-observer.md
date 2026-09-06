# Soak watch — independent external observation

**Read `soak-watch.md` first. That is the ER-L4 operator log and it is
authoritative; this file is a second, independent observation of the same run
made from another worktree, by a watcher that could not see the harness's own
outputs.** Both were written on 2026-09-04 without knowledge of each other.

## What this file got wrong, corrected against the ER-L4 log

The observer had no access to
`.superpowers/sdd/candidates/2026-09-04-b88c0f8/soak/`, which lives in the
candidate clone, so it repeatedly concluded from local absence that things did
not exist. Four claims below are wrong and are corrected here rather than
edited out of the ticks:

1. **"No soak harness in the tree" (tick 1) and "the terminal comparison has no
   executable referent" (tick 18) are wrong.** The soak was driven by the
   harness the whole time:
   `qa/capacity.py profile --duration 28800 --documents 80 --large-every 500
   --sample-every 30 --compose-project caos-cand-20260904 --restart-every 7200
   --restart-command "docker compose -p caos-cand-20260904 restart -t 0 worker"`,
   started `2026-09-04T00:19:33Z`. The later in-file correction, which said the
   harness existed but "the run was not started through" it, is also wrong.
2. **"No pre-soak baseline" is wrong.** Two were recorded before the run:
   `soak/baseline-pre.json` (harness) and `soak/pre-soak-authority.json`
   (whole-store snapshot from `soak/authority_snapshot.sh`).
3. **The worker container replacements recorded as outside interventions at
   ticks 8 and 14 were the harness's own injected fault** — `--restart-every
   7200`, with restarts at 02:20:43Z, 04:21:19Z and 06:22:01Z. They were the
   experiment, not interference with it. The app/db restarts before ticks 3 and
   4 and the project replacement before tick 10 are the candidate stack being
   stood up, which the observer joined mid-setup.
4. **Harness output existed at every tick** — `soak/profile.log`,
   `soak/profile/samples.jsonl` (631 samples), `soak/profile/profile.json`.

The ER-L4 log records the soak completing on its own at `2026-09-04T08:20Z`
with `leakage []`, 6,291 runs accepted, no `driver_error` and no traceback.
That corroborates this file's independent terminal reading: last run created
`2026-09-04T08:20:36Z`, 6,304 runs, 6,302 succeeded, 0 failed.

## What this file contributes, and one correction it makes in the other direction

Three things survive the corrections above, because they were measured rather
than inferred:

- **An eighteen-tick resource series taken from outside the harness** — CPU,
  memory, connections, handles and TCP state breakdowns, orphan-row and
  cross-case queries straight against the database — which is independent
  confirmation of the harness's own `samples.jsonl`.
- **Two candidate findings raised and then refuted by further evidence**: open
  file handles (F1, tick 6, closed at tick 7) and the CLOSE_WAIT bursts
  (ticks 11, 13, 17). The refutations are the useful part; each shows the
  quantity reversing, which is what distinguishes churn from a leak.
- **The clamav OOM (F2), found independently at tick 10.** The ER-L4 log dates
  it precisely to between 03:30:50Z and 03:31:36Z.

**And this observer's follow-up corrects a claim both logs made.** ER-L4 says
"Uploads have failed closed since then"; this file said the OOM stopped source
admission. **Both are wrong.** The stack runs `ENVIRONMENT=development`, so
`sources/domain.py::scan_content` returns after its EICAR substring check and
never opens the clamd socket. Probed on 2026-09-06 with clamd still dead: a
clean upload returned **201 in 0.02 s** and EICAR still returned **422**.
Admission never depended on clamd here; it stopped because the harness stopped
seeding. The production-configured re-run in
`.superpowers/sdd/production-intake-identity-probes-2026-09-06.md` shows what
failing closed actually looks like — `503 malware scanner unavailable` — and
that it only happens under `ENVIRONMENT=production`.

---

Loop: `/loop 30m` (cron job f122776c, session-only, 30-minute cadence).
Rule: observe only. Never restart, scale, or reconfigure — the soak is evidence.

## 2026-09-03 tick 1 — NO SOAK RUNNING

Sampled: `docker ps`, `docker stats`, repo tree, `.superpowers/sdd/`, `qa/`.

| Signal | Observation |
|---|---|
| Candidate stack | Only `caos-cand-20260903-pg` (postgres:17-alpine), up ~4 min. No candidate `app`, `worker`, `caddy`, or `clamav` container. |
| CPU / memory | pg: 0.00% CPU, 35.82 MiB / 3.813 GiB |
| DB connections | not sampled — no application attached to the candidate database |
| Handles, jobs, permits | n/a — no app or worker process exists |
| Checkpoint size, vault growth, export storage | n/a — no candidate data volume in use |
| Provider usage, success/refusal counts, error classes | n/a — no harness output exists |
| Harness | No soak harness in the tree. `qa/` holds `capacity.py`, `probe.py`, `scenarios.py`, `seed.py`, `edge_proxy.py` — `capacity.py` has `limits`/`profile`/`baseline`/`compare`, none of which is an eight-hour soak driver. |
| Pre-soak baseline | Not found. No recorded baseline for authorities, model hashes, filed bytes, or offline reconstruction. |

**Finding (tick 1): the premise is not yet true.** The soak is not running, no harness
was launched, and no pre-soak baseline exists to compare against. `caos-cand-20260903-pg`
looks like the first step of another session standing the candidate stack up, not a soak
in flight. Nothing was touched.

Loop continues; the next tick will pick the soak up once the app/worker containers and a
harness output appear.

## 2026-09-03 21:14 tick 2 — STACK UP, SOAK NOT STARTED

Candidate stack came up between ticks. Still no soak driver and no harness output.

| Signal | Observation |
|---|---|
| Containers | `app-1` up 12m (healthy), `worker-1` up 8m, `db-1` up 14m (healthy), `clamav-1` up 14m (healthy), `pg` up 18m |
| CPU | app 0.48%, worker 0.00%, db 0.00%, clamav 0.02%, pg 0.01% |
| Memory | app 133.1 MiB, worker 67.6 MiB, db 40.3 MiB, clamav 1.007 GiB, pg 24.9 MiB (of 3.813 GiB) |
| DB connections | 5 total on `caos`: 1 active, 4 idle |
| Open file handles (app pid 1) | 14 |
| Active jobs / permits | none — no build, export or freeze job rows exist |
| Checkpoint size | `/data/checkpoints.db` absent (no run has been started) |
| Vault growth | `/vault` 72K |
| Export storage | `/data/exports` absent |
| Provider usage | none |
| Success / refusal counts | only `GET /api/health` 200s (container healthcheck); no application traffic |
| Error classifications | none in `docker logs --since 40m` |
| Live rows | `audit_chain_heads` = 1; every other table empty |
| Harness output | still none; no `capacity.py`/`scenarios.py`/`probe.py` process on the host |
| Pre-soak baseline | still not recorded |

No finding: nothing is monotonically growing because nothing is running. Values above
stand as the **idle reference** for later ticks. Nothing was touched.

## 2026-09-03 21:44 tick 3 — STACK RESTARTED, JOURNEY TRAFFIC, STILL NO SOAK

**The candidate stack was restarted between tick 2 and tick 3** (uptimes reset:
`app-1` 26s, `worker-1` 16s, `db-1` and `clamav-1` ~1m; `pg` unchanged at 48m).
Not by this loop — nothing here was touched. A restart mid-soak would invalidate a
soak run, so it is recorded here for the record; there was no soak in flight to void.

Traffic is now real but browser-journey shaped (frontend `HEAD`/`GET` route probes,
`/api/me`, `/api/cases`, `/api/runs/{id}` from the Docker gateway `172.19.0.1`), not
an eight-hour load driver. No `capacity.py`/`scenarios.py`/`probe.py` process on the host.

| Signal | tick 2 (idle) | tick 3 | Note |
|---|---|---|---|
| CPU | app 0.48%, db 0.00% | app 14.59%, db 9.36%, worker 0.00%, clamav 0.03%, pg 0.00% | load onset |
| Memory | app 133.1 MiB | app 148.6 MiB, worker 69.3 MiB, db 55.3 MiB, clamav 1021 MiB, pg 47.4 MiB | within profile |
| DB connections | 5 (1 active, 4 idle) | 9 (1 active, 8 idle) | pool fill after restart, not growth under steady state |
| Open handles (app pid 1) | 14 | 25 | ditto |
| Active jobs / permits | none | none — no build/export/freeze job in flight | |
| Checkpoint size | absent | `/data/checkpoints.db` still absent (Postgres domain store; SQLite checkpoints not on this path) | |
| Vault | 72K | 4.5M | grew with the seeded cases |
| Export storage | absent | still absent | |
| Provider usage | none | none observed (host-control style journeys) | |
| Success counts | health only | 10 runs `succeeded`, 2 `paused` (Deep Research plan gate); HTTP log has **zero** non-2xx/3xx responses | |
| Refusal counts | 0 | 0 | |
| Error classifications | none | none; no run carries an error, no typed-refusal or untyped exception in app or worker logs | |
| Live rows | `audit_chain_heads` 1 | run_events 220, run_artifacts 90, executions 90, run_nodes 85, audit_events 56, sources 24, audit_chain_heads 14, runs/cases/case_members/run_budgets 12, source_sets 10 | |
| Event classes | — | node.running 83, node.succeeded 83, run.running 12, run.created 12, run.succeeded 10, research.plan_ready 3, run.paused 3, research.plan_approved 1 | all typed |
| Orphan rows | — | `run_events` with no parent run: **0**; `source_sets` with no case: **0** | |
| Cross-case events | — | none: 10 distinct case ids across 12 runs, every event resolves to its own run | |

**No finding.** Connections and handles rose (5→9, 14→25) but the process was
replaced between the samples, so this is start-up fill, not a leak; tick 3's values
become the new steady-state reference. Nothing was touched.

Still missing for the loop's terminal step: an eight-hour soak driver, harness output,
and a recorded pre-soak baseline of authorities, model hashes, filed bytes and offline
reconstruction.

## 2026-09-03 22:14 tick 4 — LOAD RUNNING, CLEAN, SECOND RESTART RECORDED

**Second restart between ticks.** `app-1`/`worker-1` uptime 14m at 22:14, i.e. started
~22:00, while at tick 3 (21:44) they were 26s/16s old. `pg` unchanged (~1h). Not this
loop. Again there was no soak in flight to void, but two restarts in the hour before a
declared eight-hour soak are worth pinning: the soak's clock must start after the last one.

Load is now substantial and run-shaped — 309 runs, 17 concurrently `running`.
Still no `capacity.py`/`scenarios.py`/`probe.py` process on the host and no harness
output file, so the driver is external to this checkout.

| Signal | tick 3 | tick 4 | Note |
|---|---|---|---|
| CPU | app 14.59%, db 9.36% | app 69.42%, db 38.07%, worker 0.00%, clamav 0.01%, pg 0.00% | inside profile (3.813 GiB / multi-core host) |
| Memory | app 148.6 MiB | app 545.4 MiB, worker 69.6 MiB, db 126 MiB, clamav 1014 MiB, pg 38.3 MiB | app +397 MiB under 17 concurrent runs |
| DB connections | 9 (1 active, 8 idle) | 9 (1 active, 6 idle, **2 idle in transaction**) | total flat across a 20× load increase — pool is bounded, not leaking |
| Open handles (app pid 1) | 25 | 46 | rose with concurrency, not with time; watch |
| Active jobs / permits | none | `model_builds` 0, `deliverable_freeze_jobs` 0 — worker idle, log empty | |
| Checkpoint size | absent | `/data/checkpoints.db` still absent | Postgres domain store |
| Vault | 4.5M | 41M | tracks 112 cases / 2124 sources |
| Export storage | absent | still absent | nothing frozen or exported yet |
| Provider usage | none | none observed | |
| Success counts | 10 succeeded | 286 succeeded, 17 running, 2 queued, 2 paused | |
| Refusal counts | 0 | 0 | |
| Error classifications | none | **0** HTTP 4xx/5xx in the whole app log; **0** `Traceback`/`ERROR`/`Exception` lines; no run in a failed status; no run carries an error | no untyped error anywhere |
| Live rows | run_events 220 … | run_events 5777, audit_events 2532, run_nodes 2521, run_artifacts 2438, executions 2437, sources 2124, source_sets 2110, runs 309, run_budgets 300, run_snapshots 277, audit_chain_heads 114, cases 112, case_members 112, case_intakes 8 | |
| Event classes | 8 classes | node.running 2465, node.succeeded 2463, run.created 310, run.running 307, run.succeeded 289, research.plan_ready 3, run.paused 3, research.plan_approved 1 | all typed; no untyped or failure class |
| Orphan rows | 0 | orphan events **0**, orphan source_sets **0**, orphan artifacts **0** | |
| Cross-case events | none | none — every event, artifact and source set resolves to its own parent | |

**No finding.** Connections are flat (9 → 9) while load rose ~20×, which is the strongest
evidence so far against a connection leak; handles 25 → 46 scale with the 17 in-flight runs
rather than with elapsed time. The two `idle in transaction` connections are new and are the
one thing to watch: if that count climbs tick over tick it becomes a finding. Nothing touched.

## 2026-09-03 22:44 tick 5 — NO RESTART, LOAD SUSTAINED, STILL CLEAN

First tick with **no restart**: `app-1`/`worker-1` 44m uptime, consistent with the ~22:00
local start, so ticks 4 → 5 are the first same-process comparison. (Container clock is UTC,
one hour behind host local — noted so mtimes are not misread as stale.)

Checkpoints located: they are on the **vault** volume, `/vault/checkpoints.db`, not `/data`.

| Signal | tick 4 | tick 5 | Note |
|---|---|---|---|
| CPU | app 69.42%, db 38.07% | app 79.71%, db 32.42%, worker 0.11%, clamav 0.01%, pg 0.00% | inside profile |
| Memory | app 545.4 MiB | app 646.4 MiB, worker 69.7 MiB, db 176.8 MiB, clamav 1015 MiB, pg 39.7 MiB | app +101 MiB over 30 min at ~16 concurrent runs |
| DB connections | 9 (1 active, 6 idle, 2 idle-in-tx) | 9 (2 active, 7 idle, **0 idle-in-tx**) | flat at 9 for three ticks; the idle-in-transaction pair cleared — the tick-4 watch item is closed |
| Open handles (app pid 1) | 46 | 55 | breakdown: 39 sockets, 6 checkpoint-db files, 2 pipes, 1 anon_inode, 1 /dev/null — sockets are the whole delta, i.e. in-flight HTTP + pool, not retained descriptors |
| Active jobs / permits | 0 / 0 | `model_builds` 0, `deliverable_freeze_jobs` 0, worker idle (0.11% CPU, empty log) | |
| Checkpoint size | not located | 2.5 MB db + 4.4 MB WAL + 32 KB shm, written live | |
| Vault | 41M | 41M — `sources` 34M, checkpoints 6.9M | flat: the driver re-runs over existing cases, adding no sources |
| Export storage | absent | still absent | nothing frozen or exported |
| Provider usage | none | none observed | |
| Success counts | 286 succeeded, 17 running | 1037 succeeded, 16 running, 4 queued, 2 paused (1059 runs total) | +751 runs in 30 min |
| Refusal counts | 0 | 0 | |
| Error classifications | 0 | **0** HTTP 4xx/5xx; **0** Traceback/ERROR/Exception; **0** runs in a failed status | no untyped error |
| Live rows | run_events 5777 … | run_events 20650, run_nodes 8827, run_artifacts 8743, executions 8743, audit_events 3286, sources 2124, source_sets 2110, runs 1059, run_budgets 1051, run_snapshots 1029, audit_chain_heads 114, cases 112, case_members 112, case_intakes 8 | sources/source_sets/cases all flat |
| Event classes | 8, all typed | node.running 8767, node.succeeded 8767, run.created 1063, run.running 1058, run.succeeded 1041, research.plan_ready 3, run.paused 3, research.plan_approved 1 | still 8, all typed, no failure class |
| Orphan rows | 0 / 0 / 0 | orphan events **0**, orphan source_sets **0**, orphan artifacts **0** | |
| Cross-case events | none | none | |

**No finding.** The three quantities the loop watches for monotonic growth are behaving:
connections flat at 9 across a 90× rise in cumulative runs, orphans identically zero, jobs
and permits zero. Handles 46 → 55 is entirely sockets and tracks in-flight requests rather
than elapsed time. `node.running` = `node.succeeded` exactly (8767 = 8767), so no node is
stranded. Nothing touched.

Still absent: harness output, and the pre-soak baseline of authorities, model hashes,
filed bytes and offline reconstruction that the terminal comparison requires.

## 2026-09-03 23:14 tick 6 — FINDING F1: app file handles rising at flat concurrency

No restart (uptime ~1h, same process as tick 5). Load steady.

| Signal | tick 4 | tick 5 | tick 6 | Note |
|---|---|---|---|---|
| CPU | app 69.42%, db 38.07% | app 79.71%, db 32.42% | app 69.03%, db 36.61%, worker 0.12%, clamav 0.01%, pg 0.00% | flat, inside profile |
| Memory | app 545.4 MiB | app 646.4 MiB | app 547.7 MiB, worker 69.6 MiB, db 181.4 MiB, clamav 1011 MiB, pg 37.0 MiB | app **fell** 646 → 548 MiB — no memory leak |
| DB connections | 9 | 9 | 9 (2 active, 7 idle) | flat for four ticks |
| **Open handles (app pid 1)** | **46** | **55** | **61** | **rising — see F1** |
| — of which sockets | 39 | 39 | 51 | |
| Active jobs / permits | 0 / 0 | 0 / 0 | `model_builds` 0, `deliverable_freeze_jobs` 0 | worker idle |
| Checkpoint size | — | 2.5 MB + 4.4 MB WAL | 2.5 MB db + 4.4 MB WAL + 32 KB shm | unchanged |
| Vault | 41M | 41M | 41M (sources 34M, checkpoints 6.9M) | flat |
| Export storage | absent | absent | absent | |
| Provider usage | none | none | none observed | |
| Success counts | 286 succ / 17 run | 1037 succ / 16 run / 4 q / 2 paused | 1779 succ / 16 run / 4 q / 2 paused (1801 total) | +742 runs in 30 min |
| Refusal counts | 0 | 0 | 0 | |
| Error classifications | 0 | 0 | **0** HTTP 4xx/5xx, **0** Traceback/ERROR/Exception, **0** failed runs | no untyped error |
| Live rows | run_events 5777 | 20650 | run_events 35389, run_nodes 15093, run_artifacts 14778, executions 14567, audit_events 3881, sources 2124, source_sets 2110, runs 1801, run_budgets 1791, run_snapshots 1774, audit_chain_heads 114, cases 112, case_members 112 | sources/cases flat |
| Event classes | 8, typed | 8, typed | 8, typed; node.running 15004 vs node.succeeded 15003 (one node in flight) | no failure class |
| Orphan rows | 0/0/0 | 0/0/0 | **0/0/0** | |
| Cross-case events | none | none | none | |

### F1 — app open file handles grew 46 → 55 → 61 across three ticks while concurrency was flat

**Evidence.** Same process throughout (no restart since ~22:00 local). Concurrent load was
identical at ticks 5 and 6 — 16 `running`, 4 `queued`, 2 `paused` in both samples — yet the
app's fd count rose 55 → 61, and the socket share of those fds rose 39 → 51. Non-socket fds
are constant at 10 (6 checkpoint-db files, 2 pipes, 1 anon_inode, 1 /dev/null).

Socket detail at tick 6, from `/proc/1/net/tcp{,6}`:

- TIME_WAIT (`06`) **785**, ESTABLISHED (`01`) **46**, LISTEN (`0A`) 2, CLOSE_WAIT (`08`) **0**
- Of the 46 established: **15 to remote port 0x1538 = 5432 (PostgreSQL)**, the remaining ~31
  to ephemeral client ports (inbound HTTP)
- fd socket-inode spread 17726357 … 18512169 — the low end is old, i.e. some sockets held
  since well before this tick

**What this is not.** There is no CLOSE_WAIT backlog, which is the signature of leaked
accepted sockets; app RSS *fell* over the same interval (646 → 548 MiB); and the domain
pool is flat at 9 sessions on `caos`. So this is not a runaway descriptor leak, and the
process is nowhere near a default 1024 soft limit.

**What is unexplained.** The app holds **15** established sockets to 5432 while
`pg_stat_activity` reports **9** sessions on the `caos` database — a six-socket gap, and the
growth is on the socket side only. The candidates are inbound keep-alive connections held
open by the driver, long-lived SSE run-event tails, or pool sockets counted against another
database. Distinguishing them needs one more same-process sample at flat concurrency.

**Status: open, watch.** Two more ticks at 16 concurrent runs will settle it — if handles keep
climbing while `pg_stat_activity` stays at 9 and CLOSE_WAIT stays 0, it is an inbound-connection
retention issue rather than a pool leak. Nothing was touched.

## 2026-09-03 23:44 tick 7 — F1 REFUTED AND CLOSED

No restart (uptime 2h, same process as ticks 5–6).

**F1 does not hold.** The handle count reversed: 46 → 55 → 61 → **39**. Sockets fell
51 → 29, established sockets 46 → 26, and sockets to PostgreSQL 15 → **6**. The growth
tracked in-flight work and drained; it was never monotonic. The 15-vs-9 gap flagged at
tick 6 also closed on its own (6 app sockets to 5432 now, against 14 DB sessions), which
confirms the reading that those were transient connections in flight, not retained
descriptors. **F1 is closed as not-a-defect.** No change was made to produce this — the
process is the same one, untouched.

| Signal | tick 5 | tick 6 | tick 7 | Note |
|---|---|---|---|---|
| CPU | app 79.71%, db 32.42% | app 69.03%, db 36.61% | app 72.44%, db 37.27%, worker 0.12%, clamav 0.01%, pg 0.00% | steady, inside profile |
| Memory | app 646.4 MiB | app 547.7 MiB | app 638.0 MiB, worker 69.6 MiB, db 178.7 MiB, clamav 1014 MiB, pg 37.8 MiB | oscillates 548–646 MiB, no trend |
| DB connections | 9 | 9 | **14** (2 active, 8 idle, 4 idle-in-tx) | up; the 4 idle-in-tx had already cleared when re-queried seconds later — transient, as at tick 4 |
| Open handles | 55 | 61 | **39** | reversed; F1 refuted |
| — sockets | 39 | 51 | 29 | |
| — TCP states | — | TIME_WAIT 785, ESTAB 46, LISTEN 2, CLOSE_WAIT 0 | TIME_WAIT 817, ESTAB 26, LISTEN 2, **CLOSE_WAIT 0** | CLOSE_WAIT stays zero |
| — sockets to 5432 | — | 15 | 6 | gap closed |
| Active jobs / permits | 0 / 0 | 0 / 0 | `model_builds` 0, `deliverable_freeze_jobs` 0 | worker idle for 2h |
| Checkpoint size | 2.5M + 4.4M WAL | same | 2.5M db + 4.4M WAL + 32K shm | unchanged across 4 ticks |
| Vault | 41M | 41M | 41M (sources 34M) | flat |
| Export storage | absent | absent | absent | nothing frozen or exported |
| Provider usage | none | none | none observed | |
| Success counts | 1037 succ | 1779 succ | 2524 succ / 13 running / 7 queued / 2 paused (2546 total) | +745 runs in 30 min, steady rate |
| Refusal counts | 0 | 0 | 0 | |
| Error classifications | 0 | 0 | **0** HTTP 4xx/5xx, **0** Traceback/ERROR/Exception, **0** failed runs | still no untyped error |
| Live rows | run_events 20650 | 35389 | run_events 50183, run_nodes 21329, executions 21282, run_artifacts 21282, audit_events 4771, runs 2546, run_budgets 2538, run_snapshots 2516, sources 2124, source_sets 2110, audit_chain_heads 114, cases 112 | sources/cases flat at 2124/112 |
| Event classes | 8, typed | 8, typed | 8, typed; node.running 21284 vs node.succeeded 21283 (one in flight) | no failure class in 50,183 events |
| Orphan rows | 0/0/0 | 0/0/0 | **0/0/0** | |
| Cross-case events | none | none | none | |

**No open finding.** Connections rose 9 → 14, which is the one quantity to carry into tick 8;
it is not yet growth (it was 9 for four consecutive ticks and the idle-in-tx entries drained
within seconds). Nothing touched.

## 2026-09-04 00:14 tick 8 — CONNECTION SPIKE INVESTIGATED AND REFUTED; WORKER CONTAINER REPLACED

Two things moved. Neither is a defect.

**(a) The connection "growth" is a sampling artefact.** The first sample this tick read
**18** sessions on `caos` (1 active, 9 idle, 8 idle-in-transaction), which alongside 9 → 9 →
9 → 14 would have read as monotonic growth. It is not. Three consecutive counts taken
immediately after returned **9, 9, 9**. Inspecting the idle-in-transaction sessions while
they existed:

```
pid 122447  idle in transaction  age -00:00:00.004903  SELECT sources.id, sources.case_id, ...
pid 122443  idle in transaction  age -00:00:00.005380  SELECT sources.id, sources.case_id, ...
pid 122444  idle in transaction  age -00:00:00.005204  SELECT run_nodes.id, run_nodes.run_id, ...
pid 122446  idle in transaction  age -00:00:00.005929  BEGIN
```

Ages are **milliseconds** — ordinary in-flight transactions caught between statements, not
sessions parked with work held open. Granted locks at the same instant: 3 ExclusiveLock,
1 AccessShareLock. The pool's steady state is 9; bursts are concurrency, not retention.
**No finding.**

**(b) The worker container was replaced between ticks.** `worker-1` uptime 10 min against
`app-1`/`db-1` at 2 h; `RestartCount 0`, `ExitCode 0`, `StartedAt 2026-09-03T23:03:45Z`
(= 00:03 local). RestartCount 0 with a fresh start time means Docker did not restart it —
the container was recreated by someone outside this loop. Recorded for the same reason as
the tick 3 and tick 4 restarts: **this loop touched nothing**, and any eight-hour soak clock
must start after the last such intervention.

| Signal | tick 6 | tick 7 | tick 8 | Note |
|---|---|---|---|---|
| CPU | app 69.03%, db 36.61% | app 72.44%, db 37.27% | app 85.17%, db 37.51%, worker 0.12%, clamav 0.01%, pg 0.00% | inside profile |
| Memory | app 547.7 MiB | app 638.0 MiB | app 556.7 MiB, worker 69.5 MiB, db 224.3 MiB, clamav 1020 MiB, pg 36.1 MiB | app oscillates 548–646 MiB with no trend across 4 ticks; db creeping 126 → 177 → 179 → 224 MiB |
| DB connections | 9 | 14 | **9** (steady; 18 momentarily) | see (a) |
| Open handles | 61 | 39 | 52 | oscillating, confirms F1 closed |
| — TCP states | TW 785, EST 46, CW 0 | TW 817, EST 26, CW 0 | TW 856, EST 44, LISTEN 2, **CLOSE_WAIT 0** | CLOSE_WAIT zero for three ticks |
| Active jobs / permits | 0 / 0 | 0 / 0 | `model_builds` 0, `deliverable_freeze_jobs` 0 | worker still idle after replacement |
| Checkpoint size | 2.5M + 4.4M WAL | same | 2.5M db + 4.4M WAL + 32K shm | unchanged across 5 ticks |
| Vault | 41M | 41M | 41M (sources 34M) | flat |
| Export storage | absent | absent | absent | |
| Provider usage | none | none | none observed | |
| Success counts | 1779 succ | 2524 succ | 3274 succ / 16 running / 3 queued / 2 paused (3295 total) | +749 runs, rate steady for four ticks (751, 742, 745, 749) |
| Refusal counts | 0 | 0 | 0 | |
| Error classifications | 0 | 0 | **0** HTTP 4xx/5xx, **0** Traceback/ERROR/Exception, **0** failed runs | no untyped error in 3295 runs |
| Live rows | run_events 35389 | 50183 | run_events 62360, run_nodes 27630, executions 27573, run_artifacts 27573, audit_events 5520, runs 3295, run_budgets 3288, run_snapshots 3265, sources 2124, source_sets 2110, audit_chain_heads 114, cases 112 | sources/cases still flat at 2124/112 |
| Event classes | 8, typed | 8, typed | 8, typed; node.running 27576 vs node.succeeded 27575 | no failure class in 62,360 events |
| Orphan rows | 0/0/0 | 0/0/0 | **0/0/0** | |
| Cross-case events | none | none | none | |

**No open finding.** One value to carry: db container memory 126 → 177 → 179 → 224 MiB is
the only quantity rising across four ticks; at 224 MiB of 3.813 GiB it is unremarkable for a
PostgreSQL cache warming under sustained load, but it is now the tracked series. Nothing touched.

## 2026-09-04 00:19 tick 9 — SHORT TICK (5 min after tick 8), ALL CLEAN

This tick fired 5 minutes after tick 8 rather than 30, so the deltas are one-sixth of a
normal interval and carry proportionally less signal.

| Signal | tick 8 (00:14) | tick 9 (00:19) | Note |
|---|---|---|---|
| CPU | app 85.17%, db 37.51% | app 76.59%, db 42.58%, worker 0.20%, clamav 0.01%, pg 0.00% | inside profile |
| Memory | app 556.7 MiB, db 224.3 MiB | app 506.7 MiB, db 249.9 MiB, worker 69.5 MiB, clamav 1020 MiB, pg 36.1 MiB | app fell again (range 507–646 across 5 ticks, no trend) |
| DB connections | 9 (three samples) | **9, 9, 9** | steady state confirmed a second time |
| Open handles | 52 | 62 | oscillating in 39–62 band; F1 stays closed |
| — TCP states | TW 856, EST 44, CW 0 | TW **671**, EST 46, LISTEN 2, **CLOSE_WAIT 0** | TIME_WAIT fell 856 → 671, i.e. the kernel is draining, not accumulating |
| Active jobs / permits | 0 / 0 | `model_builds` 0, `deliverable_freeze_jobs` 0 | worker idle since replacement |
| Checkpoint size | 2.5M + 4.4M WAL | 2.5M db + 4.4M WAL + 32K shm | unchanged, 6 ticks |
| Vault | 41M | 41M (sources 34M) | flat |
| Export storage | absent | absent | |
| Provider usage | none | none observed | |
| Success counts | 3274 succ / 16 run / 3 q / 2 paused | 3393 succ / 16 running / 3 queued / 2 paused (3414 total) | +119 runs in 5 min ≈ 714/30 min, same rate |
| Refusal counts | 0 | 0 | |
| Error classifications | 0 | **0** HTTP 4xx/5xx, **0** Traceback/ERROR/Exception, **0** failed runs | |
| Live rows | run_events 62360 | run_events 67358, sources 2124, cases 112 | corpus still fixed |
| Event classes | 8, typed | 8, typed; node.running 28567 **=** node.succeeded 28567 (nothing in flight at the sample) | no failure class in 67,358 events |
| Orphan rows | 0/0/0 | **0/0/0** | |
| Cross-case events | none | none | |

**db memory series resolved, not a finding.** 126 → 177 → 179 → 224 → 250 MiB. `shared_buffers`
is 16384 × 8 kB = **128 MiB**, so the resident set is a bounded shared-buffer pool plus per-backend
memory, converging rather than growing without limit. At 250 MiB of 3.813 GiB it is 6.4% of the
host allowance.

**No open finding.** Nothing touched.

## 2026-09-04 05:57 tick 10 — STACK REPLACED, 5h38m COVERAGE GAP, **FINDING F2: ClamAV OOM-killed**

Three structural facts before the numbers:

1. **The Compose project was replaced.** Ticks 1–9 watched `caos-cand-20260903-*`; those
   containers no longer exist. The live stack is `caos-cand-20260904-*`, `app`/`db` up 5 h
   (started ~00:57 local), `worker` up 35 min, `pg` up 6 h. Not this loop.
2. **The database survived the replacement** — runs 3414 → 3682 and run_events 67,358 →
   72,713 continue the tick-9 series, so the evidence chain is intact even though every
   process is new.
3. **Coverage gap: 00:19 → 05:57 local (5 h 38 min) went unobserved** — the loop did not fire.
   Anything that happened in that window is not in this record.

### F2 — the ClamAV container was OOM-killed and clamd is not answering

**Evidence.**

```
docker inspect …-clamav-1 --format '{{.HostConfig.Memory}} {{.State.OOMKilled}} {{.RestartCount}}'
0 true 0
```

- `OOMKilled: true`, `RestartCount: 0` — the container was never restarted, so it is up but
  its clamd is gone; `ps` inside shows `[clamd]` in brackets (no live command line) beside a
  running freshclam.
- Healthcheck: **5 consecutive failures, exit 21**, output `PING timeout exceeded; No response from clamd`.
- Container RSS collapsed **1020 MiB → 45.28 MiB** between tick 9 and tick 10.
- Its own log stops at **03:27:28** (`SelfCheck: Database status OK`) — silent for ~2.5 h.
- No memory limit is set on the container (`HostConfig.Memory 0`), so this was host-level
  pressure, with ~175 MB of signatures (`main.cvd` 89 MB + `daily.cld` 86 MB) loaded under
  **qemu-x86_64 emulation** (the process list shows every binary wrapped by `/usr/bin/qemu-x86_64`).

**Consequence for the soak.** Source admission has stopped. All 8,024 `sources` rows were
created inside the 00:00 UTC hour and the newest is **00:20:45 UTC**; there have been **zero**
`POST /api/intake` requests in the app log since. The soak is therefore no longer exercising
the admission path at all — runs continue against already-admitted sources. This is a gap in
what the soak proves, not a corruption of what it has proved.

**Not an untyped error.** The app log still carries **0** HTTP 4xx/5xx and **0**
Traceback/ERROR/Exception lines. Nothing attempted an ingest and got an unhandled failure;
the driver simply stopped ingesting. The scanner-down refusal path is consequently
**unproven by this soak**.

**Status: open.** Nothing was touched — no restart, no scale, no reconfigure.

| Signal | tick 9 (20260903 stack) | tick 10 (20260904 stack) | Note |
|---|---|---|---|
| CPU | app 76.59%, db 42.58% | app 79.47%, db 50.51%, worker 0.03%, clamav 0.01%, pg 0.00% | inside profile |
| Memory | app 506.7, db 249.9, clamav 1020 MiB | app 696.9, db 187.4, worker 83.8, **clamav 45.3**, pg 36.9 MiB | clamav collapse is F2 |
| DB connections | 9, 9, 9 | **10, 9, 9** | steady state 9 across a whole stack replacement |
| Open handles | 62 | 61 | band 39–62 holds; F1 stays closed |
| — TCP states | TW 671, EST 46, CW 0 | TW 951, EST 61, LISTEN 2, **CLOSE_WAIT 0** | CLOSE_WAIT zero for five ticks |
| Active jobs / permits | 0 / 0 | `model_builds` 0, `deliverable_freeze_jobs` 0 | worker has never claimed a job in 10 ticks |
| Checkpoint size | 2.5M db + 4.4M WAL | **5.7M db + 4.6M WAL** + 32K shm | first movement — grew with the larger corpus |
| Vault | 41M (sources 34M) | sources **57M** + checkpoints 10.3M | grew with the 8,024-source corpus |
| Export storage | absent | absent | nothing frozen or exported in 10 ticks |
| Provider usage | none | none observed | |
| Success counts | 3393 succ / 16 run | 3660 succ / 12 running / 8 queued / 2 paused (3682 total) | |
| Refusal counts | 0 | 0 | |
| Error classifications | 0 | **0** HTTP 4xx/5xx, **0** Traceback/ERROR/Exception, **0** failed runs | |
| Live rows | run_events 67358, sources 2124 | run_events 72713, run_nodes 30906, executions 30758, run_artifacts 30486, audit_events 11806, sources **8024**, source_sets 8010, runs 3682, run_budgets 3671, run_snapshots 3651, audit_chain_heads 114, case_members 113, cases 112 | sources 2124 → 8024 during the gap |
| Event classes | 8, typed | 8, typed; node.running 30864 **=** node.succeeded 30864 | no failure class in 72,713 events |
| Orphan rows | 0/0/0 | **0/0/0** | ten consecutive ticks at zero |
| Cross-case events | none | none | |

## 2026-09-04 06:14 tick 11 — F2 PERSISTS, FIRST CLOSE_WAIT SEEN, OTHERWISE CLEAN

No restart (same processes as tick 10). **F2 is unchanged and still open**: clamav
`unhealthy`, `OOMKilled=true`, `RestartCount=0`, RSS pinned at 45.3 MiB. Newest `sources`
row is still **2026-09-04T00:20:45Z** and `sources` is still 8024 — admission has now been
stopped for ~6 hours of wall clock.

| Signal | tick 10 | tick 11 | Note |
|---|---|---|---|
| CPU | app 79.47%, db 50.51% | app 85.43%, db 47.23%, worker 0.00%, clamav 0.01%, pg 0.00% | inside profile |
| Memory | app 696.9, db 187.4, clamav 45.3 MiB | app 696.1, db 190.9, worker 83.8, clamav 45.3, pg 36.9 MiB | app flat to 0.8 MiB over 17 min |
| DB connections | 10, 9, 9 | **9, 9, 9** | steady state 9 for six ticks |
| Open handles | 61 | **82** | rising again — see note |
| — TCP states | TW 951, EST 61, CW 0 | TW **1154**, EST **76**, LISTEN 2, **CLOSE_WAIT 2** | first CLOSE_WAIT of the watch |
| Active jobs / permits | 0 / 0 | `model_builds` 0, `deliverable_freeze_jobs` 0 | worker has claimed nothing in 11 ticks |
| Checkpoint size | 5.7M db + 4.6M WAL | 5.7M db + 4.6M WAL + 32K shm | flat |
| Vault | sources 57M + checkpoints 10.3M | unchanged | flat, consistent with admission being stopped |
| Export storage | absent | absent | |
| Provider usage | none | none observed | |
| Success counts | 3660 succ / 12 run / 8 q | 3876 succ / 17 running / 2 queued / 2 paused (3897 total) | +215 runs in 17 min ≈ 380/30 min — **about half the 20260903 rate** (~745), consistent with a larger 8,024-source corpus per run |
| Refusal counts | 0 | 0 | |
| Error classifications | 0 | **0** HTTP 4xx/5xx, **0** Traceback/ERROR/Exception, **0** failed runs | |
| Live rows | run_events 72713, sources 8024 | run_events 76982, sources 8024, cases 112 | corpus frozen by F2 |
| Event classes | 8, typed | 8, typed; node.running 32654 vs node.succeeded 32653 | no failure class in 76,982 events |
| Orphan rows | 0/0/0 | **0/0/0** | eleven consecutive ticks at zero |
| Cross-case events | none | none | |

**Handles 61 → 82: not yet a finding.** The same quantity was raised as F1 at tick 6 and
refuted at tick 7 when it fell to 39; the band across eleven ticks is 39–82 with no trend.
Concurrency also rose this tick (12 → 17 running), which accounts for the direction. The
**2 CLOSE_WAIT** are new and are the specific thing to watch: CLOSE_WAIT was exactly 0 for
five consecutive ticks, and unlike TIME_WAIT it does not drain on its own — if it climbs
tick over tick that is a genuine descriptor leak, distinct from the socket churn F1 turned
out to be. Two is noise; the series is now tracked.

Nothing touched.

## 2026-09-04 06:44 tick 12 — CLOSE_WAIT WATCH CLEARED, F2 STILL OPEN

No restart. **F2 unchanged**: clamav `unhealthy`, `OOMKilled=true`, `RestartCount=0`,
RSS 45.1 MiB, newest `sources` row still **2026-09-04T00:20:45Z**, `sources` still 8024.
Admission has been stopped for ~6.5 hours.

| Signal | tick 10 | tick 11 | tick 12 | Note |
|---|---|---|---|---|
| CPU | app 79.47% | app 85.43% | **app 96.25%**, db 40.21%, worker 0.14%, clamav 0.01%, pg 0.00% | app near one-core saturation; highest of the watch |
| Memory | app 696.9, db 187.4 | app 696.1, db 190.9 | app 708.1, db 189.7, worker 83.8, clamav 45.1, pg 36.9 MiB | app band 507–708 MiB over 12 ticks |
| DB connections | 10, 9, 9 | 9, 9, 9 | **9, 9, 17** | same burst pattern as tick 8; steady state still 9 |
| Open handles | 61 | 82 | 89 | |
| — TCP states | TW 951, EST 61, **CW 0** | TW 1154, EST 76, **CW 2** | TW **1058**, EST 81, LISTEN 2, **CLOSE_WAIT 0** | |
| Active jobs / permits | 0 / 0 | 0 / 0 | `model_builds` 0, `deliverable_freeze_jobs` 0 | nothing claimed in 12 ticks |
| Checkpoint size | 5.7M + 4.6M WAL | same | 5.7M db + 4.6M WAL + 32K shm | flat 3 ticks |
| Vault | sources 57M | unchanged | sources 57M + checkpoints 10.3M | flat, consistent with F2 |
| Export storage | absent | absent | absent | nothing frozen or exported in 12 ticks |
| Provider usage | none | none | none observed | |
| Success counts | 3660 succ | 3876 succ | 4262 succ / 15 running / 5 queued / 2 paused (4284 total) | +387 runs in 30 min, matching tick 11's projected ~380 |
| Refusal counts | 0 | 0 | 0 | |
| Error classifications | 0 | 0 | **0** HTTP 4xx/5xx, **0** Traceback/ERROR/Exception, **0** failed runs | |
| Live rows | run_events 72713 | 76982 | run_events 84700, sources 8024, cases 112 | |
| Event classes | 8, typed | 8, typed | 8, typed; node.running 35934 **=** node.succeeded 35934 | no failure class in 84,700 events |
| Orphan rows | 0/0/0 | 0/0/0 | **0/0/0** | twelve consecutive ticks at zero |
| Cross-case events | none | none | none | |

**CLOSE_WAIT watch closed.** It went 0 → 2 → **0**, so the tick-11 pair drained; there is no
descriptor leak. Handles 61 → 82 → 89 continue to move with concurrency inside a 39–89 band
and TIME_WAIT fell 1154 → 1058 over the same interval, i.e. the kernel is retiring sockets
faster than new ones accumulate. Neither quantity is monotonic. **No new finding.**

The one number worth naming is app CPU at **96.25%** — the highest of the watch and close to
saturation of a single core. It has risen 79 → 85 → 96 across three ticks while throughput
held steady at ~380 runs per 30 min, so the app is doing the same work for more CPU. If it
pins at ~100% with throughput falling, that is the saturation boundary of the declared
profile and becomes a finding; at present throughput is flat, so it is recorded, not raised.

Nothing touched.

## 2026-09-04 07:14 tick 13 — CLOSE_WAIT SPIKE REFUTED, F2 STILL OPEN, APP RSS NOW THE TRACKED SERIES

No restart (app/db 6 h, same processes). **F2 unchanged**: clamav `unhealthy`,
`OOMKilled=true`, `RestartCount=0`, RSS 45.1 MiB; `sources` still 8024, newest still
**00:20:45Z**. Admission stopped ~7 hours.

| Signal | tick 11 | tick 12 | tick 13 | Note |
|---|---|---|---|---|
| CPU | app 85.43%, db 47.23% | app **96.25%**, db 40.21% | app **79.56%**, db 45.57%, worker 0.00%, clamav 0.01%, pg 0.00% | the 96% was transient — the tick-12 saturation watch is closed |
| Memory | app 696.1 | app 708.1 | **app 742.1**, db 189.6, worker 83.8, clamav 45.1, pg 36.9 MiB | app rising four ticks — see note |
| DB connections | 9, 9, 9 | 9, 9, 17 | **9, 9, 9** | steady state 9 for eight ticks |
| Open handles | 82 | 89 | 89 | flat |
| — TCP states | TW 1154, EST 76, CW 2 | TW 1058, EST 81, CW 0 | TW **1171**, EST 69, LISTEN 2, CW **7 → 0, 0, 0** | see note |
| Active jobs / permits | 0 / 0 | 0 / 0 | `model_builds` 0, `deliverable_freeze_jobs` 0 | nothing claimed in 13 ticks |
| Checkpoint size | 5.7M + 4.6M WAL | same | 5.7M db + 4.6M WAL + 32K shm | flat 4 ticks |
| Vault | sources 57M | same | sources 57M + checkpoints 10.3M | flat, consistent with F2 |
| Export storage | absent | absent | absent | nothing frozen or exported in 13 ticks |
| Provider usage | none | none | none observed | |
| Success counts | 3876 succ | 4262 succ | 4658 succ / 15 running / 5 queued / 2 paused (4680 total) | +396 runs in 30 min; rate steady at ~390 for three ticks |
| Refusal counts | 0 | 0 | 0 | |
| Error classifications | 0 | 0 | **0** HTTP 4xx/5xx, **0** Traceback/ERROR/Exception, **0** failed runs | |
| Live rows | run_events 76982 | 84700 | run_events 92423, sources 8024, cases 112 | |
| Event classes | 8, typed | 8, typed | 8, typed; node.running 39202 vs node.succeeded 39201 | no failure class in 92,423 events |
| Orphan rows | 0/0/0 | 0/0/0 | **0/0/0** | thirteen consecutive ticks at zero |
| Cross-case events | none | none | none | |

**CLOSE_WAIT spike refuted.** The first sample read 7 — the highest of the watch — but three
immediate rechecks returned **0, 0, 0**, and the sockets were gone before their remote ports
could be read. They were closed within seconds of the peer's FIN, which is correct behaviour,
not retention. Series across the watch: 0,0,0,0,0,2,0,7→0. Not monotonic; **no finding**.

**New tracked series: app RSS.** 696.9 → 696.1 → 708.1 → **742.1 MiB** across four ticks, the
first quantity in this watch to rise four samples running. Two things argue against calling it
a leak yet: the same process oscillated 507–708 MiB earlier without trending, and 742 MiB is
19% of the 3.813 GiB host allowance. But unlike handles and CLOSE_WAIT it has not reversed
once. It is not one of the quantities the loop names for findings (connections, handles, jobs,
permits, orphan rows), so it is recorded as a watch item; two more rising ticks with flat
throughput would make it worth raising.

Nothing touched.

## 2026-09-04 07:44 tick 14 — APP RSS WATCH CLOSED, CONNECTION POOL RESOLVED, F2 STILL OPEN

No app/db restart (6 h). `worker-1` was replaced again (22 min uptime) — the third such
intervention from outside this loop; recorded, not caused here. **F2 unchanged**: clamav
`unhealthy`, `OOMKilled=true`, `RestartCount=0`, RSS 45.1 MiB; `sources` still 8024.
Admission stopped ~7.5 hours.

| Signal | tick 12 | tick 13 | tick 14 | Note |
|---|---|---|---|---|
| CPU | app 96.25%, db 40.21% | app 79.56%, db 45.57% | app 79.39%, db 44.09%, worker 0.00%, clamav 0.01%, pg 0.00% | steady |
| Memory | app 708.1 | app **742.1** | app **646.1**, db 191.5, worker 67.6, clamav 45.1, pg 36.9 MiB | reversed — see note |
| DB connections | 9, 9, 17 | 9, 9, 9 | **13, 18, 18** then **9, 9, 9, 9, 18** | resolved — see note |
| Open handles | 89 | 89 | 103 | band now 39–103, still non-monotonic |
| — TCP states | TW 1058, EST 81, CW 0 | TW 1171, EST 69, CW 7→0 | TW 1130, EST 92, LISTEN 2, **CLOSE_WAIT 0** | |
| Active jobs / permits | 0 / 0 | 0 / 0 | `model_builds` 0, `deliverable_freeze_jobs` 0 | nothing claimed in 14 ticks |
| Checkpoint size | 5.7M + 4.6M WAL | same | 5.7M db + 4.6M WAL + 32K shm | flat 5 ticks |
| Vault | sources 57M | same | sources 57M + checkpoints 10.3M | flat, consistent with F2 |
| Export storage | absent | absent | absent | nothing frozen or exported in 14 ticks |
| Provider usage | none | none | none observed | |
| Success counts | 4262 succ | 4658 succ | 5047 succ / 15 running / 5 queued / 2 paused (5069 total) | +389 runs in 30 min; rate ~390 for four consecutive ticks |
| Refusal counts | 0 | 0 | 0 | |
| Error classifications | 0 | 0 | **0** HTTP 4xx/5xx, **0** Traceback/ERROR/Exception, **0** failed runs | |
| Live rows | run_events 84700 | 92423 | run_events 100181, sources 8024, cases 112 | |
| Event classes | 8, typed | 8, typed | 8, typed; node.running 42498 vs node.succeeded 42497 | no failure class in 100,181 events |
| Orphan rows | 0/0/0 | 0/0/0 | **0/0/0** | fourteen consecutive ticks at zero |
| Cross-case events | none | none | none | |

**App RSS watch closed.** The four-tick rise 696.9 → 696.1 → 708.1 → 742.1 reversed to
**646.1 MiB**. Over fourteen ticks the app has oscillated 507–742 MiB with no trend. Not a leak.

**Connection pool resolved.** The first three samples read 13, 18, 18 — the first time the
count sat above 9 across consecutive reads. Five further samples gave **9, 9, 9, 9, 18**, so
the distribution is bimodal, not rising. Composition at the burst: `172.19.0.4` (app) **6**,
`172.19.0.5` (worker) **2**, plus 1 local — oldest idle session 1.98 s, the single
idle-in-transaction aged in milliseconds. Steady state is 9 with short bursts to ~18 under
concurrency. Not monotonic; **no finding**.

Every quantity the loop names for findings has now been tested and cleared at least once:
connections (bimodal 9/18, resolved here), handles (39–103, F1 refuted at tick 7), jobs and
permits (identically 0 across fourteen ticks), orphan rows (0/0/0 across fourteen ticks).
No cross-case event has appeared in 100,181 events, and no fault has produced an untyped
error — the app log carries zero 4xx/5xx and zero exception lines for the whole watch.

**F2 remains the only open finding.** Nothing touched.

## 2026-09-04 08:14 tick 15 — STEADY, F2 STILL THE ONLY OPEN FINDING

No app/db restart (7 h). `worker-1` 52 min, consistent with the tick-14 replacement — no new
intervention. **F2 unchanged**: clamav `unhealthy`, `OOMKilled=true`, `RestartCount=0`,
RSS 45.1 MiB, CPU now 0.00%; `sources` still 8024. Admission stopped ~8 hours.

| Signal | tick 13 | tick 14 | tick 15 | Note |
|---|---|---|---|---|
| CPU | app 79.56%, db 45.57% | app 79.39%, db 44.09% | app 81.36%, db 36.06%, worker 0.12%, clamav 0.00%, pg 0.00% | steady three ticks |
| Memory | app 742.1 | app 646.1 | app 694.9, db 193.6, worker 67.6, clamav 45.1, pg 36.9 MiB | inside the 507–742 MiB band; RSS watch stays closed |
| DB connections | 9, 9, 9 | 13,18,18 / 9,9,9,9,18 | **9, 15, 15, 14, 12** | bimodal as resolved at tick 14; steady floor 9 |
| Open handles | 89 | 103 | **63** | reversed again; band 39–103 over fifteen ticks |
| — TCP states | TW 1171, EST 69, CW 7→0 | TW 1130, EST 92, CW 0 | TW 1055, EST 49, LISTEN 2, CW **2** | TIME_WAIT falling three ticks (1171→1130→1055) |
| Active jobs / permits | 0 / 0 | 0 / 0 | `model_builds` 0, `deliverable_freeze_jobs` 0 | nothing claimed in 15 ticks |
| Checkpoint size | 5.7M + 4.6M WAL | same | 5.7M db + 4.6M WAL + 32K shm | flat 6 ticks |
| Vault | sources 57M | same | sources 57M + checkpoints 10.3M | flat, consistent with F2 |
| Export storage | absent | absent | absent | nothing frozen or exported in 15 ticks |
| Provider usage | none | none | none observed | |
| Success counts | 4658 succ | 5047 succ | 5435 succ / 15 running / 4 queued / 2 paused (5456 total) | +387 runs in 30 min; rate ~390 for five consecutive ticks |
| Refusal counts | 0 | 0 | 0 | |
| Error classifications | 0 | 0 | **0** HTTP 4xx/5xx, **0** Traceback/ERROR/Exception, **0** failed runs | |
| Live rows | run_events 92423 | 100181 | run_events 107960, sources 8024, cases 112 | |
| Event classes | 8, typed | 8, typed | 8, typed; node.running 45805 **=** node.succeeded 45805 | no failure class in 107,960 events |
| Orphan rows | 0/0/0 | 0/0/0 | **0/0/0** | fifteen consecutive ticks at zero |
| Cross-case events | none | none | none | |

**No new finding.** Handles reversed 103 → 63 and the 2 CLOSE_WAIT sit inside the noise band
already characterised at ticks 11–13. Throughput has been flat at ~390 runs per 30 minutes for
five consecutive ticks while CPU held at ~80%, so the app is inside the declared profile with
headroom; nothing is degrading.

**F2 remains the only open finding, and it now bounds what this soak can claim.** Admission has
been dead for eight hours of a run whose purpose is to exercise the stack under sustained load:
every one of the 5,456 runs executed against the same 8,024 sources admitted before 00:20:45Z.
The soak is evidence for run execution, event integrity and resource stability; it is **not**
evidence for intake, scanning, or the scanner-down refusal path.

Nothing touched.

## 2026-09-04 08:44 tick 16 — STEADY, F2 STILL THE ONLY OPEN FINDING

No restarts. **F2 unchanged**: clamav `unhealthy`, `OOMKilled=true`, `RestartCount=0`,
RSS 45.1 MiB, CPU 0.00%; `sources` still 8024. Admission stopped ~8.5 hours.

| Signal | tick 14 | tick 15 | tick 16 | Note |
|---|---|---|---|---|
| CPU | app 79.39%, db 44.09% | app 81.36%, db 36.06% | app 93.50%, db 40.87%, worker 0.00%, clamav 0.00%, pg 0.00% | second excursion into the 90s (tick 12 was 96.25%); throughput unaffected |
| Memory | app 646.1 | app 694.9 | app 744.1, db 195.2, worker 67.6, clamav 45.1, pg 36.9 MiB | top of the 507–744 MiB band, not beyond it |
| DB connections | 13,18,18 / 9,9,9,9,18 | 9,15,15,14,12 | **9, 18, 18, 18, 18** | bimodal 9/18 exactly as characterised at tick 14 |
| Open handles | 103 | 63 | 68 | band 39–103 across sixteen ticks |
| — TCP states | TW 1130, EST 92, CW 0 | TW 1055, EST 49, CW 2 | TW 1097, EST 54, LISTEN 2, CW **1** | CLOSE_WAIT noise band 0–7, never retained |
| Active jobs / permits | 0 / 0 | 0 / 0 | `model_builds` 0, `deliverable_freeze_jobs` 0 | nothing claimed in 16 ticks |
| Checkpoint size | 5.7M + 4.6M WAL | same | 5.7M db + 4.6M WAL + 32K shm | flat 7 ticks |
| Vault | sources 57M | same | sources 57M + checkpoints 10.3M | flat, consistent with F2 |
| Export storage | absent | absent | absent | nothing frozen or exported in 16 ticks |
| Provider usage | none | none | none observed | |
| Success counts | 5047 succ | 5435 succ | 5825 succ / 12 running / 8 queued / 2 paused (5847 total) | +391 runs in 30 min; rate ~390 for **six** consecutive ticks |
| Refusal counts | 0 | 0 | 0 | |
| Error classifications | 0 | 0 | **0** HTTP 4xx/5xx, **0** Traceback/ERROR/Exception, **0** failed runs | |
| Live rows | run_events 100181 | 107960 | run_events 115607, sources 8024, cases 112 | |
| Event classes | 8, typed | 8, typed | 8, typed; node.running 49046 vs node.succeeded 49045 | no failure class in 115,607 events |
| Orphan rows | 0/0/0 | 0/0/0 | **0/0/0** | sixteen consecutive ticks at zero |
| Cross-case events | none | none | none | |

**No new finding.** CPU touched 93.5% for the second time without throughput moving — runs per
30 minutes have been 387, 396, 389, 387, 391 across the last five intervals, a spread of under
2.5%. That is the signature of a workload inside its profile, not one saturating: at saturation
the CPU pins high *and* throughput falls, and it has not.

**F2 is the standing conclusion of this watch.** Sixteen ticks, 5,847 runs, 115,607 events, zero
untyped errors, zero orphans, zero cross-case events — but every run since 00:20:45Z executed
against a frozen corpus because the scanner has been dead the whole time. Nothing touched.

## 2026-09-04 09:16 tick 17 — CPU EASED, CLOSE_WAIT SPIKE REFUTED AGAIN, F2 UNCHANGED

No restarts (app/db 8 h, worker 2 h). **F2 unchanged**: clamav `unhealthy`,
`OOMKilled=true`, `RestartCount=0`, RSS 45.1 MiB; `sources` still 8024. Admission stopped ~9 hours.

| Signal | tick 15 | tick 16 | tick 17 | Note |
|---|---|---|---|---|
| CPU | app 81.36%, db 36.06% | app 93.50%, db 40.87% | **app 54.88%**, db 28.12%, worker 0.00%, clamav 0.01%, pg 0.34% | lowest since tick 3 |
| Memory | app 694.9 | app 744.1 | app 694.9, db 214.9, worker 67.6, clamav 45.1, pg 36.9 MiB | mid-band |
| DB connections | 9,15,15,14,12 | 9,18,18,18,18 | **14, 9, 15, 14, 9** | bimodal 9/≤18, floor still 9 |
| Open handles | 63 | 68 | 79 | band 39–103 across seventeen ticks |
| — TCP states | TW 1055, EST 49, CW 2 | TW 1097, EST 54, CW 1 | TW 1085, EST 57, LISTEN 2, CW **9 → 0,0,0,0** | see note |
| Active jobs / permits | 0 / 0 | 0 / 0 | `model_builds` 0, `deliverable_freeze_jobs` 0 | nothing claimed in 17 ticks |
| Checkpoint size | 5.7M + 4.6M WAL | same | 5.7M db + 4.6M WAL + 32K shm | flat 8 ticks |
| Vault | sources 57M | same | sources 57M + checkpoints 10.3M | flat, consistent with F2 |
| Export storage | absent | absent | absent | nothing frozen or exported in 17 ticks |
| Provider usage | none | none | none observed | |
| Success counts | 5435 succ | 5825 succ | 6242 succ / 13 running / 6 queued / 2 paused (6263 total) | +416 runs in 32.5 min ≈ **384/30 min** — rate held while CPU fell 93.5% → 54.9% |
| Refusal counts | 0 | 0 | 0 | |
| Error classifications | 0 | 0 | **0** HTTP 4xx/5xx, **0** Traceback/ERROR/Exception, **0** failed runs | |
| Live rows | run_events 107960 | 115607 | run_events 123808, sources 8024, cases 112 | |
| Event classes | 8, typed | 8, typed | 8, typed; node.running 52520 vs node.succeeded 52519 | no failure class in 123,808 events |
| Orphan rows | 0/0/0 | 0/0/0 | **0/0/0** | seventeen consecutive ticks at zero |
| Cross-case events | none | none | none | |

**CLOSE_WAIT spike refuted a second time.** The first read was 9 — a new high — and four
immediate rechecks returned **0, 0, 0, 0**, the same pattern as tick 13's 7→0. Across the watch
CLOSE_WAIT has been 0,0,0,0,0,2,0,7→0,0,2,1,9→0: it appears in single-sample bursts and is always
gone seconds later. Sockets are being closed on the peer's FIN as they should. No finding.

**CPU fell 93.5% → 54.9% while throughput held at ~384 runs per 30 min.** Six intervals now read
387, 396, 389, 387, 391, 384 — under 3% spread across a CPU range of 55–96%. The declared profile
has clear headroom; the earlier 93–96% readings were sampling excursions, not the ceiling.

**F2 unchanged and still the only open finding.** Nothing touched.

## 2026-09-04 11:23 tick 18 — LOAD DRAINED; WATCH CLOSED

The load phase is over. App CPU **0.69%**, worker 0.84%, db 0.39%; app handles **19**
(6 established, 5 TIME_WAIT, 2 listening); connections **9, 9, 9, 9, 9**; the only HTTP
traffic in the log is the container healthcheck. Last run created **2026-09-04T08:20:36Z**
(09:20 local), so the driver stopped ~2 h before this tick. (Coverage gap 09:16 → 11:23.)

**Terminal state of the run set — clean.**

| Quantity | Final value |
|---|---|
| Runs | **6304** total: 6302 `succeeded`, 2 `paused` (the two Deep Research plan gates), **0 running, 0 queued, 0 failed** |
| `run.created` / `run.running` | 6304 / 6304 — every run entered execution |
| `node.running` / `node.succeeded` | **53032 / 53032 — exactly equal; no node stranded** |
| Run events | 124,981 across 8 classes, all typed; no failure class ever appeared |
| Orphan rows | events 0, source_sets 0, artifacts 0 — **zero at all eighteen ticks** |
| Cross-case events | none at any tick |
| HTTP 4xx/5xx | **0** for the entire watch |
| Traceback / ERROR / Exception | **0** for the entire watch |
| Sources / cases | 8024 / 112, frozen since 00:20:45Z |
| Checkpoint | 5.7M db + 4.6M WAL + 32K shm |
| Vault | 57M sources + 10.3M checkpoints |

### Verdict

**Inside the declared profile, for the part of the system it exercised.** Across eighteen
ticks the four quantities the loop watches for monotonic growth were each tested and each
reversed or stayed flat: connections (bimodal 9/≤18, floor 9 throughout), handles (39–103,
ending at 19), jobs and permits (identically 0), orphan rows (identically 0). CPU ranged
55–96% while throughput held to under 3% spread (387, 396, 389, 387, 391, 384 runs per
30 min), which is headroom, not saturation. Memory oscillated 507–744 MiB with no trend.
Two candidate findings were raised and both were refuted by further evidence (F1, handles,
tick 6 → tick 7; CLOSE_WAIT bursts at ticks 11/13/17, each gone within seconds).

**What this soak does not cover.** Three limits, and they are large:

1. **F2 (open, unrepaired): the ClamAV container was OOM-killed** — `OOMKilled=true`,
   `RestartCount=0`, clamd unresponsive to PING (healthcheck exit 21), RSS 1020 MiB → 45 MiB,
   its log silent since 03:27. Source admission stopped at **00:20:45Z** and never resumed;
   every one of the 6,304 runs executed against a frozen 8,024-source corpus. Intake,
   scanning, and the scanner-down refusal path are **unexercised**.
2. **No model build, export, freeze or filing ran.** `model_builds` and
   `deliverable_freeze_jobs` were **0 at all eighteen ticks** and `/data/exports` never
   existed. The worker claimed no job in the entire watch.
3. **No provider usage was observed at any tick.**

### The terminal comparison cannot be run

The loop's closing step — "run the post-soak six documents-only journeys from the harness,
compare authorities, model hashes, filed bytes, and offline reconstruction against the
pre-soak baseline the harness recorded" — has no executable referent in this tree, and this
was verified at tick 1 and re-checked since:

- **There is no soak harness.** `qa/` holds `capacity.py` (`limits`/`profile`/`baseline`/
  `compare`), `probe.py`, `scenarios.py`, `seed.py`, `edge_proxy.py`; none drives an
  eight-hour soak or the six documents-only journeys. No harness process ever appeared on the
  host, and no harness output file was written at any tick.
- **There is no pre-soak baseline.** Nothing recorded authorities, model hashes, filed bytes
  or an offline reconstruction before the load began, so there is nothing to compare against.
- **There would be nothing to compare even if a baseline existed**: zero model builds, zero
  freezes, zero exports, zero filings occurred during the watch (limit 2 above).

Fabricating a comparison against a baseline that was never recorded would be the opposite of
evidence. The watch is therefore closed on the observations above rather than on that step.

**Nothing was restarted, scaled or reconfigured by this loop at any tick.** Four interventions
from outside it are recorded in this file: stack restarts before ticks 3 and 4, worker
container replacements before ticks 8 and 14, and the whole Compose project being replaced
(`caos-cand-20260903-*` → `caos-cand-20260904-*`) before tick 10.

## 2026-09-04 — CORRECTION: the harness exists; the claim above was wrong

Tick 1 recorded "no soak harness in the tree" and tick 18 concluded the terminal
comparison "has no executable referent". **Both are wrong**, and the record is corrected here
rather than edited above.

`qa/capacity.py` is the harness, and its module docstring says so:

- **`profile --duration 28800`** is the eight-hour soak — declared **PERF-013**. It drives the
  declared profile (25 subjects, 20 jobs, 4 streams, 2 previews, 300 rpm, 100 cases × 100
  documents), rotates all six pathways in `job_driver`, checks cross-case leakage, and with
  `--compose-project` samples CPU, memory, connections, checkpoint and vault growth — the same
  quantities this loop sampled by hand for eighteen ticks.
- **`baseline` / `compare`** are the pre- and post-soak authority comparison — declared
  **PERF-015**, `docs/PERIMETER_LEDGER.csv:81`. `baseline` records exactly what the loop's
  terminal step names: accepted snapshot digest, model build payload digests, frozen
  deliverable ids/status/digests and per-format export SHA-256s, and the audit chain head read
  out of the case's audit package. `compare` diffs two of them, with `--allow-audit-growth`
  for the rows a soak legitimately appends.
- The **six documents-only journeys** are `caos/frontend/scripts/workbench-smoke.mjs`
  (**WEB-002**, `docs/PERIMETER_LEDGER.csv:53`), one script over three engines.

**Verified working against the live candidate stack** (read-only GETs, nothing touched):

```
$ python qa/capacity.py baseline --url http://127.0.0.1:18300 --subjects 2 --out post-soak-baseline.json
baseline of 8 cases written to post-soak-baseline.json

$ python qa/capacity.py compare post-soak-baseline.json post-soak-baseline.json
{"before": "536795063f8dbb08", "after": "536795063f8dbb08", "cases": 8, "changed": []}   exit 0
```

The recorded baseline also confirms limit 2 of the verdict independently: every case reads
`"builds": []` and `"frozen": []`. Nothing was ever built or frozen.

**What was actually missing was not the harness but its use.** `capacity.py profile` seeds
subjects named `capacity-<n>`; this stack has `capacity-0` and `capacity-1` with 8 cases
between them, so `profile` has been run here at some point — but the load this loop watched
was a different driver (112 cases, 8,024 intake-shaped sources, browser-journey HTTP), and no
`baseline` was taken before it started. That is why there was nothing to compare against:
**the run was not started through the harness**, so it recorded no pre-soak authorities.

The corrected conclusion: the eighteen-tick observation stands exactly as written, and the
terminal comparison was unavailable because the soak was driven outside `capacity.py`, not
because the tooling was absent.
