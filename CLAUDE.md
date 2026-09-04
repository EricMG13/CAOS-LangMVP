# CLAUDE.md — engineering contract

This file is the contract for working in this repo. `docs/DECISIONS.md` is the
binding decision record (later sections override earlier ones); the
invariant-to-test table lives in `SPEC_RECONCILIATION.md`; `CONTEXT.md` defines
the product vocabulary — use its terms, avoid its "avoid" terms. For frontend
work, `DESIGN.md` and `.impeccable.md` govern the visual language.

## The ten invariants (never weaken)

Each has a named failing test — see the table in `SPEC_RECONCILIATION.md` for
the exact test IDs. Any change that would make one of these tests pass
vacuously is wrong even if the suite stays green.

1. Runs execute only against the pinned, immutable source set. Supplied-only
   evidence; web discovery is structurally banned; withdrawal is checked live.
2. Every `read_evidence` is validated at the host boundary and fails closed
   with a typed refusal — no text ever returned on refusal.
3. The host owns identity. Provider-claimed frontmatter never survives;
   checkpointed digests are expectations re-verified against the store.
4. Methodology authority is the verified vendored bundle — integrity checked on
   the bytes at use. A run pinned to one build never executes under another.
   Behavior changes ride wrappers or registry entries *where they can*: that
   seam leaves the whole-tree pin meaningful and stays preferred. The bundle
   under `caos/server/caos/methodology/vendor/` may be edited in-tree, but only
   under a dated `DECISIONS.md` entry recording the change and regenerating the
   manifests (`caos/scripts/regenerate_deploy_v_integrity.py`) — see §14.11,
   which supersedes §12.27's "the bundle is never edited". Because a bundle
   change moves the pin with it, that entry, not
   `test_vendored_bundle_is_the_approved_unmodified_release`, is the authority
   for what the tree should contain.
5. Every gate where execution waits on a human is a digest-bound interrupt;
   approval binds the exact reviewed content (preview digest + input
   fingerprint). Single-actor releases (model Sign-Off) are store CAS
   transactions, not interrupts.
6. Execution is durable and exactly-once: resume from the last checkpoint,
   never restart. A crash in the commit gap yields one artifact, one charge,
   one terminal event.
7. Model calculation is pure and finite — non-finite values and zero
   denominators refused before use.
8. Budgets fail closed — every ceiling refuses the next operation before
   overspend; no provider call without a reservation.
9. Module output survives only as the strict canonical envelope — bounded
   schema, undeclared fields refused, citations only from delivered evidence.
10. A run's route is static: node set and edges are a pure function of
    (pathway, depth). No data-selected edges, ever. Replay from the same pins
    is equivalent by the same path.

Standing rules that back them:

- **Wire strictness.** Every JSON success serves a *named* model from
  `caos/server/caos/responses.py`; new fields mean a model change plus an update
  to the pinned key sets in `caos/tests/spec/test_http_contracts_spec.py`. Two
  carve-outs are real and deliberate, so do not read "strict" as universal. SSE
  and binary downloads are not JSON at all (`OPENAPI_EXEMPT`). And six
  service-owned envelopes — model queue, assumption registry, preview, scenario,
  revision, frozen deliverable — subclass `OpenWireModel` (`extra="allow"`)
  because their payload shape belongs to the model/deliverable service rather
  than the wire contract. Everything else is `extra="forbid"` both ways and
  serves nothing undeclared.
- **Transactional pairing.** Governed writes commit state + audit event in one
  transaction; run-state transitions commit state + run event in one
  transaction, and every event insert rides a conditional transition (zero rows
  updated → no event), which is what makes terminal events exactly-once.
- **Boundary text.** Every string that can enter pinned state or events carries
  `BoundaryText`, never a bare `str`: it must UTF-8-encode (lone surrogates
  rejected), carry no control bytes and no bidirectional override/isolate
  controls (CVE-2021-42574 — directional *marks* stay legal for RTL issuer
  names), and it is NFC-normalized *before* the length bound is applied. Bare
  `str` on a field that reaches a revision, a frozen payload or an audit event
  is a defect: it lets a control byte through to break the XLSX render, and it
  lets two spellings of one string mint two lineages.
- **Auth edge.** Dev trusts `x-caos-role`; production derives role from OIDC
  groups only — client role headers never escalate (`identity.py`). Unknown
  runs and unauthorized runs return the same 404.
