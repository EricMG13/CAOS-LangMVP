# Spec Reconciliation — spec-v1

Every row classified CONTRACTUAL in TEST_INVENTORY.md (229 after the RV reclassification) maps below to
(a) a spec test in `caos/tests/spec/` (red today by design — the implementation does not exist),
(b) a phase-2 test in `caos/tests/` that already passes because its surface was built in phase 2, or
(c) an entry in the exclusion/deferral lists at the end.

Spec-suite state at tag `spec-v1`: **314 red (122 failed + 192 errors), 0 passing.** The 53 passing tests
in the repo are all phase-2 tests (`test_bundle` 7, `test_config_and_vault` 10, `test_source_ingestion` 29,
`test_store` 7) — green because ingestion, the domain store, the bundle loader, and config were built in
phase 2 before this spec suite was ordered; each asserts a real contractual guarantee and fails on regression.

Abbreviations: file names drop the `test_` prefix and `_spec` suffix (`runs` = spec/test_runs_spec.py;
`p2:` = passing phase-2 test).

## test_source_ingestion.py — 15 rows → phase 2 (all passing)

All fifteen rows map 1:1 onto `p2:test_source_ingestion.py`, which was ported from the same briefs in
phase 2: zero-byte, evidence-free text/csv/xlsx/json, non-finite JSON (5 cases), duplicate JSON keys,
non-UTF-8, invalid PDF, textless-PDF accepted, non-empty xlsx accepted, JSON scalars accepted, extraction
caps (rows/sheets/line), content dedup + withdrawal reopening, atomic rollback, public-field hiding.
`test_clamav_config…` was MECHANISM (not owed).

## test_clean_slate.py — 22 rows

| Legacy row | Target |
|---|---|
| deploy_v_integrity_and_cp_parse_route_order | p2:test_bundle (integrity, tamper, 16 golden routes, CP-PARSE-first, plan-digest pinning) |
| end_to_end_source_run_snapshot_and_stale_boundary | runs::gate/pin/acceptance tests + misc::switch_required + http_contracts run family |
| run_is_pinned_to_immutable_source_set_and_full_upgrade_is_linked | runs::run_pinned…upgrade_links_origin |
| acceptance_refuses_a_missing_historical_source_set | runs::acceptance_refuses_missing_historical_source_set |
| source_empty_run_pauses_and_forged_identity_cannot_cross_case | runs::empty_source_set_pauses… + case_reader_cannot…outsiders_see_nothing |
| read_only_member_cannot_upgrade_a_run | misc::read_only_member_cannot_upgrade_a_run |
| research_plan_approval_respects_case_writer_authorization_matrix | deliverables::filing-gate authz pair (re-hosted per §11.9; approver-gating adaptation recorded in its ROW MAPPING) |
| source_withdrawal_versions_active_set_and_stales_assumptions | p2:test_store::withdrawal_stales_citing_assumptions… |
| withdrawn_sources_are_rejected_for_new_evidence_references | p2:test_store (assumption half); thesis half EXCLUDED (E1) |
| report_inputs_rejects_withdrawn_source_evidence | EXCLUDED (E1) |
| promoted_note_can_be_repromoted_after_its_source_is_withdrawn | p2:test_store::promotion_after_withdrawal_mints_new_identity |
| full_credit_model_dependent_node_hands_off_to_model_builder | misc::cp2g_emits_handoff_without_fabricated_workbook_values |
| analyst_versions_are_cas_and_recommendation_vocabulary_is_exact | EXCLUDED (E1); CAS invariant asserted on deliverables (stale-version CAS test) |
| report_inputs_version_together | EXCLUDED (E1) |
| clean_slate_structured_deliverable_template_and_strict_save | deliverables::template + strict-schema tests |
| financial_and_rv_guards | misc::financial_guards_and_rv_signal_bands + model_builder::finite_guards |
| rv_currency_is_normalized_before_comparability_checks | misc::rv_currency_normalized… |
| rv_universe_is_persisted_with_its_version | misc::rv_universe_round_trips_through_the_store |
| prompt_compiler_keeps_document_text_below_typed_authority | modules::prompts_keep_untrusted… + invocation_plan_rejects_forbidden_keys |
| visual_recipe_is_declarative_and_fails_closed | misc::visual_recipe_is_declarative_and_fails_closed |
| production_rejects_forged_forwarded_identity | runs::production_rejects_forged_forwarded_identity (methodology-draft step-up half EXCLUDED with E2) |
| frozen_report_requires_exact_preview_and_approver | deliverables::approval_binds_exact_preview_digest… (re-hosted onto the filing gate) |

## test_ledger_contracts.py — 35 contractual rows

Storage/evidence rows: source_duplicate_and_withdrawal_are_atomic → p2:store+ingestion (dedup, versioning,
rollback); assumption_creation_and_withdrawal_orders_match → p2:store; source_reads_hide_adapter_fields →
p2:ingestion::public_source_reads_hide…; governed_writes_commit_state_and_audit_together → p2:store;
pinned_evidence_is_validated_in_one_catalog_read → evidence (all boundary tests);
distinct_same_body_note_promotion → p2:store; note_promotion_changes_source_authority_once → p2:store;
note_promotion_delegation_rolls_back → p2:store; deliverable_revision_lookup_preserves_immutable_history →
deliverables::stored_revisions_are_isolated…; report_freeze_and_approval_require_exact_preview →
deliverables::approval_binds…+bit_identical.

