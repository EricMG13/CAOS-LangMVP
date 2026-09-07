# Analyst View Coverage Ledger

This ledger is documentation and test input for Analyst Workbench presentation
mapping. It is not an execution registry. `caos.modules.registry.MODULES` and
`compiled_route(pathway, depth)` remain the only runtime authorities.

## Pinned authority

- Execution branch: `codex/analyst-workbench-capabilities`
- Baseline commit: `31482a7912c9e58017c2784bf098a6868978cd01`
- Methodology build: `237bf4bc56b616b1c679a32c3733a2d9baf580b113758329320478e0226bae9d`
- Mapping target: `caos.module-presentation.v1`
- Inventory source: current `ModuleSpec.reference_files` plus the verified
  vendored schema bytes they name. Table prefixes remain exactly as pinned even
  when historical consolidation makes them differ from the current module ID.

Every listed table remains available as an accessible table. `V+T` permits a
developer-designed chart only when compatible finite numeric values express a
real comparison, trajectory, distribution or matrix; the equivalent table is
still required. `T` is deliberately table-only. `N+T` uses narrative plus
evidence/status matrices and is not deficient for having no chart. Missing or
incompatible inputs produce a typed unavailable view, never a fabricated value.

## Active route inventory

- Full Credit FULL: `CP-PARSE, CP-0, CP-1, CP-1A, CP-1B, CP-1D, CP-1C,
  CP-2, CP-2A, CP-2G, CP-2E, CP-2H, CP-3, CP-4, CP-4C, CP-5, CP-6`.
- Deep Research FULL adds its current `CP-DR` module to the common
  `CP-PARSE, CP-0` prefix.
- SCREEN routes also make `CP-L10` active. Its pinned nested profile schemas
  retain `TL10`, `TL20`, `TL23`, `TL30` and `TL40` identities under the one
  current registry module.
- The other five FULL routes are unchanged subsets of these current IDs. No
  legacy alias is presented as a separately executing module.

## Module coverage

All rows are scoped to the methodology build above. The “required fields” cell
is the minimum presentation-binding group; it does not narrow the pinned schema
or permit unlisted columns to be discarded.

