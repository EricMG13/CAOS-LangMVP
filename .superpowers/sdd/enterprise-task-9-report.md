# Enterprise Task 9 report — source-complete modelling for all pathways

Executed as `ER-G4` (started 2026-09-02) in
`.claude/worktrees/design-critique-export-d9156d` on branch
`claude/enterprise-readiness-model-cccaaa`, cut from `origin/main` at `c70902f`
(the Task 8 squash merge, PR #41). Local interpreter: Python 3.14.6 in a
dedicated venv built from the hashed lock
(`uv venv --python 3.14 caos/server/.venv314` then
`uv pip install --require-hashes -r caos/server/requirements-dev.txt` and an
editable, dependency-less install of `caos/server`; no `uv run`, no `uv.lock`).
The 30-document Carnival corpus was copied from the primary checkout
(gitignored). Frontend dependencies were already installed in the worktree.

Inputs read before starting: Task 9 of
`docs/superpowers/plans/2026-09-01-enterprise-testing-readiness-execution.md`,
Phase 3 items 9 and 10 of `ENTERPRISE_READINESS_PLAN.md`, CALC-001–CALC-020 and
the metamorphic rule under "Test deterministic models and scenarios" in
`ENTERPRISE_TESTING_READINESS.md`, `docs/DECISIONS.md` §14.12–§14.17,
`SPEC_RECONCILIATION.md` (CP-MODEL rows and the calculator addendum), the
model service, the Distressed overlay, the intake service and classifier, the
loan-universe importer, the corpus host control and the existing model,
intake, Distressed and deliverable specs.

## Status

Complete on the branch: every gate in "Commands and results" is green on the
final code (the full backend suite row carries its own result), and the draft
pull request https://github.com/EricMG13/CAOS-LangMVP/pull/44 to `main` carries
the same table. Licensed market marks and
live-model qualification of every effect stay BLOCKED EXTERNAL (Open items).

## Design (decided before the first test)

Findings that shaped it:

- Only Full Credit builds a model and only Distressed declares a model effect
  (`ModelService._resolve_snapshot` dispatches on those two pathways;
  `on_accepted` queues for those two). Earnings Update and Covenant &
  Refinancing acceptance reads `NOT_READY / ACCEPTED_FULL_CREDIT_REQUIRED`;
  Relative Value and Deep Research the same. The deliverable path for
  Earnings and Covenant reuses the nearest validated Full Credit build
  (`PRIOR_FULL_CREDIT_BASE`) but no model record says what those pathways did
  to the model.
- The Distressed overlay is the right shape to generalise: a validated prior
  Full Credit READY build, the accepted run's verified calculation records,
  one `pathway_effects` entry on the model payload, its own input fingerprint,
  a "Pathway Effects" audit worksheet on every export, and a deliverable guard
  that binds the effect to the accepted snapshot.
- The intake manifest (`case_intakes.record.documents`) already carries a
  disposition, a bounded reason and expected consumers per supplied file, but
  nothing downstream reads it: no model record proves that a `used` annual,
  quarterly or forecast document reached model inputs, calculations or cited
  analysis, and a Full Credit build over a case whose artifacts cite one of
  three documents reads READY.
- `read_evidence` is bounded run-wide at ten reads per agent module
  (`EVIDENCE_READS_PER_MODULE`), so a source-complete provider double must
  spread its reads across the route rather than read every source in every
  module. `HostControlProvider` reads one block of the first source only, so
  every keyless host-control run is, truthfully, not source-complete beyond
  one document.
- Loan-workbook cell text is bounded (32 KB) but not `BoundaryText`
  (`artifacts/loan_universe.py::_text`), the known gap in `CLAUDE.md`.
- Screen-depth Full Credit has no canonical modules, so its accepted
  snapshot read as `CANONICAL_MODEL_INPUTS_INVALID` — a depth precondition
  reported as corruption.

Decisions:

- **One overlay mechanism, five effects.** `_resolve_snapshot` dispatches on
  the accepted run's pathway. Full Credit builds the complete model as before.
  Every other pathway resolves through one `_resolve_overlay_snapshot`: the
  nearest validated Full Credit ancestor (`_prior_full_credit_snapshot`, chain
  validated by identity, base fully live), the base build re-verified by
  recomputation (`_validated_base_build`), the accepted run's calculation
  records re-executed and compared record-for-record
  (`_validated_calculations`, generalised from the CP-4C check), and one
  effect entry. Effect ids: `EARNINGS_PERIOD_FORECAST_VARIANCE`,
  `COVENANT_REFINANCING_ASSUMPTIONS`, `RELATIVE_VALUE_MARKET_MARKS`,
  `DISTRESSED_SCENARIO_RECOVERY` (unchanged shape), `DEEP_RESEARCH_REVALIDATION`.
  The base model's tabs are copied byte-identically into the overlay payload;
  the effect never rewrites a base period, assumption or output (invariant
  CALC-006 by construction); the overlay has its own input fingerprint so a
  base build and its overlays are distinct, content-addressed rows.
- **Earnings Update updates periods and forecast variance.** The effect
  carries `period_updates` — every reported period in the run's verified
  CP-1/CP-1B `credit_metrics` records with its reported inputs and host-
  recomputed KPIs, authority `REPORTED_ACTUAL` — and `forecast_variance`: for
  each reported fiscal year the base model forecasts (BASE and DOWNSIDE
  columns, authority `ANALYST_FORECAST`), reported minus forecast and the
  finite ratio, or a named gap (`FORECAST_PERIOD_NOT_MODELLED`,
  `ACTUAL_NOT_DISCLOSED`) — never zero, never interpolated.
- **Covenant & Refinancing updates covenant and refinancing assumptions.** The
  effect carries `covenant_updates` (every CP-4 `covenant_headroom` test:
  threshold, current ratio, headroom, status, authority
  `DOCUMENTARY_COVENANT_TERMS`), `refinancing_updates` (CP-4C `funding_gap`
  maturity wall, liquidity and gap per view) and `assumption_updates`: the
  base registry slots a covenant test maps to (`covenant.max_total_leverage`
  for a maximum leverage test), with the base row's value/status and the
  proposed documentary value, treatment `PROPOSED_FOR_SIGN_OFF`; a test with
  no registry slot is a named gap (`UNMAPPED_COVENANT_TEST`). Adoption goes
  through Model Builder's preview → sign-off seam; nothing is applied
  silently.
- **Relative Value attaches time-aligned market marks supplied by upload.**
  The accepted run's plan must pin a loan universe (the intake imports the
  workbook before the gate; a manual run without one reads
  `RELATIVE_VALUE_MARKET_MARKS_REQUIRED`); the effect re-reads the store
  record, recomputes `universe_digest`, requires the workbook's source to be
  in the accepted set, and attaches a bounded projection of every row
  (instrument key, borrower, sector, bid/ask, mid YTM, mid DM, maturity) plus
  `time_alignment`: the workbook date against the base model's latest
  reported period end and the run's analysis date, status `ALIGNED`,
  `PRECEDES_LATEST_REPORTED_PERIOD` or `POSTDATES_ANALYSIS` — a labelled
  limitation, never a silent acceptance and never a fabricated mark. The
  licensed pack is an external input; the fixture is synthetic.
