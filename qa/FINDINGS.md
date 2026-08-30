# QA findings — production-configured local pass

Environment, data and acceptance criteria: `qa/INVENTORY.md`. Every defect below
was found by driving the shipped static export against a production-mode server
(PostgreSQL, clamd, OIDC-shaped edge identity, worker) on synthetic
production-scale data — never against a dev server or a mocked route.

Nine defects, all fixed and covered by a regression test. Three of the nine were
only reachable after an earlier one was fixed, which is why they had never been
seen: the chain was broken at the first link.

## The shared cause

Eight of the nine are the same failure: **the contract tests exercise the
service's internal shape, and the browser suites mock the routes, so nothing
compares the wire against the client that consumes it.**

| Where the two sides disagreed | Test that should have caught it | Why it did not |
|---|---|---|
| `POST …/models` body | `test_model_builder_spec` | sends `json={}`; the workbench sends no body |
| Build `export` state | model spec | reads the service dict, never the wire's `null` |
| Model readiness `accepted_snapshot` | model spec | asserts `snapshot_id`, the key the service returns |
| Deliverable freeze `draft_id` | `test_deliverables_spec` | builds the request from `revision["draft_id"]`, a key the wire never served |
| Signed revision `signed_by`/`signed_at` | model spec | asserts service keys; the envelope is `extra="allow"`, so invented client keys fail silently |
| Decimal outputs | — | no test rendered a served value |
| Offered vs startable pathway | — | the frontend held a second copy of the MVP cut |
| READER write controls | `ModelBuilder.test.ts` gates on `canWrite`; the shell had no such test | the shell was never asserted against a role |

Each fix therefore lands with a test written **from the wire only** — the same
bytes a browser gets.

---

## F-1 · Run Console offers a pathway the engine refuses — High

**Where** `caos/frontend/src/components/Workspace.tsx` (Purpose select) ·
`caos/server/caos/engine/runtime.py:47` (`MVP_PATHWAYS`)

**Repro** Run Console → Purpose → *Distressed & Restructuring* → Compile and run.

**Observed** `PATHWAY NOT AVAILABLE` in the page error region.
Server log: `POST /api/cases/case-08daa968247648afb2e7/runs → 422`,
body `{"detail":{"code":"PATHWAY_NOT_AVAILABLE"}}`.

**Expected** AC-RUN-5 — a pathway the menu offers as enabled is startable.

**Cause** `contracts.PATHWAYS` has six pathways and the Purpose menu lists all
six; `MVP_PATHWAYS` has four. Deep Research had a served capability flag; the
other non-MVP pathway had nothing, so the menu and the engine drifted apart with
no signal between them.

