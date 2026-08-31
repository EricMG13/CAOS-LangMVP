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
   The vendored bundle under `caos/server/caos/methodology/vendor/` is never
   edited; behavior changes ride wrappers or registry entries.
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
  drive one run from two event loops.
- Run progress reaches the UI as graph events: `GET /api/runs/{id}/events` is a
  thin SSE tail of `run_events` (Last-Event-ID resume; stream closes once a
  terminal run is fully delivered). The frontend never reads event payloads —
  event names trigger a RunRecord refetch.
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
- The run console has exactly one home. Cases and Deep-Dive render `RunSummary`
  (status, module progress, a link) and never the compile form or the accept
  control — that is what keeps `/cases/` to one page-level primary action
  (`DESIGN.md:348`).
- Visual language is established: dark institutional terminal, semantic color
  only, motion only for live state. `DESIGN.md` and `.impeccable.md` govern;
  inherit, don't reinvent.

## Running and testing

- Dev server: `python caos/server/dev.py` (SQLite under `.dev-data`, loopback
  bind, startup recovery, serves `caos/frontend/out` when built). Deterministic
  screen routes need no API key; agent execution requires
  `AGENT_EXECUTION_ENABLED=true` + `ANTHROPIC_API_KEY`.
- Production entrypoints: `caos/server/run.py` (combined app — validated env,
  auto-continue, recovery; the Docker `app` target's CMD) and
  `caos/server/worker.py` (polls the store for QUEUED model builds/exports and
  executes them; the only process with LibreOffice, so XLSX rendering lives
  here and nowhere else). `worker.py --once` runs a single pass.
- Suite: `python -m pytest caos/tests -q` — fully green (611 passed with the
  real-issuer corpus downloaded; 12 corpus tests skip without it).
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
  `npm run a11y` and `npm run test:workbench` (both green).
- Real-issuer corpus (`caos/tests/test_corpus_pathways.py`, marker
  `corpus_run`): real annual reports, EDGAR complete submissions and XBRL
  company facts, pinned by URL in `caos/tests/corpus/sources.txt` and fetched
  by `caos/tests/corpus/fetch.sh` (needs `SEC_USER_AGENT`; `documents/` is
  gitignored). Without the corpus the tests skip. Default is a smoke subset;
  `CORPUS_FULL=1` classifies every document and runs every live route. Add a
  document by appending a `<name> <url>` line — nothing else changes. CI fetches
  it on one matrix leg and the nightly runs it with `CORPUS_FULL=1`, both
  cached on the hash of `sources.txt` and both best-effort: a download failure
  skips the corpus tests instead of failing the build, and only a complete fetch
  is cached. Both need the `SEC_USER_AGENT` repo variable set to a contact with
  an email in it — EDGAR answers 403 to a user agent carrying only a name or a
  URL — and warn in the run log when it is unset.
- Lint: `ruff check --config ruff.toml caos/server caos/tests --exclude
  caos/server/caos/methodology/vendor`.

## Known gaps (honest ledger)

- The ported frontend calls some routes this server does not yet serve; those
  surfaces degrade or stay hidden behind the capability gate: Admin Studio
  (`/admin/audit`, `/admin/bundle`), one-way sensitivities
  (`/models/sensitivities/one-way`), worksheet reads
  (`/models/{build_id}/worksheet`), model build export
  (`POST /models/{build_id}/export` — only `GET …/download` is served),
  revision rebase-preview, revision export and revision download
  (`/model-revisions/rebase-preview`, `/model-revisions/{id}/export`,
  `GET /model-revisions/{id}/download` — the download is served for a model
  build only, never for a revision), and deep-research plan approval
  (`/runs/{id}/research-plan/approve`).
  The Command Center lens, the Report Studio deliverables workspace, model
  scenarios/previews, model sign-off and run resume are all served and wired —
  do not re-add them to this list.
- Backup encryption is **untested here**: `caos/deploy/backup.sh` and
  `restore_drill.sh` now encrypt with `age`, but neither `age` nor a running
  Compose stack exists in the dev worktree, so only their syntax is checked.
  Drill a real backup/restore pair before relying on either.
- The Dockerfile still installs `libreoffice-calc` and its apt dependencies
  unversioned. The base images are digest-pinned, so the build is reproducible
  to the layer boundary but not through apt.
- `caos/server/requirements.txt` pins versions, not hashes. pip-audit gates
  known CVEs; nothing gates a compromised release of a pinned version.
- Exports have no claim at all — two workers would both render the same export.
  Only the failure fallback is CAS-bound. Harmless today (single worker,
  content-addressed output), wrong under a second worker.
- `RequestCeilings` counts in-process, so its ceilings are per app instance.
  That matches the single-instance deployment the SQLite checkpoints already
  force; scaling out means moving them to a shared store first.
- The gzip exclusion for XLSX only covers the model-build download, the sole
  route setting that media type. The deliverable export serves md/pdf/xlsx
  alike as `application/octet-stream`, so its already-compressed formats are
  re-compressed (harmless, wasted CPU). Closing it means serving a real media
  type per format there — a wire-visible change.
- Run checkpoints are SQLite on the data volume even under a Postgres domain
  store (`run.py` notes this); the postgres checkpoint saver is pinned in
  requirements but not wired in the engine. Single app instance only.
- `caos/server/requirements.txt` mirrors `pyproject.toml` dependencies by
  hand — change them together.
- Source-set version allocation now locks the case row before it reads the
  current version (`storage/store.py::_next_source_set`), so two concurrent
  ingests into one case cannot both mint the same version. The lock is a no-op
  on SQLite and **has not been exercised against a live PostgreSQL** — only the
  emitted clause is pinned. Locking the set row instead would not work:
  `ORDER BY version DESC LIMIT 1 FOR UPDATE` re-reads the same unchanged row
  and still computes N+1.
- The OpenRouter binding meters by estimate, not by count.
  `engine/openrouter.py` is a second provider-port adapter (selected by
  `build_provider` only when `OPENROUTER_API_KEY` is set and
  `ANTHROPIC_API_KEY` is not). OpenRouter has no pre-call token-counting
  endpoint, so `count_tokens` measures locally with tiktoken and multiplies by
  `TOKEN_ESTIMATE_MARGIN`. Invariant 8's reservation is therefore approximate on
  this provider in a way it is not on Anthropic; `reconcile_provider` still
  corrects `used` to the actual figures, so the aggregate ceiling holds, but the
  pre-call reservation can be wrong by the margin. The margin is calibrated
  against measurements recorded in the module docstring — raise it, never lower
  it. The docstring also records why z-ai/glm-5.3-flash cannot complete CP-1.
- Large documents are packed, not indexed line by line. The run's source
  manifest carries one row per block into *every* module prompt, so block count
  must not track document size: `pack_blocks` in `sources/domain.py` emits one
  block per line while a document is small (byte-identical to the old
  extractor, `builtin-v1`, `{"line": n}` locators) and bounded line groups once
  it is not (`builtin-v2`, `{"lines": [first, last]}`), splitting any line wider
  than `MAX_BLOCK_CHARS` instead of refusing it. A 300-page annual report is
  ~145 blocks rather than 7,119, and three 12 MB credit agreements still pin one
  run inside `MAX_MANIFEST_BLOCKS`. What is still refused: extracted text over
  `MAX_SOURCE_TEXT` (12 MB) and uploads over `max_source_bytes` (25 MB) — an
  EDGAR *complete submission package* hits both, which is correct; the unit CAOS
  ingests is a document, not a filing bundle.
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
- Blocks live in one JSON column on the source row, so `read_evidence` parses
  every block of a source on each call. Measured at the ceiling: a 10 MB source
  costs 17 ms per read, so a run's ~80 reads cost about 1.4 s. Fine at current
  volumes, wrong if evidence reads become hot — the fix is a blocks table keyed
  by (source_id, block_id), not a smaller ceiling.
