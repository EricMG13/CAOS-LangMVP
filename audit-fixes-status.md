# Applied audit fixes — 2026-09-08

Branch: `codex/audit-fixes`; base: `f72e7bb8083548c77a85ac335adcc1b2ea6eca17`. Changes are uncommitted; no push, deployment or live service modification was requested.

**44 findings have code, test or documentation corrections.** D24 and D41 retain documented behavior; 13 findings were not established and were not applied. Partial findings are corrected only to the extent supported by the validation evidence. The original supplied audit is unchanged.

[Original validation and severity corrections](/Users/ericguei/.codex/worktrees/e0aa/CAOS-LangMVP/audit-findings-validation.md) · [Confidence review](/Users/ericguei/.codex/worktrees/e0aa/CAOS-LangMVP/audit-fixes-confidence-review.md) · [Post-edit rewrite tournament](/Users/ericguei/.codex/worktrees/e0aa/CAOS-LangMVP/audit-fixes-rewrite-review.md)

## Verification

- Broad backend run: **2,010 passed, 36 skipped, 11 failed** in 572.71s. Seven failures were localhost sandbox restrictions; their rerun outside the sandbox passed (10 tests including adjacent scanner checks). Three v5 raw-Markdown compatibility failures were corrected and rerun successfully (4 focused publication tests plus the ordinary distressed export E2E).
- **One pre-existing failure remains**: `test_accepted_research_flows_through_draft_freeze_file_and_reconstruction` raises `REPORT_INPUT_UNAVAILABLE` at opinion signing. An isolated export of the untouched base commit reproduces the same failure at the same line. The fix set does not weaken this report-input guard.
- Final focused startup, API and budget checks: **115 passed, 2 PostgreSQL skips, 1 socket test deselected**; the socket test subsequently passed. Health/config edge follow-up: **30 passed**. API/misc/queue follow-up: **49 passed**.
- Publication/package/golden suite: **58 passed** before the minimal inline escaping refinement; affected v5 publication tests and real distressed exports passed after it. The app and offline verifier share identical renderer code.
- Authorization audit: **64 routes, 552 actor-matrix cells, 20 cross-case probes, zero failures**.
- Frontend: **195 Node tests passed**; final lint, TypeScript and static build passed. Full Chromium, Firefox and WebKit journeys passed. Rebuilt axe sweep: **122 combinations, zero violations, zero unresolved ARIA values**, with **23 inconclusive records retained** (12 empty-table checks, 11 contrast checks). Details follow below.
- Quality ledger: **59 routes / 430 product files / 138 features covered**. Ruff and whitespace checks pass. Resource verification: **310 files, zero mismatches**; this is a workspace resource check, not a rebuilt-image deployment claim.
- External limits: opt-in PostgreSQL tests need a test URL; live IdP session behavior, provider qualification, deployment inventory and full production load were not inferred from local fixtures.

## Per-finding disposition