Run rows: run_and_nodes_are_created_as_one_pending_transition → runs::gate-exit pin + event tests (the
run+plan+pointer unit); duplicate_run_modules_and_collapsed_snapshot_cardinality → p2:bundle route-dup +
runs::snapshot_rejects_forged; run_claim_respects_shared_active_job_limit → runs::admission_ceiling;
node_completion_copy_failure_is_atomic_and_retryable + finalization_copy_failure → runs::crash_between_store_
commit_and_checkpoint (atomic+retryable via reuse-first CAS); snapshot_acceptance_updates_case_and_run_together
→ runs::acceptance_is_idempotent…together; run_public_shape_includes_ordered_nodes_and_events →
runs::event_log + http_contracts run family; loan_universe_versions_supersede_reject_withdraw +
postgres_loan_import_and_withdrawal_serialize → loan_universe (4 tests, both orders + injected interleaving);
postgres_assumption_creation_and_withdrawal_serialize → p2:store sequential halves + DEFERRED (D3) for the
two-connection staging; postgres_two_connection_uniqueness_and_claim_races → p2 dedup unique index
(ingest half), thesis half EXCLUDED (E1), two-connection staging DEFERRED (D3);
publication_versions_conflict_without_partial_append → EXCLUDED (E1).

Model rows (13): all → model_builder per its ROW MAPPING block (result validation matrix, bounded
errors/export-requeue, sign-off CAS/append-only/identity/superseded, authority order ×2, serialization with
concurrent completion, cross-case/superseded rejection, shared admission budget, concurrent queue idempotency,
two-writer CAS).

## test_cp_dr_runtime.py — 35 contractual rows (re-hosted per DECISIONS §11.9)

snapshot_payload_rejects_forged_succeeded_run → runs::snapshot_rejects_forged;
memory_research_plan_pause_and_exact_approval → deliverables filing gate (hash-bound interrupt);
cpdr_rejects_nonfinite_and_false_citations → evidence::forged_citation + model_builder NaN-refusal;
host_provenance_controls + material_source_characterisation → misc::confidence_derives_only_from_host…;
promoted_note_origin_digest → p2:store (content-addressed promotion);
prompts_keep_complete_brief_and_untrusted_separate → modules::prompts_keep_untrusted…;
vendored_authority_fails_if_integrity_changes → p2:bundle tamper + modules::verify_at_use;
agent_loop_rejects_malformed_usage + gateway_rejects_invalid_token_counts → budget::malformed_usage;
gateway_rejects_duplicate_json_keys → misc::final_model_output_rejects_duplicate_json_keys;
gateway_records_terminal_when_reservation_fails → budget::no_provider_call_without_reservation;
cpdr_authority_mismatches_fail_closed → modules::run_pins_build_id… + runs::withdrawing_pinned_source;
cpdr_reclaimed_unresolved_inflight → budget::unresolved_inflight…without_respend;
cpdr_existing_fingerprint_relinked → runs::kill/crash tests (reuse-first, zero provider calls);
strict_artifact_validator_rejects_noncanonical → modules::canonicalize/headings + state::plan tamper;
entrypoints_require_current_bundle_integrity → modules::swap-bundle + verify_at_use;
evidence_reads_enforce_case_pin_withdrawal_block_identity → evidence (six boundary tests);
runwide_budget_ceilings → budget::each_ceiling_refuses…;
manifest ×4 (ceiling, oversized fields, locator nodes, exact boundaries) → budget manifest/locator tests;
unexpected_post_provider_failure_sanitized + failure_metadata_no_secrets → budget::secret_bearing_failure;
approval_wait_excluded_while_planning_charged → budget::gate_wait_accrues_zero;
success_finalization_single_terminal_mutation → runs::event_log single run.succeeded + crash-gap;
finalization_reservation_failure + atomic_success_rollback → runs::crash-gap (one artifact/charge/terminal);
slow_render / throwing_host_ops / slow_atomic_completion / no_pending_final_validation → DEFERRED (D1);
174_plus_ten_never_commits + two_second_commits_inside_deadline → DEFERRED (D2);
(budget constants themselves: budget::literal-constants tests).

## test_cp_dr_planning.py — 9 contractual rows

Eight → deliverables filing-gate tests per its ROW MAPPING (caller-owned authority fields; canonical hash
form; bit-identical approval + one audit event; wrong/tampered/changed-source-set/wrong-phase rejection;
upstream identity required; 404/403 matrix; approver-standing matrix — with the recorded approver-gating
adaptation). The ninth, research_plan_is_deterministic_complete_and_identity_bound, re-hosts its
determinism/identity core onto the run plan: runs::plan_digest_is_carried_outside… + replay test.

## test_cp_model.py (45) + test_model_acceptance_queue.py (6) + test_model_store.py (1)

