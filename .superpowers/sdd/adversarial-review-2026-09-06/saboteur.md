# Saboteur review — CAOS (server + frontend), worktree `fe-followup` @ 18dccbb

Mindset: break it in production. Every finding names the file and line, the concrete failure, the reproduction (scripts live beside this report under `scratchpad/agents/saboteur/`), the rule it breaks, and a one-line fix. Severity: CRITICAL = data loss / breach / outage; WARNING = likely bug in an edge case, degraded availability or misleading result; NOTE = minor.

All paths are relative to `/Users/ericguei/Claude/Projects/CAOS-LangMVP/.claude/worktrees/fe-followup/`.

Totals: **CRITICAL 1, WARNING 7, NOTE 3.**

---

## S1 — CRITICAL — Startup recovery runs every stranded run to completion, serially and inline, before the socket is bound (CONFIRMED)

**Where:** `caos/server/caos/engine/runtime.py:2162-2198` (`Engine.recover`: `await self._drive(run["id"], None)` at 2187 and 2198, no `interrupt_after`); `caos/server/run.py:137-138` (`await engine.recover()` then `uvicorn.Server(...).serve()`); `dev.py` uses the same `serve`.

**Claim:** After any restart, the API — `/api/health` included — is unreachable until every non-terminal run has executed to its terminal state, one after another, on the serving loop.

**Scenario:** The app process dies (OOM, deploy, node drain) while K agent runs are mid-flight. On restart `recover()` re-drives each of them with the full provider loop inline; each can spend up to its 15-minute `active_minutes` budget and `MAX_ACTIVE_JOBS` allows 20. Nothing answers on the port meanwhile: liveness probes fail, the orchestrator restarts the container, which starts recovery again from the last checkpoint. One stranded FULL_CREDIT run keeps the instance dark for minutes; a busy desk keeps it dark for hours.

**Reproduction:** `r1_recover_blocks.py` — start a FULL_CREDIT/screen run under host control with a provider that sleeps 0.5 s per call, "crash" (close the engine after the gate), build a second engine over the same store + checkpoint exactly as `run.py::serve` does, time `recover()`:

```
after start_run: running nodes: 9
after crash: status in store = running executed modules so far = []
recover() returned after 12.2s; run status now = succeeded; provider calls made inside recover() = 23; continuations scheduled = 0
```

`recover()` made all 23 provider calls itself and scheduled nothing; `run.py` reaches `uvicorn.Server.serve()` only after that.

**Rule violated:** `docs/DECISIONS.md` §10 item 5 — "re-admit only crashed mid-run threads through the normal admission gate **with bounded concurrency**"; item 9 ("Capacity self-heals after crashes"). Invariant 6 is intact; availability is not.

**Fix:** In `recover()`, reconcile statuses and, with `_auto_continue` on, `self._schedule_continuation(run_id)` (or drive with `interrupt_after=["gate"]` then schedule) instead of awaiting `_drive(run_id, None)`; or run recovery as a task after the socket binds, with readiness reporting `recovering` until it finishes.

---

## S2 — WARNING — Source admission (text extraction, malware scan, vault write) runs on the event loop and freezes the whole instance for every upload (CONFIRMED)

**Where:** `caos/server/caos/sources/domain.py:410-430` (`async def prepare_upload` calls the synchronous `scan_content` 426, `extract_blocks` 429 and `vault.put` — write + `fsync` — 430 directly); `caos/server/caos/api/__init__.py:430-442` (`upload_source` is `async def`, awaits `ingest_upload` → `prepare_upload`); `caos/server/caos/intake/service.py:170` (`_prepare` loops up to 40 files through the same path). In production `scan_content` (`domain.py:121-150`) also opens a blocking socket to clamd with a 15 s timeout and streams the whole file through it.

