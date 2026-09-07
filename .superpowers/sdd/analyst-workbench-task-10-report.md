# Analyst Workbench Task 10 qualification report

**Owner status:** implementation and owner qualification complete; fresh independent Task 10 review and final whole-branch Astra review remain intentionally separate. This report does not claim a merge, deployment, live-provider qualification, or global completion.

**Execution boundary:** branch `codex/analyst-workbench-capabilities`, Task 10 baseline/HEAD at qualification `90403c7ce94e6384fd1f4595eff893935e5530f9`, isolated worktree `/Users/ericguei/Claude/Projects/CAOS-LangMVP/.claude/worktrees/analyst-workbench-codex`. The definitive combined app ran at `http://127.0.0.1:19276` with `--scanner-fixture --report-fixtures`, data `/private/tmp/caos-task10-definitive.oTpXik/harness-data-escalated`, a disposable edge secret and the harness-owned worker. No second worker, port 8000, legacy case, live/paid provider, credential copy, vendored methodology, push, PR, merge or deployment was used.

## Acceptance matrix

| Workstream | Status | Final evidence |
|---|---|---|
| A. Complete Model experience | PASS (fixture orchestration) | Actual accepted Full Credit model build/edit/Base/Downside/sign-off in all three engines; settled MODEL/Cash Flow worksheet, period/section navigation and sticky/local scrolling captures at 1440/1024/720; historical/calculated locks, lineage, minimum-cash edge/failure cases and serialized calculations retained by the complete backend/fault suites. |
| B. Module-driven Report | PASS (fixture orchestration and frozen bytes) | Actual populated v2 report in all engines; optional commentary, opinion Sign-Off, asynchronous freeze and independent filing; receipt-matched MD/PDF/XLSX and audit ZIPs; actual Full Credit→Earnings Update overlay journey; all 46 PDF pages and all 30 native XLSX sheets of the receipt-matched representative export independently reviewed. |
| C. Live Run insight | PASS | Actual live Full Credit run retained separately; 11 supported pathway/depth plans compare exact served/displayed node IDs, modules and dependency-pair multisets; Deep Research/screen is correctly API 422 and UI-disabled; named/open/disposed SSE ownership, malformed graph and ordinary non-research pause passed. |
| D. Visual Analysis | PASS (fixture presentation) | Actual accepted canonical chart/table and sources in all engines; full-app positive, all-negative and mixed+zero signed stacks in all engines; exact table rows preserved; missing/malformed/failure/recovery and rapid-switch lifecycle assertions retained. |

The host-control answer keys prove deterministic orchestration, authority continuity, rendering and publication mechanics only. They do not qualify the analytical quality of a live model or a real issuer recommendation.

## Production findings and fixes

1. **Paper chart source contrast.** Loaded Report charts inherited workspace muted/accent colors on cream paper (2.315:1 and 1.949:1). `globals.css` now scopes the existing paper meta/link tokens to paper chart source labels and normal/hover links. Final computed values are `rgb(93, 93, 104)` and `rgb(47, 84, 201)`; their contrast against `#f7f4ec` is 5.913:1 and 5.911:1. Loaded-paper axe passes in all three engines.
2. **1024px publication-controls squeeze.** The three-column open Report persisted until 900px and left a 154px paper. The existing two-column arrangement now begins at 1100px. Final measured paper width at 1024 is 778px with controls open and approximately 499.34px closed in every engine. The 900px and 700px behavior is preserved.

No publication authority, analytical calculation, route graph, model state or persisted schema was changed. All other changes are qualification scripts/tests and package-script entries.

## Commands and results

All commands used the workdirs named below. The exact backend record is retained at `evidence/task10/backend-required-gate.txt`.

### Backend — repository root

Fixture resolution probe:

```sh
caos/server/.venv314/bin/python -m pytest caos/tests/test_audit_regressions.py caos/tests/test_verify_package_bounds.py caos/tests/spec/test_source_complete_modelling_spec.py --fixtures-per-test -q
```

Exit 0. The root paths resolved first and `test_source_complete_modelling_spec.py` used `caos/tests/spec/conftest.py::settings` with execution enabled.

Complete required gate:

