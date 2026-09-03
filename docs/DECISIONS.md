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

1. **Digest-preimage meta-rule.** Every digest preimage is an exact pinned projection — fields × order × time-source — implemented once per record type and shared by the writer and every later verifier. Digests are carried outside the digested blob; preimage = record minus the per-type exclusion set ({plan_digest}; snapshot {digest, id}; …). A snapshot binds `previous_snapshot_id` because that chain edge selects the prior model authority for Distressed overlays. Optional keys are absent, never null. Golden tests: compile → checkpoint round-trip → re-assert passes; one-byte mutation fails.
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
11. **Repair and recorder rules.** Repairable iff ValueError-family raised by validate; the repair turn is tool-less; repair text ≤ 1,500 chars; a max_tokens stop-reason is immediate AGENT_OUTPUT_INVALID and does not consume the repair. Attempt recorder: scalar allowlist with str[:200], lists only ≤50 items × ≤160-char strings, kind[:40]; terminal rows are cap-exempt and recorded only after provider interaction; the cap and terminal ring are superseded by §14.7; every row snapshots the digests in force at write time.
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
| Attempt caps | legacy 100; superseded by §14.7 | domain.py:1359-1376 | recorder | test_attempt_recorder |
| Repair text limit | 1,500 chars | provider.py:437 | loop | test_repair_rules |
| Max active jobs (admission) | 20, derived by COUNT(non-terminal RUNNING executions); interrupt-paused threads hold no slot | store.py MAX_ACTIVE_JOBS | admission gate | test_admission_ceiling |
| Lease/heartbeat/fencing | replaced by: per-thread locks + advisory lock + execution epoch WHERE-predicate on every ledger/event/artifact write + resume tickets | store.py, domain.py | storage layer | test_epoch_fencing (re-hosts excluded fencing rows) |

## 13. MVP-extension amendments (2026-08-27, phases 4–5 build — dated deviations and confirmations)

