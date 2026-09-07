# CAOS audit and unknown-behaviour goal prompts

Prepared on 7 September 2026 against checkout `31482a7`. These are prompts for future execution, not audit results. Recheck the current application when running them.

CAOS serves institutional leveraged-finance analysts: supplied documents become evidence-bound analysis, Model Builds, Analyst Model Revisions and governed Deliverables. Its declared target is enterprise-testing readiness. The prompts below follow that scope.

## What to retain from the examples

Use the library's evidence-based audit, finite product inventory, repeated verification and explicit stopping conditions. The strongest starting points are [Groundtruth](https://signals.forwardfuture.com/loop-library/loops/groundtruth-audit-loop/) and [Full Product Evaluation](https://signals.forwardfuture.com/loop-library/loops/full-product-evaluation-loop/). Adapt [Quality Streak](https://signals.forwardfuture.com/loop-library/loops/quality-streak-loop/) to a fixed, varied scenario set, and combine automated accessibility scans with the manual checks described in [Accessibility Repair](https://signals.forwardfuture.com/loop-library/loops/accessibility-repair-loop/).

Make four changes to the attached examples:

- Record intended behaviour and observed implementation separately. Deriving correctness solely from code can turn an existing bug into an acceptance criterion.
- Replace “no undiscovered features” with reconciliation of explicit inventories, and replace “no unknown behaviours” with completed experiments and a visible uncertainty backlog.
- Use coverage to locate missing tests. Neither 100% line coverage nor an invented confidence percentage proves correct behaviour.
- Repair confirmed defects. “Refactor until happy” and mandatory commits after every step do not provide a measurable quality gate.

CAOS already has `docs/QUALITY_LEDGER.csv` with 138 feature rows at this checkout, plus defect, simulation, perimeter and qualification records. Reuse these spreadsheet-compatible files; do not create a competing feature workbook.

## Running order

Copy one numbered prompt into a goal task. Each prompt reads the shared contract from this file, so it can be used independently in this repository. Run 01 and 02 first. Use 03–12 to investigate particular risks, 13 to sweep dead and redundant code with Fallow, 14 to repair confirmed defects and verified cleanup candidates, and 15 to evaluate the resulting candidate. The optional campaign prompt chains them together.

| Goal | Purpose | Default authority |
|---|---|---|
| 01 | Reconcile features, contracts and existing evidence | Audit and records |
| 02 | Find untested assumptions and interaction failures | Tests and records |
| 03 | Exercise real user journeys and accessibility | Tests and records |
| 04 | Challenge document intake and input boundaries | Tests and records |
| 05 | Challenge identity, case isolation and authority | Tests and records |
| 06 | Interrupt, race and resume durable work | Tests and records |
| 07 | Verify calculations, scenarios and model lineage | Tests and records |
| 08 | Challenge AI outputs and qualification claims | Tests and records |
| 09 | Verify publication and independent reconstruction | Tests and records |
| 10 | Detect silent failures and unsafe logging | Tests and records |
| 11 | Measure capacity and prove isolated recovery | Tests and records |
| 12 | Test whether the test harness detects real defects | Tests and records |
| 13 | Sweep dead and redundant code with the Fallow skill | Audit and records |
| 14 | Repair confirmed causes and verified cleanup candidates | Local product fixes |
| 15 | Rerun the fixed matrix and issue an evidence verdict | Validation and records |

## Shared contract

The following instructions apply to every numbered goal when executed.

### Establish authority and scope

1. Read applicable `AGENTS.md` instructions, `CLAUDE.md`, `CONTEXT.md`, `docs/DECISIONS.md`, `SPEC_RECONCILIATION.md` and the relevant sections of `ENTERPRISE_TESTING_READINESS.md`. Later binding decisions override earlier ones. Preserve all ten engine invariants. Use the product vocabulary in `CONTEXT.md`.
2. Record the commit, branch, existing dirty files, patch digest when applicable, runtime versions, environment, fixture digests, provider binding and available services. Preserve other work. Establish the current baseline before changing tests or code; historical green results are references, not current evidence.
3. Use an isolated local or explicitly authorised enterprise test environment with synthetic or already approved fixtures. Tests may create and remove their own disposable data. Follow existing authorisation for provider spending and external data; credentials being present do not establish a spending allowance. Continue independent keyless work if live qualification is unavailable. Keep production data, public publishing and external communications outside this campaign unless separately authorised.
4. Goals 01–13 and 15 may update audit records and add minimal tests, fixtures or test instrumentation. They do not authorise product behaviour changes. Goal 14 authorises the smallest local fixes for confirmed defects and verified dead-code removal or duplicate consolidation. A request to run the full campaign includes that repair phase. Existing explicit user instructions take precedence over these defaults.
5. For every code change, including test code, run `confidence-review` before declaring the change complete. For non-trivial implementation changes, also run `rewrite-tournament` in no-argument post-edit mode on the changed functions; its trivial, documentation, configuration, generated-file and test-only exclusions remain applicable. Reverify any changes those reviews introduce.

