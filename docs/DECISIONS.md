# Migration Decision Record — CAOS on LangGraph

Status: proposed 2026-08-26 (phase 1). Legacy source: `/Users/ericguei/Claude/Projects/CAOS` at `84f9705`.
This record is the contract for the build. Deviations require a new dated entry, not an edit.

## 1. The MVP cut

**Pathways in (both depths, 8 routes):** FULL_CREDIT, EARNINGS_UPDATE, COVENANT_REFINANCING, RELATIVE_VALUE.

**Pathways out:** DEEP_RESEARCH (CP-DR is out of scope by brief), DISTRESSED_RESTRUCTURING, and the two internal pathways PORTFOLIO_DECISION and DECISION_LEDGER (their terminal modules CP-6 and CP-8 never had real execution in legacy and none of the four MVP deliverable audiences need them). Routes remain compilable from the catalog — `StartRunRequest` validation simply refuses the cut pathways.

**Module execution in:** real agent execution (LLM against verified skill authority) for **nine** modules — the legacy canonical six (CP-1, CP-1A, CP-1B, CP-2, CP-2A, CP-2G) plus three newly wired modules that legacy could never reach: **CP-1C PeerBenchmark, CP-1D EarningsQuality, CP-5 EvidenceTraceValidator**. These three satisfy the "three unreachable live catalog modules" criterion and are chosen for pathway value: CP-5 gives EARNINGS_UPDATE and COVENANT_REFINANCING a real QA terminal, CP-1C serves RELATIVE_VALUE and FULL_CREDIT, CP-1D feeds CP-2G. Every other route module (CP-PARSE, CP-0, CP-L10, CP-2E, CP-2H, CP-3, CP-4, CP-4C) executes as a **deterministic host module** — the same typed `SYSTEM_ANALYSIS` payload contract legacy used for them, ported as plain functions. Agent execution runs at FULL depth only; SCREEN routes are deterministic end to end (LITE profile is SCREENING_ONLY by catalog design). Upgrading a deterministic module to agent execution later is one registry entry.

**Features in:** source ingestion with the full validation/vault/ClamAV posture; runs on LangGraph with events and Run Console; snapshot accept/switch/diff/lens; the complete Model Builder chain (CP-MODEL build, assumption registry, previews, scenarios, one-way sensitivities, revisions, Sign-Off, exports, verified downloads); the Deliverables pipeline (drafts, freeze, approval-gated filing, request-changes, md/pdf/xlsx exports); RV loan-universe import and reads; append-only audit; admin bundle-verify and audit endpoints; the legacy auth edge model unchanged; the ported frontend.

**Features out (each is a superseded or unreachable surface, not an invariant):**
- The legacy report era: thesis, recommendation matrix, notes (incl. promotion), assumptions, report freeze/approve/export endpoints. Superseded by the Deliverables pipeline; the current frontend calls none of them. Their contractual tests are excluded with per-test justification in the invariant reconciliation (the invariants they protect — CAS writes, withdrawn-evidence bans, approval digest pinning — are asserted on the surviving surfaces).
- Methodology draft editing (admin drafts/validate/confirm). Bundle verify and audit stay; editing methodology is not an MVP activity.
- CP-MEMO (docx consolidation; `navigable: false`, no route) and CP-DR anything.
- Run upgrade (screen→full re-run) stays IN — it is one endpoint over the same engine.

## 2. Graph decomposition

**Run graphs.** One compiled `StateGraph` per (pathway, depth) — eight static graphs built at startup from the verified catalog routes, CP-PARSE at stage 0. Node = live catalog module. Edges = the catalog navigation dependencies exactly as `bundle.compile()` resolves them today (modules with no in-route upstream depend on CP-0; CP-0 depends on CP-PARSE). Where the DAG allows parallelism (e.g. CP-1A/CP-1B/CP-1D after CP-1) the graph fans out; LangGraph's superstep semantics replace the legacy 4-thread inner pool. **There is no dynamic routing: a run's path is fixed by (pathway, depth) at start, satisfying invariant 10 structurally.** Failure routing is a fixed conditional edge per node: success → declared successors, typed failure → finalize-failed. A blocked DAG (pending nodes, none ready) cannot occur in a static compiled graph; the compile step asserts acyclicity and coverage at startup, which is where legacy's `DAG_BLOCKED` guarantee moves.

