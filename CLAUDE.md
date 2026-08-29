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

- **Wire strictness.** Every JSON success serves a named strict model from
  `caos/server/caos/responses.py` (`extra="forbid"` both ways). Nothing
  undeclared is ever served; new fields mean a model change plus an update to
  the pinned key sets in `caos/tests/spec/test_http_contracts_spec.py`. SSE and
  binary downloads are the only non-JSON exemptions (`OPENAPI_EXEMPT`).
- **Transactional pairing.** Governed writes commit state + audit event in one
  transaction; run-state transitions commit state + run event in one
  transaction, and every event insert rides a conditional transition (zero rows
  updated → no event), which is what makes terminal events exactly-once.
- **Boundary text.** Every string that can enter pinned state or events is
  validated at the API boundary: must UTF-8-encode, lone surrogates rejected,
  NFC-normalized.
- **Auth edge.** Dev trusts `x-caos-role`; production derives role from OIDC
  groups only — client role headers never escalate (`identity.py`). Unknown
  runs and unauthorized runs return the same 404.

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
- Suite: `python -m pytest caos/tests -q` — fully green (392). Spec tests
  (`caos/tests/spec/`) are the contractual surface — they pin invariants and
  wire shapes; phase-2 tests cover ingestion/store/bundle/config. The surrogate
  boundary test sends its lone surrogate as a pre-encoded `\ud800` JSON escape
  (httpx cannot UTF-8-encode the raw character — `SPEC_RECONCILIATION.md`
  addendum).
- Frontend: `npm run lint`, `npx tsc --noEmit`, `npm run test:unit`,
  `npm run build`; browser checks against the combined app on `:8000`:
  `npm run a11y` and `npm run test:workbench` (both green).
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
- The 2026-08-27 security review's remaining findings are open and recorded in
  `.agent-reviews/redteam.md` (2026-08-28 section): `run_sec_audit.py` accepts a
  pre-handler `422` as authentication evidence, so it cannot detect an
  unauthenticated route; a global `READER` may create cases and is stored as
  case `ANALYST`; the edge serves no HSTS/CSP/nosniff and leaves `/docs` on; no
  per-subject rate, SSE-connection, or preview-concurrency limit exists; backups
  are plaintext with an unkeyed `cksum` manifest; several deployed images, apt
  packages, Actions, and the Trivy installer are tag- or branch-mutable; and the
  AI PR reviewer holds an API key on `pull_request` from any branch.
- The export half of `worker.run_pending` still writes `EXPORT_FAILED` with no
  CAS at all — the build half is now bound to the identity it dispatched, the
  export half is not.
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