| Current module | Pinned reference / table or section IDs | Required fields available to mapping | Analysis policy | Report binding |
| --- | --- | --- | --- | --- |
| `CP-PARSE` | `CP-PARSE_SCHEMA_REFERENCE.md`: `P1–P8` | run/objective/status; immutable roots and hashes; source identity/authority/entity/period/version; triage scores/decisions; parse method/fidelity/coverage/limitations; artifact hash/locator/lineage; active representation; batch/member/index/checksum/safe-path status | `N+T`: preparation status, fidelity and representation registers | Evidence / QA |
| `CP-0` | `CP-0_SCHEMA_REFERENCE.md`: `T1–T8` | objective/issuer/period/preparation validation; source quality/usability; hierarchy/presence/minimum; module demand/readiness; gaps/conflicts/severity/remediation; evidence locator; run/output/warning/consumer; exact recommended command handoff | `N+T`: readiness, evidence and gap registers | Evidence / QA and readiness |
| `CP-1` | `CP-1_SCHEMA_REFERENCE.md`: `T4.1–T4.19`, contextual `cp1.operating_kpi_schedule`, `cp1.cp_model_segment_allocation`, canonical sections 1–17 | source/entity/period/basis; normalization before/after/rationale; statement line item × periods; constructed-period status; metric/formula/input/value/status; KPI/trend; definition conflicts; gaps/readiness; model period/account IDs and values; segment revenue; EBITDA add-backs; debt facility terms; reconciliation values/tolerance/status; optional KPI `kpi_id/label, business_unit/category, display_priority, period_id, value, unit, value_type, status, source_id/locator`; conditional allocation `slot_id, slot_label, component_segment_ids` | `V+T` for financial, KPI, bridge, debt and reconciliation series; `T` for source, definition, gap and readiness registers | Financial performance; capital structure; Base/Downside model; evidence |
| `CP-1A` | `CP-1A_SCHEMA_REFERENCE.md`: `source_classification`, `transaction_summary`, `company_description`, `revenue_business_mix`, `ownership_register`, `operating_model`, `cp1a.cp_model_snapshot_fields`, `events_timeline`, `credit_translation`, `gaps_ledger`, `conflict_log`, `downstream_readiness` | each object remains present; snapshot fields are exactly `field_id, value, status, source_id, source_locator, as_of` for issuer, sector, country, shareholders, transaction summary and business description | `N+T`; `V+T` only for supported business-mix/operating series | Business / transaction; risks and catalysts |
| `CP-1B` | `CP-1B_SCHEMA_REFERENCE.md`: `T4.1–T4.15` | source classification; inherited definitions/formulas/conflicts; top-sheet label/value; financial lines × periods/change/note; KPI/change/trend/status; variance drivers/implication; actions/comparability/source; benchmark expected/actual/variance; conflicts; monitoring; gaps; comparator IDs/periods/basis/values/changes/status; validation/add-back tolerances; model readiness | `V+T` for performance, KPI, variance and comparator series; `T` for authority, conflicts, monitoring and readiness | Earnings Update; financial performance and earnings quality |
| `CP-1C` | `CP-1C_SCHEMA_REFERENCE.md`: `T4.1–T4.11`, `T4.D1` | peer selection/availability/quality; borrower-peer metric alignment and comparability; operating, cash-flow, credit, trading and transaction metrics with period/currency/status; statistics including N/quartiles/range; outliers; implied EV range; gaps; supplied candidate source/locator/decision | `V+T` for comparable metrics, distributions and implied ranges; `T` for universe, alignment and gaps | Relative value; peer / issuer comparison |
| `CP-1D` | `CP-1D_SCHEMA_REFERENCE.md`: `T1D.1–T1D.7` | add-back identity/amount/period/category/source; achievability and counterevidence; recurrence verdict; quality-adjusted EBITDA bridge; adjusted EBITDA/CFO/conversion/gap; leverage bases/delta; gaps/follow-up | `V+T` for EBITDA bridge, conversion and leverage sensitivity; `T` for evidence assessments and gaps | Earnings quality; risks / limitations |
| `CP-2` | `CP-2_SCHEMA_REFERENCE.md`: `T2.1`, `T2.7`, `T2.10–T2.12` | source identity/quality/period/use; financial dimension/assessment/rationale; ranked material driver/evidence/mechanic/implication/direction/confidence; business factor/downside path; trigger/threshold/impact/source | `N+T`: scorecard, materiality, issuer and monitoring matrices | Credit summary; risks / catalysts / monitoring |
| `CP-2A` | `CP-2A_SCHEMA_REFERENCE.md`, `CP-2B_SCHEMA_REFERENCE.md`: `T2B.1–T2B.9`, `T5.1–T5.7` | source register; business fact/mechanic/implication; fragility breakpoint/confidence; operating stress → cash/leverage/liquidity consequence; downside causal vector and PD/LGD/RV/monitoring consequence; sensitivity method/result/status; monitoring/handoff/gaps; event/date/category/probability/impact/priority/receiving module | `V+T` for downside sensitivity and probability/impact matrices; `N+T` for pathway, catalyst and handoff registers | Base/Downside model; risks / catalysts / monitoring |
| `CP-2G` | `CP-2G_ForwardCreditModel.schema.md`: `T2H.1–T2H.9` | source/upstream/period/status/locator; historical-to-base adjustment; driver/slot/case/period/value/unit/assumption/source/status; forward revenue/EBITDA/margin/CFO/capex/FCF; debt/cash/liquidity roll-forward; leverage/coverage/runway; shock/breakpoint/consequence; deleveraging targets/triggers; gaps/conflicts | `V+T` for forecast, liquidity, credit-metric and breakpoint series; `T` for authority, assumptions, handoff and gaps | Base/Downside model; liquidity / covenants; monitoring |
| `CP-2E` | `CP-2E_SCHEMA_REFERENCE.md`, `CP-2F_SCHEMA_REFERENCE.md`: `T2F.1–T2F.9`, `T2G.1–T2G.8` | debt/rate/currency/maturity/hedge; hedge notional/strike/coverage; floating exposure and +100 bps cash/FCF/liquidity result; FX mismatch, commodity/inflation and macro transmission; transition/social risks; materiality; KPI/SPT/ratchet terms; demand/access direction; evidence/confidence/gaps | `V+T` for rate, FX and quantified macro sensitivities; `N+T` for transition, social, access and gap registers | Liquidity; refinancing and macro risks |
| `CP-2H` | `CP-2H_RatingTransition.schema.md`, `CP-3D_MarketImpliedRisk.schema.md`: `T2R.1–T2R.10`, `T3E.1–T3E.10` | agency rating/outlook/date/source; applicable criteria; agency-to-CP metric adjustments; trigger direction/threshold/case-period value/headroom/status; modifiers/migration/divergence/instrument implications; market instrument/source/timestamp/freshness; price/yield/spread/duration; curve and comparator differences; implied-risk inputs/results; liquidity/technicals; fundamental-market alignment; repricing; monitoring/gaps | `V+T` for trigger, migration, curve, market, implied-risk and repricing comparisons; `T` for evidence/methodology/divergence/gaps | Rating and market risk; refinancing; relative value; monitoring |
| `CP-3` | `CP-3_SCHEMA_REFERENCE.md`, `CP-3A_SCHEMA_REFERENCE.md`, `CP-3B_SCHEMA_REFERENCE.md`: `T3.1`, `T3.3–T3.7`, `T3.9–T3.10`, `T3B.1–T3B.8`, `T3B.10–T3B.11`, `T3C.1–T3C.9` | issuer/security scoring and overrides; dated market levels/comps/seniority/compensation; fundamental/RV/structural matrix and ranking; instrument terms, structural position, legal overlay, recovery and preference; portfolio fit/sizing/risk-budget/concentration/liquidity/downside/monitoring; evidence/confidence/gaps | `V+T` for scores, market compensation, rankings, recovery and concentration/downside matrices; `T` for structural, preference, fit, monitoring and gap registers | Relative value; structure / seniority; compensation / ranking; trade gates |
| `CP-4` | `CP-4_SCHEMA_REFERENCE.md`, `CP-4B_SCHEMA_REFERENCE.md`, `CP-4D_SCHEMA_REFERENCE.md`, `CP-4A_SCHEMA_REFERENCE.md`: `T4.2–T4.3`, `T4.9–T4.13`, `T4D.1–T4D.8`, `T4F.1–T4F.6`, `T4C.2–T4C.9`, `T4C.11–T4C.12` | controlling documents/clauses/authority; covenant mechanics and PD/LGD/RV effects; norms/aggressiveness/red flags; entity/guarantee/collateral/priority/transfer/priming; intercreditor parties/rank/enforcement/turnover/recovery control; covenant formula/inputs/headroom; basket usage/capacity; leakage/add-back inflation/priorities; evidence/confidence/status/gaps | `V+T` only for supported headroom/capacity comparisons; otherwise `N+T` legal, structural and evidence matrices | Liquidity / covenants; legal structure; risks / monitoring |
| `CP-4C` | `CP-4C_RestructuringScenario.schema.md`, `CP-3C_SCHEMA_REFERENCE.md`: `T4E.1–T4E.10`, `T3D.1–T3D.11` | jurisdiction/distress gate; claim amount/security/priority; scenario valuation inputs; path/process/consent/new-money/treatment/milestones; waterfall allocation/residual; fulcrum range; recovery by class/value/timing; transfer/intercreditor risk; catalysts/gaps; maturity wall; liquidity/access; legal capacity/sponsor willingness/refinancing path/vulnerability; creditor exposure; scenario/monitoring | `V+T` for maturity, waterfall, fulcrum, recovery, exposure and scenario comparisons; `N+T` for process, legal, catalyst and gap registers | Distressed priority, liquidity, scenarios, recovery / fulcrum and process milestones |
| `CP-5` | `CP-5_SCHEMA_REFERENCE.md`: `T5B.1–T5B.8` | source identity/quality/use; ranked material drivers and originating modules; conclusion/evidence/citation/classification/confidence/trace status; statement/source path/file/page/module; calculation/assumption/formula/status; missing-citation severity/remediation; auditability assessment; gaps | `N+T`: traceability, lineage, finding and auditability registers | Evidence Register / QA |
| `CP-6` | `CP-6_SCHEMA_REFERENCE.md`, `CP-6A_SCHEMA_REFERENCE.md`: `T6A.4`, `T6A.6–T6A.7`, `T6A.11`, `T6E.4`, `T6E.6–T6E.7`, `T6E.11` | challenged claim/counterevidence/vector/mechanic/implication/falsifier; chair/CIO evidence weighting; disputed positions/resolution/evidence/implication; gaps/follow-up | `N+T`: challenge, evidence-weighting and resolution matrices; no decorative score chart | Optional IC-specific challenge content within risks / monitoring when present; never a report prerequisite |
| `CP-DR` | `CP-DR_DeepResearch.schema.md`: canonical `Audit Summary`, `Analysis`, `Evidence Trace`, `Source Registry`, `Gaps & Conflicts`, `QA Validation` sections | scope/subject/question/mode/approved-plan hash; coverage score/status/stop reason; findings, evidence/counterevidence, implications and unresolved questions retain source trace | `N+T`: research narrative, evidence and unresolved-question registers | Deep Research scope, findings, evidence / counterevidence, implications and unresolved questions |
| `CP-L10` | `CP-L10_SCHEMA_REFERENCE.md`, `CP-L20_SCHEMA_REFERENCE.md`, `CP-L23_SCHEMA_REFERENCE.md`, `CP-L30_SCHEMA_REFERENCE.md`, `CP-L40_SCHEMA_REFERENCE.md`: `TL10.1–TL10.4`, `TL20.1–TL20.4`, `TL23.1–TL23.4`, `TL30.1–TL30.4`, `TL40.1–TL40.4` | each profile preserves Source and Scope Gate (`subject_identity, source_ref, source_owner_module, as_of_or_period, scope_status, topics_supported, limitation`), Topic Allocation (`topic_id, topic_label, source_owner_modules, materiality, evidence_status, disposition, priority_rank, summary, source_refs, upgrade_module_ids`), Decision Screen (`screen_item, assessment, evidence, credit_transmission, screening_implication, confidence, source_refs`) and Gaps/Upgrade (`topic_id, trigger, missing_inputs, decision_impact, required_source, target_full_module_id, expected_owned_object, blocking_for_full_decision`) | `N+T`: four explicit screening tables for the selected profile; no FULL calculation or invented chart | Screening summary, implications and upgrade gaps for the selected pathway |

## Report section policy

Template v2 uses fixed developer-designed sections populated from the rows
above. Full Credit's default output title is **Credit Report**. IC-specific
CP-6 content may appear when present but is not a prerequisite. The six pathway
identities, CP-6 route membership, model selection, opinion Sign-Off, freeze,
source authority and independent filing controls do not change.

Stored v1 drafts, recovery copies, revisions, Frozen Deliverables and Filed
Deliverables dispatch through their recorded v1 template/renderer identities.
They are never reinterpreted by this ledger. Moving to v2 requires an explicit
new revision and renewed Sign-Off.