- **Deep Research revalidates or declares no numeric effect.** With a prior
  Full Credit READY build the acceptance queues `DEEP_RESEARCH_REVALIDATION`
  (`numeric_effect: NONE`, the base recomputed and compared, the CP-DR
  artifact and approved plan hash bound); without one readiness is
  `NOT_READY / DEEP_RESEARCH_NO_NUMERIC_EFFECT` — the declaration is the
  typed state, not a fabricated model. Supersedes the "queues no build" clause
  of §14.16.
- **Source lineage is part of the model.** Every build (base or overlay)
  carries `source_lineage`: one row per source in the accepted snapshot's set
  with the intake disposition and reason when the accepted run came from an
  intake (else `used` / "supplied through the source route"), the expected
  consumers, the artifacts that cite it, the model-facing tables that name it,
  and one binding: `MODEL_INPUT`, `CITED_ANALYSIS`, `MARKET_MARKS`,
  `SUPERSEDED`, `NOT_REQUIRED` (duplicate / insufficient / other) or `UNBOUND`.
  A `used` relevant source (annual, quarterly, earnings, guidance/forecast,
  legal, restructuring, market marks, brief) that is `UNBOUND` fails the build
  with the typed `MODEL_SOURCE_LINEAGE_INCOMPLETE` — a host-control run that
  cited one of three documents is not source-complete and now says so. The
  lineage rides the payload (fingerprint-bound), the worksheet, the export
  ("Source Lineage" audit sheet) and a `model.build_ready` audit event written
  in the same transaction as the READY transition.