- **Readiness.** `GET /api/health` serves liveness *and* readiness on one strict
  model: `{status, store, bundle, checkpointer}`, 200 when all hold and 503
  otherwise. The probes really run (store `SELECT 1`, full bundle integrity
  verification, the real LangGraph checkpoint schema plus a bounded write-lock
  acquisition) but at most once per `READINESS_TTL_SECONDS` — the route skips
  both oauth2-proxy auth and the rate ceiling, so its cost is an anonymous
  caller's to spend.

## Where the graph lives

- `engine/graphs.py` — the static route shape: `compiled_route(pathway, depth)`
  compiles the vendored catalog into a `RouteGraph` (nodes, edges, stages).
- `engine/runtime.py` — `Engine`: builds one LangGraph `StateGraph` per
  (pathway, depth), drives it with durable checkpoints (SQLite dev, Postgres
  prod), owns the gate node (source-set pinning), module nodes, budget
  metering, finalization, recovery, snapshot acceptance.
- `storage/runs.py` — the run store: runs, nodes, artifacts, snapshots, budget
  ledger, and the append-only `run_events` log (per-run monotonic `seq`).
- Execution model: `start_run`/`resume` drive **through the plan gate only**
  (`interrupt_after=["gate"]`) so the immutable plan returns immediately. The
  serving entrypoint calls `engine.enable_auto_continue()` to schedule the rest
  on its loop; tests keep explicit control with `engine.wait(run_id)`. Never
  drive one run from two event loops. A module registered with
  `plan_approval=True` (CP-DR) parks its run on a second digest-bound
  interrupt, `PLAN_APPROVAL_REQUIRED`, before any reuse or provider call:
  `engine/research.py` proposes the plan from the pinned run plan, the brief
  and the upstream artifacts, `RunStore.propose_research_plan` persists it with
  its `sha256:` hash, and `Engine.approve_research_plan` is the expected-hash
  compare-and-swap that lets `wait()` re-enter the node (invariant 5,
  DECISIONS §14.16).
- Every pathway declares one model effect (DECISIONS §14.18). Full Credit
  builds the complete model from the six canonical artifacts; Earnings Update,
  Covenant & Refinancing, Relative Value, Distressed and Deep Research resolve
  through `models/service.py::_resolve_overlay_snapshot` — the nearest
  validated Full Credit ancestor, its build re-verified by recomputation, the
  accepted run's calculation records re-executed, one `pathway_effects` entry
  on a byte-identical copy of the base tabs under the overlay's own input
  fingerprint. Every build carries `source_lineage` (one row per pinned
  source: intake disposition, consumers, citing artifacts, model tables,
  binding); a `used` relevant document bound to nothing is
  `MODEL_SOURCE_LINEAGE_INCOMPLETE` and never READY. Readiness answers
  `FULL_DEPTH_REQUIRED`, `PRIOR_FULL_CREDIT_MODEL_REQUIRED`,
  `DEEP_RESEARCH_NO_NUMERIC_EFFECT` and `RELATIVE_VALUE_MARKET_MARKS_REQUIRED`
  as NOT_READY preconditions; the READY transition audits `model.build_ready`
  in its own transaction.
- Run progress reaches the UI as graph events: `GET /api/runs/{id}/events` is a
  thin SSE tail of `run_events` (Last-Event-ID resume; stream closes once a
  terminal run is fully delivered). The frontend never reads event payloads —
  event names trigger a RunRecord refetch.
- Publication (DECISIONS §14.19, Task 10). The analyst signs an opinion on the
  exact saved revision (`POST …/deliverables/{pathway}/opinion`, append-only
  `deliverable_opinions`, expected-head CAS); freeze refuses without a current
  sign-off and refuses an `ANALYST_JUDGMENT` narrative that states an uncited
  figure. `POST …/freeze` renders nothing: it queues a
  `deliverable_freeze_jobs` row and `worker.py` renders md/pdf/xlsx from the
  frozen payload's `publication` document, publishes hash-addressed, reads
  each export back verified, and only then writes the FROZEN record — so a
  local freeze completes only with `python caos/server/worker.py` running
  beside `dev.py`, exactly like model builds. Filing refuses the opinion
  signer and the freeze actor (`APPROVER_NOT_INDEPENDENT`) and writes an
  immutable detached receipt (`GET …/by-id/{id}/receipt`); the approved bytes
  always read `PENDING APPROVAL`. `POST /api/cases/{id}/members` provisions a
  distinct approver (stored case APPROVER/ADMIN standing plus a current global
  writer role). The audit log is append-only and hash-chained per case
  (`audit_chain_heads` lock row; `store.audit_chain`/`verify_audit_chain`);
  `GET /api/cases/{id}/audit-package` serves the case package and
  `caos/server/caos/audit/verify_package.py` verifies it with the standard
  library alone, re-rendering the Markdown export from the frozen payload.
  `caos/publishing/markdown.py` is copied verbatim into the verifier and a
  test pins the copy; change them together. PDF text is shaped from the
  vendored DejaVu bundle (`caos/server/caos/publishing/fonts/`, digests in
  `renderers.FONT_BUNDLE`, hermetic fontconfig, hinting off) and never from
  the host's "sans"; the cross-format goldens pin page counts under that
  bundle, so a renderer change is reviewed by regenerating them
  (`CAOS_REGENERATE_GOLDENS=1`) after inspecting every page and sheet.