1. **CP-MODEL calculation runs in-process under the legacy 30s aggregate
   request deadline** (deviation from §10.8's process isolation). Rationale:
   golden-input calculations complete in well under a second, nothing in the
   calculation path executes untrusted code, and the spec suite pins the
   deadline behavior, not the process boundary. Restoring process isolation is
   a service-internal change (`caos/models/service.py::_calculate`).
2. **The deliverable filing gate is a store-backed parked-thread state
   machine, not a LangGraph thread** (deviation from §2's "own small graph").
   The store CAS was already the final arbiter (§10.7); §12.21/22 semantics
   (one-shot single-effect resume, RESUME_NOT_APPLIED on stale/duplicate)
   are asserted by the spec suite against this seam. A LangGraph interrupt
   would add a checkpointer without adding arbitration.
3. **Acceptance no longer moves the visible snapshot** — only an explicit
   switch does, and divergence surfaces as `switch_required` (this is the spec
   suite's reading of the snapshot-lens contract; §2's finalize gate is
   unchanged).
4. **Dev identity default subject is `analyst`** (was `local-analyst`) so
   headerless local calls act as the actor the fixtures seed cases with.
   Production identity derivation is untouched.
5. **Deliverable model authority is resolved from seeded/stored model-identity
   records** (`deliverable_models`); wiring it to the live Model Builder store
   is a record-shape mapping, not a service change.
6. **Two spec rows are red by catalog contradiction, unedited** (tests are the
   approved specification; the user decides): the CP-3-binding row runs the
   LITE RELATIVE_VALUE route whose verified catalog selection is
   CP-0/CP-L10/CP-1C — no CP-3 node exists to bind, and adding one is a
   methodology change (§11.4); the CP-2G deterministic-handoff row still
   contradicts the agent-wired registry union (recorded in phase 3).
7. **§7's three isolated registry-only wiring commits are performed**
   (a0ff900, 9a50c5b, fa72153, ddb014b) — see MODULE_GRANULARITY.md's dated
   amendment for the receipts.

8. **(2026-08-27, user-approved spec amendment)** The CP-3 loan-universe
   binding test now targets the RELATIVE_VALUE FULL route via the
   scripted-canonical run seam — resolving §13.6's first contradiction the
   right way round (the LITE selection stays untouched). Scripted runs now
   take fixtures only for the six canonical modules; every other node runs its
   real deterministic path, so the CP-3 binding is exercised by the same code
   production uses. Red count drops to 13 (12 environment + the CP-2G row).

9. **(2026-08-27, user-approved spec amendment)** The CP-2G handoff-discipline
   test now asserts on the canonical agent envelope produced through the
   scripted-canonical seam, resolving §13.6's second contradiction: CP-2G
   stays agent-wired, the stored handoff must still compute nothing Model
   Builder owns and carry no signing claims, and the original vacuous
   `or`-form signing check is a plain ban. Red count drops to 12 — exactly the
   recorded environment defects; every contractual row is green.
10. **(2026-08-27, user-approved spec amendment — phase-6 reconciliation)** The
    eleven asyncio-blocked spec tests are repaired: the three
    `asyncio.get_event_loop().run_until_complete` glue lines (the
    `evidence_context` fixture plus two `test_state_spec` scenarios) become
    `asyncio.run`; test bodies untouched. All eleven pass. The sole remaining
    red is the surrogate-serialization test, whose httpx client cannot encode
    its own request on this interpreter (contract verified server-side with a
    raw-bytes 422).
11. **(2026-08-27)** The D1/D2 deferrals land: `test_finalization_metering.py`
    carries one test per re-hosted row plus the §12.14 wrapper-coverage test
    enumerating the loop's step table. `_finalize_node` now meters the final
    re-validation as a §12.14 bracket (charged even on throw) and fails the
    run closed on an over-ceiling charge before `finalize_success` — a success
    commit never lands past the budget ceiling (the 174+10 contract, expressed
    as charge-then-commit rather than a literal deadline parameter). Suite:
    380 passed, 1 red (§13.10).

## 14. Enterprise-testing amendments (2026-09-01, user approved — binding; wins over §§1–13 where they conflict)

1. **The MVP qualification scope is six pathways.** Full Credit, Earnings
   Update, Covenant & Refinancing, Relative Value, Distressed & Restructuring,
   and Deep Research must pass their supported-depth contracts. The four-path
   cut in §1 and `docs/SCOPING_PROPOSAL.md` is superseded. Deep Research keeps
   its governed-brief and approval contract; this amendment does not invent an
   unsupported screen depth.
2. **Source documents are the sole analytical input.** Runtime ingestion is
   user-upload only. EDGAR, filing fetch, peer discovery, web acquisition, and
   implicit source retrieval remain prohibited. The host owns document
   classification, source dispositions, route selection, pinning, and the
   recovery journey.
3. **Fixed prose is never deterministic analysis.** The placeholder
   `SYSTEM_ANALYSIS` payload remains a development host control and cannot
   authorize ordinary completion, acceptance, modelling, publication, or
   qualification. A semantic module executes through the one qualified
   provider binding at every supported depth. Host-deterministic execution is
   limited to extraction, normalization, allowlisted calculations, validation,
   canonicalization, rendering, and other operations whose result is fully
   determined by pinned inputs.
4. **CP-PARSE and CP-0 remain separate static graph nodes.** CP-PARSE owns the
   preparation inventory and fidelity disposition; CP-0 owns analytical source
   readiness. Both consume the host-built pinned source manifest and the
   verified CP-0/CP-PARSE methodology authority. This preserves the existing
   graph identity without treating a filename inventory as source-readiness
   analysis.
5. **Provider qualification follows effective execution policy.** Widening a
   module or depth from fixed host control to provider execution changes the
   parameter/context digest and invalidates earlier qualification records.
   Enterprise startup still exposes exactly one current qualified Anthropic
   binding and no picker or fallback.
6. **Host controls are not candidate evidence.** Scripted providers, golden
   outputs, and placeholder capabilities may prove orchestration and failure
   boundaries only. A pathway is available for enterprise testing only after
   its ordinary run, source coverage, model effect, deliverable, publication,
   and reconstruction contracts pass. Live-model analytical qualification is
   retained separately and fails closed when credentials, corpus bytes, answer
   keys, or reviewer evidence are absent.
7. **Enterprise route expansion changes two host ceilings.** Each module is
   limited to 10 evidence reads, 873,814 returned bytes, and 200 distinct
   evidence references (with 1–50 unique block IDs per read), so every delivered
   set remains representable by the canonical schema. The attempt audit cap and
   terminal ring are 256 records, with a test proving that this covers the upper
   bound for every MVP pathway/depth including calculation, retry, repair, and
   terminal rows. These values are included in the provider parameter-context
   digest; changing them invalidates prior provider qualifications.
8. **Methodology calculations have host-owned work-factor bounds.** The
   recovery-waterfall calculator is limited to 100,000 case/claim/cost work
   units before verified vendor code executes. The limit is part of the
   provider parameter-context digest and rejects oversized valid JSON as
   `METHODOLOGY_INPUT_INVALID`.
9. **Confidence provenance is explicit.** The host validates bounds and
   recomputes score arithmetic, but the lineage/finding/coverage counts remain
   qualified-provider declarations until analyst acceptance. Every canonical
   artifact labels that basis and states that analyst review is required; it
   never represents those inputs as host-attested facts.
10. **Analytical insufficiency is not malformed output.** A valid canonical
    result with source gate `fail` or `partial` terminates immediately as
    `SOURCE_EVIDENCE_INSUFFICIENT` or `SOURCE_EVIDENCE_RESTRICTED`; it does not
    consume the single JSON-repair allowance or collapse into
    `AGENT_OUTPUT_INVALID`.
11. **The vendored Deploy V bundle is now maintained in-tree, and that is a
    deviation — recorded here rather than left implicit.** Item 2's
    supplied-only prohibition was applied by editing the vendored methodology
    itself, not by wrapper or registry: CP-1C's peer-source hierarchy drops its
    web-scrape tier and its declared default becomes
    `{"peer_set":"supplied_or_document_disclosed","source_mode":"supplied_only"}`;
    CP-4's `REF_CP-4_EDGAR` acquisition lane is deleted from `CP-4_RUNBOOK.md`
    and `REF_CP-4_STEPS.md`; `CANON_SHARED.md`'s "Controlled Public-Web
    Exception" becomes the "Supplied-Evidence Boundary". Sixteen files change,
    build id `7fa967c4…` → `1912cb03…`, and the 307-file inventory and path set
    are unchanged; the manifests are regenerated by
    `caos/scripts/regenerate_deploy_v_integrity.py`.

    This **supersedes** §12.27's parenthetical "the bundle is never edited" and
    the identically worded standing rule under invariant 4 in `CLAUDE.md`. Both
    must be amended rather than left asserting something untrue.

    Invariant 4 itself is unchanged: authority is still the verified bundle,
    still hashed on the bytes at use, and a run pinned to one build still never
    executes under another. What changes is *who may issue a build* — this repo
    may now, where previously only an upstream release could.

    The cost is explicit. Regenerating the integrity manifest is part of a
    bundle change, so the whole-tree pin in
    `test_vendored_bundle_is_the_approved_unmodified_release` moves with every
    such change and stops being independent evidence that the tree is
    unmodified; it degrades to a consistency check. This dated entry, not that
    test, is therefore the authority for the current bundle contents, and any
    further bundle change requires its own entry. Where the sanctioned seam can
    carry the behaviour instead — the wrapper's inert-phrase declaration, or a
    registry field such as CP-1C's existing `source_mode` — it remains
    preferred, because it leaves the pin meaningful.

12. **Screen depth is provider-backed (2026-09-02, decision D1).** Supersedes
    §1's "SCREEN routes are deterministic end to end" and the deterministic-
    screen wording that stood in `ENTERPRISE_TESTING_READINESS.md` RUN-030 and
    `ENTERPRISE_READINESS_PLAN.md` scope decision 4 (both amended the same day).
    `modules/registry.py` defaults `mode_screen` to `agent`; CP-PARSE, CP-0,
    CP-2E, CP-2H, CP-3, CP-4, CP-4C, CP-6 and CP-L10 execute through the one
    qualified provider at both depths, with the same verified assembled
    authority and the same host tools. Screen determinism now means identical
    host-validated identity for identical pins and build: the plan digest, the
    source pins, the calculation records (canonical input and output digests)
    and the canonical envelope are byte-equal across replays; provider prose is
    compared by validated canonical contract (AUD-019). Consequences recorded
    here, not discovered later: no route runs without a provider, so the
    keyless browser gates bind `CAOS_PROVIDER=host_control` (item 15); the
    provider parameter/context digest changed (new tool set, new modes, the
    §14.7 budgets), so every earlier qualification record is invalid (§14.5).

13. **Deploy V build `237bf4bc…` (2026-09-02, decisions D2 and D7).** The
    second in-tree bundle edit under item 11's rule. Files: the cp-0 skill
    (`skills/cp-0-source-readiness/SKILL.md`) split into two runnable profiles,
    CP-PARSE (owns `document_parse_manifest` and the P1–P8 registers) and CP-0
    (consumes it, owns `source_readiness_register`), which implements item 4's
    separate static nodes; `skills/cp-2h-ratings-migration-trigger/scripts/
    bond_analytics.py` gains `MAX_BOND_YEARS = 100` and
    `MAX_CALL_SCHEDULE_ITEMS = 100` as defence in depth, while the authoritative
    bound lives in the host (`methodology/execution.py::_enforce_work_factor`,
    item 8) and refuses first as `METHODOLOGY_INPUT_INVALID`; the module catalog
    (`CREDIT_OS_V_MODULE_CATALOG_v2.json`) records CP-PARSE as a
    `runnable_profile` instead of an alias, adds `CP-L10 → CP-2A` (REQUIRED,
    `SCREENING_ONLY`) in place of `CP-0 → CP-2A` on the FULL_CREDIT and
    DISTRESSED screen routes, adds `CP-4C → CP-6` on the FULL_CREDIT and
    DISTRESSED full routes, and adds `CP-3` to the DISTRESSED full route at
    stage 9 with edges from CP-1, CP-2, CP-2G and CP-2H and to CP-6; the
    manifests, baseline, retrieval index and copilot prompts are regenerated
    (`caos/scripts/regenerate_deploy_v_integrity.py --check` is current). Why
    the seam could not carry it: the profile split changes the vendored skill's
    own trigger and output contract, which a wrapper cannot restate without
    contradicting the skill text the model reads; the catalog is the route
    authority `engine/graphs.py` compiles, so an edge is a bundle change by
    definition; the vendor bound is duplicated on purpose. Costs recorded: the
    tree pin moves `1f1a71d3…` → `9905f67b…`; every entry in
    `GOLDEN_AUTHORITY_DIGESTS` was regenerated (the assembled authority carries
    the catalog); `caos/deploy/verify_image_resources.py` expects 310 checks
    (307 pinned files plus the baseline, manifest and child-schema-registry
    files `DeployVBundle.verify` now verifies against the integrity source hashes). Every compiled route cell is pinned by digest in
    `spec/test_runs_spec.py::ROUTE_GOLDENS`; a later route change moves that
    table in the same commit as its own entry here.

14. **Calculation completeness is a typed model outcome, never evidence
    insufficiency (2026-09-02, decision D6).** A `run_methodology_calculation`
    call whose verified calculator returns no usable result (per
    `calculation_output_complete`) is answered with a typed tool result,
    `{"complete": false, "code": "METHODOLOGY_CALCULATION_INCOMPLETE"}`, and
    the model may run that calculator once more; the retry spends the module's
    single repair allowance, shared with the final-output repair. After the
    allowance, the core calculators (`credit_metrics` on CP-1 and CP-2G;
    `funding_gap` and `recovery_waterfall` on CP-4C in a DISTRESSED run) end
    the run as `METHODOLOGY_CALCULATION_INCOMPLETE`; every other assigned
    calculator that stays incomplete becomes a host-declared limitation: absent
    from the pinned `calculations`, present in the artifact's
    `calculation_limitations`, and flagged `host:calculation_incomplete:<id>`
    in the handoff `limitation_flags` (a host-derived field in the provenance
    block). `SOURCE_EVIDENCE_INSUFFICIENT` and `SOURCE_EVIDENCE_RESTRICTED`
    remain reserved for the provider-declared source gate (item 10); item 12.27's
    CP-1C terminal for absent peers stands. Provider doubles that drive host
    controls feed answer-keyed inputs (`caos/tests/calculator_fixtures.py`) so
    every defence under test is actually reached.

15. **Authority locking, publication binding and the development provider
    (2026-09-02, decisions D8 and D9).** The process-wide authority lock covers
    mutations only (source ingest, withdrawal, note promotion, run
    finalization, model queueing and sign-off); transient model reads run
    unguarded, and `Engine.accept` waits for the lock in a worker thread so the
    event loop keeps serving. Model build completion and every model export
    publish through a compare-and-swap that also requires each pinned source
    to be live in the same statement (`expected_live_source_ids`); a withdrawal
    that lands first yields the typed `MODEL_AUTHORITY_CHANGED` /
    `MODEL_EXPORT_AUTHORITY_CHANGED` records, never a READY file. Intermediate
    snapshots in a Distressed ancestry are validated by identity; only the base
    whose artifacts are consumed must be fully live. The residual
    statement-level window on PostgreSQL is Task 12's to close with database
    locks. `CAOS_PROVIDER=host_control` binds a development-only answer-keyed
    provider (`engine/host_control.py`, identity `host_control`) for the
    keyless browser gates; production refuses it at the provider builder and at
    engine construction. Local development evidence is produced on Python 3.14
    (decision D3), matching nightly and the image.
16. **Deep Research: governed brief and digest-bound plan approval (2026-09-02,
    Task 7).** `DEEP_RESEARCH` joins the engine cut at full depth only
    (`runtime.supported_depths`; the LITE route still compiles, the engine
    never starts it, so `startable_routes()` is the one list the case wire,
    the corpus control and the probes enumerate). CP-DR is a registry entry
    (`modules/registry.py`, `plan_approval=True`, golden authority digest
    `76e990f4…`) over the vendored `cp-dr-deep-research` skill; the bundle is
    untouched. The brief (`contracts.ResearchBrief`, every string
    `BoundaryText`) is validated before any row exists, locked in the run's
    creating transaction (`run_research`), and bound into run authority as
    `plan.research_brief_digest` at gate exit; it selects nothing about the
    node set (invariant 10). After CP-0 succeeds, the CP-DR node builds the
    plan as a pure function of the pinned run plan, the brief and the upstream
    artifacts (`engine/research.py`: three workstreams — primary, adversarial,
    synthesis — `source_mode` fixed to `supplied_only`), persists it with
    `sha256:<canonical digest>` and parks the run on the second interrupt
    `PLAN_APPROVAL_REQUIRED` (events `run.paused`, `research.plan_ready`;
    no metered bracket covers the wait). Approval is a store compare-and-swap
    on the exact proposed hash while the run is parked on this gate
    (`RESEARCH_PLAN_STALE`, `RESEARCH_PLAN_NOT_PENDING`), one transaction
    with the run transition, the ticket, the run event
    `research.plan_approved` and the audit event of the same name; the engine
    re-checks provider identity and pinned-source liveness first and never
    drives the graph inline. On re-entry the node recomputes the plan and
    refuses `RESEARCH_PLAN_MISMATCH` when the approved hash is not the plan
    that would execute; a `POST /resume` re-parks, and startup recovery
    re-enters an interrupted thread whose run is already `running` (approved,
    then crashed before the continuation) rather than skipping it. The approved scope rides the
    module's host identity (`research`: brief, brief digest, approved hash,
    workstreams) into the prompt under the untrusted label and into the
    artifact, and the host stamps the nine CP-DR envelope fields the pinned
    common validator requires (`scope_type`, `scope_key`, `subject_name`,
    `research_question`, `source_mode`, `approved_plan_hash`,
    `coverage_score` = validated field coverage, `research_status`,
    `research_stop_reason`) — a stored CP-DR artifact is always `Complete`
    because a partial or failed gate is a typed refusal in the validate step.
    Wire: `CanonicalRunResponse.research` (`ResearchStateResponse`, present on
    Deep Research runs only), `GET /api/runs/{id}/research-plan` (case member)
    and `POST /api/runs/{id}/research-plan/approve` (case writer; 404 for
    outsiders, 403 for readers, 409 stale/not-pending, 422 malformed hash).
    `deep_research_available` is `Engine.deep_research_availability()` — the
    cut, the compiled route, the registry and the provider binding — never a
    literal. Deep Research is model-optional: it declares no numeric effect
    (item 18 supersedes the original "acceptance queues no build" —
    acceptance now queues a `DEEP_RESEARCH_REVALIDATION` overlay when a Full
    Credit model exists in the case, and `queue_build` answers
    `MODEL_NOT_READY: DEEP_RESEARCH_NO_NUMERIC_EFFECT` when none does); the
    deliverable draft, freeze, file and reconstruction path is the ordinary
    one. Host control proves orchestration only; the C22 pack and live-model
    qualification are external inputs.
17. **Document-first intake (2026-09-02, Task 8, ETR-B01).** Supplied
    documents are the only analytical input of the golden journey.
    `POST /api/intake` is one strict multipart transaction (`files`, optional
    `case_id`) served by `intake/service.py`, which orchestrates the existing
    domain services and never another route. Admission is prepare-all then
    admit-all: `sources/domain.py::prepare_upload` is the single-source
    route's own check sequence split off from the store write (`ingest_upload`
    composes the two, so the route and its tripwires do not move); any file
    that fails refuses the whole pack with a typed `422` and one structured
    finding per file, persisting nothing but a content-addressed vault blob
    and an `intake.refused` audit row. `DomainStore.admit_intake` commits the
    case (when new, with its membership and `case.created`), every source
    row, one source-set version, `source.ingested` per source, the
    `case_intakes` row and `intake.admitted` in one transaction, so no
    partial, invisible or unaudited admission can exist. Host classification
    (`sources/classify.py`) is deterministic and bounded: document type,
    period, revision status, issuer candidate and text layer are read through
    fixed signal tables over the first blocks and the filename; each value
    carries its signals and a confidence, the wire labels the set
    `host_classification`, and the UI shows them as machine suggestions.
    Instructions in documents are inert because type and route depend on
    structural signals — a form heading, a legal instrument, a brief that
    validates against `ResearchBrief`, a workbook that parses against the
    CP-3 template — never on imperative text. The route is Full Credit at
    full depth unless the pack proves a narrower objective: a valid brief
    file selects Deep Research (the brief is still the analyst's, supplied as
    a file); a valid loan-universe workbook selects Relative Value and is
    imported through `import_loan_source` so the gate pins it; a
    restructuring instrument selects Distressed; an earnings-only pack
    selects Earnings Update; a legal-only pack selects Covenant &
    Refinancing. Case resolution never crosses membership: an explicit case
    needs write standing (404 outsiders, 403 readers); otherwise the actor's
    own cases are matched by normalized issuer and only an unambiguous match
    resolves; mixed issuers (`INTAKE_ISSUER_AMBIGUOUS`) and a pack that
    disagrees with the explicit case (`INTAKE_ISSUER_MISMATCH`) are refused.
    Exact duplicates collapse to one source with both names on the manifest;
    a same-name different-bytes pair is `INTAKE_SOURCE_CONFLICT`; a restated
    document supersedes the original for its period and both stay admitted
    and linked. A pack with no usable evidence stays admitted and returns
    the typed `INTAKE_EVIDENCE_INSUFFICIENT` clarification with its next
    action; dropping the missing document into the same case admits only
    what is new and starts the run. An engine refusal leaves the pack
    admitted in `execution_unavailable` with its typed code. The intake key
    (actor, normalized issuer, sorted digests) makes a double submit return
    the same intake and run; `GET /api/cases/{id}/intake` and
    `cases.current_execution_id` are what refresh and restart read. The
    frontend adds the reserved `.cases-intake` panel — a real multi-file
    input behind its label plus a drop region, fenced by a local request
    counter and the authority match, adopting the case then the run through
    the reducer under the inert `intake` scope — and keeps the run console
    as the one home for progress and acceptance; a completed intake run is
    presented for review and never accepted on the analyst's behalf. Known
    bound: the 32 MiB edge body cap limits one request; a larger pack is
    admitted across intakes into the same case.
