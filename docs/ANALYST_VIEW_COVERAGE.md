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

## Exact presentation binding

All rows below are scoped to the pinned methodology build above. Column names
are transcribed from the current schema or its module output profile; a slash,
ellipsis or grouped phrase is retained when that is how the pinned schema names
the field. `none` is also exact: CP-PARSE and CP-0 currently require register
presence and governed content but declare no fixed columns. The ledger does not
tighten those schemas by inventing headers.

Analysis policies are `V+T` (a finite, compatible visualization may accompany
the complete table), `N+T` (narrative plus the complete evidence/status table),
and `T` (complete table only). A Report binding of `Analysis only` is the
explicit table-only presentation allowed by the brief. All other bindings name
the fixed template-v2 section that consumes the object.

### CP-PARSE

Reference: `CP-PARSE_SCHEMA_REFERENCE.md`. Its output profile declares
`columns: none` for every required P1–P8 register.

| Table / section ID | Required columns or governed content | Analysis policy | Report binding |
| --- | --- | --- | --- |
| `P1` Pipeline | `none`; run identity, objective, preparation status | `N+T` | Evidence / QA |
| `P2` Workspace Record | `none`; immutable source roots, managed workspace, original hashes | `T` | Analysis only |
| `P3` Input Sources | `none`; original identity, authority, entity, period, version links | `T` | Evidence / QA |
| `P4` Triage Register | `none`; scores, frozen decisions, rationale, overrides, profiles | `N+T` | Evidence / QA |
| `P5` Parse Jobs | `none`; methods, status, fidelity, coverage, limitations | `N+T` | Evidence / QA |
| `P6` Prepared Artifacts | `none`; artifact paths/hashes, locators, original lineage | `T` | Analysis only |
| `P7` Representation Catalog | `none`; one active content representation per retained logical source | `N+T` | Evidence / QA |
| `P8` Package Record | `none`; batches, members, indexes, checksums, safe-path validation | `T` | Evidence / QA |

### CP-0

Reference: `CP-0_SCHEMA_REFERENCE.md`. Its output profile declares
`columns: none` for every required T1–T8 register; T8's row contract below is
additionally explicit in the pinned method.

| Table / section ID | Required columns or governed content | Analysis policy | Report binding |
| --- | --- | --- | --- |
| `T1` Input Gate | `none`; objective, issuer, period, CP-PARSE lineage, validation status | `N+T` | Evidence / QA and readiness |
| `T2` Source Register | `none`; original authority, active-representation quality and usability | `T` | Evidence / QA |
| `T3` Source Hierarchy | `none`; source class, authority rule, presence, missing minimum | `N+T` | Evidence / QA |
| `T4` Content-to-Module Map | `none`; active representation, evidence demand, readiness effect | `T` | Evidence / QA and readiness |
| `T5` Gaps/Conflicts | `none`; gaps, conflicts, severity, affected modules, remediation | `N+T` | Risks / limitations |
| `T6` Evidence Trace | `none`; evidence ID, original source, active representation, locator | `T` | Evidence / QA |
| `T7` Master Index State | `none`; run, upstream preparation, outputs, warnings, consumers | `T` | Analysis only |
| `T8` Recommended Run Command Sheet | `sequence; module_id; candidate_command; exact_command; source_files_to_attach; upstream_handoff; readiness; why_now_or_blocker` | `T` | Readiness |

### CP-1

Reference: `CP-1_SCHEMA_REFERENCE.md`.

| Table / section ID | Required columns | Analysis policy | Report binding |
| --- | --- | --- | --- |
| `T4.1` Source Register | `File Name; Doc Type; Period; Currency; Unit; Perimeter; Basis; Tier; Use; Limits` | `T` | Evidence / QA |
| `T4.2` Entity Period Key | `Entity; Role; FY End; Currency; Unit; Perimeter; Basis; Periods` | `T` | Financial performance |
| `T4.3` Normalization Reg | `Description; Source; Type; Before; After; Rationale; Periods` | `N+T` | Financial performance |
| `T4.4` Income Statement | `Line Item; Period 1…N` | `V+T` | Financial performance |
| `T4.5` Cash Flow Statement | `Line Item; Period 1…N` | `V+T` | Financial performance |
| `T4.6` Balance Sheet | `Line Item; Period 1…N` | `V+T` | Financial performance |
| `T4.7` Normalized Financials | `Line Item; Statement Source; Period 1…N` | `V+T` | Financial performance |
| `T4.8` Constructed Period Reg | `Metric; Type; FY/Stubs; Value; Status; Sources; Limits` | `T` | Financial performance |
| `T4.9` Calculation Register | `Metric; Formula; Num/Den+Source; Period; Value; Status; Tier; Limits` | `T` | Evidence / QA |
| `T4.10` KPI Dashboard | `Category; Metric; Periods; Trend; Analyst Note` | `V+T` | Financial performance |
| `T4.11` Def Conflict Reg | `Metric; Canonical; Issuer; Source; Periods; Materiality; Downstream; Resolution` | `N+T` | Risks / limitations |
| `T4.12` Gaps & Warnings | `Description; Item; Periods; Downstream; Severity; Action` | `N+T` | Risks / limitations |
| `T4.13` Downstream Readiness | `Module; Status; Gaps; Actions` | `T` | Analysis only |
| `T4.14` Model Period Register | `period_id; FY/Q; type; dates; audit; currency; unit; basis; perimeter; source` | `T` | Base / Downside model |
| `T4.15` Model Account Register | `metric_id; period_id; value; sign; class; status; source; conflicts; limits` | `V+T` | Base / Downside model |
| `T4.16` Segment Revenue Schedule | `issuer-specific segment_id/name/type; priority; period_id; revenue; status; source` | `V+T` | Business / transaction and Base / Downside model |
| `T4.17` Adjusted EBITDA Bridge | `issuer-specific addback_id/label/classification/realization_status; priority; period_id; value; definition; source` | `V+T` | Earnings quality |
| `T4.18` Debt Facility Register | `facility_id; period_id; carrying value; principal; drawn; commitment; security; seniority; coupon; maturity` | `V+T` | Capital structure and liquidity / covenants |
| `T4.19` Model Reconciliation Register | `check_id; period_id; reported; calculated; difference; tolerance; status; explanation` | `T` | Evidence / QA |
| `cp1.operating_kpi_schedule` (contextual) | `kpi_id; kpi_label; business_unit; kpi_category; display_priority; period_id; value; unit; value_type; status; source_id; source_locator` | `V+T` | Financial performance and Base / Downside model |
| `cp1.cp_model_segment_allocation` (conditional) | `slot_id; slot_label; component_segment_ids` | `T` | Analysis only |
| canonical sections `1–17` | `Source Register; Entity Period Key; FS Coverage; Normalized IS; Normalized BS; Normalized CFS; Normalization Register; Calculation Register; Constructed Period Register; KPI Dashboard; Definition Conflict Register; Gaps & Warnings; Downstream Readiness; Evidence Trace; QA Status; Limitation Flags; Module Handoff` | `N+T` | Financial performance, Base / Downside model and Evidence / QA |

### CP-1A

Reference: `CP-1A_SCHEMA_REFERENCE.md`; exact register headers come from its
pinned module output profile. The absorbed T2D registers remain separately
required and are not aliases for the twelve CP-1A objects.