```sh
caos/server/.venv314/bin/python -m pytest caos/tests/test_audit_regressions.py caos/tests/test_verify_package_bounds.py caos/tests/spec/test_model_builder_spec.py caos/tests/spec/test_source_complete_modelling_spec.py caos/tests/spec/test_module_presentation_spec.py caos/tests/spec/test_deliverables_spec.py caos/tests/spec/test_publication_spec.py caos/tests/spec/test_publication_charts_spec.py caos/tests/spec/test_publication_goldens_spec.py caos/tests/spec/test_http_contracts_spec.py caos/tests/spec/test_audit_package_spec.py caos/tests/spec/test_distressed_model_overlay.py caos/tests/spec/test_ordinary_distressed_e2e.py -q
```

Exit 0: **1001 passed, 1 warning in 1611.44s (26:51)**. The warning is the existing Starlette TestClient deprecation. Backend/tests/fixtures remained unchanged throughout Task 10 (`HEAD:caos/server` tree `b5fa78e0ec6fdc86370fbe418291b20a4a133dea`; `HEAD:caos/tests` tree `8a361cc3d7bd450c85b2965844a8040985995d63`). The original run omitted `--durations=25`; no per-test causal timing claim is made and the byte-identical backend was not repeated solely to add metadata.

### Frontend preparation — `caos/frontend`

Before starting the definitive harness:

```sh
npm run lint
npx tsc --noEmit
npm run test:unit
npm run build
```

All exit 0. Lint 5.997s; TypeScript 1.320s; Node **183/183** in 713.09ms; production build 3.670s with 20 static pages. After final test-only repairs, `npm run lint && npx tsc --noEmit && npm run test:unit && git diff --check` again exited 0 in 9.1s; **183/183** in 782.288ms. The only warnings were the known Node `MODULE_TYPELESS_PACKAGE_JSON` notices. The final built CSS contains both the paper-source rule and the 1100px breakpoint.

Two command-discovery mistakes were retained rather than hidden: `npm run typecheck` and `npm test -- --run ...` do not exist. They exited non-zero without changing files; the declared `npx tsc --noEmit` and `npm run test:unit` commands then passed.

### Definitive disposable harness — repository root

```sh
CAOS_EDGE_SECRET=<disposable> CAOS_OPERATOR_USER=journey-operator caos/server/.venv314/bin/python qa/serve_browser_integration.py --port 19276 --data-dir /private/tmp/caos-task10-definitive.oTpXik/harness-data-escalated --scanner-fixture --report-fixtures
```

The first sandboxed bind was refused by the environment; the scoped approved loopback run succeeded. An earlier invocation also correctly refused a pre-created `--data-dir`; the final directory was new. The harness alone owned its worker.

### Explicit fault regressions — `caos/frontend`

```sh
CAOS_URL=http://127.0.0.1:19276 CAOS_EDGE_SECRET=<disposable> CAOS_BROWSER=chromium node scripts/fault-regressions.mjs
```

Final exit 0, **57.17s**. Passed:

- F6/F7 unsigned opinion navigation guard, reload recovery and cloned-tab ownership;
- F14 delayed receipt A versus selected receipt B, with the exact A request waiter installed before the switch and observed browser settlement `requestfailed` before the final B assertion;
- F10 Python-calculated worksheet formula display;
- F8/F9 serialized calculations, latest preview and fresh-build sign-off head;
- F11 worksheet switching and keyboard navigation;
- v2 commentary autosave, recovery and revision restoration.

### Accessibility — `caos/frontend`

For each engine:

```sh
CAOS_URL=http://127.0.0.1:19276 CAOS_EDGE_SECRET=<disposable> CAOS_BROWSER=<chromium|firefox|webkit> npm run a11y
```

All final runs exit 0 with **122 axe scans per engine / 366 total**, plus Model and Report keyboard checks; zero violations. Chromium 151.0.7922.34 took 115.50s, Firefox 153.0 took 138.15s, WebKit 26.5 took 135.04s. Scope: 17 routes × 6 widths, pending research plan, Admin, 3 Model tabs × 3 widths, 3 Report widths, and review/filed/loading/error/refusal states. The final current-v2 journey separately scanned a loaded canonical Analysis chart/table and loaded paper Report chart/table in every engine.

### Full workbench smoke and performance — `caos/frontend`

```sh
CAOS_URL=http://127.0.0.1:19276 CAOS_EDGE_SECRET=<disposable> CAOS_RESULTS_DIR=/private/tmp/caos-task10-definitive.oTpXik/evidence/workbench-final npm run test:browsers
```

Chromium and Firefox passed in the all-engine invocation; the later WebKit keyboard-focus repair was rerun alone in a distinct result directory with the same app/data and passed. No timing limit was relaxed.