**Claim:** One admissible upload stalls every coroutine on the loop — SSE tails, `/api/health`, every other request — for as long as extraction takes; a 40-file intake stalls it for the sum. Escalation: `/api/health` is exempt from the rate ceiling but served by the frozen loop, so ordinary concurrent uploads make readiness time out, the load balancer drops the instance, and a restart lands in S1.

**Reproduction:** `r6a_extract_timing.py 12000` — a 2.4 MB, 12,000×64 workbook inside every ceiling: `extract_blocks took 5.4s on the calling thread; blocks = 347` (a 24,000-row run was *refused* only after the full walk — the refusal path costs the same). `r6b_live_upload_blocks_loop.py` against `dev.py` on :8801 while probing `/api/health` with a 1 s client timeout:

```
upload outcome: {'status': 201, 'seconds': 5.89, 'blocks': 347}
/api/health probes during the upload: 10; max latency 1.00s; probes over 0.5s: 5; probes that hit the 1s client timeout: 5
/api/health after the upload: 0.001s
```

**Rule violated:** `docs/DECISIONS.md` §10 item 8 — "**No event-loop starvation.** All ported sync domain code runs via `asyncio.to_thread` on a bounded pool" (compare `Engine.accept`, which does exactly that, DECISIONS.md:432-436).

**Fix:** Read the bytes on the loop, then `await asyncio.to_thread(prepare_upload_sync, ...)` (scan + archive check + extraction + vault publish) on the bounded pool; same in `IntakeService._prepare`.

---

## S3 — WARNING — A refused intake pack leaves every prepared document in the content-addressed vault with no store row, and nothing ever collects it (CONFIRMED)

**Where:** `caos/server/caos/sources/domain.py:430` (`vault.put` inside `prepare_upload`, before any admission decision); `caos/server/caos/intake/service.py:170-192` (`_prepare` writes all files to the vault, then refuses the pack on `INTAKE_ADMISSION_REFUSED` / `INTAKE_SOURCE_CONFLICT`); `service.py:151, 291` (later refusals after the same writes). `DomainStore.refuse_intake` ("a refused pack persists nothing but its audit row") is true of the database only.

**Claim:** Disk on the vault volume grows by up to 40 × 25 MiB per refused request with no reference, no quota and no GC, and any writer can repeat it 300 times a minute.

**Scenario:** 39 valid 25 MiB documents plus one `.exe` → `INTAKE_ADMISSION_REFUSED`, ~975 MiB stays under `vault/sources/`. Repeat with different bytes; the volume fills; every later freeze/export `publish_hash_addressed_bytes` fails with `OSError` and the worker marks jobs FAILED. Reached accidentally too: two files with one filename in a drop is the documented `INTAKE_SOURCE_CONFLICT` case and orphans both.

**Reproduction:** `r2_intake_orphans.py`:

```
refused: INTAKE_SOURCE_CONFLICT
vault files left behind (count, bytes): (2, 14000000)
source rows: 0 case rows: 0
refused again: INTAKE_ADMISSION_REFUSED
vault files after second refusal (count, bytes): (3, 20400003)
source rows: 0
```

**Rule violated:** DECISIONS §14.17 / CLAUDE.md golden journey — intake "admits every file or none in one transaction"; the vault publish is outside that transaction. Resource exhaustion; no invariant number.

**Fix:** Stage prepared bytes in a per-request temporary directory and publish to the vault only after `admit_intake` commits (or unlink every prepared `vault_path` no `sources` row references when the pack is refused).

---

## S4 — WARNING — `MemberRequest.subject` is a bare `str`: control bytes, bidi overrides and un-normalised forms enter `case_members`, the hash-chained audit log and the case wire (CONFIRMED)

**Where:** `caos/server/caos/contracts.py:156-158` (`subject: str = Field(min_length=1, max_length=200)`); `caos/server/caos/api/__init__.py:1136-1144`; `caos/server/caos/storage/store.py:616-640` (`add_member` insert/update + `_audit(... member=member ...)`).