| Table / section ID | Required columns | Analysis policy | Report binding |
| --- | --- | --- | --- |
| `source_classification` | `Source ID; Source class; Quality; Use; Limitation` | `T` | Evidence / QA |
| `transaction_summary` | `Transaction; Status; Credit relevance; Source` | `N+T` | Business / transaction |
| `company_description` | `Issuer; Business description; Country; Sector` | `N+T` | Business / transaction |
| `revenue_business_mix` | `Business line; Revenue mix; Period; Status; Limitation` | `V+T` | Business / transaction |
| `ownership_register` | `Owner / class; Control; Economic interest; Credit relevance; Source` | `N+T` | Business / transaction |
| `operating_model` | `Operating driver; Measure; Period; Status; Credit relevance` | `V+T` | Business / transaction |
| `cp1a.cp_model_snapshot_fields` | `field_id; value; status; source_id; source_locator; as_of` | `T` | Base / Downside model |
| `events_timeline` | `Date / window; Event; Credit relevance; Status; Source` | `V+T` | Risks / catalysts / monitoring |
| `credit_translation` | `Evidence; Risk mechanic; Credit implication; Confidence; Limitation` | `N+T` | Credit summary and risks / catalysts |
| `gaps_ledger` | `Gap; Affected analysis; Severity; Action; Status` | `N+T` | Risks / limitations |
| `conflict_log` | `Conflict; Sources; Materiality; Resolution; Downstream impact` | `N+T` | Risks / limitations |
| `downstream_readiness` | `Module; Status; Gap; Required action` | `T` | Analysis only |
| `T2D.1` | `source_document_id; source_document_name; source_quality; period; entity_covered; data_supplied; limitation; downstream_use` | `T` | Evidence / QA |
| `T2D.2` | `Item; Source-Supported Fact; Evidence Quality; Source Trace; Credit Mechanic; Credit Implication; Limitation` | `N+T` | Business / transaction |
| `T2D.3` | `Governance Topic; Source-Supported Fact; Risk Direction; Risk Mechanic; Credit Implication; Evidence Quality; Source Trace; Limitation` | `N+T` | Risks / catalysts |
| `T2D.4` | `Flag ID; Behavior Type; Documented Action; Behavior Category; Amount / Funding Source; Legal-Capacity Link; Risk Mechanic; Credit Implication; Evidence Quality; Source Trace; Limitation` | `N+T` | Risks / catalysts |
| `T2D.5` | `Capital Allocation Item; Source-Supported Fact; Direction; Risk Mechanic; Credit Implication; Evidence Quality; Source Trace; Limitation` | `N+T` | Business / transaction and risks / catalysts |
| `T2D.6` | `Acquisition / Period; Source-Supported Fact; Funding Mix; EBITDA / Pro Forma Basis; Integration Evidence; Leverage / Liquidity Effect; Risk Mechanic; Credit Implication; Source Trace; Limitation` | `N+T` | Business / transaction and capital structure |
| `T2D.7` | `Disclosure Item; Available?; Source-Supported Detail; Credit Relevance; Severity; Source Trace; Required Follow-Up` | `T` | Evidence / QA |
| `T2D.8` | `Dimension; Assessment; Evidence; Risk Mechanic; Credit Implication; Score; Evidence Quality; Source Trace; Limitation` | `N+T` | Risks / catalysts |
| `T2D.9` | `Risk-Level Driver; Evidence; Risk Mechanic; Credit Implication; Evidence Quality; Source Trace; Countervailing Evidence; Limitation` | `N+T` | Risks / catalysts |
| `T2D.10` | `Downstream Module; Handoff Tag; Handoff Item; Why It Matters; Required Consumer Action; Source / Flag Link; Limitation` | `T` | Analysis only |
| `T2D.11` | `Gap ID; Missing Data; Why It Matters; Affected Section / Flag / Export Record; Consequence for Confidence; Required Follow-Up Source` | `N+T` | Risks / limitations |

### CP-1B

Reference: `CP-1B_SCHEMA_REFERENCE.md`.

| Table / section ID | Required columns | Analysis policy | Report binding |
| --- | --- | --- | --- |
| `T4.1` | `Source File Name; Document Type; Period Coverage; Evidence Quality Tier; Analytical Use; Limitations` | `T` | Evidence / QA |
| `T4.2` | `Metric Name; CP-1 Canonical Def; CP-1 Formula; EBITDA Def in Use; Inheritance Status; Conflict Note` | `T` | Earnings quality |
| `T4.3` | `Row Label; Value/Observation (13 rows)` | `N+T` | Earnings Update |
| `T4.4` | `Line Item; Period 1…N; YoY Abs/%; Analyst Note (19 lines)` | `V+T` | Earnings Update and financial performance |
| `T4.5` | `KPI Category; Metric; Period 1…N; YoY Change; Trend; Calc Status; Note` | `V+T` | Earnings Update and financial performance |
| `T4.6` | `Metric; Basis; Prior/Current; Abs/%; Mgmt/Analyst Driver; Credit Implication` | `V+T` | Earnings Update and earnings quality |
| `T4.7` | `Event; Date; Description; Impact; Comparability Effect; Credit Implication; Source` | `N+T` | Earnings Update and risks / catalysts |
| `T4.8` | `Metric; Benchmark Source/Type; Expected/Actual; Variance; Credit Implication` | `V+T` | Earnings Update and earnings quality |
| `T4.9` | `Conflict; Sources; Metrics; Periods; Materiality; Resolution; Downstream Impact` | `N+T` | Risks / limitations |
| `T4.10` | `Signal Type; Metric; Evidence; Severity; Credit Implication; Action` | `N+T` | Monitoring |
| `T4.11` | `Gap; Affected Metric; Periods; Downstream Impact; Severity; Action` | `N+T` | Risks / limitations |
| `T4.12` / `cp1b.model_comparator_register` | `metric_id; current/reference period IDs; basis; values; changes; status; comparability flags` | `V+T` | Base / Downside model |
| `T4.13` / `cp1b.model_validation_register` | `metric_id; period_id; CP-1 value; comparison value; difference; tolerance; status; explanation` | `T` | Evidence / QA |
| `T4.14` / `cp1b.addback_validation_register` | `addback_id; period_id; CP-1/comparison values; tolerance; status; label/definition checks` | `T` | Earnings quality and Evidence / QA |
| `T4.15` / `cp1b.model_readiness` | `downstream module; status; blocking metric/period IDs; conflicts; explanation` | `T` | Analysis only |
| `cp1b.cp_model_snapshot_fields` | `field_id; value; status; source_id; source_locator; as_of` | `T` | Base / Downside model |

### CP-1C and CP-1D

References: `CP-1C_SCHEMA_REFERENCE.md`, `CP-1D_SCHEMA_REFERENCE.md`.

| Module / table ID | Required columns | Analysis policy | Report binding |
| --- | --- | --- | --- |
| `CP-1C/T4.1` | `Entity Name; Peer Category Label; Source of Selection; Dimensions Assessed; Strengths; Limitations; Data Availability; Evidence Quality Tier; Usable For; Exclusion Reason` | `T` | Relative value |
| `CP-1C/T4.2` | `Metric; Borrower Value/Period; Peer Entity/Value/Period; AP1-AP11; Comparability Status; Limitation Notes` | `T` | Relative value |
| `CP-1C/T4.3` | `Entity; Revenue; Revenue Growth; Gross Margin; EBITDA; EBITDA Margin; EBIT Margin; Period; Currency; Calc Status; Comp Status` | `V+T` | Relative value |
| `CP-1C/T4.4` | `Entity; FCF; FCF Conversion; Capex/Revenue; Capex/EBITDA; WC/Revenue; Period; Currency; Calc Status; Comp Status` | `V+T` | Relative value |
| `CP-1C/T4.5` | `Entity; Total/Net/Sr Sec Leverage; Int/Adj Int Coverage; FFO/Debt; Liquidity; Period; Currency; Calc/Comp Status` | `V+T` | Relative value |
| `CP-1C/T4.6` | `Metric; Borrower Value; Peer Avg/Median/Min/Max; Q1/Q3; N; Borrower Position` | `V+T` | Relative value |
| `CP-1C/T4.7` | `Entity; Metric; Value; Peer Range; Deviation; Direction; 6 Implication Columns; Downstream Handoff` | `V+T` | Relative value and risks / catalysts |
| `CP-1C/T4.8` | `Entity; Mkt Cap; Date; EV; EV/Revenue; EV/EBITDA; Period; Metric Def; Comp Status; Source` | `V+T` | Relative value |
| `CP-1C/T4.9` | `Txn Name; Date; Type; Buyer/Seller; TV; TV/Revenue; TV/EBITDA; Period; Metric Def; Comp Status; Source` | `V+T` | Relative value |
| `CP-1C/T4.10` | `Method; Multiple Source/Value; Borrower Metric/Period; Implied EV/Low/Median/High; Calc Status; Limitations` | `V+T` | Relative value |
| `CP-1C/T4.11` | `Gap; Affected Metric/Section; Affected Peer(s); Downstream Impact; Severity; Action` | `N+T` | Risks / limitations |
| `CP-1C/T4.D1` (conditional) | `Candidate; Supplied Source File; Source Locator; Selection Basis; Dimensions Assessed; Inclusion Decision; Evidence Tag; Limitation` | `T` | Evidence / QA |
| `CP-1D/T1D.1` | `Add-Back ID; Description; Amount; Period; Category; Source / Locator; Management Rationale; Evidence ID` | `T` | Earnings quality |
| `CP-1D/T1D.2` | `Add-Back ID; Achievability Basis; Actions Taken To Date; Run-Rate Claimed; Realized To Date; Time To Realize; Evidence Quality; Countervailing Evidence; Assessment; Evidence ID` | `N+T` | Earnings quality |
| `CP-1D/T1D.3` | `Add-Back ID; Claimed Non-Recurring; Prior Occurrences (periods); Recurrence Pattern; Verdict; Risk Mechanic; Credit Implication; Evidence ID` | `N+T` | Earnings quality |
| `CP-1D/T1D.4` | `Step; Amount; Basis; Supported / Challenged / Rejected; Cumulative EBITDA; Evidence ID` | `V+T` | Earnings quality |
| `CP-1D/T1D.5` | `Period; Adjusted EBITDA; CFO; Conversion %; Gap; Explanation; Risk Mechanic; Credit Implication; Evidence ID` | `V+T` | Earnings quality |
| `CP-1D/T1D.6` | `Metric; On Reported EBITDA; On Adjusted EBITDA; On Quality-Adjusted EBITDA; Delta (turns); Credit Implication; Evidence ID` | `V+T` | Earnings quality and capital structure |
| `CP-1D/T1D.7` | `Gap; Missing Data; Why It Matters; Impact on Output; Required Follow-Up` | `N+T` | Risks / limitations |

