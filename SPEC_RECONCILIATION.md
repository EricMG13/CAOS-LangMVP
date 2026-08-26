# Spec Reconciliation — spec-v1

Every row classified CONTRACTUAL in TEST_INVENTORY.md (229 after the RV reclassification) maps below to
(a) a spec test in `caos/tests/spec/` (red today by design — the implementation does not exist),
(b) a phase-2 test in `caos/tests/` that already passes because its surface was built in phase 2, or
(c) an entry in the exclusion/deferral lists at the end.

Spec-suite state at tag `spec-v1`: **315 red (122 failed + 193 errors), 0 passing.** The 53 passing tests
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