**Thread = run.** `thread_id = run_id`. The source-set-empty pause is an entry-gate `interrupt()` (resume after upload re-checks and proceeds). Finalize node re-verifies every module artifact (existence, run ownership, module match, digest) before the run reaches SUCCEEDED — legacy's finalization gate, kept verbatim as a node.

**Deliverable lifecycle graph.** Freeze → render exports → `interrupt()` awaiting approval → file / request-changes. Thread per frozen deliverable. This makes invariant 5 a literal graph gate: filing resumes the same thread, approval binds to `preview_digest` + `input_fingerprint` at the resume boundary, and the store CAS on the frozen record remains the final arbiter under concurrent approvals. Model **Sign-Off stays a store CAS transaction, not an interrupt**: Sign-Off is the author's self-release (CONTEXT.md) — nothing suspends waiting for a second human, so a graph gate would be ceremony. Justified here so the "approval gates are graph interrupts" criterion is read as: every gate where execution waits on a human is an interrupt (source gate, deliverable filing); gates that are single-actor atomic commits stay transactions.

## 3. State schema (run graph)

Pydantic state, lean by design — large payloads live in the domain store, the checkpointer carries identity and control state:

- Pinned at start, never rewritten: `run_id, case_id, pathway, depth, profile_id, selection_id, plan_digest, methodology_build_id, model, source_set_id, source_set_version, source_set_digest, issuer identity`.
- `artifacts: dict[module_id → {artifact_id, digest}]` (merge reducer; payload markdown/tables live in the store; digests in state keep content addressing checkpoint-stable).
- `node_status: dict[module_id → status]` (merge reducer) — feeds the RunRecord read model.
- `error: {code, module_id?} | None` — typed terminal codes preserved verbatim from legacy taxonomy.
- Budget **snapshot** for visibility only. The budget ledger of record is in the domain store (below).

## 4. Persistence boundary

Three stores, one database:

1. **LangGraph checkpointer** (`langgraph-checkpoint-postgres` in production, `-sqlite` in dev/tests) owns execution state: node progress, interrupts, resumability. A worker restart resumes every unfinished thread from its last checkpoint at startup (re-invoke with `None` input); the kill/resume test proves it.
2. **Domain store** (one SQLAlchemy-Core schema, SQLite dev/tests + Postgres prod) owns the entities: cases/members, sources/blocks, source_sets + immutable history, runs (read model row), run_events (append-only, per-run monotonic sequence), artifacts, snapshots, model builds/jobs/revisions/exports, deliverable revisions/frozen/exports, loan universes, audit (append-only). Store transactions keep the legacy atomicity contracts: state+audit together, state+event together, CAS with typed conflicts carrying current state.
3. **Vault** — content-addressed bytes (sources, model workbooks, deliverable exports), atomic fsync+rename writes, sha256-verified on every read. Ported from legacy `sources/domain.py` semantics unchanged.

The **budget ledger** (reserve → reconcile, inflight request digest, active-time, evidence read/byte counters, attempts audit) lives in the domain store keyed by run_id with atomic operations — not in graph state — because parallel module nodes must contend on one fail-closed ledger, and because an unresolved inflight digest surviving a crash must fail the resumed run closed (legacy semantics, kept).

## 5. Legacy machinery → framework primitive

| Legacy machinery | Replaced by |
|---|---|
| ThreadPoolExecutor dispatch, `pending_runs()` polling, worker loop | asyncio tasks running `graph.ainvoke`; startup recovery re-invokes unfinished threads from checkpoints |
| Leases, 20s heartbeats, `_LeaseFence`, `JobFencedError`, attempt tokens | Single-writer-per-thread via the checkpointer in a single-service MVP; crash recovery = checkpoint resume; the global MAX_ACTIVE_JOBS=20 admission ceiling survives as a store-backed counter checked at run/build start (contractual) |
| Store run-row read-modify-write merges | LangGraph state channels with reducers; domain entities in store transactions |
| Hand-rolled SSE bus (`wait_for_events` condition variables) | Append-only `run_events` table (contractual: atomic with state changes) + a thin SSE endpoint tailing it with Last-Event-ID resume, keepalives, and the legacy event names verbatim. The frontend never reads payloads — event names trigger a refetch of the RunRecord — so the contract to preserve is names + RunRecord shape |
| `AnthropicGateway` + hand-rolled tool loop | `langchain-anthropic` `ChatAnthropic` (`max_retries=0` — the host owns retry policy) with `read_evidence` as a bound `@tool` (Pydantic args, strict), structured output via the adapter's JSON-schema output mode; the loop is a small bounded function: count → reserve (store) → invoke → validate usage → reconcile, one retry on timeout with byte-identical request digest, one repair turn, every legacy stop-reason/strictness rule kept as validation |
| `_PlanningPause` / paused-run application state | `interrupt()` — source gate now; deliverable filing gate; (CP-DR plan approval would be one too, but is out of scope) |
| memory_ledgers/postgres_ledgers dual implementations (6,655 lines) | One SQLAlchemy-Core store, two engine dialects |
| Legacy migrations runner | Fresh schema; `create_all` + a single baseline migration. No live data migrates (greenfield) |

