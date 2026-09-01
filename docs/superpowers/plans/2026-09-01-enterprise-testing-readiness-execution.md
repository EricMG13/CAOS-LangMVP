# Enterprise-Testing Readiness Execution Plan

> **For Codex:** Execute this plan task by task with `subagent-driven-development`. Use a fresh implementer and a fresh reviewer for each task, keep `.superpowers/sdd/progress.md` current, and run `rewrite-tournament` plus `confidence-review` when their trigger conditions apply.

**Goal:** Make the MVP enterprise-testing ready: a user uploads a complete issuer source pack, CAOS runs every one of the six governed pathways with the sole qualified machine-generation binding, produces source-complete analysis and a financial model, lets an analyst own the opinion, publishes institutional deliverables through a separate approver, and retains enough immutable evidence to reconstruct every machine-produced output.

**Architecture:** Keep the existing strict FastAPI contracts, `Provider` port, static route compiler, source vault, run/model/deliverable stores, canonical `document_sections`, renderer seam, and frontend authority reducer. Extend those seams in dependency order. Do not add a second workflow engine, route catalog, provider framework, renderer lifecycle, or test framework.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy/SQLite/PostgreSQL, LangGraph, pytest, Ruff, Next.js 16, React 19, TypeScript, Node 24, Playwright, Docker Compose, existing CI/nightly workflows.

**Authoritative baseline:** `main` commit `ba97a89899440532686b08050127d48db9a509b9` on 2026-09-01. Development evidence: Ruff passes; backend `655 passed, 2 skipped, 864 warnings`; full retained corpus host control `34 passed, 124 warnings`; module consistency `26 modules, 0 drift`; bundle `7 passed`; frontend lint/typecheck/unit (`113 passed`), build, and workbench browser journey pass. Release gates are red: `run_sec_audit.py` has 10 failures and `docs/quality_ledger_coverage.py` has 10 failures. This evidence is not candidate qualification.

---

## Global constraints

- Enterprise-test scope is all six pathways at supported depths: Full Credit, Earnings Update, Covenant & Refinancing, Relative Value, Distressed & Restructuring, and Deep Research.
- Source admission is user-upload only. No EDGAR, SEC-fetch, web-acquisition, or implicit external-document tool may exist in runtime methodology or tests.
- The golden user journey takes source documents as its only analytical input. Human acceptance, opinion sign-off, and approver filing remain explicit governance actions.
- The enterprise profile exposes exactly one qualified provider/model/policy binding and never falls back.
- A deterministic path may calculate, validate, canonicalize, or render. It may not emit generic analysis and call it successful.
- Every supplied document receives a governed disposition. Every relevant annual, quarterly/interim, forecast, and forecast-revision document reaches accepted analysis/model lineage.
- Scripted providers and golden fixtures are host controls only; they never count as live-model qualification.
- A required gate fails on missing bytes, credentials, environment, answer keys, reviewers, or retained results. It does not skip or waive.
- Do not claim production readiness. The terminal claim is enterprise-testing ready for one controlled candidate.

## Task 1: Restore a truthful green development baseline

**Files:**
- Modify: `run_sec_audit.py`
- Modify: `docs/QUALITY_LEDGER.csv`
- Modify: `docs/quality_ledger_coverage.py`
- Modify: `.github/workflows/nightly.yml`
- Modify: `CLAUDE.md`
- Modify: `ENTERPRISE_READINESS_PLAN.md`
- Modify: `docs/superpowers/plans/2026-08-31-legacy-builder-core-adaptation.md`
- Test: `caos/tests/spec/test_model_builder_spec.py`
- Test: `caos/tests/spec/test_observability_spec.py`

**Step 1 — Preserve the failing baseline.** Run `python run_sec_audit.py` and `python docs/quality_ledger_coverage.py`; retain the exact 10 + 10 failures in the task report.

**Step 2 — Repair the security audit contract.** Add valid minimal request bodies for rebase preview, tornado, and one-way sensitivity so foreign-case membership and reader-write authorization are reached before schema validation. Keep the body-probe drift assertion exact.

**Step 3 — Repair ledger coverage.** Map the eight served model/model-revision routes to the existing model feature rows and map `draft-history-smoke.mjs` plus `identity-a11y.mjs` to the existing UI/operations features. Do not weaken route/file discovery or exclude the new surfaces.

**Step 4 — Align supported runtimes.** Change nightly Python 3.11 to Python 3.14, matching the supported/tested baseline; retain Node 24.