All 52 → model_builder per its ROW MAPPING block, with three rows expressed in sibling files it names
(host identity → modules; unreturned-source citation → modules; turn-budget arithmetic → budget) and one
recorded PARTIAL (model_api freeze/approval halves live on the deliverables surface per §10.10).

## test_deliverables.py (21) + test_deliverable_exports.py (8)

All 29 → deliverables per its ROW MAPPING block (splits/merges documented inline; none inexpressible).

## test_http_response_contracts.py — 15 contractual rows

Fourteen → http_contracts per its ROW MAPPING block (families ×9, strict rejects, audit actions ×15,
lifecycle shapes, source shapes, withdrawn retrievability, promotion conflict, snapshot diff identity,
OpenAPI strictness, canonical generation state, RV findings strictness, fail-closed response validation).
methodology_draft_response_validates_each_lifecycle_shape → EXCLUDED (E2).

## test_loan_universe.py — 17 contractual rows

All 17 → loan_universe per its ROW MAPPING block (parser determinism/provenance, fail-closed findings ×5,
formula non-execution, package screening ×2, sheet cap, idempotent import, structured-findings preservation,
vault digest recheck, case scoping, withdrawal deactivation, CP-3 binding).

## Exclusions (surfaces cut from the MVP — DECISIONS §1, §10.10, §11.9)

- **E1 — legacy report era** (thesis, recommendation matrix, report freeze/approve/export): 5 full rows +
  the thesis halves of 2 mixed rows. The invariants they carried (CAS conflicts, withdrawn-evidence ban,
  approval digest binding) are asserted on the surviving store/deliverables surfaces mapped above.
- **E2 — methodology draft editing**: 1 row (+ the step-up half of the production-identity row). Bundle
  verify and audit remain covered; editing methodology is not an MVP activity.

## Deferrals (tests that need the built implementation's internals to be expressible)

- **D1 — metering-bracket coverage** (4 rows: slow-render, throwing-host-ops, slow-completion,
  final-validation charging): the §12.14 wrapper-coverage test enumerates the built loop's step table;
  it lands with the loop in phase 3 and is named in DECISIONS §12.14.
- **D2 — finalization deadline under a fake clock** (2 rows): the never-commit-past-ceiling /
  commit-inside-deadline pair needs the store finalize transaction's deadline parameter; lands with the
  phase-3 store finalize. The single-terminal and rollback halves are already spec'd (runs crash-gap tests).
- **D3 — two-real-connections Postgres staging** (residual halves of 2 rows): the guarantees are spec'd
  via both sequential orders + injected interleaving; the two-connection Postgres variant runs in the
  both-dialects CI lane once the store has a Postgres test target (container available locally).

## Invariant-to-test table + suite reconciliation (2026-08-27, phase 6)

Suite state on this date: **380 passed, 1 red.** The 11 asyncio-blocked tests were repaired
with user sign-off (the three `asyncio.get_event_loop().run_until_complete` glue lines became
`asyncio.run`; test bodies untouched) and all pass. The one red is
`test_focus_questions_reject_surrogates_at_the_api_contract`, which cannot serialize its own
request on this interpreter (httpx `json.dumps` fails on the lone surrogate client-side); the
contract was verified server-side with a raw-bytes request (422, input not echoed).

Addendum (2026-08-27, later the same day, user-approved): the surrogate test was repaired to
send exactly that raw-bytes form — the body is pre-serialized with `ensure_ascii` so the lone
surrogate rides the wire as the JSON escape `\ud800`, which the server decodes back into the
surrogate before the boundary check; the test now also asserts the rejected input is not
echoed. Suite state after the repair: **384 passed, 0 red.**

The ten invariants are numbered here exactly as the repo already numbers them (spec-file
docstrings, DECISIONS.md §§6/2/12, code comments); no other enumeration exists in-repo.

