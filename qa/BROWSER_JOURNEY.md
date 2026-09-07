# Enterprise browser journey

`caos/frontend/scripts/production-browser-journey.mjs` drives the shipped static
frontend and real HTTP endpoints. It has no route interception, direct database
writes, or successful-response fixtures. Use a fresh case per run; generated
synthetic packs receive a unique issuer. `CAOS_PACK_DIR` may supply a document pack.

The driver covers intake, execution and acceptance, operator bootstrap and exact
replay, model worker completion and analyst sign-off, signed model XLSX export
completion and exact download, Report authoring and exact citations, opinion
sign-off, asynchronous freeze, independent filing, all three deliverable exports,
detached receipt and offline audit verification. It also checks stale
model/draft/opinion/preview refusals, revocation, signer/Reader denial, filing
replay and withdrawn evidence. Acceptance can queue the model immediately; the
model queue endpoint is exercised idempotently and the page is refreshed before
editing the resulting forecast.

## Configured enterprise stack

Build and deploy the candidate normally with its PostgreSQL store, worker, real
scanner, trusted identity edge and qualified provider binding. The runner needs
the edge credential and four distinct configured identities. The operator must
be in the explicit enterprise-operator policy. Keep credentials outside the repo.

```sh
cd caos/frontend
CAOS_URL=https://candidate.example \
CAOS_EDGE_SECRET="$EDGE_SECRET" \
CAOS_ANALYST_USER="$ANALYST_SUBJECT" \
CAOS_OPERATOR_USER="$OPERATOR_SUBJECT" \
CAOS_APPROVER_USER="$APPROVER_SUBJECT" \
CAOS_READER_USER="$READER_SUBJECT" \
CAOS_BROWSER=chromium \
CAOS_JOURNEY_OUT="$EVIDENCE_DIR/chromium" \
node scripts/production-browser-journey.mjs
```

Repeat for Firefox and WebKit, and each enabled provider binding. The default
evidence label is `live-provider`; a host-control provider is refused under that
label. The caller still owns production candidate identity and qualification
verification: a browser pass alone is not a qualification record or capacity test.

## Isolated local integration fixture

`qa/serve_browser_integration.py` is a test assembly outside the shipped app. It
serves production trusted-edge identity and API authorization with the real
static frontend, model/deliverable workers and isolated SQLite files. Its injected
development provider preserves real tool/evidence/calculation calls and reuses
the existing canonical model answer key through `qa/browser_fixture_provider.py`.
The answer key is synthetic orchestration data, not extracted financial facts.
Production entrypoints still reject host control.

After `npm run build` in `caos/frontend`, start the fixture from the repo root:

```sh
CAOS_EDGE_SECRET="$LOCAL_TEST_EDGE_SECRET" \
caos/server/.venv/bin/python qa/serve_browser_integration.py \
  --port 19182 --data-dir /tmp/caos-browser-fresh-run --scanner-fixture
```

The data directory must not already exist. Supply `--clamav-host` and
`--clamav-port` instead of `--scanner-fixture` to use a running real scanner.
The explicit scanner fixture uses the development scanner only inside this
process; it leaves the production scanner qualification gate unmet.

Run the browser driver with the same secret, `CAOS_URL=http://127.0.0.1:19182`
and `CAOS_JOURNEY_EVIDENCE=integration-host-control`. Default subjects are
`journey-analyst`, `journey-operator`, `journey-approver`, and `journey-reader`.
All source and case writes still use the HTTP boundary.

Each run writes `result.json`, actor traces, exact exports, detached receipt and
offline verification. Failures also retain screenshots. Keep development axe and
workbench suites on separate local fixtures when running concurrently: they share
the development subject's normal request quota and can otherwise provoke 429s.

`scripts/enterprise-ui-smoke.mjs` provides separate focused response-fixture
coverage for provider policy conflicts, lazy evidence paging, delayed search,
exact block focus, safe tables, accepted Report defaults and Reader explanations.
It also runs axe on the operator controls at desktop and 720 px and on a rendered
artifact table. Run it with each `CAOS_BROWSER` value against the built frontend.
It is explicitly UI state/contract coverage and must not substitute for this
real HTTP journey.
