---
meta:
  contentType: Reference
  audience: Product, engineering, quality assurance, security, model risk, and credit analysts
---

# Validate CAOS for enterprise testing

This document defines the release gate for a controlled enterprise evaluation of CAOS. It replaces production readiness as the MVP target. The gate proves that complete supplied source packs can drive all six pathways, a source-grounded financial model, analyst-reviewed institutional deliverables, and complete machine auditability across every model the application permits.

## Document plan

- **Goal**: decide whether a build can enter enterprise testing
- **Audience**: product owners, engineers, quality assurance, security reviewers, model-risk reviewers, credit analysts, approvers, and enterprise test owners
- **Content plan**: define scope, qualification gates, test data, automated checks, adversarial simulations, human reviews, evidence, and exit criteria
- **Open questions**: which model catalog will be exposed, which enterprise identity provider will front the test environment, and which licensed real-issuer documents may enter the test corpus

`ENTERPRISE_READINESS_PLAN.md` orders the implementation work needed to satisfy this standard.

## Define enterprise-testing readiness

Enterprise-testing ready means CAOS can run inside a controlled enterprise test environment with enterprise identity, network, secrets, and monitoring controls. It does not mean the application is ready for unrestricted production use.

The MVP must satisfy this operating promise:

> Annual reports, quarterly/interim reports, forecasts, and every other relevant supplied source enter a controlled evidence room. A governed process dispositions and reconciles them, runs any of the six pathways, produces the source-grounded financial model and institutional deliverables, and presents the interpretation for review. A human analyst owns the opinion. A separate authorized approver publishes exact files plus an approval receipt for external stakeholders. Every machine-produced input, inclusion/exclusion decision, calculation, transformation, and output remains auditable.

Providing documents is the only required analytical input. Analyst review, opinion sign-off, and publish approval remain deliberate governance actions. The enterprise MVP exposes one qualified machine-generation binding and no LLM/provider picker. Signed financial-model selection, revisions, assumptions, scenarios, and sign-off remain governed analyst controls.

The following outcomes count as correct:

1. CAOS produces a fully validated result that an analyst can review
2. CAOS refuses with a typed, actionable reason because evidence, model capability, authority, or budget is insufficient

A partial, unsupported, unaudited, or silently degraded result never counts as success. “100%” means every accepted output satisfies the controls. It does not mean every document pack contains enough evidence for a credit conclusion. Each complete positive pack must succeed; a refusal is correct only for a pack whose answer key designates refusal and cannot substitute for proving a pathway works.

## Keep production operations outside the MVP gate

The enterprise-testing gate does not require:

- Multi-region or active-active deployment
- Horizontal application scaling
- A multi-worker LangGraph checkpoint implementation
- Formal uptime, recovery-time, or recovery-point service-level agreements
- Twenty-four-hour operations, on-call staffing, or customer support processes
- Automated production rollout, rollback, or tenant migration
- Production data retention schedules or regulatory certification
- Capacity beyond the declared enterprise test profile
- Direct email, portal, or data-room distribution to external stakeholders

The enterprise test may run one application instance and one background worker. The limitation must appear in the environment record. A test owner must not interpret a successful enterprise evaluation as a production approval.

Security properties that protect analytical integrity remain in scope. Enterprise perimeter controls do not replace case isolation, evidence validation, prompt-injection resistance, authorization, audit logs, exact approvals, or output integrity.

## Preserve the existing sources of truth

This standard adds release gates without duplicating existing tests:

- `TEST_INVENTORY.md` remains the exhaustive historical classification of 347 legacy tests
- `SPEC_RECONCILIATION.md` remains the mapping for 229 contractual rows and the ten engine invariants
- `docs/QUALITY_LEDGER.csv` remains the feature-to-test ledger
- `docs/QUALITY_DEFECTS.csv` remains the defect and regression-test record
- The vendored methodology schemas and validators remain the analytical output contracts

Every contractual row, invariant, and in-scope feature remains mandatory unless this document explicitly excludes it. An old `PASS` does not satisfy the gate. The release candidate must rerun the associated evidence on the candidate commit.