| # | Invariant | Failing test on break | Status |
|---|---|---|---|
| 1 | Runs execute only against the pinned, immutable source set — supplied-only evidence, web discovery structurally banned, withdrawal checked live | `spec/test_runs_spec.py::test_withdrawing_pinned_source_mid_run_fails_the_run_closed` (pin placement: `…::test_gate_exit_pins_exact_current_source_set_and_later_uploads_do_not_move_it`) | green |
| 2 | Every `read_evidence` is validated at the host boundary (case, pin, withdrawal, block identity) and fails closed with a typed refusal, no text returned | `spec/test_evidence_spec.py::test_read_outside_pinned_source_set_fails_closed` | green (fixture glue repaired with user sign-off 2026-08-27) |
| 3 | The host owns identity: provider-claimed frontmatter never survives; checkpointed digests are expectations re-verified against the store, never authority | `spec/test_modules_spec.py::test_host_owns_identity_and_discards_provider_frontmatter` | green |
| 4 | Methodology authority is the verified vendored bundle — integrity checked on the bytes at use; a run pinned to one build never executes under another | `spec/test_modules_spec.py::test_verify_at_use_rejects_bytes_that_mismatch_the_pinned_manifest` (build pin: `…::test_run_pins_build_id_and_refuses_execution_under_a_different_bundle`) | green |
| 5 | Every gate where execution waits on a human is a digest-bound interrupt; approval binds the exact reviewed content | `spec/test_deliverables_spec.py::test_approval_binds_exact_preview_digest_and_fingerprint_mismatch_leaves_frozen_retryable` | green |
| 6 | Execution is durable and exactly-once: resume from last checkpoint, never restart; a crash in the commit gap yields one artifact, one charge, one terminal | `spec/test_runs_spec.py::test_worker_killed_mid_run_resumes_from_last_checkpoint_not_restart` (crash gap: `…::test_crash_between_store_commit_and_checkpoint_write_yields_one_artifact_one_charge`) | green |
| 7 | Model calculation is pure and finite — non-finite values and zero denominators refused, forecast values driver-sourced | `spec/test_model_builder_spec.py::test_finite_guards_reject_non_finite_and_zero_denominators` | green |
| 8 | Budgets fail closed — every ceiling refuses before overspend; no provider call without a reservation; unresolved inflight fails the resumed run | `spec/test_budget_spec.py::test_each_ceiling_refuses_the_next_operation_before_overspend` | green |
| 9 | Module output survives only as the strict canonical envelope — bounded schema, undeclared fields refused, citations only from delivered evidence | `spec/test_modules_spec.py::test_canonical_output_schema_is_strict_and_bounded` | green |
| 10 | A run's route is static — node set and edges are a pure function of (pathway, depth); replay from the same pins is equivalent by the same path | `spec/test_runs_spec.py::test_node_set_and_edges_are_a_pure_function_of_pathway_and_depth` (replay: `…::test_replay_from_same_pinned_sources_and_build_is_equivalent_by_the_same_path`) | green |

### CONTRACTUAL-row reconciliation (229 rows)

229 = **223 mapped and green** + **6 excluded with recorded justification** (E1 ×5, E2 ×1).

The D1/D2 deferrals — recorded above as "lands with phase 3" and found unlanded at the phase-6
check — landed 2026-08-27 in `caos/tests/test_finalization_metering.py`, one test per re-hosted
row plus the §12.14 wrapper-coverage test that enumerates the loop's step table (count, create,
evidence read, final parse/validate, reuse-validation, completion write, final verification):

- D1 (4 rows): slow render charged before completion; throwing host ops charge active time;
  slow atomic completion crosses the ceiling and cannot succeed; final validation charged
  before run success.
- D2 (2 rows): a success commit that would breach the ceiling never lands (durable failed
  state, no success event, acceptance refused); a within-budget commit lands succeeded with
  exactly one event, re-read from a revived engine.

The D2/D1-4 contract required one implementation change: `Engine._finalize_node` now meters
the final re-validation as a §12.14 bracket (charged even on throw) and fails the run closed
on an over-ceiling charge before `finalize_success` — success never commits past the budget
ceiling. Verified: the pre-change runtime fails exactly the wrapper-coverage, final-validation,
and never-lands tests.

D3 (residual Postgres two-connection halves of 2 rows) remains deferred on its original reason —
no Postgres test target exists in CI yet; flagged for the phase-6 gate since this is the last phase.

## Prompt-injection behaviour suite (2026-08-31)

Every document CAOS ingests is attacker-controlled. Until this date the only
recorded defence was the untrusted label (`methodology/prompt.py`,
`engine/authority.py::compile_module_prompts`) and one *placement* test —
`spec/test_modules_spec.py::test_prompts_keep_untrusted_data_out_of_system_authority`,
which asserts that source-derived text stays out of the system prompt. Nothing
asserted **behaviour**: what the host does when a document instructs the model
to escape and the model complies.

`caos/tests/spec/test_injection_spec.py` (14 tests) closes that half against
`caos/tests/fixtures/injection/` — ten adversarial documents — driven by a
maximally cooperative provider double (`CompliantProvider`). It reads the pinned
document through the real `read_evidence` tool, parses the attacker's
`CAOS-INJECT:` directive out of the returned evidence, and carries it out
verbatim: it never resists, refuses, or sanitizes. Every assertion is on the
**host's** refusal — a test that passes only because the model behaved asserts
nothing, so none is written that way.