**Claim:** The one string that decides who may file a deliverable is admitted without the boundary every other pinned/audited string gets.

**Consequences:** (a) An approver provisions "Amélie" typed in NFD; the IdP presents the NFC subject; `is_member`/`require_standing` compare bytes, so the provisioned approver never matches and filing is refused — or two spellings mint two member rows for one person. (b) `mallory<NUL>x` and `mallory<U+202E RLO>gnip` are stored, appear in the `case.member_added` audit row (chained, immutable), in the audit package, and are served to every case reader in `members`, where the override reorders the rendered name (CVE-2021-42574 — the class the boundary rule exists for).

**Reproduction:** `r4_member_boundary.py` (TestClient, dev identity, actor seeded as case APPROVER):

```
control byte NUL -> 201 stored members: ["'analyst'", "'mallory\\x00x'"]
bidi override RLO -> 201 stored members: [..., "'mallory\\u202egnip'"]
NFD (decomposed e-acute) -> 201 stored members: ["'Ame<U+0301>lie'", ...]
lone surrogate -> 422 (pydantic refuses the raw bytes; fine)
audit rows for case.member_added carry member = ['Ame<U+0301>lie', 'mallory\\u202egnip', 'mallory\\x00x', 'analyst']
GET case members served: ['Ame<U+0301>lie', 'analyst', 'mallory\\x00x', 'mallory\\u202egnip']
```

**Rule violated:** CLAUDE.md standing rule "Boundary text" — "Bare `str` on a field that reaches ... an audit event is a defect"; DECISIONS §12.3.

**Fix:** `subject: BoundaryText = Field(min_length=1, max_length=200)`, and NFC-normalise `identity.subject` in `identity_from_request` so stored standing and presented identity compare equal.

---

## S5 — WARNING — `Engine.switch_visible` commits the case pointer and its audit event in two transactions (CONFIRMED)

**Where:** `caos/server/caos/engine/runtime.py:2346-2351` (`self.store.update_case(case_id, visible_snapshot_id=...)` at 2350, then `self.store.audit_event("snapshot.visible_switched", ...)` at 2351 — two separate `engine.begin()` blocks, `store.py:643-650` and `store.py:462`); route `api/__init__.py` `switch_snapshot`.

**Claim:** A failure between the two commits (connection drop, `OperationalError`, process kill) moves the visible lens with no audit row while the route answers 5xx.

**Scenario:** The analyst switches the visible snapshot; the audit insert fails; the response is 503 `STORE_UNAVAILABLE`; the workbench says it failed, yet every reader now sees the other snapshot and the audit package has no record of who moved it.

**Reproduction:** `r3_switch_visible.py` (audit insert made to fail after the pointer update):

```
route answers 5xx: audit insert failed (connection dropped between the two transactions)
visible_snapshot_id before: None after: snap-test | audit rows added: 0
```

**Rule violated:** CLAUDE.md standing rule "Transactional pairing — Governed writes commit state + audit event in one transaction".

**Fix:** Add `DomainStore.switch_visible_snapshot(case_id, snapshot_id, actor)` doing the update and `self._audit(conn, ...)` inside one `engine.begin()`; call it from `switch_visible`.

---

## S6 — WARNING — `pack_blocks` is not bounded by 600 blocks; two ordinary-sized documents push a run past `MAX_MANIFEST_BLOCKS`, and the CLAUDE.md ledger line claiming otherwise is false (CONFIRMED)

**Where:** `caos/server/caos/sources/domain.py:367-405` (`pack_blocks`; `width` at 385; a fragment longer than `width - size - 1` always flushes, so any line in `(width/2, width]` becomes its own block); docstring `domain.py:45` ("at most MAX_SOURCE_TEXT / MAX_BLOCK_CHARS = 600 for any shape of document"); `caos/server/caos/engine/budget.py` `bound_manifest` (`MAX_MANIFEST_BLOCKS = 2_000`, rows = sources + blocks, run-wide).