- `observability.py` — structured JSON logs on stdout (stdlib only). Seven log
  points and no debug channel: run/node transitions (all of them via
  `RunStore._emit`), typed refusals, provider call start/finish, budget
  reserve/reconcile, the gate interrupt, startup recovery, worker job failures.
  **Never log source text, evidence block text, module output, prompts, or
  anything else a document produced** — log the typed code, never `str(exc)`
  from either process. The worker records exception classes only. Every string,
  including nested mapping keys, is redacted and truncated to `MAX_STRING`;
  `spec/test_observability_spec.py` enforces the ban with a sentinel document
  driven through real ingestion and a real agent node.

## How to add or upgrade a module

The registry is the only seam (`DECISIONS.md §7`). Adding or upgrading a module
touches `caos/server/caos/modules/registry.py` alone: one entry —
`module_id`, `mode` (`agent` | `deterministic`), `skill_slug`,
`reference_files`, `max_output_tokens`, `aliases` for superseded ids (see
`MODULE_GRANULARITY.md`). The graph builder consumes only the registry and the
catalog routes. Land it as an isolated commit: the registry entry plus its
wiring test (`caos/tests/test_module_wiring.py` pattern). Do not touch the
engine, the bundle, or the routes.

## Frontend

- `Workspace.tsx` is deliberately one file: a workspace-authority state machine
  (`lib/workspaceAuthority.ts`, reducer-tested) that arbitrates case/run
  authority against stale responses, route replays, and cross-case races. Don't
  decompose it casually; behavior changes go through the authority unit tests
  and the workbench smoke.
- Static export (`output: "export"`, trailing slashes). Dev proxies `/api/*` to
  `:8000`; production serves the export from the server image. Route hrefs must
  keep the trailing slash (see the comment in `lib/workbench.ts#withQuery`).
  The export and the JSON API are served gzipped — `create_app` installs
  `GZipMiddleware` (`minimum_size=1024`), and its content-type exclusions are
  load-bearing: `text/event-stream` keeps the run-events tail streaming and the
  XLSX media type is excluded because a workbook is already a zip.
- Next emits a `noModule` legacy polyfill bundle (112,594 B, byte-identical to
  `next/dist/build/polyfills/polyfill-nomodule.js`) that every route's HTML
  references. There is no config switch for it and no browser with ES-module
  support fetches it — do not "optimize" it away by deleting build output.
- The run console has exactly one home. Portfolio links into a credit and
  Deep-Dive reads accepted artifacts; neither renders the compile form or the
  accept control. Run progress, compilation and acceptance stay in
  `/run-console/`.
- The golden journey is document-first (Task 8, DECISIONS §14.17): the Cases
  page's `.cases-intake` panel posts files and nothing else to
  `POST /api/intake`; the server creates or resolves the case, admits every
  file or none in one transaction, classifies the evidence, selects the route
  and starts the run. Issuer, label, document types, periods, dispositions and
  the route are served as labelled machine suggestions and never taken from
  the browser or from document instructions. The create-case and compile
  forms remain as advanced controls; a completed intake run is opened for
  review in the run console and is never accepted on the analyst's behalf.
- Visual language is established: dark institutional terminal, semantic color
  only, motion only for live state. `DESIGN.md` and `.impeccable.md` govern;
  inherit, don't reinvent.

## Running and testing

- Dev server: `python caos/server/dev.py` (SQLite under `.dev-data`, loopback
  bind, startup recovery, serves `caos/frontend/out` when built). Every route
  is provider-backed at both depths (`docs/DECISIONS.md` §14.3, §14.12), so no
  route runs without a provider: development agent execution requires
  `AGENT_EXECUTION_ENABLED=true` and exactly one provider key, or
  `CAOS_PROVIDER=host_control` for the development-only answer-keyed binding
  the keyless browser gates use (orchestration proof, never analysis; refused
  in production). The placeholder deterministic executor is test-only and
  returns `DETERMINISTIC_EXECUTOR_UNAVAILABLE` on any ordinary path.