| Injected instruction | Structural defence asserted | Invariant |
|---|---|---|
| read a source uploaded after the pin (`evidence_escape`) | pinned-set membership, typed refusal, no text returned | 1, 2 |
| read a source in another case (`evidence_escape`) | case binding on the pinned set | 1, 2 |
| read a source withdrawn mid-module (`evidence_escape`) | withdrawal re-checked live inside every read, not once at module entry | 1, 2 |
| read a homoglyph / zero-width lookalike of the pinned id (`homoglyph_evidence_escape`) | membership is byte equality — no confusable or NFKC folding | 1, 2 |
| fetch a URL through a second tool wearing `read_evidence`'s argument shape (`web_discovery`) | the tool surface is exactly one tool, refused by name | 1 |
| answer with no evidence because "the analyst approved" (`instruction_override`) | supplied evidence is a floor (`evidence_refs` min 1), backstopped by the delivered-set contract | 1, 9 |
| add undeclared envelope fields (`envelope_smuggling`) | strict canonical envelope refuses, never tolerates | 9 |
| cite a block the host never delivered (`citation_forgery`) | declared refs must equal the delivered set exactly | 9 |
| dictate the artifact's own frontmatter identity and build id (`provider_frontmatter_forgery`) | envelope rebuilt from pinned state; the run succeeds and every claimed value is gone | 3 |
| claim an external QA attestation over a failing source gate (`qa_status_forgery`) | `require_qa_passed` over host-recomputed confidence; non-Passed is terminal | 3, 9 |
| carry a forged "CAOS HOST EXECUTION CONTRACT" amendment (`fake_host_framing`) | the injection is delivered to the model and the system prompt stays byte-identical to the verified bundle authority (golden digest) for the whole run | 4 |
| supply forbidden `InvocationPlan` keys and a bidi-override focus question (`authority_key_injection`) | allowlist refusal per key; `validate_boundary_text` at the API boundary | 3, §12.3 |

### Anti-vacuity ledger

Each row below deletes exactly one host-side check, runs the whole suite, and
records what turns red. Ten of the fourteen new tests have an isolating deletion.
The other four are defence-in-depth scenarios, verified as such rather than
assumed: the cross-case read is caught independently by pinned-set membership
*and* by the case binding (deleting either leaves it green, which is why row 1
turns only the out-of-set test red); the two homoglyph parametrizations pin the
byte-equality *property* of membership, which a deletion cannot express (the
weakening that would break them is adding confusable or NFKC folding); and the
no-evidence answer is refused by `evidence_refs` min-length first and by the
delivered-set citation contract second — removing the min-length bound leaves it
green, so both were measured, not assumed.

| # | Check deleted | New test that turns red | Pre-existing tests also red |
|---|---|---|---|
| 1 | pinned-set membership (`engine/evidence.py`) | `test_out_of_set_source_named_by_the_document_is_refused_and_returns_no_text` | none |
| 2 | live withdrawal check (`engine/evidence.py`) | `test_withdrawal_racing_the_injected_read_is_caught_live_inside_the_tool` | 2 (evidence spec) |
| 3 | `CanonicalModuleOutput` `extra="forbid"` (`methodology/canonical.py`) | `test_smuggled_envelope_fields_are_refused_not_ignored` | 1 (modules spec) |
| 4 | `read_evidence` tool-name check (`engine/loop.py`) | `test_web_discovery_instruction_cannot_reach_a_second_tool` | none |
| 5 | host frontmatter stamp + section rebuild (`methodology/canonical.py`) | `test_forged_frontmatter_from_the_document_never_survives_canonicalization` | none |
| 6 | delivered-set citation equality (`methodology/canonical.py`) | `test_citation_to_an_undelivered_block_is_refused` | 1 (evidence spec) |
| 7 | system/user prompt separation (`engine/authority.py`) | `test_a_forged_host_contract_inside_a_document_never_becomes_system_authority` | 4 (modules spec, module wiring) |
| 8 | `InvocationPlan` allowlist (`methodology/prompt.py`) | `test_every_forbidden_authority_key_the_document_names_is_refused` | 1 (modules spec) |
| 9 | focus-question boundary text (`engine/runtime.py`) | `test_a_focus_question_copied_out_of_a_document_carries_no_authority` | none |
| 10 | `require_qa_passed` in the agent validate step (`engine/runtime.py`) | `test_a_document_cannot_talk_a_blocked_module_into_qa_passed` | none |

No host code changed: every defence these tests assert already existed. Suite
state after the addition: **461 passed, 12 skipped** (the skips are the
real-issuer corpus tests, which run when the corpus is downloaded).

## read_evidence argument-shape enumeration (2026-08-31)

`read_evidence` is the only tool a module can call, so its argument surface is
the whole agentic attack surface. Invariant 2's named test asserted one refusal
class (a source outside the pinned set) and the injection suite added three more
end to end (cross-case, withdrawn mid-module, homoglyph ids). What no test
enumerated was the rest of the shapes a module can put on the wire, and nothing
asserted invariant 2's "no text" clause *literally* — that no source text
escapes through an error message, a diagnostic field, or an exception string.

`caos/tests/spec/test_evidence_spec.py` now carries that enumeration: 33 refusal
scenarios, each asserted twice — once for the typed taxonomy code, once for the
literal no-text contract (the rendered exception chain plus `args` carries none
of three marker strings; the delivered set stays empty; the ledger does not
move). Both assertions run against a pinned FULL_CREDIT run whose evidence text
is a unique marker.