| Finding | Disposition | Result |
|---|---|---|
| D1 | Corrected | Prefixed ZIPs receive the archive ceilings before workbook parsing. |
| D2 | Corrected | All XML/rels parts reject DOCTYPE before openpyxl; incorrect backend claim corrected. |
| D3 | Corrected | PDF extraction has child-process CPU/wall limits, Linux memory cap and incremental text/page ceilings. |
| D4 | Corrected | Deep JSON recursion receives a typed 422; rendered JSON accumulation is bounded. |
| D5 | Corrected | The exact source manifest is checked before run admission and rechecked at use. |
| D6 | Corrected | Transport and intake aggregate byte/text limits refuse before admission. |
| D7 | Corrected | Case pages use batched queries; UI/operational callers page; full source listings refuse over budget. |
| D8 | Corrected | Concurrent health requests share one shielded background task; probes/cache are bounded. |
| D9 | Corrected | Validation-error locations are safe bounded text or a fixed placeholder. |
| D10 | Corrected | Completed run locks are weakly retained; active owners/waiters keep synchronization. |
| D11 | Corrected | Renderer v5 escapes inline metadata and folds line breaks; historical v3/v4 bytes retain old rules. |
| D12 | Corrected | Unicode Cc controls rejected except intentional CR/LF/TAB narrative formatting. |
| D13 | Corrected | Derived issuer/case fields pass the same CreateCaseRequest contract as manual input. |
| D14 | Corrected | Filename/media metadata is normalized and bounded before extracting or storing uploads. |
| D15 | Corrected | Deliverable errors expose bounded code-shaped values, not raw validation messages. |
| D16 | Corrected | Self-role and last-admin mutations return exact typed 409 responses. |
| D17 | Corrected | Authorization matrix rejects unexpected 5xx and proves invalid authorized transitions preserve standing; upgrade errors are typed. |
| D18 | Not established | Provisioning authority and independent filing are separate documented policies; no ADMIN privilege change. |
| D19 | Corrected | A missing production edge secret refuses authentication at the boundary. |
| D20 | Not established | Authenticated GET download access logging is intentional; no blanket Origin restriction. |
| D21 | Corrected | SSE checks current case membership before every event and poll. |
| D22 | Not established | A database owner can rewrite both rows and local anchors; same-database chaining cannot solve that threat. |
| D23 | Corrected | Reference proxy sessions expire after one hour without refresh; tails reconnect within five minutes. |
| D24 | Retained policy | Only canonical GET /api/health is public; slash/noncanonical requests stay protected intentionally. |
| D25 | Corrected | Unused financial helper removed; tests exercise actual calculation/serialization guards. |
| D26 | Corrected | Unused BudgetLedger removed; ceiling tests exercise durable RunStore reservations and charges. |
| D27 | Not established | Missing scanner inventory coverage did not establish an active authority vulnerability. |
| D28 | Corrected | Calculation ceiling covers assumption-registry; coverage test discovers actual registered calculator callers. |
| D29 | Not established | Non-finite/overflow numeric input already fails production normalization before calculation. |
| D30 | Corrected | Worker poll interval validated as finite and between 0.1 and 60 seconds before assembly. |
| D31 | Corrected | Database pool timeout maps to the existing safe STORE_UNAVAILABLE 503. |
| D32 | Corrected | Worker documentation matches per-item finalization and intentional supervisor restart on store failure. |
| D33 | Corrected | Auto-queue failures log safe run id/exception class after durable acceptance; retry proof retained. |
| D34 | Not established | A false finalization return can be a legitimate duplicate/no-op; no proven lost-terminal defect. |
| D35 | Corrected | 404/405 UI copy is neutral about resource access and deployment availability. |
| D36 | Corrected | Normal Workspace/ReportStudio run refreshes omit unused embedded event history. |
| D37 | Corrected | Malformed/empty successful JSON gets a typed UI error; body-read cancellation preserves AbortError identity. |
| D38 | Corrected | Health documentation includes the scanner field and bounded probe behavior. |
| D39 | Not established | Static Next bootstrap requires its existing CSP allowance; no exploitable path established or safe hash migration requested. |
| D40 | Corrected | Compose passes password separately; SQLAlchemy constructs/parses the encoded DSN; blank dev fallback preserved. |
| D41 | Retained policy | Unsaved recovery drafts deliberately survive logout within subject/case/pathway/tab scope; no new deletion policy invented. |
| D42 | Not established | Header-visible case identifiers are minted and membership-checked; no header injection path established. |
| D43 | Corrected | Quality coverage maps the six missing scripts; coverage gate passes. |
| D44 | Corrected | Four unique fixture browser scripts have npm commands and a Chromium CI gate. |
| D45 | Corrected | Browser assertions require nonempty evidence, independent frozen objects, edited input effects and positive anchors. |
| D46 | Corrected | Page/dialog/error observers start early and final assertions include auxiliary pages and final interactions. |
| D47 | Corrected | Axe scans anchor headings, retain incomplete results and fail unresolved ARIA values; the empty source reader has a valid accessible name. |
| D48 | Corrected | Empty browser selection fails; child processes and manual barriers have deadlines and timer cleanup. |
| D49 | Corrected | Inventory and perimeter documentation match the served members POST route and manual/deployment scope. |
| D50 | Corrected | Every workbook XML part is screened through the existing streaming parser before extraction/import. |
| D51 | Not established | Operator-controlled catalog credential selection is an intended capability, not arbitrary untrusted input. |
| D52 | Not established | The suggested semaphore change would release an unacquired slot; existing acquisition semantics retained. |
| D53 | Not established | Compilation already serializes under the bundle lock; global executable-module caching was not justified. |
| D54 | Corrected | Manifest byte ceiling includes the complete canonical array, metadata, separators and brackets. |
| D55 | Not established | Pinned scanner default accommodates current source cap; asserted 25 MB stream limit was disproved. |
| D56 | Corrected | Checkpoint/role ownership precedes schema work; config validation precedes sidecar creation; cleanup retains ownership correctly. |
| D57 | Not established | Execution-disabled provider construction makes no provider HTTP request; switch behavior is correct. |
| D58 | Corrected | All 11 checkout steps disable persisted credentials; YAML regression covers the workflows. |
| D59 | Corrected | Stale bundle-count commentary corrected; resource gate verifies all 310 files. |

## Scope notes

Integration review additionally caught and corrected health worker occupancy, completion-time cache freshness, response-body abort classification, blank-URL compatibility, validation-before-lock ordering and first-party pagination consumers. These were regressions in the initial implementation or necessary caller adaptations, not new product scope.

No dependencies, vendored methodology changes, new privilege policy or destructive draft cleanup were introduced. The current behavior amendments are recorded in [DECISIONS §14.28](/Users/ericguei/.codex/worktrees/e0aa/CAOS-LangMVP/docs/DECISIONS.md).