### Keep one traceable record

6. Preserve existing IDs, CSV schemas and status conventions in `docs/QUALITY_LEDGER.csv` and `docs/QUALITY_DEFECTS.csv`. Link relevant entries in `docs/SIMULATION_LEDGER.csv`, `docs/PERIMETER_LEDGER.csv` and `docs/QUALITY_QUALIFICATION.csv`. Use the existing candidate evidence directory when one exists; otherwise retain evidence under `.superpowers/sdd/quality-loops/<run-id>/`. Put richer outcomes in linked reports instead of silently changing ledger schemas. An XLSX view, if requested later, is an export of these records.
7. Each test result must identify its test/scenario ID, Feature ID, contract or independent oracle, fixture and seed, actor, starting state, actions, expected result, observed result, command or browser trace, timestamp and tested build/environment. Each failure also needs a Defect ID, severity, reproduction, affected invariant, root-cause hypothesis and evidence location. Keep source text and secrets out of ordinary logs and reports.
8. Separate confirmed defects, observations without an agreed requirement, unresolved product decisions, blocked checks and disproved suspicions. Classify a defect from a violated contract or demonstrated harm, not from personal preference. When requirements conflict, record the conflict and continue work that does not depend on resolving it. Do not silently rewrite an oracle to agree with the implementation.

### Seek counterexamples and stop honestly

9. Reuse existing pytest, browser, corpus, simulation and qualification harnesses. Before adding a check, locate its nearest existing test and identify the missing failure mode. Prefer a small deterministic regression over new infrastructure. Verify that tests actually reach the boundary they claim to exercise.
10. For unknown behaviour, test sequences, boundary values and combinations as well as isolated actions. Write each invariant or expected relationship before the experiment. Keep deterministic seeds, minimise failures to the smallest reproducer, and reserve fresh variants for verification after a fix. A host-control result proves orchestration only; SQLite does not prove PostgreSQL races; a mocked provider does not qualify live analysis; an automated scan does not prove full accessibility.
11. Before starting, declare the goal's finite scenario matrix and its exclusions. Unless the user supplies another budget, cap each goal at three investigation passes or 90 minutes of wall time, whichever comes first. A pass covers the declared matrix and records newly discovered candidates; it is not an unbounded search. Two passes without new evidence stop exploration as STALLED unless the stated exit criteria already hold. Budget exhaustion produces a resumable handoff, never an automatic pass.
12. Return a goal verdict of COMPLETE, FINDINGS, BLOCKED, STALLED or EXHAUSTED, with completed/required counts, defects, evidence links, environment limits and the next bounded action. An audit can be COMPLETE while recording product defects; make those two conclusions explicit. A validation pass requires every mandatory check in its declared scope to pass. Missing access, skipped checks and unsupported environments remain unverified. Never claim that unknown behaviours have been eliminated.

## 01 — Reconcile the application with its quality inventory

```text
Apply the Shared contract in docs/QUALITY_GOAL_PROMPTS.md to Goal 01.

Establish what CAOS currently exposes and which behaviour has credible evidence. Trace the document-to-filed-deliverable flow forward, then trace a filed value backward to its input and approval authority.

Reconcile four inventories: frontend routeDestinations and forwardedRoutes; registered HTTP/OpenAPI routes; services, background jobs and state transitions; existing requirements and quality-ledger rows. Include roles, controls, empty/loading/error/refusal states, configuration-dependent capabilities and features reachable only through the API. Record excluded generated or reference material with reasons.

For each feature retain or allocate its Feature ID, user story, intended behaviour and authority, observed implementation, dependencies, boundary cases, linked tests and present evidence level. If only implementation describes a behaviour, label the acceptance criterion provisional. Resolve discrepancies against current code and configuration; old documentation is not proof that a route exists or is unavailable.

Build the six-pathway × two-depth matrix, including prerequisites and currently advertised availability. Link the ten engine invariants and G0–G9 requirements to evidence. Identify stale PASS records without erasing their history.

Loop over inventory discrepancies until every enumerated surface maps to a feature and every feature maps to a reachable surface or an explained exclusion. Return the reconciled ledgers, missing tests, requirements conflicts and a prioritised uncertainty list. Completion establishes an inventory baseline; it does not certify feature correctness.
```