### CP-2 and CP-2A

References: `CP-2_SCHEMA_REFERENCE.md`, `CP-2A_SCHEMA_REFERENCE.md`,
`CP-2B_SCHEMA_REFERENCE.md`.

| Module / table ID | Required columns | Analysis policy | Report binding |
| --- | --- | --- | --- |
| `CP-2/T2.1` | `source_document_id; source_document_name; source_quality; period; entity_covered; data_supplied; limitation; downstream_use` | `T` | Evidence / QA |
| `CP-2/T2.7` | `Dimension; Assessment; Credit Rationale` | `N+T` | Credit summary |
| `CP-2/T2.10` | `Rank; Driver; Evidence; Risk Mechanic; Credit Implication; Direction; Confidence` | `N+T` | Credit summary and risks / catalysts |
| `CP-2/T2.11` | `Business Quality Factor; Assessment; Primary Downside Path; Credit Relevance` | `N+T` | Credit summary and risks / catalysts |
| `CP-2/T2.12` | `Trigger; Threshold / Signal; Why It Matters; Credit Impact; Source / Limitation` | `N+T` | Monitoring |
| `CP-2/cp2.cp_model_strengths_weaknesses` | `direction; rank; label; mechanism; evidence_ids; status; source_id; source_locator; as_of` | `N+T` | Credit summary and Base / Downside model |
| `CP-2A/T2B.1` | `source_document_id; source_document_name; source_quality; period; entity_covered; data_supplied; limitation; downstream_use` | `T` | Evidence / QA |
| `CP-2A/T2B.2` | `Dimension; Source-Supported Fact; Risk Mechanic; Credit Implication; Source Trace; Limitation` | `N+T` | Base / Downside model |
| `CP-2A/T2B.3` | `Fragility Driver; First Break Point; Evidence; Risk Mechanic; Credit Implication; Confidence; Source Trace` | `N+T` | Risks / catalysts |
| `CP-2A/T2B.4` | `Operating Stress; Cash-Flow Impact; Leverage / Liquidity Result; Credit Consequence; Evidence Status; Source Trace` | `V+T` | Base / Downside model |
| `CP-2A/T2B.5` | `Pathway Row ID; Pathway Category; Driver; Causal Vector; PD/LGD/RV/Monitoring Consequence; Source Trace; Confidence; Downstream Module` | `N+T` | Base / Downside model and risks / catalysts |
| `CP-2A/T2B.6` | `Sensitivity; Input Basis; Formula / Method; Result; Credit Interpretation; Status; Source Trace` | `V+T` | Base / Downside model |
| `CP-2A/T2B.7` | `Trigger ID; Indicator; Leading / Lagging; Threshold or Qualitative Signal; Linked Pathway Row; Escalation Consequence; Source Trace; Limitation` | `N+T` | Monitoring |
| `CP-2A/T2B.8` | `Downstream Module; Handoff Item; Why It Matters; Required Consumer Action; Source / Pathway Link; Limitation` | `T` | Analysis only |
| `CP-2A/T2B.9` | `Gap ID; Missing Data; Why It Matters; Affected Pathway / Calculation / Trigger; Consequence for Confidence; Required Follow-Up Source` | `N+T` | Risks / limitations |
| `CP-2A/T5.1` | `Event ID; Source Document; Event Description; Event Category; Date/Range; Evidence Quality; Source Reliability` | `T` | Risks / catalysts |
| `CP-2A/T5.2` | `Date/Window; Event Description; Event Category; Credit Relevance Summary; Source` | `V+T` | Risks / catalysts |
| `CP-2A/T5.3` | `Event ID; Description; Probability; Credit Impact Channel(s); Impact Severity; Affected Metrics; Risk Direction; Source` | `N+T` | Risks / catalysts |
| `CP-2A/T5.4` | `Event ID; Description; Probability; Impact; P/I Classification` | `V+T` | Risks / catalysts |
| `CP-2A/T5.5` | `Event ID; Description; Priority; Monitoring Frequency; Trigger Condition; Responsible Module` | `T` | Monitoring |
| `CP-2A/T5.6` | `Event ID; Description; Priority; Receiving Module; Handoff Content; Timing; Rationale` | `T` | Monitoring |
| `CP-2A/T5.7` | `Gap Description; Affected Section; Downstream Impact; Severity; Recommended Action` | `N+T` | Risks / limitations |
| `CP-2A/cp2b.cp_model_catalysts` | `rank; event_date_or_window; event; credit_relevance; status; source_id; source_locator; as_of` | `V+T` | Risks / catalysts and Base / Downside model |

### CP-2E and CP-2G

References: `CP-2E_SCHEMA_REFERENCE.md`, `CP-2F_SCHEMA_REFERENCE.md`,
`CP-2G_ForwardCreditModel.schema.md`.