**Claim:** A 12 MB document with ~10–20 k-character lines yields ~1,200 blocks; a 1.3 MB document of 2.1 k-character paragraphs yields 620; two of the former exceed the run-wide ceiling, so the run pins at the gate, charges the reuse-validation bracket, then fails `AGENT_BUDGET_EXCEEDED` in `_execute_agent` before the first provider call — after the analyst waited for the gate and the plan.

**Reproduction:** `r7_pack_blocks.py`:

```
blocks for one 12 MB document: 1199 (docstring: at most 600 for any shape)
blocks for a 1.3 MB document of 2,100-char lines: 620 (MAX_BLOCKS_PER_SOURCE switch point = 320)
bound_manifest refused 3 such 12 MB documents: AGENT_BUDGET_EXCEEDED | rows = 3600 > MAX_MANIFEST_BLOCKS = 2000
bound_manifest refused 2 such 12 MB documents: AGENT_BUDGET_EXCEEDED | rows = 2400 > MAX_MANIFEST_BLOCKS = 2000
```

**Ledger claim proven false:** CLAUDE.md "Known gaps" line 457: "three 12 MB credit agreements still pin one run inside `MAX_MANIFEST_BLOCKS`" — two suffice for this line shape (minified/inline-XBRL-like text, wide table rows, single-line paragraphs). Invariant 8 still fails closed; the defect is a misleading result (a pinned run that can never execute) and a false ledger.

**Fix:** Guarantee the bound: split fragments at `width` (not only at `MAX_BLOCK_CHARS`) so every block packs to `width`, giving ≤ `ceil(len/width) + 1`; and refuse at ingest (typed 422) when a document's block count would make any run's manifest exceed the ceiling, rather than at the first provider call.

---

## S7 — WARNING — Any non-`AgentError` exception inside a module node strands the run `running` forever with `error: null`, an admission slot held, the SSE tail open and no automatic resume (CONFIRMED)

**Where:** `caos/server/caos/engine/runtime.py:688-710` (`_drive` catches only `AgentError`; every other exception propagates and leaves the store row `running`); `runtime.py:303-320` (`_schedule_continuation.finish` only logs `engine.continuation_failed`); `_run_module` `except (AgentError, StoreConflict)` (an `OperationalError` from `node_running`/`complete_node`/`charge_budget`, an `OSError` from the vault, a checkpoint write error all escape).

**Claim:** One transient infrastructure fault turns a live run into a zombie: status `running`, no terminal event, still counted by `active_admission_count` (20 of these = `ADMISSION_BUSY` for every new run and model build), the Run page shows LIVE with an open keepalive stream, and nothing retries. The exits are a restart (S1) or a manual `POST /resume`, which then executes the whole remainder inside that HTTP request.

**Reproduction:** `r10_stuck_running.py` — one `OperationalError("database is locked")` injected into the first `node_running` after the gate, auto-continue on:

```
start_run returned: running
after the continuation died: status = running | error = None | active_admission_count = 1 | nodes running = [] | latest ticket = None
resume() returned after 0.4s with status succeeded (the whole remaining run executed inside the HTTP request; continuations = 0)
```

SQLite "database is locked" is a realistic dev/staging fault (5 s default busy timeout versus a 40-document `admit_intake` writing megabytes of block JSON); on PostgreSQL the same shape is a dropped connection.

**Rule violated:** DECISIONS §10 item 9 ("Capacity self-heals after crashes") holds only across a process restart; invariant 6's "resume from the last checkpoint" has no trigger while the process lives.

**Fix:** In `_drive`, after the `AgentError` branch, catch `Exception` and `finalize_failure(run_id, "RUN_EXECUTION_FAILED", None)` — or have `finish()` reschedule the continuation with bounded backoff and fail the run after N attempts; either way the run must reach a terminal event without a restart.