- Production entrypoints: `caos/server/run.py` (combined app — validated env,
  qualified Anthropic-only provider assembly, auto-continue, recovery; the
  Docker `app` target's CMD) and
  `caos/server/worker.py` (polls the store for QUEUED model builds/exports and
  executes them through the current Python workbook renderer; its image includes
  LibreOffice, but runtime exports do not yet invoke the verified LibreOffice
  path). `worker.py --once` runs a single pass.
- Development evidence (not candidate qualification): the suite count is
  measured, never quoted from memory; the enterprise-readiness task reports
  under `.superpowers/sdd/` carry the exact result of each landed task on the
  declared Python 3.14 interpreter. The security audit and quality-ledger
  gates each started with 10 failures and were repaired in enterprise-readiness
  Task 1. None of this qualifies live analysis or an enterprise candidate.
  Spec tests (`caos/tests/spec/`) are the contractual surface —
  they pin invariants and wire shapes; `test_injection_spec.py` pins the
  behavioural half of the prompt-injection defence: adversarial documents in
  `caos/tests/fixtures/injection/` driven by a provider double that obeys them,
  asserting only the host's refusal (`SPEC_RECONCILIATION.md` carries its
  anti-vacuity ledger). `test_evidence_spec.py` enumerates the whole
  `read_evidence` argument surface — 33 refusal shapes, each asserted for its
  typed code *and* for invariant 2's no-text clause read literally (nothing in
  the exception chain, the delivered set, or the ledger) — plus the read path's
  only bound, which is run-wide and not per-node (`SPEC_RECONCILIATION.md`
  carries the shape table and its anti-vacuity ledger).
  Phase-2 tests cover ingestion/store/bundle/config. The
  surrogate boundary test sends its lone surrogate as a pre-encoded `\ud800`
  JSON escape (httpx cannot UTF-8-encode the raw character —
  `SPEC_RECONCILIATION.md` addendum).
- Frontend: `npm run lint`, `npx tsc --noEmit`, `npm run test:unit`,
  `npm run build`; browser checks against the combined app on `:8000`:
  `npm run a11y` and `npm run test:workbench` (both green). The workbench
  journey is one Playwright script over three engines: `CAOS_BROWSER=chromium
  |firefox|webkit npm run test:workbench`, or `npm run test:browsers` for all
  three in sequence (`npx playwright install firefox webkit` once); every run
  writes `caos/frontend/test-results/<browser>/workbench-report.json` and keeps
  a trace and a full-page screenshot only on failure (`CAOS_TRACE=0` disables
  tracing). The a11y sweep scans empty, populated, review, filed, loading,
  error and refusal states, each asserted on screen before axe runs.