| Argument shape | Refusal |
|---|---|
| absent / unknown `block_id`; empty `block_id` | `AGENT_OUTPUT_INVALID` |
| duplicate `block_ids`; empty list; > 50 ids | `AGENT_OUTPUT_INVALID` |
| `block_ids` not a list (str, dict, null) | `AGENT_OUTPUT_INVALID` |
| a `block_id` that is int, float, null, bool, array, or bytes | `AGENT_OUTPUT_INVALID` |
| `source_id` that is int, float, null, array, dict, bool, or bytes | `AGENT_OUTPUT_INVALID` |
| a `block_id` valid for a *different* source of the same case | `AGENT_OUTPUT_INVALID` |
| lone-surrogate `block_id`; 1 MB `block_id` | `AGENT_OUTPUT_INVALID` |
| source in another case | `AGENT_AUTHORITY_MISMATCH` |
| source withdrawn (before, or live during, the run) | `AGENT_AUTHORITY_MISMATCH` |
| source in this case but outside the pinned set (a later source-set version) | `AGENT_AUTHORITY_MISMATCH` |
| unknown, empty, lone-surrogate, or 1 MB `source_id` | `AGENT_AUTHORITY_MISMATCH` |
| read-count ceiling; byte ceiling; run-wide ledger ceiling | `AGENT_BUDGET_EXCEEDED` |
| tool arguments off the strict `{source_id, block_ids}` shape (14 forms) | `AGENT_OUTPUT_INVALID` |
| duplicate JSON keys in a tool-call argument object | `AGENT_OUTPUT_INVALID` |

Block ids are per-source counters (`b00001`…), so they collide across sources by
construction. Evidence identity is therefore the `(source_id, block_id)` **pair**:
`test_a_block_id_that_collides_across_sources_reads_only_the_named_source` pins
that naming the pinned source can never reach another source's like-named block.

**No refusal leaks content.** Every `AgentError` message on the read path is a
static literal; the persisted run error is `{code, module_id}` and carries no
message; and structurally a refusal is never a `tool_result` at all — it ends the
module, so there is no channel left to carry text, a code, or a reason. Two
adjacent paths were inspected and are not leaks: `validate_citations` and the
canonical validators raise fixed strings, and the loop's repair turn echoes
`str(exc)[:1500]` from validating the model's **own** output back to the same
model, which is not a trust boundary.

### The read path's other side: bounding the call count

There is **no per-node bound**. The reader a module node is handed is sized
`limits["evidence_reads"] - used` read at node entry, so a looping module drinks
the whole run's allowance. It cannot stall the run: the run-wide ledger refuses
read N+1 and the run fails closed. Measured on FULL_CREDIT/full (N=9, ceiling 90):
CP-1 took exactly 91 turns — 90 reads then the refusal — and `used` landed exactly
on the ceiling, never past it. A *failed* read cannot be looped at all, because
the refusal is not answered back to the model. Concurrent sibling nodes in one
superstep each size their reader from the same pre-read `used`, which is why the
ledger, not the local guard, is the binding bound.

### Three defects found and closed

1. **An unhashable `block_id` left the boundary as a bare `TypeError`.**
   `len(block_ids) != len(set(block_ids))` was evaluated before the element-type
   check, so `[["b00001"]]` raised `TypeError: unhashable type: 'list'` instead
   of a typed refusal — collapsed downstream to `CANONICAL_GENERATION_FAILED`,
   which fails closed but violates §12.9's rule that the adversarial suite pins
   which code each refusal carries. Fix: the element-type check moves ahead of
   the dedup set (`engine/evidence.py`).
2. **A ledger-refused read left a citation expectation.** The delivered-set
   update ran *before* the run-wide `charge_budget` call, so a read the store
   refused still registered `(source_id, block_id)` as delivered. §12.10 orders
   it charge → delivered-set → return. Unreachable while one node runs alone
   (the local guard trips first), reachable between concurrent sibling nodes.
   Fix: the ledger charge moves ahead of both the reader's counters and the
   delivered-set update (`engine/evidence.py`).