**What copies across as domain code (decision, per file):** `contracts.py` (already seeded), the methodology package (`bundle.py`, `canonical.py` validation/envelope/projection halves, `prompt.py`, `cpdr.py` excluded), the vendored Deploy V bundle (already seeded, byte-identical), source ingestion/extraction (`sources/domain.py`), artifact validation (`artifacts/domain.py`), the CP-MODEL calculation engine (`engine/`), deliverable domain + export renderers, loan-universe parser. **What does not, in any form:** `workflows/domain.py`, `workflows/provider.py`, `http.py`, and the store implementations — rewritten against the framework. The runner halves of `canonical.py` (anything driving the loop) are rewritten; its validators/canonicalize/envelope stamping copy.

## 6. Budgets (invariant 8)

Limits stay host-owned code constants exactly as legacy set them: canonical envelope (evidence_reads 60, evidence_bytes 5 MiB, input 500k, output = Σ per-module caps, active 15 min, retries 1, repairs 1, turns = evidence_reads + module_count + repairs) generalised so the turn arithmetic covers the nine agent modules; per-module max_tokens from the registry (CP-1 32k, CP-1A/1B 12k, CP-2/2A 16k, CP-2G 24k; new: CP-1C 12k, CP-1D 12k, CP-5 16k — the caps legacy assigned to comparable table-count modules, recorded in the registry, not inferred methodology). Manifest bounding caps, attempt-audit allowlist/truncation, per-call timeout = min(150s, remaining active time) all carry over as store/loop validation.

## 7. Module registry (the declarative seam)

`modules/registry.py`: one dict entry per live catalog module — `{module_id, mode: agent|deterministic, skill_slug, reference_files, max_output_tokens, aliases: [...superseded ids]}` plus the CP-2B derived-projection declaration on CP-2A. The graph builder consumes only the registry and the catalog routes; **adding or upgrading a module touches the registry alone.** The three new wirings land as three isolated commits touching only registry entries (plus their tests) to prove it. Superseded IDs resolve through the alias map, so both forms address the same node (see MODULE_GRANULARITY.md).

## 8. Testing and verification

- Contractual tests from TEST_INVENTORY.md are ported per their porting briefs; the reconciliation table lands with the invariant-to-test table. Exclusions (report-era, CP-DR, methodology-draft rows) each get one line.
- Kill/resume: a test kills the process (or cancels the task and reopens the checkpointer) mid-run and asserts resume from the last checkpoint, not restart.
- Adversarial `read_evidence`: a scripted provider requests a block outside the pinned source set / withdrawn source / foreign case; the test asserts typed refusal and run failure, with no block text returned.
- Every invariant 1–10 gets a named test in the final table.
- Fresh-context verifier subagents check each phase gate against this record and the brief; nothing merges on self-review alone.

## 9. Phases (one branch each, merged at gate)

1. `phase-1-design` — this record, MODULE_GRANULARITY.md, red-team pass. Gate: objections fixed or accepted.
2. `phase-2-foundation` — pyproject/venv, package skeleton, domain code ported (bundle+integrity, ingestion, engine, contracts wiring), domain store schema, vault. Gate: bundle verify + ingestion/store tests green.
3. `phase-3-run-engine` — registry, graphs, deterministic modules, budgets, provider loop, events/SSE, run+snapshot endpoints, kill/resume + adversarial tests. Gate: run-engine tests green.
4. `phase-4-model-builder` — CP-MODEL chain on the new store. Gate: model contractual tests green.
5. `phase-5-deliverables` — deliverable graph with filing interrupt, exports, RV surfaces. Gate: deliverable tests green.
6. `phase-6-ship` — frontend served, deploy, README/CLAUDE.md, invariant table, TEST_INVENTORY reconciliation, final verifier pass. Gate: success criteria demonstrably true.

## 10. Red-team amendments (2026-08-26, adopted — binding overrides of §§1–8)