**Step 5 — Refresh documentation.** Mark the legacy builder Tasks 1–7 implemented at `ba97a89`, replace stale unserved-route claims, record the exact baseline and open warnings, keep Admin Studio as an honest unavailable capability, and state that all six-pathway enterprise qualification remains open.

**Step 6 — Verify.** Run the two repaired gates, Ruff, targeted model/observability tests, frontend unit tests, and YAML syntax/loading. Expected: zero audit/ledger failures and no new skips.

## Task 2: Remove every external filing and peer-discovery acquisition dependency

**Files:**
- Modify: `caos/server/caos/methodology/vendor/deploy_v/skills/cp-4-legal-covenant-interpreter/SKILL.md`
- Modify: `caos/server/caos/methodology/vendor/deploy_v/skills/cp-4-legal-covenant-interpreter/references/CP-4_RUNBOOK.md`
- Modify: `caos/server/caos/methodology/vendor/deploy_v/skills/cp-4-legal-covenant-interpreter/references/REF_CP-4B_STEPS.md`
- Modify: `caos/server/caos/methodology/vendor/deploy_v/skills/cp-4-legal-covenant-interpreter/references/REF_CP-4_STEPS.md`
- Modify: `caos/server/caos/methodology/vendor/deploy_v/CANON_SHARED.md`
- Modify: deployed `cp-1c-peer-benchmark` skill and references to require supplied peer evidence only
- Modify: vendored bundle manifest/digests through `caos/scripts/regenerate_deploy_v_integrity.py`
- Add: `caos/scripts/regenerate_deploy_v_integrity.py` because the distributed package omits its original builder
- Modify: `docs/quality_ledger_coverage.py` to map the replacement command to existing methodology-integrity features
- Test: `caos/tests/test_bundle.py`
- Test: `caos/tests/spec/test_modules_spec.py`
- Modify: `caos/server/caos/modules/registry.py` only for the regenerated CP-1C assembled-authority pin
- Test: add the smallest tracked-text prohibition test beside the bundle tests

**Step 1 — Add a failing prohibition test.** Assert the deployed methodology and tracked product text contain no EDGAR name, SEC retrieval endpoint, `EDGAR_USER_AGENT`, `/api/edgar`, agent acquisition instruction, or CP-1C peer-discovery/scraping lane. Exclude immutable issuer PDF bytes only.

**Step 2 — Delete the acquisition lanes.** Remove the EDGAR reference section and every instruction that asks an agent to search, fetch, or vault external filings. Remove the shared CP-1C public-web exception and all deployed peer-discovery/scraping instructions. Preserve CP-1C benchmarking with analyst-uploaded lists or peers disclosed in supplied evidence; absent or insufficient peer evidence produces a typed gap and limited or blocked status.

**Step 3 — Regenerate integrity metadata.** The distributed package does not ship its original builder. Use the minimal stdlib `caos/scripts/regenerate_deploy_v_integrity.py` replacement; never hand-edit a digest without regenerating its preimage.

**Step 4 — Verify.** Run the prohibition test, module consistency, bundle verification, methodology specs, and a repository search. Expected: zero forbidden references and zero bundle drift.

## Task 3: Remove build-time external font dependence

**Files:**
- Modify: `caos/frontend/app/layout.tsx`
- Modify: `caos/frontend/app/globals.css`
- Test: `caos/frontend/src/lib/workbench.test.ts`
- Test: `caos/frontend/scripts/workbench-smoke.mjs`

**Step 1 — Add a failing source/build assertion.** Prove no `next/font/google`, `fonts.googleapis.com`, or `fonts.gstatic.com` dependency remains.

**Step 2 — Use native font stacks.** Remove the three Google font imports and bind the existing sans/display/mono CSS variables to OS-native stacks. Preserve current typography hierarchy and accessible sizing.

**Step 3 — Verify offline.** Run lint, TypeScript, unit tests, and `npm run build` with outbound network unavailable. Run the workbench browser smoke and record FCP/DCL.

## Task 4: Close development resource leaks before stress work

**Files:**
- Modify: the shared pytest fixtures in `caos/tests/conftest.py` and `caos/tests/spec/conftest.py`
- Modify: source-upload tests only where they own upload handles
- Modify: store/app lifecycle code only when a warning reproduces outside a test-owned fixture
- Test: add one focused lifecycle regression test in the owning test file

**Step 1 — Classify warnings by owner.** Run the full suite and corpus suite with `-W always`, group warnings into database engine/connection, aiosqlite saver, upload temporary file, deprecation, and third-party noise. Trace each first-party resource to its creator and shutdown owner.