## 02 — Turn uncertainty into falsifiable experiments

```text
Apply the Shared contract in docs/QUALITY_GOAL_PROMPTS.md to Goal 02. Reuse Goal 01's inventory if it still matches this checkout; otherwise reconcile the affected scope first.

Enumerate the assumptions least supported by evidence across frontend state, API validation, storage transactions, engine checkpoints, provider interactions, models and publication. For each, write: the assumption; why it may fail; impact; supporting evidence; the smallest experiment that could disprove it; and a control that shows the experiment reached the intended path.

Choose 20 previously untested experiments before execution. Include action-order changes, duplicate requests, delayed responses, interruption, role changes, source withdrawal, stale revisions and combinations across component boundaries. Use pairwise combinations for the ordinary matrix and explicit three-way combinations for high-risk seams. Examples to investigate include withdrawal during model publication and an old Run response arriving after a case switch and permission downgrade.

Execute the highest-risk experiment, minimise any counterexample, record it, then update the remaining ranking. Do not spend the budget repeating already-proven happy paths. Use deterministic seeds for generated sequences and retain rejected or invalid sequences with their reasons.

Finish when the 20 experiments have retained outcomes and every new finding has an owner action, or at the shared stop boundary. Return the uncertainty register, tested hypotheses, disproved suspicions, minimal failures and a fresh-variant backlog. An unexplained anomaly remains unresolved even if a retry passes.
```

## 03 — Exercise document-first journeys and browser behaviour

```text
Apply the Shared contract in docs/QUALITY_GOAL_PROMPTS.md to Goal 03.

Start from fresh browser sessions and exercise CAOS through visible controls. Prepare fixtures before the journey, but do not use hidden API mutations to substitute for a missing UI step. Use the actual combined app and worker; record the provider mode.

Follow document intake → Run review and explicit acceptance → Analysis → Model Build → Draft Revision and scenarios → Sign-Off → Deliverable authoring and opinion → freeze → filing by an independent authorised actor → download and receipt. Run complete positive fixtures for all applicable pathways; use negative fixtures to test specifically expected refusals. Respect depth-specific prerequisites instead of calling every refusal a success.

Cover all current destinations, legacy forwarding links, deep links, browser back/forward, reload, multiple tabs and unsaved-work protection. Inject slow and out-of-order responses, dropped SSE connections, repeated clicks and case/run switches. Verify that the visible case, model, evidence and action target always agree, and that the UI never claims a server mutation succeeded when it did not.

Use the existing Chromium, Firefox and WebKit journeys. Check desktop, tablet and narrow layouts, keyboard navigation, focus return, zoom, reduced motion and screen-reader behaviour where available, against WCAG 2.2 AA. Record unavailable manual checks separately from axe results.

Repeat affected journeys after any authorised repair. Return route/state/actor coverage, traces or screenshots for failures, accessibility barriers and recovery behaviour. Pass only the declared journeys actually completed without hidden assistance, lost work or authority mismatches.
```

## 04 — Challenge source intake and input boundaries

```text
Apply the Shared contract in docs/QUALITY_GOAL_PROMPTS.md to Goal 04.

Trace every source-admission path, including document-first multipart intake, direct source upload and loan-universe import. Derive limits from current contracts and configuration, then test just below, exactly at and just above each limit in its real unit: bytes, extracted characters, blocks, rows, columns, sheets and request size.

Extend the existing corpus with bounded, synthetic cases for malformed/truncated files, extension-versus-content disagreement, unsupported formats, textless or rotated PDFs, duplicate archive entries, traversal names, compressed expansion, hidden spreadsheet content, formula cells, missing cached values, external links and extreme dimensions. Include NFC variants, legitimate RTL text, forbidden bidi controls, control bytes, lone surrogates and very long lines.

Exercise renamed duplicates, mixed valid/invalid batches, conflicting periods, amendments and restatements both within one intake and across separate intakes. Record observed dispositions and their policy basis; do not invent a supersession rule for an unresolved product decision.

Inspect database state, vault references and audit records after rejection or interruption. Verify the documented transaction boundary, source-set version allocation, absence of unintended partial admission, and actionable bounded refusals without document leakage. Apply resource caps to malformed-file experiments.

Loop over each uncovered boundary family, shrink failures and link them to the intake/evidence features. Return the boundary matrix, retained fixtures and transaction evidence. Passing requires every declared case to match its prewritten outcome, including required successful admissions.
```