18. **Every pathway declares one model effect, and a model is source-complete
    or it is not READY (2026-09-02, Task 9, ETR-B12).** Full Credit builds the
    complete model from the six canonical artifacts as before. Every other
    pathway resolves through one overlay mechanism
    (`models/service.py::_resolve_overlay_snapshot`): the nearest validated
    Full Credit ancestor in the acceptance chain (intermediate snapshots by
    identity, the base fully live), the base build re-verified by
    recomputation, the accepted run's calculation records re-executed against
    the pinned binding record for record (`_validated_calculations`,
    generalised from the CP-4C check), and one `pathway_effects` entry
    (`caos.model-pathway-effect.v1`) on a byte-identical copy of the base tabs
    under the overlay's own input fingerprint. The base model's periods,
    assumptions and outputs are never rewritten (CALC-006 by construction);
    reported actuals, external forecasts and analyst scenarios keep distinct
    `authority` labels inside the effect. Effects: Earnings Update
    `EARNINGS_PERIOD_FORECAST_VARIANCE` (the run's verified CP-1/CP-1B
    `credit_metrics` periods as `REPORTED_ACTUAL`, and reported-minus-forecast
    per base and downside column for the same fiscal year, with
    `FORECAST_PERIOD_NOT_MODELLED`, `ACTUAL_NOT_DISCLOSED` and
    `ZERO_FORECAST_DENOMINATOR` as named gaps — never zero); Covenant &
    Refinancing `COVENANT_REFINANCING_ASSUMPTIONS` (CP-4 `covenant_headroom`
    tests and CP-4C `funding_gap` views as documentary terms, plus
    `assumption_updates` mapping a maximum-leverage test to
    `covenant.max_total_leverage`: `PROPOSED_FOR_SIGN_OFF` when the base slot is
    READY, `PROPOSED_REQUIRES_FULL_CREDIT_HANDOFF` when the accepted CP-2G
    handoff left it UNAVAILABLE, because the pinned engine lets a preview move
    a value and never a status; `UNMAPPED_COVENANT_TEST` otherwise); Relative
    Value `RELATIVE_VALUE_MARKET_MARKS` (the loan universe the run pinned at its
    gate, re-read and digest-verified, attached as a bounded row projection
    with `time_alignment` against the base model's latest reported period end
    and the run's analysis date — `ALIGNED`, `PRECEDES_LATEST_REPORTED_PERIOD`
    or `POSTDATES_ANALYSIS`, the last two as named limitations; a run with no
    pinned workbook reads `RELATIVE_VALUE_MARKET_MARKS_REQUIRED`); Distressed
    `DISTRESSED_SCENARIO_RECOVERY` (shape unchanged from §14.15); Deep Research
    `DEEP_RESEARCH_REVALIDATION` (`numeric_effect: NONE`, the base recomputed
    and compared, the brief digest and approved plan hash bound; with no Full
    Credit model in the case readiness is `DEEP_RESEARCH_NO_NUMERIC_EFFECT` —
    this supersedes item 16's "acceptance queues no build"). Acceptance of any
    of the six pathways queues its effect (`on_accepted`). Two further truthful
    readiness states: `FULL_DEPTH_REQUIRED` when the accepted route lacks the
    modules the effect consumes (screen-depth Full Credit, Earnings, Covenant
    and Relative Value; Distressed screen keeps CP-4C and overlays), and
    `PRIOR_FULL_CREDIT_MODEL_REQUIRED` for an overlay pathway with no Full
    Credit model in its chain (Distressed keeps `DISTRESSED_BASE_MODEL_REQUIRED`);
    `queue_build` answers `MODEL_NOT_READY: <code>` so the wire code is
    unchanged. Source lineage is part of every build: one row per source in the
    accepted snapshot's set with the intake disposition and reason (every intake
    of the case, later rows superseding), the expected consumers, the artifacts
    that cite it, whether a model-facing table names it, and one binding —
    `MODEL_INPUT`, `CITED_ANALYSIS`, `MARKET_MARKS`, `RESEARCH_BRIEF`,
    `SUPERSEDED`, `NOT_REQUIRED` or `UNBOUND`. A `used` document of a relevant
    class (annual, quarterly, earnings, guidance, legal, restructuring, market
    marks, brief) that is `UNBOUND` makes the model
    `MODEL_SOURCE_LINEAGE_INCOMPLETE` (NOT_READY, the detail naming the source
    ids); an `other` document nothing consumed is `NOT_REQUIRED` with its reason,
    never silently discarded. The lineage digest is in the input fingerprint,
    the lineage rides the payload, the preview worksheet and the export
    ("Source Lineage" audit sheet beside "Pathway Effects"), and the READY
    transition writes `model.build_ready` (build, snapshot, run, payload
    digest) in the same transaction. `HostControlProvider` reads one block of
    every pinned source, bounded by the module read allowance, so keyless runs
    are source-complete up to that allowance; the corpus double spreads one
    read of each of the thirty documents across the route. Loan-workbook cell
    text passes `validate_boundary_text` at the importer
    (`RV_CELL_TEXT_INVALID`, workbook REJECTED), closing the `CLAUDE.md` gap at
    the one seam every path shares. Deliverables still bind the prior Full
    Credit base for Earnings and Covenant (§10.10 as amended by §14.15) and the
    current overlay for Distressed; rendering the new effects in published
    outputs is Task 10's. Licensed market marks and live-model qualification
    of every effect remain external inputs.