The phase-1 red-team pass (.agent-reviews/redteam.md, same date) raised fifteen objections; all fifteen are adopted. Where this section conflicts with §§1–8, this section wins.

1. **Exactly-once module execution.** Every agent node is reuse-first: before any provider work it looks up a valid artifact by (run_id, module_id, input_fingerprint), re-validates, and relinks with zero provider calls. All store state transitions are conditional CAS updates so a re-executed node no-ops. The kill/resume suite includes a crash injected between the store commit and the checkpoint write, asserting one artifact, one budget charge, one `run.succeeded`.
2. **Agent execution serialises per run.** A per-run `asyncio.Lock` wraps agent-module execution (legacy `_canonical_generation_lock` semantics); deterministic nodes still fan out. The budget ledger keeps its single inflight slot and sequential active-time meaning.
3. **Single-writer per thread is enforced, not assumed.** Per-thread in-process `asyncio.Lock` plus a Postgres advisory lock held for the duration of any `ainvoke`/resume; recovery and API resumes skip held threads. (SQLite dev is single-process; the process lock suffices.)
4. **Pin-time is entry-gate exit.** The gate node loops `while current source set is empty: interrupt()`; on a non-empty set it reads one store snapshot, compiles the plan, and writes the complete pin (source_set id+version+digest, plan_digest) exactly once. Nothing is pinned before the gate; §3's "pinned at start" reads "pinned at gate exit, then never rewritten".
5. **Startup recovery discriminates thread populations.** Enumerate threads; skip any whose latest checkpoint holds a pending interrupt; reconcile store statuses; re-admit only crashed mid-run threads through the normal admission gate with bounded concurrency. Superseding a frozen deliverable terminalises its thread (typed SUPERSEDED outcome) — no zombie interrupt population.
6. **Envelope arithmetic corrected and generalised.** Output ceiling = Σ per-module caps **+ max cap** (repair headroom), matching legacy `canonical.py`. The whole envelope (turns = evidence_reads + |route agent modules| + repairs, output, completion set) is a pure function of (compiled route, registry), tested per route. CP-MODEL's six-module `validate_bundle` is invoked only for accepted FULL_CREDIT runs — the only source of model builds.
7. **Deliverable thread choreography.** thread_id = digest(case_id, pathway, draft_version, draft_digest) so racing freezes converge; resume is refused unless the thread's current state shows the pending filing interrupt; the gate validates the resume payload and re-interrupts on typed rejection (record stays retryable); store CAS remains the final arbiter of FILED.
8. **No event-loop starvation.** All ported sync domain code runs via `asyncio.to_thread` on a bounded pool (recorded constant); CP-MODEL calculation keeps process isolation with the legacy aggregate per-request deadline.
9. **Admission ceiling is derived, not stored.** `COUNT(*)` of non-terminal runs/builds inside the admission transaction (MAX_ACTIVE_JOBS = 20); recovery reconciles statuses first. Capacity self-heals after crashes.
10. **Cut narrowed.** Notes (including promotion) and assumptions stay in the MVP — promotion mints sources and carries invariant-1 guarantees (no withdrawn-source resurrection, cross-ledger atomicity) with no other asserting surface. The report-era cut is now only: thesis, recommendation matrix, legacy report freeze/approve/export.
11. **Registry honesty and caps.** The rewritten runner drives every per-module table (authority files, output caps, projections, bundle membership) from the registry — then the three new wirings genuinely touch only the registry. Recorded host budget policy: CP-1C 12k, CP-1D 12k, **CP-5 24k** (it consumes every upstream artifact; 16k plausibly truncates). A `max_tokens` stop-reason fails the module immediately as AGENT_OUTPUT_INVALID and does not consume the shared repair.
12. **Execution-schema versioning.** A state schema version is stamped into pinned state; resume under a mismatched version fails closed with a typed error (operator path: re-freeze / re-run). langgraph, checkpointer, and langchain-anthropic versions pinned exactly.
13. **Event log correctness under parallelism.** Per-run sequence from a counter row locked in the event-writing transaction; every event insert rides a conditional state transition (zero rows updated → no event), giving exactly-once terminal events by construction.
14. **Host-owned request identity.** Reservation digests and token-count preimages are computed from host-owned canonical fields only, never adapter internals; a congruence test asserts count/create equivalence and that refusal / max_tokens / pause_turn stop reasons reach the host validator.
15. **Provider concurrency cap restored.** One `asyncio.Semaphore(2)` at the model boundary; acquisition waits bounded by remaining wall clock; queue-wait is excluded from the active-time meter.

