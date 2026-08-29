# Red-team log

Append-only. New dated sections at the end; never edit an existing entry.

## 2026-08-26 — Migration architecture (phase 1, pre-build)

Reviewer: fresh-context adversarial subagent against docs/DECISIONS.md, MODULE_GRANULARITY.md, TEST_INVENTORY.md, and legacy `workflows/domain.py` / `workflows/provider.py` / `methodology/canonical.py`. Fifteen objections; every one adopted as a design change (none accepted-as-risk). Resolutions are binding and recorded in docs/DECISIONS.md §10.

1. **[HIGH] Domain-store commit and checkpoint commit are not atomic → crash in the gap double-spends and double-mints.** Adopted: reuse-first execution — every agent node first queries the store for a valid artifact keyed (run_id, module_id, input_fingerprint), re-validates, and relinks with zero provider calls (generalising legacy's CP-DR relink, which `test_cpdr_existing_fingerprint_is_relinked_without_provider_call` already demands); every store state transition is a conditional CAS so re-emission no-ops; the kill/resume suite includes a crash injected between store commit and checkpoint write asserting one artifact, one charge, one `run.succeeded`.
2. **[HIGH] Parallel agent fan-out is incompatible with the single-slot budget ledger legacy semantics (legacy held `_canonical_generation_lock`).** Adopted option (a): a per-run `asyncio.Lock` serialises agent-module execution; deterministic nodes still run parallel. Keeps the one-inflight-digest ledger and sequential active-time semantics the contractual tests assert.
3. **[HIGH] "Single-writer-per-thread via the checkpointer" named a mechanism that does not exist.** Adopted: per-thread in-process `asyncio.Lock` around every `ainvoke`/resume, plus a Postgres advisory lock held for the invoke duration (SQLite dev is single-process and covered by the process lock); recovery and API resumes skip a held thread.
4. **[HIGH] Entry-gate interrupt contradicted "pinned at start" and naive `interrupt()` replay lets an empty set through.** Adopted: pin-time is entry-gate exit. The gate loops `while current source set empty: interrupt()`, then reads one store snapshot, compiles the plan, and writes the full pin (source set id+version+digest, plan_digest) exactly once. Tests: resume with still-empty set re-pauses without pinning; resume after upload pins exactly the verified version.
5. **[HIGH] Startup recovery treated four thread populations as one.** Adopted: recovery enumerates threads, skips any with a pending interrupt, reconciles store statuses, and feeds only crashed mid-run threads through the normal admission gate with bounded concurrency; superseding a frozen deliverable terminalises its thread (resume-to-end, typed SUPERSEDED outcome) so no zombie population accretes.
6. **[MEDIUM-HIGH] Budget envelope misstated (Σ vs Σ+max repair headroom) and legacy envelope/validation code is FULL_CREDIT-hardcoded.** Adopted: output ceiling = Σ per-module caps + max (repair headroom); the envelope is a pure function of (compiled route, registry) — turns, output, completion set per route; CP-MODEL `validate_bundle` stays six-module and is invoked only for accepted FULL_CREDIT runs (the only builds legacy queues). Per-route envelope test across all eight routes.
7. **[MEDIUM-HIGH] Deliverable-graph thread identity and resume choreography unspecified where contractual tests attack.** Adopted: thread_id = deterministic digest of (case_id, pathway, draft_version, draft_digest) so racing freezes converge on one thread; the resume API refuses unless the thread's current state shows the pending filing interrupt; the gate validates the resume payload and re-interrupts on typed rejection (stale digest leaves the record retryable); the store CAS remains the final arbiter.
8. **[MEDIUM-HIGH] Blocking sync work in a single asyncio process starves the event loop.** Adopted rule: all ported sync domain code called from async context goes through `asyncio.to_thread` on a bounded pool; CP-MODEL calculation keeps process isolation with the legacy aggregate per-request deadline (contractual); the pool bound is a recorded constant and the real compute ceiling.
9. **[MEDIUM] A stored admission counter leaks capacity across crashes.** Adopted: no counter — admission does `COUNT(*)` of non-terminal runs/builds inside the admission transaction; startup recovery reconciles statuses before admitting new work. Preserves the contractual capacity-returns-on-completion behaviour.
10. **[MEDIUM] The cut orphaned contractual invariants: note promotion (content-addressed idempotency, cross-ledger atomicity, no withdrawn-source resurrection) and assumption staleness propagation.** Adopted: notes (incl. promotion) and assumptions stay IN the MVP. The report-era cut narrows to thesis, recommendation matrix, and legacy report freeze/approve/export. The reconciliation table maps every remaining excluded contractual row to a named surviving test.
11. **[MEDIUM] "One registry entry" was aspiration until canonicalize/validation tables are registry-driven; new-module max_tokens were unexamined; truncation policy undefined.** Adopted: the rewritten runner drives all per-module tables from the registry (the three new wirings then genuinely touch only the registry); caps recorded as host budget policy — CP-1C 12k, CP-1D 12k, CP-5 24k (CP-5 consumes every upstream artifact; 16k plausibly truncates its evidence enumeration); a `max_tokens` stop-reason fails the module immediately as AGENT_OUTPUT_INVALID and does not consume the shared repair (repair is reserved for parseable-but-invalid responses).
12. **[MEDIUM] Durable threads outlive code; no state/graph versioning.** Adopted: a state schema version is stamped into pinned state; resume with a mismatched version fails closed with a typed error and a defined operator path (re-freeze the deliverable / re-run the run); checkpointer serializer and langgraph versions pinned exactly.
13. **[MEDIUM] Per-run event sequencing under parallel writers and exactly-once terminal events were asserted, not designed.** Adopted: sequence assignment via a per-run counter row locked in the event-writing transaction; every event insert rides a conditional state transition (zero rows updated → no event) so replays no-op; `run.succeeded` emitted exactly once by construction.
14. **[LOW-MEDIUM] Adapter-assembled requests can break reservation accuracy and retry identity.** Adopted: the reservation digest and count preimage are computed over host-owned canonical fields only, never adapter internals; `langchain-anthropic` pinned exactly; a congruence test asserts count-request/create-request equivalence and that `refusal`/`max_tokens`/`pause_turn` stop reasons reach the host validator.
15. **[LOW] Global provider concurrency cap dropped.** Adopted: one `asyncio.Semaphore(2)` at the model boundary (recorded constant); acquisition waits (bounded by remaining wall clock) and queue-wait time is excluded from the active-time meter, consistent with the contractual approval-wait exclusion principle.

Explicitly not objected to by the reviewer (kept as designed): static compiled routes as the structural form of invariant 10; DAG_BLOCKED moved to compile-time assertion plus kept finalize re-verification; the vault port; Sign-Off as store CAS rather than interrupt; the no-split module granularity call.

## 2026-08-26 — Second pass (user review of the amended design)

Five findings, all with legacy-code receipts; all adopted as binding changes (docs/DECISIONS.md §11).

1. **State schema fails a checkpoint round-trip as written.** (a) The pin was loose scalars in un-annotated last-value-wins channels — any node return could silently overwrite `source_set_id`/`plan_digest` and the checkpoint would persist the overwrite; legacy was immune because the pin lived in one immutable `run["plan"]` blob with `plan_digest = digest(plan)` computed once. Adopted: state carries the plan blob + digest; every node re-asserts `digest(plan) == plan_digest` on entry. (b) The digest framing was backwards: legacy recomputes `digest(source_set)` per attempt from the live store record re-read by id — the checkpointed digest is an expectation to compare, never the value of record. Adopted as a stated rule. (c) Withdrawal cannot round-trip through any checkpointed value: `read_pinned_evidence` re-checks `source["withdrawn"]` live on every call, and the resume path re-runs those live checks — a source withdrawn while a run sat at an interrupt is banned on resume. Adopted with a test.
2. **The cut mis-stated the route facts.** CP-6 remains in the in-scope FULL_CREDIT full route (16-node route terminal; `FULL_CREDIT_32.non_executable_module_ids` is `[]`), so it must be registered — deterministic, like legacy ran it; dropping it would edit a verified route, which is a methodology change we are not entitled to make. MVP module union is 18 including CP-PARSE and CP-6. "SCREENING_ONLY by catalog design" was a misreading (it is a `decision_scope` field on CP-L10's artifact contract); deterministic SCREEN is a recorded choice, and its consequence is that **execution mode is per (module, profile), not per module** — the registry schema now expresses `mode` per profile (CP-1A: agent at FULL, deterministic at LITE). Widening agent execution beyond legacy's single gated route (`is_canonical_full_credit`) to all FULL-depth routes is acknowledged as an extension, not a port.
3. **"No dynamic routing" was too broad.** The failure edge is selected by a node's own return value, and the deliverable file/request-changes branch is human-chosen. The narrower, true, and testable claim: the module node set and dependency edges are a pure function of (pathway, depth) — no branch can add, skip, reorder, or substitute a module (catalog basis: `profile_selection.immutable_within_run: true`, `selection_scope: PER_RUN`). Adopted the cheaper structural fix for run graphs: no conditional failure edges at all — nodes raise typed terminal errors, one graph-boundary handler finalizes; no node returns a routing decision.
4. **Granularity: the no-split position is vacuous by catalog receipt, and one alias does not resolve.** Absorbed phases have no separate contracts because their tables are contracted on the parent (CP-2B → CP-2A `T2B.1–9`; CP-1E → CP-1D `T1E.*`; CP-6A/CP-6E → CP-6 `T6A.*/T6E.*`; CP-5A/CP-5B → CP-5 `T5.*/T5B.*`) — recorded as the receipt table. CP-PARSE is simultaneously `superseded_module_ids["CP-PARSE"].absorbed_by = "CP-0"` and a runnable preparation stage that `compile()` emits as its own node: the alias map gets an explicit carve-out (CP-PARSE addresses its own stage-0 node, never CP-0). 18 of 19 aliases resolve plainly; one two-hop chain (CP-4D → CP-4B → CP-4).
5. **The contractual reconciliation was structurally wrong about CP-DR rows and notes.** 44 contractual rows live in CP-DR test files; the inventory classified them contractual precisely because their assertions protect surviving invariants (ceilings-before-overspend, reservation-before-provider-call, unresolved-inflight fails closed, duplicate-JSON-key rejection, NaN/Inf rejection, untrusted-data prompt separation, secret non-persistence, atomic single-mutation finalization) — none are excludable; all re-host on the nine agent modules, and the eight plan-approval-gate rows re-host on the deliverable filing interrupt. One is a priced design constraint: active time charges measured compute segments, never `now - started_at` — an interrupted run must accrue nothing at a human gate. Notes/promotion leave the cut (promotion mints content-addressed sources; its atomic-rollback and idempotency tests have no other vehicle). Genuinely excludable: nine report-era rows (thesis/recommendation CAS and freeze/approve family, including the thesis halves of two mixed tests) and one methodology-draft row; `test_production_rejects_forged_forwarded_identity`'s auth core re-hosts rather than drops.

## 2026-08-26 — Third pass (pre-build, six stress areas, four fresh-context attack agents)

Ordered before any further code, covering: checkpoint serialization vs immutability; interrupts at committee latency; bundle upgrade under a live run; host ceilings under a framework loop; attended-surface assumptions in the nine wired modules; incidentally-enforced legacy guarantees. Four fresh-context agents attacked the design (one empirically, against the installed langgraph 1.2.11 / checkpoint 4.2.0 / checkpoint-sqlite 3.1.1 / checkpoint-postgres 3.1.2 / langchain-anthropic 1.6.1 / anthropic 0.125.0 stack), plus the independent review supplied with the instruction. Every objection below is adopted as a binding design change recorded in docs/DECISIONS.md §12 unless marked accepted-with-owner. Nothing was left as silent risk.

### A. Checkpoint serialization vs immutability and content addressing (empirical)

1. **[HIGH] Serde rewrites strings across the checkpoint boundary.** `ormsgpack OPT_REPLACE_SURROGATES` replaces lone surrogates with U+FFFD on round-trip (demonstrated); a surrogate in `focus_questions` (routine from PDF extraction) poisons `plan_digest` into a permanent false-tamper failure after restart; Postgres `Jsonb` hard-rejects the same input that SQLite dev silently strips. Adopted: Unicode boundary validation (must utf-8-encode, surrogates rejected, NFC) on every string entering pinned state or events; serde round-trip identity tests per state field against BOTH savers (§12.3, §12.2).
2. **[HIGH] Pydantic/typed values degrade silently in checkpoints.** Demonstrated: revival via `model_construct` bypasses validators (rejected values come back inside "validated" types); `exclude=True` fields resurrect as defaults while a `model_dump` digest stays green; unimportable classes revive as raw dicts; `LANGGRAPH_STRICT_MSGPACK=true` (the documented hardening) silently degrades every custom type; tuples revive as lists with the JSON digest still matching (equal-but-not-identical, digest green); dataclass `init=False` fields revive as `None`; ZoneInfo→fixed-offset with `fold` loss. Adopted: channel values are JSON-native plain data only — no models, tuples, datetimes, Decimals, or dataclasses in state; the plan blob is deepcopy-frozen at gate exit; recursive type-identity round-trip test in CI (§12.2).
3. **[HIGH] The §11.1 re-assertion is false against the seeded `compile()`** — `plan_digest` is inserted into the digested dict, so `digest(plan) == plan_digest` is False by construction. Adopted: digests are carried outside the digested blob; preimage = blob without the digest key, defined once as a shared projection function; golden compile→checkpoint→re-assert test plus one-byte-mutation failure test (§12.1).
4. **[MEDIUM] Checkpoint write asymmetry:** regular task writes are first-wins (`ON CONFLICT DO NOTHING`) while special channels are last-wins; a double-crash can replay a stale write over a newer store record. Adopted: the reuse/relink path must emit byte-identical write payloads (ids resolved from the store, never regenerated); kill/resume suite gains a double-crash injection asserting replayed channel value equals the store record (§12.9, §12.28).
5. **[MEDIUM] Background serialization of mutable state** (`durability="async"`) can persist a half-mutated blob. Adopted: `durability="sync"` on gate and finalize supersteps; frozen plan blob (§12.2, §12.27).

### B. Interrupts at committee latency (days–weeks; empirical)

6. **[HIGH] Two racing `Command(resume=…)` deliveries BOTH execute** — demonstrated: both ran the gate node and the downstream filing node, no exception, forked checkpoint lineage, last-wins visibility. LangGraph 1.2.11 has no thread locking or conflict detection; §10.7's check-then-act refusal cannot close the race. Adopted: a store-side resume ticket — a one-shot CAS row keyed (thread_id, interrupt_id) written when the interrupt surfaces, consumed transactionally by the gate before acting; the losing racer finds it consumed and terminates without side effects. §10.3's locks are retained on every resume entry point (§12.23).
7. **[MEDIUM] Late, duplicate, and stale-id resumes silently no-op with a success-shaped response**, and the pending interrupt id churns on every rejection cycle. Adopted: the resume API never returns `invoke()` output as success — it re-reads state and requires the targeted interrupt gone AND the domain CAS advanced, else returns typed `RESUME_NOT_APPLIED` carrying the current interrupt id (§12.24).
8. **[MEDIUM] Deliverable thread identity omitted the methodology build** — freeze under build N could converge or refile under N+1, and a filing-time re-render would emit N+1 bytes under an N approval. Adopted: build_id joins the deliverable thread_id digest; the filing gate re-asserts frozen/plan/approval build_id equality and serves only the already-rendered vault bytes whose digest equals the approved preview_digest — filing never re-renders (§12.25).
9. **[MEDIUM] Nothing expires, nothing prunes, and parked threads freeze the dependency pins.** Savers implement only `delete_thread`; serde announces a future breaking change; one un-pooled psycopg connection dies over weeks. Adopted: terminalized threads are deleted after the domain store holds the audit trail; an upgrade runbook requires draining or park→resume-testing parked threads before any pin bump; `psycopg_pool` with health checks is mandatory in prod (§12.27).
10. **[MEDIUM] Pydantic state coercion re-runs on every node entry and silently drops unknown channels**, so a schema-version field inside the model is checked after the damage. Adopted: the version stamp is checked at the raw checkpoint layer before any coercion; pinned fields carry no defaults (§12.26).

### C. Methodology bundle upgraded under a half-completed run

11. **[HIGH] The methodology swap was silent.** A restart under a newer valid bundle passes `verify()` (current files vs current manifest), `build_id` reads N+1, and the resumed run — node identity in LangGraph is name-only — executes new methodology under an old pinned label; with a surviving process it is worse: construction-time catalog N with disk reads N+1, mixed authority. Adopted: the plan pins the integrity-manifest digest; every authority-file read used for prompt assembly hashes the exact bytes fed to the model against the PINNED build's manifest entry (verify-at-use, the vault's read-verification pattern); `plan.build_id == bundle.build_id` pre-flight is necessary but the byte-level check is the guarantee (§12.6). The filing-gate build assertion (item 8) covers the deliverable side.
12. Authority-assembly format (wrapper text, reference-file order, join separator) is part of the methodology build surface: golden-digest test per module; changing assembly is a methodology change (§12.7).

### D. Host-enforced ceilings under the framework-managed loop

13. **[HIGH] The SDK timeout is not a wall clock** — httpx read timeout is between-bytes (a trickling response runs 20+ minutes inside "150s"), and `default_request_timeout=None` disables timeouts entirely while disarming the SDK's streaming guard. Adopted: enforcement is `asyncio.timeout(min(150, remaining))` around every provider await (count and create), mapped to AGENT_PROVIDER_TIMEOUT with the inflight digest left unresolved; the SDK timeout stays as an inner hint; `default_request_timeout=150` pinned (§12.17).
14. **[HIGH] Absent/malformed usage passes as zeros and refunds the reservation** — `usage_metadata` is getattr-with-zero-defaults, so the ported legacy validation is dead code and reconcile would credit tokens back on every stripped-usage response. Adopted: validate the raw response usage (`response_metadata`), requiring the key present, `input_tokens` int > 0, `output_tokens` int ≥ 0, cache-token fields absent or zero; violations are AGENT_OUTPUT_INVALID with the inflight reservation unresolved (§12.19).
15. **[HIGH] Count/create congruence is impossible through `invoke()`** — the adapter has two divergent request builders (list-form system silently dropped from count; `strict` flag omitted from count-path tools; `output_config` absent from count; env-var-keyed content translation on create only; beta rerouting). Adopted: one host-owned request builder; count and create call the adapter's async client directly (`messages.count_tokens` / `messages.create`) with the host-built payload; the count body is the payload restricted to its accepted fields; `read_evidence` is passed as the raw Anthropic tool dict; system is a plain string. Honest restatement recorded: at the metered boundary ChatAnthropic serves as message formatter, output normalizer, and pinned client factory — `invoke()`/`bind_tools`/`with_structured_output` are not the metered path (§12.18).
16. **[HIGH] Checkpoint-subtraction metering is wrong under asyncio** — it charges a run for event-loop suspension (a fan-out run serializing on the per-run agent lock burns its ceiling ~3× fast), and the "re-checkpoint at resume" clause is fail-open if mis-ordered. This reopens and settles the §11.8-vs-second-pass contradiction: gap-charging is rejected. Adopted: active time = Σ explicitly bracketed single-operation segments (no awaits inside a bracket); charge-then-suspend at every lock, gate, and interrupt; budget check after every bracket; coverage by construction — one `timed()` wrapper is the only call site, with a test asserting every step in the node sequence is wrapped; the reuse-validation and completion-write segments are bracketed; `check_budget` is the last statement before a node reports success. The 5.0s prepaid finalization allowance with in-transaction deadline is the recorded exception (§12.16, §12.15).
17. **[MEDIUM] Silent streaming reroute** — a `stream_mode="messages"` caller flips node-internal calls to the streaming path with different usage provenance. Adopted: `disable_streaming=True` pinned and asserted; moot at the create boundary under the direct-client rule but retained as belt (§12.20).
18. **[MEDIUM] Adapter-supplied `max_tokens` default** (model-profile/4096) can silently replace the registry cap. Adopted: the builder sets `max_tokens` from the registry unconditionally; startup assert; congruence test per module (§12.20).
19. **[MEDIUM] Sync-only token counting on the event loop** via a different client. Closed by the direct-async-client rule inside the asyncio.timeout clamp (§12.18).
20. **[MEDIUM] Legacy response-shape checks do not survive adapter normalization** (single text block collapsed to string; refusal surfaces as stop_reason, not a block). Adopted: the validator is re-specified with `stop_reason` as the single authority — exactly {tool_use, end_turn} allowed, everything else typed failure — with a stub-response test per stop reason; the host parses raw content with duplicate-key-rejecting JSON and never consumes adapter-parsed objects (§12.13).
21. **[LOW] Process-global LLM cache** can satisfy invoke() with zero wire calls. `cache=False` pinned; moot under direct client (§12.20).
22. **[LOW] Repair/retry byte-identity holds through the adapter** under three asserted conditions (`max_retries=0`, timeout outside the digest, stable message objects); two-build byte-equality test adopted (§12.20).
23. **[LOW] `asyncio.Semaphore` has no non-blocking acquire.** Adopted: a plain integer slot counter (2), synchronous check-and-decrement on the loop, typed AGENT_BUDGET_EXCEEDED denial, release in finally — legacy semantics restored exactly (§12.21).

### E. Attended-surface audit of the nine wired modules

All nine SKILL/STEPS corpora audited against the "no inferred human answers" rule. Result: every module has a legal unattended terminal state (BLOCKED, `[Insufficient Information]`, conflict registers, gap ledgers with named gap codes) — nothing requires inventing an answer. Dispositions adopted (§12.29):
24. The five legacy neutralization mechanisms are replicated for all nine modules: host wrapper text (no conversational channel), pinned identity/manifest/upstreams labeled untrusted, conflict→fail-closed validation instead of chat stops, host discard-and-recompute of identity/trace/registry/confidence, and the qa-Passed gate (non-Passed module QA is terminal failure, the legacy rule).
25. **CP-2G's staged elicitation** (forecast_horizon / base_period / cases) is resolved at pin time from the module's own contract defaults (exactly three consecutive fiscal years after the latest CP-1 actual; CP-1-anchored base; BASE+DOWNSIDE), validated pre-dispatch.
26. **CP-1C's declared default (`auto_discover_and_verify` over `reputable_public_web`) is structurally banned by invariant 1** — web reads are outside the pinned source set. The host wrapper pins supplied-only mode; peers come from disclosed evidence or the module emits its Blocked/document-disclosed-only terminal. A pin-time `peer_list` input is recorded as the future upgrade if Blocked proves common.
27. **CP-5A's authorized-reviewer acceptance is the one hard human point.** Adopted mapping onto existing gates rather than a new mid-run interrupt: CP-5 produces its artifact unattended (its Severity Engine is deterministic); snapshot acceptance — already a human act — refuses when CP-5 reports Blocked (unremediated Critical), and a Restricted status rides the snapshot into deliverables as a surfaced limitation. No node ever self-overrides.
28. **CP-2's superseded deep-synthesis phrase-trigger** still present in REF_CP-2_STEPS.md contradicts its SKILL: the bundle cannot be edited (boundary), so the host wrapper explicitly declares phrase-triggers inert.

### F. Incidental legacy guarantees (fifteen further findings, all adopted)

29. **[HIGH] Digest-preimage meta-rule** (organizes four findings): every digest preimage is an exact pinned projection — fields × order × time-source — implemented once and shared by writer and every later verifier; list order comes from the pinned plan / stored source-set sequence (position column), never collection order; fields are added to records only after digesting under a per-type exclusion set; the six-field source-set projection is pinned (§12.1, §12.5).
30. **[HIGH] Single time authority:** the only timestamp below the pin is the pinned `created_at`; reporting_period/analysis_date/filenames are slices of it; nodes never call the clock for artifact content; snapshot `accepted_at` is the recorded integrity-only exception. Mocked-clock cross-midnight test adopted (§12.4).
31. **[HIGH] Store failure codes are part of the contract:** typed error enum with the exact legacy strings; authority checks precede block-existence checks in evidence reads (withdrawn/foreign source is never blamed on the model); the adversarial test asserts which code each refusal carries (§12.10).
32. **[HIGH] Acceptance consults completion markers** that must now commit atomically with artifact link/relink — otherwise the reuse path produces runs that succeed but can never be accepted (§12.9).
33. **[MEDIUM-HIGH] complete_node is upsert-by-fingerprint with validate-then-replace arbitration** including hard-delete of an invalid stored artifact; unique index + all three branches tested (§12.9).
34. **[MEDIUM-HIGH] The citation contract is delivered-evidence exact-set:** ledger charge → returned-set update → return is one ordered unit inside the tool; a ceiling-rejected read leaves no expectation (§12.11).
35. **[MEDIUM-HIGH] Repair-vs-terminal is decided by exception family** (ValueError-family from validate repairs once, tool-less; AgentError is terminal); recorder rules pinned: terminal rows cap-exempt with [-100:] trim, recorded only after provider interaction, per-row digest snapshots (§12.12).
36. **[MEDIUM-HIGH] Run-level error collapse:** agent-module failures surface as CANONICAL_GENERATION_FAILED at run level with the specific code in the terminal attempt row — kept explicitly (§12.10).
37. **[MEDIUM] Two divergent reserve semantics existed (canonical vs CP-DR);** canonical's idempotent budget-free retry reservation is the rule; re-hosted CP-DR rows adjust with one-line justifications (§12.14).
38. **[MEDIUM] Envelope scaling decision:** per-module allowances × route agent-module count (10 reads, 5MiB/6 evidence bytes, 500k/6 input tokens per module — N=6 reproduces legacy exactly); output = Σ caps + max(caps); turns = reads + N + repairs; count_tokens is turn-free, tested (§12.22). Residual liveness risk (ceilings binding on legitimate nine-module runs) accepted, owner: lead engineer, monitored at the phase-6 live smoke.

### Accepted risks (with owner)

- SQLite-dev vs Postgres-prod dialect divergence beyond the both-savers CI net: accepted for dev-only paths; owner: lead engineer; the contractual suites run against both savers.
- Envelope liveness under scaling (item 38): accepted, monitored at phase-6 smoke.
- All other objections: fixed in design (docs/DECISIONS.md §12), to be verified by the named tests during phases 3–6.

## 2026-08-27 — Adversarial Review: CI entrypoints merge (`91fea8f`)

Reviewer: three-persona adversarial pass (Saboteur, New Hire, Security Auditor), followed by live DAP inspection of the two critical execution paths.

Scope: `HEAD~1..HEAD` — 28 files, 478 additions, 79 deletions. The worktree was clean, so the no-argument review used the latest commit fallback. Verdict: **BLOCK**.

### Critical findings

1. **[CRITICAL] Deterministic runs use and cite withdrawn evidence.** Flagged independently by the Saboteur and Security Auditor, then promoted from WARNING to CRITICAL. `Engine._run_module` verifies the immutable source-set record at `caos/server/caos/engine/runtime.py:300`, but the live `withdrawn` flag is checked only later inside the agent path. Artifact reuse and deterministic execution bypass that check; the deterministic branch passes every pinned source id into `evidence_refs` at `runtime.py:336`.

   Reproduction: start a Full Credit screen run, withdraw its pinned source after gate exit, then continue the run. The run finishes `succeeded`, creates nine artifacts, and cites the withdrawn source. Live debugger confirmation stopped at `runtime.py:333` for `CP-PARSE`: `mode == "deterministic"`, while evaluating the pinned sources returned `[('src-…', True)]` for `(source_id, withdrawn)`. Execution was immediately about to call `build_deterministic_payload(..., source_ids=source_set["source_ids"])`.

   Required fix: perform one shared live-source validation immediately after source-set expectation verification and before reuse or mode dispatch. A missing, foreign, or withdrawn pinned source must raise the typed authority failure on every path.

2. **[CRITICAL] The production worker can publish an old calculation under a new input fingerprint.** Flagged independently by the Saboteur and New Hire, then promoted from WARNING to CRITICAL. `ModelService.queue_build` permits an active `BUILDING` row to be re-pointed at `caos/server/caos/models/service.py:242`. `run_build_for_tests` captures the row before its claim, ignores the claim CAS result at `service.py:364`, and computes from that captured record. `_complete` checks only `status in (QUEUED, BUILDING)` at `service.py:407`; it does not bind completion to the captured fingerprint. The new aliases at `service.py:884-885` make those historical test helpers the production worker entrypoints.

   Reproduction: start computation with fingerprint `old-input`, re-point the `BUILDING` row to `new-input`, and allow completion. Live debugger confirmation at `service.py:407` showed the persisted fingerprint as `new-input` while `result["payload"]["computed_from"] == "old-input"`. Stepping over the CAS produced `changed == True`; the final inspected tuple was `('READY', 'new-input', 'old-input')`. A separate synchronized two-worker probe showed one claim winner and one loser, but both entered computation because the losing CAS result is ignored.

   Required fix: make the claim result authoritative, never compute after a lost claim, and bind completion to an immutable job identity or captured input fingerprint. Do not mutate the authority identity of an executing row.

### Warnings

1. **[WARNING] The route-security audit treats request-shape rejection as authentication.** The Security Auditor found that `run_sec_audit.py:62-64` accepts either `401` or `422` from an empty request. A body-required endpoint with no authentication therefore passes the audit because the empty probe returns `422`, even though the same endpoint returns `200` without credentials when sent a valid body. This was reproduced against the assembled FastAPI app by adding a body-required unauthenticated probe route: `empty_probe_status=422`, `audit_accepts_status=True`, `valid_body_status_without_auth=200`.

   Required fix: enforce authentication before body validation (preferably at a shared middleware/dependency boundary) and require `401` for every non-public unauthenticated probe. Do not whitelist `422` as security evidence.

2. **[WARNING] Documented production placeholders are accepted as real secrets.** The Security Auditor found predictable database, edge, session, OAuth client, and cookie values in `caos/.env.example:10-20`. Compose checks only that required values are present, and `Settings.validate_runtime` rejects only the old development literals. A production configuration using `change-me-edge-secret` and `change-me-session-secret` passed validation unchanged.

   Required fix: reject known placeholder values in production and add deployment preflight validation for secrets consumed outside `Settings`. Prefer empty required example values where Compose can fail closed.

### Test and review gaps

- `caos/tests/test_worker.py` exercises one worker and no re-pointing, despite claiming CAS behavior; it cannot detect either worker race above.
- The withdrawal contract test covers the full/agent path but not a screen/deterministic path, leaving invariant 1 only partially enforced.
- The current route audit reported 41 routes and zero failures despite the demonstrated `422` false-negative class.

### Verification record

- Backend suite: **384 passed**, one unrelated Starlette/httpx deprecation warning.
- Frontend unit suite: **53 passed**. Local lint could not run because the existing `node_modules` did not contain `eslint`.
- `run_sec_audit.py`: **41 audited routes, zero reported failures**; the synthetic unauthenticated body route proved the gate unsound.
- DAP/debugpy live inspection confirmed both critical state transitions at their production call sites; the worker confirmation scenario exited zero after the debugger-only timeout was widened.

Merge/deploy guidance: do not ship until both critical authority failures are fixed and guarded by regression tests. The two warnings should also be resolved before this script is treated as a security gate or the example environment is used operationally.

## 2026-08-27 — Security Threat Model and OWASP Review

Reviewer: `securecoder:determine-threat-model` followed by `owasp-security`. Scope: the FastAPI and static-frontend application, OIDC edge, source ingestion and parsers, run/LLM boundary, model worker, persistent storage, backup/restore scripts, container build, and CI workflows. The vendored methodology corpus was treated as integrity-pinned data rather than independently security-reviewed source code.

Verdict: **BLOCK**. This pass adds one confirmed critical authorization defect. The two critical integrity failures in the immediately preceding review (withdrawn evidence on deterministic runs and stale worker calculations published under a new fingerprint) remain part of the release block and are not duplicated below.

### Security threat model

#### Component and data-flow overview

| Component / boundary | Trust level | Data and authority crossing it |
|---|---|---|
| Browser → Caddy (`:443`) | Untrusted network | OIDC session cookie, JSON bodies, multipart source uploads, SSE connections, filed/model downloads |
| Caddy → oauth2-proxy → FastAPI | Trusted deployment edge | Caddy strips caller-owned forwarded identity headers, adds `X-Edge-Authorization`; oauth2-proxy supplies OIDC subject/email/groups |
| FastAPI → domain store | Privileged internal | Cases, membership, extracted source text, notes, runs, immutable artifacts, model revisions, deliverable state, audit events |
| FastAPI / worker → vault volume | Privileged internal | Original source bytes, generated model workbooks, frozen deliverable exports |
| Run engine → Anthropic | External processor | Verified methodology, case/source metadata, selected evidence blocks, validated upstream artifacts; API credential stays in the SDK configuration |
| Anthropic → run engine | Untrusted model output | Tool calls and canonical JSON/Markdown, admitted only after host validation and authority checks |
| PostgreSQL job rows → model worker | Privileged execution boundary | Build/export jobs and model inputs; worker can write model/export state and vault artifacts |
| Database + vault → backup directory | Operator-controlled boundary | Complete database dump and complete vault archive, including confidential credit material |
| Pull-request diff → AI security-review action | Untrusted or semi-trusted CI input | Repository content is processed by an AI action with a Claude API key and PR-comment permission |

#### Entry points

- Public HTTP: Caddy ports 80/443, OIDC callback, `/api/health`, all authenticated `/api/*` routes, FastAPI OpenAPI/docs routes, and static Next.js assets.
- High-cost HTTP: multipart source upload, run start/resume/upgrade, model queue/preview/sign-off/download, deliverable render/freeze/file/export, and long-lived SSE event streams.
- Background execution: `caos/server/worker.py` polls database queues and produces model/XLSX artifacts.
- Operator/CI: Docker Compose environment variables, image builds, GitHub Actions, `backup.sh`, and `restore_drill.sh`.
- Local-only development: `dev.py` binds loopback and trusts development identity headers; this is not a production trust boundary.

#### Sensitive assets

- Original credit documents, extracted evidence blocks, analyst notes, model assumptions/outputs, frozen and filed deliverables.
- User subject, email, OIDC groups, case membership, approval identities, and append-only audit history.
- PostgreSQL, OIDC, edge-proxy, cookie, session, and Anthropic credentials.
- Methodology authority files, source-set pins, artifact digests, model fingerprints, approval digests, and backup contents.

#### Privileged actions

- Create and administer case state; add or change case membership (store/operator surface).
- Upload/withdraw evidence, promote notes, start/resume/accept/upgrade runs, and switch visible snapshots.
- Queue builds, compute previews, sign model revisions, and publish/download generated workbooks.
- Freeze deliverables, request changes, file an approved deliverable, and serve filed exports.
- Change methodology/dependency pins, build and publish containers, run privileged CI integrations, and restore backups.

#### Primary attacker models

1. An authenticated `READER` or compromised low-privilege OIDC account trying to mutate governed state or exhaust shared capacity.
2. A case member attempting cross-case IDOR, stale-authority reuse, or approval bypass.
3. A malicious uploaded document trying parser exploitation, archive bombs, formula injection, prompt injection, or stored XSS.
4. A compromised provider response trying unauthorized tool use, authority expansion, data exfiltration, or unbounded spend.
5. A malicious or compromised pull-request author targeting CI credentials and write-capable integrations.
6. An attacker with read/write access to backup storage, container registries, dependency distribution, or deployment secrets.

### Confirmed findings

#### 1. [CRITICAL] A downgraded global `READER` retains deliverable filing authority

Mapping: OWASP A01 Broken Access Control; ASVS 5.0 access-control and privilege-revocation controls; Agentic AI identity/privilege abuse.

Production identity derives the current global role from OIDC groups (`caos/server/caos/identity.py:45-48`). Ordinary writes correctly require both a current global writer role and a stored case writer role (`identity.py:61-72`). The separate filing helper does not: `require_case_approver` checks only stored case standing and never checks `who.role` (`caos/server/caos/api/__init__.py:680-688`). Both `/approve` and `/request-changes` rely on that helper (`api/__init__.py:743-759`).

Impact: a user formerly granted case `APPROVER` or `ADMIN` standing can still file a governed deliverable or request changes after the IdP downgrades the account to `caos-reader`. The current OIDC revocation signal is ignored at the highest-integrity human gate.

Adversarial proof: a production-mode request with `x-forwarded-groups: caos-reader` from a subject stored as case `APPROVER` reached the deliverable domain and returned `404` for a deliberately missing deliverable, rather than being stopped with `403`. That proves the approval authorization gate was passed.

Required fix: apply the same two-dimensional check as other writes before the case-approver check—current global role must be one of `ANALYST`, `APPROVER`, or `ADMIN`, while stored case role must be `APPROVER` or `ADMIN`. Add the omitted `global READER × case APPROVER/ADMIN` denial cases to both filing endpoints' authorization matrix.

#### 2. [WARNING] Global `READER` accounts can create cases and are stored as case `ANALYST`

Mapping: OWASP A01 Broken Access Control and A10 Mishandling of Exceptional Conditions; ASVS 5.0 least privilege.

`POST /api/cases` calls `identity()` but performs no role check (`caos/server/caos/api/__init__.py:128-131`). `DomainStore.create_case` then inserts the creator with stored role `ANALYST` (`caos/server/caos/storage/store.py:191-199`).

Impact: every authenticated reader can create an unbounded number of case and membership rows. The stored `ANALYST` assignment does not permit writes while the current global role remains `READER`, but it creates latent case authority that becomes active if the IdP later promotes that account to any writer role.

Adversarial proof: a production-mode `caos-reader` request returned `201`; the returned case stored that reader as `ANALYST`.

Required fix: require a current global writer role before case creation, or explicitly document reader-created cases as policy and add quotas plus a non-writer stored role. Do not silently assign authority above the current identity role.

#### 3. [WARNING] The live upload route bypasses its hardened helper and enables cheap resource exhaustion

Mapping: OWASP A10 Mishandling of Exceptional Conditions; OWASP LLM10 Unbounded Consumption; ASVS 5.0 file-handling and availability controls.

The public route buffers the complete upload with `await upload.read()` and checks size only afterward (`caos/server/caos/api/__init__.py:158-178`). It reimplements ingestion instead of calling `sources.domain.ingest_upload`, which already canonicalizes the filename, enforces the suffix allowlist, reads at most `max_bytes + 1`, and rejects empty files (`caos/server/caos/sources/domain.py:286-307`). The edge allows 250 MiB per request (`caos/deploy/Caddyfile:3-5`) and defines no request-rate or per-user concurrency limit. Other amplifiers are unbounded item length for each run `focus_question` (`caos/server/caos/contracts.py:131-140`) and one database poll every 0.4 seconds per SSE connection (`caos/server/caos/api/__init__.py:386-423`). Synchronous model previews are also outside the queued-job admission ceiling.

Impact: an authenticated account can consume application memory, parser/ClamAV CPU, database polling capacity, worker CPU, vault storage, and potentially provider budget. The global 250 MiB edge limit is a ceiling, not a safe per-route resource policy.

Adversarial proof: the live endpoint returned `201` for both an unsupported `unsupported.exe` source and a zero-byte `empty.bin`; the hardened helper would return `415` and `422`, respectively.

Required fix: delegate the route to the existing `ingest_upload` helper; use a substantially smaller route-specific cap where business inputs permit; bound each focus question; and add per-subject/IP rate limits, model-preview concurrency limits, and SSE connection limits at the edge/application boundary.

#### 4. [WARNING] The public edge omits browser hardening headers and leaves framework docs enabled

Mapping: OWASP A02 Security Misconfiguration; ASVS 5.0 HTTP security-header and production-surface controls.

The Caddy policy configures compression, a body cap, identity-header scrubbing, and proxying, but no explicit HSTS, CSP/`frame-ancestors`, `X-Content-Type-Options`, `Referrer-Policy`, or `Permissions-Policy` (`caos/deploy/Caddyfile:1-13`). `FastAPI(title="caos")` keeps `/docs`, `/redoc`, and `/openapi.json` enabled by default. OIDC protects these through the deployment edge, but every admitted domain user receives a larger browser and API-discovery surface than necessary.

Required fix: add tested response headers at Caddy, with a CSP compatible with the static Next.js output, and disable framework documentation endpoints in production unless they are an explicit operator feature.

#### 5. [WARNING] Backups have permissions but no confidentiality or authenticity protection

Mapping: OWASP A04 Cryptographic Failures and A08 Software or Data Integrity Failures; ASVS 5.0 data-protection and backup controls.

`backup.sh` correctly uses `umask 077`, but writes a plaintext PostgreSQL dump and gzip-compressed full vault archive (`caos/deploy/backup.sh:20-40`). Its manifest uses unkeyed POSIX `cksum`; `restore_drill.sh` trusts a matching manifest stored beside the data (`caos/deploy/restore_drill.sh:71-82`). An attacker able to alter the backup pair can replace both data and checksum, while read access exposes the complete confidential corpus.

Required fix: require authenticated encryption before a backup leaves the host (for example, an operator-managed KMS/envelope or age/GPG workflow), keep the verification key separate from the backup, and document retention, rotation, access logging, and restore authorization. SHA-256 alone would detect accidents but would still not authenticate an attacker-writable backup.

#### 6. [WARNING] Runtime and CI supply-chain inputs are only partially immutable

Mapping: OWASP A03 Software Supply Chain Failures; OWASP LLM03 Supply Chain; ASVS 5.0 dependency and build integrity controls.

Positive controls exist: application base images and oauth2-proxy are digest-pinned, the frontend uses `npm ci`, and CI runs pip-audit, npm audit, Bandit, Trivy, and Gitleaks. Remaining mutable inputs include `postgres:17-alpine`, `clamav/clamav:1.4`, `caddy:2.10-alpine`, helper `alpine:3.20` images (`caos/deploy/docker-compose.yml:3,19,121`; `backup.sh:31`), non-exact Python runtime requirements (`caos/server/requirements.txt:7-14`), unversioned apt packages including LibreOffice (`caos/deploy/Dockerfile:11-15,28-30`), tag-based GitHub Actions, and a Trivy installer fetched from a mutable `main` URL and piped into a shell (`.github/workflows/ci.yml:138-145`).

Required fix: digest-pin deployed images and privileged Actions, generate a hash-locked Python dependency set, verify downloaded tooling by digest/signature, and make package-update provenance an explicit reviewed change. Keep the existing vulnerability gates; they address known CVEs, not source authenticity.

#### 7. [WARNING] The AI pull-request reviewer processes attacker-controlled diffs with a repository secret

Mapping: OWASP LLM01 Prompt Injection, LLM06 Excessive Agency, and LLM02 Sensitive Information Disclosure; Agentic AI prompt/tool misuse.

The workflow itself states that the action is not hardened against prompt injection and should run only on trusted diffs (`.github/workflows/security-review.yml:1-8`). Nevertheless it triggers on every pull request, checks out the PR head, exposes `CLAUDE_API_KEY`, and grants `pull-requests: write` (`security-review.yml:15-38`). GitHub withholds secrets from ordinary fork PRs, but same-repository branches, compromised contributors, and changes admitted through misconfigured approval policy remain in scope; the trust decision is not enforced by the workflow.

Required fix: gate the secret-bearing job behind an explicit protected-environment approval or trusted label set by a separate secretless workflow; minimize token permissions; and ensure the review action cannot execute repository content or emit secrets. Keep the action SHA pin.

### Needs manual review

1. **External LLM data governance.** When agent execution is enabled, selected evidence text and upstream artifacts are sent to Anthropic (`caos/server/caos/engine/anthropic.py:38-78`; `engine/evidence.py:100-116`). Confirm contractual retention, training exclusion, regional processing, legal basis, client confidentiality, incident notification, and deletion requirements. This cannot be established from source code.
2. **Encryption and monitoring outside the repository.** Confirm disk/volume/database encryption, key rotation, secret-manager use, network policy, backup destination ACLs, centralized audit-log export, alerting for repeated authorization failures/resource spikes, and tested incident response. Compose's internal bridge and container restrictions are useful but do not prove host/cloud controls.

### Controls validated / false-positive dispositions

- **Forwarded-header spoofing — controlled in the documented production topology.** Caddy removes caller-supplied identity and edge-secret headers, oauth2-proxy supplies OIDC identity, and FastAPI rejects requests without the shared edge secret. Development header trust is loopback-only by `dev.py` and is not a production finding.
- **Cross-case IDOR — no confirmed route found.** Case membership is checked before reads/writes, child records are re-bound to `case_id`, and unknown versus unauthorized run IDs return a uniform 404.
- **SQL injection — no confirmed sink found.** User values flow through SQLAlchemy expressions; reviewed raw SQL is static schema/restore logic, not request-derived query text.
- **Stored XSS / unsafe Markdown — controlled.** The frontend uses a closed Markdown grammar and React text nodes (`caos/frontend/src/lib/filedMarkdown.ts`; `components/FiledProof.tsx`) with no `dangerouslySetInnerHTML`/`innerHTML` sink.
- **Archive traversal and malware handling — controlled after admission.** Production ClamAV fails closed; ZIP entry count, expanded size, compression ratio, and traversal are bounded (`caos/server/caos/sources/domain.py:61-125`). Finding 3 concerns the route bypass around type/empty/bounded-read admission, not these checks.
- **Prompt-injection authority expansion — materially constrained.** Source data is labeled untrusted, methodology files are hash-verified at use, the only model tool is strict `read_evidence`, live case/pin/withdrawal authority is rechecked per read, budgets/timeouts are host-owned, and output is strict-schema validated with exact citation reconciliation (`engine/authority.py:22-100`; `engine/evidence.py:62-136`). Residual analytical misinformation remains a human-review risk, not a demonstrated tool-escape path.
- **Formula injection — covered.** Deliverable XLSX tests assert `=`-prefixed analyst text remains a literal string while governed numeric cells remain typed.
- **Secret scanning — clean in this pass.** Local `gitleaks detect --no-git` exited successfully with no findings.

### Verification and release order

- Targeted production-mode authorization probe: global `READER` + stored case `APPROVER` passed the filing helper and reached domain lookup (`404`, not authorization `403`).
- Targeted ingestion probe: unsupported suffix and empty upload both returned `201` through the live API route.
- Static review covered all registered API handlers, identity and membership checks, ingestion/parsing, vault paths, model/deliverable publication, LLM authority/tool/budget boundaries, deployment, backup/restore, and CI security gates.
- Not exercised: a live production reverse proxy/IdP, live Anthropic request, cloud encryption/monitoring, or a fresh online dependency advisory scan.

Release order: fix the three open criticals first (the two preceding integrity failures plus finding 1), then close the upload/resource and backup risks before internet-facing production. The remaining warnings are defense-in-depth or operational controls but should not be treated as silently accepted risk.

## 2026-08-28 — Remediation of the three open criticals (verification pass)

> The two 2026-08-27 sections this responds to — "Adversarial Review: CI
> entrypoints merge (`91fea8f`)" and "Security Threat Model and OWASP Review" —
> were uncommitted in the main checkout's copy of this file when this pass ran,
> so they are not in this branch's history. Their findings are restated below
> where the remediation depends on them.

Reviewer: verification-first re-read of the two 2026-08-27 sections against the
tree at `ed4796e`, then remediation. Every finding below was re-reproduced
before it was touched; every fix was proven by disarming it and watching its own
test go red.

### Re-verification of the prior sections

All three criticals and every warning were still open at `ed4796e`. Fresh
reproductions:

- **Withdrawn evidence (CI-entrypoints §1).** A screen-depth `FULL_CREDIT` run
  whose pinned source is withdrawn after gate exit finished `succeeded` with
  nine artifacts, every one citing the withdrawn source id. The root cause is
  structural and was not stated in the original finding: `store.withdraw` mints
  a *new* source-set version and leaves the pinned record byte-identical
  (`storage/store.py:326`), so `verify_source_set_expectation` can never see a
  withdrawal — the live check is the only guard, and both the artifact-reuse
  relink and the deterministic branch returned before reaching it. The bypass
  therefore covered agent runs too, via reuse on resume, not only deterministic
  ones. Blast radius was bounded on one side: `deliverables.service.
  _validate_citations` still refuses to freeze a withdrawn citation, so the
  breach reached run artifacts, accepted snapshots and model builds, never a
  filed deliverable.
- **Stale worker calculation (CI-entrypoints §2).** Reproduced exactly:
  `claim_b_lost_cas=False` yet computation proceeded; an executing `BUILDING`
  row accepted a new `input_fingerprint`; completion published `READY` under
  `new-input-fingerprint` carrying a payload computed from the old one.
- **Downgraded `READER` files (OWASP §1).** A production-mode request with
  `x-forwarded-groups: caos-reader` from a subject stored as case `APPROVER`
  reached the deliverable domain and returned `DELIVERABLE_NOT_FOUND` — a
  domain-level miss, where a non-member gets the uniform case-level 404. That
  body difference is the proof the authorization gate was passed.

One calibration against the original text: the `422` route-audit warning is real
as a **CI-gate defect**, not as a live authentication bypass. Probed against the
assembled app, a body-required endpoint returns `422` to an unauthenticated
empty probe but `401` to an unauthenticated *valid* body — no currently-served
route is exposed by it. The defect is that the gate cannot detect a regression,
and it runs in both `ci.yml` and `nightly.yml`.

### Fixed

1. **One shared live-source validation.** `Engine._live_sources` runs
   immediately after the source-set expectation check and **before** the reuse
   lookup and the mode dispatch, so reuse-relink, deterministic and agent paths
   all fail closed on a missing, foreign or withdrawn pinned source.
   `_execute_agent` now builds its provider manifest from those validated rows
   instead of re-reading them.
2. **The worker claim is authoritative and completion is identity-bound.**
   A lost claim CAS returns the current row and never computes; the claimed row
   (not the pre-claim read) is the computation's authority; `update_build` gained
   `expected_input_fingerprint` so `_complete` and `_fail` can only write under
   the identity the payload was computed from. Re-pointing a `BUILDING` row now
   sets it back to `QUEUED`, so the abandoned executor's completion no-ops and a
   worker recomputes under the new identity.
3. **Filing honours the current global role.** `require_case_approver` now
   requires a current global writer role *and* stored case `APPROVER`/`ADMIN`
   standing, matching `require_case(write=True)`. An IdP downgrade revokes
   filing authority immediately; case standing still never escalates.
4. **The upload route delegates to its hardened helper.** `POST
   /api/cases/{id}/sources` calls `sources.domain.ingest_upload` instead of
   reimplementing ingestion, restoring the suffix allowlist, the empty-source
   refusal, the bounded read and filename canonicalization. Before this,
   `ingest_upload` had no production caller at all — its three hardening tests
   were passing against a function no request reached.

Found and fixed during the confidence pass on the above, same defect class:
`worker.run_pending`'s own failure fallback wrote `FAILED` with no identity
binding, so a calculation that died after a re-point would drag the requeued
build down with it. It now binds to the fingerprint the pass dispatched.

### Test gaps closed

Seven tests, each proven red with its fix disarmed:
`test_withdrawing_pinned_source_fails_a_screen_run_on_the_deterministic_path`,
`test_reuse_relink_on_resume_revalidates_live_sources` (crash-in-commit-gap then
withdraw, then recover onto the committed artifact),
`test_a_lost_claim_never_computes_and_never_touches_the_winner`,
`test_a_repointed_build_never_publishes_the_abandoned_calculation`,
`test_a_crashing_pass_never_fails_a_row_that_was_repointed_under_it`,
`test_downgraded_global_reader_loses_filing_authority_despite_case_standing`
(which also pins the unchanged direction: a global `APPROVER` without case
standing still gets 404), and
`test_upload_route_enforces_the_same_admission_as_the_ingestion_helper`.

### Still open (unchanged from the 2026-08-27 sections)

`run_sec_audit.py`'s `422` acceptance; `READER` case creation stored as case
`ANALYST`; missing per-subject rate, SSE-connection and preview-concurrency
limits and a route-specific upload cap; Caddy browser-hardening headers and the
enabled `/docs`; production placeholder secrets passing `validate_runtime`;
backup confidentiality and authenticity; mutable image/dependency/Action/tooling
inputs; the AI PR reviewer's secret exposure; and both "needs manual review"
items. The export half of `worker.run_pending` still writes `EXPORT_FAILED`
with no CAS.

### Verification record

- Backend suite: **392 passed** (385 before, plus the seven above), one
  unrelated Starlette/httpx deprecation warning.
- `ruff check --config ruff.toml caos/server caos/tests --exclude
  caos/server/caos/methodology/vendor`: **All checks passed**.
- Each of the seven tests was run with its own fix disarmed and observed to
  fail on the assertion it exists to make, then re-armed.
- Not exercised: a live reverse proxy/IdP, a live Anthropic request, a real
  two-process worker race (the claim and re-point are driven through the same
  store CAS the two processes share), or the frontend suites.

## 2026-08-29 — Remediation of the remaining warnings

Reviewer: continuation of the 2026-08-28 pass, closing the warnings left open
there. Every code fix is proven by disarming it and watching its own test go red;
the deployment fixes are marked honestly where they could not be executed here.

### Fixed in the application

1. **The route audit is sound, because the app made it so.** The real defect was
   never a specific unauthenticated route — probing confirmed a body-required
   endpoint returns `401` to a valid unauthenticated body — it was that FastAPI
   validates the body before the handler, so `422` and "no auth at all" are
   indistinguishable to `run_sec_audit.py`. `EdgeIdentityGate` (pure ASGI, so
   the run-events tail keeps streaming) now refuses unauthenticated `/api`
   callers before routing, and the audit requires `401` with no `422`
   whitelist and additionally probes each route with a body. Soundness was
   demonstrated both ways: an injected unauthenticated body-required route that
   previously served `200` to a valid anonymous body now returns `401`, and
   removing the gate turns the audit red with 30 failures.
2. **Production refuses documented placeholder secrets.** `validate_runtime`
   rejects the dev literals, any `change-me`/`replace-me`/`example`-prefixed
   value, anything under 32 characters, and a placeholder `POSTGRES_PASSWORD`
   read out of `DATABASE_URL` (the only place the app can see it).
   `.env.example` now ships every required secret EMPTY, so Compose's
   `${VAR:?}` fails closed on a half-filled file rather than booting on a
   predictable value. This is a deliberate upgrade gate: a deployment running a
   short secret will refuse to start until it is regenerated.
3. **Case creation requires a writer role.** A global `READER` could create
   cases and was stored as case `ANALYST` — latent authority that would activate
   on the next IdP promotion.
4. **Browser hardening on every response.** `SecurityHeaders` sets CSP, nosniff,
   `Referrer-Policy`, `Permissions-Policy` and `Cross-Origin-Opener-Policy`, with
   HSTS in production only (pinning HTTPS for localhost would wedge a developer's
   browser). It lives in the app, not Caddy, because the app is the origin for
   the static export and the JSON API alike — one place, unit-tested. `script-src`
   keeps `'unsafe-inline'`: the static export ships two inline bootstrap scripts
   whose payload changes each build, so neither a nonce nor a hash is available.
   `/docs`, `/redoc` and `/openapi.json` are off in production; `app.openapi()`
   still serves the contract tests in-process.
5. **Per-subject admission ceilings.** `RequestCeilings` charges a token bucket
   per authenticated subject (300/min) and caps the two shapes the bucket cannot
   see because they hold a worker for their whole lifetime: concurrent
   run-events streams (4) and in-flight model previews (2). Keyed by subject,
   not IP — an IP punishes an office behind one NAT and does not slow one
   account with a token. Verified against the live UI: 60 rapid reads all `200`.
6. **A route-specific source cap.** Sources are now capped at 25 MiB
   (`MAX_SOURCE_MB`) with the edge body cap lowered to 32 MiB — the transport
   ceiling and "what a governed source may be" are different questions.
7. **Every wire string list is bounded per item.** `max_length` on a list bounds
   the count only; `focus_questions` and the four `ThesisRequest` lists could
   each carry unbounded bytes into pinned state, run events and every compiled
   prompt.
8. **The export failure fallback is CAS-bound**, like the build half already was.

### Fixed in deployment and CI

- Every GitHub Action is pinned to a commit SHA. The Trivy installer is fetched
  from the release tag rather than `main` and verified against a SHA-256 before
  it is executed — a `curl | sh` from a mutable branch runs whatever that branch
  holds at the moment CI fires.
- `postgres`, `clamav`, `caddy` and `alpine` are digest-pinned (resolved from
  the registry, not guessed). oauth2-proxy and the Python base image already were.
- Backups are encrypted to an `age` recipient, with the plaintext dump never
  landing on disk. age is an AEAD, so it supplies the authenticity an unkeyed
  `cksum` beside the data never could: an attacker who can rewrite the archive
  can rewrite the checksum, but cannot forge the ciphertext. The manifest's
  SHA-256 is demoted to an honest corruption pre-check. Key handling, rotation,
  retention, destination ACLs and two-person restore authorization are written
  into the script header as policy the script cannot enforce.
- Both deploy scripts moved to `bash` with `set -euo pipefail`. **This was a bug
  introduced by the encryption change and caught in the confidence pass:** under
  POSIX `sh` a pipeline reports only its last command, so a failed `pg_dump`
  piped into `age` still produced a valid encryption of zero bytes that
  `test -s` accepted — a "successful" backup of nothing.
- The AI PR reviewer's secret-bearing step is conditioned on the PR head being
  same-repo, and the activation notes now name the protected-environment gate as
  the control that actually addresses a compromised contributor.

### Tests

Nine added, each proven red with its fix disarmed:
`test_unauthenticated_requests_are_refused_before_request_shape_validation`,
`test_production_serves_no_framework_documentation_surface`,
`test_production_refuses_documented_placeholder_secrets`,
`test_global_reader_cannot_create_a_case`,
`test_every_response_carries_the_browser_hardening_headers`,
`test_focus_questions_and_thesis_items_are_bounded_per_item`,
`test_a_crashing_export_pass_never_clobbers_an_export_published_under_it`,
`test_per_subject_rate_ceiling_refuses_and_is_not_shared_between_subjects`, and
`test_concurrent_stream_slots_are_capped_and_always_returned` (driven against
the middleware directly — `TestClient` cannot hold an endless SSE body open).

### Still open

- **The backup round trip is unexercised here.** Neither `age` nor a running
  Compose stack exists in the dev worktree, so the scripts are syntax-checked
  only. Drill a real encrypt/verify/decrypt/restore before relying on them.
- Dockerfile apt packages, `libreoffice-calc` included, remain unversioned.
- `requirements.txt` pins versions, not hashes.
- Exports have no claim at all — two workers would both render one export.
- `RequestCeilings` counts in-process, so ceilings are per app instance. That
  matches the single-instance deployment the SQLite checkpoints already force.
- Both "needs manual review" items (external LLM data governance; encryption,
  monitoring and incident response outside the repository) are unchanged.

### Verification record

- Backend suite: **401 passed** (392 before), one unrelated Starlette/httpx
  deprecation warning. `ruff check`: clean. `run_sec_audit.py`: 42 routes, zero
  failures under the strict `401` rule.
- Live UI check against the combined app: the register renders with no CSP
  violation and no blocked resource; 60 rapid reads all `200`; a `.exe` is
  refused `415`, an empty file `422`, a 26 MiB file `413`.
- Middleware order verified empirically rather than by reasoning about
  `add_middleware` prepend semantics: unauthenticated → `401` from the gate
  (not `422`, not `429`), and both the `401` and the `429` carry the CSP.

## 2026-08-29 — Provenance note on the two 2026-08-27 sections

The two 2026-08-27 sections above were written into the main checkout's working
copy of this file and never committed. The 2026-08-28 and 2026-08-29 remediation
passes were carried out against them from a worktree, which is why the
2026-08-28 entry opens by saying they "are not in this branch's history" — true
when written, and left unedited here because this log does not rewrite entries.

They are committed now, inserted in date order rather than appended, so the
record reads chronologically and the remediation entries sit after the findings
they answer. Nothing in either section was altered: the inserted text is
byte-identical to the 194 lines that were sitting uncommitted at `ed4796e`.