| Module / table ID | Required columns | Analysis policy | Report binding |
| --- | --- | --- | --- |
| `CP-2E/T2F.1` | `source_document_id; source_document_name; source_quality; period; entity_covered; data_supplied; limitation; downstream_use` | `T` | Evidence / QA |
| `CP-2E/T2F.2` | `Debt Instrument; Amount; Fixed / Floating; Base Rate; Margin / Coupon; Currency; Maturity; Hedge Status; Source Trace; Credit Implication` | `V+T` | Liquidity / refinancing |
| `CP-2E/T2F.3` | `Hedge Type; Notional; Instrument Covered; Rate / Strike; Maturity; Coverage Status; Source Trace; Limitation` | `V+T` | Liquidity / refinancing |
| `CP-2E/T2F.4` | `Metric; Amount; Formula / Source; Status; Credit Implication; Source Trace` | `V+T` | Liquidity / refinancing |
| `CP-2E/T2F.5` | `Sensitivity; Formula; Source Inputs; Estimated Cash Impact; FCF / Liquidity Implication; Status; Source Trace` | `V+T` | Liquidity / refinancing |
| `CP-2E/T2F.6` | `Exposure Type; Revenue Currency / Region; Cost Currency / Region; Debt / EBITDA / Cash / Covenant Currency; Natural Hedge?; Evidence; Risk Mechanic; Credit Implication; Source Trace; Limitation` | `V+T` | Risks / catalysts |
| `CP-2E/T2F.7` | `Input / Commodity / Inflation Driver; Cost Exposure; Pass-Through Mechanism; Evidence; Risk Mechanic; Credit Implication; Source Trace; Limitation` | `N+T` | Risks / catalysts |
| `CP-2E/T2F.8` | `Macro Driver; Evidence; Risk Mechanic; FCF / Liquidity Impact; Refinancing / RV Implication; Monitoring Trigger; Source Trace` | `N+T` | Risks / catalysts and monitoring |
| `CP-2E/T2F.9` | `Gap; Missing Data; Why It Matters; Impact on Output; Required Follow-Up; Downstream Module Affected` | `N+T` | Risks / limitations |
| `CP-2E/T2G.1` | `Source; Reliability (audited/assured vs self-reported); Greenwashing Flag; Module Status` | `T` | Evidence / QA |
| `CP-2E/T2G.2` | `Exposure; Source/Date; Transmission Mechanic; Affected Driver; Evidence ID` | `N+T` | Risks / catalysts |
| `CP-2E/T2G.3` | `Exposure; Source/Date; Transmission Mechanic; Event-Risk vs Ongoing; Evidence ID` | `N+T` | Risks / catalysts |
| `CP-2E/T2G.4` | `Factor; Materiality Class; Transmission Basis; Catalyst (if Watch); Evidence ID` | `N+T` | Risks / catalysts |
| `CP-2E/T2G.5` | `Instrument; KPI; SPT + Test Date; Ratchet (direction, bps); Symmetry; Credit-Meaningful?; Expected Spread Effect; Evidence ID` | `V+T` | Liquidity / refinancing and risks / catalysts |
| `CP-2E/T2G.6` | `Effect; Direction; Quantified vs Directional; Linked Maturity/Funding Need; Evidence ID` | `N+T` | Liquidity / refinancing |
| `CP-2E/T2G.7` | `Material Factor; Risk Mechanic; Credit Implication; Confidence; Evidence ID` | `N+T` | Risks / catalysts |
| `CP-2E/T2G.8` | `Gap; Missing Item; Why It Matters; Impact on Output; Required Follow-Up` | `N+T` | Risks / limitations |
| `CP-2E/Overall Credit Implication` (required section 9) | `highest-priority material factor; affected credit metric or decision dimension; Evidence → Risk Mechanic → Credit Implication path; direction and supported quantification; uncertainty; monitoring condition; single CP-6 debate handoff` | `N+T` | Risks / catalysts and monitoring |
| `CP-2G/T2H.1` | `source_id; upstream module/run/period; status; locator; limitation` | `T` | Evidence / QA |
| `CP-2G/T2H.2` | `metric; historical actual; LTM/base; adjustment; basis; evidence_id` | `V+T` | Base / Downside model |
| `CP-2G/T2H.3` / `cp2g.cp_model_forecast_drivers` | `driver_id; slot_id; case; period_id; fiscal_year; value; unit; assumption_id; status; source_id; source_locator; as_of; gap_code` | `T` | Base / Downside model |
| `CP-2G/T2H.4` | `period; case; revenue; EBITDA; margin; CFO; capex; FCF; evidence/assumption IDs` | `V+T` | Base / Downside model |
| `CP-2G/T2H.5` | `period; case; opening debt/cash; issuance; repayment; interest; closing debt/cash; accessible liquidity` | `V+T` | Base / Downside model and liquidity / refinancing |
| `CP-2G/T2H.6` | `period; case; gross/net leverage; coverage; FCF/debt; liquidity runway; definition IDs` | `V+T` | Base / Downside model and liquidity / refinancing |
| `CP-2G/T2H.7` | `driver shock; first break; period; liquidity/covenant/refinancing consequence; recovery action` | `V+T` | Base / Downside model and risks / catalysts |
| `CP-2G/T2H.8` | `case; trajectory; target/date; dependency; trigger; downstream module` | `V+T` | Base / Downside model and monitoring |
| `CP-2G/T2H.9` | `item; conflict/gap; affected case/period; model impact; required evidence` | `N+T` | Risks / limitations |

### CP-2H

References: `CP-2H_RatingTransition.schema.md`,
`CP-3D_MarketImpliedRisk.schema.md`.

| Table ID | Required columns | Analysis policy | Report binding |
| --- | --- | --- | --- |
| `T2R.1` | `agency; issuer/instrument; rating; outlook/watch; effective date; source; locator; status` | `T` | Rating and market risk |
| `T2R.2` | `agency; criteria; publication/effective date; applicable entity/instrument; limitation` | `T` | Rating and market risk |
| `T2R.3` | `agency metric; CP metric; adjustments; period/perimeter; formula; evidence_id` | `T` | Rating and market risk |
| `T2R.4` | `agency; rating type; trigger direction; metric; threshold; case/period value; headroom; status` | `V+T` | Rating and market risk |
| `T2R.5` | `agency; factor; current evidence; supportive/neutral/negative/unknown; rationale; locator` | `N+T` | Rating and market risk |
| `T2R.6` | `agency; case; transition class; earliest timing; catalyst; confidence; evidence/forecast IDs` | `V+T` | Rating and market risk and risks / catalysts |
| `T2R.7` | `issue; agency A/B positions; methodology/perimeter/timing explanation; unresolved conflict` | `N+T` | Risks / limitations |
| `T2R.8` | `instrument; issuer rating link; notching/recovery evidence; possible direction; limitation` | `N+T` | Rating and market risk |
| `T2R.9` | `nearest trigger; buffer; leading indicator; review date/event; downstream module` | `V+T` | Monitoring |
| `T2R.10` | `missing/stale item; affected agency/trigger; impact; required follow-up` | `N+T` | Risks / limitations |
| `T3E.1` | `security_id; issuer; currency; coupon; maturity/call; seniority; source; timestamp; quote_type; freshness` | `T` | Relative value |
| `T3E.2` | `security_id; bid/mid/ask or evaluated price; yield; spread/OAS/DM; duration; benchmark; observation ID` | `V+T` | Relative value |
| `T3E.3` | `security_id; maturity/call date; spread/yield; seniority; curve residual; explanation status` | `V+T` | Relative value |
| `T3E.4` | `comparator; alignment basis; spread/yield/price; period; difference; comparability limitation` | `V+T` | Relative value |
| `T3E.5` | `security_id; model; horizon; recovery; discount/benchmark; implied default/loss/break-even; formula ID; limitation` | `V+T` | Relative value and rating and market risk |
| `T3E.6` | `security_id; bid-ask; trade frequency/volume; issue size; ownership/flow/supply evidence; direction; confidence` | `V+T` | Relative value |
| `T3E.7` | `market implication; CP-2/2H/2R evidence; aligned/divergent; possible basis; unresolved question` | `N+T` | Relative value and rating and market risk |
| `T3E.8` | `scenario; driver; spread/yield/price assumption; calculated move; convexity/call limitation` | `V+T` | Relative value and risks / catalysts |
| `T3E.9` | `observable; threshold; cadence/event; downstream module; evidence source` | `T` | Monitoring |
| `T3E.10` | `missing/stale/conflicting item; affected calculation/security; impact; required evidence` | `N+T` | Risks / limitations |

### CP-3

References: `CP-3_SCHEMA_REFERENCE.md`, `CP-3A_SCHEMA_REFERENCE.md`,
`CP-3B_SCHEMA_REFERENCE.md`.

