---
meta:
  contentType: Plan
  audience: Product, engineering, quality assurance, security, model risk, credit analysts, approvers, and enterprise test owners
---

# Make CAOS enterprise-testing ready

## Outcome

Deliver an MVP that can enter a controlled enterprise test environment and prove this journey on one candidate commit and image:

> A user supplies all relevant source documents, including annual reports, quarterly/interim reports, and forecasts. CAOS creates or resolves the case, prepares and reconciles the complete evidence set, chooses and executes any of the six governed pathways, produces the source-grounded financial model and pathway deliverables, and opens a reviewable interpretation. A human analyst owns the final opinion. A separate authorized approver publishes exact files for external stakeholders. Every machine-produced input, inclusion/exclusion decision, calculation, transformation, and output can be reconstructed from retained evidence.

This plan implements the binding standard in `ENTERPRISE_TESTING_READINESS.md`. It does not duplicate that document's 340 checks. Each phase maps the existing checks, simulations, blockers, and gates to implementation work and retained evidence.

## Scope decisions

These decisions keep the MVP small while preserving every enterprise integrity requirement:

1. **Enterprise testing, not production**: do not add high availability, horizontal scaling, multi-region deployment, production service levels, or unrestricted external distribution.
2. **One enforced topology**: one application instance, one background worker, PostgreSQL domain storage, and one durable SQLite checkpoint volume.
3. **All six governed pathways**: Full Credit, Earnings Update, Covenant & Refinancing, Relative Value, Distressed, and Deep Research must compile, execute, produce their declared model/deliverables, and reconstruct at every supported depth. A pathway cannot appear in enterprise UI or contracts unless the same candidate proves its complete route.
4. **Two tested depths**: screen and full remain in the qualification matrix. Screen preserves the source-grounded deterministic contract required by `RUN-030`; full uses the qualified provider for source interpretation. Either may return a typed insufficiency refusal, but neither may return a generic fixed summary or unsupported analysis.
5. **One qualified machine-generation binding**: expose no user LLM/provider picker in the enterprise MVP. The environment activates exactly one provider/model/policy binding that has passed the complete matrix. A second binding is not selectable until it passes the same matrix. Signed financial-model selection, assumptions, revisions, scenarios, and sign-off remain governed analyst controls and are not LLM selection.
6. **No silent fallback**: an absent, unqualified, unavailable, over-budget, or contract-incompatible model produces a typed refusal. It never falls back to another model or to placeholder analysis.
7. **Documents are the only analytical input**: case metadata and the default route are derived server-side. Every supplied file receives an auditable relevance disposition. Every relevant annual, quarterly/interim, forecast, and forecast-revision document feeds the analysis and financial-model lineage; no relevant source may be silently ignored. When the documents cannot establish the subject or minimum evidence, CAOS asks one bounded clarification or refuses; it does not require the analyst to recreate source facts in forms.
8. **Human governance remains explicit**: analyst review and opinion sign-off, followed by separate approver filing, are deliberate actions. They are governance decisions, not extra analytical inputs.
9. **Institutional deliverable benchmark**: meet or exceed the information hierarchy, committee readability, paper presentation, tabular financial precision, evidence visibility, and decision usefulness of Credit Operating System commit [`e566c1b`](https://github.com/EricMG13/Credit-Operating-System/tree/e566c1b78e0e7a35b2cd854b26f8d4f3e8a4f53a). Copy no seeded facts or fixture content; use the pinned repository only as a design and publishing benchmark.
10. **Reuse before invention**: extend the current strict contracts, provider port, ingestion service, static route compiler, stores, authority reducer, deliverable lifecycle, test fixtures, route audit, quality ledger, and CI workflows.

## Success measures

The plan is complete only when:

- `ETR-B01` through `ETR-B13` are closed with retained evidence.
- G0 through G9 pass on the same commit, image digests, model binding, corpus version, and enterprise-test environment.
- The document-first browser journey accepts only source documents as analytical input.
- All six pathways compile and run at both depths. Every complete positive pack produces its declared analysis, financial model, and pathway deliverables; sparse or contradictory negative packs produce the expected typed refusal rather than standing in as proof that the pathway works.
- Every accepted analysis and model has a complete inclusion/exclusion manifest for all supplied annual, quarterly/interim, forecast, and forecast-revision documents, with 100% of relevant files traced to model inputs, assumptions, calculations, or cited analysis.
- Every accepted result is either fully supported or a typed refusal.
- Every selectable model is qualified; for this MVP, that means the sole active binding.
- SIM-001–030, two-connection PostgreSQL races, declared-capacity tests, maximum-shape tests, restart/recovery tests, and the eight-hour soak pass without cross-case leakage or leaked jobs, connections, handles, or partial files.
- Each pathway's browser preview, Markdown, PDF, XLSX, model appendix, and evidence/QA package passes the pinned institutional-deliverable rubric and independent blind review.
- Every filed byte is bound to a human opinion sign-off and a separate approver action.
- An independent reviewer reconstructs sampled machine outputs without application-team help.
- No required check is skipped, waived, flaky, marked not run, or represented only by historical prose.

## External inputs required before candidate qualification

These are decisions or assets, not reasons to delay implementation:

| Input | Owner | Needed by | Failure mode |
|---|---|---|---|
| Exact provider, model ID/version, parameters, and contractual settings | Model risk and product | Phase 2 qualification | No active enterprise model; application fails closed |
| Provider credentials in a protected test environment | Enterprise test owner | Phase 2 qualification | Live qualification cannot run |
| Approved corpus bytes, licences, classifications, and answer keys | Credit analysts, legal/data owner | Phase 2 qualification | G2–G4 cannot pass |
| Enterprise identity provider, group claims, and test accounts | Enterprise identity owner | Phase 6 | G5 and G9 cannot pass |
| Expected user concurrency, document sizes, and run-volume envelope | Enterprise test owner | Phase 6 | Performance exit cannot be evaluated |
| Approved benchmark screenshots, content rubric, minimum print sizes, and reviewer score threshold pinned to Credit Operating System `e566c1b` | Credit analysts, design owner, and external-stakeholder reviewer | Phase 4 | Deliverable quality cannot pass |
| Release-package signer and evidence retention location | Enterprise test owner | Phase 7 | Candidate cannot receive final sign-off |

## Dependency order

| Phase | Depends on | Primary result |
|---|---|---|
| 0. Truthful baseline | None | One current requirement, route, test, and evidence inventory |
| 1. Pin machine authority and transaction truth | Phase 0 | Every run/output records actual authority; core governed writes are atomic |
| 2. Build the qualification foundation | Phases 0–1 | Versioned source packs, all-pathway harness, answer keys, and host controls are ready |
| 3. Deliver document-first intake and models | Phases 1–2 contracts | Documents automatically become a review-ready governed run and financial model |
| 4. Deliver institutional publication and audit | Phases 1–3 | Analyst-owned, benchmark-quality files are attributable and reconstructable |
| 5. Prove PostgreSQL, stress, and failure safety | Phases 1–4 | Concurrency, load, crash, restart, and recovery outcomes are exact and fail closed |
| 6. Prove the enterprise profile | Phases 0–5 | Identity, security, browser, accessibility, and capacity gates pass |
| 7. Qualify the candidate | All prior phases | Final live six-pathway qualification and G0–G9 evidence package are signed |

## Readiness-check ownership

The 340 IDs remain defined in `ENTERPRISE_TESTING_READINESS.md`. This map assigns each family to the phase that implements the missing controls and the phase that produces final candidate evidence.

| Check family | Count | Implementation owner | Candidate proof |
|---|---:|---|---|
| UX-001–020 | 20 | Phase 3 | Phases 6–7 browser and analyst review |
| SRC-001–030 | 30 | Phases 2–3 | Phases 5–7 corpus, fault, and security results |
| EVD-001–020 | 20 | Phases 1–2 | Phases 2 and 7 qualification/reconstruction |
| RUN-001–030 | 30 | Phases 1–3 | Phases 5 and 7 route/recovery results |
| MOD-001–025 | 25 | Phases 1–2 | Phases 2 and 7 live qualification matrix |
| ANA-001–020 | 20 | Phases 2 and 4 | Phase 7 analyst scorecards and sign-offs |
| CALC-001–020 | 20 | Phases 2 and 4 | Phases 2, 5, and 7 deterministic checks |
| PUB-001–030 | 30 | Phase 4 | Phases 5–7 filing, browser, and stakeholder results |
| AUD-001–020 | 20 | Phases 1 and 4 | Phase 7 independent offline reconstruction |
| IAM-001–020 | 20 | Phase 6 | Phases 6–7 enterprise identity matrix |
| SEC-001–030 | 30 | Phases 2 and 6 | Phases 6–7 security package |
| SIM-001–030 | 30 | Phase 5 | Phases 5 and 7 retained simulation results |
| WEB-001–015 | 15 | Phases 3 and 6 | Phases 6–7 browser/accessibility results |
| PERF-001–015 | 15 | Phase 6 | Phases 6–7 performance and soak results |
| REV-001–015 | 15 | Phase 7 | Phase 7 signed manual-review records |

## Allowed APIs and implementation patterns

Use this list as the default design boundary. Add a new abstraction only when none of these existing seams can express the requirement.

| Concern | Reuse |
|---|---|
| Strict boundaries | `StrictModel`, `BoundaryText`, and named FastAPI `response_model`s in `caos/server/caos/contracts.py` and `responses.py` |
| Source admission | `Vault` and `ingest_upload` in `caos/server/caos/sources/domain.py` |
| Case authority | `require_case` and case membership checks in `caos/server/caos/api/__init__.py` |
| Route authority | `compiled_route(pathway, depth)` in `caos/server/caos/engine/graphs.py` and registry-only modules |
| Execution authority | `Engine.start_run`, gate pins, per-module revalidation, budget reservation, and `read_evidence` |
| Provider seam | `Provider` plus the Anthropic and OpenRouter adapters; extend this port with immutable identity instead of inspecting environment settings later |
| Governed writes | SQL constraints, row locks, unique indexes, expected-version CAS, and state plus audit/event in one transaction |
| UI authority | `workspaceAuthority.ts` request contexts, generations, and stale-response fencing |
| Human sign-off | Exact preview digest plus expected-head CAS from Model Builder |
| Publication | Deliverable draft/freeze/file lifecycle and hash-addressed verified-byte helpers from model exports |
| Test providers | `ScriptedProvider`, `CorpusProvider`, canonical messages, and existing source/run seed helpers |
| Fault injection | Existing `*_for_tests` hooks, fake clock, kill-after-module, commit-gap, renderer, and stale-result seams |
| Concurrency tests | Existing `asyncio.gather`, `asyncio.to_thread`, and `ThreadPoolExecutor` exactly-one-winner patterns |
| Route discovery | OpenAPI path enumeration and `app.routes`; do not keep a second hand-authored route list |
| Traceability | Extend `docs/quality_ledger_coverage.py`, `docs/QUALITY_LEDGER.csv`, and `docs/QUALITY_DEFECTS.csv` |
| Browser testing | Existing Playwright dependency and combined-app harness |

## Current-state corrections applied to this plan

This is a delta plan, not a rebuild. Preserve proven controls and target the remaining false-success and enterprise-evidence gaps.

| Current evidence | Plan response |
|---|---|
| Strict wire/OpenAPI contracts, 33 evidence-refusal shapes, strong ingestion atomicity, deterministic finite calculations, append-only draft/model revisions, freeze/file separation, exact stored downloads, crash/resume seams, and Chromium accessibility coverage already exist | Reuse and extend them; do not create replacement frameworks or duplicate lifecycles |
| At `ba97a89`, backend development evidence is `655 passed, 2 skipped, 864 warnings`; the retained full-corpus host control is `34 passed, 124 warnings`. The security audit and quality-ledger gate each began with 10 failures; Task 1 repaired their probe and mapping drift. Frontend unit evidence is `113 passed`; Ruff, methodology consistency, bundle checks, the frontend build, and the workbench journey pass. | Treat all of this only as development evidence. Resolve warning ownership, rerun every candidate gate, and execute the protected live-model, stress, publication, and reconstruction gates on one immutable candidate. |
| One digest-pinned 30-document Carnival pack now covers FY2023–FY2025 annual, quarterly, guidance/forecast, and executed term-loan materials; all 30 upload and extract, and the four implemented pathways pass both depths with `CorpusProvider` | Keep it as the performing-credit host-control baseline. It is not enough for all-pathway qualification: add answer-key metadata, lender/market data for Relative Value, a genuine stressed/restructuring pack for Distressed, a question-specific pack for Deep Research, and live-provider/model/deliverable/browser proof |
| Ledger validation previously failed because `LICENSE` mapped to no feature; it now excludes that non-product file, and the former corpus waiver has current host-control evidence | Keep historical, waived, skipped, or not-run evidence from satisfying a candidate gate |
| The engine runs four pathways while UI/contracts expose six | Implement and qualify Distressed and Deep Research so all six surfaces become truthful; until that work lands, they must remain visibly unavailable rather than falsely runnable |
| `AGENT_EXECUTION_ENABLED=false` can currently emit generic deterministic `COMPLETE` summaries | Remove this false-success path first. Preserve deterministic screen execution only when it is source-grounded and contract-valid; otherwise return a typed refusal |
| OpenRouter's default is documented as unable to complete CP-1, its token estimate lacks maximum-shape proof, and current attempt metadata can report the Anthropic model | Keep OpenRouter development-only for the initial enterprise profile. Qualify one exact binding and record its actual immutable identity everywhere |
| No LLM picker exists, but signed financial-model selectors do | Keep the LLM picker absent and preserve the financial-model/revision controls |
| Draft CAS, freeze/file separation, digest-bound filing, and exact filed downloads exist | Add only missing opinion sign-off, separation of duties, disclosure/origin labels, atomic freeze publication, approver provisioning, and audit reconstruction |
| The governed builder and canonical `document_sections` deliverable implementation exists, including worksheet, sensitivity, tornado, rebase, and build/revision export routes | Preserve and reuse it. Deterministic/scripted host proof does not qualify live analysis, and all-six-pathway enterprise qualification remains open. |
| Current PDF rendering is a minimal single-column text export with fixed-line truncation and character replacement; tables/charts are flattened and XLSX is a flat dump | Replace presentation through the existing renderer seam and frozen lifecycle. Preserve source truth and exact-byte controls while adopting the pinned institutional content/layout benchmark |
| Frozen bytes are created before a filing approver exists | Keep exact frozen bytes unchanged and attach approver identity in an immutable filing receipt/audit package unless an intended approver is bound before render |
| Acceptance pointers and audit are separate writes; event sequence and budget updates lack proven database serialization; several locks are process-local | Repair the shared transactional foundations in Phase 1 and prove them with two PostgreSQL connections in Phase 5 |
| Terminal checkpoint cleanup exists, but there is no exclusive app lock or checkpoint corruption proof | Test paused/in-flight recovery and add only the missing single-instance/corruption controls |
| A real encrypted restore drill exists but exposed fresh-schema, vault-discovery, and cross-store snapshot defects | Repair those three defects and rerun under active writes; do not replace the backup system |
| Loan-workbook text can bypass `BoundaryText` and bidirectional-control validation | Close that boundary before corpus/model qualification |
| The frontend advertises an unavailable Admin Studio | Remove the destination now; add an authenticated audit/package route later only if the product actually needs it |

## Deliberate scope reductions

The binding release gates remain unchanged. These reductions remove duplicated
implementation and development-time qualification work; they do not turn a
required candidate gate into a waiver.

- **Reuse green controls.** The ten engine invariants, 223 mapped contractual
  rows, source-ingestion controls, deterministic calculations, strict response
  contracts, crash/resume seams, the 30-document Carnival host-control pack,
  and existing route/security checks are retained as candidate reruns. They are
  not separate rebuilds or new test families.
- **Keep corpus material proportionate.** Carnival is the shared complete
  performing-credit pack for C01/C17/C18/C19; C20 adds one licensed
  market-marks pack; C21 adds one stressed/restructuring pack; and C22 adds one
  question-specific research pack. C02–C16 are small, composable synthetic
  fixtures unless a live qualification answer key genuinely needs a complete
  document pack.
- **Implement one journey, parameterize its cases.** Phase 3 builds one
  document-first intake/review flow. Its six pathway selections use data-driven
  tests, not six implementations. The full three-browser matrix belongs to the
  enterprise candidate stages.
- **Use a representative presentation baseline.** Phase 4 keeps a compact
  cross-format golden set for normal, dense, long-text, multilingual, held,
  and filed output. Per-pathway visual and blind-review evidence is collected
  once on the frozen candidate in Phase 7.
- **Extend existing failure seams.** Phase 5 first reuses the existing
  kill-after-module, commit-gap, unresolved-spend, stale-worker,
  renderer-tamper, and route-injection seams. New simulation work is limited to
  unrepresented faults and two-connection PostgreSQL behaviour.
- **Candidate-only scale proof.** The declared saturation workload, full
  browser matrix, eight-hour soak, and reviewer panels are protected Phase 6–7
  work, not normal development gates.

## Phase 0 — Establish a truthful baseline

### Objective

Make G0 measurable before changing behaviour. Remove stale counts and prose-only claims so later work cannot appear complete without candidate evidence.

### Implement

1. Extend `docs/quality_ledger_coverage.py` only for unmapped enterprise IDs.
   Preserve existing test mappings, require an artifact type and G0–G9 gate for
   each added row, and reject a candidate `PASS` without a retained result from
   the same commit.
2. Generate the API route inventory from `app.openapi()["paths"]`, preserving the current explicit SSE and binary-response exemptions.
3. Generate the UI destination inventory from the actual workspace destination declarations. Replace `production-inventory.mjs` as a release gate; do not patch its foreign routes or fixture IDs.
4. Reconcile route scope across engine, OpenAPI contracts, Run Console, Report Studio, qualification, and publishing. The target is all six named pathways; while Distressed and Deep Research remain unimplemented, mark them unavailable rather than advertising false execution.
5. Reconcile contradictory suite counts, Python/Node versions, backup/checkpoint statements, and the Postgres-checkpointer statement from a fresh collected inventory. Documentation must report the candidate result, not a remembered number.
6. Fix nightly Python to the supported runtime and align CI and image Node majors.
7. Add machine-readable test results and artifact retention to existing CI jobs. At minimum retain JUnit, browser traces/screenshots on failure, security reports, route inventory, ledger validation, and image digests.
8. Keep the ordinary CI fast. Put live credentials, approved corpus, model qualification, simulations, and human sign-off behind a protected candidate run of the existing workflow.
9. Add this plan and `ENTERPRISE_TESTING_READINESS.md` to version control before implementation. Fix the current `LICENSE` ledger-coverage failure and replace stale test-count claims with collected candidate results.
10. Remove the unavailable Admin Studio destination and its nonexistent `/api/admin/bundle` and `/api/admin/audit` calls. Add audit-package UI/API later only when Phase 4 requires a user-facing download.
11. Check in the benchmark commit, a compact representative rubric, minimum print size, and reviewer threshold. Collect pathway-specific visual and blind-review evidence only in the frozen candidate run.
12. Record the minimum enterprise-test data handling, bounded logging, and reset ownership in the environment manifest. Full production lifecycle automation remains excluded.

### Primary files

- `docs/quality_ledger_coverage.py`
- `docs/QUALITY_LEDGER.csv`
- `docs/QUALITY_DEFECTS.csv`
- `run_sec_audit.py`
- `caos/frontend/scripts/production-inventory.mjs`
- `caos/frontend/src/components/Workspace.tsx`
- `caos/frontend/src/components/report/ReportStudio.tsx`
- `caos/frontend/src/lib/workbench.ts`
- `.github/workflows/ci.yml`
- `.github/workflows/nightly.yml`
- `README.md`, `CLAUDE.md`, `docs/DECISIONS.md`, and `SPEC_RECONCILIATION.md`

### Documentation references

- `ENTERPRISE_TESTING_READINESS.md`: Preserve the sources of truth; Apply release gates; Produce a release evidence package.
- `SPEC_RECONCILIATION.md`: ten invariants and remaining D3 deferral.
- `TEST_INVENTORY.md`: historical classification only; do not use it as a current pass result.

### Verify

- [ ] Route inventory exactly matches the candidate OpenAPI document.
- [ ] UI inventory contains no unavailable or engine-rejected pathway.
- [ ] Distressed and Deep Research are either engine-backed end to end or explicitly unavailable everywhere; no surface claims success early.
- [ ] Admin Studio and its nonexistent calls are absent.
- [ ] Every in-scope ledger and ETR ID resolves to an observable check and expected artifact.
- [ ] A missing, renamed, skipped, waived, stale, or unexecuted required test makes validation fail.
- [ ] CI and image runtimes match declared supported versions.
- [ ] Test counts are collected, not inferred from static function definitions.
- [ ] The retained artifact set includes commit and image identity.
- [ ] G0 has no unknown status.
- [ ] `LICENSE` and every other in-scope product file map to a feature or an explicit documented exclusion.
- [ ] The pinned deliverable rubric and reviewer threshold are checked in and reference immutable benchmark artifacts.

### Anti-pattern guards

- Do not copy all 340 checks into 340 new tests. Map existing proof first and add only missing observables.
- Do not count source-regex frontend checks as behavioural evidence.
- Do not count a historical `PASS`, a documented scenario, or a green tool that scanned zero files.
- Do not maintain route lists independently of OpenAPI and actual UI declarations.

### Exit

`ETR-B08` is closed. The candidate workflow can identify every required check and the exact evidence artifact that will prove it.

## Phase 1 — Pin truthful machine authority and transaction truth

### Objective

Close false-success, attribution, and governed-write defects before producing more outputs. A run must never infer machine identity from current environment settings after it starts, and no accepted authority may be split across non-atomic writes.

### Implement

1. Remove the generic deterministic `COMPLETE` fallback. In enterprise mode, unavailable agent-backed interpretation returns a typed refusal. Preserve deterministic screen modules only when their output is derived from the pinned sources and validated contract.
2. Extend the existing `Provider` port with an immutable identity value containing:
   - provider name;
   - exact model ID and provider-reported version when available;
   - adapter/runtime version;
   - generation parameters and context policy digest;
   - qualification-record ID and digest.
3. Make both existing adapters provide that identity. Do not introduce a new provider framework.
4. Make the initial enterprise profile use one qualified Anthropic binding. Keep OpenRouter and its current GLM default development-only until they independently pass identity, CP-1, token-reservation, and maximum-shape qualification.
5. Validate the active binding's signed or digest-bound qualification record at startup and refuse enterprise mode when it is missing, expired, for another build, or for another policy.
6. Keep the LLM/provider picker absent. Preserve signed financial-model selection and revision controls.
7. Pin provider identity into the run/plan authority at `Engine.start_run`; never reread `settings.anthropic_model` or `settings.openrouter_model` to describe an existing run.
8. Record the actual provider identity on every attempt, event, artifact, accepted snapshot, model build, deliverable freeze, audit entry, API response, frontend review surface, and release-package sample.
9. Add request digest, response digest, provider request ID, usage, retry index, terminal code, and bounded error classification. Do not retain raw prompts, hidden reasoning, provider error bodies, or secrets.
10. Record each `read_evidence` call with run, module, provider attempt, source-set version, source/block IDs, returned-byte digest, budget effect, and result code.
11. Make provider absence, identity mismatch, unqualified binding, expired qualification, model substitution, and unresolved spend typed fail-closed states.
12. Require the qualified binding for full-depth source interpretation. Keep screen source-grounded and deterministic, and keep deterministic code for declared arithmetic, canonicalization, and rendering. A generic fixed payload must not reach acceptance or publication.
13. Make snapshot acceptance, the run pointer, the case pointer, the actual acceptance timestamp, and the audit event one transaction.
14. Add database winner/loser semantics for event-sequence allocation, budget reserve/reconcile, acceptance, model revisions/sign-off, and deliverable/opinion revisions. Use typed conflicts; never rely on process-local locks for correctness.

### Primary files

- `caos/server/caos/engine/provider.py`
- `caos/server/caos/engine/anthropic.py`
- `caos/server/caos/engine/openrouter.py`
- `caos/server/caos/engine/runtime.py`
- `caos/server/caos/engine/loop.py`
- `caos/server/caos/engine/evidence.py`
- `caos/server/caos/config.py`
- `caos/server/run.py`
- `caos/server/caos/storage/runs.py`
- `caos/server/caos/storage/models.py`
- `caos/server/caos/storage/deliverables.py`
- `caos/server/caos/api/__init__.py`
- `caos/server/caos/responses.py`
- `caos/frontend/src/lib/api.ts`
- Existing provider, run, budget, evidence, and HTTP contract tests

### Documentation references

- `ENTERPRISE_TESTING_READINESS.md`: blockers B02–B04 and B09; Qualify every provider and model; Test machine-output auditability.
- `CLAUDE.md`: model is untrusted, budgets are pre-reserved, and all observed evidence is pinned.

### Verify

- [ ] Anthropic attempts report Anthropic and the exact configured model.
- [ ] OpenRouter attempts report OpenRouter and never `settings.anthropic_model`.
- [ ] Changing environment settings after run creation cannot change stored or returned run identity.
- [ ] A provider returning a different model/version is refused and audited.
- [ ] Every attempt and evidence read has complete bounded metadata and digests.
- [ ] Missing or expired qualification prevents enterprise run creation.
- [ ] No unavailable provider produces deterministic placeholder analysis.
- [ ] A screen run is deterministic, source-grounded, and either contract-valid or a typed refusal.
- [ ] OpenRouter cannot start an enterprise run.
- [ ] Financial-model selection controls remain available and are never presented as LLM selection.
- [ ] Acceptance commits all pointers, the actual acceptance time, and audit together or commits none.
- [ ] Event, budget, model, and deliverable contention returns one winner and typed losers without raw integrity errors.
- [ ] Crash/retry tests prove one budget outcome and one attributable attempt lineage.
- [ ] Strict response-contract tests reject missing or extra identity fields.

### Anti-pattern guards

- Do not add a user-visible list backed only by configuration.
- Do not silently fall back between providers or models.
- Do not record the default adapter's model when another adapter ran.
- Do not let the provider or document text choose its own identity, route, tools, budget, or qualification.
- Do not store raw secret-bearing model traffic to make the audit look complete.

### Exit

`ETR-B02`, `ETR-B03`, `ETR-B04`, and `ETR-B09` are closed for the initial enterprise profile by one explicit, qualified, immutable binding and fail-closed exclusion of OpenRouter. The shared governed-write foundations are ready for Phase 5 PostgreSQL proof.

## Phase 2 — Build the corpus and qualification foundation

### Objective

Build the versioned evidence packs, source-completeness contract, route contracts, answer keys, and reusable harness needed to qualify all six pathways. Run final live qualification only after intake, model, opinion, renderer, publication, and audit contracts are frozen.

### Current corpus coverage decision — 2026-08-31

The SHA-256-pinned Carnival baseline is sourced from the issuer's [financial
results archive](https://www.carnivalcorp.com/investors/financial-information/financial-report-archive/).
Its 2024 Q2 report is a 579-page combined quarterly/legal package containing
executed term-loan repricing amendments and full agreement text. It is a strong
performing-credit host-control pack, but it cannot qualify every pathway by
itself.

| Pathway | Current source-material status | Required next pack/evidence |
|---|---|---|
| Full Credit | Annual, every Q1–Q3 filing, every Q1–Q4 management update, forecasts, debt and legal materials present | Add analyst answer keys, source-disposition/use lineage, live provider, model, deliverable and browser assertions |
| Earnings Update | Three complete annual/quarterly/update cycles present | Add actual-versus-guidance and forecast-revision answer keys plus metamorphic period tests |
| Covenant & Refinancing | Executed term-loan agreements, amendments, debt disclosures and maturity/guidance material present | Add covenant clause/capacity answer keys and independently reviewed expected results |
| Relative Value | Issuer evidence is present but current loan prices, spreads, yields and comparable instruments are not issuer documents | Add a separately licensed, time-aligned user-uploaded loan-universe/market-marks pack; do not fabricate issuer-sourced marks |
| Distressed & Restructuring | Carnival is not a complete restructuring/LME qualification case and the engine route is unavailable | Build a separate 20–30 document stressed case from official materials such as [Lumen's annual reports](https://ir.lumen.com/financials/annual-reports/default.aspx), [transaction support agreement](https://ir.lumen.com/news/news-details/2023/Lumen-Announces-Broad-Agreement-With-Creditors-That-Will-Provide-The-Company-with-Significant-Flexibility-to-Execute-Its-Transformation-Strategy/default.aspx), [completed TSA transactions](https://ir.lumen.com/news/news-details/2024/Lumen-Technologies-Completes-TSA-Transactions-Enabling-Transformation-Strategy/default.aspx), and [exchange offers](https://ir.lumen.com/news/news-details/2024/Lumen-Announces-Exchange-Offers-for-Unsecured-Notes-of-Lumen-and-Level-3/default.aspx), then implement the route |
| Deep Research | A generic issuer pack cannot prove an arbitrary research question and the engine route is unavailable | Add question-specific positive/negative packs with approved research briefs, answer keys, forbidden conclusions and time-bounded external evidence, then implement the route |

No public issuer-only corpus can prove Relative Value without separate market
data, and no source pack can prove a route whose runtime graph does not execute.
Those are product/input gaps, not corpus-count problems.

### Implement

1. Keep Carnival as the shared complete performing-credit pack for C01/C17/C18/C19; add one licensed market-marks pack for C20, one stressed/restructuring pack for C21, and one question-specific pack for C22. Build C02–C16 as composable synthetic fixtures unless a live answer key requires a full pack. Record retained filename, provenance, licence/classification, SHA-256, document type, reporting/forecast period, supersession status, expected facts, conflicts, forbidden conclusions, route expectation, and analyst-approved answer-key version.
2. For every supplied file, create a governed disposition: `used`, `superseded`, `conflicting`, `out_of_scope`, or `insufficient`. Every `used` file must reach evidence/model lineage; every other disposition needs a bounded auditable reason. Source-set membership alone is not proof of use.
3. Reconcile annual, quarterly/interim, LTM, management/lender forecast, analyst base, and analyst downside periods by issuer perimeter, fiscal calendar, as-of date, currency, units, accounting definition, and restatement precedence. Preserve reported actuals, external forecasts, and analyst scenarios as distinct authorities.
4. Keep network retrieval outside pytest. Make the fetch step verify every digest. Candidate qualification must hard-fail on missing or mismatched required bytes.
5. Preserve `CorpusProvider` tests as host-control tests only. They prove ingestion, route, evidence, and contract behaviour, not model quality.
6. Implement Distressed and Deep Research route/methodology contracts through the existing registry and static compiler. Do not create a second route catalog.
7. Add one parameterized qualification harness over:
   - the active provider/model/policy binding;
   - six pathways;
   - two depths;
   - at least one complete positive pack per route/depth cell;
   - applicable sparse, ambiguous, conflicting, hostile, and over-limit negative packs;
   - three cold repetitions per required live cell in Phase 7.
8. Score facts, citation correctness, unsupported claims, conflict handling, refusal behaviour, limitations, route completeness, document-use coverage, model effects, security behaviour, latency, and budget against the answer keys.
9. Require every complete positive cell to succeed with its declared route contract. A refusal is valid only for a designated negative pack and cannot substitute for proof that a pathway runs.
10. Add metamorphic completeness tests: remove or change one annual, quarterly/interim, and forecast source in turn; add an irrelevant source; add a restatement/conflict; withdraw or corrupt a bound source. Assert the expected input, artifact, model fingerprint, output, limitation/refusal, and audit lineage changes.
11. Validate all loan-workbook and deterministic document-derived text through `BoundaryText`, including bidirectional overrides, zero-width characters, confusables, and formula-leading cells, before it reaches CP-3, a model, or a renderer.
12. Exercise prompt-injection C12 through the exact live provider path and assert that instructions in evidence cannot alter tools, prompts, route, budgets, authority, or outputs.
13. Make qualification evidence bind the model, provider, adapter, policy, corpus digest, candidate build/image, date, expiry, and reviewer. Automatically refuse an active binding when any required cell fails or expires.
14. Build and validate the reusable harness here with host controls and protected development runs. Execute the final complete live matrix only in Phase 7.

### Primary files

- `caos/tests/corpus/sources.txt` or its manifest replacement
- `caos/tests/corpus/fetch.sh`
- `caos/tests/test_corpus_pathways.py`
- `caos/tests/spec/spec_helpers.py`
- `caos/server/caos/modules/registry.py`
- `caos/server/caos/engine/graphs.py`
- `caos/server/caos/models/service.py`
- `caos/server/caos/models/engine.py`
- Loan-workbook ingestion/rendering code and tests
- Existing provider and budget tests
- `.github/workflows/ci.yml`
- `.github/workflows/nightly.yml`
- `docs/QUALITY_LEDGER.csv`

### Documentation references

- `ENTERPRISE_TESTING_READINESS.md`: Build the qualification corpus; Qualify every provider and model; Test analytical interpretation and opinion ownership.
- Vendored methodology schemas and validators: analytical contracts and forbidden partial outputs.

### Verify

- [ ] Every C01–C22 required byte is locally retained and digest-verified before the run.
- [ ] Missing corpus data fails rather than skips.
- [ ] The same qualification assertions address all twelve route/depth cells.
- [ ] Each cell has a complete positive pack whose expected result is success and separate negative packs whose expected result may be refusal.
- [ ] Distressed and Deep Research compile from the same registry authority and satisfy explicit analytical contracts.
- [ ] Every supplied file has one disposition; every relevant file reaches analysis/model lineage.
- [ ] Annual, quarterly/interim, forecast, LTM, base, and downside values retain distinct authority and reconcile predictably.
- [ ] Removing or changing each required document class changes or blocks the exact downstream authority named by the answer key.
- [ ] Irrelevant files do not perturb results and are never silently discarded.
- [ ] Bidirectional/control text cannot bypass the boundary into model or deliverable output.
- [ ] Accepted outputs contain no unsupported material claim or unresolved citation.
- [ ] Sparse and conflicting packs produce correct limitations or typed refusals.
- [ ] Prompt injection never changes host authority.
- [ ] The harness records exact candidate/binding identities and makes any failing required cell release-blocking.
- [ ] No scripted provider result is labelled live model qualification.

### Anti-pattern guards

- Do not use `continue-on-error`, skip-on-missing, mutable network bytes, or unsigned answer keys.
- Do not average away one failed route or corpus cell.
- Do not count a refusal-only cell as proof a supported pathway works.
- Do not count a pinned source as used unless its downstream lineage or explicit exclusion is proved.
- Do not force irrelevant or superseded documents into calculations; disposition them explicitly.
- Do not create separate copied suites per provider; parameterize one contract.
- Do not accept generic deterministic summaries as document interpretation.
- Do not qualify the current OpenRouter default from comments or small smoke tests.

### Exit

The no-skip corpus, twelve-cell harness, source-completeness contract, and Distressed/Deep Research contracts are implementation-ready. `ETR-B05`, `ETR-B11`, and `ETR-B12` close only when the final live matrix passes in Phase 7.

## Phase 3 — Deliver the document-first journey and source-complete model

### Objective

Close the gap between the current case/forms/route ceremony and the promised experience: the user supplies documents and CAOS opens the resulting analysis, financial model, and deliverable draft for review.

### Implement

1. Add the minimum server-owned document-intake application service and one thin strict multipart endpoint. It must orchestrate existing domain services; endpoint functions must not call other endpoint functions.
2. Accept one or more source documents as the only analytical fields. Enforce existing upload size, suffix, archive, malware, extraction, normalization, vault, and source-set rules through `ingest_upload` rather than copying them.
3. Stage or mark the case non-runnable until every supplied document has passed admission. A partial failure must leave no runnable analysis, no invisible accepted source, and a complete audit trail.
4. Derive issuer, case label, sector confidence, document types, periods, and pathway fit server-side from prepared evidence. Treat those values as machine suggestions, never as authority supplied by document instructions.
5. Produce the source-disposition and period-coverage manifest during intake, including issuer, document type, reporting/forecast period, revision/supersession status, inclusion/exclusion reason, and downstream analysis/model consumers.
6. Resolve a permitted existing case only when normalized identity and membership rules are unambiguous. Otherwise create a new case. Never merge across cases on model confidence alone.
7. Default the document-first path to Full Credit/full. Select Earnings Update, Covenant & Refinancing, Relative Value, Distressed, or Deep Research only when host-owned classification proves the matching objective and record the reason. Do not ask the user to choose a pathway or depth in the golden journey.
8. Start the run server-side with the pinned source set, methodology, route, budget, and qualified provider identity.
9. Produce the source-grounded financial model from the complete relevant manifest. Full Credit creates the complete model; every other pathway must update or revalidate the model periods, assumptions, scenarios, or risk calculations its declared contract depends on. A pathway must never fabricate an unrelated standalone model.
10. Keep actual annual/quarterly values, management/lender forecasts, analyst base/downside assumptions, derived periods, gaps, overrides, and scenario outputs distinguishable and source-linked. Missing values remain unavailable, never zero-filled or silently interpolated.
11. Return a durable intake/run/model/deliverable status that can survive refresh and restart. Stream progress from the existing persisted run event log.
12. When analysis succeeds, open the review result with the proposed model and draft deliverables. Do not auto-accept the machine conclusion or model assumptions as the analyst's opinion.
13. When the subject or evidence is insufficient, return one typed, actionable clarification/refusal state. Preserve already admitted documents so the analyst can add the missing source without re-entering facts.
14. Replace the current first-run case form and manual Compile-and-run ceremony with a keyboard-accessible drop zone/file picker and clear progress, evidence, model-gap, refusal, and review states.
15. Keep `workspaceAuthority.ts` as the sole frontend stale-response guard. Bind every intake/run response to the current case/source/run generation.
16. Preserve advanced existing APIs for focused tests and internal use, but do not make them required user actions in the enterprise journey.

### Primary files

- `caos/server/caos/sources/domain.py`
- `caos/server/caos/storage/store.py`
- `caos/server/caos/api/__init__.py`
- `caos/server/caos/contracts.py`
- `caos/server/caos/responses.py`
- `caos/server/caos/engine/runtime.py`
- `caos/server/caos/models/service.py`
- `caos/server/caos/models/engine.py`
- `caos/server/caos/deliverables/service.py`
- `caos/frontend/src/components/Workspace.tsx`
- `caos/frontend/src/lib/workspaceAuthority.ts`
- `caos/frontend/scripts/workbench-smoke.mjs`
- Source-ingestion, HTTP-contract, run, evidence, and frontend authority tests

### Documentation references

- `ENTERPRISE_TESTING_READINESS.md`: blocker B01; Test the document-first experience; Test source intake and evidence preparation.
- `PRODUCT.md`: MVP Release Standard.

### Verify

- [ ] A fresh analyst can start with only one or more files and no case form.
- [ ] The server, not the browser, owns case resolution, route selection, source pinning, and run creation.
- [ ] Existing-case resolution never crosses membership or tenant boundaries.
- [ ] Unsafe or partly failed packs cannot become runnable.
- [ ] Six document-only journeys cause host classification to select each of the six pathways without user route selection.
- [ ] Refresh, reconnect, double-submit, back navigation, and stale responses converge on one durable intake/run.
- [ ] The golden journey asks for no source facts, pathway, depth, model, or budget.
- [ ] Success opens a source-grounded review result; insufficiency opens a typed next action.
- [ ] A complete Full Credit pack produces a validated financial model using all relevant annual, quarterly/interim, and forecast sources.
- [ ] Each other pathway updates or revalidates its declared model dependencies and produces no unrelated synthetic model.
- [ ] Every model input, assumption, derived period, calculation, gap, override, and scenario traces to the source-disposition manifest.
- [ ] Machine suggestions are visibly identified and auditable.
- [ ] The analyst is never represented as having accepted or authored the machine output merely by uploading documents.
- [ ] Keyboard, focus, error-summary, zoom, reflow, and reduced-motion behaviour pass.

### Anti-pattern guards

- Do not make a browser chain of create, upload, route, run, and accept the authority transaction.
- Do not duplicate source validation in the new endpoint.
- Do not accept provider, model, hashes, confidence, or route nodes from the browser or document.
- Do not silently merge cases or hide a partial ingest.
- Do not confuse automatic review readiness with human opinion acceptance.

### Exit

`ETR-B01` is closed. UX-001–020 pass through six retained document-first browser journeys and focused server tests. The source-complete model is ready for analyst sign-off and publication.

## Phase 4 — Deliver institutional publication, opinion ownership, and reconstruction

### Objective

Turn machine interpretation into an analyst-owned external work product whose content and presentation are suitable for institutional stakeholders, without losing the distinction between evidence, calculation, machine interpretation, and human opinion.

### Minimum pathway output contract

Every pathway publishes a decision-first report, the relevant model appendix/workbook, and an Evidence & QA Control Sheet from one frozen payload. The product names may evolve, but these contents may not disappear.

| Pathway | Required decision deliverable | Required model content |
|---|---|---|
| Full Credit | Credit Snapshot and committee memo | Historical/quarterly/LTM model, capital structure, base/downside, debt schedule, gaps, and overrides |
| Earnings Update | Earnings update with thesis impact and next decision | Actual-versus-prior/forecast bridge, updated LTM, forecast revisions, and changed assumptions |
| Covenant & Refinancing | Covenant, capacity, liquidity, and refinancing brief | Debt/maturity schedule, covenant headroom, capacity, liquidity runway, and refinancing scenarios |
| Relative Value | Relative-value recommendation with sizing and catalysts | Comparable instruments, spread/price context, scenario value, downside/recovery, and portfolio constraints |
| Distressed | Distress, restructuring, and recovery decision memo | Liquidity runway, claim hierarchy, waterfall/recovery, restructuring scenarios, and control milestones |
| Deep Research | Evidence-led research and decision memo | The source-grounded model/appendices required by the research question, with explicit unknowns and no generic module dump |

### Implement

1. Preserve the existing generated and analyst-authored block types. Add a report-level append-only analyst opinion sign-off containing:
   - exact draft revision and digest;
   - accepted snapshot and source-set identities;
   - selected signed model identity;
   - opinion, limitations, material overrides, and rationale;
   - analyst subject, timestamp, and expected-head CAS.
2. Prevent `ANALYST_JUDGMENT` from carrying unsupported documentary facts. Facts asserted in human narrative must cite evidence or be explicitly framed as judgment/assumption.
3. Require a current opinion sign-off before freeze. Editing the draft, changing evidence/model authority, or superseding the snapshot invalidates the sign-off.
4. Provision a distinct approver through the existing case-membership store/service and one minimal authenticated mutation if needed. Do not build a general administration subsystem.
5. Enforce separation of duties: the filing approver must be authorized for the case and must not be the analyst/opinion signer or freeze actor.
6. Keep freeze and filing separate. Frozen report bytes state `Pending approval` and bind the opinion signer. Filing approval remains digest-bound and exactly once. Record the actual approver, approval time, and filed digest in an immutable detached filing receipt/audit package; never rerender approved bytes merely to insert an approver name.
7. Add external disclosures to browser preview, Markdown, PDF, and XLSX: content origin, sources, limitations, machine assistance, analyst opinion owner, approval state, as-of date, version, and file digest. Ship the detached filing receipt with the approved external package.
8. Ensure every renderer preserves evidence-versus-analyst labels and the source-disposition register. Do not leave origin labels only in the browser preview.
9. Redesign the existing renderer outputs to meet the pinned `e566c1b` institutional benchmark:
   - decision and recommendation first, followed by rationale, winning/losing arguments, key credit facts, risks, catalysts, triggers, next decisions, and supporting appendices;
   - a strong paper masthead with issuer, report type, as-of date, run/version, authority, approval state, and page numbering;
   - readable hierarchy, tabular aligned numerics, restrained signal-only colour, deliberate whitespace/rules, repeated table headers, source register, limitations, and conditional/held watermarks;
   - charts only when they explain trajectory, capacity, valuation, or recovery, each with units, source IDs, accessible summary, and an equivalent table;
   - XLSX cover/control sheet, pathway tables, model/debt/scenario sheets, source audit, gaps/warnings, typed numeric cells, safe text, frozen panes, filters where useful, and no executable content;
   - full Unicode support with no silent character replacement, fixed-line truncation, generic bullet flattening, clipping, or unreadably small print.
10. Render browser, Markdown, PDF, and XLSX from one server-frozen typed content payload. Prove semantic parity for headings, facts, numbers, units, citations, labels, limitations, model identity, and opinion across formats.
11. Replace plain critical `write_bytes` publication with the existing hash-addressed atomic publication and verified-read pattern.
12. Keep filed downloads byte-for-byte identical to the approved stored payload. Never rerender on download.
13. Add approved cross-format goldens for representative normal, dense, long-text, multilingual, held, and filed states. Inspect every affected PDF page and XLSX sheet. Run the per-pathway blind rubric review by two credit analysts and one external-stakeholder reviewer once on the frozen Phase 7 candidate; material inferiority in hierarchy, legibility, print fidelity, evidence clarity, or decision usefulness fails the gate.
14. Add missing governed audit events for source scanning/extraction, relevance disposition, evidence reads, provider activity, preview, rebase, sign-off, freeze, export, approval, filing, download, and typed refusals.
15. Make audit storage append-only at the database boundary and add a hash-linked sequence or equivalent integrity proof that detects mutation, deletion, insertion, and reordering.
16. Add one case-scoped audit-package builder containing manifests and bounded metadata for sources/dispositions, route/plan, evidence reads, provider attempts, artifacts, snapshots, models, report revisions, opinion sign-off, approval receipt, filed bytes, methodology, runtime, and environment.
17. Add an offline verifier that checks all digests, links, ordering, authorities, and exact filed bytes without a running application and without secrets or hidden reasoning.
18. Add authenticated API routes only if the product needs to download the package or audit view. Admin Studio was removed in Phase 0 and must not return as a placeholder.

### Primary files

- `caos/server/caos/contracts.py`
- `caos/server/caos/deliverables/service.py`
- `caos/server/caos/storage/deliverables.py`
- `caos/server/caos/publishing/renderers.py`
- `caos/server/caos/storage/store.py`
- `caos/server/caos/storage/runs.py`
- `caos/server/caos/api/__init__.py`
- `caos/frontend/src/components/report/ReportStudio.tsx`
- `caos/frontend/src/components/report/DeliverableDocument.tsx`
- `caos/frontend/src/components/Workspace.tsx`
- Existing model, deliverable, audit, HTTP, and browser tests

### Documentation references

- `ENTERPRISE_TESTING_READINESS.md`: Test analytical interpretation and opinion ownership; Test report authoring and external publishing; Test machine-output auditability.
- `CONTEXT.md`: model and deliverable language.
- `docs/DECISIONS.md`: append-only revisions, authority, and exact publication decisions.
- Credit Operating System [`DESIGN.md`](https://github.com/EricMG13/Credit-Operating-System/blob/e566c1b78e0e7a35b2cd854b26f8d4f3e8a4f53a/DESIGN.md), [`ReportDoc.tsx`](https://github.com/EricMG13/Credit-Operating-System/blob/e566c1b78e0e7a35b2cd854b26f8d4f3e8a4f53a/caos/frontend/src/components/reports/ReportDoc.tsx), [`builders.ts`](https://github.com/EricMG13/Credit-Operating-System/blob/e566c1b78e0e7a35b2cd854b26f8d4f3e8a4f53a/caos/frontend/src/lib/reports/builders.ts), and [`report_exports.py`](https://github.com/EricMG13/Credit-Operating-System/blob/e566c1b78e0e7a35b2cd854b26f8d4f3e8a4f53a/caos/server/report_exports.py): content hierarchy and presentation patterns only; never copy seeded data or fallback behaviour.

### Verify

- [ ] Machine interpretation, sourced fact, deterministic calculation, analyst judgment, assumption, and limitation remain distinguishable in storage, API, UI, and every export.
- [ ] A stale or mismatched analyst sign-off cannot freeze.
- [ ] The opinion signer cannot approve/file the same output.
- [ ] A normal governed workflow can provision and use a distinct approver without direct database seeding.
- [ ] Exactly one concurrent filer wins and the loser receives a typed conflict.
- [ ] Filed downloads equal the approved bytes and fail on tampering.
- [ ] Approver identity verifies in the detached filing receipt/package while the approved report bytes remain unchanged.
- [ ] Every pathway produces its decision report, relevant model appendix/workbook, and Evidence & QA Control Sheet from one frozen payload.
- [ ] Browser, Markdown, PDF, and XLSX are semantically equivalent and contain no generic filler, silent truncation, missing glyphs, clipping, overlap, orphan headings, split headers, stale values, or lost citations.
- [ ] Numeric formats, units, signs, nulls, estimates, actuals, forecasts, scenarios, and source locators follow one tested convention.
- [ ] Visual regression and blind rubric review meet or exceed the pinned benchmark on every critical criterion.
- [ ] Editing any bound authority invalidates downstream sign-off/approval.
- [ ] Audit insertion, update, deletion, and reordering are detected.
- [ ] The offline verifier reconstructs sampled claims and bytes from the package.
- [ ] The package contains no secret, hidden reasoning, unauthorized full source, or raw provider error body.
- [ ] An independent analyst and auditor can follow the result without application-team help.

### Anti-pattern guards

- Do not mix machine output and analyst opinion into an unlabeled narrative.
- Do not use `ANALYST_JUDGMENT` as a citation bypass.
- Do not let the same subject sign and approve.
- Do not rerender after approval or write frozen bytes non-atomically.
- Do not copy the benchmark's seeded issuer facts, browser-owned composition, tiny 5–6px appendix type, or reference-data fallback.
- Do not use pixel similarity as a substitute for source truth, semantic parity, accessibility, and stakeholder review.
- Do not append audit asynchronously after the governed state transaction.
- Do not equate raw prompt logging with auditability.

### Exit

G7 and G8 pass for focused tests. Publishing and audit reconstruction are ready for the final candidate journey.

## Phase 5 — Prove PostgreSQL concurrency, stress, and failure safety

### Objective

Close durability and failure-under-load gaps under the declared single-instance topology without implementing production scaling.

### Implement

1. Reuse the digest-pinned PostgreSQL CI container/network setup to add a pytest target using two genuinely independent database connections.
2. Port the existing exactly-one-winner patterns to:
   - duplicate and concurrent source ingestion;
   - source-set allocation and withdrawal;
   - assumption/model revision and sign-off;
   - run acceptance;
   - draft save/freeze;
   - opinion sign-off and filing.
3. Prove database serialization for run-event sequence allocation, budget reserve/reconcile, snapshot acceptance, model/deliverable/opinion revisions, sign-off, freeze, and filing. The loser must receive a typed retry/conflict, never a raw integrity error or divergent state.
4. Preserve SQLite unit tests and compiled `FOR UPDATE` checks as fast mechanism tests, but never label them PostgreSQL behavioural proof.
5. Eliminate unclosed SQLite/aiosqlite connections, file handles, and worker resources before load testing. A soak with leak warnings or monotonically growing orphan state fails.
6. Map SIM-001–030 to existing kill-after-module, commit-gap, unresolved-spend, stale-worker, renderer-tamper, and browser-route injection seams before creating new fault hooks.
7. Add only missing simulations for checkpoint absent/truncated/locked/corrupt, disk-full writes, database disconnect-after-ack, scanner/IdP outage, LibreOffice hang, repeated restart loop, and audit-package interruption. Qualify paused/in-flight checkpoint recovery; terminal checkpoint cleanup already exists and should remain.
8. Use focused development faults for the changed path. Repeat the route-balanced six-pathway saturated workload only in the protected candidate run.
9. After every simulation, assert one valid final state across domain data, checkpoints, files, budget, events, audit, and user-visible status both before and after restart.
10. Enforce the single application instance with an exclusive operating-system lock on the durable checkpoint location or an equally small native guard. A second instance must fail startup clearly before serving traffic.
11. Record the one-app/one-worker ceiling in the environment manifest and verify Compose creates exactly that topology.
12. Repair and prove backup/restore for: a fresh database before lazy model tables exist; vault discovery without Compose-label dependence or silent omission; and one documented consistent snapshot point across PostgreSQL, checkpoint/WAL, and vault bytes.
13. Rerun encrypted backup, restore, paused/in-flight recovery, and candidate-data reset under active writes using the exact enterprise-test image and schema.

### Primary files

- Existing storage and spec tests
- `caos/server/caos/storage/store.py`
- `caos/server/caos/storage/models.py`
- `caos/server/caos/storage/deliverables.py`
- `caos/server/caos/storage/runs.py`
- `caos/server/caos/engine/runtime.py`
- `caos/server/run.py`
- `caos/server/worker.py`
- `caos/deploy/docker-compose.yml`
- `caos/deploy/backup.sh`
- `caos/deploy/restore_drill.sh`
- `.github/workflows/ci.yml`

### Documentation references

- `ENTERPRISE_TESTING_READINESS.md`: blockers B07 and B10; Run failure and concurrency simulations; Test the declared enterprise profile.
- `SPEC_RECONCILIATION.md`: D3 PostgreSQL deferral and ten invariants.

### Verify

- [ ] Every required PostgreSQL race uses two independent connections.
- [ ] Exactly one winner commits, and state plus audit agree.
- [ ] Every SIM-001–030 result is retained with injected fault, expected outcome, actual outcome, and post-restart state.
- [ ] Event, budget, acceptance, model, draft, opinion, freeze, and filing races have database-enforced one-winner results.
- [ ] No stress/simulation run leaks a database connection, file handle, worker permit, job, or checkpoint authority.
- [ ] Unknown provider spend never retries and double-spends.
- [ ] Partial files, state, events, and approvals never masquerade as complete.
- [ ] A second app instance cannot acquire the checkpoint authority.
- [ ] One app and one worker recover queued and in-flight work under the documented topology.
- [ ] Backup/restore and clean reset preserve or remove exactly the declared data.
- [ ] Fresh-schema, label-independent vault discovery, and cross-store snapshot consistency drills pass under active writes.
- [ ] Faults under a saturated six-pathway workload remain typed, bounded, auditable, and restart-safe.
- [ ] All ten engine invariants pass against PostgreSQL where the invariant depends on database behaviour.

### Anti-pattern guards

- Do not implement a distributed checkpointer, shared app fleet, or high-availability control plane.
- Do not use thread races against one SQLite connection as PostgreSQL evidence.
- Do not assert only the HTTP result; verify database, checkpoint, files, events, budgets, and audit.
- Do not retry an operation whose provider spend or publication result is unknown.

### Exit

`ETR-B07` and `ETR-B10` are closed. G6 passes under the declared enterprise-test topology.

## Phase 6 — Prove security, identity, browser, accessibility, and capacity

### Objective

Run the completed journey through the actual enterprise perimeter and client matrix, then prove the environment is safe and repeatable enough for controlled testing.

### Implement

1. Extend `run_sec_audit.py` from unauthenticated and spoofed-role checks to the full role, case-membership, cross-case, and object-level authorization matrix discovered from OpenAPI.
2. Test the actual Caddy, oauth2-proxy, identity claims, secure cookies, logout, expired session, revoked membership, and IdP-outage behaviour using enterprise test accounts.
3. Exercise upload and prompt-injection controls with C01–C22, including Unicode/confusables, archive bombs, macros/external links, formula injection, fake system messages, encoded instructions, and exfiltration attempts.
4. Replace the current unsafe/unexecuted AI pull-request review with a protected, read-only recorded review or equivalent control. It must not expose a secret or write token to untrusted diff instructions, and its non-vacuity must be testable.
5. Retain non-empty SAST, dependency, secret, workflow, container, and image scan results. Produce an SBOM and bind it to the candidate image digest.
6. Pin mutable scanner images/actions and record exceptions. High or critical integrity, authorization, data-loss, audit, or publication findings block the candidate.
7. Parameterize the existing Playwright journey for Chromium, Firefox, and WebKit. Add structured reports and traces/screenshots on failure using the installed framework.
8. Replace source-regex assertions with rendered behavioural tests only where the enterprise guarantee is otherwise unproved. Keep useful structural tripwires as mechanism tests.
9. Run WCAG 2.1 AA automation plus keyboard-only, focus, zoom/reflow, screen-reader, status announcement, and reduced-motion manual checks over empty, loading, populated, error, refusal, review, and filed states.
10. Keep limit-boundary tests in development. Run the full declared `PERF-001–015` profile—25 authenticated subjects, 20 active mixed-pathway jobs, four streams and two previews per subject, 300 requests per subject/minute, 100 cases × 100 retained documents, 25 MB sources, 32 MB requests, and every configured maximum model/evidence/report shape—only as protected candidate evidence.
11. For each admission and size limit, run one below, exactly at, and one above. Above-limit work must refuse before consuming provider/worker capacity and must not degrade other subjects.
12. Run the route-balanced mixed workload covering all six pathways and both depths only as protected candidate evidence; retain latency, throughput, CPU, memory, database connections, open handles, checkpoint/vault growth, provider usage, success/refusal counts, and error classifications.
13. Run the eight-hour soak with restart and reconnect events only on the candidate. Repeat all six documents-only journeys afterward and compare authorities, model hashes, filed bytes, and offline reconstruction with the pre-soak baseline.
14. Prove deterministic reset, declared retention, and tenant/case isolation between enterprise test cycles.

### Primary files

- `run_sec_audit.py`
- `.github/workflows/ci.yml`
- `.github/workflows/nightly.yml`
- `.github/workflows/security-review.yml`
- `caos/deploy/Caddyfile`
- `caos/deploy/oauth2-proxy.cfg`
- `caos/deploy/docker-compose.yml`
- Existing upload/security tests
- `caos/frontend/scripts/workbench-smoke.mjs`
- `caos/frontend/scripts/a11y-axe.mjs`
- Frontend rendered tests

### Documentation references

- `ENTERPRISE_TESTING_READINESS.md`: blocker B06; Test identity, authorization, and tenant isolation; Test application and artificial-intelligence security; Test browser, accessibility, and compatibility; Test the declared enterprise profile.
- `PRODUCT.md`: WCAG 2.1 AA target and interaction principles.

### Verify

- [ ] Every discovered protected route enforces identity before validation and correct case/object authority afterward.
- [ ] Header spoofing, IDOR, revoked membership, cross-case reads/writes, and role escalation fail closed.
- [ ] IdP/scanner/provider outages do not bypass controls or leak data.
- [ ] Prompt injection cannot change host instructions, tools, evidence scope, model, budget, approval, or publication.
- [ ] Security scanners prove non-empty scope and retain candidate-bound results.
- [ ] The protected AI/diff review cannot expose secrets or write through untrusted input.
- [ ] Chromium, Firefox, and WebKit pass all six documents-only journeys and their review/publication states.
- [ ] Automated and manual accessibility checks pass all material states.
- [ ] Capacity and soak stay within predefined thresholds with no cross-case leakage, orphan authority, or audit loss.
- [ ] Below/at/above limit behavior is exact; saturation faults remain typed and do not cause collateral denial of service.
- [ ] The post-soak six-pathway results, model identities, deliverable bytes, and audit reconstructions match the pre-soak authority baseline.
- [ ] The enterprise profile resets and repeats from a clean state.

### Anti-pattern guards

- Do not treat frontend role visibility as authorization.
- Do not activate the existing AI review unchanged.
- Do not accept a green scanner that scanned nothing.
- Do not add a second browser framework.
- Do not claim production capacity, uptime, or high availability from enterprise-test measurements.

### Exit

`ETR-B06` is closed. G1, G5, and G9 pass in the declared enterprise environment.

## Phase 7 — Qualify and sign one candidate

### Objective

Run the already-built gates against one immutable candidate and retain enough evidence for independent review. Phase 7 contains no new product implementation.

### Implement

1. Build application and worker images once. Record commit, clean/dirty state, image digests, dependency locks, SBOM, runtime versions, and enterprise topology.
2. Freeze the corpus manifest, qualified provider binding, methodology manifest, environment manifest, expected performance envelope, and test inventory before the candidate run.
3. Execute the previously built deterministic CI, corpus host controls, final `one binding × six pathways × two depths × required packs × three cold repetitions` live matrix, PostgreSQL races, mapped SIM-001–030 evidence, three-browser journeys, accessibility, security, performance, saturation faults, eight-hour soak, reset, backup/restore, deliverable benchmark review, and audit reconstruction against those exact identities. Do not create a second release-only implementation or test framework.
4. Run six golden journeys from documents through source-disposition review, pathway execution, model creation/update, deliverable review, analyst opinion sign-off, separate approval, exact filed download plus filing receipt, and offline audit verification.
5. Conduct REV-001–015 with independent analysts, model risk, security, accessibility, external-stakeholder, audit, operations, and enterprise-test reviewers.
6. Adjudicate every finding. Rerunning after a code, corpus, model-policy, image, methodology, or environment change creates a new candidate; do not mix results.
7. Assemble the immutable evidence package listed in `ENTERPRISE_TESTING_READINESS.md`, hash the package, and obtain enterprise test-owner sign-off.
8. Update `docs/QUALITY_LEDGER.csv`, `docs/QUALITY_DEFECTS.csv`, `SPEC_RECONCILIATION.md`, and the blocker table only from retained candidate evidence.

### Documentation references

- `ENTERPRISE_TESTING_READINESS.md`: Apply release gates; Review the application manually; Produce a release evidence package; Enforce release exit criteria.
- `CLAUDE.md`: ten binding engine invariants.

### Verify

- [ ] G0–G9 pass on the same commit, image, provider binding, corpus, methodology, and environment.
- [ ] All 340 checks and simulations map to a retained result; no required item is skipped, waived, flaky, not run, or unknown.
- [ ] All thirteen blockers show evidence-backed closure.
- [ ] All ten engine invariants pass.
- [ ] Every selectable model passes; the MVP exposes only the sole passing binding.
- [ ] All twelve route/depth cells succeed on complete positive packs; designated negative packs refuse exactly as specified.
- [ ] Every supplied document has an auditable disposition and every relevant annual, quarterly/interim, forecast, and forecast-revision file reaches the accepted analysis/model lineage.
- [ ] The documents-only journey for each of the six pathways passes in all three browsers.
- [ ] Every pathway's report, model appendix/workbook, Evidence & QA Control Sheet, and filing receipt pass semantic, visual, accessibility, integrity, and blind benchmark review.
- [ ] SIM-001–030, two-connection races, below/at/above limits, failure under saturation, the eight-hour soak, recovery, and reset all have retained passing evidence.
- [ ] Independent analysts approve every required golden route/depth result.
- [ ] No critical or high security/integrity defect is open.
- [ ] The independent offline reconstruction succeeds for every pathway/depth sample and every filed format without application-team help.
- [ ] The evidence package digest and test-owner signature verify.

### Anti-pattern guards

- Do not combine evidence from different commits, images, corpus versions, model policies, or environments.
- Do not waive a core gate.
- Do not label a typed refusal as failure when the answer key requires refusal; do not label a missing test as refusal.
- Do not promote the enterprise-testing result to production approval.

### Exit

The enterprise test owner signs the candidate evidence manifest. The MVP is enterprise-testing ready and nothing more is implied.

## Final verification commands

Run the exact locked commands from the candidate workflow. The current command baseline is:

```bash
python -m ruff check --config ruff.toml caos/server caos/tests --exclude caos/server/caos/methodology/vendor
python run_sec_audit.py
python docs/quality_ledger_coverage.py
python -m pytest caos/tests -q -W always

cd caos/frontend
npm ci
npm run lint
npx tsc --noEmit
npm run test:unit
npm run build
npm run test:workbench
npm run a11y
```

The completed candidate workflow must add protected invocations for the digest-verified annual/quarterly/forecast corpus, final six-pathway live qualification, source-completeness/metamorphic tests, two-connection PostgreSQL tests, SIM-001–030, three browsers, deliverable semantic/visual inspection and blind review, enterprise identity/scanner profile, failure-under-load, performance/soak, backup/restore, audit reconstruction, and evidence-package verification. Those commands must come from checked-in scripts or workflow steps rather than a hand-executed release checklist.

## Blocker closure map

| Blocker | Closing phase | Required evidence |
|---|---|---|
| ETR-B01 | Phase 3 | Documents-only browser journey and focused intake authority tests |
| ETR-B02 | Phase 1 | No picker; one qualified binding pinned at run creation |
| ETR-B03 | Phase 1 | OpenRouter/GLM excluded from the enterprise profile until full independent qualification |
| ETR-B04 | Phase 1 | Actual provider/model identity on attempts, outputs, and audit |
| ETR-B05 | Phase 7 | Digest-pinned approved corpus with answer keys and no required skip in the final live matrix |
| ETR-B06 | Phase 6 | Protected recorded review/equivalent with tested untrusted-input safety |
| ETR-B07 | Phase 5 | Two-connection PostgreSQL race results |
| ETR-B08 | Phase 0 | OpenAPI/UI-generated current inventory |
| ETR-B09 | Phase 1 | OpenRouter excluded from the initial enterprise profile; shape proof required before later admission |
| ETR-B10 | Phase 5 | Enforced single instance plus restart/corruption evidence |
| ETR-B11 | Phase 7 | Distressed and Deep Research contracts plus successful route/model/publication/audit qualification |
| ETR-B12 | Phase 7 | Complete source-disposition and annual/quarterly/forecast lineage proof |
| ETR-B13 | Phase 7 | Every pathway and format passes the pinned institutional benchmark rubric |

## Work deliberately excluded

Do not add these to the MVP plan unless the enterprise-testing standard changes:

- Multiple simultaneous application instances
- Distributed or PostgreSQL LangGraph checkpoints
- Multi-region deployment or disaster-recovery service levels
- Production rollout, rollback, or tenant-migration automation
- Automated external email, portal, or data-room delivery
- User-selectable LLM/provider bindings beyond the first independently qualified binding
- Raw prompt, chain-of-thought, or provider-body retention
- New test frameworks where pytest and the installed Playwright library already cover the need