## 05 — Challenge identity, case isolation and changing authority

```text
Apply the Shared contract in docs/QUALITY_GOAL_PROMPTS.md to Goal 05.

Derive the protected route inventory from the current app and OpenAPI, including SSE, binary exports and privileged administration. Reuse the perimeter harness and its nine actor profiles: outsider, global-admin outsider, removed member, stored reader, global admin stored as reader, downgraded writer, analyst, approver and administrator.

Exercise case and run IDs in paths, queries, bodies and nested references. Check both reads and writes, malformed unauthenticated requests, mass assignment, forged development-role headers at the production edge, stale sessions and identical handling of unknown versus invisible resources.

Revoke or downgrade standing between request validation and commit. Verify that writes recheck current authority and that the losing operation cannot commit state, expose evidence or create a misleading successful audit event. Test concurrent member changes and provider-default changes with stale expected versions.

Distinguish the author's Model Revision Sign-Off from independent Deliverable filing. Test actor combinations explicitly: an opinion signer or freeze actor must not gain filing authority merely through another global role. Exercise direct HTTP calls as well as disabled UI controls.

Loop through the route × actor × action matrix and report omissions as unverified. For refusals inspect bodies, exception chains, logs, streams and downloads for leakage. Return the access matrix, confirmed bypasses, negative controls and commit-time evidence; an HTTP error alone is insufficient if the mutation already happened.
```

## 06 — Interrupt, race and resume durable work

```text
Apply the Shared contract in docs/QUALITY_GOAL_PROMPTS.md to Goal 06.

Map the existing SIM-001–SIM-030 tests to current transaction and checkpoint seams. Add only missing fault windows: before reservation, after reservation, during provider execution, after provider success but before persistence, between domain commit and checkpoint advancement, and during model or freeze-job completion.

Use controlled interleavings for competing intake, withdrawal, acceptance, budget reservation, model builds, revision Sign-Off, draft saves, opinions, freezes and filing. Test source withdrawal and methodology/provider identity changes while work is paused. Every run must retain its pinned route and identities; restart must not silently select a new binding or source set.

After crash/restart or duplicate delivery, inspect durable rows and ledgers: legal state transitions, one committed artifact per logical operation, correct reservation/reconciliation, monotonic event sequences, one terminal event, and recoverable queued work. Reconnect SSE with old, current and malformed cursors and check that the UI converges to server state.

Test each budget ceiling below/at/above the boundary, including concurrent reservations, reported usage changes and provider timeouts. If a remote outcome is unknowable, preserve that uncertainty and follow the documented recovery policy; do not infer exactly-once billing from a local mock.

Run SQLite coverage and real PostgreSQL tests using independent connections in disposable databases. Record them as distinct evidence. Repeat newly exposed interleavings from fresh state and retain the minimal schedule. Return the fault matrix, post-restart snapshots, event/charge counts and unresolved windows.
```

## 07 — Verify financial calculations and model lineage