| Table ID | Required columns | Analysis policy | Report binding |
| --- | --- | --- | --- |
| `T3.1` | `source_document_id; source_document_name; source_quality; period; entity_covered; data_supplied; limitation; downstream_use` | `T` | Evidence / QA |
| `T3.3` | `Category; Factor; Weight; Raw Score 1–5; Weighted Score; Confidence; Evidence; Risk Mechanic; Credit Implication` | `V+T` | Relative value |
| `T3.4` | `Override Type; Trigger Evidence; Score Cap / Penalty; Revised Composite Score; Explanation` | `T` | Relative value |
| `T3.5` | `Security; Market Level; Market Date; Source; Quote Quality; Comps; Seniority / Security; Compensation vs. Risk; RV Label` | `V+T` | Relative value |
| `T3.6` | `Security / Issuer; Fundamental View; Relative-Value View; Structural / Recovery View; Final Matrix Bucket; Rationale` | `N+T` | Relative value |
| `T3.7` | `Rank; Issuer; Security / Tranche; Composite Score /100; Normalized /5.0; Credit Tier; Fundamental View; Relative Value View; Final Recommendation; Strongest Attribute; Weakest Attribute; Key Credit Issue; Monitoring Trigger` | `V+T` | Relative value |
| `T3.9` | `Trigger; Threshold / Signal; Why It Matters; Credit / RV Impact; Evidence ID` | `T` | Monitoring |
| `T3.10` | `Gap; Missing Data; Why It Matters; Impact on Output; Required Follow-Up` | `N+T` | Risks / limitations |
| `T3B.1` | `source_document_id; source_document_name; source_quality; period; entity_covered; data_supplied; limitation; downstream_use` | `T` | Evidence / QA |
| `T3B.2` | `Instrument; Type; Amount; Currency; Maturity; Seniority / Lien; Collateral; Guarantors; Coupon / Margin; Fixed / Floating; Source Trace` | `V+T` | Capital structure |
| `T3B.3` | `Instrument; Price; Spread / Yield / DM; Market Date; Source; Quote Quality; Call Schedule; Covenant Package; Liquidity; Source Trace` | `V+T` | Relative value |
| `T3B.4` | `Instrument; Structural Rank; Contractual Seniority; Lien Priority; Guarantee Coverage; Collateral Coverage; Structural Subordination; Priming Capacity; Key Risk Mechanic; Source Trace` | `N+T` | Legal structure and capital structure |
| `T3B.5` | `Instrument; Legal / Structural Finding; Priming Risk; Leakage Risk; Weak Collateral; Covenant Weakness; LME Vulnerability; Exposed Creditor Class; Source (CP-4 / CP-4A / CP-3C); Source Trace` | `N+T` | Legal structure and risks / catalysts |
| `T3B.6` | `Instrument; Recovery Sensitivity; Evidence; Risk Mechanic; Credit Implication; Confidence; Source Trace` | `V+T` | Relative value and recovery |
| `T3B.7` | `Instrument; Market Level; Market Date; Structural Rank; Recovery Sensitivity; Compensation Adequacy; Compensation vs. Risk; Source Trace` | `V+T` | Relative value |
| `T3B.8` | `Instrument; Preference; Structural Position; Recovery Sensitivity; Compensation Adequacy; Confidence; Key Reason; Monitoring Trigger; Source Trace` | `N+T` | Relative value |
| `T3B.10` | `Trigger; Instrument; Threshold / Signal; Why It Matters; Credit / Recovery Impact; Evidence ID` | `T` | Monitoring |
| `T3B.11` | `Gap; Missing Data; Why It Matters; Impact on Output; Required Follow-Up` | `N+T` | Risks / limitations |
| `T3C.1` | `Input; Available / Missing; Source; Limitation; Portfolio Impact` | `T` | Relative value |
| `T3C.2` | `Name / Instrument; Fit Category; Evidence; Risk Mechanic; Why It Fits / Does Not Fit; Constraints / Notes; Source Trace` | `N+T` | Relative value |
| `T3C.3` | `Name / Instrument; Sizing Posture; Evidence; Reason; Key Risk; Implementation Note; Confidence; Source Trace` | `N+T` | Relative value |
| `T3C.4` | `Flag; Evidence; Risk Mechanic; Why It Matters; Caution Level; Portfolio Impact; Source Trace` | `N+T` | Risks / catalysts |
| `T3C.5` | `Exposure Dimension; Current Exposure; Proposed / Pro Forma Exposure; Limit / Capacity; Evidence Status; Risk Mechanic; Portfolio Implication; Source Trace` | `V+T` | Relative value |
| `T3C.6` | `Liquidity / Implementation Factor; Evidence; Risk Mechanic; Implementation Consequence; Constraint / Action; Source Trace` | `N+T` | Relative value and liquidity / refinancing |
| `T3C.7` | `Downside Scenario / Driver; Input Basis; Formula / Method; Result / Directional View; Portfolio Loss / Risk-Budget Implication; Status; Source Trace` | `V+T` | Relative value and risks / catalysts |
| `T3C.8` | `Trigger ID; Indicator; Leading / Lagging; Threshold or Qualitative Signal; Linked Risk Flag; Portfolio Action; Source Trace; Limitation` | `T` | Monitoring |
| `T3C.9` | `Gap ID; Missing Data; Why It Matters; Affected Sizing / Risk Budget / Trigger; Consequence for Confidence; Required Follow-Up Source` | `N+T` | Risks / limitations |

### CP-4

References: `CP-4_SCHEMA_REFERENCE.md`, `CP-4B_SCHEMA_REFERENCE.md`,
`CP-4D_SCHEMA_REFERENCE.md`, `CP-4A_SCHEMA_REFERENCE.md`.

| Table / section ID | Required columns or format | Analysis policy | Report binding |
| --- | --- | --- | --- |
| `T4.2` | `Authority Rank; Document; Document Type; Version / Date; Status; Governing Role; Credit Relevance; Evidence ID` | `T` | Legal structure |
| `T4.3` | `Topic; Provision Summary; Source / Clause; Risk Mechanic; Credit Implication; Market Norm Assessment; Evidence ID` | `N+T` | Legal structure and risks / catalysts |
| `T4.9` | `Legal Topic; Supported Fact; Risk Mechanic; PD Effect; LGD / Recovery Effect; Monitoring Implication; Evidence ID` | `N+T` | Legal structure and recovery |
| `T4.10` | `Topic; Issuer Provision; Market / Third-Party Reference; Relative Assessment; Agreement / Discrepancy; Credit Implication; Evidence ID` | `N+T` | Legal structure |
| `T4.11` | `Area; Score 1–5; Evidence; Risk Mechanic; Credit Implication; Confidence; Evidence ID` | `T` | Legal structure |
| `T4.12` | `Red Flag / Trigger; Provision or Signal; Why It Matters; PD / LGD / RV Impact; Monitoring Action; Evidence ID` | `N+T` | Risks / catalysts and monitoring |
| `T4.13` | `Gap; Missing Document / Clause / Schedule; Why It Matters; Impact on Output; Required Follow-Up` | `N+T` | Risks / limitations |
| provision sections `4–8`: EBITDA, Definitions, and Ratio Mechanics; Debt Incurrence, Incremental Facilities, and MFN; Leakage, Restricted Payments, Investments, and Asset Transfers; Collateral, Guarantees, and Structural Subordination; Events of Default, Remedies, and Amendment Risk | `Standard Finding Format: Provision → Source → Summary → Risk Mechanic → PD Effect → LGD/Recovery Effect → Monitoring Implication → Credit Implication → Confidence → Evidence ID` | `N+T` | Legal structure and risks / catalysts |
| `T4D.1` | `Source; Status; Authority Rank; Limitations; Module Status` | `T` | Evidence / QA |
| `T4D.2` | `Entity; Role; Jurisdiction; Parent; Designation; Material Value Held; Inside Credit Group?; Evidence ID` | `N+T` | Legal structure |
| `T4D.3` | `Entity × Tranche; Guarantee Type; Direction; Release Trigger; Evidence ID` | `N+T` | Legal structure and capital structure |
| `T4D.4` | `Entity × Lien; Excluded Assets; Release Mechanic; Perfection Limit; Evidence ID` | `N+T` | Legal structure and capital structure |
| `T4D.5` | `Claim/Tranche; Obligor Entity; Reachable Value; Structural-Priority Label; Stranded Value Named; Recovery-Access Implication; Confidence; Evidence ID` | `N+T` | Legal structure and recovery |
| `T4D.6` | `Route; Entity Path; Enabling Provision (CP-4 ref); Value Exposed; Severity 1–5; Recovery/Priority Implication; Demonstrated vs Theoretical; Evidence ID` | `N+T` | Legal structure and recovery |
| `T4D.7` | `Vulnerability; Enabling Provision (CP-4 ref); Affected Creditor Class; Demonstrated vs Theoretical; Structural Implication; Confidence; Evidence ID` | `N+T` | Legal structure and recovery |
| `T4D.8` | `Gap; Missing Document/Schedule/Provision; Why It Matters; Impact on Output; Required Follow-Up` | `N+T` | Risks / limitations |
| `Overall Structural View` (required section 9) | `worst open route; handoff artifact for CP-3A; CP-6; CP-4A` | `N+T` | Legal structure and risks / catalysts |
| `T4F.1` | `Document; Parties; Date; Governing Law; Status; Source / Locator; Evidence ID` | `T` | Legal structure |
| `T4F.2` | `Creditor Class; Rank; Security Interest; Enforcement Rights; Voting Weight; Evidence ID` | `N+T` | Legal structure and recovery |
| `T4F.3` | `Provision; Standstill Period; Trigger; Who Controls Enforcement; Creditor Class Affected; Risk Mechanic; Credit Implication; Evidence ID` | `N+T` | Legal structure and recovery |
| `T4F.4` | `Provision; Turnover Obligation; Release Authority; Purchase Option; Conditions; Countervailing Evidence; Evidence ID` | `N+T` | Legal structure and recovery |
| `T4F.5` | `Creditor Class; Realised-Recovery Mechanic; Control Weakness; Severity; Risk Mechanic; Credit Implication; Evidence ID` | `N+T` | Legal structure and recovery |
| `T4F.6` | `Gap; Missing Data; Why It Matters; Impact on Output; Required Follow-Up` | `N+T` | Risks / limitations |
| `T4C.2` | `Authority Rank; Source; Source Type; Version / Date; Status; Controls Legal Formula / Financial Input / Usage; Credit Relevance; Evidence ID` | `T` | Legal structure and liquidity / covenants |
| `T4C.3` | `Definition / Ratio; Source / Clause; Formula / Definition Summary; Required Inputs; Capacity Effect; Risk Mechanic; Credit Implication; Evidence ID` | `N+T` | Liquidity / covenants |
| `T4C.4` | `Test; Test Type; Threshold; Current Basis; Formula; Headroom; Status; Limitation; Risk Mechanic; Credit Implication; Evidence ID` | `V+T` | Liquidity / covenants |
| `T4C.5` | `Capacity Type; Basket / Test; Formula; Conditions; Current Input; Usage; Estimated Capacity; Remaining Capacity; Status; Severity; Risk Mechanic; Credit Implication; Evidence ID` | `V+T` | Liquidity / covenants |
| `T4C.6` | `Route; Supported Legal Capacity; Current Calculation Status; Priming / Dilution Mechanic; PD Effect; LGD / Recovery Effect; RV / Security Selection Effect; Evidence ID` | `N+T` | Legal structure and liquidity / covenants |
| `T4C.7` | `Leakage Route; Supported Fact; Formula / Basket; Usage / Remaining Capacity; Restricted-Group / Collateral Impact; Severity; Credit Implication; Evidence ID` | `V+T` | Legal structure and liquidity / covenants |
| `T4C.8` | `Add-Back / Definition Feature; Source / Clause; Cap / Condition; Calculation Status; Capacity Inflation Mechanic; PD / LGD / RV Implication; Evidence ID` | `N+T` | Liquidity / covenants and earnings quality |
| `T4C.9` | `Flag; Supported Fact; Creditor Risk; Severity; Confidence; Downstream Module; Evidence ID` | `N+T` | Risks / catalysts |
| `T4C.11` | `Priority; Capacity Item; Severity; Confidence; Primary Risk Mechanic; PD Effect; LGD / Recovery Effect; Monitoring Action; Evidence ID` | `N+T` | Liquidity / covenants and monitoring |
| `T4C.12` | `Gap; Missing Data; Why It Matters; Impact on Output; Required Follow-Up` | `N+T` | Risks / limitations |
| `Capacity Source Gate` (required section 1) | `Gate status; input inventory` | `N+T` | Legal structure and liquidity / covenants |
| `Nearest Pressure Point` (required section 10) | `Single pressure point with 6 required fields: Pressure Point; Evidence; Risk Mechanic; Credit Implication; Monitoring Signal; Evidence Needed to Tighten View` | `N+T` | Liquidity / covenants and monitoring |
| `Overall Covenant Capacity View` (required section 13) | `Required formulation; 3–5 supported bullets; completion statement` | `N+T` | Liquidity / covenants and risks / catalysts |