**Fix** The engine's cut is now served (`CaseResponse.available_pathways =
sorted(MVP_PATHWAYS)`) and the menu disables anything outside it, with a note
naming what is unavailable. Deep Research keeps its separate actor-specific
gate. Adding a pathway to `MVP_PATHWAYS` now lights it up in the workbench with
no second list to update.

**Regression** `caos/tests/spec/test_runs_spec.py::test_case_wire_offers_exactly_the_pathways_the_engine_will_start`
— for every pathway in `contracts.PATHWAYS`, offered ⇔ startable.

## F-2 · "Build model" is dead: 422 "Field required" — Critical

**Where** `caos/server/caos/api/__init__.py` (`queue_model`) ·
`caos/frontend/src/components/model/ModelBuilder.tsx:311,594`

**Repro** Any model-ready case → Model Builder → Build model.

**Observed** The message "Field required" beside the button; status stays
READY TO BUILD. `POST /api/cases/{id}/models → 422`,
`{"detail":[{"loc":["body"],"msg":"Field required","type":"missing"}]}`.

**Expected** AC-MB — the primary action queues a build.

**Cause** The route declared `body: QueueModelRequest = Body(...)` — a required
body on a model with **no fields**, which exists only to forbid undeclared ones.
`api.ts` POSTs with a JSON content type and no body, so FastAPI refused it.

**Impact** Model Builder could produce nothing, and with it the whole Report
Studio chain for any template that requires a model. F-5, F-6, F-8 and F-9 were
all downstream of this and unreachable until it was fixed.

**Fix** `Body(default_factory=QueueModelRequest)`. A body-less POST and `{}`
both queue; `{"x": 1}` is still 422.

**Regression** `test_model_builder_spec.py::test_queue_build_accepts_the_body_less_post_the_workbench_sends`.

## F-3 · READER is offered six writes that all answer 403 — High

**Where** `caos/frontend/src/components/Workspace.tsx`

**Repro** Sign in with `x-forwarded-groups: caos-reader` on a case the reader is
a member of. Every destination below offers an enabled control.

**Observed** Create case, Upload and version source set (Cases **and** Sources),
Compile and run, Accept analytical snapshot, Switch visible snapshot, Upload CP-3
workbook. Submitting any of them:
`POST /api/cases → 403 {"detail":"insufficient role"}`.

**Expected** AC-ROLE-4 / AC-SHELL-1 — no control for a role that cannot use it.

**Cause** `Workspace.tsx` fetched `/api/me` and used `role` for exactly two
things: the Admin Studio rail entry and the resume button. Model Builder and
Report Studio both compute `canWrite = role !== "READER"` and gate every write;
the shell's own controls did not.

**Fix** One derived predicate in the shell, threaded to Cases, Sources, Run
Console, Deep-Dive and RV Screener. Each write panel is replaced by a one-line
reason rather than a disabled control, matching how Report Studio already reads.

**The first fix was incomplete — see R-2.** It gated on `role`, which defaulted
to `"ANALYST"` and was never demoted when `/api/me` failed, so a reader on a
degraded server still saw every control. The predicate is now tri-state
(`yes` / `no` / `unknown`) over a `READER` default, which also makes Model
Builder and Report Studio fail closed for free.

**Regression** `caos/frontend/scripts/workbench-smoke.mjs` — a reader browser
context asserts each control is absent and read access is intact, **and** a
second pass with `/api/me` aborted asserts the same with the identity
unresolved.

## F-4 · Every block of a large document shows a raw JSON locator — Medium

**Where** `caos/frontend/src/lib/workbench.ts` (`formatBlockLocator`)

**Repro** Sources → open a document over `MAX_BLOCKS_PER_SOURCE`.

**Observed** `B00001 · {"LINES":[1,95]}` on every block.

**Expected** AC-SOURCES-2 / PRODUCT.md ("no raw terminal dumps") — a locator
reads as English.

**Cause** The formatter humanised `{"line": n}` and `{"page": n}` only. Its own
comment said "today's ingestion emits `{"line": n}` only", which stopped being
true when `pack_blocks` gained its `builtin-v2` grouped branch — the branch that
handles every annual report and credit agreement of real size.

**Fix** `{"lines": [first, last]}` → `lines 1–95` (and `line 7` when the range is
one line); `pages` likewise; a malformed range still falls back to JSON.

**Regression** `caos/frontend/src/lib/workbench.test.ts` — six new cases
including the three malformed shapes.

## F-5 · A READY build with no export blanks the whole page — Critical

**Where** `caos/server/caos/api/__init__.py` (`_wire_build`) ·
`ModelBuilder.tsx`

**Repro** Build a model (needs F-2 fixed), then open Model Builder.

**Observed** Next's "This page couldn't load" instead of the workspace. Console:
`TypeError: Cannot read properties of null (reading 'status')`.

**Expected** AC-X-2 — a missing optional field degrades one control, never the page.

**Cause** `_wire_build` served `export: null` when the build had no export
record; the client's `ModelBuild` type declares `export` non-nullable and reads
`build.export.status` in six places. Every build is in that state until someone
exports it, so this was the *normal* case.

**Fix** Two layers, deliberately. The wire serves `{"status": "NOT_REQUESTED",
"error": null}` — `NOT_REQUESTED` is the export's own name for that state. And
every dereference is optional-chained with the types made optional to match, so
a future hole in this field costs one control, not the workspace.

**Regression** `test_model_builder_spec.py::test_a_build_with_no_export_still_serves_its_export_state`.

## F-6 · Model readiness always reports "Not accepted" — Medium

**Where** `caos/server/caos/models/service.py` (`readiness`)

**Repro** Model Builder on a case with an accepted snapshot and a READY build.

**Observed** "ACCEPTED AUTHORITY → Snapshot: Not accepted", contradicting the
topbar's "Accepted 30 Aug 2026, 22:26" on the same screen.
`GET /api/cases/{id}/model` → `"accepted_snapshot": null`.

**Expected** AC-SHELL-3 — the authority panel never contradicts the strip.

**Cause** The route projected `readiness.get("accepted_snapshot")`; the service
returned the same fact under `snapshot_id`. The key mismatch silently produced
`null` on every response.

**Fix** The service returns `accepted_snapshot: {id, run_id, digest}` — the name
the wire and the client both use — alongside `snapshot_id`.

**Regression** `test_model_builder_spec.py::test_readiness_names_the_accepted_snapshot_it_resolved`.

## F-7 · A deliverable can never be frozen: DELIVERABLE_DRAFT_STALE — Critical

**Where** `caos/server/caos/api/__init__.py` (`_wire_dl_revision`) ·
`ReportStudio.tsx` (`freeze`)

**Repro** Report Studio → draft every required section → Freeze saved v1.

**Observed** `DELIVERABLE_DRAFT_STALE` on a draft saved seconds earlier and
untouched since. `POST …/deliverables/FULL_CREDIT/freeze → 409`.

**Expected** AC-RS-2 — freezing a saved, unmodified draft succeeds.

**Cause** `FreezeDeliverableRequest` is keyed on `draft_id`
(`dldraft-0b18c…`), but the draft wire served only `id`, which is the *revision*
(`dlrev-4c6e5…`). No client reading the wire could name the draft, so the
workbench sent the revision id and `_revision_for_freeze` fell through its loop
to "unknown draft".

**Impact** Freeze, filing, and all three deliverable exports were unreachable —
the entire committee-output half of the product.

**Fix** `DeliverableRevisionResponse` now carries `draft_id`, and Report Studio
sends it. Verified end to end afterwards: draft → **FROZEN** → (as APPROVER)
**FILED** → MD 6 597 B, PDF 3 211 B, XLSX 7 277 B all served.

**Regression** `test_deliverables_spec.py::test_freeze_round_trips_on_nothing_but_what_the_draft_wire_serves`
— the test is allowed to read only the wire response, which is exactly the
constraint the shipped client works under.

## F-8 · A signed revision shows "undefined · —" as its signer — Medium

**Where** `ModelBuilder.tsx` (`ModelRevision`)

**Repro** Model Builder → edit an assumption → Preview → note → Sign Off.

**Observed** "Active Analyst Model · R1 / undefined · — · Raised FY2025…", and
the same blanks in the revision history table.

**Expected** AC-MB-2 — a signed revision names its signer and instant.

**Cause** The revision envelope is service-owned (`OpenWireModel`,
`extra="allow"`), so it serves `created_by` / `created_at`. The client declared
and read `signed_by` / `signed_at`, which the envelope's laxity let pass as
`undefined` rather than failing.

**Fix** Read the served names; "Signed" stays the label an analyst sees.

**Regression** `test_model_builder_spec.py` sign-off test now pins the envelope's
key names and asserts the invented ones are absent.

## F-9 · Model outputs render at raw decimal precision — Medium

**Where** `ModelBuilder.tsx` → moved to `modelBuilderState.ts` (`formatModelValue`)

**Repro** Model Builder → Model view, with an Active Analyst Model.

**Observed** `ACCESSIBLE LIQUIDITY 136.88000000000000000000`,
`CASH AND EQUIVALENTS 61.88000000000000000000`.

**Expected** PRODUCT.md — "numbers read as audited rather than decorative"
(AC-X-5's spirit); every other surface formats to two decimals.

**Cause** The calculation engine serializes Decimals, so outputs arrive as
numeric **strings** (`"136.8800000000000000000000000"`). The formatter handled
`typeof value === "number"` and fell through to `String(value)` for everything
else.

**Fix** Numeric strings are formatted with the same `Intl.NumberFormat`; a string
that is not a number is still shown verbatim. Moved beside the other pure state
helpers so it can be unit-tested (the component file cannot be imported by
`node --test`).

**Regression** `modelBuilderState.test.ts` — 14 cases including `Infinity`,
`NaN`, `""`, `-1.5e2`, and a non-numeric string.

---

## Adversarial review of the fixes (R-*)

Running `adversarial-reviewer` over this session's own diff returned **BLOCK**.
Four of its findings were confirmed by reproduction and fixed; the review is the
reason the two most serious ones are not still in the branch.

**R-1 · `qa/env.sh` failed the repo's own gitleaks gate — critical.** Two
`generic-api-key` findings (entropy ~3.98) on committed 64-hex secrets, and
gitleaks is a gate on both `ci.yml:319` and `nightly.yml:137`; the branch would
have failed CI on push. The secrets are now generated on first use into
`qa/.secrets` (gitignored). Verified clean in both scan modes.

**R-2 · The READER gate failed open — critical.** Reproduced against the *fixed*
build with `/api/me` aborted:
`{"writeButtons":["Create case","Upload and version source set"],"fileInputs":1}`
— the exact controls F-3 removes, and the POST they offer answers 403. `role`
defaulted to `"ANALYST"` and the catch only called `setError`. Now `READER` by
default with a `roleResolved` flag; unresolved renders "Confirming your access…"
rather than either a write control or a false reader claim. Covered by the new
smoke pass.

**R-3 · The new number formatter could print a number the server never sent —
warning.** `formatModelValue("12345678901234567890.5")` returned
`"12,345,678,901,234,567,000"`, and `"1e309"` disappeared as "Unavailable". The
double round-trip is now used only inside `Number.MAX_SAFE_INTEGER`; outside it
the served digits are shown verbatim. Ugly and exact beats tidy and wrong in a
product that promises every number is one click from its evidence.

**R-4 · Three expressions of one predicate — warning.** `canWrite` as a prop,
`role` as a prop recomputed inside two components, and a third inline
`role !== "READER"` for the resume control. Collapsed to one derived
`writeAccess`, with the `READER` default making the two `role` consumers correct
without touching them. The duplicated reader sentence went with it (one
`WriteBlocked` component).

Also from the review, fixed: the QA proxy now refuses a non-loopback upstream
(it mints identities with the real edge secret, and loopback was the only thing
making that a fixture rather than a bypass), and a missing `EDGE_PROXY_SECRET`
reports a sentence instead of a `KeyError` traceback.

Left as recorded rather than fixed: `qa/probe.py` mutates the seeded dataset on
each run with no cleanup, and a served `available_pathways: []` would disable
every option while leaving the submit button enabled — a degenerate config that
no deployment produces.

## Observations — not defects, recorded for the ledger

**O-1 · Four served capabilities have no user surface.** `POST/GET
/api/cases/{id}/notes`, `POST …/notes/{id}/promote`, `POST/GET
/api/cases/{id}/rv` and `POST /api/runs/{id}/upgrade` are all served, audited and
tested, and no frontend code calls them. Promoting an analyst note to a governed
source (`src-note-…`) is a real product capability that an analyst cannot reach.

**O-2 · A case can never gain an approver.** `store.add_member` requires the
actor to already hold case ADMIN/APPROVER standing (or global ADMIN), and no HTTP
route grants membership. A case created by an analyst therefore has exactly one
member forever, so `require_case_approver` can never be satisfied and the
deliverable filing gate is unreachable in any deployment without out-of-band
database access. This QA pass had to seed membership through the store
(`qa/seed.py::add_members`) to exercise filing at all.

**O-3 · Report Studio persists nothing until every required section is drafted.**
The status reads "Complete required sections to autosave". The unsaved-draft
guards (click, popstate, beforeunload) do warn, so nothing is lost silently — but
an analyst who drafts two sections and closes the tab keeps nothing.

**O-4 · `GET /api/cases/{id}/sources` returns every block of every source.**
Measured on the seeded case with one large document: 2 545 200 B raw, 81 490 B
gzipped, 64–170 ms. Fine at this size; it grows linearly with document size and
is fetched on every Sources and Report Studio visit.

**O-6 · The artifact reader is a deliberately minimal markdown renderer.**
`artifactReader.ts` promotes `## ` lines to headings and leaves everything else
as plain text — no library, no HTML, documented as the safe choice. The
consequence on a real CP-1 output is that `### Model period register`,
`<!-- table-id: cp1.model_period_register -->` and pipe-delimited tables all
reach the analyst verbatim, so the module output they are meant to read closely
is the least readable surface in the product. Widening it is a design decision,
not a defect fix, so it is recorded rather than changed.

**O-5 · The deliverable export serves `application/octet-stream` for md/pdf/xlsx.**
Already in CLAUDE.md's ledger. Confirmed live: all three formats download with
that type, so the already-compressed ones are re-gzipped.

## Checked and clean

- Escape closes both `<dialog>`s and returns focus to the trigger (verified
  under Playwright — the Browser pane's key injection does not drive the native
  close request, which produced a false positive first).
- `worker.py --once` exits cleanly; the hang seen in `qa/seed_model.py` is that
  script's own undisposed engine pool, not the shipped entrypoint.
- The CSP `style-src 'self'` violation in the console came from Next's error
  page during the F-5 crash, not from the app.
- A blank screenshot when scrolled is a Browser-pane capture artifact:
  `elementFromPoint` returns visible, painted content at the same coordinates.
- Production identity edge: no secret → 401; wrong secret → 401; client
  `x-caos-role` never escalates; unknown and unauthorised cases are both 404.
- Source admission: >25 MB, `.exe`, empty, whitespace-only and EICAR are all
  refused, and none of them versions the source set.
- Boundary text: control bytes, bidi overrides and over-length are refused; an
  RTL directional mark is accepted.