| Engine | Final status / duration | DCL | FCP | Budget | Request count | Loaded chart axe | Signed-stack cases |
|---|---:|---:|---:|---|---:|---:|---:|
| Chromium 151.0.7922.34 | PASS / 162.394s | 65.8ms | 168ms | enforced, 250/400ms | case list 1 | 1 | 3 |
| Firefox 153.0 | PASS / 176.288s | 178ms | 231ms | recorded only (not calibrated) | case list 1 | 1 | 3 |
| WebKit 26.5 | PASS / 179.895s | 23ms | 97ms | recorded only (not calibrated) | case list 1 | 1 | 3 |

Every final report records no console errors. Existing same-client request budgets, reduced-motion, keyboard/focus, refusal/failure/recovery, stale authority, missing data, partial analysis and export failure assertions remain intact.

### Run graph gates — `caos/frontend`

```sh
CAOS_URL=http://127.0.0.1:19276 CAOS_EDGE_SECRET=<disposable> CAOS_RESULTS_DIR=/private/tmp/caos-task10-definitive.oTpXik/evidence/graph-matrix-final node scripts/task10-graph-matrix.mjs
```

Exit 0, **11.17s**. The JSON contains 12 matrix entries but only **11 supported rendered DAGs**. For each supported pair, exact served node IDs/modules and the complete dependency-pair multiset equal the UI result. Each SVG path's native start/end (`getPointAtLength` + `getScreenCTM`) must be within 2px of the rendered source right-center/target left-center. The twelfth entry is not a DAG: Deep Research/screen is a retained API 422 `requires full depth` response plus UI-forced full/disabled Screen proof.

```sh
CAOS_URL=http://127.0.0.1:19276 CAOS_RESULTS_DIR=/private/tmp/caos-task10-definitive.oTpXik/evidence/run-graph-lifecycle-final node scripts/run-graph-smoke.mjs
```

Exit 0, **4.50s**. Initial run fetches 1; `onopen` owned exactly the second; named `node.succeeded` owned exactly the third; a deliberately invoked callback on the disposed old stream owned **0** refetches. Ordinary `SOURCE_SET_EMPTY` pause was shown without a Research-pause label. Existing same-document stream, branch/merge, failure and malformed-dependency fallback proofs passed.

### Actual accepted-v2 Full Credit journey — `caos/frontend`

For each engine:

```sh
CAOS_URL=http://127.0.0.1:19276 CAOS_EDGE_SECRET=<disposable> CAOS_BROWSER=<engine> CAOS_RESULTS_DIR=/private/tmp/caos-task10-definitive.oTpXik/evidence/qualification-<engine>-final npm run test:qualification
```

Chromium PASS 93.03s, Firefox PASS 97.07s, WebKit PASS 92.02s. Each journey used actual `/api/intake`, a successful Full Credit/full run, UI acceptance, actual canonical CP-1 chart/table/source, actual model build/edit/sign-off, actual v2 report/commentary/opinion, worker freeze, a distinct provisioned approver, filing and downloads. Each retains 23 screenshots (all four capability routes at 1440/1024/720 plus content-focused chart/table, Cash Flow and Report captures), no page errors and two loaded-chart axe checks.

| Engine | Case / accepted snapshot | Build / revision | Deliverable / receipt | MD / PDF / XLSX SHA-256 | Audit ZIP SHA-256 |
|---|---|---|---|---|---|
| Chromium | `case-1a63…` / `snap-b6b42…` | `mdl-f773…` / `rev-a297…` | `dlv-7e5b…` / `rcpt-029d…` | `bcd9d41c…` / `42878a4b…` / `c50e8e5f…` | `42a91762…` |
| Firefox | `case-3e9d…` / `snap-2e9d6…` | `mdl-5540…` / `rev-f62c…` | `dlv-2575…` / `rcpt-5e70…` | `207505e9…` / `82ff9b73…` / `9b1ba6d1…` | `69cccc4e…` |
| WebKit | `case-7209…` / `snap-d40e5…` | `mdl-3f3f…` / `rev-ce43…` | `dlv-a0f4…` / `rcpt-84d9…` | `26ce0901…` / `4252c6d2…` / `e274c38d…` | `ffbbe14a…` |