### CP-4C

References: `CP-4C_RestructuringScenario.schema.md`,
`CP-3C_SCHEMA_REFERENCE.md`.

| Table ID | Required columns | Analysis policy | Report binding |
| --- | --- | --- | --- |
| `T4E.1` | `trigger; evidence/date; affected entity/instrument; jurisdiction; status; limitation` | `N+T` | Distressed scenarios |
| `T4E.2` | `class/claim ID; obligor; principal/accrued/PIK; currency; security/guarantee; priority; disputed/contingent; evidence` | `T` | Capital structure and recovery |
| `T4E.3` | `scenario; valuation date; metric/cash flow; multiple/discount; EV; source/judgment IDs; limitation` | `V+T` | Distressed scenarios and recovery |
| `T4E.4` | `path; process/jurisdiction; consent/vote; new money; class treatment; milestones; blockers; probability class` | `N+T` | Distressed scenarios |
| `T4E.5` | `scenario; entity; available value; priority claim; allocation; residual; legal evidence ID` | `V+T` | Recovery |
| `T4E.6` | `scenario/EV range; last covered class; first impaired class; fulcrum class/range; uncertainty` | `V+T` | Recovery |
| `T4E.7` | `scenario; class/instrument; allowed claim; cash/debt/equity/warrant value; total recovery; timing; currency` | `V+T` | Recovery |
| `T4E.8` | `mechanism; affected classes; required capacity/consent; evidence; possible outcome` | `N+T` | Legal structure and recovery |
| `T4E.9` | `event/milestone; earliest/latest timing; evidence; consequence; downstream module` | `V+T` | Distressed scenarios and monitoring |
| `T4E.10` | `claim/legal/value/process gap; affected scenario/class; impact; required evidence` | `N+T` | Risks / limitations |
| `T3D.1` | `source_document_id; source_document_name; source_quality; period / date; entity_covered; data_supplied; limitation; downstream_use` | `T` | Evidence / QA |
| `T3D.2` | `Instrument; Amount; Currency; Maturity Date; Years to Maturity; Seniority / Lien; Coupon / Margin; Fixed / Floating; Call Date; Refinancing Pressure; Credit Implication; Source Trace` | `V+T` | Liquidity / refinancing |
| `T3D.3` | `Factor; Evidence; Current Level / Status; Direction; Risk Mechanic; Credit Implication; Confidence; Source Trace` | `N+T` | Liquidity / refinancing |
| `T3D.4` | `Legal-Capacity Indicator; Available / Not Available / Unclear; Evidence; Risk Mechanic; LME Paths Enabled; Confidence; Source Trace` | `N+T` | Legal structure and distressed scenarios |
| `T3D.5` | `Factor; Evidence; Assessment; Risk Mechanic; Credit Implication; Source Trace` | `N+T` | Distressed scenarios |
| `T3D.6` | `Path Type; Feasibility; Likelihood Direction; Evidence Supporting; Evidence Against; Legal Capacity Required; Creditor Impact; Source Trace` | `N+T` | Distressed scenarios |
| `T3D.7` | `Dimension; Score; Evidence; Risk Mechanic; Credit Implication; Source Trace` | `T` | Distressed scenarios |
| `T3D.8` | `Creditor Class; Exposure: Base Case; Exposure: Stress Case; Exposure: LME Case; Recovery Implication; Priming / Subordination Risk; Source Trace` | `V+T` | Recovery |
| `T3D.9` | `Trigger; Indicator; Threshold / Qualitative Signal; Leading / Lagging; Why It Matters; Linked Path(s); Source Trace` | `T` | Monitoring |
| `T3D.10` | `Scenario; Key Assumptions; Refinancing Path; Timeline; Creditor Impact; Recovery Implication; Probability Direction; Confidence; Source Trace` | `V+T` | Distressed scenarios and recovery |
| `T3D.11` | `Gap; Missing Data; Why It Matters; Impact on Output; Required Follow-Up` | `N+T` | Risks / limitations |

### CP-5

Reference: `CP-5_SCHEMA_REFERENCE.md`.

| Table / section ID | Required columns or format | Analysis policy | Report binding |
| --- | --- | --- | --- |
| `T5B.1` | `Source Document ID; Source Document Name; Source Quality; Period; Entity Covered; Data Supplied; Limitation; Downstream Use` | `T` | Evidence / QA |
| `T5B.2` | `Rank; Credit Driver; Originating Module; Source-Supported Basis; Why Material; Committee Relevance; Source Trace; Limitation` | `N+T` | Credit summary and Evidence / QA |
| `T5B.3` | `Credit Driver / Conclusion; Originating Module; Source Evidence; Citation Present?; Source Quality; Classification; Claim Status; Confidence Level; Traceability Status` | `N+T` | Evidence / QA |
| `T5B.4` | `Statement; Source Path; Source File; Source Document ID; Page / Section; Module Section; Type; Source Quality; Notes` | `T` | Evidence / QA |
| `T5B.5` | `Item; Where Used; Source Inputs / Assumption; Formula or Logic; Status; Claim Status; Confidence Level; Credit Relevance; Source Trace` | `T` | Evidence / QA |
| `T5B.6` | `Severity; Conclusion; Issue; Classification; Why It Matters; Required Remediation; Affected Output / Export Record` | `N+T` | Evidence / QA and risks / limitations |
| `T5B.7` | `Auditability Dimension; Assessment; Evidence; Risk Mechanic; Credit Implication; Remediation Needed` | `N+T` | Evidence / QA |
| `T5B.8` | `Gap ID; Gap; Missing Evidence / Citation; Why It Matters; Impact on Output; Consequence for Confidence; Required Follow-Up Source` | `N+T` | Evidence / QA and risks / limitations |
| `Overall Traceability View` (required section 9) | `Required formulation: "Overall, evidence traceability is [Assessment]. Of the Top 5 material credit drivers, [N] are directly sourced, [N] are calculated, [N] are assumption-based, [N] are analyst inferences, and [N] are weak-lineage/untraced/conflicting/insufficient-information items. The most important provenance gap is [gap], which matters because [risk mechanic] and implies [committee-readiness impact]."` | `N+T` | Evidence / QA |