**Step 2 — Add one failing lifecycle check per root cause.** Prefer fixing shared fixture/application teardown once over closing resources in every test.

**Step 3 — Implement bounded cleanup.** Close SQLAlchemy engines, async savers, TestClients/apps, and upload streams through their existing lifecycle APIs. Do not suppress `ResourceWarning`.

**Step 4 — Verify.** Run targeted tests with `-W error::ResourceWarning`, then the full suite and corpus suite. Expected: zero first-party resource leaks; separately document unavoidable third-party deprecations.

## Task 5: Pin truthful provider authority and remove false success

**Files:**
- Modify: `caos/server/caos/engine/provider.py`
- Modify: `caos/server/caos/engine/anthropic.py`
- Modify: `caos/server/caos/engine/openrouter.py`
- Modify: `caos/server/caos/engine/runtime.py`
- Modify: `caos/server/caos/engine/loop.py`
- Modify: `caos/server/caos/config.py`
- Modify: `caos/server/run.py`
- Modify: `caos/server/caos/storage/runs.py`
- Modify: `caos/server/caos/responses.py`
- Test: provider, runtime, evidence, budget, observability, and HTTP contract tests

**Step 1 — Specify immutable identity.** Add failing tests for provider name, exact model, provider version when supplied, adapter version, parameter/context digest, and qualification-record digest on run creation, attempts, artifacts, snapshots, and API responses.

**Step 2 — Implement one identity value on the existing Provider port.** Both adapters expose it; runtime reads it once at run creation. Remove hard-coded Anthropic-model attribution from OpenRouter paths.

**Step 3 — Remove generic successful analysis.** In enterprise mode, an agent-designated module with agent execution disabled, absent credentials, mismatched identity, or missing qualification returns a typed refusal. Deterministic calculation/validation modules remain.

**Step 4 — Enforce one binding.** Enterprise startup accepts only the selected qualified Anthropic binding for the initial candidate; OpenRouter remains development-only until separately qualified. No picker or fallback is added.

**Step 5 — Verify.** Run provider matrix host controls, runtime/budget/evidence tests, strict response tests, security audit, and full backend suite.

## Task 6: Execute Distressed & Restructuring end to end

**Files:**
- Modify: `caos/server/caos/engine/runtime.py`
- Modify: `caos/server/caos/modules/registry.py`
- Modify: methodology route/profile data only through its canonical registry/build process
- Modify: `caos/server/caos/api/__init__.py`
- Modify: `caos/frontend/src/components/Workspace.tsx`
- Test: `caos/tests/spec/test_runs_spec.py`
- Test: `caos/tests/test_corpus_pathways.py`
- Test: deliverable/model/browser specs

**Step 1 — Add failing full and screen route tests.** Require compile, start, evidence pin, module completion, acceptance, model revalidation/update, deliverable draft/freeze/file, and reconstruction identity.

**Step 2 — Add only missing module contracts.** Reuse the static compiler and existing deterministic/agent module registry. No Distressed-specific orchestration engine.

**Step 3 — Expose availability from runtime truth.** Add Distressed to the canonical available set only when both depths and downstream contracts pass.

**Step 4 — Verify with a designated positive stressed pack.** A complete positive pack succeeds; sparse/legal-gap packs return answer-keyed typed refusals.

## Task 7: Execute Deep Research with a governed brief and approval gate

**Files:**
- Modify: `caos/server/caos/contracts.py`
- Modify: `caos/server/caos/storage/runs.py`
- Modify: `caos/server/caos/engine/runtime.py`
- Modify: `caos/server/caos/api/__init__.py`
- Modify: `caos/server/caos/responses.py`
- Modify: `caos/frontend/src/components/Workspace.tsx`
- Test: run/HTTP/research-plan/browser specs

**Step 1 — Add failing persistence tests.** The validated research brief, digest, proposed deterministic plan, approval hash, actor, and timestamp survive restart and are bound into run authority.

**Step 2 — Forward and persist the brief.** Remove the current API discard. Reject a missing/full-depth-incompatible brief before run creation.

**Step 3 — Implement the existing UI’s approval contract.** Add case-authorized read/approve endpoints with expected-hash CAS; resume only the exact approved plan.

**Step 4 — Enable Deep Research only after the route passes.** Update the one runtime availability set and remove hard-coded `deep_research_available: false`.

**Step 5 — Verify.** Positive question-specific packs succeed; ambiguous, injection-bearing, and insufficient packs follow answer-keyed refusal/limitation behavior.