Full identities and hashes live in each `qualification.json`. Root independently recomputed all nine download hashes/lengths against metadata and detached receipts, checked approver independence, and ran the offline verifier on every final audit ZIP: all exit 0, `findings: []`, 19 audit events, 29 objects, one run/build/frozen/receipt and Markdown reconstruction each.

### Actual accepted-v2 incremental publication — `caos/frontend`

```sh
CAOS_URL=http://127.0.0.1:19276 CAOS_EDGE_SECRET=<disposable> CAOS_RESULTS_DIR=/private/tmp/caos-task10-definitive.oTpXik/evidence/incremental-final npm run test:incremental-qualification
```

Exit 0, **81.66s**. Case `case-3d9fe…`: accepted Full Credit `run-00331…` / `snap-9080…` / build `mdl-bd4f…`, followed by accepted Earnings Update `run-14bf…` / `snap-44a2…` / overlay `mdl-0112…`. The frozen v2 payload binds `CURRENT_ACCEPTED_OVERLAY`, exactly one Earnings Update effect and the prior build ancestry, while labelling unchanged prior-model base values separately. Deliverable `dlv-0cfc…` was filed by an independent approver with receipt `rcpt-965f…`.

MD/PDF/XLSX SHA-256: `3e4ba68c…`, `de24b6b7…`, `90d00e11…`; ZIP `2531627d…`. A fresh offline check exited 0 in 0.16s with `findings: []`, 22 audit events, 34 objects, two runs/builds, one frozen/receipt and Markdown reconstruction; all three downloaded hashes equal the receipt.

## Visual and native inspection

- Root personally reviewed all 46 pages of the receipt-matched representative actual-v2 PDF: no footer/source/watermark collision; all chart labels/axes/keys and exact tables were retained; high-precision ratio views correctly stayed exact-table-only.
- Root rendered the receipt-matched XLSX read-only with installed LibreOffice 26.2.5.2 in an isolated profile, then Poppler, and personally reviewed all 30 sheets including 8 native charts. The original/copy SHA-256 stayed `f16d746c…`. Full registers, three maturity keys, Base/Downside cash/FCF, zero score baseline, exact fallbacks and source/revision registers were retained.
- Root reviewed the retained focused views across all three engines, including each engine's 1024 paper chart/table, selected Analysis, MODEL/Cash Flow and closed Report frames, measured open/closed 1024 geometry, and all three full-app signed-stack captures. The exact reviewed inventory and scope are in the root visual record. No remaining visual defect was found.
- This representative 46-page/30-sheet review is byte-identical-backend renderer evidence, not a claim that the three newly generated final PDFs/XLSX files were each rerasterized. Their bytes and offline packages were independently verified.

Authoritative controller records:

- `.superpowers/sdd/analyst-workbench-task-10-visual-review.md`
- `.superpowers/sdd/analyst-workbench-task-10-root-offline-verification.md`
- `.superpowers/sdd/analyst-workbench-task-10-root-accessibility.md`
- `.superpowers/sdd/analyst-workbench-root-confidence.md`

## Failed attempts and root causes

Failed artifacts are separated under `evidence/task10/failed-attempts/`; later passes did not overwrite them.

- Initial graph code called a non-existent response method; corrected to the actual Playwright response API. The first real matrix then discovered the existing Deep Research/screen 422 contract. The plan was corrected to 11 supported displays plus one explicit negative contract. A later count-only success was strengthened to exact native endpoint/dependency-pair comparison before acceptance.
- Early qualification attempts retained wrong DTO assumptions (`build.accepted_snapshot_id` location), collapsed v2 controls and ambiguous v2 labels, then optional Cash Flow/MODEL selectors. Each was narrowed to served DTOs, `aria-expanded`, exact IDs and mandatory worksheet/section assertions. Failed JSON/screens are retained.
- Fault regression first timed out on hidden opinion controls, then an unbounded receipt waiter exposed a collapsed history panel. Its frozen fixture also omitted required `evidence`; the v1 narrative loop did not describe current v2 and an empty evidence-bound optional comment correctly did not autosave. The final fixture opens controls, includes `evidence: []`, waits visible Saved states, makes commentary valid and awaits exact receipt request settlement. No production fault was found.
- Standalone Chromium axe first hit sandbox Mach-port denial. WebKit's first final accessibility run used plain Tab and followed native macOS control navigation to a `<summary>`; focused evidence showed Option-Tab reaches the section buttons. The final test reuses the existing engine-specific `Alt+Tab` convention and preserves the same assertion.
- WebKit workbench reached and captured all signed-stack cases but later failed because a mouse `.click()` does not natively focus buttons. The retry uses explicit focus+Enter for the intended keyboard activation/focus assertion and passed. The failed trace/report/screenshot remain separate.
- The first definitive harness command used an already-created data directory and correctly refused it; a new path was used. The sandboxed loopback bind failed and the scoped approved invocation succeeded.