- **Truthful readiness states.** `FULL_DEPTH_REQUIRED` for an accepted
  screen-depth run whose route lacks the modules its effect needs (Full
  Credit, Earnings, Covenant and Relative Value at screen depth; Distressed
  screen keeps CP-4C and still overlays); `PRIOR_FULL_CREDIT_MODEL_REQUIRED`
  for an overlay pathway with no Full Credit model in the chain (Distressed
  keeps its pinned `DISTRESSED_BASE_MODEL_REQUIRED`). `queue_build` refuses
  with `MODEL_NOT_READY: <code>` so the wire code is unchanged. Model Builder
  renders any blocker code generically; no frontend change.
- **Host control becomes source-complete.** `HostControlProvider` reads one
  block from each pinned source (bounded by the module read allowance) so the
  keyless gates exercise every supplied document; the corpus double spreads
  thirty reads across the route.
- **Loan-workbook text is `BoundaryText` at the importer.** `_text` runs the
  boundary validator; a failing cell is a structured finding
  (`RV_CELL_TEXT_INVALID`) and the workbook is REJECTED, closing the
  `CLAUDE.md` gap at the one seam every path shares.

## Delivered

- **One overlay mechanism, five effects** (`caos/server/caos/models/service.py`):
  `_resolve_snapshot` dispatches on the accepted pathway; `_require_effect_modules`
  turns a screen-depth route without the effect's modules into
  `FULL_DEPTH_REQUIRED`; `_resolve_overlay_snapshot` resolves the base chain,
  re-verifies the base build, re-executes the run's calculation records
  (`_validated_calculations`, generalised from the CP-4C check with a
  `required` set) and builds the effect from one of five builders
  (`_earnings_effect`, `_covenant_effect`, `_relative_value_effect`,
  `_distressed_effect`, `_deep_research_effect`); module-level helpers
  `_forecast_variance`, `_covenant_assumption_updates`, `_covenant_slot`,
  `_latest_reported_period_end`, `_table_rows`, `_decimal_text`. The
  Distressed effect keeps its pinned shape (`distressed_authority`, the CP-4C
  artifact ids) and gains `limitations`.
- **Source lineage** (`_source_lineage`, `_live_snapshot_sources`): one row
  per pinned source with disposition, reason, consumers, citing artifacts,
  model-table membership and binding; `MODEL_SOURCE_LINEAGE_INCOMPLETE` with a
  detail naming the unbound source ids; the lineage digest inside every input
  fingerprint; `source_lineage` on every build payload; a "Source Lineage"
  audit worksheet beside "Pathway Effects" on previews and exports
  (`_audit_rows`, `_audit_tab`, `_audit_tabs`, `_with_audit_tabs`).
  `DomainStore.intakes_for_case` supplies the merged intake manifests;
  `methodology/canonical.py::model_facing_source_ids` is the one reader the
  validator and the lineage share.
- **Truthful readiness** (`PRECONDITION_DETAILS`): `PRIOR_FULL_CREDIT_MODEL_REQUIRED`,
  `DEEP_RESEARCH_NO_NUMERIC_EFFECT`, `FULL_DEPTH_REQUIRED`,
  `RELATIVE_VALUE_MARKET_MARKS_REQUIRED`, `MODEL_SOURCE_LINEAGE_INCOMPLETE`
  read as NOT_READY with a rendered detail; `queue_build` answers
  `MODEL_NOT_READY: <code>`; `ModelInputError` carries an optional `detail`.
  `on_accepted` queues for all six pathways.
- **Audit lineage**: `ModelStore.update_build(audit=...)` runs a callback in
  the READY transaction; `_complete` writes `model.build_ready` (build,
  snapshot, run, payload digest) through the existing audit keys.
- **Doubles**: `engine/host_control.py` reads one block of every pinned
  source, bounded by `EVIDENCE_READS_PER_MODULE`; the corpus `CorpusProvider`
  spreads one read of each document across the route and emits the golden
  CP-MODEL fixtures for the canonical modules, so the six-route host control
  builds the Full Credit model and every overlay.
- **Importer**: `artifacts/loan_universe.py::_text` runs
  `validate_boundary_text`; `RV_CELL_TEXT_INVALID` is a structured finding.
