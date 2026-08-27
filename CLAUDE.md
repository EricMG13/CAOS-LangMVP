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
- Visual language is established: dark institutional terminal, semantic color
  only, motion only for live state. `DESIGN.md` and `.impeccable.md` govern;
  inherit, don't reinvent.

## Running and testing

- Dev server: `python caos/server/dev.py` (SQLite under `.dev-data`, startup
  recovery, serves `caos/frontend/out` when built). Deterministic screen routes
  need no API key; agent execution requires `AGENT_EXECUTION_ENABLED=true` +
  `ANTHROPIC_API_KEY`.
- Suite: `python -m pytest caos/tests -q`. Spec tests (`caos/tests/spec/`) are
  the contractual surface — they pin invariants and wire shapes; phase-2 tests
  cover ingestion/store/bundle/config. One known red:
  `test_focus_questions_reject_surrogates_at_the_api_contract` (httpx cannot
  serialize the surrogate client-side on Python 3.14; the server contract was
  verified with a raw-bytes request — `SPEC_RECONCILIATION.md`).
- Frontend: `npm run lint`, `npx tsc --noEmit`, `npm run test:unit`,
  `npm run build`; browser checks against the combined app on `:8000`:
  `npm run a11y` (green) and `npm run test:workbench`.
- Lint: `ruff check --config ruff.toml caos/server caos/tests --exclude
  caos/server/caos/methodology/vendor`.

## Known gaps (v0.1.0 — honest ledger)

- The ported frontend calls some routes this server does not yet serve; those
  surfaces degrade or stay hidden: Command Center lens (`/cases/{id}/lens`),
  Admin Studio (`/admin/audit`, `/admin/bundle`), Report Studio deliverables
  workspace (`GET /cases/{id}/deliverables/{pathway}`), model scenarios /
  one-way sensitivities / worksheet reads / rebase-preview / revision export
  under the frontend's paths, deep-research plan approval. A paused run has no
  resume control in the UI (`POST /api/runs/{id}/resume` exists server-side).
- `npm run test:workbench` is red in the Report Studio scenario-exhibit step
  (mocked-flow scope switch); everything through workspace authority, Run
  Console, palette, and deep research passes.
- CI (`.github/workflows/ci.yml`) references entrypoints and manifests that do
  not exist yet: `caos/server/run.py`, `worker.py`, `requirements*.txt`,
  `caos/scripts/build_frontend.sh`, `run_sec_audit.py`, `caos/.env.example` —
  the browser, image, deploy-assets, and security jobs cannot run as written.
  `caos/server/dev.py` is the only entrypoint in-tree.