## Confidence review and tournament decision

The required confidence review enumerated and checked these weakest points:

1. **Was the final app built with both CSS fixes?** Corrected an initial inspection of the wrong static path, then found both rules in `.next/static/chunks/*.css`; all final browser geometry/computed-style checks ran against that harness.
2. **Could equal edge counts hide a wrong graph?** Confirmed the final matrix compares all 11 exact dependency-pair multisets from native SVG endpoints, not counts alone; Deep Research/screen is filtered as the one refusal.
3. **Could a stale receipt callback win after the assertion?** Replaced the fixed delay with the exact retained Request's `requestfailed`/finished Response waiter installed before the selection change; final run observed `requestfailed` and retained receipt B.
4. **Could the Task 9 full-app fixture miss reordered signs/zeros?** Confirmed the exact positive, all-negative and mixed+zero rows match Task 9; all three engines report 3 settled canvases, exact input-order tables and no chart failure. Root reviewed the actual images against the approved outward ordering.
5. **Could identities/hashes be prose-only?** Mechanical `jq` checks passed for all three main journeys and the incremental journey: status, snapshot ancestry, build/revision, open/closed widths, axe flags, zero page errors, download/receipt SHA equality and distinct approvers. Offline CLI checks passed.
6. **Could a Task 10 mutating script hit port 8000?** Every new mutating script requires explicit `CAOS_URL`, loopback hostname, non-8000 port and edge secret. Historical scripts retained their defaults but every invocation explicitly named port 19276.
7. **Was backend evidence stale after a fix?** Confirmed Task 10 changed no backend/test/fixture path and the recorded Git trees equal HEAD. Frontend production changed only CSS; all final browser gates used the post-build harness.
8. **Did responsive repair damage 900/700 rules?** Static regression bounds the two-column rule between the 1100 and 900 media blocks; 1440/1024/720 actual captures and no-overflow checks passed in all engines.

No additional product bug remained after those checks. `git diff --check`, syntax checks, lint, TypeScript and 183 unit tests pass. The SHA-256 manifest covers every retained evidence file.

The no-argument rewrite tournament was not run: the production edit is a trivial declarative CSS token/breakpoint move with no changed function or material symbol; all JavaScript additions are test-only. This matches the plan/skill's explicit test/doc/trivial exemption and avoids inventing a production rewrite target.

## Evidence inventory and limits

Durable evidence root: `.superpowers/sdd/evidence/task10/` (manifest `SHA256SUMS.txt`). Important subdirectories:

- `qualification-final/{chromium,firefox,webkit}/` — 69 screenshots, 3 JSON records, 9 exports and 3 audit ZIPs.
- `incremental-v2-final/` — final report screenshot, JSON, 3 exports and audit ZIP.
- `workbench-final/{chromium,firefox,webkit}/` — successful reports/screens, including all signed stacks.
- `graph-matrix-final/` and `run-graph-lifecycle-final/` — exact graph JSON/screens and lifecycle screens.
- `accessibility-all-engines/` — full logs, WebKit focus probe and failed/successful provenance.
- `native-xlsx/{render,pages}/` — isolated-profile native workbook render output and 30 reviewed sheet images; disposable LibreOffice profile excluded.
- `reviewed-export-example/` — the exact representative PDF (`f356a187…`) and XLSX (`f16d746c…`) reviewed by root, plus all 46 PDF page rasters; the original files were copied without modification and the disposable LibreOffice profile remains excluded.
- `failed-attempts/` — qualification, graph-contract and WebKit focus failures kept separately.
- `incremental-v2-prior-final-build/` — earlier independently verified incremental success retained for provenance; the definitive final run is the separate `incremental-v2-final/` directory.

Remaining limits: no live/provider analytical-quality qualification, real issuer, PDF/UA certification, manual screen-reader certification, calibrated Firefox/WebKit performance threshold, deployment inventory, external penetration test or production deployment was authorized or performed. The root-first pytest fixture-order limitation remains explicit; future mixed root/spec commands must preserve the verified ordering or run suites separately.