- **Tests**: `caos/tests/spec/test_source_complete_modelling_spec.py` (27
  tests: the source-complete Full Credit build with its export and audit, the
  lineage oracle, eight metamorphic cases, the re-dropped source-route
  document, every pathway's effect in one case, misaligned marks, missing
  marks, Deep Research without a base, four screen-depth preconditions, the
  forged-record refusal, CALC-005/006 and CALC-012 at six boundary cells);
  `test_corpus_pathways.py` asserts every pinned document is cited
  on every route and the accepted snapshot's model effect per (pathway,
  depth); `test_model_builder_spec.py` pins the new code on the two
  non-Full-Credit tests.
- **Docs**: `docs/DECISIONS.md` §14.18 and the §14.16 cross-reference;
  `SPEC_RECONCILIATION.md` (CALC-001–020 map, metamorphic table, anti-vacuity
  ledger); `ENTERPRISE_TESTING_READINESS.md` ETR-B12; `CLAUDE.md` (model
  effects, the closed importer gap, two new follow-ups);
  `docs/QUALITY_LEDGER.csv` F-MODEL-01.

## Assumptions stated

- "Every used source reaches model inputs, assumptions, calculations, or
  cited analysis" is read literally against the accepted snapshot: a source
  reaches the model when a model-facing table names it, the pinned loan
  universe or the bound brief is it, or an accepted artifact cites it.
  Calculation records carry no source ids, so "calculations" is proven
  through the artifact that ran them. The host cannot force a model to cite a
  document; it can refuse to call the result source-complete, which is what
  `MODEL_SOURCE_LINEAGE_INCOMPLETE` does.
- Every delivered evidence block must be cited (`validate_citations` requires
  equality), so a document the analysis did not use is one it never
  requested. The doubles model "unused" as "never read".
- The covenant effect proposes registry updates; the pinned CP-MODEL engine
  refuses a preview that changes an assumption's status, so a slot the
  accepted CP-2G handoff left UNAVAILABLE is `PROPOSED_REQUIRES_FULL_CREDIT_HANDOFF`,
  not adoptable through preview. The governed route to adopt it is a Full
  Credit re-run whose CP-2G sources the covenant. Recorded in §14.18.
- The quarterly report's answer-keyed effect is the CP-1B snapshot table
  (adding a fifth reported quarter to the four-quarter golden would change
  every fixture-driven test); its removal changes the input, the artifact,
  the fingerprint and the lineage and no output, which is what the test pins.
- Deliverable binding for Earnings and Covenant is unchanged
  (`PRIOR_FULL_CREDIT_BASE`); the new effects are on the overlay builds and
  their exports. Rendering them in published outputs is Task 10 (recorded in
  `CLAUDE.md`).
- The corpus control asserts `RELATIVE_VALUE_MARKET_MARKS_REQUIRED` for the
  Relative Value full route because the Carnival pack carries no CP-3
  workbook; the synthetic workbook proves the attachment in the spec.
- "Corrupt a bound source" is exercised at the store boundary (the pinned
  blocks), which is the authority every model read re-verifies; vault-byte
  corruption is caught at gate exit and at export by the existing checks and
  was not added to every readiness read (cost: hashing every source per read).

## Commands and results