The institutional deliverable benchmark is Credit Operating System commit [`e566c1b`](https://github.com/EricMG13/Credit-Operating-System/tree/e566c1b78e0e7a35b2cd854b26f8d4f3e8a4f53a). It is a presentation/content reference only, not runtime or truth authority. Candidate outputs must match or exceed its decision-first hierarchy, committee readability, tabular financial precision, paper presentation, evidence visibility, and decision usefulness without copying seeded data, fixture conclusions, browser-owned authority, or unreadably small print.

## Resolve current readiness blockers

These items block an enterprise-testing-ready claim until evidence closes them:

| ID | Current condition | Required closure |
|---|---|---|
| ETR-B01 | Closed by Task 8 (2026-09-02): `POST /api/intake` creates or resolves the case, admits every document or none, classifies the evidence server-side, selects the route from host classification and starts the run; the Cases page drop zone is the entry surface and the run console opens the review. Live-model qualification of the journey remains open | Keep the six document-only route selections and the refusal, recovery, restart and reader checks retained in `spec/test_intake_spec.py` and the workbench smoke; qualify the journey against the qualified provider in Tasks 11 and 13 |
| ETR-B02 | Provider and model selection is environment-wide at process start, not a user-visible run choice | Either remove user model choice from the enterprise test or implement a pinned, allowlisted choice whose exact provider, model, version, and policy are recorded on the run |
| ETR-B03 | `z-ai/glm-5.3-flash` is documented in `openrouter.py` as unable to complete the full CP-1 contract | Remove it from selectable models or prove a corrected configuration passes the full qualification matrix |
| ETR-B04 | Run attempt metadata currently uses `settings.anthropic_model` even when the OpenRouter binding is active | Record the actual provider and model from the active provider on every attempt, artifact, event, and audit path |
| ETR-B05 | The real-issuer corpus ledger row is `WAIVED` | Run an approved real-issuer corpus or replace the waiver with an enterprise-approved, representative corpus and a signed equivalence rationale |
| ETR-B06 | The AI pull-request security review ledger row is `NOT RUN` | Activate it in a safe workflow or replace it with an equivalent recorded review that tests untrusted diff handling |
| ETR-B07 | Two-connection PostgreSQL race coverage remains deferred in `SPEC_RECONCILIATION.md` | Run the ingestion, assumption, model, acceptance, and publication races against two real database connections |
| ETR-B08 | `production-inventory.mjs` targets routes and seeded data that this build does not serve | Replace it as a release gate with an enterprise-test inventory generated from this build's OpenAPI and current UI destinations |
| ETR-B09 | OpenRouter reserves tokens from a local estimate | Prove the estimate never permits a configured budget overrun across every selectable OpenRouter model and maximum request shape |
| ETR-B10 | PostgreSQL domain data and SQLite checkpoints impose a single-instance ceiling | Record the ceiling, enforce one application instance in the test environment, and pass restart and corruption simulations under that topology |
| ETR-B11 | Distressed (Task 6) and Deep Research (Task 7) now execute through the ordinary provider path under host control — Deep Research with a governed brief and a digest-bound plan approval — but neither is live-model qualified | Pass the same run, corpus, model, publication, and audit matrix as every other pathway against the qualified provider; the Deep Research cell also needs the question-specific C22 pack |
| ETR-B12 | Closed by Task 9 (2026-09-02) under host control: every build carries a source-lineage record (intake disposition and reason, expected consumers, citing artifacts, model-facing tables, one binding per source), a `used` relevant document bound to nothing is the typed `MODEL_SOURCE_LINEAGE_INCOMPLETE` and never READY, and every pathway declares one model effect on the nearest validated Full Credit model (`docs/DECISIONS.md` §14.18). The metamorphic cases in `spec/test_source_complete_modelling_spec.py` and the six-route corpus control assert the answer-keyed changes. Live-model qualification of every effect remains open | Keep the lineage oracle, the metamorphic cases and the corpus lineage assertions retained; qualify every pathway's effect against the qualified provider in Tasks 11 and 13; the licensed market-marks pack for Relative Value is an external input |
| ETR-B13 | Current deliverables are materially below the approved institutional design benchmark | Pin the Credit Operating System reference and pass automated rendering checks plus independent side-by-side review for every pathway and published format |

## Apply release gates

The release candidate passes only when every gate below passes on the same commit and environment image:

| Gate | Required result |
|---|---|
| G0: Scope and traceability | Every in-scope requirement maps to at least one test and one retained result |
| G1: Deterministic automation | Unit, contract, integration, browser, accessibility, image, and static checks pass with no required skips |
| G2: Evidence integrity | Every accepted claim and number resolves to a pinned source or a declared deterministic calculation |
| G3: Model qualification | Every selectable provider and model passes every required route, evidence, security, and failure-mode test |
| G4: Analyst validation | Independent analysts accept the facts, reasoning boundaries, limitations, opinion controls, and external-stakeholder presentation |
| G5: Security | Application, API, upload, identity, authorization, dependency, secret, and artificial-intelligence security tests pass |
| G6: Resilience | Crash, retry, concurrency, withdrawal, corruption, and restart simulations preserve exact-once and fail-closed behavior |
| G7: Publishing | Only analyst-owned, approver-authorized, digest-bound files can be published or downloaded as filed outputs |
| G8: Audit reconstruction | An independent reviewer reconstructs sampled outputs from the retained audit package without application-team help |
| G9: Enterprise test deployment | The declared single-instance enterprise test profile boots, resets, isolates test data, and repeats the golden journey |

No core gate may use a waiver. A waiver may cover an explicitly excluded production operation only.

## Build the qualification corpus

The corpus must contain approved synthetic packs and approved real-issuer packs. Each pack needs a source manifest, expected facts, known conflicts, forbidden conclusions, route expectations, and an analyst-approved answer key. Every supplied file receives one governed disposition: `used`, `superseded`, `conflicting`, `out_of_scope`, or `insufficient`. Every `used` file must reach evidence or financial-model lineage; every other disposition requires a bounded reason.

| Pack | Required content and purpose |
|---|---|
| C01 | Complete audited annual financials, every relevant quarterly/interim statement, management and lender forecasts and revisions, debt schedule, covenant documents, presentation, and market marks |
| C02 | Sparse pack with material missing evidence and no support for a committee-ready conclusion |
| C03 | Two sources that disagree on debt, earnings, transaction value, or covenant definitions |
| C04 | Restated accounts and superseded prior-period documents |
| C05 | Multi-currency issuer with explicit foreign-exchange rates and missing rate cases |
| C06 | Finance-company or financing-subsidiary perimeter requiring industrial and finance debt separation |
| C07 | Textless scanned PDF, rotated pages, poor optical character recognition, tables, footnotes, and charts |
| C08 | Valid and invalid spreadsheets with hidden sheets, formulas, external links, macros, merged cells, blank cells, and extreme dimensions |
| C09 | Duplicate files, renamed duplicates, amendments, waivers, and an active source later withdrawn |
| C10 | Relative-value workbook with duplicates, identifier aliases, conflicting rows, dates, currencies, and blank optional cells |
| C11 | Covenant and refinancing pack with insufficient inputs for exact capacity calculation |
| C12 | Prompt-injection pack containing direct overrides, indirect instructions, tool requests, encoded payloads, fake system messages, and data-exfiltration requests |
| C13 | Boundary pack at every file-size, block-count, row, column, sheet, line-length, token, and output-size limit |
| C14 | Unicode pack with normalization variants, right-to-left controls, confusables, lone surrogates, control characters, and non-English issuer names |
| C15 | Malformed files, polyglots, archive bombs, traversal paths, duplicate archive members, corrupted packages, and malware-test signatures |
| C16 | Subsequent-event pack with post-period refinancing, disposal, dividend, acquisition, or earnings evidence |
| C17 | Real-issuer Full Credit pack with an independently authored benchmark conclusion |
| C18 | Real-issuer Earnings Update pack with prior accepted analysis and changed-period evidence |
| C19 | Real-issuer Covenant and Refinancing pack |
| C20 | Real-issuer Relative Value pack and normalized loan universe |
| C21 | Real-issuer Distressed pack with liquidity, claim hierarchy, restructuring alternatives, recovery answer keys, and an independently authored conclusion |
| C22 | Real-issuer Deep Research pack with a bounded research question, complete relevant evidence set, expected synthesis, and an independently authored conclusion |

Store corpus documents outside the test source tree when licensing requires it. Pin each retained byte digest in the test manifest. Never let a network fetch silently turn a required corpus test into a skip. C01 and C17–C22 are complete positive packs and must succeed; refusal is permitted only for a negative pack whose answer key explicitly requires it.

## Test the document-first experience

These tests prove that documents are the only required analytical input:

- **UX-001**: Drop one or more supported documents onto the entry surface and create or select the correct case without asking for analytical fields
- **UX-002**: Derive issuer, reporting period, document type, and candidate objective from evidence, then show the derivation and confidence for review
- **UX-003**: Default to the governed Full Credit route when no narrower objective is safely supported
- **UX-004**: Ask only a blocking clarification that cannot be answered from the supplied documents
- **UX-005**: Never ask the analyst to retype a number, table, source locator, or fact already present in evidence
- **UX-006**: Automatically inventory, scan, extract, deduplicate, version, and freeze the source set
- **UX-007**: Automatically compile and start the route after the source gate passes
- **UX-008**: Pause with one actionable missing-evidence message when the source gate fails
- **UX-009**: Resume automatically after the missing document arrives, without recreating the case or route
- **UX-010**: Open the completed analytical review when the run succeeds
- **UX-011**: Present facts, machine analysis, analyst edits, analyst opinion, limitations, and approval state as distinct content
- **UX-012**: Expose no LLM/provider picker in the enterprise MVP; preserve signed financial-model selection, scenario, revision, and sign-off controls
- **UX-013**: Preserve the same workflow and controls for every qualified model choice
- **UX-014**: Protect unsaved analyst edits during navigation, refresh, reconnect, and browser history changes
- **UX-015**: Let a reader inspect evidence and run history without exposing write controls
- **UX-016**: Let an analyst review and sign an opinion without exposing approver-only filing controls
- **UX-017**: Let an approver compare the exact frozen preview before filing
- **UX-018**: Complete the golden journey with keyboard-only operation
- **UX-019**: Complete the golden journey at desktop and supported narrow-screen widths
- **UX-020**: Surface typed failures without raw provider, database, secret, stack, or rejected-input content

## Test source intake and evidence preparation

These tests apply to PDF, XLSX, JSON, TXT, Markdown, and CSV sources where supported:

- **SRC-001**: Accept every declared supported type with valid evidence
- **SRC-002**: Reject an unsupported extension, media type, signature, or extension-content mismatch
- **SRC-003**: Reject zero-byte and evidence-free files before any source or source-set mutation
- **SRC-004**: Reject invalid UTF-8, duplicate JSON keys, non-finite JSON values, and over-range numbers
- **SRC-005**: Preserve finite zero, false, blank optional cells, signs, units, currencies, periods, entities, and definitions
- **SRC-006**: Accept a structurally valid textless PDF and record the lack of a text layer
- **SRC-007**: Reject malformed PDF structures and parser exceptions without partial state
- **SRC-008**: Reject active workbook content, external relationships, unsafe package parts, and formula execution
- **SRC-009**: Treat an uncached spreadsheet formula as null, not as a calculated value
- **SRC-010**: Exclude hidden sheets and columns when the contract requires visible evidence only
- **SRC-011**: Enforce row, column, sheet, line, source-byte, block-count, and total-text ceilings at exact boundaries
- **SRC-012**: Reject a source that would require truncation rather than ingesting a prefix
- **SRC-013**: Reject archive traversal, absolute paths, symlinks, duplicate members, decompression bombs, nested archive bombs, and excessive member counts
- **SRC-014**: Run malware scanning when configured and fail closed when the scanner is unavailable in the enterprise profile
- **SRC-015**: Keep source roots immutable and store derivatives in a controlled workspace
- **SRC-016**: Verify source bytes before and after preparation
- **SRC-017**: Preserve page, slide, sheet, row, cell, clause, and block locators through extraction
- **SRC-018**: Prove every prepared representation maps to one original source digest
- **SRC-019**: Enforce one active content representation per retained logical source
- **SRC-020**: Keep every base legal document, amendment, waiver, and supplement separately active and linked
- **SRC-021**: Collapse exact active duplicates without losing original names or locators
- **SRC-022**: Reject conflicting duplicates and identifier mappings with structured findings
- **SRC-023**: Reupload withdrawn bytes as a new source identity and a later source-set version
- **SRC-024**: Roll back source metadata, vault bytes, audit events, and source-set changes when any persistence step fails
- **SRC-025**: Re-hash vault bytes before every governed use and reject corruption
- **SRC-026**: Prevent one case from reading or importing another case's source
- **SRC-027**: Keep storage paths, scanner details, adapters, and internal metadata out of public responses
- **SRC-028**: Treat every document instruction, link, macro, prompt, and embedded command as inert evidence
- **SRC-029**: Normalize accepted pinned text to Unicode Normalization Form C after validation and within the stored length bound
- **SRC-030**: Reject control characters, lone surrogates, invalid byte strings, and bidirectional text that violates the display policy

## Test source sets, citations, and provenance

These tests prove that accepted analysis never separates from its exact evidence authority.

Before execution, classify every supplied source by document type, reporting/forecast period, revision/supersession status, relevance disposition, and downstream consumers. Reconcile annual, quarterly/interim, LTM, external forecast, analyst base, and analyst downside authorities without silently merging them.

- **EVD-001**: Create the source and source-set version in one atomic transaction
- **EVD-002**: Pin the exact source-set ID, version, member IDs, and member digests before analytical execution
- **EVD-003**: Keep a running analysis on its pinned set when later documents arrive
- **EVD-004**: Refuse acceptance when the historical pinned set cannot be resolved
- **EVD-005**: Reject withdrawn sources for every new note, assumption, model, report, citation, and run read
- **EVD-006**: Preserve historical accepted work while marking dependent current work stale after withdrawal
- **EVD-007**: Validate case, source-set membership, withdrawal state, source digest, and block identity on every `read_evidence` call
- **EVD-008**: Return no evidence text when any read check fails
- **EVD-009**: Prohibit listing, searching, or reading unpinned case evidence from the model tool surface
- **EVD-010**: Prohibit web, email, filesystem, shell, and arbitrary network evidence acquisition during a run
- **EVD-011**: Require every factual statement to cite at least one delivered evidence block or an approved deterministic result
- **EVD-012**: Require every numeric statement to retain value, unit, currency where relevant, period, entity, source, and locator
- **EVD-013**: Reject fabricated, duplicate, foreign-case, withdrawn, unreturned, or malformed citations
- **EVD-014**: Preserve all source figures for one conflicting event and log one explicit conflict
- **EVD-015**: Never treat null, unavailable, not calculable, or not disclosed as zero
- **EVD-016**: Flag subsequent events by date and keep them outside period figures
- **EVD-017**: Separate source authority from extraction confidence and prepared-representation fidelity
- **EVD-018**: Reconstruct each accepted citation from the stored source bytes and locator
- **EVD-019**: Produce the same evidence-read result after restart from the same pins
- **EVD-020**: Include source, relevance disposition, downstream consumer, block, caller module, run, attempt, time, result code, and returned-byte digest in the audit record

## Test route compilation and execution

Run these tests for Full Credit, Earnings Update, Covenant and Refinancing, Relative Value, Distressed, and Deep Research at screen and full depth:

Each of the twelve route/depth cells requires a complete answer-keyed success pack. Sparse, ambiguous, hostile, or over-limit refusal packs are additional tests and cannot replace a successful cell.

- **RUN-001**: Compile a static node set and edge set from only pathway, depth, verified catalog, and build
- **RUN-002**: Produce the same route and plan digest for identical inputs
- **RUN-003**: Reject unsupported pathways before pinning evidence or creating work
- **RUN-004**: Start every route with the governed source-readiness stage
- **RUN-005**: Prevent document content, model output, or intermediate data from adding, removing, or reordering route nodes
- **RUN-006**: Create the run, nodes, initial events, budget, plan, and pointers atomically
- **RUN-007**: Pause an evidence-free run before any analytical module executes
- **RUN-008**: Bind every node to run, case, profile, route occurrence, source set, plan digest, methodology build, provider, and model
- **RUN-009**: Reject a module invocation whose route occurrence or upstream digest does not reproduce
- **RUN-010**: Execute each dependency before its consumer and reject missing blocking inputs
- **RUN-011**: Keep optional or limited upstream states explicit in the output
- **RUN-012**: Reuse an existing valid fingerprint with zero provider calls and byte-identical artifact linkage
- **RUN-013**: Reject a reused artifact whose bytes, identity, schema, citations, or lineage no longer validate
- **RUN-014**: Resume from the last durable checkpoint after process restart
- **RUN-015**: Never restart completed nodes during resume
- **RUN-016**: Emit exactly one terminal run state and one terminal event
- **RUN-017**: Keep event IDs ordered, durable, resumable, and case-scoped
- **RUN-018**: Return missed Server-Sent Events from `Last-Event-ID` without duplication
- **RUN-019**: Exclude human gate wait time from active execution budget
- **RUN-020**: Charge failed model, evidence, validation, repair, and finalization work to the correct budget
- **RUN-021**: Reserve budget before every provider call and refuse before overspend
- **RUN-022**: Fail a resumed run with unresolved in-flight provider spend rather than spending twice
- **RUN-023**: Enforce active-job, stream, preview, tool-call, retry, repair, token, artifact, and active-time ceilings
- **RUN-024**: Upgrade a screen result by creating a linked new full run after validated output and explicit confirmation
- **RUN-025**: Never mutate the profile or history of the source screen run during upgrade
- **RUN-026**: Accept only a succeeded, fully revalidated run
- **RUN-027**: Atomically create the immutable snapshot and update the accepted pointer
- **RUN-028**: Make repeated acceptance idempotent
- **RUN-029**: Show snapshot drift and require an explicit switch to a newer accepted snapshot
- **RUN-030**: Produce identical host-validated screen identity for identical pinned inputs and build: the plan digest, source pins, calculation records (canonical input and output digests), and the canonical envelope are byte-equal across replays; provider prose is compared by validated canonical contract, as AUD-019 requires (`docs/DECISIONS.md` §14.3, §14.12)

## Qualify every provider and model

Let `Q` contain every provider, model identifier, model version, context policy, and parameter set exposed in the enterprise test. Execute the complete matrix `Q × six pathways × two depths × required corpus packs`.

- **MOD-001**: Hide every model that lacks a current qualification result for the candidate build
- **MOD-002**: Pin the exact provider, model ID, provider-reported version when available, parameters, and adapter version at run start
- **MOD-003**: Record the active provider and model, never a default from another adapter
- **MOD-004**: Run three cold repetitions for every agent-backed matrix cell
- **MOD-005**: Require every repetition to pass schema, evidence, citation, budget, security, and audit gates
- **MOD-006**: Compare model conclusions to the pack's permitted and forbidden conclusions
- **MOD-007**: Require 100% citation resolution and 0 unsupported material claims in accepted output
- **MOD-008**: Require 100% traceability for numbers, units, currencies, periods, and definitions
- **MOD-009**: Require all methodology registers, headings, frontmatter, and bounded fields
- **MOD-010**: Require explicit gaps when evidence is missing or conflicted
- **MOD-011**: Require the strongest supported counterargument and the condition under which it wins
- **MOD-012**: Require downside reasoning to identify cause, first break, transmission, consequence, and observable trigger
- **MOD-013**: Prevent a model from changing host-owned identity, quality status, confidence inputs, or authority fields
- **MOD-014**: Prevent a model from invoking undeclared tools or tool arguments
- **MOD-015**: Reject mixed text and tool output where the provider contract permits only one action
- **MOD-016**: Reject truncated, duplicate-key, non-finite, oversized, extra-field, or malformed final output
- **MOD-017**: Permit one bounded repair only where the contract allows it and disable evidence tools during repair
- **MOD-018**: Preserve assistant and tool-result ordering across a provider continuation
- **MOD-019**: Map timeouts, connection errors, rate limits, policy refusals, authentication failures, malformed usage, and unknown stop reasons to typed outcomes
- **MOD-020**: Keep provider error bodies, prompts, keys, headers, and secrets out of durable events and client responses
- **MOD-021**: Prove estimated OpenRouter reservations remain conservative at minimum, typical, and maximum request shapes
- **MOD-022**: Reject a model that cannot complete any required full-depth module
- **MOD-023**: Revoke qualification after model, adapter, methodology, system prompt, schema, or policy change
- **MOD-024**: Make model qualification expire on a declared review date even when the model name has not changed
- **MOD-025**: Publish the qualified-model catalog and its evidence to test owners

Passing host controls is mandatory but not sufficient. Independent analysts must also accept the analytical usefulness of every model in `Q`. Average quality cannot hide a failing route or pack.

## Test analytical interpretation and opinion ownership

These tests prove that CAOS supports analyst judgment without presenting machine prose as a human opinion.

- **ANA-001**: Separate documentary fact, management language, machine interpretation, credit implication, gap, and analyst opinion
- **ANA-002**: Attach a source and locator to every documentary fact
- **ANA-003**: Label management language and prevent it from becoming an unqualified fact
- **ANA-004**: Express material conclusions as evidence, risk mechanic, and creditor implication
- **ANA-005**: Preserve source, definition, perimeter, period, and module disagreements
- **ANA-006**: Prevent silent normalization or reconciliation
- **ANA-007**: Label every normalization as analyst judgment and show source and normalized values
- **ANA-008**: Keep legal capacity separate from observed willingness and current financial feasibility
- **ANA-009**: Prevent exact covenant-capacity claims when required legal inputs are absent
- **ANA-010**: Separate industrial and finance-company cash, debt, cash flow, liquidity, and leverage
- **ANA-011**: Keep matched-funding debt outside industrial leverage when the approved perimeter requires it
- **ANA-012**: Treat non-debt funding float under its governed definition and never substitute ordinary payables
- **ANA-013**: Test calculations against independently computed answer keys at exact rounding boundaries
- **ANA-014**: Test materiality and confidence changes when evidence is removed, conflicted, downgraded, or withdrawn
- **ANA-015**: Prevent missing evidence from creating an adverse fact or invented filler
- **ANA-016**: Show what changed between prior and current accepted analyses
- **ANA-017**: Keep an analyst's edits, comments, assumptions, and sign-off distinct from machine-authored content
- **ANA-018**: Require an analyst sign-off note that states the opinion, limitations, material overrides, and rationale
- **ANA-019**: Prevent machine content from being presented as the analyst's opinion before sign-off
- **ANA-020**: Retain every superseded analyst opinion and its exact supporting snapshot

## Test deterministic models and scenarios

These tests prove that financial outputs come from validated inputs and reproducible calculations.

The source-completeness oracle must also run metamorphic cases: remove or change one required annual, quarterly/interim, and forecast source in turn; add an irrelevant source; add a restatement/conflict; and withdraw or corrupt a bound source. The corresponding input, artifact, model fingerprint, result, limitation/refusal, and audit lineage must change exactly as the answer key specifies.

- **CALC-001**: Validate every CP-MODEL input table, identity, status, unit, period, definition, source, and relevance-manifest membership before calculation, including all relevant supplied annual, quarterly/interim, forecast, and forecast-revision documents
- **CALC-002**: Refuse a build when any unconditional stable table is absent
- **CALC-003**: Preserve unavailable optional assumptions as null with a named gap
- **CALC-004**: Reject NaN, infinity, invalid decimal text, zero denominators, and out-of-bound assumptions
- **CALC-005**: Derive quarter, year-to-date, full-year, last-twelve-month, pro-forma, base, and downside periods from the governed formulas
- **CALC-006**: Never overwrite a directly reported period with a derived period
- **CALC-007**: Produce identical calculation outputs from identical canonical inputs
- **CALC-008**: Match every workbook formula result to the Python calculation engine
- **CALC-009**: Account for every workbook formula and reject unrecognized or unrecalculated cells
- **CALC-010**: Record first covenant, liquidity, leverage, or coverage breach consistently
- **CALC-011**: Keep scenario, sensitivity, preview, and rebase results transient until analyst sign-off
- **CALC-012**: Apply hard bounds at one value below, at, and one value above each boundary
- **CALC-013**: Bind a preview to build, registry digest, assumption values, draft generation, and output digest
- **CALC-014**: Reject sign-off of a stale preview, stale build, stale source set, changed registry, or changed assumptions
- **CALC-015**: Commit a signed model revision and its audit event atomically using compare-and-swap
- **CALC-016**: Preserve immutable revision history and mark superseded revisions without altering bytes
- **CALC-017**: Rebase only compatible assumptions and require review of changed or invalidated assumptions
- **CALC-018**: Export the exact signed revision and verify its digest before download
- **CALC-019**: Make concurrent build, preview, sign-off, and export requests idempotent or explicitly conflicting
- **CALC-020**: Reproduce a signed model from retained inputs, engine version, and assumption registry

## Test report authoring and external publishing

These tests prove that external files contain reviewed content and match the exact approved bytes.

Every pathway must publish a decision-first report, its relevant model appendix/workbook, and an Evidence & QA Control Sheet from one server-frozen typed payload. Browser, Markdown, PDF, and XLSX must preserve the same reviewed facts, numbers, units, citations, origin labels, limitations, model identity, and analyst opinion. The pinned benchmark is a minimum qualitative bar, not a pixel-copy target.

- **PUB-001**: Create a report draft from the accepted snapshot, approved template, and selected qualified model authority
- **PUB-002**: Generate only template-declared machine blocks
- **PUB-003**: Validate every generated table and citation before it enters the draft
- **PUB-004**: Keep analyst-authored opinion blocks distinct from generated fact and analysis blocks
- **PUB-005**: Require analyst ownership of the external opinion and material overrides
- **PUB-006**: Save drafts as append-only revisions using expected-version compare-and-swap
- **PUB-007**: Reject stale saves without appending partial content or audit events
- **PUB-008**: Preserve revision history after source withdrawal, model supersession, and later edits
- **PUB-009**: Mark a draft stale when its accepted snapshot, source set, model revision, template, or methodology authority changes
- **PUB-010**: Require the analyst to resolve or acknowledge every material stale dependency before freeze
- **PUB-011**: Freeze the exact draft version, content digest, template, snapshot, model authority, and cited evidence set
- **PUB-012**: Render Markdown, Portable Document Format, and spreadsheet files deterministically where the template supports them
- **PUB-013**: Verify rendered bytes and digest before recording a successful freeze
- **PUB-014**: Prevent rendering failure from creating a frozen or filed record
- **PUB-015**: Sanitize filenames and document metadata
- **PUB-016**: Prevent spreadsheet-formula injection in exported text cells
- **PUB-017**: Prevent HTML, script, active-link, or Markdown injection in browser previews and exported files
- **PUB-018**: Inspect every page and sheet for clipping, overlap, missing glyphs, unreadable tables, broken page breaks, stale values, weak hierarchy, misaligned numerics, excessive density, and material inferiority to the pinned Credit Operating System benchmark
- **PUB-019**: Require an approver with current case standing who is independent of the analyst/opinion signer and freeze actor, and prove the approver can be provisioned without direct database seeding
- **PUB-020**: Bind approval to the exact preview digest and approval fingerprint
- **PUB-021**: Reject approval after any byte, dependency, standing, or source-status change
- **PUB-022**: Emit one filed record and one filing audit event under concurrent approval attempts
- **PUB-023**: Download only the exact filed bytes and verify the digest again at read time
- **PUB-024**: Exclude internal prompts, provider traces, secrets, draft comments, hidden controls, and non-publishable notes from external files
- **PUB-025**: Include required source, limitation, machine-assistance, analyst-opinion, approval-state, date, version, and digest disclosures; keep the post-freeze approver identity in an immutable detached filing receipt unless an intended approver was prebound
- **PUB-026**: Prove an external reader can distinguish sourced facts, analyst opinion, assumptions, and limitations
- **PUB-027**: Request changes without mutating the frozen artifact
- **PUB-028**: Preserve prior filed versions after a later revision or refiling
- **PUB-029**: Block direct external transmission from the MVP unless a separately tested enterprise connector is authorized
- **PUB-030**: Reconstruct each published statement and number from the frozen audit package

## Test machine-output auditability

Every machine-produced object includes a type, immutable identity, creator, creation time, case, source authority, input digest, output digest, code or methodology version, and status.

- **AUD-001**: Record source upload, scan, extraction, preparation, relevance disposition, period/revision classification, deduplication, withdrawal, and promotion events
- **AUD-002**: Record route compilation, plan digest, source-set pin, methodology build, profile, pathway, and depth
- **AUD-003**: Record every model attempt with actual provider, model, adapter, request digest, response digest, usage, retry, repair, and terminal code
- **AUD-004**: Record every evidence read without storing unauthorized text or secrets
- **AUD-005**: Record canonicalization, validation findings, confidence inputs, artifact digest, and lineage
- **AUD-006**: Record budget reservations, actual usage, reconciliation, and remaining ceilings
- **AUD-007**: Record run pause, resume, failure, success, acceptance, snapshot switch, and upgrade linkage
- **AUD-008**: Record model build, preview digest, scenario parameters, analyst sign-off, revision, rebase, and export
- **AUD-009**: Record report generation, analyst edits, freeze, render, change request, approval, filing, and download
- **AUD-010**: Attribute each event to machine, analyst, approver, administrator, worker, or system recovery
- **AUD-011**: Make audit events append-only and transactionally consistent with the governed mutation
- **AUD-012**: Detect missing sequence numbers, duplicate terminal events, broken digest links, and impossible state transitions
- **AUD-013**: Reject an audit event whose case, actor, artifact, or authority does not exist
- **AUD-014**: Preserve timestamp ordering and record monotonic durations separately from wall-clock time
- **AUD-015**: Keep secrets, access tokens, provider error bodies, rejected source text, and hidden chain-of-thought out of audit storage
- **AUD-016**: Export a case audit package with source-disposition, route, model, report, filing-receipt, environment, and object manifests plus digests
- **AUD-017**: Verify every object in an audit package after transfer to a separate review machine
- **AUD-018**: Reconstruct a sampled run at every pathway/depth, every published model revision, filing receipt, and filed format from the package without live provider access
- **AUD-019**: Compare reconstructed files byte for byte where deterministic and by validated canonical contract where model prose is nondeterministic
- **AUD-020**: Fail the release when any published machine-derived claim lacks a complete audit path

## Test identity, authorization, and tenant isolation

These tests prove that enterprise identity and case membership control every read and mutation.

- **IAM-001**: Reject every protected route without the enterprise edge authorization secret before body validation
- **IAM-002**: Derive role only from trusted enterprise groups in the enterprise profile
- **IAM-003**: Ignore client-supplied development role headers in the enterprise profile
- **IAM-004**: Strip every identity header the application trusts at the edge
- **IAM-005**: Test group case, whitespace, duplicates, multiple roles, missing subject, and missing groups
- **IAM-006**: Enforce membership before case read, source read, artifact read, run read, model read, report read, and audit export
- **IAM-007**: Enforce writer standing before upload, withdrawal, promotion, start, resume, upgrade, acceptance, model sign-off, and draft save
- **IAM-008**: Enforce approver standing before filing and change requests
- **IAM-009**: Prevent global role from overriding case membership
- **IAM-010**: Return the same not-found response for absent and invisible resources
- **IAM-011**: Test every route against outsider, reader, analyst, approver, administrator, removed member, and forged identity
- **IAM-012**: Recheck standing at commit time after a role or membership changes mid-request
- **IAM-013**: Prevent cross-case IDs in request bodies from changing the path-scoped case
- **IAM-014**: Reject mass assignment of identity, status, digest, authority, actor, version, and approval fields
- **IAM-015**: Test concurrent authorization change against freeze and filing
- **IAM-016**: Expire sessions and revoke access according to the enterprise edge configuration
- **IAM-017**: Reject replayed write requests where the operation is not idempotent
- **IAM-018**: Record successful and refused privileged actions without leaking invisible resource identity
- **IAM-019**: Run an automated route audit that discovers routes from OpenAPI and tests authentication and response precedence
- **IAM-020**: Review every new route for membership, role, strict request, strict response, audit, and rate-limit coverage

## Test application and artificial-intelligence security

These tests cover the web, API, supply-chain, document, model, and agent attack surfaces.

- **SEC-001**: Run dependency, container, secret, static-analysis, and software-bill-of-materials scans on the candidate commit
- **SEC-002**: Fail a security scan that parsed no files or covered less than the declared source floor
- **SEC-003**: Pin third-party workflow actions and downloaded installers by immutable digest
- **SEC-004**: Review GitHub workflows for untrusted event data entering an artificial-intelligence prompt through direct expressions, environment variables, command output, logs, or fetched pull-request content
- **SEC-005**: Prevent artificial-intelligence workflow agents from receiving broad write permissions, unsafe sandboxes, wildcard callers, repository secrets, or untrusted diffs
- **SEC-006**: Test broken object authorization against every case-scoped identifier
- **SEC-007**: Test injection in JSON, SQL-like strings, filenames, Markdown, YAML frontmatter, spreadsheet cells, document metadata, and query parameters
- **SEC-008**: Test cross-site scripting and content injection in every rendered artifact and browser panel
- **SEC-009**: Test request smuggling, duplicate headers, duplicate JSON keys, unsupported content encodings, and oversized compressed bodies at the enterprise edge
- **SEC-010**: Verify Content Security Policy, transport, framing, MIME, referrer, cache, and permissions headers on application, API, error, and download responses
- **SEC-011**: Keep framework documentation and debug surfaces closed in the enterprise profile
- **SEC-012**: Test per-subject request, stream, preview, upload, and active-job ceilings
- **SEC-013**: Test direct prompt override, role replacement, fake system messages, and instruction hierarchy attacks in documents
- **SEC-014**: Test indirect prompt injection in tables, footnotes, hidden cells, document properties, optical-character-recognition text, and source links
- **SEC-015**: Test encoded and obfuscated injections using Base64, Unicode confusables, zero-width characters, right-to-left controls, and split tokens
- **SEC-016**: Test requests to reveal system prompts, methodology text, other cases, secrets, tool schemas, hidden reasoning, or provider metadata
- **SEC-017**: Test requests to call undeclared tools, change route, bypass approval, alter budgets, write files, contact networks, or publish content
- **SEC-018**: Test many-shot context stuffing at exact token and evidence-block limits
- **SEC-019**: Test poisoned documents that repeat false facts, cite each other, or imitate canonical handoffs
- **SEC-020**: Require host validation to reject a model that follows any document instruction
- **SEC-021**: Scan model output for system-prompt leakage, secrets, personal data, unsafe links, active content, and unexpected code
- **SEC-022**: Test model extraction probes with repeated similar queries and verify rate and audit signals
- **SEC-023**: Prove model providers do not train on enterprise test data under the approved account policy
- **SEC-024**: Verify provider retention, regional routing, encryption, and account isolation settings before corpus use
- **SEC-025**: Test egress allowlists so the application can reach only approved provider, identity, scanner, and update endpoints
- **SEC-026**: Test lost, rotated, malformed, and over-privileged secrets
- **SEC-027**: Verify logs, traces, crash reports, test artifacts, and continuous-integration output contain no corpus bytes or credentials unless explicitly approved
- **SEC-028**: Run an authorized API and upload penetration test against the enterprise image
- **SEC-029**: Map artificial-intelligence findings to relevant MITRE ATLAS techniques and application findings to the adopted OWASP API and web categories
- **SEC-030**: Retest every confirmed security defect with a permanent regression test

## Run failure and concurrency simulations

Use deterministic fault injection. Repeat each simulation before and after restart, then inspect domain state, checkpoints, events, files, budgets, and audit records.

| ID | Injected condition | Required result |
|---|---|---|
| SIM-001 | Kill the process before provider call | No reservation or provider interaction |
| SIM-002 | Kill after reservation but before provider call | Resume resolves the reservation without duplicate spend |
| SIM-003 | Kill during provider call | Resume never spends again when the prior request is unresolved |
| SIM-004 | Kill after provider response but before artifact commit | One valid artifact after recovery |
| SIM-005 | Kill after artifact commit but before checkpoint write | Reuse-first recovery yields one artifact, one charge, and one terminal event |
| SIM-006 | Kill during final validation | No successful run commits past validation or budget ceilings |
| SIM-007 | Kill during snapshot acceptance | Run and case accepted pointers remain atomic |
| SIM-008 | Kill during model build or workbook render | One retryable failed or queued job, never a false ready file |
| SIM-009 | Kill during report render, freeze, or filing | No partial frozen or filed record |
| SIM-010 | Database unavailable before a write | Typed failure and no partial filesystem mutation |
| SIM-011 | Database disconnect after write acknowledgement | Idempotent retry resolves the committed state |
| SIM-012 | Serialization failure or deadlock | One winner or explicit retry, never divergent active state |
| SIM-013 | Two concurrent identical uploads | One active source identity and one source-set transition |
| SIM-014 | Upload and withdrawal interleave | A valid monotonic source-set history under both commit orders |
| SIM-015 | Two workers claim one model job | One executor wins and one exits without mutation |
| SIM-016 | Two analysts sign the same model base | One revision wins and one receives a conflict |
| SIM-017 | Two approvers file the same digest | One filed object and one filing event |
| SIM-018 | Source withdraws during evidence read | The read or subsequent validation fails closed |
| SIM-019 | Source withdraws after run success but before acceptance | Acceptance refuses or revalidates according to the pinned-source rule |
| SIM-020 | Membership changes during freeze or filing | Commit-time authorization rejects stale authority |
| SIM-021 | Vault byte changes after upload | Digest verification blocks every derived use |
| SIM-022 | Checkpoint file is absent, truncated, locked, or corrupt | Startup refuses or recovers without inventing progress |
| SIM-023 | Disk becomes full during vault or export write | No partial object is recorded as complete |
| SIM-024 | Provider returns timeout, disconnect, 429, 500, 401, 403, 422, redirect, malformed usage, or malformed output | Bounded retry policy and typed sanitized terminal outcome |
| SIM-025 | Server-Sent Event connection drops and reconnects | Missed events replay once and current state converges |
| SIM-026 | Browser receives an older response after case or run switch | Authority generation discards the stale response |
| SIM-027 | Wall clock moves backward or forward | Ordering and budget calculations remain valid through monotonic time |
| SIM-028 | Enterprise identity provider or malware scanner is unavailable | Protected work fails closed with an actionable status |
| SIM-029 | LibreOffice hangs or exits nonzero | Export finalizes failed without a published digest |
| SIM-030 | Repeated restart loop during active work | Recovery remains idempotent and bounded |

## Test browser, accessibility, and compatibility

These tests prove that supported enterprise browsers expose the same governed workflow to every user.

- **WEB-001**: Lint, type-check, unit-test, and build the static frontend from a clean dependency install
- **WEB-002**: Run all six document-first pathway journeys in Chromium, Firefox, and WebKit versions approved for the enterprise test
- **WEB-003**: Test direct navigation, refresh, back, forward, deep links, unknown routes, and expired case context
- **WEB-004**: Test loading, empty, unavailable, restricted, stale, failed, paused, succeeded, and partial-data states
- **WEB-005**: Test Server-Sent Event reconnect, duplicate event, out-of-order response, and long-running stream behavior
- **WEB-006**: Test all forms with keyboard, screen reader, zoom at 200% and 400%, reduced motion, forced colors, and high contrast
- **WEB-007**: Run an automated Web Content Accessibility Guidelines 2.1 AA scan on every destination and major state
- **WEB-008**: Manually test accessible names, focus order, focus restoration, landmarks, headings, tables, errors, status announcements, dialogs, and tabs
- **WEB-009**: Prevent color-only status and preserve readable contrast in exported and browser content
- **WEB-010**: Test dense tables with horizontal scroll, sticky labels, long values, nulls, large numbers, and narrow screens
- **WEB-011**: Test download names, media types, content disposition, cache behavior, and digest display
- **WEB-012**: Test browser preview content as untrusted text and prevent script execution
- **WEB-013**: Test session expiry and permission changes without losing unsaved local work
- **WEB-014**: Test local draft isolation across cases, tabs, users, and browser restarts
- **WEB-015**: Capture approved preview and publication screenshots for every pathway and representative dense, long-text, multilingual, conditional, held, and filed state

## Test the declared enterprise profile

The candidate test profile uses one application instance, one model/export worker, PostgreSQL for domain data, a durable checkpoint volume, and enterprise edge identity. Test at these declared limits unless the test owner approves a different manifest:

- 25 concurrent authenticated subjects
- 20 active jobs across the instance
- 4 event streams per subject
- 2 model previews per subject
- 300 requests per subject per minute
- 100 cases with 100 retained documents each
- 25 MB maximum governed source and 32 MB maximum request body
- The maximum permitted evidence blocks, route nodes, artifact bytes, model inputs, and report blocks from current configuration

Run these checks:

- **PERF-001**: Prove admission refuses the twenty-first active job before allocating provider or worker capacity
- **PERF-002**: Prove per-subject stream, preview, and request ceilings do not affect other subjects
- **PERF-003**: Hold 20 route-balanced runs across all six pathways and both depths with mixed deterministic and agent modules without cross-case data or event leakage
- **PERF-004**: Upload maximum-size supported files concurrently and preserve atomic intake
- **PERF-005**: List 100 cases without loading evidence-block bodies and keep response growth proportional to returned metadata
- **PERF-006**: Exercise 100-document source lists, source-set pins, withdrawals, and audit export
- **PERF-007**: Generate simultaneous model previews and verify no persisted transient state
- **PERF-008**: Queue concurrent model builds and exports and verify fair, bounded worker progress
- **PERF-009**: Keep non-provider API reads below 1s at the 95th percentile in the declared lab profile
- **PERF-010**: Deliver persisted run events to connected browsers within 2s at the 95th percentile after commit
- **PERF-011**: Keep the browser responsive during maximum-length tables and event histories
- **PERF-012**: Record CPU, memory, database connections, checkpoint size, vault growth, and export storage during the full test
- **PERF-013**: Run an eight-hour route-balanced soak with repeated upload, run, accept, model, draft, freeze, approve, receipt, download, and audit-export cycles, including representative faults under saturation
- **PERF-014**: Finish the soak with no leaked jobs, permits, file handles, database connections, or growing orphan state
- **PERF-015**: Repeat all six golden journeys after the soak and compare authority, model hashes, filed bytes, and audit reconstruction to the pre-soak baseline

Performance numbers qualify this enterprise test profile only. They are not production service-level objectives.

## Review the application manually

Automated tests cannot approve analytical judgment or external communication. Complete these recorded reviews:

- **REV-001: Credit analyst blind review**: two analysts independently compare every golden result with the source pack and answer key
- **REV-002: Disagreement adjudication**: a third analyst resolves material score differences and records the rule used
- **REV-003: Model-risk review**: review model qualification, known limitations, removal rules, provider policy, prompt controls, and failure behavior
- **REV-004: Evidence audit**: sample claims and numbers from every module, model, and published format and reconstruct each locator
- **REV-005: Opinion ownership review**: verify the final opinion is visibly analyst-owned and every machine contribution is distinguishable
- **REV-006: External stakeholder review**: assess clarity, confidentiality, source disclosure, limitations, terminology, decision usefulness, institutional presentation, and whether each output is no worse than the pinned Credit Operating System benchmark
- **REV-007: Threat-model review**: cover actors, trust boundaries, data flows, assets, abuse cases, mitigations, and residual risks
- **REV-008: Authorization review**: inspect every route and state mutation against the role and membership matrix
- **REV-009: Data-governance review**: approve corpus licensing, provider handling, retention, deletion, audit export, and test reset
- **REV-010: Accessibility review**: complete manual assistive-technology and keyboard testing
- **REV-011: Architecture-boundary review**: verify host-owned identity, authority, routing, evidence, budgets, calculations, and approvals remain outside model control
- **REV-012: Audit reconstruction exercise**: give an independent reviewer only the audit package and measure whether they reconstruct the sampled result
- **REV-013: Failure tabletop**: walk through compromised document, provider incident, evidence withdrawal, corrupt vault, bad publication, and lost approver access
- **REV-014: Enterprise environment review**: approve identity, network, egress, secrets, encryption, logging, data reset, and single-instance enforcement
- **REV-015: Scope review**: confirm excluded production operations have not re-entered the MVP gate through an implicit requirement

Each review records reviewer identity, role, date, build digest, corpus version, result, findings, and sign-off.

## Produce a release evidence package

Store one immutable package for the candidate build containing:

- Git commit, dirty-state result, container digests, dependency locks, and software bill of materials
- Enterprise test environment manifest and single-instance limitation
- OpenAPI document and generated route inventory
- Qualified provider and model catalog
- Corpus manifests, per-file relevance dispositions, period-coverage maps, and source digests
- Unit, contract, integration, browser, accessibility, corpus, model-matrix, performance, soak, and simulation results
- Statement, branch, and critical-path coverage reports
- Static analysis, dependency, container, secret, workflow, penetration, and artificial-intelligence security reports
- Quality ledger and defect ledger snapshots
- Pinned deliverable benchmark/rubric, pathway/format visual goldens, semantic-parity reports, analyst scorecards, adjudications, external-stakeholder review, approval records, and filing receipts
- Run, evidence, model, report, publication, and audit reconstruction samples
- Every excluded production requirement and approved test-only limitation
- Zero unresolved required skips, waivers, missing artifacts, or unknown statuses

Hash the package and have the enterprise test owner sign the manifest.

## Enforce release exit criteria

The MVP is enterprise-testing ready only when all conditions below are true:

- Every G0 through G9 gate passes on the same candidate commit
- Every selectable model passes the complete qualification matrix
- All six pathways pass every applicable route, model, corpus, publication, browser, and reconstruction gate at both depths
- Every accepted model and interpretation proves complete, reasoned coverage of all relevant supplied annual, quarterly/interim, forecast, and forecast-revision documents
- Independent blind review finds every required browser, Markdown, PDF, and XLSX deliverable no worse than the pinned Credit Operating System benchmark
- Every core test has a retained result and no required test is skipped, waived, flaky, or marked not run
- All ten engine invariants pass
- All in-scope quality-ledger features pass on the candidate
- The current blocker table contains no open item
- No open critical or high security, integrity, authorization, audit, data-loss, or publication defect exists
- No accepted or published output contains an unsupported material claim or unresolved citation
- Every machine-produced published element has a complete audit path
- Independent analysts approve every golden route and model combination
- The document-first journey passes without analytical data entry beyond source documents
- Analyst opinion and approval remain human-owned and digest-bound
- The enterprise test owner signs the release evidence package

Failure leaves the build in development status. A typed refusal from the application may be a correct test outcome. A missing test, missing audit path, or unqualified model is never a correct release outcome.