### CP-6

References: `CP-6_SCHEMA_REFERENCE.md`, `CP-6A_SCHEMA_REFERENCE.md`. Every
Report binding here is optional IC-specific content; no row is a report
prerequisite.

| Profile / table or section ID | Required columns or format | Analysis policy | Report binding |
| --- | --- | --- | --- |
| `CP-6/T6A.4` | `Bull Claim Attacked; Bear Counter-Evidence; Fragility Vector; Legal / Covenant Exploit; Risk Mechanic; Credit Implication; What Would Prove Bear Wrong` | `N+T` | Optional IC challenge |
| `CP-6/T6A.6` | `Dimension; Score (1-5); Bull Evidence; Bear Evidence; Chair Assessment` | `T` | Optional IC challenge |
| `CP-6/T6A.7` | `Disputed Risk; Bull Position; Bear Position; Resolution; Evidence Basis; Credit Implication` | `N+T` | Optional IC challenge |
| `CP-6/T6A.11` | `Gap ID; Gap; Why It Matters; Impact on Debate; Required Follow-Up` | `N+T` | Optional IC challenge |
| `CP-6/section 1` IC Debate Source Gate | `Gate status (Full Run / Ready with Limitations / Blocked); source register` | `N+T` | Optional IC challenge |
| `CP-6/section 2` Pre-Debate Thesis Map | `Narrative: 10-dimension evidence map; central investment controversy` | `N+T` | Optional IC challenge |
| `CP-6/section 3` Bull Analyst Opening Statement | `3 structured claims: Evidence; Risk Mechanic; Credit Implication; Monitoring Signal` | `N+T` | Optional IC challenge |
| `CP-6/section 5` Bull Analyst Defense | `Structured rebuttals per attack: rebuttal evidence; mitigation logic; Rebuttal Status` | `N+T` | Optional IC challenge |
| `CP-6/section 8` Action Bias Determination | `Required formulation: "Final Action Bias: [Bias]. The decision is driven by [evidence], because [mechanic], which implies [implication]. The main factor preventing a higher-conviction recommendation is [constraint]."` | `N+T` | Optional IC challenge |
| `CP-6/section 9` Single Greatest Uncertainty | `Structured: uncertainty; why it matters; evidence needed; positive/negative resolution impact` | `N+T` | Optional IC challenge |
| `CP-6/section 10` IC Chair Final Memo | `Narrative: Decision; winner; Bull/Bear evidence; legal/recovery; liquidity/refi; RV/portfolio; follow-up` | `N+T` | Optional IC challenge |
| `CP-6A/T6E.4` | `RV Bullet Attacked; Compliance Counter-Evidence; Constraint Vector; Risk Mechanic; Credit Implication; What Would Prove Compliance Wrong` | `N+T` | Optional IC challenge |
| `CP-6A/T6E.6` | `Dimension; Score (1-5); RV Evidence; Compliance Evidence; CIO Assessment` | `T` | Optional IC challenge |
| `CP-6A/T6E.7` | `Disputed Risk; RV Position; Compliance Position; Resolution; Evidence Basis; Credit / Portfolio Implication` | `N+T` | Optional IC challenge |
| `CP-6A/T6E.11` | `Gap ID; Gap; Why It Matters; Impact on Debate; Required Follow-Up` | `N+T` | Optional IC challenge |
| `CP-6A/section 1` Portfolio Debate Source Gate | `Gate status (Full Run / Ready with Limitations / Blocked); source register` | `N+T` | Optional IC challenge |
| `CP-6A/section 2` Pre-Debate Portfolio Thesis Map | `Narrative: evidence map; central portfolio controversy` | `N+T` | Optional IC challenge |
| `CP-6A/section 3` The RV Trader's Pitch | `3 structured bullets: Evidence; Risk Mechanic; Credit Implication; Monitoring Signal` | `N+T` | Optional IC challenge |
| `CP-6A/section 5` The RV Trader's Defense | `Structured rebuttals per attack: rebuttal evidence; mitigation logic; Rebuttal Status; proposed sizing constraint` | `N+T` | Optional IC challenge |
| `CP-6A/section 8` Final Sizing Posture | `Required formulation: "Final Sizing Posture: [Posture]. The decision is driven by [evidence], because [mechanic], which implies [implication]."`; canonical translation | `N+T` | Optional IC challenge |
| `CP-6A/section 9` Exact Portfolio Constraint | `Structured: constraint category; evidence; risk mechanic; credit/portfolio implication; evidence needed` | `N+T` | Optional IC challenge |
| `CP-6A/section 10` CIO Final Memo | `Narrative: Decision; winner; RV/Compliance evidence; legal/recovery; liquidity/refi; RV/portfolio; sizing constraint; follow-up` | `N+T` | Optional IC challenge |

### CP-DR

Reference: `CP-DR_DeepResearch.schema.md`. The pinned output profile declares
no required register IDs; its exact contract is the envelope extension plus
the six ordered canonical sections below.

| Table / section ID | Required fields or content | Analysis policy | Report binding |
| --- | --- | --- | --- |
| output-envelope extension | `scope_type; scope_key; subject_name; research_question; source_mode; approved_plan_hash; coverage_score; research_status; research_stop_reason` | `T` | Deep Research scope |
| `Audit Summary` | common CP fields plus output-envelope extension and confidence/QA status | `N+T` | Deep Research scope |
| `Analysis` | `approved scope; executive answer; perspective/workstream findings; causal synthesis; implications/scenarios; profile-specific tables` | `N+T` | Deep Research findings and implications |
| `Evidence Trace` | claim-to-source evidence and counterevidence with retrievable locators | `T` | Deep Research evidence / counterevidence |
| `Source Registry` | source identity, independence/origin, freshness and scope use | `T` | Deep Research evidence / counterevidence |
| `Gaps & Conflicts` | disagreements, unresolved questions, coverage gaps and required follow-up | `N+T` | Deep Research unresolved questions |
| `QA Validation` | plan-hash continuity, scope/source-mode/capability/coverage/independence/numeric/locator/freshness/injection/static-reference/parity checks | `T` | Evidence / QA |

### CP-L10 SCREEN profiles

References: `CP-L10_SCHEMA_REFERENCE.md`, `CP-L20_SCHEMA_REFERENCE.md`,
`CP-L23_SCHEMA_REFERENCE.md`, `CP-L30_SCHEMA_REFERENCE.md`,
`CP-L40_SCHEMA_REFERENCE.md`. The five profiles use the same four exact column
contracts; each ID below is a distinct required table for the selected profile.

| Table IDs | Required columns | Analysis policy | Report binding |
| --- | --- | --- | --- |
| `TL10.1`; `TL20.1`; `TL23.1`; `TL30.1`; `TL40.1` | `subject_identity; source_ref; source_owner_module; as_of_or_period; scope_status; topics_supported; limitation` | `N+T` | Screening summary |
| `TL10.2`; `TL20.2`; `TL23.2`; `TL30.2`; `TL40.2` | `topic_id; topic_label; source_owner_modules; materiality; evidence_status; disposition; priority_rank; summary; source_refs; upgrade_module_ids` | `N+T` | Screening summary and implications |
| `TL10.3`; `TL20.3`; `TL23.3`; `TL30.3`; `TL40.3` | `screen_item; assessment; evidence; credit_transmission; screening_implication; confidence; source_refs` | `N+T` | Screening implications |
| `TL10.4`; `TL20.4`; `TL23.4`; `TL30.4`; `TL40.4` | `topic_id; trigger; missing_inputs; decision_impact; required_source; target_full_module_id; expected_owned_object; blocking_for_full_decision` | `N+T` | Screening upgrade gaps |

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

## Implemented Report v2 section bindings (Task 7)