---

## S8 — WARNING — `POST /api/runs/{id}/resume` on a run that is already executing waits behind the thread lock for the rest of the run instead of skipping it (CONFIRMED on the mechanism)

**Where:** `caos/server/caos/engine/runtime.py:2075-2093` (`resume`: with no unconsumed ticket it goes straight to `_drive(Command(resume=True), interrupt_after=["gate"])`); `runtime.py:693` (`_drive` takes the per-thread lock with a blocking `async with`); route `api/__init__.py` `resume_run` (no status precondition).

**Claim:** A resume issued while the continuation holds the thread — a double-click, a stale tab, a retry after a 429 — does not answer until the run finishes; with a live provider that is minutes, longer than any browser or proxy timeout, and the caller cannot tell "already running" from "resumed".

**Reproduction:** `r8_live_resume.py` against `dev.py` :8801 — `POST /resume` fired 10 ms after `start_run` returned `running`:

```
POST /resume on the running run answered 200 after 0.37s with status=succeeded
run status observed by a second client while /resume was in flight: [(0.02, 'running'), (0.3, 'running'), (0.56, 'succeeded')]
```

The response is the terminal record: the request waited for the whole run (0.37 s under host control; the provider loop's duration in production).

**Rule violated:** DECISIONS §10 item 3 — "recovery and **API resumes skip held threads**". Awaited, not skipped.

**Fix:** In `Engine.resume`, refuse unless the stored status is `paused` with an unconsumed ticket (`EngineError("RESUME_NOT_APPLIED")` → 409), and take the thread lock non-blockingly (`if lock.locked(): raise`).

---

## S9 — NOTE — An SSE `Last-Event-ID` outside SQLite's 64-bit range crashes the tail after the 200 headers; an EventSource then reconnects with the same header forever (CONFIRMED)

**Where:** `caos/server/caos/api/__init__.py:715` (`cursor = int(header)`; Python ints are unbounded, only `ValueError` is caught), `:723-726` (the generator calls `events_after` after the headers went out); `caos/server/caos/storage/runs.py:815` (`events_after` binds the cursor to `seq > :cursor`).

**Claim:** `Last-Event-ID: 99999999999999999999` raises `OverflowError: Python int too large to convert to SQLite INTEGER` inside the generator; the client sees a 500 body then a connection reset and, being an EventSource, retries with the same id every few seconds, each retry charging a rate-ceiling token and a stream slot.

**Reproduction:** `r5_sse_cursor.py` (TestClient) and `r8_live_resume.py` (live):

```
Last-Event-ID='99999999999999999999': status 500, 21 bytes, events=0            (TestClient)
SSE with huge Last-Event-ID: 500 body: b'Internal Server Error' ... httpx.ReadError: Connection reset by peer   (live)
server.log: OverflowError: Python int too large to convert to SQLite INTEGER
```

`-5`, `abc`, `1e3` fall back to a full replay (fine). The workbench never sends such an id; on PostgreSQL the same input is a `DataError`.

**Rule:** none (wire robustness). **Fix:** `cursor = min(max(cursor, 0), 2**62)` or catch `(ValueError, OverflowError)` and treat as 0.

---

## S10 — NOTE — `_finalize_node` discards the blamed module when finalization refuses a run (PLAUSIBLE)

**Where:** `caos/server/caos/engine/runtime.py:1752-1775` (`except (AgentError, StoreConflict) as exc: ... finalize_failure(run_id, exc.code, None)`); `_validated_plan_artifacts` raises `ModuleFailure("RUN_NOT_READY"|"QA_BLOCKED", module_id, ...)`.

**Claim:** A run that fails its final re-verification records `error: {"code": "RUN_NOT_READY"}` with no `module_id`; the offending node stays `succeeded` on a `failed` run, so the Run page and the `run.failed` event cannot say which artifact failed.

**Reproduction:** not reproduced — the `ModuleFailure` subclass is caught by the `AgentError` clause and `exc.module_id` is never read.

**Rule:** observability intent (SPEC_RECONCILIATION "which run is stuck, which node"). **Fix:** `module_id = exc.module_id if isinstance(exc, ModuleFailure) else None` before `finalize_failure`.

---

## S11 — NOTE — A case APPROVER can re-role every member, including the case ADMIN and themselves; a case can lose all approver standing with no route to repair it (PLAUSIBLE)

**Where:** `caos/server/caos/storage/store.py:616-640` (`add_member` updates an existing subject's role unconditionally once the actor has ADMIN/APPROVER standing, `:632-634`); `caos/server/caos/api/__init__.py:1136-1144` (the route passes `actor_role=None`, so a global ADMIN cannot use it to repair standing; no other route writes `case_members`).

**Claim:** One approver demoting the admin and the other approvers (or themselves, by mistake) leaves a case whose deliverables can never be filed (`require_case_approver` → 403 for everyone) and whose only repair is a database write — the same bootstrap the browser-journey notes already need to seed the first admin.

**Reproduction:** not reproduced — direct reading of the update branch; the audit row records the change but nothing prevents it.

**Rule:** separation-of-duties intent of DECISIONS §14.19. **Fix:** refuse `add_member` when `member == actor`, refuse demoting the last ADMIN/APPROVER of a case, and let a current global ADMIN provision standing through the route.

---

## Areas read and found sound (coverage)

- **`storage/runs.py`** — conditional transitions everywhere; `_emit` locks the run row and allocates `seq` in the same transaction; `finalize_success`/`finalize_failure` CAS; `pin_plan` CAS on `plan_digest IS NULL`; `accept_snapshot` CAS on both the case and the run pointer; `reserve_provider`/`reconcile_provider` under `FOR UPDATE`, reconcile commits the true-up before raising when the provider reports more tokens than reserved (invariant 8 holds); `record_attempt` ring bounded. Two concurrent accepts of one run returned one snapshot id (live check in `r8`).
- **`storage/store.py`** — audit chain lock row + unique `(chain_key, chain_seq)`; ingest/withdraw/promote under the process lock with conditional updates; `_next_source_set` locks the case row; `read_source_bytes` verifies path, size and digest; `admit_intake` is one transaction on the database side (S3 covers the bytes).
- **`engine/loop.py`, `engine/budget.py`, `engine/evidence.py`** — count → reserve → create → validate usage → reconcile; one byte-identical timeout retry, one repair; `validate_usage` refuses bools/negatives/cache tokens; `EvidenceReader.read` orders budget → argument bounds → live authority → charge → delivered-set; slots released in `finally`; `locator_is_bounded` is iterative.
- **`engine/runtime.py` gate/reuse/agent path** — `_gate_node` early-returns on a pinned plan (crash between pin and checkpoint is safe); `_await_research_approval` re-reads the store on every re-entry and refuses a hash that is not the plan that would execute (a stray `POST /resume` on a plan-approval-parked run re-parks it; no bypass); `_execute_agent` refuses a leftover in-flight digest; finalization under the authority lock; `methodology/execution.py:154` `_normalise_json` refuses non-finite calculator inputs including an overflowing `1e999` (invariant 7); `SimulatedCrash` is `BaseException`.
- **`engine/state.py`** — digests carried outside the digested blob; `verify_source_set_expectation` re-reads the store.
- **`atomic_files.py`** — `O_EXCL` temp + fsync + `os.replace`; no-follow descriptor chain; before/after `fstat` identity; over-length detection.
- **`instance_lock.py`, `run.py`, `dev.py`, `config.py`** — `flock` before recovery and bind; strict env parsing; production placeholder rejection; `MAX_SOURCE_MB <= MAX_UPLOAD_MB` enforced.
- **`storage/models.py`, `models/service.py` (queue/claim/complete/export/download)** — claim CAS `QUEUED|FAILED → BUILDING`; completion bound to the dispatched fingerprint and to every pinned source being live in the same statement; a re-point mid-flight makes the stale executor no-op; `recover_builds` requeues BUILDING at worker start; download verifies vault key, digest, size and identity digest. The export double-render is the ledger's known gap.
- **`storage/deliverables.py`, `deliverables/service.py`** — opinion head CAS under the case advisory lock; freeze captures the exact revision (a later draft `PUT` cannot change what the worker renders); `publish_frozen` refuses a divergent render for one identity; filing CAS `FROZEN → FILED` with commit-time standing recheck, sibling supersession and the detached receipt in one transaction; `APPROVER_NOT_INDEPENDENT` checks signer and freeze actor.
- **`worker.py`** — per-item failure finalisation bound to the claimed identity; startup requeue of RENDERING/BUILDING rows.
- **`intake/service.py`** — pack refused as a whole; issuer suggestions host-derived; duplicate bytes deduplicated; typed unavailability on engine refusal (S3 is the only defect found).
- **`api/__init__.py`** — 404 symmetry for unknown/unauthorised runs (`visible_run`); the gate authenticates before validation; `OperationalError → 503`; `RequestCeilings` decrements stream/preview slots in `finally`; readiness TTL-cached; validation errors never echo input.
- **Frontend** — `workspaceAuthority.ts` fences stale responses by generation + case + run (unit-tested); `Workspace.tsx` fences every fetch with a request counter *and* `matchesAuthority`, opens the `EventSource` only for an unsettled run bound to the selected case and closes it on settle/unmount/case change (no reconnect loop on a terminal run), refetches on event names only; `reportRecovery.ts` bounds length/depth/value count, validates every field and swallows `JSON.parse` failures; `ReportStudio` wraps every `localStorage` access in `try/catch` (quota/blocked storage degrade to "recovery unavailable"); `modelBuilderState.ts` `scrubberCommitDecision` reverts empty entries and `editAssumption` guards `rawValue.trim() === ""` before `Number()`; `RouteForwarder.tsx` replaces history through the external `replaceState`; `WorkbenchShell.tsx` passes dialog openers explicitly. Non-finding worth knowing: `api.ts::api` dereferences `body.detail` on whatever `response.json()` returned, so a non-OK body that is the JSON literal `null` would surface as a `TypeError` rather than an `ApiRequestError` — no route serves that today.

## Commands run

```
# orientation
/usr/bin/git log --oneline -3; wc -l <server files>; sed/cat over every file listed in the brief (server and frontend)
/usr/bin/grep over docs/DECISIONS.md, SPEC_RECONCILIATION.md, CLAUDE.md for prior acknowledgment of each finding

# in-process reproductions (python = caos/server/.venv314/bin/python of the target-consolidation-checklist worktree; sys.path -> this tree's caos/server)
python r1_recover_blocks.py            # S1
python r2_intake_orphans.py            # S3
python r3_switch_visible.py            # S5
python r4_member_boundary.py           # S4 (FastAPI TestClient)
python r5_sse_cursor.py                # S9 (TestClient)
python r7_pack_blocks.py               # S6
python r6a_extract_timing.py 12000     # S2 timing (an earlier 24000-row run was refused only after the full walk)
python r10_stuck_running.py            # S7

# live server (stopped afterwards with pkill -f dev.py)
ENVIRONMENT=development CAOS_PROVIDER=host_control AGENT_EXECUTION_ENABLED=true PORT=8801 \
  CAOS_DATA_DIR=<scratch>/data_server CAOS_STORAGE_DIR=<scratch>/data_server/vault python dev.py
python r8_live_resume.py               # S8, double-accept (sound), S9 live
python r6b_live_upload_blocks_loop.py  # S2 live
curl http://127.0.0.1:8801/api/health
```

No tracked file was modified; no git write operation was run.
