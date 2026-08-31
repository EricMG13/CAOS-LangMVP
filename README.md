# CAOS — Credit Agent OS (LangGraph MVP)

CAOS turns governed source documents into committee-ready credit conclusions for
institutional leveraged-finance analysts. Every number is one click from its
evidence: runs execute a static module DAG against a pinned, immutable source
set; results become content-addressed artifacts, accepted snapshots, analyst
models, and filed deliverables — each transition audited and digest-bound.

The MVP release target is **enterprise-testing readiness**, not production
readiness. The candidate must prove the controlled document-to-analysis-to-
publication journey and its full machine audit trail inside a declared
enterprise test environment. It does not claim high availability, horizontal
scaling, production service levels, or unrestricted external deployment. See
`ENTERPRISE_TESTING_READINESS.md` for the binding gate.

The run engine executes the vendored `deploy_v` methodology bundle on LangGraph
with durable SQLite/Postgres checkpoints. Four pathways are in the MVP cut
(Full Credit, Earnings Update, Covenant & Refinancing, Relative Value) at two
depths (screen, full). Screen-depth routes are fully deterministic and run
without any model API key.

## Layout

| Path | What lives there |
|---|---|
| `caos/server/caos/` | FastAPI edge (`api/`), run engine on LangGraph (`engine/`), domain + run stores (`storage/`), module registry (`modules/`), vendored methodology bundle (`methodology/`), Model Builder (`models/`), Deliverables (`deliverables/`), loan-universe import (`artifacts/`), strict wire models (`responses.py`) |
| `caos/frontend/` | Next.js workspace (static export) — eight destinations around one `Workspace.tsx` authority machine |
| `caos/tests/` | Phase-2 unit tests + the contractual spec suite (`spec/`) |
| `caos/deploy/` | Dockerfile, compose, Caddy/oauth2-proxy edge, backup/restore drills |
| `docs/DECISIONS.md` | The binding migration decision record (§§1–13) |
| `ENTERPRISE_TESTING_READINESS.md` | Enterprise test scope, exhaustive validation matrix, simulations, review gates, and exit criteria |
| `ENTERPRISE_READINESS_PLAN.md` | Ordered implementation plan for closing the enterprise-test blockers and proving gates G0–G9 |
| `SPEC_RECONCILIATION.md` | Invariant-to-test table and CONTRACTUAL-row reconciliation |
| `CONTEXT.md` | Ubiquitous language for models and deliverables |
| `Modular OS/` | Methodology reference material (read-only) |

## Run it locally

Server (Python ≥3.12, deps per `caos/server/pyproject.toml`):

```bash
cd caos/server && python dev.py
```

`dev.py` uses SQLite under `./.dev-data`, runs startup recovery, and — when
`caos/frontend/out` exists from a build — serves the full app at
`http://localhost:8000`. Agent (LLM) execution stays off unless
`AGENT_EXECUTION_ENABLED=true` and `ANTHROPIC_API_KEY` are set; deterministic
screen routes work end to end without either.

Production runs the same assembly through `caos/server/run.py` (the Docker
`app` target) with `caos/server/worker.py` executing queued model builds and
LibreOffice XLSX exports; `caos/deploy/` has the compose stack and
`caos/.env.example` the environment to fill in.

Frontend, hot-reloading against that server:

```bash
cd caos/frontend && npm ci && npm run dev
```

Then: create a case → upload a source → Run Console → Compile and run. Progress
streams from the persisted graph event log (`run_events`) over SSE; accept the
succeeded run to mint the case's analytical snapshot.

## Checks

```bash
python -m pytest caos/tests -q            # full suite, green (384)
ruff check --config ruff.toml caos/server caos/tests --exclude caos/server/caos/methodology/vendor
cd caos/frontend
npm run lint && npx tsc --noEmit && npm run test:unit && npm run build
npm run a11y                              # WCAG sweep against the combined app on :8000
npm run test:workbench                    # full browser journey against the combined app
```

`CLAUDE.md` is the engineering contract — read it before changing the engine,
the wire surface, or the frontend authority machine.