```text
Apply the Shared contract in docs/QUALITY_GOAL_PROMPTS.md to Goal 07.

Trace accepted evidence through calculation records, Model Builds, the Assumption Registry, Analyst Model Revisions, scenarios and exports. Use the existing CALC-001–020 mappings and source-complete modelling tests as the baseline.

Check arithmetic against small independently calculated fixtures and the approved methodology. Do not reuse the production calculation function as the expected-value oracle. Cover missing values versus zero, NaN/infinity, zero denominators, sign conventions, units, currencies, period alignment, rounding, covenant thresholds and exact Assumption Guardrail boundaries.

Write conditional metamorphic relationships before testing them. Examples: consistently scaling compatible monetary inputs preserves a dimensionless ratio; changing source order preserves semantic results when precedence is unchanged; a no-change scenario reproduces its reference values; an in-scope evidence change affects the expected downstream calculation. State preconditions and tolerances; hashes, provenance and nonlinear outputs need not remain identical.

For every pathway, verify prerequisites, the accepted authority used, declared model effect and source_lineage. Every relevant used source must have its required binding. Check overlays against the correct Full Credit ancestor and expose a missing effect rather than allowing a successful build with unchanged unsupported outputs.

Verify that scenarios and Apply to Draft do not release shared revisions, that immutable Model Builds stay unchanged, and that stale revisions and Rebase Candidates retain correct ownership and authority. Return calculation discrepancies, lineage gaps and invariant results with reproducible numbers. Missing independent answer keys remain a qualification gap.
```

## 08 — Challenge AI outputs and distinguish qualification evidence

```text
Apply the Shared contract in docs/QUALITY_GOAL_PROMPTS.md to Goal 08.

Use two explicitly separated tracks: deterministic hostile-provider tests for host enforcement, and live-provider evaluation only within existing authorisation, budget and approved corpus access. Inventory current provider catalog entries, pinned identities, route/depth support and qualification records before execution.

In the host track, use documents and provider responses that attempt instruction override, forged host/frontmatter identity, cross-case evidence reads, web discovery, fabricated citations, undeclared envelope fields, excessive output, malformed tool arguments, invalid calculation references and dishonest usage or model identity. A deliberately compliant-to-the-attack provider double must reach the host boundary. Verify typed refusal, no returned evidence text on refused reads, no forbidden tool effect, correct budget handling and no success artifact from an invalid response.

Also run valid controls. Test missing, conflicting, restated and multilingual evidence, Deep Research plan approval and stale approval digests. The application must succeed on designated complete positive packs and refuse only where the answer key permits it.

For live evaluation, use the existing qualification harness and approved C01–C22 manifests and answer keys. Keep development cases and fresh holdouts separate. Bind results to build, corpus, provider/model identity and evaluation configuration; repeat nondeterministic cases with the declared sampling policy. Do not edit answer keys to rescue a model or substitute generated answers for independent analyst approval.

Return HOST-ENFORCEMENT, ORCHESTRATION and LIVE-QUALIFICATION results separately. Missing credentials, spending authority, licensed marks, C21/C22 inputs or analyst sign-off block the affected qualification cells, not unrelated host tests. A host-control green run can never produce a live QUALIFIED verdict.
```

## 09 — Verify exact publication and independent reconstruction

```text
Apply the Shared contract in docs/QUALITY_GOAL_PROMPTS.md to Goal 09.

Trace each pathway's Deliverable from its analytical/model authority through draft revision, opinion, freeze job, frozen payload, independent filing, exported bytes and detached receipt. Determine current supported bindings from the decision record and implementation; expose mismatches without inventing new pathway policy.

Attempt opinion reuse after edits, stale expected heads, preview-digest mismatches, source withdrawal, competing freezes, worker death, repeated filing, same-actor filing and content mutation after review. Assert both successful authorised transitions and fail-closed invalid transitions. A queued freeze is not a Frozen Deliverable until the worker has rendered and verified the required bytes.

Compare browser, Markdown, PDF and XLSX for facts, units, periods, signs, rounding, citations, model identity and approval meaning. Inspect representative pages and worksheets for clipped tables, missing glyphs, unreadable text and misleading hierarchy. Use semantic parity across formats and byte hashes within each frozen format; different formats are not expected to share a digest. Approved frozen bytes remain unchanged; the detached receipt carries the filing decision.

Export a test audit package and reconstruct sampled published values using the standalone verifier in a clean environment without the running app. Tamper separately with an artifact, export, citation, manifest and audit-chain link; verify each required integrity failure is detected. Record the limit of chain verification without an independently retained anchor.

Return per-pathway publication evidence, reconstruction results, actor/digest checks and rendering defects. Stop with blocked evidence where an independent reviewer, benchmark or supported rendering environment is missing. Never call internal fixture agreement independent analyst validation.
```

## 10 — Find silent failures and unsafe observability