| Gate | Command | Result |
| --- | --- | --- |
| Baseline backend (before changes) | `caos/server/.venv314/bin/python -m pytest caos/tests -q -p no:cacheprovider` | `1004 passed, 2 skipped, 1 warning in 857.67s` (the two skips are the PostgreSQL tests) |
| New spec (before the 27th test was added; all 27 pass inside the full run below) | `caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_source_complete_modelling_spec.py -q -p no:cacheprovider` | `26 passed, 1 warning in 118.42s` |
| Affected suites (model builder, Distressed overlay, ordinary Distressed e2e, research, loan universe, worker, HTTP contracts, deliverables, intake) | same interpreter, the nine files | model/Distressed/research/loan/worker/contracts `61 passed` after the two pinned tests were updated; deliverables + research `112 passed`; intake `30 passed` |
| Ruff | `caos/server/.venv314/bin/python -m ruff check --config ruff.toml caos/server caos/tests --exclude caos/server/caos/methodology/vendor` | `All checks passed!` |
| Route security audit | `caos/server/.venv314/bin/python run_sec_audit.py` | `{'audited_routes': 54, 'case_boundary_routes': 43, 'failures': 0}` |
| Quality ledger | `caos/server/.venv314/bin/python docs/quality_ledger_coverage.py` | `routes checked: 49   product files: 249   features: 122` — complete |
| Corpus host control, every startable route and depth, with lineage and model-effect assertions | `CORPUS_FULL=1 caos/server/.venv314/bin/python -m pytest caos/tests/test_corpus_pathways.py -q -p no:cacheprovider` | `34 passed, 1 warning in 209.63s` |
| Frontend lint / typecheck / unit / build | `npm run lint && npx tsc --noEmit && npm run test:unit && npm run build` (from `caos/frontend`) | exit 0; unit `tests 116, pass 116, fail 0`; `Compiled successfully`, 12 static pages |
| Workbench browser smoke | `CAOS_PROVIDER=host_control AGENT_EXECUTION_ENABLED=true caos/server/.venv314/bin/python caos/server/dev.py` on `:8000`, then `npm run test:workbench` | exit 0 (`caseRequests: 1`), on the rebuilt export |
| Accessibility sweep | a second host-control server on `:8766` with a fresh `CAOS_DATA_DIR`, then `CAOS_URL=http://127.0.0.1:8766 npm run a11y` | exit 0: `routes 9, viewports 6, combinations 70, violations 0` |
| Full backend suite (final code, corpus present) | `caos/server/.venv314/bin/python -m pytest caos/tests -q -p no:cacheprovider` | `1031 passed, 2 skipped, 1 warning in 1077.28s (0:17:57)` — the two skips are the PostgreSQL tests; 27 more than the baseline, all from the new spec |

Two gate findings worth recording:

- The accessibility sweep against the **populated** `:8000` server (after the
  smoke) reports `landmark-complementary-is-top-level` on `/sources/`
  (`.source-register`) and `/model-builder/`: those `<aside>` panels sit inside
  the shell's `<main>` and only render when a case with sources is selected.
  Task 8 ran the sweep against a fresh server on `:8766`, which is what this
  task repeats. On the fresh server the only failing node was the Model
  Builder cell-lineage panel, which the sweep exercises through its mocked
  ready-model fixture; `ModelBuilder.tsx` now renders it as a named
  `<section>` (a region landmark, allowed inside `main`) instead of an
  `<aside>`. The remaining nested asides on populated pages are a follow-up
  (Open items).
- The first affected-suite pass reported 109 setup errors in the intake and
  deliverables specs; they were caused by editing `store.py` while that run
  was in flight, and the re-runs quoted above are clean.

## Confidence review

Least confident about (ranked), each investigated in the code and, where a
bug was suspected, driven to a concrete failing case before any patch:

1. **A `duplicate` intake row waving a document out of the lineage.** A
   document admitted through the source route has no intake row; dropping
   the same bytes again yields only a `duplicate` row, and the first merge
   rule stored it, so `disposition != "used"` read as `NOT_REQUIRED` — a
   relevant document escaped the oracle. Constructed: manual upload of the
   annual, then the pack through intake. CONFIRMED; patched at the merge
   (a duplicate row lends its classification, the source stays `used`);
   regression `test_redropping_a_source_route_document_cannot_wave_it_out_of_the_lineage`.
2. **The base fingerprint moving after a later intake into the same case**
   (the lineage digest is in the fingerprint, so a later manifest row for a
   base source would orphan the base build). Investigated: `_apply_dispositions`
   supersedes within the pack only; `_apply_existing_sources` writes duplicate
   rows, which the merge now never lets override; withdrawn sources leave
   the live set and invalidate the snapshot first. Verified fine by
   `test_every_pathway_overlays_its_declared_effect_on_the_full_credit_model`
   (four later intakes into the base case; every overlay still resolves the
   base) and the corpus control (eleven later acceptances on one case).
3. **Evidence delivered but uncited.** `validate_citations` requires the
   cited set to equal the delivered set, so "used but not cited" cannot
   exist; the doubles model "unused" as "never requested". Verified by the
   first version of the lineage-oracle test failing at CP-PARSE with
   `AGENT_OUTPUT_INVALID` when it merely dropped a citation. By design;
   recorded in the anti-vacuity ledger.