- Perimeter gates (Task 12b, DECISIONS §14.22): `run_sec_audit.py` discovers
  routes from OpenAPI and drives nine actors through every route (outsider,
  global-admin outsider, removed member, stored reader, global admin stored
  as reader, downgraded writer, analyst, approver, administrator), cross-case
  ids in bodies and sub-paths, mass assignment and the commit-time standing
  recheck; `caos/tests/test_workflow_security.py` pins every workflow
  read-only, commit-pinned, digest-pinned and hashed; `caos/scripts/
  recorded_review.py` is the pull-request check (`security-review.yml`) and
  `caos/scripts/scan_floors.py` refuses a scanner that scanned nothing;
  `caos/tests/spec/test_limits_spec.py` proves below/at/above for every
  admission and size ceiling; `docs/PERIMETER_LEDGER.csv` (pinned by
  `test_perimeter_ledger.py`) maps IAM/SEC/WEB/PERF to their mechanism.
  `qa/capacity.py limits` runs the ceilings over HTTP against a host-control
  server; `profile`, `baseline` and `compare` are candidate-only harnesses
  and never a capacity or availability claim. The profile drives subjects at
  the declared 300/min, so the application's typed 429s are expected traffic:
  every driver, holder and sampler thread backs off and retries through
  `admitted()` and records a failure under `driver_error` instead of dying
  (`caos/tests/test_capacity_harness.py`; defects D-013–D-015 from the first
  candidate's soak). Candidate evidence is committed under
  `.superpowers/sdd/candidates/<id>/` and is excluded from the quality-ledger
  file scan (`docs/quality_ledger_coverage.py`) because it is evidence about
  the product, not the product.
- Real-issuer corpus (`caos/tests/test_corpus_pathways.py`, marker
  `corpus_run`): one 30-document Carnival Corporation leveraged-credit case,
  acquired from the issuer's investor-relations site and pinned by SHA-256 in
  `caos/tests/corpus/sources.txt`. `fetch.sh` only acquires test fixtures; every
  application interaction uploads those retained bytes through the public
  multipart source route. `documents/` is gitignored. Default runs the cheaper
  classification subset and Full Credit at both depths; `CORPUS_FULL=1`
  classifies every document and runs every executable route. CI and nightly
  hard-fail when a required fixture cannot be acquired and cache only a complete
  fetch.
- Qualification corpus and harness (Task 11, DECISIONS §14.20): every pack
  C01–C22 is a versioned manifest plus an attested answer key under
  `caos/tests/corpus/packs/<id>/` (`manifests.py` validates and resolves bytes;
  `synthetic.py` regenerates C02–C16, digest-checked; C20–C22 are external
  under `$CAOS_CORPUS_EXTERNAL_DIR`). `caos/tests/corpus/qualify.py` runs the
  matrix (`plan`, `cell`, `matrix`, `verdict`, `pin`): one cell per fresh
  process, scored by `scoring.py`, bound to provider identity, corpus digest,
  build, date, expiry and reviewer; a host-control binding reads
  ORCHESTRATION_PROOF, never QUALIFIED. Run it keyless:
  `ANTHROPIC_API_KEY= CAOS_PROVIDER= caos/server/.venv314/bin/python
  caos/tests/corpus/qualify.py matrix --binding host_control --packs C03
  --reviewer <name>`. A fixture or key change is re-pinned with `pin`; the
  tool refuses to re-sign an analyst-approved key. The protected
  `.github/workflows/enterprise-qualification.yml` runs the live matrix on
  dispatch. `docs/QUALITY_QUALIFICATION.csv` maps MOD-001–MOD-025 to the
  harness, the runtime or an external input.
- PostgreSQL target (Task 12a): `caos/tests/test_postgres_races.py` and the
  real-database tests in `test_single_instance.py` run only with
  `CAOS_TEST_POSTGRES_URL` set to a role that may `CREATE DATABASE` (every test
  makes and drops its own database); `CAOS_REQUIRE_POSTGRES=1` turns a missing
  URL into a failure, which is how CI's `postgres` job runs them against the
  digest-pinned container. Locally, point the URL at the QA container.
  Failure simulations SIM-001–SIM-030 map to retained tests in
  `docs/SIMULATION_LEDGER.csv`, pinned by `caos/tests/test_simulation_ledger.py`.
- Lint: `ruff check --config ruff.toml caos/server caos/tests --exclude
  caos/server/caos/methodology/vendor`.
- Dependencies: `caos/server/pyproject.toml` is the single source of truth.
  `requirements.txt` and `requirements-dev.txt` are **generated** locks — fully
  pinned, transitively complete, and hashed — and the Docker image and CI both
  install them with `--require-hashes`, so a compromised re-release of an
  already-pinned version cannot enter a build. After changing a dependency,
  regenerate both with the command in each file's own header; forgetting to
  turns `caos/tests/test_dependency_pins.py` red rather than surfacing at
  deploy time. The cost is real and deliberate: the old `>=` floors meant every
  image rebuild silently pulled the newest starlette/uvicorn/sqlalchemy,
  security fixes included. Frozen pins stop that, so the locks go stale until
  someone recompiles — pip-audit (`security` job) and Trivy (`image` job) are
  what turn that staleness into a red build instead of silence. Recompiling is
  the response to a red gate, not an optional hygiene chore.

## Known gaps (honest ledger)

- The AI pull-request review is gone (ETR-B06): `security-review.yml` runs
  the recorded read-only diff review instead, and no workflow holds a secret
  outside the dispatch-only qualification job or a write token anywhere.
- Admin Studio remains an explicit unavailable capability (`/admin/audit`,
  `/admin/bundle`). Worksheet reads, one-way sensitivity, tornado, revision
  rebase preview, build/revision export and download, and the Deep Research
  plan routes (`GET /runs/{id}/research-plan`,
  `POST /runs/{id}/research-plan/approve`, Task 7) are served and must not be
  re-added to this gap list. `deep_research_available` on the case wire is
  derived from the engine (cut, compiled route, registry, provider binding),
  never a literal.
- Deep Research is qualified by host control only. The corpus test runs
  `DEEP_RESEARCH` at full depth on the Carnival pack with a fixture brief and
  proves the brief, the approval gate and the route complete; it proves nothing
  about any research question. The question-specific C22 pack and live-model
  qualification remain external inputs (BLOCKED EXTERNAL in
  `.superpowers/sdd/enterprise-task-7-report.md`).
- The governed builder and canonical deliverable implementation exists, but its
  deterministic/scripted development proof does not qualify live analysis.
  Enterprise qualification across all six pathways remains open.
- The encrypted Postgres/vault backup streams and restore checks were exercised
  with real `age`, PostgreSQL, and Docker-volume data on 2026-08-30; the three
  defects that drill found (`caos/deploy/RESTORE-DRILL-2026-08-30.md` F1–F3)
  were repaired in Task 12a and have regression tests in
  `caos/tests/test_deploy_topology.py`: the store creates its whole schema at
  startup (so the drill's table check holds for a fresh deployment),
  `backup.sh` resolves the vault volume from the app container's `/vault`
  mount or `CAOS_VAULT_VOLUME` and never fails silently, and it pauses the
  app and worker containers for the whole capture so the dump and the vault
  archive share one snapshot point (`checkpoints.db-shm` excluded). The
  scheduled off-host transfer, rotation, and retention were not exercised and
  remain deployment gates.
- The Dockerfile installs `libreoffice-calc` and its 167 apt dependencies
  unversioned. This is an **accepted** gap, not an oversight, and the reason is
  narrower than it looks: apt is not unauthenticated. The `InRelease` file is
  signed by the Debian archive key and carries the SHA256 of every `Packages`
  index, which carries the SHA256 of every `.deb` — so the tamper-evidence
  property `--require-hashes` buys for pip is already present here. What is
  missing is *date* reproducibility: two builds a month apart get different
  point releases (125 MB across 167 files, per architecture). The alternatives
  cost more than they close. Pinning `snapshot.debian.org` freezes the archive
  at a timestamp, which also freezes `apt-get upgrade -y` — the image stops
  receiving Debian security updates until someone bumps the snapshot, turning a
  live patch path into a manual chore, and it makes every build depend on a
  host that is slow and periodically unavailable. Vendoring the `.debs` means
  125 MB per architecture in the repo, re-vendored on every security update.
  Exact `=version` pins without a snapshot break the build within weeks, when
  Debian's mirrors drop the superseded point release. Trivy's fixable
  HIGH/CRITICAL gate on the built image (`ci.yml`, `image` job) is what actually
  observes what shipped. Promoting this to `docs/DECISIONS.md` is a call for the
  decision owner, not a documentation chore.
- Exports have no claim at all — two workers would both render the same export.
  Only the failure fallback is CAS-bound. Harmless today (single worker,
  content-addressed output, and a second worker is refused at startup), wrong
  under a second worker. Build claims are CAS-bound and, since Task 12a, a
  `BUILDING` row a dead worker left behind is requeued at the next worker
  start (`ModelService.recover_builds`), like `RENDERING` freeze jobs.
- `RequestCeilings` counts in-process, so its ceilings are per app instance.
  That matches the single-instance deployment the SQLite checkpoints already
  force; scaling out means moving them to a shared store first. The instance
  ceiling is enforced, not assumed (Task 12a): `run.py` and `dev.py` take an
  exclusive `flock` on `checkpoints.db.lock` beside the checkpoint database
  (`caos/instance_lock.py`) before recovery runs or a socket is bound, so a
  second app over the same data directory exits `INSTANCE_ALREADY_RUNNING`;
  the PostgreSQL role advisory locks (`store.single_instance`) stay beside
  it, Compose declares `deploy.replicas: 1` for `app` and `worker`, and
  `caos/deploy/ENVIRONMENT_MANIFEST.md` records the ceiling.
- The gzip exclusion for XLSX only covers the model-build download, the sole
  route setting that media type. The deliverable export serves md/pdf/xlsx
  alike as `application/octet-stream`, so its already-compressed formats are
  re-compressed (harmless, wasted CPU). Closing it means serving a real media
  type per format there — a wire-visible change.
- Run checkpoints are SQLite on the data volume even under a Postgres domain
  store (`run.py` notes this); the postgres checkpoint saver is pinned in
  requirements but not wired in the engine. Single app instance only.
- Source-set version allocation locks the case row before it reads the
  current version (`storage/store.py::_next_source_set`), so two concurrent
  ingests into one case cannot both mint the same version. Locking the set row
  instead would not work: `ORDER BY version DESC LIMIT 1 FOR UPDATE` re-reads
  the same unchanged row and still computes N+1. Since Task 12a this and every
  other governed race is proven on two independent PostgreSQL connections in
  `caos/tests/test_postgres_races.py` (CI job `postgres` against the pinned
  container; locally `CAOS_TEST_POSTGRES_URL=postgresql+psycopg://…` against
  the QA container). That target repaired six read-then-write races the
  process locks could not order across connections — event `seq`, the budget
  ledger, duplicate withdrawal, assumption-vs-withdrawal, and the model,
  opinion, draft, freeze and publication heads (`store.lock_case`, a
  transaction-scoped case advisory lock) — and found that the Task 10
  deliverable DDL could not be created through psycopg at all. The
  process-wide locks remain the SQLite mechanism only; SQLite thread races
  and compiled `FOR UPDATE` checks are never PostgreSQL proof
  (`SPEC_RECONCILIATION.md`, "Two-connection PostgreSQL races";
  `docs/DECISIONS.md` §14.21).
- The OpenRouter binding is development-only and meters by estimate, not by
  count. `engine/openrouter.py` is a second provider-port adapter selected by
  `build_provider` only in development when it is the sole configured key.
  Production refuses OpenRouter, and every environment refuses ambiguous dual
  credentials. OpenRouter has no pre-call token-counting
  endpoint, so `count_tokens` measures locally with tiktoken and multiplies by
  `TOKEN_ESTIMATE_MARGIN`. Invariant 8's reservation is therefore approximate on
  this provider in a way it is not on Anthropic; `reconcile_provider` still
  corrects `used` to the actual figures, so the aggregate ceiling holds, but the
  pre-call reservation can be wrong by the margin. The margin is calibrated
  against measurements recorded in the module docstring — raise it, never lower
  it. Run, plan, artifact, snapshot, and attempt records carry the immutable
  provider identity; run events and acceptance audit carry its digest. Usage-valid
  responses that report a different model/version are
  reconciled for spend and then refused before parsing or tool execution. The
  docstring also records why z-ai/glm-5.3-flash cannot complete CP-1.
- Large documents are packed, not indexed line by line. The run's source
  manifest carries one row per block into *every* module prompt, so block count
  must not track document size: `pack_blocks` in `sources/domain.py` emits one
  block per line while a document is small (byte-identical to the old
  extractor, `builtin-v1`, `{"line": n}` locators) and bounded line groups once
  it is not (`builtin-v2`, `{"lines": [first, last]}`), splitting any line wider
  than `MAX_BLOCK_CHARS` instead of refusing it. A 300-page annual report is
  ~145 blocks rather than 7,119, and three 12 MB credit agreements still pin one
  run inside `MAX_MANIFEST_BLOCKS`. What is still refused: extracted text over
  `MAX_SOURCE_TEXT` (12 MB) and uploads over `max_source_bytes` (25 MB). The unit
  CAOS ingests is one user-provided document, not a multi-document container.
- `npm run test:production-inventory` does not pass against this build and never
  could: `caos/frontend/scripts/production-inventory.mjs` walks
  `GET /api/cases/{id}/runs` (only POST is served) and `/api/cases/{id}/members`
  (no route at all), and its `CAOS_CASE_ID` default is a fixture case id from a
  seeded deployment. It is not in CI. Treat it as the inventory for a deployment
  that serves those routes, not as a check on this one.
- The `security` job's `python-version: "3.12"` pin is load-bearing. bandit 1.7.10
  reaches for the `ast.Constant.s` alias a newer interpreter no longer provides;
  under 3.14 it skips all 35 server files and still exits 0, so the SAST gate
  would pass while scanning nothing. The step now asserts bandit's JSON report
  carries no parse errors and covers the server, so a naive version bump fails
  loudly instead of silently.
- Loan-workbook cell text is `BoundaryText` at the importer since Task 9:
  `artifacts/loan_universe.py::_text` runs `validate_boundary_text` after the
  32 KB bound, and a failing cell is the structured finding
  `RV_CELL_TEXT_INVALID` (the workbook is REJECTED). This is the one seam every
  path shares — the CP-3 artifact, the Relative Value model effect and every
  renderer read the stored rows.
- Deliverables for Earnings Update and Covenant & Refinancing still bind the
  prior Full Credit base build (`PRIOR_FULL_CREDIT_BASE`), not the overlay
  build that carries their pathway effect; Relative Value and Deep Research
  deliverables bind no overlay either. The effects ride the overlay builds'
  payloads and exports today; rendering them in published outputs is Task 10.
- Cross-intake restatement is not recorded by intake: a restated annual dropped
  into a case whose original came from an earlier intake is admitted as `used`
  without marking the original `superseded` (`intake/service.py::
  _apply_dispositions` groups the current pack only). The model's lineage then
  binds both by citation. Supersession across intakes is a follow-up.
- Earnings Update and Covenant & Refinancing deliverables bind the prior Full
  Credit base build (DECISIONS §14.18), so their pathway effects reach the
  overlay build and the model export but not the published deliverable; the
  Distressed overlay does render. Binding those two pathways' deliverables to
  their overlay builds is a model-authority change that existing tests pin
  (`test_live_incremental_pathway_publishes_against_a_validated_prior_full_credit_model`)
  and stays open after Task 10.
- The deliverable export route still serves md/pdf/xlsx as
  `application/octet-stream` (a wire-visible decision, unchanged in Task 10);
  the audit package is `application/zip`, which the gzip middleware already
  excludes.
- The audit chain has no external anchor beyond the audit package manifest:
  an actor who can drop the database triggers and rewrite every row after a
  point can re-chain the tail. Detect that by comparing a retained package's
  `audit/head.json` with the live head; an HMAC key or an external timestamp
  anchor is the upgrade path.
- Freezing renders the PDF with pango-view page by page (each page embeds its
  own font subsets), so a filed PDF is roughly 90–150 KB per page and a freeze
  costs two to ten seconds of worker time; the deliverable spec files take
  about seven minutes for that reason. A single multi-page pango render or a
  shared font subset is the upgrade path.
- PDF text in scripts the vendored DejaVu bundle does not cover (CJK, Arabic,
  Indic, …) is shaped by the host's fallback fonts — `fonts-noto-cjk` in the
  image, whatever a developer Mac has. Every span carries an absolute line
  height, so pagination does not move with the fallback face, but glyph
  shapes and advances in those scripts follow the host. Vendoring a CJK face
  (16 MB and up per weight) is the upgrade path if those scripts become
  routine.
- Live qualification has not run. The harness, the manifests and the draft
  answer keys exist; the provider credential, every analyst-scope approval,
  the licensed marks (C20), the Lumen stressed pack (C21) and the research
  pack (C22) are external inputs listed as BLOCKED EXTERNAL in
  `.superpowers/sdd/enterprise-task-11-report.md`. Until they exist every
  `verdict --binding live` is UNQUALIFIED by construction.
- The loan-universe importer opens workbooks `data_only`, so a formula cell
  has no cached value and reads as blank; a formula in an optional numeric
  column imports silently (C08 records this as observed behaviour, not a
  refusal). Refusing formula cells outright is a product decision left open.
- The model-preview ceiling (two in flight per subject) is proven in-process
  (`test_limits_spec.py`); over HTTP a preview against a case with no READY
  build refuses in microseconds, so `qa/capacity.py limits` records the
  observed statuses and points at the in-process proof rather than claiming
  an HTTP observation. The 32 MiB request ceiling is Caddy's (`max_size`); the
  app enforces the 25 MiB source ceiling and refuses a source cap above the
  request cap at startup, and the harness probes the request ceiling only when
  given `--edge-url`.
- Digest pinning has two recorded exceptions beyond apt (below): the Playwright
  browser builds are pinned by the package-lock's playwright version and build
  number and downloaded without a digest check by `npx playwright install`,
  and pip-audit/bandit install from `caos/server/requirements-security.txt`
  (hashed) while apt supplies pango and the CJK fonts. Both are listed in
  `caos/tests/test_workflow_security.py::ACCEPTED_UNPINNED`.
- Dialog openers are passed explicitly, never inferred from
  `document.activeElement`: WebKit does not focus a button or link on click,
  so an inferred opener is `<body>` there and cancelling the dialog drops focus
  to the landmark. `AcceptDialog` and the palette-initiated discard were fixed
  in Task 12b; `closeDrawer` in `WorkbenchShell` still infers and is open. A
  focus repair that runs on a timer must first check where the browser's own
  close restoration left focus and whether the user has moved since
  (`DraftDiscardDialog.dismiss`) — the 24 ms focus steal that fix removed was
  the "flaky" CI focus failure the Task 10 report left open. Under WebKit the
  smoke presses `Alt+Tab` to reach links, drops the CSP line for the
  automation-inserted `<style>body {}</style>`, and does not assert the
  route-intercepted download (Chromium and Firefox prove it). WebKit also
  rejects a same-origin fetch still in flight at navigation with a
  `TypeError` worded `<url> due to access control checks.`, which Next's
  unawaited prefetches turn into a page error on a slow runner; the smoke
  drops that page error only with evidence (WebKit, same origin, that exact
  URL answered 2xx/3xx on this page — `scripts/webkit-teardown.mjs`, D-016)
  and retains every dropped entry in the report.
- Blocks live in one JSON column on the source row, so `read_evidence` parses
  every block of a source on each call. Measured at the ceiling: a 10 MB source
  costs 17 ms per read, so a run's ~80 reads cost about 1.4 s. Fine at current
  volumes, wrong if evidence reads become hot — the fix is a blocks table keyed
  by (source_id, block_id), not a smaller ceiling.