```text
Apply the Shared contract in docs/QUALITY_GOAL_PROMPTS.md to Goal 10.

Enumerate meaningful transitions and refusals for intake, evidence access, runs, gates, provider calls, budgets, worker jobs, model revisions and publication. For each, define the minimal operational evidence needed to distinguish success, refusal, retry, abandonment and recovery. Reuse observability.py and the existing observability spec tests.

Drive at least one real success and one applicable failure through each event family. Include a disconnected client, provider timeout, worker failure, failed commit and startup recovery. Correlate logs with persisted events and durable state: there must be enough identity to diagnose an operation without falsely reporting an uncommitted success or losing a terminal outcome.

Use sentinel document text and synthetic secrets to test source/prompt/output leakage, nested mapping keys, exception chains, control characters, huge strings and redaction/truncation. Verify runtime logs remain bounded and useful. Treat the governed evidence store and audit package separately from ordinary application logging.

Check that readiness failures are observable and return the declared status, while anonymous health checks remain bounded. Confirm that retry noise cannot hide a permanently stuck job and that any recorded alerting claims have an exercised signal path.

Loop over unexplained or silent outcomes and record precise missing log points or incorrect classifications for Goal 14. Return event-to-evidence coverage, failed probes and leakage checks. Do not add raw document content or indiscriminate debug logging to increase a coverage score.
```

## 11 — Measure the declared deployment and prove recovery

```text
Apply the Shared contract in docs/QUALITY_GOAL_PROMPTS.md to Goal 11.

Read the current enterprise environment manifest and capacity harness. Pin workload, hardware, software, dataset size and acceptance thresholds before measurement. Use the declared single app/single worker topology with PostgreSQL domain data, SQLite checkpoints and the vault where that is the target profile. Do not turn this goal into horizontal-scaling implementation.

Measure representative document intake, evidence reads, Run updates/SSE, model previews, freeze/export jobs and concurrent browser use. Record p50/p95/p99 latency, completed work, refusal/error rates, queue age and memory before/during/after bounded load. Exercise the real configured ceilings at their owning layer, including the edge when a request-size limit belongs there. Expected 429s still need correct backoff and accounting; do not silently discard driver failures or stalled work.

Repeat comparable measurements after an authorised fix. If no performance target exists, report a baseline and the missing decision instead of inventing a pass threshold. Separate host-control timing from live-provider latency and cost.

Using synthetic test data, exercise backup and restore into a fresh disposable environment. Verify consistency across domain rows, checkpoints and vault objects, retained identities/digests, authorised reads/writes, queued-job recovery and the resumed golden journey. Measure actual recovery duration and data loss against any declared targets. Prove a second app or worker is refused as designed.

Return capacity evidence, resource leaks, restoration proof and environment differences. A local restore does not prove off-host transfer, retention, licensed-data recovery or production availability; record any required but unexercised deployment step explicitly.
```

## 12 — Verify that the tests can detect the failures

```text
Apply the Shared contract in docs/QUALITY_GOAL_PROMPTS.md to Goal 12.

Audit test credibility against the feature and invariant matrix. Inspect test collection, mandatory skips, xfails, mocks, conditional early returns, browser-console filters, scanner errors and assertions that could pass without reaching the claimed boundary. Check that inventory scripts target current routes and that security tools actually scan their intended files.

Use statement/branch coverage and change history to select missing high-risk behaviours, not to chase an aggregate percentage. For each of the ten engine invariants, choose one representative test and prove its assertion is sensitive to a plausible defect. Where necessary, temporarily introduce one minimal guard or transaction-order mutation in a disposable checkout, run the target test, retain the result and remove the mutation. Never leave a mutant in the product tree. Explain equivalent or surviving mutants rather than counting all mutations as failures.

Run suspected flaky tests five times under fixed conditions, then exercise the affected suite with controlled order/timing variation. Preserve failed seeds and traces. Investigate shared state, missing waits, races and external dependencies; blind retries or sleeps do not establish stability.

Add only the smallest missing checks. Do not weaken an assertion, suppress an unexplained error, regenerate a golden without inspection or change a scanner floor to make the result green.

Return missing behaviours, vacuous tests, mutation results, flakes and scanner/route discrepancies. Completion means the audit matrix is accounted for; surviving high-risk gaps still block a quality claim and feed Goal 14.
```

## 13 — Sweep dead and redundant code with Fallow