## Exact commands and logs

All backend pytest commands used `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=caos/server` and `/Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/.venv314/bin/python`, with `-p no:cacheprovider`.

```sh
python -m pytest caos/tests -q -p no:cacheprovider --tb=short -n 4 --dist loadfile
python -m pytest -q -p no:cacheprovider --tb=short caos/tests/test_single_instance.py caos/tests/spec/test_budget_spec.py caos/tests/spec/test_audit_boundaries_spec.py -k "not second_dev_server"
python run_sec_audit.py
python -m ruff check --config ruff.toml caos/server caos/tests qa/probe.py qa/capacity.py run_sec_audit.py
python docs/quality_ledger_coverage.py
python caos/deploy/verify_image_resources.py
npm run test:unit
npm run lint
npx tsc --noEmit
npm run build
CAOS_BROWSERS=chromium,firefox,webkit npm run test:browsers
CAOS_BROWSERS=firefox npm run test:browsers
npm run a11y
```

Local run logs: [broad backend](/tmp/audit-backend-full.log), [untouched-base research reproduction](/tmp/audit-research-baseline.log), [final focused checks](/tmp/audit-final-focused.log), [Markdown recheck](/tmp/audit-markdown-recheck.log), [distressed export recheck](/tmp/audit-distressed-recheck.log), [authorization audit](/tmp/audit-sec-final.log).

Final integration review: [review](/tmp/audit-integration-review.md), [pagination confidence review](/tmp/audit-integration-pagination-confidence.md), [pagination rewrite review](/tmp/audit-integration-pagination-rewrite.md), [frontend implementation review](/tmp/audit-fixes-frontend-report.md), [startup implementation review](/tmp/audit-startup-fixes-report.md).

Final shared-renderer/ledger/workflow/capacity check: **39 passed**. The full
browser run exposed unrounded input-derived fixture output (corrected) and WebKit
screenshot tooling injecting a CSP-blocked `body {}` stylesheet. An isolated
probe recorded no errors through navigation/axe and the exact warning during
screenshot. The shared observer preserves actual and unattributed CSP failures; an isolated
positive/negative probe verified that behavior. Firefox's final HTTP-refusal
assertion initially depended on a Chromium console message; the correction
compares exact expected and observed HTTP URL/status counts instead.

## Browser integration evidence

| Engine | Version | Latest full journey | Duration | Console/page errors |
|---|---|---|---|---|
| Chromium | 151.0.7922.34 | Passed | 161.4s | 0 |
| Firefox | 153.0 | Passed after HTTP-observation correction | 178.7s | 0 |
| WebKit | 26.5 | Passed | 173.0s | 0 |

The three-engine command initially finished with Chromium/WebKit passing and
Firefox failing at the new final assertion; the full Firefox rerun passed after
the test-only correction. No product code changed between those runs. Each
journey includes one loaded-chart axe check, three signed-stack cases, governed
model/report workflows, responsive/reduced-motion views and reader access checks.

These runs used the combined static export and FastAPI app on a disposable local
production-identity fixture at port 19184, with scanner and report fixtures. They
do not qualify a live scanner, provider, IdP or deployment.

Logs: [three-engine run](/tmp/audit-workbench-final.log),
[Firefox rerun](/tmp/audit-workbench-firefox-final.log),
[195 final Node tests](/tmp/audit-frontend-unit-final.log).
The final JSON evidence is in each ignored
`caos/frontend/test-results/<engine>/workbench-report.json`.

Final accessibility triage found a broken source-reader heading reference in six
repeated viewport scans. The section now receives its selected filename or Source
document as its accessible name, including the empty/loading/error states. A new
central axe assertion fails unresolved ARIA attribute values; the stored failing
scan reproduced that refusal before the markup fix. The rebuilt frontend passed
all 195 Node tests, lint, TypeScript and static export. This final ARIA-only
product correction is covered by the rebuilt axe sweep; it does not change the
model/report workflows previously exercised in all three engines.

### Final rebuilt accessibility sweep

**Passed:** Chromium 151.0.7922.34; 17 routes including 8 forwarders across 6
viewports, plus 20 controlled fixture/state checks: **122 combinations, zero
violations and zero unresolved ARIA values**. The source-reader defect is absent.

The fresh fixture database has no ordinary case rows, so the final report retains
12 `th-has-data-cells` records for empty tables. It also retains 11 `color-contrast`
records where elements are partially obscured at the 200% viewport. These 23
records are repeated scan results, not 23 established product defects. They are
not treated as accessibility passes; manual table/contrast review remains open.
No style or keyboard behavior was changed to suppress them.

[Complete axe results, including every inconclusive node](/tmp/audit-axe-final.log).
The disposable server was stopped after verification. Final whitespace and
quality-ledger checks passed; the changes remain uncommitted.