3. **Duplicate JSON keys in tool arguments were silently last-wins on the
   OpenRouter binding.** `engine/openrouter.py::_blocks` parsed tool-call
   arguments with a plain `json.loads`, so `{"source_id": A, …, "source_id": B}`
   collapsed to B. Not an authority bypass — B is still authority-checked — but
   the §12.9 duplicate-key rule that governs the final output governs this
   string for the same reason: the model authors it and the host parses it.
   Fix: the same `reject_duplicate_keys` hook the final-output parser uses.
   (The Anthropic binding is unaffected: `block.input` arrives pre-parsed from
   the SDK and the host never sees the raw bytes. The enclosing OpenRouter
   response body stays on plain `response.json()` — its shape is the gateway's,
   not the model's, and `_blocks` trusts that shape throughout.)

### Anti-vacuity ledger

| # | Check deleted | Test that turns red | Pre-existing tests also red |
|---|---|---|---|
| 1 | element-type check ahead of the dedup set (`engine/evidence.py`) | `test_every_argument_shape_fails_closed_with_a_typed_refusal[block_id_is_an_array]` | none (+ its no-text twin) |
| 2 | `object_pairs_hook` on tool arguments (`engine/openrouter.py`) | `test_duplicate_tool_argument_keys_are_refused_not_collapsed` | none |
| 3 | ledger charge ahead of the delivered-set update (`engine/evidence.py`) | `test_a_ledger_refused_read_leaves_no_expectation_even_though_rows_were_built` | none |
| 4 | the loop ending the module on a refused read (`engine/loop.py`, replaced with an error row returned as a `tool_result`) | `test_a_refused_read_ends_the_module_instead_of_returning_a_reason_to_the_model` | none |
| 5 | the reader's local `read_limit` guard (`engine/evidence.py`) | `test_every_argument_shape…[read_ceiling]` + its no-text twin | 1 (`test_ceiling_rejected_read_leaves_no_citation_expectation`) |

Row 5 is the measured, not assumed, one: deleting the local guard leaves
`test_an_unbounded_read_loop_is_stopped_by_the_run_evidence_read_ceiling`
**green**, because that test pins the run-wide ledger ceiling and the ledger is a
second, independent bound. The two are recorded here as distinct defences rather
than one.

### Recorded non-findings

- **Identifier strings have no length bound.** A 1 MB `source_id` or `block_id`
  is refused by membership / block lookup, not by a length check, so the refusal
  costs one hash of the string. No fix: what a module can send is already bounded
  by its `max_output_tokens` cap, so there is no amplification to close.
- **`on_read` makes two `charge_budget` calls** (reads, then bytes) that are not
  atomic with each other. If the byte charge fails the read charge stands — an
  over-charge, the fail-closed direction, and the module dies either way.

Suite state after the addition: **570 passed** (the real-issuer corpus is
downloaded in this worktree; without it 12 corpus tests skip).

## Observability suite (2026-08-31)

Until this date the server had no logging, no metrics and no tracing — verified,
not assumed: `grep "import logging\|logger\."` over `caos/server` (excluding the
vendored venv under `caos/`) returned nothing. Three operational questions had no
answer short of attaching a debugger to production: **which run is stuck, what
did it refuse, what has it spent.**

`caos/server/caos/observability.py` answers them with stdlib logging and a JSON
formatter — no dependency, no framework, no debug channel. Seven log points and
nothing else:

| Point | Seam | Events |
|---|---|---|
| run + node state transitions | `storage/runs.py::RunStore._emit` | `run.created`, `run.running`, `run.paused`, `node.running`, `node.succeeded`, `run.succeeded`, `run.failed` |
| typed refusals | `engine/runtime.py` module + finalize handlers | `refusal` (code + module_id) |
| provider calls | `engine/loop.py` | `provider.call.start`, `provider.call.finish` |
| budget ledger | `storage/runs.py::reserve_provider` / `reconcile_provider` | `budget.reserved`, `budget.reconciled` |
| gate interrupt | `engine/runtime.py::_gate_node` | `gate.interrupt`, `gate.resolved` |
| startup recovery | `engine/runtime.py::recover` | `recovery.started`, `recovery.run` |
| worker job failure | `worker.py` | `worker.job_failed` |

`_emit` is the whole first row because every durable transition already passes
through it and nothing else does. `refusal` is logged at the module boundary
rather than read off `run.failed`, because `finalize_failure` is a CAS: racing
sibling failures in one superstep no-op, so the run row records only the refusal
that won. The log records all of them.

### The ban, and its test

**No document-derived text may ever reach a log line.** Source text, evidence
block text, module output and compiled prompts are attacker-controlled, and a log
sink sits outside every boundary the ten invariants defend. Two mechanisms:

1. **Call-site discipline.** Host-owned scalars only. Refusals log the taxonomy
   code and never `str(exc)` — a validation failure quotes the model's own output.
2. **A structural bound.** Every string on a line is redacted, then truncated to
   `MAX_STRING` (200). A slip costs a couple of hundred characters, not a document.

`caos/tests/spec/test_observability_spec.py` (26 tests) drives a real ingestion
and a real agent module over a document carrying a unique sentence, captures every
record any logger emits, renders each through the production formatter, and
asserts the sentence is absent. Anti-vacuity is asserted in the same test: the log
must be non-empty, the run must have succeeded, and the sentinel must have reached
the model — a host that never read the evidence cannot pass by doing less.

### Anti-vacuity ledger

| # | Check deleted / defect injected | Test that turns red | Notes |
|---|---|---|---|
| 1 | `log_event("evidence.read", rows=[r["text"] …])` added to `engine/evidence.py` | `test_no_document_text_ever_reaches_a_log_line` | the leak the suite exists to catch |
| 2 | `log_event("provider.call.start", …)` moved ahead of `slots.acquire_or_deny()` | `test_a_denied_provider_slot_logs_no_call_that_never_happened` | measured out of process (see below) |
| 3 | the refusal `log_event` removed from `_run_module` | `test_a_refused_read_logs_its_typed_code_and_none_of_the_document` | |
| 4 | `_clean`'s non-string branch left bypassing the bound | `test_every_logged_string_is_bounded_so_no_field_can_become_a_content_channel` | |
| 5 | `HealthResponse` left as `{status}` | `spec/test_http_contracts_spec.py::test_health_serves_the_pinned_readiness_key_set` | |
| 6 | a timeout/retry left with only the successful call's finish line | `test_a_retry_closes_every_started_provider_attempt` | every started attempt terminates |
| 7 | nested mapping keys bypassed `_clean` | `test_registered_secrets_are_redacted_from_nested_dictionary_keys` | registered secret reproduced in a key |
| 8 | worker failure logged `str(exc)` | `test_worker_failure_logs_the_exception_type_but_never_its_message` | document sentinel reproduced through the formatter |
| 9 | checkpointer probe tested only generic SQLite writability | `test_a_malformed_checkpoint_schema_is_not_ready` | readiness was true while a saver write failed |

Row 2 is the measured one. In-process the two orderings are *behaviourally*
identical — a standalone driver over `run_agent_module` with a never-released slot
raises `AGENT_BUDGET_EXCEEDED` in 0.000 s with zero provider calls either way — so
this is a log-correctness defect, not a control-flow one: the pre-fix order emits
one `provider.call.start` line for a call that never happened, and `start` with no
`finish` is exactly the shape an operator greps for to find a hung run. Verified
by capturing the formatter's output around that driver (1 line before the fix, 0
after) rather than through pytest, whose run does not terminate on this particular
failure for reasons that are in the reporting layer, not the engine.