```text
Apply the Shared contract in docs/QUALITY_GOAL_PROMPTS.md to Goal 13. Invoke the fallow skill and follow its analysis and trace workflow.

Inspect the existing .fallowrc.json, resolved project root, workspace discovery, entry points, framework plugins and exclusions before scanning. CAOS currently scopes Fallow to caos/frontend, explicitly retaining scripts and test entry points. Verify that Next.js routes, framework exports, package scripts and CI entry points are represented. Fallow analyses JavaScript/TypeScript; list the Python backend and other unsupported material as outside its coverage.

Run a full scoped baseline for unused files, exports, types, members and dependencies, then duplication detection in strict and semantic modes. Prefer the available Fallow MCP analysis tools; when using the CLI, follow the skill's JSON, quiet, explain and exit-handling rules. Retain typed JSON reports, tool version, configuration, scanned-file counts, diagnostics and clone fingerprints. Invalid/empty output, parser failures, unresolved imports or an empty scan cannot establish a clean result. Do not substitute a changed-files-only scan for the baseline.

Trace each candidate before recommending a change: trace_file and trace_export for reachability, trace_dependency for imports and script usage, and trace_clone for every duplicate group. Cross-check dynamic imports, side effects, re-export chains, framework conventions, compatibility routes and use from tests or build tooling. Unobserved runtime coverage alone does not prove dead code. Preserve intentionally independent implementations, generated files, methodology pins and tests whose duplication protects an independent oracle.

Classify findings as verified removal, verified consolidation, intentional retention, false positive or unresolved. For consolidation, establish equivalent contracts and side effects before choosing an existing shared implementation; similar syntax alone is insufficient. Record file/symbol, finding identity, usage evidence, affected Feature IDs and validation needed in a linked cleanup report. Use the defect ledger only where a real defect is confirmed.

Preview any proposed automatic removal with fix_preview or fallow fix --dry-run. This goal does not apply deletions. Send only verified candidates to Goal 14; keep hooks, telemetry and cloud monitoring outside this sweep. Repeat analysis when discovery gaps are resolved, retaining before/after scope. Finish when every finding has an evidence-backed disposition or at the shared stop boundary. Return reports, candidate groups, retained exceptions and unsupported scope; zero warnings is not the target.
```

## 14 — Repair confirmed causes and search every sibling path

```text
Apply the Shared contract in docs/QUALITY_GOAL_PROMPTS.md to Goal 14. This goal authorises local product fixes for confirmed defects and verified cleanup candidates in the current quality records.

Deduplicate findings by root cause, identify dependencies and prioritise security, evidence integrity, data loss, incorrect calculations, authority and broken journeys. Select one coherent defect or verified cleanup group. For defects, reproduce the failure before editing and trace every caller of the function or boundary involved. Compare the failing path with sibling paths that already behave correctly.

For defects, implement the smallest fix at the shared cause, reusing existing helpers and contracts. Add a regression that fails on the original code and passes with the repair. Search the rest of the repository for variants of the same failure pattern; extend the repair only where evidence confirms the defect. Respect existing product decisions, single-instance limits and approved methodology pins.

For Goal 13 cleanup candidates, invoke the fallow skill again and recheck usage traces against the current patch. Remove one verified dead-code group or consolidate one equivalent duplicate group at a time. Preview automatic fixes first and apply them only if the preview exactly matches the reviewed scope; otherwise edit that scope manually. For behaviour-preserving cleanup, use passing before/after checks instead of inventing a failing regression. Rerun the same Fallow scope plus affected lint, typecheck, unit, build and browser checks. Do not lower thresholds, hide findings or create a speculative abstraction to improve the report.

Run the original reproduction, sibling-path checks, relevant invariant tests and affected real-user journey. Run rewrite-tournament in no-argument post-edit mode for non-trivial changed functions and confidence-review before accepting the patch; investigate every low-confidence point and reverify any further edits. Preserve unrelated user changes.

Update the defect and feature records with cause, fix, evidence and remaining limits. An unimplemented requirement requiring a product decision remains open; do not make it disappear through a waiver, relabelled test or undocumented scope reduction.

Repeat for the next confirmed group within the shared budget. Return the reviewable patch, regression evidence, unresolved defects, cleanup results and the exact scope that Goal 15 must rerun. Do not merge, deploy or publish as a side effect of repairing the application.
```

## 15 — Rerun the fixed matrix and issue the final verdict