## Task 8: Make document upload the complete analytical journey

**Files:**
- Modify: `caos/server/caos/sources/domain.py`
- Modify: `caos/server/caos/storage/store.py`
- Modify: `caos/server/caos/api/__init__.py`
- Modify: `caos/server/caos/contracts.py`
- Modify: `caos/server/caos/responses.py`
- Modify: `caos/server/caos/engine/runtime.py`
- Modify: `caos/frontend/src/components/Workspace.tsx`
- Modify: `caos/frontend/src/lib/workspaceAuthority.ts`
- Test: ingestion, source-completeness, intake transaction, and browser tests

**Step 1 — Specify one strict multipart intake transaction.** Multiple uploaded files are the only analytical fields. Partial admission never creates a runnable partial case.

**Step 2 — Build a server-owned source manifest.** Classify issuer, document type, period, forecast/revision status, and pathway fit; record `used`, `superseded`, `conflicting`, `out_of_scope`, or `insufficient` with bounded reasons.

**Step 3 — Select the route server-side.** Default to Full Credit/full and select another route only from host-owned evidence classification. The golden UI has no pathway/model/provider picker.

**Step 4 — Persist progress and recovery.** Reuse run events and frontend generation fencing so refresh/restart returns to the same intake/run/model/deliverable authority.

**Step 5 — Verify 20–30-document cases.** Test success, partial failure, duplicate, wrong issuer, scanned/no-text refusal, restatement, conflict, and add-missing-source recovery.

## Task 9: Prove source-complete modelling for all pathways

**Files:**
- Modify: `caos/server/caos/models/service.py`
- Modify: `caos/server/caos/models/engine.py`
- Modify: model storage/contracts/responses
- Modify: model builder/report studio only for new truthful states
- Test: CP-MODEL specs, corpus lineage tests, metamorphic tests

**Step 1 — Define pathway model effects.** Full Credit builds the complete model. Earnings updates periods/forecast variance, Covenant updates covenant/refinancing assumptions, Relative Value attaches time-aligned market marks, Distressed updates scenarios/recovery, and Deep Research revalidates or declares no numeric effect.

**Step 2 — Require complete relevant-source lineage.** Every used annual, quarterly/interim, forecast, and revision source reaches model inputs, assumptions, calculations, or cited analysis. Every non-used document has an explicit disposition.

**Step 3 — Add metamorphic proof.** Remove/change each relevant document class and assert the expected fingerprint, assumption, output, limitation, or refusal change; irrelevant files must not perturb results.

**Step 4 — Verify.** Run all six route/depth host controls and the protected live qualification subset; no source-complete claim may rely on `run_scripted_for_tests`.

## Task 10: Complete opinion ownership, publication, and reconstruction

**Files:**
- Modify: `caos/server/caos/deliverables/service.py`
- Modify: `caos/server/caos/storage/deliverables.py`
- Modify: `caos/server/caos/publishing/renderers.py`
- Modify: `caos/server/caos/api/__init__.py`
- Modify: `caos/frontend/src/components/report/*`
- Create: a case-authorized audit-package exporter and standalone verifier under existing server/QA namespaces
- Test: deliverable, authorization, atomic-file, renderer, browser, and offline reconstruction tests

**Step 1 — Bind analyst opinion.** Store exact reviewed preview digest, analyst identity, opinion text/status, and expected-head CAS before freeze.

**Step 2 — Keep approver separation.** A distinct authorized approver files the exact frozen bytes. Add immutable filing receipt; never re-render during filing.

**Step 3 — Close the export crash window.** Publish and verify all formats before a frozen record becomes fileable, or introduce one explicit export-ready state with restart recovery.

**Step 4 — Export an audit package.** Include source manifest/digests, evidence reads, provider identity/attempts, route/methodology, artifacts, model inputs/calculations/revisions, opinion, frozen/filed hashes, and audit events without secrets or hidden reasoning.

**Step 5 — Verify offline.** A standalone verifier reconstructs sampled outputs and validates every digest with no database or application-team help.

**Step 6 — Meet the pinned institutional benchmark.** Preserve canonical sections while adding the minimum layout/table/chart changes needed for the approved Credit Operating System rubric. Retain semantic, visual, accessibility, and blind-review artifacts for every pathway/format.

## Task 11: Build the blocking enterprise qualification corpus and live matrix

**Files:**
- Modify: `caos/tests/corpus/sources.txt` or replace it with versioned manifests
- Modify: `caos/tests/test_corpus_pathways.py`
- Create: answer keys and pack metadata under `caos/tests/corpus/` without embedding licensed bytes in Git
- Create: protected enterprise-qualification workflow using existing CI conventions
- Modify: `docs/QUALITY_LEDGER.csv`

