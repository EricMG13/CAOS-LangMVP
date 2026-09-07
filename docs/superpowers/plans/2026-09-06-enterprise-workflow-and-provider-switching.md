# Resolve the six enterprise workflow improvements

Date: 2026-09-06. Planning baseline: `ecdfaee78b535826caa2f6d0a7532842f9aee15a` (PR #74).
Status: implementation executed on 2026-09-06; regression and browser verification recorded under qa/evidence. Analytical qualification and full production capacity gates remain open where the required approvals, corpus and hardware are absent.

The outcome is a real case moving from supplied documents through analysis, Model Build, analyst Sign-Off, Frozen Deliverable and independent filing, with evidence that the complete workflow works under both OpenAI and Anthropic. All six recommendations are in scope.

The user's updated requirement is authoritative: enterprise deployments must switch between OpenAI/ChatGPT and Anthropic/Claude, and model identifiers must be configurable. This supersedes the existing Anthropic-only/no-picker policy. Integration uses the vendors' APIs. No particular GPT or Claude model version is prescribed by this plan.

## Scope and operating decisions

- Initial adapters: direct OpenAI and the existing direct Anthropic adapter. Additional models use configuration where an adapter supports their contract; another vendor uses the existing Provider port. “Any model” means the architecture does not hard-code a model choice; enterprise availability still requires capability checks and model-specific qualification.
- Proposed switch location: an enterprise operator selects the default provider/model in Admin. It applies to newly admitted runs. Run and run history display the actual pinned provider/model. Document-first intake remains documents-only.
- Every run retains its exact binding through execution, research-plan approval, recovery, acceptance and screen-to-full upgrade. Default changes never substitute a provider inside an existing run. A missing, expired or revoked binding produces an actionable refusal.
- Both provider credentials may coexist on the server. Browsers select safe catalog IDs, never credentials, arbitrary endpoint URLs or qualification claims. Model IDs, model parameters, endpoint/account policy and qualification metadata belong to server configuration.
- One deployment is one enterprise security boundary for this iteration. Operator authority is current trusted global ADMIN plus a server-configured subject allowlist. This gives narrowly defined bootstrap/model-policy powers, not general case-read access. Ordinary case membership and independent filing remain separately enforced.
- Reuse the existing Provider port, engine, store transactions, audit chain, static frontend and test harnesses. Keep the aggregate provider/job ceilings and the ten engineering invariants.

| Recommendation | Implementation | Closure evidence |
|---|---|---|
| 1. First approver | Phase 1 | An analyst-created case obtains an independent approver through the application; atomic and permission checks pass |
| 2. Real provider analysis, expanded to enterprise switching | Phases 2 and 7 | Both vendors work; every enabled model passes the complete live matrix and analyst review |
| 3. Scanner recovery | Phase 3 | Killing clamd triggers automatic recovery; uploads fail closed during the outage |
| 4. Browser/API contract protection | Phases 6 and 7 | Shipped static frontend completes the production workflow through real API responses |
| 5. Evidence usability | Phase 5 | Tables, exact citations, contextual Report defaults and permission explanations work |
| 6. Source loading and latency | Phase 4, confirmed in Phase 7 | Inventory loads exclude evidence text; full search remains correct; measured read p95 meets the existing target |

## Phase 0 — Documentation discovery and contract alignment

Discovery is complete for the baseline. Read these references again when implementing the relevant phase; current code takes precedence over stale gap lists. The frozen `b88c0f8` candidate's results are historical evidence, not measurements of this baseline.

| Area | Verified existing API/pattern | Source |
|---|---|---|
| Provider port | `Provider.identity`, `count_tokens(ProviderRequest)`, `create_message(ProviderRequest)`; the loop supports synchronous or awaitable results | [provider.py:445](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/engine/provider.py:445), [loop.py:196](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/engine/loop.py:196) |
| Provider provenance | `ProviderIdentity`, `ProviderQualification.validate_binding`, `RunStore.create_run(..., provider_identity=...)` | [provider.py:141](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/engine/provider.py:141), [runs.py:824](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/storage/runs.py:824) |
| Governed case writes | Case transaction locking, `require_standing`, `_audit(conn, ...)`, existing member insertion | [store.py:260](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/storage/store.py:260), [store.py:455](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/storage/store.py:455), [store.py:602](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/storage/store.py:602) |
| Source projection/detail | `list_source_filenames()` already avoids materializing block JSON; `visible_source()` and the detail GET enforce ownership | [store.py:878](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/storage/store.py:878), [api/__init__.py:495](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/api/__init__.py:495) |
| Frontend reuse | Shared `markdownBlocks`, retained `normalizeEvidenceRefs().blockIds`, native accessible Deliverable tables, `WriteBlocked` | [artifactReader.ts:14](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/frontend/src/lib/artifactReader.ts:14), [DeliverableDocument.tsx:93](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/frontend/src/components/report/DeliverableDocument.tsx:93), [Workspace.tsx:32](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/frontend/src/components/Workspace.tsx:32) |
| Production journey | Full HTTP sequence already exists, but uses development identity/direct-store provisioning; browser success fixtures do not replace it | [golden_journeys.py:392](/Users/ericguei/Claude/Projects/CAOS-LangMVP/qa/golden_journeys.py:392), [workbench-smoke.mjs:524](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/frontend/scripts/workbench-smoke.mjs:524) |

Before changing behavior, append a dated decision to [DECISIONS.md](/Users/ericguei/Claude/Projects/CAOS-LangMVP/docs/DECISIONS.md:295) superseding §14.5's one-Anthropic-binding/no-picker restriction. Align UX-012, MOD-001–025 and provider assumptions in [ENTERPRISE_TESTING_READINESS.md](/Users/ericguei/Claude/Projects/CAOS-LangMVP/ENTERPRISE_TESTING_READINESS.md:154), [CLAUDE.md](/Users/ericguei/Claude/Projects/CAOS-LangMVP/CLAUDE.md), deployment documentation and the frontend capability map. Record the operator policy, first-bootstrap semantics, default-switch behavior, qualification eligibility and migration rules below.

Verification: each of the six rows above has an implementation phase and closure check; the revised decision explicitly cites the user's multi-provider requirement; old qualification reports remain dated historical records. New routes and fields specified below are proposed work, not existing APIs.

Guard: no code or qualification evidence should claim all models work simply because they share a provider or adapter.

## Phase 1 — Bootstrap the first independent approver

Depends on Phase 0. Resolve recommendation 1 and the associated UI/API permission mismatch.

Implement:

1. Add a dedicated first-approver operation, proposed `POST /api/admin/cases/{case_id}/bootstrap-approver`. Require the trusted operator authority defined above. Accept only a validated target subject and audit rationale; the granted case standing is fixed to APPROVER.
2. Reuse the store's case lock and audit transaction. Check case existence, absence of an existing approver/admin, and a durable one-shot bootstrap marker; insert standing, marker and audit event atomically. Target must differ from the case creator and operator. An exact retry returns the recorded receipt without a second mutation; a conflicting retry is refused. Revocation does not reopen bootstrap.
3. Make this work for cases created by both `create_case()` and atomic `admit_intake()`. Do not expose the store's general `actor_role="ADMIN"` bypass through the ordinary membership endpoint.
4. Add an operator-only Admin form accepting a known case ID, even when the operator cannot select that case in the normal case list. Expose only the necessary server-derived operator capability flags through the strict identity response; the frontend must not reconstruct the secret allowlist. Return a minimal receipt; the operator gains no case membership or evidence visibility. Analysts can copy their case ID and see an actionable “awaiting approver provisioning” state.
5. Align Admin provisioning and Report filing controls with the real rule: a current global writer plus stored case APPROVER/ADMIN standing. Use one shared frontend predicate over already served identity/membership fields, and keep signer/freezer independence. Unresolved identity remains fail-closed.

Read/copy: [case creation and membership](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/storage/store.py:563), [intake creation](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/storage/store.py:717), [shared approver guard](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/api/__init__.py:1213), [Admin](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/frontend/src/components/Workspace.tsx:1920), [filing predicate](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/frontend/src/components/report/reportStudioState.ts:28), [positive role matrix](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/tests/spec/test_deliverables_spec.py:1966).

Verification:

- Analyst creates a case; separate authorized operator provisions a distinct approver through HTTP/Admin; that approver later files independently.
- Ordinary admins outside the allowlist, analysts, readers and forged role headers cannot bootstrap. Ordinary case-read privacy remains intact.
- Self/creator targets, role mass assignment and repeated conflicting grants are refused. Two concurrent bootstrap attempts produce one durable grant and one audit record; audit failure rolls everything back.
- Existing case approvers across all permitted global writer roles get the correct UI; signer and freezer still cannot file. Exercise commit-time revocation using [SIM-020](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/tests/spec/test_simulations_spec.py:598).

Guard: do not weaken `require_case_approver`, globally promote the creator, or assume an existing IdP directory lookup can validate the nominated subject. The target's current global role is checked when they act. Existing cases with an approver use ordinary membership; loss of all approvers after bootstrap is an explicit audited operator-recovery procedure, never an automatic reopening of this grant.

## Phase 2 — Add configurable providers and the enterprise switch

Depends on Phase 0. Implement in three reviewable slices: adapter/harness correctness; binding resolution/persistence; Admin switch and provenance UI. Final live qualification is Phase 7.

### 2A. OpenAI adapter and qualification recorder

Reuse the existing Provider port and installed `httpx` for a direct OpenAI adapter. Keep the shared count → reserve → call → validate usage → reconcile loop. The official APIs are `POST /v1/responses/input_tokens` and `POST /v1/responses`; translate between their payloads and the host's normalized request/response structures. Read the [input-token API](https://developers.openai.com/api/reference/python/resources/responses/subresources/input_tokens) and [Responses API](https://developers.openai.com/api/reference/python/resources/responses/methods/create) before implementing.

Use explicit model configuration, disabled automatic input truncation, and an output reservation covering reasoning as well as visible tokens. Count the complete accepted request shape, including tools and continuation context; verify usage against reservations at minimum, typical and maximum supported shapes. Return typed sanitized failures for refusals, incomplete output, malformed usage, transport errors and identity mismatch. Reconcile known spend before rejecting an otherwise usage-valid response.

Map the existing host tools to strict function schemas and disable parallel tool calls. Preserve tool-call IDs, output ordering and any opaque reasoning continuation required by the chosen model. If necessary, add a bounded continuation field to the existing port, included in counting/request identity and scoped to one module invocation. It must never become analytical evidence, UI text, audit content or a mutable cross-run adapter cache. Read [function calling](https://developers.openai.com/api/docs/guides/function-calling); its continuation rules are provider-specific.

Use stateless Responses requests with `store=false`; account-level retention and regional processing remain enterprise configuration checks. This flag alone is not proof of zero retention. [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data).

Repair `RecordingProvider.create_message()` before any paid qualification: it currently reads `.content` from an unawaited real-adapter coroutine. Await synchronous/async results correctly, record after resolution, and close owned adapters during harness teardown. Discovery reproduced the defect with an async fake without making a provider call. Reuse the production resource-ownership pattern.

Read/copy: [Anthropic adapter](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/engine/anthropic.py:31), [OpenRouter HTTP translation](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/engine/openrouter.py:103), [metered loop](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/engine/loop.py:243), [recorder](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/tests/corpus/qualify.py:155), [owned resource cleanup](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/run.py:150).

### 2B. Catalog, default policy and immutable run resolution

1. Add a small server-owned binding catalog keyed by stable binding ID. Each entry names adapter, model/version policy, parameters/context policy, approved endpoint/account-policy identity, secret reference and qualification record/digest. Model IDs are configuration values, not a fixed two-model enum.
2. Replace credential-precedence/single-Anthropic checks in Settings, production assembly and Engine with explicit catalog resolution. Multiple configured credentials are valid; each enabled production binding must be individually eligible. Host control remains development-only. OpenRouter requires its own later production admission evidence; a direct OpenAI adapter does not implicitly qualify it.
3. Persist a versioned deployment default binding in the existing store and audit changes in the same transaction. Proposed APIs: a safe catalog/default read and an operator-only `POST /api/admin/provider-default` with `binding_id` and `expected_version`. The browser cannot submit credentials, URLs, arbitrary parameters or a self-asserted qualification. Keep the default-selection version separate from each binding's execution-policy digest, so changing the default does not invalidate an unchanged model's qualification.
4. Resolve the default once at run admission and persist the complete identity with the run. Use that identity to find the adapter at every later execution boundary, replacing comparisons/invocations against the single `self.provider`. Cover direct runs, document-first intake, Deep Research, upgrades, background continuations, recovery and acceptance. Keep old bindings available while their runs need them and policy permits use. Historical reading and offline verification use retained identities/bytes and do not require a live provider connection.
5. Make qualification eligibility verify the selected candidate, not just a record's self-hash. Current v1 `ProviderQualification.validate_binding` checks provider/methodology/expiry but has no candidate-image fields. Extend the existing versioned qualification record with candidate commit, image-set manifest digest and corpus digest, reusing the harness's evidence identities; validate these during production eligibility checks. Preserve historical v1 records for reading, and never relabel legacy runs with the new default.
6. Keep concurrency at two provider calls and twenty active jobs across the entire engine, regardless of catalog size. Drain the engine before closing each owned adapter exactly once. Updating the default does not close adapters used by existing runs.

Read/copy: [Settings](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/config.py:25), [build_provider](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/run.py:26), [Engine binding checks](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/engine/runtime.py:248), [identity guard](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/engine/runtime.py:360), [qualification validation](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/engine/provider.py:299), [admission persistence](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/storage/runs.py:824).

### 2C. Operator switch and visible provenance

Add the provider/model default selector to Admin with the current policy version, qualified choices, a change receipt and clear availability reasons. Show the resolved provider/model on Run and historical run views using existing identity fields. Resolve a concurrent default change atomically: every new run gets exactly one valid binding. Update deployment env/Compose wiring, secret redaction and the capability map.

Verification for Phase 2:

- OpenAI and Anthropic satisfy the same host tool/schema/evidence/usage checks. Async and synchronous recorder fakes both complete and close correctly.
- Start a Claude run, switch the default to OpenAI, then resume/recover/accept the Claude run; a new intake uses OpenAI. Repeat in reverse and across a process restart. Screen-to-full upgrade retains its original binding.
- Revoked, expired, unavailable, mismatched or unqualified bindings fail before generation; a different returned model is accounted for and refused. No automatic vendor fallback occurs.
- Two simultaneous default updates obey expected-version CAS. Unauthorized users cannot change policy; no secrets appear in responses, logs, events or artifacts.
- Concurrent runs across both adapters still share the existing ceilings. Failed preflight creates no partial run. Shutdown closes all clients without orphaned tasks.
- Qualification selection is explicit in the CLI/workflow and evidence paths include binding identity. Reuse [identity tests](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/tests/test_provider_identity.py), [run preflight/recovery tests](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/tests/spec/test_runs_spec.py:1369), [qualification tests](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/tests/test_qualification_harness.py).

Guards: no new gateway framework, per-provider multiplication of global limits, silently relaxed identity equality, invented SDK methods, provider-hosted web/file tools, or raw hidden reasoning persistence. Unsupported model capabilities mean ineligible selection until resolved and qualified.

## Phase 3 — Recover scanner failures and report readiness honestly

Depends on Phase 0. Can be implemented independently of Phases 1–2.

Inspect the pinned ClamAV image's startup/update scripts. Make daemon death terminate its container, allowing the existing restart policy to recover it; preserve initial signature loading and FreshClam updates. Do not assume replacing the entrypoint with `clamd` preserves initialization. Budget memory for signature reload as well as steady state and record the supported hardware profile. [Official container guidance](https://docs.clamav.net/manual/Installing/Docker.html).

Add a bounded scanner probe to the cached production readiness path. Extend the strict health response with a safe scanner status (`ready`, `unavailable`, or `not_required` for the development bypass) and show an actionable upload-unavailable state. Overall readiness requires `ready` in production; development must not claim it proved a scanner connection. A `PING` must receive a valid `PONG`; readiness is not permission to skip per-upload scanning. [ClamD protocol](https://docs.clamav.net/manual/Usage/ClamdProtocol.html).

Read/copy: [Compose scanner](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/deploy/docker-compose.yml:27), [production scanner boundary](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/sources/domain.py:120), [cached readiness](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/engine/runtime.py:2200), [strict health model](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/responses.py:61), [SIM-028](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/tests/spec/test_simulations_spec.py:508).

Verification: on an isolated production stack with signatures present, clean upload succeeds; kill the daemon while container PID1 is alive; readiness degrades within its documented TTL and clean uploads return 503 without admission/vault side effects; the container restarts and uploads recover automatically. Repeat after a signature reload; EICAR remains refused. Record detection/recovery duration, platform, image and peak memory. Set and meet a recovery bound in the Phase 0 deployment decision using the measured startup profile.

Guard: a container healthcheck alone is not recovery, an EICAR substring check alone is not proof of the daemon path, and the old development soak cannot prove production scanner behavior. Keep liveness supervision distinct from dependency readiness so an outage does not cause an application restart loop.

## Phase 4 — Load source summaries and preserve complete search

Depends on Phase 0. Complete before the citation-navigation work in Phase 5.

1. Capture a fresh baseline on the chosen code/image, hardware and dataset. Retain request counts, response bytes, query/serialization time, CPU/memory, success/refusal counts and p50/p95. Historical `b88` read p95 was 1.28 s for cases, 1.41 s for sources and 1.20 s for case detail; it does not establish the current bottleneck.
2. Add a distinct strict source-summary type and narrow query, using `list_source_filenames()` as the projection pattern. Proposed `GET /api/cases/{id}/source-summaries` serves bounded pages of metadata/block counts without block text or application-side JSON materialization. Define stable pagination and update route/response coverage.
3. Move Sources and Report inventories to summaries. Reuse the existing case-scoped source-detail GET only when a source is selected or a citation is opened. Preserve request cancellation/generation fences. Provide “show more” beyond the current 40/20-block display caps; add a separate block-page API only if selected-source measurements justify it.
4. Preserve Report's current full-case text/locator search. Move that behavior to a bounded case-scoped server search, proposed `GET /api/cases/{id}/evidence-search`, returning source/block IDs, locators and bounded snippets with stable continuation. Search unopened active sources too. Define empty/short-query behavior, input/result bounds and stale-result cancellation; authorization and live withdrawal checks precede disclosure.
5. Repeat the same profile. If case-list/detail p95 still misses the target, optimize the measured SQL, serialization, event-refetch or queue bottleneck. The source projection is a hypothesis to measure, not a claim that it fixes all latency.

Read/copy: [narrow/full source queries](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/storage/store.py:878), [current source API](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/api/__init__.py:414), [frontend source type](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/frontend/src/lib/api.ts:14), [Report loading/search](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/frontend/src/components/report/ReportStudio.tsx:240), [capacity harness](/Users/ericguei/Claude/Projects/CAOS-LangMVP/qa/capacity.py:589), [historical measurements](/Users/ericguei/Claude/Projects/CAOS-LangMVP/.superpowers/sdd/enterprise-task-13-report.md:557).

Verification: initial Sources/Report inventory requests contain no block text and make no N-per-source detail requests; SQL projections avoid reading full source rows into the application; search finds a term in an unopened document beyond the first page; every block remains reachable; rapid case changes and withdrawn/foreign IDs cannot display unrelated evidence. SQLite and PostgreSQL retain the detailed-source contract. All relevant non-provider reads must meet the existing `<1 s p95` target on the declared profile before recommendation 6 is closed.

Guard: do not globally change `DomainStore.list_sources()` to summaries; execution, model and qualification callers need complete evidence. Do not replace text search with filename-only filtering or introduce a cache/search service without measured need. Agree a document-size/block-count profile consistent with the existing run-manifest ceiling before comparing results.

## Phase 5 — Make evidence and Report context usable

Depends on Phase 4 for lazy evidence access and Phase 1 for final permission predicates.

Implement:

- Extend the shared artifact parser with the supported Markdown table subset and render it through native accessible table markup in both artifact consumers. Reuse the Deliverable table layout. Preserve escaped text, bounded input and readable fallback for malformed tables.
- Carry exact block context in `/sources/?case=…&source=…&block=…` links, drawer state and “Open full source.” Load, reveal, select and focus the cited block even beyond the first page. Source-only citations remain clearly source-level; invalid IDs never silently select the first unrelated block. Historical withdrawn evidence displays its status and cannot become current evidence.
- Initialize Report from the latest accepted snapshot's run pathway, matching backend deliverable authority. Reuse the already served `SnapshotResponse.run_id`, currently omitted from the frontend Snapshot type. An unaccepted selected run or an old pinned Analysis lens must not choose the template. Preserve explicit template choice, case scoping and the existing dirty-draft switch guard.
- Reuse visible `WriteBlocked`/Reader explanations at the arrival point of Model, Run and Analysis. Model already has a Reader note in its assumptions tab; move/reuse it. Fix the `Draft authority vUnavailable` formatting.

Read/copy: [shared parser](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/frontend/src/lib/artifactReader.ts:14), [Sources/ArtifactReader](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/frontend/src/components/Workspace.tsx:1251), [Analysis citations](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/frontend/src/components/Workspace.tsx:1741), [drawer](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/frontend/src/components/WorkbenchShell.tsx:241), [snapshot wire](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/responses.py:303), [Report authority](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/caos/deliverables/service.py:712), [guarded pathway switch](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/frontend/src/components/report/ReportStudio.tsx:556).

Verification: shared normal/malformed/escaped-pipe/hostile-HTML fixtures render safely; tables remain usable at 720 px and 200% zoom; keyboard citation activation, focus return and back/forward work for a block after 40; delayed fetches do not cross cases or overwrite an edited draft. Test Report defaults for every supported pathway, including no accepted authority. Existing read-only and unresolved-identity states remain correctly enforced. Run the existing accessibility sweep.

Guard: retain static-export route conventions and workspace authority/dirty-state machinery. Read installed Next.js guides before frontend code changes, as [frontend AGENTS.md](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/frontend/AGENTS.md) requires. Full notes management or a wider navigation redesign is outside these six improvements.

## Phase 6 — Protect the actual production browser/API journey

Depends on Phases 1–5. Build the harness now; its real-provider execution is a Phase 7 gate.

Adapt the existing complete HTTP journey and browser driver to the shipped static export, production `run.py`, PostgreSQL, worker, scanner and trusted identity edge. Replace direct-store bootstrap with Phase 1's API. Use separate analyst, operator, independent approver and reader sessions. Update stale route/status/lifecycle assumptions rather than assuming `production-inventory.mjs` is executable on the current build.

The successful journey must use real backend responses: intake → completed run/research approval when required → analyst acceptance → Model Build → Analyst Model Revision and Sign-Off → Deliverable Draft/citations → opinion Sign-Off → asynchronous freeze → independent filing → md/pdf/xlsx downloads, detached receipt and offline audit verification. Preserve pathway-specific prerequisites and prior Full Credit authority where an overlay needs it.

Keep fast development browser checks and fixture-based visual/error coverage. Add provider-free production tests for identity, bootstrap, scanner and source contracts to ordinary CI where feasible. Put the credentialed complete journey in the protected enterprise workflow; execute for every enabled binding. Never enable host control in production to make this gate green.

Read/copy: [HTTP journey](/Users/ericguei/Claude/Projects/CAOS-LangMVP/qa/golden_journeys.py), [browser script](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/frontend/scripts/workbench-smoke.mjs), [current browser CI](/Users/ericguei/Claude/Projects/CAOS-LangMVP/.github/workflows/ci.yml:116), [protected workflow](/Users/ericguei/Claude/Projects/CAOS-LangMVP/.github/workflows/enterprise-qualification.yml), [exact export checks](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/tests/spec/test_deliverables_spec.py:1987), [historical contract defects](/Users/ericguei/Claude/Projects/CAOS-LangMVP/qa/FINDINGS.md:12).

Verification: run the complete primary journey in Chromium, Firefox and WebKit; the backend live matrix covers all pathway/depth combinations. Assert real response status/keys, worker completion, source and provider provenance, exact file hashes, independent identity, audit verification and harmless replay. Include stale draft/opinion/model/source refusals and case-standing revocation. Retain traces/screenshots on failure and flag unexpected API errors or 429s rather than accepting a degraded page as a successful journey.

Guard: successful model/membership/freeze/file responses cannot be route-fulfilled fixtures in the production acceptance test. Merely passing a health endpoint or an internal service test does not close recommendation 4.

## Phase 7 — Qualify both vendors and close the candidate

Depends on all implementation phases. This is the final verification phase and closes recommendation 2 plus the integrated acceptance gates.

1. Freeze one new code commit and candidate image set after local checks pass. Record the methodology/corpus/adapter/parameter-policy identities. Keep qualification records as external deployment evidence so creating them does not change the code/image they qualify.
2. Use the repaired harness on that candidate to qualify each explicit binding. Its evaluation assembly may use an unqualified live adapter to produce evidence; that does not relax production admission. Parameterize the existing `plan`, `cell`, `matrix` and `verdict` commands/workflow by binding; these new selection options must be implemented before documenting runnable commands.
3. Run every required corpus cell for all six pathways and supported depths, with three cold repetitions per live cell. Retain per-binding evidence and failures. Every repetition must pass schema, evidence, citation, budget, security and audit gates; independent analysts assess usefulness, permitted/forbidden conclusions and material claims. No average can conceal a failed cell.
4. Issue each eligible binding's digest-bound qualification record with the existing policy's 90-day expiry, then deploy the unchanged candidate in production mode. Run Phase 6's full browser journeys with both vendors and the default-switch/recovery checks. Qualification and production deployment proof are separate required results.
5. Repeat the declared capacity profile and scanner failure/recovery drill; compare Phase 4's measurements on equivalent hardware/data/load. Keep host-control capacity results labeled as such. Record complete green/open/blocked/failed outcomes for the new candidate, without carrying forward old pass claims.

Read/copy: [qualification policy and harness](/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/tests/corpus/qualify.py:53), [model gates](/Users/ericguei/Claude/Projects/CAOS-LangMVP/ENTERPRISE_TESTING_READINESS.md:263), [qualification decision](/Users/ericguei/Claude/Projects/CAOS-LangMVP/docs/DECISIONS.md:721), [capacity harness](/Users/ericguei/Claude/Projects/CAOS-LangMVP/qa/capacity.py).

External inputs to prepare while coding proceeds:

| Input | Owner | Required for |
|---|---|---|
| OpenAI and Anthropic API access, exact model IDs and approved account/region/retention settings | Enterprise platform/data owner | Live requests and eligible model catalog |
| Approved qualification spend envelope | Enterprise test owner | Paid matrix/journey execution |
| Analyst-attested answer keys and independent reviewers | Credit/model-risk owners | Analytical qualification |
| Licensed market marks C20, stressed case C21 and question-specific research pack C22 | Corpus/data owners | Every required live cell |
| Production-shaped IdP subjects for analyst/operator/approver/reader | Identity owner | Real permission and filing journey |
| Declared hardware, document/block profile and scanner recovery bound | Platform/test owners | Comparable latency and availability evidence |

The plan can be implemented without these inputs; live qualification cannot be marked complete without them. Each selectable model must have its own current passing record. Missing credentials, packs or approvals remain explicit blocked results.

## Execution order, checks and handoff

Recommended order: Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7. Phases 1, 2, 3 and 4 can be developed independently after the decisions are recorded, using separate worktrees; integrate shared API/store/Workspace changes sequentially. Split Phase 2 into its three slices to keep reviews manageable.

For each implementation phase:

1. Re-read its exact references and inspect callers before editing. Follow existing strict request/response and transaction patterns; update OpenAPI key sets, security route classification, capability/quality ledgers and deployment docs when affected.
2. Add focused regression checks at the actual failure boundary, then run the relevant existing suites. After code changes run the user's required `confidence-review`; after non-trivial production-code changes also run `rewrite-tournament` in post-edit mode. The older prompt series' tournament waiver does not apply to this request.
3. Run backend lint/security/contract checks and frontend lint/typecheck/unit/build checks as applicable. Preserve the configured Python matrix and PostgreSQL race coverage. Run the full required repository/CI gates on the integrated candidate.
4. Record the commit, changed behavior, commands/results and outstanding external inputs in the phase handoff. Do not rewrite historical candidate evidence or unrelated active Claude progress files.

Final acceptance: all six coverage rows have retained passing evidence; both OpenAI and Anthropic are usable through the enterprise switch; every enabled model is independently qualified; an ordinary analyst-created case completes independent filing; scanner recovery is automatic; exact citations/search remain complete; read latency meets the declared target; all required regression, browser, accessibility and security checks pass.