19. **Opinion ownership, worker-published freeze, detached filing receipt,
    append-only audit chain and the offline audit package (2026-09-03, Task
    10, gates G7 and G8, ETR-B13).** An analyst opinion is an append-only,
    digest-bound store record (`deliverable_opinions`): it binds the exact
    draft revision (id, version, digest), the accepted snapshot, the source-set
    version, the digest of the revision's model identity and the methodology
    build, carries opinion, limitations, material overrides and rationale as
    required BoundaryText, and is signed through an expected-head CAS
    (`OPINION_HEAD_CONFLICT`); a single-actor release, so a store CAS and not
    an interrupt (invariant 5). Freeze refuses `OPINION_SIGNOFF_REQUIRED` /
    `OPINION_SIGNOFF_STALE`: editing the draft, moving the source set,
    superseding the snapshot or moving the model invalidates the sign-off by
    construction. `ANALYST_JUDGMENT` is not a citation bypass: a sentence that
    states a quantitative documentary claim (currency, percent, multiple,
    basis points, thousands-separated figure, year or fiscal-period token) is
    refused as `ANALYST_JUDGMENT_UNCITED_FACT` unless the block is cited or the
    sentence opens with an explicit judgment framing; this is a regex bound
    recorded as such, not language understanding. Freeze no longer renders in
    the API process: `POST …/freeze` validates and queues a
    `deliverable_freeze_jobs` row keyed by the freeze thread identity (202,
    idempotent under race and retry, FAILED jobs requeue), and `worker.py`
    renders Markdown, PDF and XLSX, publishes each hash-addressed, reads each
    back verified, and only then inserts the FROZEN record, parks the filing
    thread, audits `deliverable.frozen` and marks the job PUBLISHED in one
    transaction; a failure leaves a typed FAILED job and no frozen record;
    startup recovery requeues RENDERING jobs under the worker's single-instance
    lock; a divergent render for a published identity is
    `DELIVERABLE_FREEZE_CONFLICT`. XLSX therefore renders in the worker alone,
    and local development needs `python caos/server/worker.py` beside
    `dev.py` for a freeze to complete, exactly as model builds already do.
    Filing enforces separation of duties at the CAS
    (`APPROVER_NOT_INDEPENDENT`: the opinion signer and the freeze actor never
    file their own output) and writes an immutable detached receipt
    (`deliverable_filing_receipts`: approver, time, opinion id and signer,
    approval digest, fingerprint, export digests, approval hash,
    `receipt_digest`) in the filing transaction; the approved bytes always
    read `PENDING APPROVAL` and are never rerendered, not even to name the
    approver. A distinct approver is provisioned by
    `POST /api/cases/{case_id}/members`, which requires stored case
    APPROVER/ADMIN standing plus a current global writer role, like filing.
    Every export walks one server-frozen publication document
    (`payload.publication`: masthead, opinion-first pages, the pathway's
    canonical sections, an Evidence & QA Control Sheet, disclosures); Markdown,
    PDF (pango-view markup, measured pagination, repeated table headers,
    record layout for wide tables, pinned footer, transparent rotated
    watermark) and XLSX (cover and control, report, one filtered typed sheet
    per table, revision record, no formulas) render from it in the worker and
    the browser draws it directly, so parity is by construction and pinned by
    `test_publication_goldens_spec.py` across normal, dense, long-text,
    multilingual, held and filed states. The audit log is append-only at the
    database boundary (UPDATE/DELETE triggers on both dialects) and hash-chained
    per case under a head-row lock (`audit_chain_heads`), so mutation,
    deletion, insertion and reordering are detectable; legacy rows are chained
    once at startup; the wire shape of `audit_trail` is unchanged and typed
    refusals stay unaudited (logged). `GET /api/cases/{case_id}/audit-package`
    builds a case-scoped zip (manifests with digests; sources as block ids and
    text digests only; source sets; intakes; runs with plans, nodes, events,
    budgets, snapshots and artifacts; models and workbooks; deliverable
    revisions, opinions, jobs, frozen records, receipts and the exact filed
    bytes; the case audit chain; methodology and runtime identity) and
    `caos/server/caos/audit/verify_package.py`, standard library only,
    recomputes every digest and link and re-renders the Markdown export byte
    for byte from the frozen payload; its renderer copy is pinned byte-equal
    to `caos/publishing/markdown.py`. Deliberately not changed: the export
    route's media types (`application/octet-stream` for md/pdf/xlsx) and its
    gzip exclusion stay as they were, as a wire-visible decision for its
    owner; Earnings Update and Covenant & Refinancing deliverables still bind
    the prior Full Credit base build (§14.18), so their pathway effects reach
    the model export and the overlay build but not yet the published
    deliverable — a follow-up, not a silent narrowing. The blind rubric review
    by two analysts and an external stakeholder is candidate-only work and
    remains BLOCKED EXTERNAL with its inputs prepared.

    **Addendum (2026-09-03, CI follow-up — the font pin).** The first CI run
    of this task paginated the PDF goldens differently from the developer Mac
    (dense 8 pages against 7, multilingual 4 against 3) and extracted
    "body ." with a stray space: pango-view resolved "sans" and "monospace"
    through each host's fontconfig — Verdana and Andale Mono on the Mac,
    DejaVu on Ubuntu, Noto CJK's Latin glyphs in the image, which installs no
    DejaVu at all — so one frozen payload had three renderings. The fix is a
    font pin, not a golden update. The renderer vendors DejaVu Sans and DejaVu
    Sans Mono (regular and bold, release 2.37, Bitstream Vera licence) under
    `caos/server/caos/publishing/fonts/`, verifies the four files against the
    digests in `renderers.FONT_BUNDLE` before a render and refuses with
    `PDF_FONT_BUNDLE_INVALID`, serves them through a hermetic fontconfig
    (bundle first, the host's configuration after it for the scripts the
    bundle lacks, Debian's own DejaVu rejected by path) with pango pinned to
    the fontconfig backend, hinting off, unhinted metrics and subpixel glyph
    positions, and gives every span an absolute line height so a fallback
    face (Noto CJK in the image, whatever a developer host has) never moves a
    page break. Masthead metadata is wrapped at spaces before pango sees it,
    so a build id never splits at its hyphen. The renderer version is
    `caos.deliverable-renderer.v3`. The goldens were regenerated under the pin
    after every page and sheet was inspected, and their page counts now equal
    what CI rendered. What stays host-dependent is glyph shape for scripts
    beyond DejaVu's coverage; `fonts-noto-cjk` remains the image's declared
    fallback.

20. **The qualification corpus, attested answer keys and the live-matrix
    harness (2026-09-03, Task 11, ETR-B05 and ETR-B11).** Every qualification
    pack C01–C22 is one versioned manifest under
    `caos/tests/corpus/packs/<id>/` (`caos.corpus-pack.v1`: purpose, kind,
    stage, issuer, licence class, provenance, byte source, one row per
    document with SHA-256, media and document type, period, supersession,
    disposition, analytical role and reason, the cells the pack applies to,
    and the answer-key attestation) beside its answer key
    (`caos.answer-key.v1`: expected facts with source and match strings,
    conflicts, forbidden conclusions, per-cell outcome, refusal code, model
    effect, readiness, prerequisite, latency bound and host-control script).
    Bytes never enter a manifest: Carnival (C01, shared by C17–C20) stays
    `sources.txt` + `fetch.sh` outside pytest; C02–C16 are regenerated by
    `synthetic.py` and digest-checked (a fixture change is a manifest change
    through `qualify.py pin`); the licensed marks (C20), the Lumen stressed
    pack (C21) and the research pack (C22) are supplied under
    `$CAOS_CORPUS_EXTERNAL_DIR/<pack>/` by their owners and are unacquired
    until digest-pinned — an unpinned byte is `CORPUS_BYTES_UNACQUIRED`,
    never a skip. An answer key is signed by attestation: the manifest
    carries the key file's digest and scoped approvals; `host_control` scope
    licenses the orchestration proof, `analyst` scope alone licenses a live
    cell, and the pin tool refuses to re-sign an analyst-approved key. The
    harness (`caos/tests/corpus/qualify.py`) runs one cell per fresh process
    and store through the ordinary provider path — `run.build_provider` for
    a live binding, the answer-keyed double (identity `host_control`) for
    orchestration proof — admits the pack through the document-first intake
    when the host classifies it onto the cell's route and through the source
    routes otherwise, starts the run on the public route, approves a Deep
    Research plan on its exact hash, accepts, and executes the model build
    with the worker's function. `scoring.py` scores outcome (static route),
    facts (match string and a cited block of the expected source), citations
    (admitted and delivered), unsupported claims (forbidden conclusions and
    numeric traceability to delivered evidence, calculation records or the
    key, with fixture model tables exempt only under host control and
    recorded as such), conflicts, document use (intake dispositions, every
    relevant document cited, nothing non-relevant bound as `MODEL_INPUT`),
    model effect, refusal, latency, budget, C12 injection invariance
    (tools, verified authority digests, budget limits, identity and host
    identity equal between the clean and injected runs; no injected marker
    in any artifact) and ingest steps. Every result binds the provider
    identity (model, provider, adapter, parameter/policy digest), the corpus
    digest, the build (commit, methodology build id and manifest digest),
    the date, an expiry (`review_days` = 90) and the reviewer; `aggregate`
    counts three passes per live cell, never averages, discards stale or
    expired results (MOD-023, MOD-024), lets a refusal prove nothing, and
    reads `ORCHESTRATION_PROOF` for host control and `QUALIFIED` only for a
    complete live matrix. The protected workflow
    (`.github/workflows/enterprise-qualification.yml`, dispatch-only) runs
    the live matrix with pinned actions and retains the evidence red or
    green. Nothing here qualifies a binding: the credentials, the analyst
    approvals and the external packs are external inputs recorded in
    `.superpowers/sdd/enterprise-task-11-report.md`.

21. **Database truth, retained simulations, the single-instance lock and the
    backup snapshot point (2026-09-03, Task 12a, ETR-B07, ETR-B10, G6).**
    Serialisation of every governed race is a property of the database, proven
    on two independent PostgreSQL connections, never of a process lock. The
    read-then-write paths that a second connection could race are now
    database-ordered: `RunStore._emit` locks the run row before it allocates
    `seq`, and every run-table writer (`node_running`, `complete_node`,
    `pause_run`, finalisation) takes the run row first so the lock order is
    cycle-free; `_budget_locked` locks the ledger row (`FOR UPDATE`) so reserve,
    reconcile and charge cannot lose an update or overwrite an in-flight digest
    (invariant 8); `withdraw` is conditional on the flag it read; `save_assumption`
    reads the cited sources `FOR SHARE`; model sign-off, opinion sign-off, draft
    append, freeze request and frozen publication take a transaction-scoped
    advisory lock on the case (`store.lock_case`) before reading their head, so
    the loser re-reads and receives the typed conflict naming the winner. The
    process-wide locks stay as the SQLite mechanism, where these are no-ops.
    `caos/tests/test_postgres_races.py` is the only PostgreSQL proof; it runs
    in CI against the digest-pinned container (`ci.yml` job `postgres`,
    `CAOS_REQUIRE_POSTGRES=1`) and locally against the QA container; SQLite
    thread races and compiled `FOR UPDATE` checks are mechanism tests and are
    never called PostgreSQL evidence. Membership is rechecked at commit time
    inside the freeze-request and filing transactions (`DomainStore.
    require_standing`, `FOR SHARE` on the membership row, `CASE_STANDING_REVOKED`
    → 403), because a revocation between the route's check and the commit
    otherwise filed with stale authority (SIM-020). A database that cannot be
    reached before a write is the typed 503 `STORE_UNAVAILABLE` (SIM-010). The
    worker requeues `BUILDING` rows a dead predecessor left behind exactly as
    it requeues `RENDERING` freeze jobs (SIM-008). `node_running` never marks a
    node on a terminal run (SIM-003). SIM-001–SIM-030 each map to a retained
    test in `docs/SIMULATION_LEDGER.csv` (pinned by
    `caos/tests/test_simulation_ledger.py`) built on the existing kill-after-
    module, commit-gap, mid-provider-call, worker-fallback, render-failure and
    injection seams; the only new seams are the faulting host-control double,
    checkpoint-file damage, `ENOSPC`, and the disconnect-after-ack race. The
    single application instance is enforced by an exclusive operating-system
    lock over the checkpoint location (`caos/instance_lock.py`, `flock` on
    `checkpoints.db.lock`, taken by `run.py` and `dev.py` before recovery runs
    or a socket is bound) in addition to the PostgreSQL role advisory locks; a
    second instance fails typed (`INSTANCE_ALREADY_RUNNING`) and is proven by a
    second process. Compose declares `deploy.replicas: 1` for `app` and
    `worker` and `caos/deploy/ENVIRONMENT_MANIFEST.md` records the ceiling.
    The whole schema is created at startup (`DomainStore.from_url` constructs
    the model and deliverable stores), which is also what let the PostgreSQL
    target find that the Task 10 deliverable DDL could not be created through
    psycopg (`%` in `RAISE`): it is now executed through `sa.text`.
    `backup.sh` resolves the vault volume from the app container's `/vault`
    mount or `CAOS_VAULT_VOLUME`, never a Compose label, fails loudly, and
    captures both halves at one snapshot point by pausing the app and worker
    containers for the capture (`checkpoints.db-shm` excluded); the restore
    drill asserts the full startup schema. Not decided here: a distributed
    checkpointer, a shared fleet, a high-availability control plane, an export
    claim, or removing the SQLite process locks. Evidence:
    `.superpowers/sdd/enterprise-task-12a-report.md`.