The matrix below is the exact implementation of `caos.deliverable-template.v2`
with `caos.module-presentation.v1`; the module tables above remain the full
Analysis inventory, and their Report column describes thematic applicability,
not additional implicit required inputs. `|` is ordered alias fallback, not
concatenation. Every listed binding is required once its section is included.
Missing inputs render `REPORT_INPUT_UNAVAILABLE` and block sign/freeze while
leaving an editable draft and raw accepted Analysis available. No new module
execution or provider synthesis occurs.

| Pathway | Fixed section ID / page | Exact source module / selector |
| --- | --- | --- |
| `FULL_CREDIT` | `credit_summary` · Credit summary | `CP-2` / `T2.7`; `CP-2` / `@Analysis` |
| `FULL_CREDIT` | `business` · Business / transaction | `CP-1A` / `transaction_summary or T2D.2 or cp1a.cp_model_snapshot_fields`; `CP-1A` / `@Analysis` |
| `FULL_CREDIT` | `financials` · Financial performance and earnings quality | `CP-1` / `cp1.model_account_register or T4.15`; `CP-1` / `cp1.adjusted_ebitda_bridge or T4.17` |
| `FULL_CREDIT` | `capital` · Capital structure | `CP-1` / `cp1.debt_facility_register or T4.18` |
| `FULL_CREDIT` | `model` · Base / Downside model | `MODEL` / `outputs` |
| `FULL_CREDIT` | `liquidity` · Liquidity / covenants | `CP-4` / `T4C.3`; `CP-4` / `T4C.4` |
| `FULL_CREDIT` | `relative_value` · Relative value | `CP-3` / `T3.5`; `CP-3` / `T3.7` |
| `FULL_CREDIT` | `risks` · Risks / catalysts / monitoring | `CP-2` / `T2.10`; `CP-2` / `T2.12` |
| `FULL_CREDIT` | `qa` · Evidence / QA | `CP-5` / `T5B.3`; `CP-5` / `T5B.6` |
| `EARNINGS_UPDATE` | `context` · Period / comparator context | `CP-1B` / `T4.3`; `CP-1B` / `@Audit Summary` |
| `EARNINGS_UPDATE` | `changes` · Reported-versus-prior changes | `CP-1B` / `T4.4`; `CP-1B` / `T4.12 or cp1b.model_comparator_register` |
| `EARNINGS_UPDATE` | `quality` · Earnings quality | `CP-1B` / `T4.6`; `CP-1B` / `T4.14 or cp1b.addback_validation_register` |
| `EARNINGS_UPDATE` | `model` · Accepted pathway model effects | `MODEL` / `outputs` |
| `EARNINGS_UPDATE` | `liquidity` · Leverage / liquidity | `CP-1B` / `cp1b.cp_model_snapshot_fields` |
| `EARNINGS_UPDATE` | `monitoring` · Implications and monitoring | `CP-1B` / `T4.10`; `CP-1B` / `T4.11` |
| `COVENANT_REFINANCING` | `debt` · Debt / maturity profile | `CP-3` / `T3D.2` |
| `COVENANT_REFINANCING` | `covenants` · Covenant definitions and headroom | `CP-4` / `T4C.3`; `CP-4` / `T4C.4` |
| `COVENANT_REFINANCING` | `liquidity` · Liquidity | `CP-3` / `T3D.3`; `CP-3` / `T3C.6` |
| `COVENANT_REFINANCING` | `refinancing` · Refinancing / restructuring findings | `CP-3` / `T3D.6`; `CP-3` / `@Analysis` |
| `COVENANT_REFINANCING` | `model` · Model effects | `MODEL` / `outputs` |
| `COVENANT_REFINANCING` | `actions` · Actions and evidence | `CP-4` / `T4C.11`; `CP-3` / `T3D.9` |
| `RELATIVE_VALUE` | `universe` · Pinned instrument universe | `CP-3` / `T3B.2`; `CP-3` / `@Audit Summary` |
| `RELATIVE_VALUE` | `comparison` · Peer / issuer comparison | `CP-3` / `T3.3`; `CP-3` / `T3.6` |
| `RELATIVE_VALUE` | `structure` · Structure / seniority | `CP-3` / `T3B.4` |
| `RELATIVE_VALUE` | `compensation` · Compensation / ranking | `CP-3` / `T3.5`; `CP-3` / `T3.7` |
| `RELATIVE_VALUE` | `gates` · Catalysts, freshness and trade gates | `CP-3` / `T3B.3`; `CP-3` / `T3.9`; `CP-3` / `T3C.6` |
| `DISTRESSED_RESTRUCTURING` | `priority` · Priority stack | `CP-4C` / `T4E.2` |
| `DISTRESSED_RESTRUCTURING` | `liquidity` · Liquidity runway | `CP-3` / `T3D.3` |
| `DISTRESSED_RESTRUCTURING` | `scenarios` · Scenario / breakpoint outputs | `CP-4C` / `T4E.3`; `MODEL` / `outputs` |
| `DISTRESSED_RESTRUCTURING` | `recovery` · Recovery / fulcrum | `CP-4C` / `T4E.5`; `CP-4C` / `T4E.6`; `CP-4C` / `T4E.7` |
| `DISTRESSED_RESTRUCTURING` | `milestones` · Legal / process milestones | `CP-4C` / `T4E.4`; `CP-4C` / `T4E.9` |
| `DISTRESSED_RESTRUCTURING` | `recommendations` · Recommendations and limitations | `CP-3` / `T3D.6`; `CP-4C` / `T4E.10` |
| `DEEP_RESEARCH` | `scope` · Research question / scope | `CP-DR` / `scope` |
| `DEEP_RESEARCH` | `findings` · Findings | `CP-DR` / `@Analysis` |
| `DEEP_RESEARCH` | `evidence` · Evidence and counterevidence | `CP-DR` / `@Evidence Trace`; `CP-DR` / `@Source Registry` |
| `DEEP_RESEARCH` | `implications` · Implications | `CP-DR` / `@Analysis/Implications` |
| `DEEP_RESEARCH` | `questions` · Unresolved questions | `CP-DR` / `@Gaps & Conflicts` |

`@` binds a canonical module Markdown H2, with tables retained separately in
Analysis and the selected structured exhibits. CP-DR Findings is its Analysis
body excluding exactly one visible H3 named `Implications` or `Implications and
scenarios` (case-insensitive). Implications binds that distinct H3 body; absent
or ambiguous headings are unavailable, never duplicated as a new conclusion.
The existing canonical scanner excludes fenced code/comments/raw content when
recognizing headings. CP-DR `scope` is the Task 5 scope projection. Narrative
origins reuse validated projection origins; unrepresentable long block IDs leave
unavailable sections, never widened historical document contracts.

Shared financial chart IDs: `cp1.revenue.v1`, `cp1.ebitda.v1`,
`cp1.cfo_ncfo.v1`, `cp1.adjustments.v1` on `financials`, and
`cp1.debt_maturity.v1` on `capital`; their tables/columns/unit rules remain the
Task 5 ledger bindings above. Other selected table exhibits reuse an existing
`<module>.<table-id>.v1` chart when declared and available. Shared model charts
consume only the validated selected model and its exact outputs, with the one
explicit currency/unit from the CP-1 period register where available. Missing
units and incompatible chart values remain visible typed chart warnings with
exact tables, not fabricated points. Task 9 owns actual PDF/XLSX chart drawing.

`MODEL / outputs` includes exact model outputs and accepted `pathway_effects`
calculation outputs. For Earnings and Covenant reports, an absent incremental
effect produces a publication blocker explicitly identifying the current prior
Full Credit base resolver limitation (Task 8). This report task does not claim
that reused base forecasts are recalculated incremental effects.

Declared optional section `ic_context` binds `CP-6 / @Analysis`, defaults omitted,
and records the reason: “IC module context is optional; this report is composed
directly from pathway modules.” Explicit inclusion with no accepted CP-6 is
unavailable; omission does not change any execution route. Analyst Narrative and
Limitations are separately labelled optional overlays, never generated facts.
The only required client block is the Evidence Register. Its exact citation
union with included module refs reaches both the visible register and frozen
`payload.evidence`, publication inventory, sign/freeze authority and offline audit.

V1 templates and frozen outputs retain their recorded interpretation. V2 content
records mapping version and declared inclusion IDs; omitted request IDs retain
the previous choice, while `[]` deliberately omits all declared optional sections.
Adopting v2 is an explicit new revision requiring renewed opinion sign-off.