**Step 1 — Preserve Carnival as the performing-credit host control.** Add answer-key metadata and source dispositions; do not relabel its scripted-provider results as live qualification.

**Step 2 — Add required uploaded packs.** Add time-aligned licensed market marks/loan universe for Relative Value, a 20–30-document stressed/restructuring issuer pack, and question-specific Deep Research positive/negative packs. Every byte is retained or available from an approved immutable store and SHA-256 verified before execution.

**Step 3 — Run one parameterized matrix.** Execute one binding × six pathways × supported depths × required positive/negative packs × three cold repetitions. Score facts, citations, unsupported claims, conflicts, document use, model effects, refusals, latency, and budget.

**Step 4 — Fail closed.** Missing credentials, bytes, licence/classification, answer keys, or any failed cell makes qualification red; no skip, waiver, averaging, or refusal-as-positive-proof.

## Task 12: Prove concurrency, stress, recovery, security, and capacity

**Files:**
- Create/modify: `qa/` harnesses using pytest/Playwright and existing Compose services
- Modify: storage transactions and lifecycle code only where a failing simulation proves a defect
- Modify: `.github/workflows/ci.yml` and `.github/workflows/nightly.yml`
- Test: SIM-001–030, two-connection PostgreSQL races, restart/corruption, load, soak, backup/restore, browser/accessibility, security scanners

**Step 1 — Implement deterministic simulations.** Cover kill points, duplicate delivery, stale CAS, provider timeout/truncation, source withdrawal/corruption, renderer failure, disk full, worker restart, checkpoint corruption, and recovery.

**Step 2 — Prove database truth.** Run two independent PostgreSQL connections/processes for acceptance, event sequence, budgets, model sign-off, deliverable freeze/opinion/file, and exactly-one-winner behavior.

**Step 3 — Prove capacity.** Run below/at/above declared limits, route-balanced six-pathway mixed load, failure under saturation, and an eight-hour soak. Retain latency, throughput, CPU, memory, DB connections, handles, files, jobs, usage, errors, and cross-case leakage results.

**Step 4 — Prove enterprise security/identity.** Run real IdP group mapping, least privilege, tenant/case isolation, upload malware/archive/boundary checks, prompt injection, egress restrictions, SBOM/dependency/image scans, authorized penetration testing, three browsers, and accessibility.

**Step 5 — Prove recovery.** Run active-write encrypted backup/restore, clean reset, single-instance lock, restart, and audit reconstruction without partial state or silent success.

## Task 13: Qualify and sign one immutable candidate

**Files:**
- Modify: `docs/QUALITY_LEDGER.csv`
- Modify: `docs/QUALITY_DEFECTS.csv`
- Modify: `SPEC_RECONCILIATION.md`
- Modify: `ENTERPRISE_READINESS_PLAN.md`
- Create: retained candidate evidence manifest/package in the approved evidence location

**Step 1 — Freeze identities.** Pin commit, image digests, methodology, sole provider/model/policy binding and qualification record, corpus/answer-key digests, IdP profile, environment, and reviewer roster.

**Step 2 — Execute G0–G9 on those exact identities.** Include all 340 readiness checks, the live six-pathway matrix, publication formats, SIM-001–030, races, browsers/accessibility, security, performance/soak, backup/restore, and reconstruction.

**Step 3 — Conduct independent reviews.** Analysts, model risk, security, accessibility, external-stakeholder, audit, operations, and enterprise-test owners adjudicate every finding. Any code/corpus/model/environment change creates a new candidate.

**Step 4 — Sign only complete evidence.** Hash the package and obtain enterprise test-owner signature. Do not mark any gate pass from historical prose, a skipped/waived/not-run check, scripted-model output, or mixed-candidate evidence.

**Step 5 — Completion audit.** Re-derive every requirement from `ENTERPRISE_TESTING_READINESS.md` and this plan, link it to retained proof, and mark the goal complete only when every item is proven. The resulting claim is “enterprise-testing ready,” not production-ready.

## Required finishing sequence

After Task 13 passes:

1. Run `rewrite-tournament` for every non-trivial code task not already reviewed.
2. Run `confidence-review` over the complete branch and investigate every low-confidence point to root cause.
3. Run the `finishing-a-development-branch` skill.
4. Retain the final candidate evidence and report exact commands/results, remaining exclusions, and the enterprise test-owner signature.