4. **Host control reading every source against the read allowance.** Ten
   reads per module; a pack wider than that leaves tail sources unread and
   the model reads `MODEL_SOURCE_LINEAGE_INCOMPLETE` — the truthful outcome
   for an orchestration proof. Verified: `test_host_control_provider.py`,
   the injection and observability specs (45 passed), the workbench smoke
   and the sweep all green with the new read pattern.
5. **The covenant "update" not being adoptable.** The pinned engine refuses a
   preview that changes an assumption's status
   (`effective assumption metadata mismatch`), found when the first version
   of the overlay test tried to sign the proposed threshold. Root cause is
   the vendored contract, not a host defect; the effect now says
   `PROPOSED_REQUIRES_FULL_CREDIT_HANDOFF` for an UNAVAILABLE base slot and
   `PROPOSED_FOR_SIGN_OFF` only for a READY one. By design, recorded in §14.18.
6. **`_decimal_text` refusing non-numeric calculator values.** Only applied
   to `credit_metrics` `inputs`/`kpis` (parsed numbers or null) and covenant
   thresholds; a string there is refused as invalid input, never coerced.
   Verified against the calculator scripts (`_num`, `compute_kpis`).
7. **Model-facing tables citing a source outside their own `source_id`
   columns** (the first CP-1B answer key replaced the annual with the
   quarterly and the vendor validator refused). Fixed in the double by
   listing both ids in the `source_id` cell, which the validator accepts —
   host behaviour unchanged and correct.
8. **The `model.build_ready` actor.** The row is attributed to the actor who
   queued the build (`created_by`), because the worker has no human
   identity; the transition itself is bound by build, snapshot, run and
   payload digest. By design; worth a `system` actor if audit reviewers want
   the executor distinguished.
9. **Overlay builds becoming deliverable "application builds" for Relative
   Value and Deep Research** (`validated_publication_build` takes the latest
   READY build for pathways outside the prior-Full-Credit set). The overlay
   is the base model plus a declared effect, so publishing it is consistent;
   Earnings and Covenant keep `PRIOR_FULL_CREDIT_BASE`. By design; Task 10
   decides the rendering.
10. **The `<aside>` → `<section>` change in Model Builder.** CSS targets the
    module class, not the element; the sweep and smoke exercise the panel by
    id. Verified fine (both green).

Fixed: 1. Verified fine: 2, 4, 6, 7, 10. By design: 3, 5, 8, 9. Still open:
none in code; the external items below.

## Open items

- **BLOCKED EXTERNAL — licensed market marks for Relative Value.** The
  intake, lineage and time-alignment are built and proven against a
  synthetic CP-3-template workbook (`marks_workbook` in the spec); the
  corpus control asserts `RELATIVE_VALUE_MARKET_MARKS_REQUIRED` because the
  Carnival pack has none. Needed: the licensed C20 pack, its licence class,
  retained-byte pinning and an answer key (Task 11's manifest).
- **BLOCKED EXTERNAL — live-model qualification** of every pathway's model
  effect and of the lineage oracle against the qualified provider (Tasks 11
  and 13). Everything here is host control or an answer-keyed double.
- Deliverables for Earnings Update and Covenant & Refinancing bind the
  prior Full Credit base build, not the overlay carrying their effect;
  rendering `period_updates`, `forecast_variance`, `covenant_updates`,
  `refinancing_updates`, `market_marks` and the Deep Research declaration in
  published outputs is Task 10 (`CLAUDE.md` known gaps).
- Cross-intake restatement: a restated annual dropped into a case whose
  original came from an earlier intake is admitted as `used` without
  marking the original `superseded`; the model binds both by citation.
  Follow-up in `intake/service.py` (`CLAUDE.md` known gaps).
- Nested complementary landmarks on populated pages (`/sources/`
  `.source-register` and `.source-support`, the Model Builder assumptions
  and tornado panels, the analysis evidence rail) fail axe's
  `landmark-complementary-is-top-level` when a case with sources is selected;
  the sweep runs against a fresh server and does not reach them. Frontend
  follow-up: render them as named regions as the cell-lineage panel now is.
- `qa/scenarios.py` (not a gate) was aligned to the new
  `PRIOR_FULL_CREDIT_MODEL_REQUIRED` code; `qa/FINDINGS.md` still narrates
  the 2026-08-31 fix in its own words and was left as history.