## 11. Second-pass amendments (2026-08-26, user review — binding; wins over §§1–10 where they conflict)

1. **The pin is a blob, not scalars.** Graph state carries the immutable `plan` blob (as legacy `run["plan"]`) plus `plan_digest = digest(plan)` computed once at gate exit. Every node re-asserts `digest(plan) == plan_digest` on entry; pinned identity is read out of the plan, never from loose state keys. No un-annotated channel carries pinned identity.
2. **Checkpointed digests are expectations, not authority.** Every consumer re-reads the store record by id and recomputes its digest per attempt (legacy `workflows/domain.py:1340` semantics); mismatch is a typed failure. A resumed run never trusts its own snapshot.
3. **Withdrawal checks are live, always.** `read_evidence` re-checks the source's withdrawn flag on every call, including after resume from any interrupt; the resume path re-runs all live authority checks. Test: withdraw a pinned source while the run sits at an interrupt → resume fails closed.
4. **CP-6 is registered deterministic.** It terminates the in-scope FULL_CREDIT full route (`FULL_CREDIT_32.non_executable_module_ids == []`); the MVP module union is 18 (CP-PARSE, CP-0, CP-1, CP-1A, CP-1B, CP-1C, CP-1D, CP-2, CP-2A, CP-2E, CP-2G, CP-2H, CP-3, CP-4, CP-4C, CP-5, CP-6, CP-L10). Dropping a verified route node is a methodology change and out of bounds.
5. **Execution mode is per (module, profile).** Registry schema: `mode: {FULL_CREDIT_32: agent|deterministic, LITE_CREDIT_22: deterministic}`. Deterministic SCREEN is a recorded MVP choice, not a catalog property (`SCREENING_ONLY` is CP-L10's artifact `decision_scope`, nothing more). Widening agent execution to all FULL-depth routes (vs legacy's single `is_canonical_full_credit` route) is an extension and is tested per route.
6. **Run graphs have no data-selected edges at all.** Nodes raise typed terminal errors; one graph-boundary handler finalizes failure. The invariant-10 claim is stated narrowly: the module node set and dependency edges are a pure function of (pathway, depth); no branch can add, skip, reorder, or substitute a module. The deliverable graph's file/request-changes branch is a human decision at an interrupt, which is exactly what invariant 5 requires — not runtime autonomy.
7. **CP-PARSE alias carve-out.** The registry alias map resolves CP-PARSE to its own stage-0 node, overriding the catalog's `absorbed_by: CP-0` for node addressing; MODULE_GRANULARITY.md records the collision and carve-out.
8. **Active time is measured segments, never wall-clock subtraction.** The ledger accrues only explicitly timed host-operation segments; nothing derives from `now - started_at`. An interrupted run accrues zero at a human gate (`test_cpdr_approval_wait_is_excluded_while_planning_time_is_charged` re-hosts on the new gates).
9. **CP-DR contractual rows re-host; they are not an exclusion category.** The 44 contractual rows in CP-DR files re-host as follows: budget/ledger/validation/prompt-separation/secret-hygiene/finalization rows onto the nine agent modules and the shared loop; the eight plan-approval-gate rows onto the deliverable filing interrupt. Only nine report-era rows (thesis/recommendation CAS + legacy report freeze/approve family, incl. the thesis halves of two mixed tests) and one methodology-draft row are excluded outright; `test_production_rejects_forged_forwarded_identity`'s auth assertions re-host on the new edge.
10. **Notes and assumptions confirmed in scope** (restates §10.10 after this pass's independent confirmation: promotion is an ingestion surface minting content-addressed sources).

## 12. Third-pass amendments (2026-08-26, six-area red-team — binding; wins over §§1–11 where they conflict)

Consolidation note: where §6 conflicts with §10/§11/§12 (output Σ vs Σ+max; CP-5 16k vs 24k), the §12 restatement below is the single binding budget contract. Sources: .agent-reviews/redteam.md third pass.

### 12.A Pin, digest, and state discipline

1. **Digest-preimage meta-rule.** Every digest preimage is an exact pinned projection — fields × order × time-source — implemented once per record type and shared by the writer and every later verifier. Digests are carried outside the digested blob; preimage = record minus the per-type exclusion set ({plan_digest}; snapshot {digest, id, previous_snapshot_id}; …). Optional keys are absent, never null. Golden tests: compile → checkpoint round-trip → re-assert passes; one-byte mutation fails.
2. **State is JSON-native plain data only** (str/int/float/bool/None/list/dict). No Pydantic models, tuples, datetimes, Decimals, or dataclasses in channel values; models exist only inside node bodies. The plan blob is deepcopied at gate exit and treated read-only. CI round-trips every state field through JsonPlusSerializer against BOTH savers asserting equality and recursive type identity. `durability="sync"` on gate and finalize supersteps.
3. **Unicode boundary.** Every string that can enter pinned state or events is validated at the API boundary: must UTF-8-encode, lone surrogates rejected, NFC-normalized — before any pin is computed.
4. **Single time authority.** The only timestamp below the pin is the pinned run `created_at` (microsecond-truncated ISO); `reporting_period`, analysis dates, and filenames are slices of it; nodes never call the clock for artifact content. Snapshot `accepted_at` is the recorded exception (snapshot digests are integrity-only, never content addresses). Test: mocked day-later clock reproduces identical artifact digests.
5. **Ordered preimage lists.** Upstream artifact refs iterate the pinned plan's dependency order; `source_ids` carry an explicit position; the digested source-set identity is the pinned six-field projection {id, case_id, version, source_ids, created_by, created_at}. Test: a resumed node recomputes a byte-identical input_fingerprint.

### 12.B Methodology authority

6. **Verify-at-use.** The plan pins the integrity-manifest digest at gate exit. Every authority-file read used for prompt assembly hashes the exact bytes fed to the model against the PINNED build's manifest entry; `plan.build_id == bundle.build_id` is checked per node pre-flight but the byte-level check is the guarantee. Mixed-authority and silent-swap scenarios are typed AGENT_AUTHORITY_MISMATCH failures.
7. **Authority assembly is methodology surface.** Wrapper text, reference-file order, and the "\n\n" join are pinned; a golden authority-digest test per module locks them; changing assembly is a methodology change. Acceptance-time recomputation (authority digest, CP-2B projection) stays byte-identical via the same registry-driven functions.

### 12.C Run and artifact lifecycle

8. **complete_node semantics.** (run_id, module_id, input_fingerprint) is a unique key enforced at commit with validate-then-replace arbitration: existing valid artifact → discard candidate, relink old id; existing invalid → delete and insert fresh id; final candidate re-validated. The relink path emits byte-identical write payloads (ids from the store lookup, never regenerated). Completion markers (completed_modules, phase) commit in the same transaction as artifact link/relink. All three branches tested.
9. **Error taxonomy is contract.** Store failure codes are a typed enum with the exact legacy strings; in evidence reads, authority checks (case/set/withdrawn) precede block-existence checks — AGENT_AUTHORITY_MISMATCH before AGENT_OUTPUT_INVALID; the adversarial suite asserts which code each refusal carries. Agent-module failures surface at run level as CANONICAL_GENERATION_FAILED with the specific code in the terminal attempt row.
10. **Citation contract = delivered-evidence exact set.** Inside the read_evidence tool: ledger charge → returned-set update → return is one ordered unit; a ceiling-rejected read leaves no expectation; final validation requires evidence_refs to equal the delivered set exactly.
11. **Repair and recorder rules.** Repairable iff ValueError-family raised by validate; the repair turn is tool-less; repair text ≤ 1,500 chars; a max_tokens stop-reason is immediate AGENT_OUTPUT_INVALID and does not consume the repair. Attempt recorder: scalar allowlist with str[:200], lists only ≤50 items × ≤160-char strings, kind[:40]; terminal rows are cap-exempt (append then [-100:] trim) and recorded only after provider interaction; non-terminal rows fail closed at 100; every row snapshots the digests in force at write time.
12. **Reservation semantics.** Canonical rules only: reserve persists the inflight digest before create; a timeout retry requires inflight == digest and is budget-free; reconcile adjusts to actuals and clears inflight; an unresolved inflight on resume is terminal budget-exceeded. CP-DR's divergent double-charging retry semantics do not port; affected re-hosted rows adjust with one-line justifications.
13. **Finalization prepay exception.** Terminal commits are prepaid at the fixed 5.0s allowance and bounded by a monotonic deadline enforced inside the store transaction (TimeoutError → budget-exceeded, rolled back).

### 12.D Budget metering and the model boundary

14. **Active-time = bracketed segments** (supersedes §11.8 and the second-pass revert). Σ of explicitly bracketed single-operation segments — one provider await, one evidence read, one validation, one store write, one sync CPU block — with no other await inside a bracket; charge-then-suspend at every lock, gate, and interrupt; budget check after every bracket; the reuse-validation and completion-write segments are bracketed; check_budget is the last statement before a node reports success. Coverage by construction: one `timed()` wrapper is the only call site, and a test asserts every step in the node sequence is wrapped. Gate/interrupt wait time accrues nothing (the re-hosted approval-wait row).
15. **Wall-clock enforcement is `asyncio.timeout`.** Every provider await (count and create) runs inside `asyncio.timeout(min(150, remaining_active_seconds))` mapped to AGENT_PROVIDER_TIMEOUT with the inflight digest left unresolved. The SDK per-request timeout is an inner hint; `default_request_timeout=150` is pinned and never None.
16. **One host-owned request builder.** The payload is built once per turn from host-canonical fields; count and create go directly to the adapter's async client (`messages.count_tokens` / `messages.create`); the count body is the payload restricted to the endpoint's accepted fields; read_evidence is the raw Anthropic tool dict (strict); system is a plain string. ChatAnthropic serves as message formatter, output normalizer, and pinned client factory; `invoke()`/`bind_tools`/`with_structured_output` are not on the metered path. The reservation digest covers the host-built payload minus timeout.
17. **Usage validation targets raw usage** (response_metadata / llm_output), never `usage_metadata` (which zero-fills): the usage key must be present with `input_tokens` int > 0, `output_tokens` int ≥ 0, cache-token fields absent or 0; violation is AGENT_OUTPUT_INVALID with the reservation unresolved.
18. **Adapter pins asserted by test:** `max_retries=0`, `disable_streaming=True`, `cache=False`; `max_tokens` set from the registry unconditionally per call (startup assert + per-module congruence test); two-build byte-equality test for retry identity; per-stop-reason stub tests (`refusal`, `max_tokens`, `pause_turn`, absent) proving each reaches the host validator; the validator's single authority is `stop_reason` ∈ {tool_use, end_turn}.
19. **Provider concurrency: integer slot counter (2)**, synchronous check-and-decrement on the event loop, typed AGENT_BUDGET_EXCEEDED denial (legacy semantics restored; supersedes §10.15's blocking semaphore), release in finally.
20. **Envelope scaling.** Per-route envelope from (compiled route, registry): N = route agent-module count; evidence_reads = 10·N; evidence_bytes = ⌈(5 MiB/6)·N⌉; input_tokens = ⌈(500,000/6)·N⌉; output_tokens = Σ per-module caps + max(caps); turns = evidence_reads + N + repairs; active_minutes 15; provider_retries 1; repairs 1. N=6 reproduces legacy exactly. count_tokens never charges a turn (tested). Residual liveness risk owned by the lead engineer, checked at the phase-6 live smoke.

### 12.E Interrupt and resume correctness

21. **Resume ticket.** A one-shot CAS row keyed (thread_id, interrupt_id) is written when an interrupt surfaces; the gate consumes it transactionally before acting on the resume value; a racing second execution finds it consumed and terminates without side effects. The §10.3 per-thread locks remain on every resume entry point (API, recovery, upgrade).
22. **Resume APIs verify effect.** After any resume, the endpoint re-reads state and requires the targeted interrupt gone AND the domain CAS advanced; anything else returns typed RESUME_NOT_APPLIED with the current interrupt id (late/duplicate/stale resumes are silent no-ops in langgraph 1.2.11 and must never surface as success).
23. **Deliverable thread identity includes build_id:** thread_id = digest(case_id, pathway, draft_version, draft_digest, build_id); the filing gate re-asserts frozen.build_id == plan.build_id == approval.build_id and serves only the already-rendered vault bytes whose digest equals the approved preview_digest — filing never re-renders.
24. **Schema version at the raw layer.** The stamp is read from the raw checkpoint channel values and checked before any Pydantic coercion; pinned fields have no defaults, so an old checkpoint missing a new pinned field raises instead of fabricating.
25. **Retention and upgrades.** Terminalized threads are deleted (`delete_thread`) once the domain store holds the full audit trail; any dependency-pin bump requires draining parked threads or a park→resume test on a copied thread first; prod uses `psycopg_pool` with health checks.

### 12.F Module wiring dispositions (attended-surface audit)

26. All nine agent modules replicate the five legacy neutralization mechanisms: host wrapper (no conversational channel; declared safe defaults govern in silence), pins labeled untrusted, conflict→fail-closed validation, host discard-and-recompute of identity/trace/registry/confidence, and the qa-Passed gate (non-Passed module QA is terminal).
27. CP-2G's three staged questions are pinned from its own contract defaults (three consecutive fiscal years after the latest CP-1 actual; CP-1-anchored base; BASE+DOWNSIDE), validated pre-dispatch. CP-1C is pinned to supplied-only evidence (web discovery is structurally banned by invariant 1); absent disclosed peers it emits its Blocked/document-disclosed terminal; a pin-time peer_list is the recorded future upgrade. CP-5 runs unattended (deterministic Severity Engine); reviewer authority maps onto existing gates — snapshot acceptance refuses a CP-5 Blocked artifact, and Restricted rides the snapshot into deliverables as a surfaced limitation. CP-2's superseded deep-synthesis phrase-trigger is declared inert by the wrapper (the bundle is never edited).

### Appendix A — transcribed budget constants (the literal contract; each gets a test asserting the literal value)

| Constant | Value | Legacy source | New home | Test |
|---|---|---|---|---|
| Manifest max blocks | 2,000 | workflows/domain.py:44 | budget/constants.py | test_manifest_caps_literal |
| Manifest max bytes | 262,144 (256 KiB, canonical-JSON measure) | :45 | budget/constants.py | test_manifest_caps_literal |
| Manifest filename chars | 255 | :46 | budget/constants.py | test_manifest_caps_literal |
| Manifest media-type chars | 160 | :47 | budget/constants.py | test_manifest_caps_literal |
| Manifest field chars | 160 | :48 | budget/constants.py | test_manifest_caps_literal |
| Locator string chars | 500 | :49 | budget/constants.py | test_manifest_caps_literal |
| Locator items/container | 100 | :50 | budget/constants.py | test_manifest_caps_literal |
| Locator depth | 8 | :51 | budget/constants.py | test_manifest_caps_literal |
| Locator total nodes | 500 | :52 | budget/constants.py | test_manifest_caps_literal |
| Locator floats must be finite | — | :66-67 | manifest validator | test_manifest_caps_literal |
| Finalization allowance | 5.0 s (prepaid, in-transaction deadline) | :54 | budget/constants.py | test_finalization_allowance |
| Per-module output caps | CP-1 32k; CP-1A 12k; CP-1B 12k; CP-2 16k; CP-2A 16k; CP-2G 24k; CP-1C 12k; CP-1D 12k; CP-5 24k | canonical.py:96-105 + §10.11 policy | modules/registry.py | test_registry_output_caps |
| Per-module allowances | 10 evidence reads; 5 MiB/6 evidence bytes; 500k/6 input tokens | canonical.py:106-121 ÷ 6 | budget/envelope.py | test_route_envelopes (N=6 == legacy) |
| Output ceiling | Σ caps + max(caps) | canonical.py:109 | budget/envelope.py | test_route_envelopes |
| Turns | evidence_reads + N + repairs | canonical.py:107-121 | budget/envelope.py | test_route_envelopes |
| Active minutes | 15 | canonical.py envelope | budget/constants.py | test_route_envelopes |
| Provider retries / repairs | 1 / 1 | canonical.py envelope | budget/constants.py | test_route_envelopes |
| Provider timeout | 150.0 s (outer asyncio.timeout; SDK hint) | config.py:40, provider.py:98 | config.py + loop | test_timeout_clamp |
| Provider concurrency slots | 2 (non-blocking, typed denial) | provider semaphore | budget/constants.py | test_provider_slots |
| Evidence read block_ids per call | 1–50 unique | domain.py read_evidence | evidence tool | test_read_evidence_bounds |
| Evidence bytes measure | len(json.dumps(result, sort_keys=True)) — identical serialization to the tool_result | domain.py:1447, provider.py:412 | shared function | test_evidence_bytes_identity |
| Attempt caps | non-terminal fail at 100; terminal [-100:] ring | domain.py:1359-1376 | recorder | test_attempt_recorder |
| Repair text limit | 1,500 chars | provider.py:437 | loop | test_repair_rules |
| Max active jobs (admission) | 20, derived by COUNT(non-terminal RUNNING executions); interrupt-paused threads hold no slot | store.py MAX_ACTIVE_JOBS | admission gate | test_admission_ceiling |
| Lease/heartbeat/fencing | replaced by: per-thread locks + advisory lock + execution epoch WHERE-predicate on every ledger/event/artifact write + resume tickets | store.py, domain.py | storage layer | test_epoch_fencing (re-hosts excluded fencing rows) |