```text
Apply the Shared contract in docs/QUALITY_GOAL_PROMPTS.md to Goal 15.

Freeze the candidate identity and the mandatory validation matrix before the final run. Reconcile the current ledgers, ten invariants and G0–G9 gates. Record which evidence requires an immutable candidate commit/image, real PostgreSQL, a qualified live provider, licensed inputs or independent human review. A dirty local patch can have local evidence but cannot impersonate a frozen enterprise candidate.

Run the required unit, contract, integration, browser, accessibility, security, corpus, model, simulation, performance and publication/reconstruction checks against that candidate. Reuse project commands after verifying their prerequisites. Account for collected, passed, failed and skipped checks; missing evidence is not a pass. Fresh runs replace stale conclusions while preserving history.

Rerun Goal 13's Fallow sweep on the final candidate using the same configuration and scope. Verify each claimed removal or consolidation, investigate new findings, retain justified exceptions and confirm affected entry points and journeys still work. Include the cleanup report and before/after evidence; a lower finding count alone cannot prove a safe cleanup.

Require three consecutive complete passes of the declared representative journey and failure-scenario matrix, each from reset state with a predeclared different seed or fixture variant. Include fresh holdouts that were not used to design fixes. Do not preserve the streak by dropping difficult scenarios. Any failure resets the streak, reopens the defect and invalidates the affected evidence. If Goal 14 changes the candidate, rerun the required final matrix on the new candidate.

Package the environment, commands, fixture/provider identities, results, traces, ledger snapshots and artifact hashes in one retained evidence package. Report local validation, orchestration proof, live-model qualification and enterprise readiness separately.

Pass only when every mandatory scoped check has fresh passing evidence and no required blocker remains. Apply the repository's full enterprise gate without self-issued waivers when making an enterprise-readiness claim. Otherwise return FINDINGS, BLOCKED or EXHAUSTED with exact gaps. Report coverage as measured counts and ratios; do not assert that all unknown behaviour is gone.
```

## Optional — Run the series as one bounded campaign

```text
Use docs/QUALITY_GOAL_PROMPTS.md as the execution specification for a CAOS quality campaign. Apply its Shared contract and execute the numbered goals in order, reusing current evidence where its build, environment and scope still match. This campaign includes Goal 14's authority for local confirmed-defect repairs and verified cleanup.

Default to a total six-hour wall-time cap and at most three audit → repair → regression cycles, unless I supply another budget. The total cap overrides per-goal allowances. Prioritise integrity, authorisation, data loss and calculation risks; retain unfinished lower-priority work rather than hiding it.

After discovery, use Goals 03–12 to produce a deduplicated finding set and Goal 13 to sweep dead and redundant code with the fallow skill. Repair coherent defect and verified cleanup groups through Goal 14, then rerun their original experiments, usage traces, Fallow reports, sibling paths and applicable journeys. Revisit discovery when a repair or new behaviour exposes another surface. Finish with Goal 15 when prerequisites and budget permit.

Keep the existing ledgers current and retain a checkpoint after each goal: candidate identity, completed scope, evidence paths, findings, blocked inputs, elapsed budget and next action. Continue unaffected work when one external dependency is unavailable. Stop on the declared completion criteria, exhausted budget or an impasse requiring user input; preserve a resumable handoff and do not report a blocked qualification as success.
```

## Review notes

The prompts were checked for coverage of these situations: stale ledger evidence; code/spec disagreement; an unknown interaction; a valid positive pack; an expected negative-pack refusal; absent live-provider authority; a late response from another case; source withdrawal during work; a commit/checkpoint race; stale approval content; missing manual or PostgreSQL evidence; budget exhaustion; false-positive dead code; unsafe duplicate consolidation; and incomplete Fallow coverage. These are design checks, not executed agent evaluations or application tests.

Repository anchors used for adaptation: `CLAUDE.md`, `CONTEXT.md`, `README.md`, `ENTERPRISE_TESTING_READINESS.md`, `SPEC_RECONCILIATION.md`, the five existing quality ledgers, `caos/server/caos/api/__init__.py`, `caos/frontend/src/lib/workbench.ts`, `caos/frontend/src/lib/workspaceAuthority.ts`, `caos/frontend/package.json` and `.fallowrc.json`. Fallow instructions were adapted from the installed `fallow` skill. Treat present-day implementation observations and existing known-gap notes as starting points for investigation, not newly confirmed defects.
