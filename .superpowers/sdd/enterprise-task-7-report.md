# Enterprise Task 7 report — Deep Research with a governed brief and approval gate

Executed as `ER-G2` (started 2026-09-02) in `.claude/worktrees/er-task-07-deep-research`
on branch `claude/er-task-07-deep-research`, cut from `origin/main` at `91d9038`
(the Task 6 squash merge, PR #37). Local interpreter: Python 3.14.6
(`uv run --python 3.14 --project caos/server --extra dev`; `uv.lock` removed).
Frontend dependencies installed with `npm ci`; the 30-document Carnival corpus
copied from the Task 6 worktree (gitignored).

## Status

Complete on the branch: every gate below is green; a draft pull request to
`main` carries the same gate table. Two items stay BLOCKED EXTERNAL (Open items).

## Delivered

- **Route and registry.** `DEEP_RESEARCH` joins the engine cut at full depth
  only (`runtime.supported_depths`, `startable_routes()`); the LITE route still
  compiles (the route goldens in `test_bundle.py` are untouched) and the engine
  refuses it as `DEPTH_NOT_SUPPORTED`. CP-DR is one registry entry
  (`modules/registry.py`, `plan_approval=True`, `max_output_tokens=32_000`,
  golden authority digest `76e990f4…` over the pinned build); the vendored
  bundle is untouched. `test_module_wiring.py::test_cp_dr_agent_wiring_is_registry_only`
  proves the module executes under its assembled skill authority.
- **Brief.** `contracts.ResearchBrief` strings are `BoundaryText`;
  `engine/research.py::validate_brief` applies the same contract for
  programmatic callers. `Engine.start_run(research_brief=…)` refuses
  `RESEARCH_BRIEF_REQUIRED`, `RESEARCH_BRIEF_NOT_APPLICABLE`,
  `RESEARCH_BRIEF_INVALID` and `DEPTH_NOT_SUPPORTED` before any row exists;
  the accepted brief is locked in the run's creating transaction
  (`run_research` table) and bound into run authority as
  `plan.research_brief_digest` at gate exit (absent on every other pathway).
- **Plan and gate.** After CP-0, the CP-DR node builds the plan as a pure
  function of the pinned plan, the brief and the upstream artifacts
  (`build_research_plan`: primary / adversarial / synthesis workstreams,
  `source_mode` fixed to `supplied_only`), persists it with
  `sha256:<canonical digest>` (`RunStore.propose_research_plan`) and parks the
  run on `PLAN_APPROVAL_REQUIRED` outside every metered bracket; events
  `run.paused` and `research.plan_ready`. `POST /resume` re-parks.
- **Approval.** `Engine.approve_research_plan` re-checks provider identity and
  pinned-source liveness, then `RunStore.approve_research_plan` does the
  compare-and-swap on the exact proposed hash while the run is parked on this
  gate (`RESEARCH_PLAN_STALE`, `RESEARCH_PLAN_NOT_PENDING`), consuming the
  ticket, transitioning the run, emitting `research.plan_approved` and the
  audit event of the same name in one transaction; the continuation is
  scheduled, never driven inline. On re-entry the node recomputes the plan and
  refuses `RESEARCH_PLAN_MISMATCH` if the approved hash is not the plan that
  would execute. Startup recovery now drives an interrupted thread whose store
  status is already `running` (approved, then crashed before the continuation)
  instead of skipping it — found by the confidence review, pinned by
  `test_recovery_resumes_a_run_approved_before_the_crash`.
- **Execution envelope.** The approved scope rides the module's host identity
  (`research`: brief, brief digest, approved hash, workstreams) into the
  prompt under the untrusted label and into the artifact; the host stamps the
  nine CP-DR envelope fields the pinned common validator requires
  (`methodology/canonical.py`, `research_handoff_fields`), listed under
  host-derived provenance; the store validator
  (`storage/runs.py::_valid_research_projection`) requires them on CP-DR and
  refuses them anywhere else.
- **Wire.** `CanonicalRunResponse.research` (`ResearchStateResponse`, present
  on Deep Research runs only), `GET /api/runs/{id}/research-plan` and
  `POST /api/runs/{id}/research-plan/approve` (`ApproveResearchPlanRequest`);
  `deep_research_available` is `Engine.deep_research_availability()`;
  `run_sec_audit.py` body probe and `docs/QUALITY_LEDGER.csv` F-RUN-21 added.
- **Frontend.** The existing approval surface is reused unchanged except that
  the approve control now honours `writeAccess` like compile and accept. The
  workbench smoke's Deep Research journey runs live against the host-control
  server (brief → proposed plan → approval → succeeded); the fixture-driven
  rendering journey and the a11y `pending-plan` context are unchanged.
- **Tests.** `caos/tests/spec/test_research_spec.py` (18 tests: persistence,
  CAS, resume bypass, continuity, restart, replay, start refusals, HTTP
  authorization and key sets, derived availability, injection-bearing /
  insufficient / ambiguous briefs, deliverable draft → freeze → file →
  reconstruction); `test_runs_spec.py` and `test_corpus_pathways.py` made
  depth-aware; `test_budget_spec.py` caps; `test_http_contracts_spec.py`
  strict-schema list; `qa/probe.py` AC-RUN-5.
- **Docs.** `docs/DECISIONS.md` §14.16, `CLAUDE.md` (execution model, known
  gaps), `SPEC_RECONCILIATION.md` rows 5/6/10, `ENTERPRISE_TESTING_READINESS.md`
  ETR-B11, `docs/QUALITY_LEDGER.csv`.

## Assumptions stated

- The approval sits between CP-0 and CP-DR, not before CP-PARSE: the
  methodology approves the plan "before substantive research" with source
  readiness as advisory input, and the frontend fixture already shows CP-0
  succeeded / CP-DR pending. The plan therefore binds the exact CP-0 artifact,
  so two replays of the same brief share plan digest, workstreams, scope and
  source set but carry their own upstream artifact refs (each replay stays
  auditable to its own run, as the existing replay contract requires).
- The plan is host-deterministic (three fixed workstreams projected from the
  brief), not model-authored. The task text calls it "the proposed
  deterministic plan"; a model-authored plan would make the approved content a
  provider output, which invariant 3 forbids from carrying authority.
- `coverage_score` is the validated field-coverage ratio and a stored CP-DR
  artifact is always `Complete` / `coverage_satisfied`, because a partial or
  failed source gate is already a typed refusal in the validate step
  (`SOURCE_EVIDENCE_RESTRICTED` / `SOURCE_EVIDENCE_INSUFFICIENT`). The nine
  envelope fields are host-derived; no provider prose feeds them.
- "Revalidates the model or declares no numeric effect": Deep Research is
  model-optional, acceptance queues no build (`on_accepted` is unchanged) and
  `queue_build` answers `MODEL_NOT_READY`; the test pins that declaration.
- Approval authority is case write access (analyst, approver, admin), matching
  the compile control; the filing gate's approver-only rule is not copied.

## Commands and results

All run in `.claude/worktrees/er-task-07-deep-research` with
`caos/server/.venv/bin/python` (3.14.6) unless noted.

- `uv run --python 3.14 --project caos/server --extra dev python -m pytest --version` → `pytest 9.1.1`, `Python 3.14.6`; `uv.lock` removed.
- `npm ci` (caos/frontend) → exit 0.
- Red first: `pytest caos/tests/spec/test_research_spec.py -x` on the untouched
  engine → `TypeError: Engine.start_run() got an unexpected keyword argument
  'research_brief'`; the recovery test failed with `'running' == 'succeeded'`
  before the `recover()` change.
- `pytest caos/tests/spec/test_research_spec.py caos/tests/test_module_wiring.py`
  → `19 passed` + `4 passed` (research spec run alone: `19 passed in 2.87s`).
- `pytest` over the eight most affected spec files (`test_runs_spec`,
  `test_http_contracts_spec`, `test_budget_spec`, `test_modules_spec`,
  `test_injection_spec`, `test_observability_spec`, `test_deliverables_spec`,
  `test_ordinary_distressed_e2e`) → `347 passed in 209.65s`. (A first
  invocation that listed `caos/tests/test_bundle.py` before the spec files
  produced 25 failures / 29 errors — the known argument-order artifact that
  swaps the conftest and disables agent execution — not a regression.)
- Ruff (`--config ruff.toml caos/server caos/tests --exclude …/vendor`) → `All checks passed!`.
- `python run_sec_audit.py` → `{'audited_routes': 52, 'case_boundary_routes': 42, 'failures': 0}`.
- `python docs/quality_ledger_coverage.py` → `routes checked: 47   product files: 242   features: 121` — complete (after adding F-RUN-21).
- `CORPUS_FULL=1 pytest caos/tests/test_corpus_pathways.py` → `34 passed in 168.82s`
  (every startable route; DEEP_RESEARCH full through the approval gate with the
  fixture brief — orchestration proof only).
- Frontend: `npm run lint` exit 0, `npx tsc --noEmit` exit 0,
  `npm run test:unit` exit 0, `npm run build` exit 0.
- Host-control dev server (`CAOS_PROVIDER=host_control AGENT_EXECUTION_ENABLED=true
  ANTHROPIC_API_KEY="" PORT=8765 python caos/server/dev.py`, scratch data dir):
  `/api/health` → `{"status":"ok","store":true,"bundle":true,"checkpointer":true}`.
- `CAOS_URL=http://127.0.0.1:8765 npm run a11y` → exit 0
  (`routes 9, viewports 6, combinations 70`, pending-plan fixture exercised).
- `CAOS_URL=http://127.0.0.1:8765 npm run test:workbench` → exit 0
  (`domContentLoaded 49.7 ms, firstContentfulPaint 120 ms`), run while the
  backend suite was still executing; the server log shows one
  `POST …/research-plan/approve` → 200 and exactly one `research.plan_ready`
  and one `research.plan_approved` event for the live journey.
- `python -m pytest caos/tests -q -p no:cacheprovider` (full backend suite, run
  concurrently with the browser gates) → `968 passed, 2 skipped in 808.80s`;
  the 2 skips are the optional PostgreSQL tests (`CAOS_TEST_POSTGRES_URL` unset).

## Confidence review

Least confident about (ranked):

1. A restart after approval but before the continuation — `recover()` skipped
   every interrupted thread, so an approved run would have stayed `running`
   forever. Investigated by writing the test first
   (`test_recovery_resumes_a_run_approved_before_the_crash`, red with
   `'running' == 'succeeded'`); verdict CONFIRMED bug; patched in `recover()`
   (an interrupted thread whose store status is already `running` is driven
   from its checkpoint, logged as `resumed_after_gate`).
2. `interrupt()` returning instead of raising when `resume()` passes
   `Command(resume=True)` — the node loops on store truth, so the second
   `interrupt()` re-parks; verified by `test_resume_cannot_bypass_the_approval_gate`
   (no provider call, no artifact, one `research.plan_ready`). Fine.
3. Re-entry after approval with `wait()` (`None` input on an interrupted
   thread) — this is the same call the serving continuation makes; every
   passing gate test resumes that way. Fine.
4. The CP-DR frontmatter — the vendored common validator requires nine
   research fields the host did not stamp (found by reproducing the refusal
   with the validator's own findings list); host-derived now, listed in
   provenance, refused on any other module by the store validator. Fine.
5. `host_identity` gaining a `research` key — the store pins the exact key set;
   relaxed to allow exactly that key and cross-checks it against the stamped
   frontmatter and the re-derived expected identity. Fine (`test_plan_approval_…`
   asserts the stored artifact carries it).
6. Provider doubles patching the message — `ProviderMessage` is frozen, so the
   first version of the adversarial doubles raised and surfaced as
   `CANONICAL_GENERATION_FAILED`; rebuilt with `dataclasses.replace`. Fine.
7. Cost of `deep_research_availability()` on every case row — `compiled_route`
   and the bundle are `lru_cache`d, the identity check is a dict compare. Fine.
8. `test_finalization_metering`'s source-reading bracket check — the approval
   call sits before the `started = self._clock()` bracket, and edits after the
   suite started were below every inspected function. Verified by the
   affected-suite run; the full suite is the final word.
9. Replay equivalence — the plan hash differs across replays because it binds
   each run's own CP-0 artifact (artifact digests carry the run id, as the
   existing replay contract requires); the test compares everything except
   `upstream_artifacts`. By design, recorded under Assumptions.

Fixed: 1. Verified fine: 2–8. By design: 9. Still open: none in code; the
two BLOCKED EXTERNAL items below.

## Open items

- **BLOCKED EXTERNAL — C22 research pack.** A question-specific pack with an
  approved brief, answer keys, forbidden conclusions and time-bounded evidence
  does not exist in the repository. Needed: the pack itself (retained bytes
  pinned by SHA-256 in `caos/tests/corpus/sources.txt` style), its brief, and an
  independently authored expected conclusion. Until then Deep Research is
  qualified by host control only.
- **BLOCKED EXTERNAL — live-model qualification of CP-DR.** Needs the
  protected Anthropic credential and a re-issued qualification record:
  registering CP-DR changes `parameter_context_metadata`, so the identity
  digest any existing record was issued against no longer matches.
- The Deep Research plan is host-deterministic (three fixed workstreams). If
  the methodology owner wants model-authored workstreams inside the approved
  envelope, that is a design decision for `docs/DECISIONS.md`, not a bug.
- `caos/frontend/src/lib/api.ts` types `RunRecord.research` without the new
  `brief`, `brief_digest`, `approved_by`, `approved_at` keys; the UI does not
  read them, so the type was left alone.
- The verify loop reported the workbench smoke failing twice in a row on
  `main` at the issue #38 focus wait while a full pytest run saturated the
  machine; here it passed under the same conditions. Still tracked as #38.