### Readiness

`GET /api/health` was liveness only. It now serves `{status, store, bundle,
checkpointer}` on the same strict `HealthResponse`, 200 when all three hold and
503 otherwise, with the key set pinned in `test_http_contracts_spec.py` beside the
nine case families. The probes are real: `SELECT 1` on the domain store, the full
bundle integrity verification (invariant 4), and the actual LangGraph SQLite
schema followed by a `BEGIN IMMEDIATE`/rollback. An empty checkpoint database is
initialized through `SqliteSaver.setup`; a malformed schema fails closed; and a
competing writer gets 250 ms to release its lock before the instance reports
degraded.

Bounded to one probe per `READINESS_TTL_SECONDS` (5.0): the route skips
oauth2-proxy auth (`skip_auth_routes`) *and* the per-subject rate ceiling, so
hashing 307 bundle files (~12 ms) per anonymous request would be a lever. An app
assembled as `create_app(..., engine=None)` reports degraded rather than 500 —
that assembly is real, in the auth-edge tests.

### Secret redaction

`register_secrets` takes the exact values from `Settings` at `configure_logging`
time; a regex backstops keys nobody registered (`sk-…`, bearer tokens, DSN
userinfo), and mapping keys pass through the same cleaner as values. Exception
messages never reach a line: `worker.py::_failure` emits the exception class only,
replacing two `traceback.print_exc()` calls that printed raw tracebacks to stderr.

### Metrics and tracing: skipped

Not added. The seven log points answer all three questions as structured fields —
`node.running` without a following `node.succeeded` names the stuck node,
`refusal` carries the typed code, `budget.reconciled` carries the running `used`
totals. What would force metrics: more than one app instance (the log is
per-process, and `RequestCeilings` already counts in-process), or a need for rate
and percentile questions — "p95 provider latency", "refusals per hour by code" —
which are aggregations a log tail cannot answer. What would force tracing: a
second service in the request path. Neither exists today.

## Identity boundary audit (2026-08-31)

The requested ASVS 5.0 authentication/session/access-control audit uses the
current ASVS chapter numbers V6/V7/V8 (the requested V2/V3/V4 names are the
ASVS 4.x numbering for those domains).

- **Authentication boundary:** production accepts roles only from
  `X-Forwarded-Groups` after a constant-time edge-secret check. Environment
  selection now allowlists exactly `development` and `production` both at
  startup and inside `identity_from_request`; casing or an alias can no longer
  select development behavior. Duplicate edge, subject, email, or groups
  headers fail with 401. Header names remain correctly case-insensitive.
  Caddy strips all four trusted headers, oauth2-proxy v7.15.4 replaces its user
  headers, and `skip_auth_strip_headers = true` is now explicit rather than an
  upstream default the deployment silently depends on.
- **Access control:** `run_sec_audit.py` derives the live route table and checks
  all 42 non-public API operations at the ASGI gate. It also drives all 34
  case-scoped operations with a foreign case, every case-scoped write with a
  valid body as a stored READER, run IDs, and the model-build query ID. The only
  public path remains `GET /api/health`. Unknown and foreign runs now execute
  the same `run -> case -> membership` lookup class and return identical status,
  JSON body, and headers.
- **Internal bypass boundary:** the app port is not published and a direct
  internal request without `EDGE_PROXY_SECRET` gets 401. A process holding that
  secret can assert forwarded identity headers; this is the deliberate trusted
  edge boundary, not a cryptographically signed per-user assertion. Caddy,
  oauth2-proxy, and the worker are therefore inside the deployment trust zone
  (the worker already has database and vault authority).
- **Session management limitation:** the proxy config pins Secure, HttpOnly,
  SameSite=Lax cookies and a seven-day expiry, but it does not configure
  `cookie_refresh` or establish an idle timeout, and the repository does not
  state the IdP access/refresh-token lifetimes. ASVS session-lifetime and
  renewal alignment therefore remain unproven. No refresh interval was guessed;
  set it only after the IdP policy is known, with cookie expiry no longer than
  the effective refresh-token/session lifetime.
