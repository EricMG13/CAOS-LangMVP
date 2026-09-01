# CAOS user-surface inventory and acceptance criteria

Scope: every user-facing feature, role, route, control, input, modal, state and
workflow reachable in a **production-configured** deployment, each with the
acceptance criteria it is judged against and the finite, risk-ranked edge cases
exercised. Findings live in `qa/FINDINGS.md`.

**How much of this is automated.** `qa/probe.py` runs 40 checks covering the
HTTP-observable criteria: AC-ROLE-1..4, AC-CASES-3, AC-RUN-5, AC-X-1, AC-X-3,
AC-X-4, AC-X-7 and the edge-identity rules. `npm run a11y` covers AC-X-5 across
desktop, laptop, and 200% desktop-zoom route combinations; `npm run test:workbench` covers AC-ROUTE-1..4,
AC-SHELL-1..3, AC-DD-1..2, representative Sources/Model/Report authority and
recovery paths, and AC-X-6. Criteria not named by a standing check remain a
manual checklist.

## 0. The environment under test

| Piece | Production | Here | Fidelity |
|---|---|---|---|
| App | `caos/server/run.py`, `ENVIRONMENT=production` | same, port 8099 | identical |
| Domain store | PostgreSQL | PostgreSQL 17 in Docker, port 55433 | identical |
| Run checkpoints | SQLite on the data volume | SQLite under the QA data dir | identical (this is the shipped behaviour) |
| Identity edge | Caddy → oauth2-proxy → app | `qa/edge_proxy.py` → app | same header contract (`x-edge-authorization`, `x-forwarded-user/-email/-groups`); no real OIDC |
| Malware scan | clamd | clamav 1.4 (same pinned digest) in Docker | identical |
| Worker | `caos/server/worker.py` + LibreOffice | same, host `soffice` | identical |
| Frontend | static export served by the app | same (`npm run build` → `caos/frontend/out`) | identical |
| TLS | Caddy | none (loopback) | HSTS is emitted but ignored on an IP literal |

### Standing the stack up

```bash
docker run -d --name caos-qa-pg -e POSTGRES_PASSWORD=qa-local-only-not-a-secret-0000 \
  -e POSTGRES_DB=caos -p 55433:5432 postgres:17-alpine
docker run -d --name caos-qa-clamav --platform linux/amd64 -p 33100:3310 \
  -v "$PWD/caos/deploy/clamd.conf:/etc/clamav/clamd.conf:ro" \
  clamav/clamav:1.5@sha256:0e85467cb0d6e7d860a45035707741cd5ffc032ffefc6002a3510c75b6d07027
source qa/env.sh                                   # production-mode settings
export CAOS_DATA_DIR=.qa-data CAOS_STORAGE_DIR=.qa-vault
(cd caos/frontend && npm run build)
(cd caos/server && python run.py) &                # app on :8099
(cd caos/server && python worker.py) &             # builds + XLSX exports
python qa/edge_proxy.py &                          # trusted edge on :8100
python qa/seed.py                                  # 48 cases, ~200 sources, runs
python qa/seed_model.py                            # model-ready cases (app stopped)
python qa/probe.py                                 # 40 HTTP-observable checks
```

Browse at `http://127.0.0.1:8100`; `/_qa/role/READER` (or APPROVER / ADMIN /
NOGROUP) swaps the persona the edge asserts.

Data: `qa/seed.py` + `qa/seed_model.py`. Wholly synthetic — invented issuers,
generated document text, PRNG numbers. No real company, filing, price, person or
credential. 48 cases, ~207 sources, 15+ runs, accepted snapshots, notes,
promoted notes, withdrawn sources, RV rows, and model-ready cases.

## 1. Roles

Production derives the role from OIDC groups only (`identity.py`); a client
`x-caos-role` header is ignored. Two independent dimensions gate every write:
the **global role** (from groups) and **case standing** (the `case_members` row).

| Group | Global role | Reads a case | Writes a case | Files a deliverable | Admin Studio |
|---|---|---|---|---|---|
| `caos-admin` | ADMIN | member only | member with writer standing | member with APPROVER/ADMIN standing | unavailable contract screen |
| `caos-approver` | APPROVER | member only | member with writer standing | member with APPROVER/ADMIN standing | unavailable contract screen |
| `caos-analyst` | ANALYST | member only | member with writer standing | member with APPROVER/ADMIN standing | unavailable contract screen |
| `caos-reader` | READER | member only | never | never | unavailable contract screen |
| none | READER (floor) | member only | never | never | unavailable contract screen |

**AC-ROLE-1** An unknown/absent group set floors to READER, never to a writer.
**AC-ROLE-2** A client-supplied `x-caos-role` never changes the served role.
**AC-ROLE-3** An unauthorised case and an unknown case are indistinguishable (404 both).
**AC-ROLE-4** READER sees no write control anywhere (no upload, no compile, no accept, no sign-off, no freeze).

## 2. Routes

Nine static export routes, all trailing-slash, all rendering `Workspace`:

`/` · `/cases/` · `/sources/` · `/run-console/` · `/deep-dive/` ·
`/rv-screener/` · `/command-center/` · `/model-builder/` · `/report-studio/` ·
`/admin-studio/` · `/404.html`

Query parameters that carry state: `case`, `run`, `artifact`, `source`, `q`.

**AC-ROUTE-1** Every route deep-links: reloading with `?case=…&run=…` restores the same authority.
**AC-ROUTE-2** An unknown route renders "Page not found", not a crash or a blank shell.
**AC-ROUTE-3** A `case` query naming a case the caller cannot see does not leak its existence and does not wedge the workspace.
**AC-ROUTE-4** Route hrefs keep their trailing slash (otherwise the client payload 404s and the transition degrades to a document load).

## 3. Shell (`WorkbenchShell`) — present on every route

| Control | Kind | Acceptance criteria |
|---|---|---|
| Skip to content | link | first tab stop; moves focus to `#main-content` |
| Rail: 7 workflow links | links | Portfolio, Credit, Sources, Analysis, Market, Model and Report; exactly one carries `aria-current="page"` per route |
| Rail: tools group | links | shown only for the active workflow; Run Console shows `LIVE` only while the selected case's run is queued/running |
| Rail: Admin | link | visible to every role and opens an honest unavailable contract screen |
| Authority strip | region | shows credit, accepted snapshot, selected run and source-set identity, or explicit loading/unavailable values |
| Case `<select>` | input | lists every visible case; changing it re-homes the whole workspace |
| Sources & evidence | link | carries the selected case to the Sources workspace |
| Command palette | button + `⌘K` + `<dialog>` | opens modal, focus into the search box, Escape closes and returns focus to the trigger |
| Palette results | listbox | arrow keys move `aria-activedescendant`; Enter activates; an exact `src-…`/`art-…` id offers a direct evidence jump |
| Evidence drawer | dialog | opens only from a verified source in the active case; closes on Escape and navigation |
| Page error | `role="alert"` | announced, never silently swallowed |

**AC-SHELL-1** No route-level control appears for a role that cannot use it.
**AC-SHELL-2** The palette is operable by keyboard alone end to end.
**AC-SHELL-3** The authority strip never claims an acceptance that the case does not hold.

Edge cases: 0 cases; 48 cases in the select; a case whose name/issuer contains
RTL text; palette query matching nothing; palette open while a case switch lands.

## 4. Destination inventory

### 4.1 Cases (`/cases/`)

Panels: proposed portfolio-contract notice · Monitored credits · Create case · Pathway fit.

| Control | Kind | Acceptance criteria |
|---|---|---|
| Search credits | `type=search` | filters on issuer + name + sector, case-insensitive, live |
| Authority filter | `<select>` all/accepted/unaccepted | composes with search; count reads "N of M" |
| Open credit (per row) | link | carries the case to the Credit workflow; the selected row is visually identified |
| Create case form | name (required), issuer (required), sector | 201 → the new case is prepended, selected, and the form resets |

**AC-CASES-1** Creating a case with a blank required field is refused by the browser before any request.
**AC-CASES-2** A create that the server refuses shows the server's message; no phantom row is added.
**AC-CASES-3** Source upload refusals are verified on the Sources workflow; the Portfolio surface does not duplicate intake.
**AC-CASES-4** The page has exactly one page-level primary action.

Edge cases (risk-ranked): oversized file (>25 MB) · disallowed suffix (`.exe`)
· zero-byte file · EICAR malware string · a 160-char issuer name · control
characters / bidi override in the case name · duplicate issuer · file whose
name contains a path separator.

### 4.2 Sources (`/sources/`)

| Control | Kind | Acceptance criteria |
|---|---|---|
| Search documents | `type=search` | filters filename, source id and digest, case-insensitive and live |
| Source register | selectable rows | one row per filtered source with filename, stable id, block count and extraction state |
| Source reader | document blocks | renders up to 40 extracted blocks with locators; over 40 says so |
| Evidence support | facts + button | exposes full digest and selected-block locator; opens the source-bound evidence drawer |
| Add governed source | file form | accepts `.pdf,.xlsx,.json,.txt,.md,.csv`; 201 versions the source set |
| Evidence focus panel | panel (`?artifact=`) | renders the artifact reader with citations |

**AC-SOURCES-1** `?source=<id>` for a source outside the active case set shows a scoped message, never another case's content.
**AC-SOURCES-2** Block text renders as text — no HTML injection surface.
**AC-SOURCES-3** A withdrawn source is still visible as a record but is excluded from a new run's pinned set.

Edge cases: a source with 320 blocks (grouped `builtin-v2` locators) · a
promoted note source (`src-note-…`) · `?artifact=` for an artifact of another
case · `?source=` for a well-formed but nonexistent id.

### 4.3 Run Console (`/run-console/`)

| Control | Kind | Acceptance criteria |
|---|---|---|
| Purpose `<select>` | 6 pathways | every enabled option must be startable |
| Depth `<select>` | screen / full | `screen` disabled when pathway is DEEP_RESEARCH |
| Research brief fieldset | 6 inputs | shown only for DEEP_RESEARCH |
| Compile and run | submit | 201 → immutable plan returns immediately; the DAG renders |
| Route DAG | nodes | one node per plan module; a node with an artifact links to its output |
| Accept analytical snapshot | primary button | opens the confirm dialog; on confirm the run reads "Accepted" |
| Resume run | button | shown on a paused run; hidden for READER |
| Approve research plan | button | shown only on `PLAN_APPROVAL_REQUIRED` |

**AC-RUN-1** Progress reaches the UI from the SSE event tail without a manual refresh.
**AC-RUN-2** A terminal run closes its stream; no reconnect loop.
**AC-RUN-3** A run with an empty source set pauses with `SOURCE_SET_EMPTY` and offers the route to Sources.
**AC-RUN-4** Acceptance is confirmed in a modal that names what it replaces.
**AC-RUN-5** A pathway the server refuses must not be offered as an enabled option.

Edge cases: compile with no case · compile with zero sources · two runs on one
case in sequence · accept twice (idempotent) · accept a failed run · reload
mid-run · switch case while a run streams.

### 4.4 Deep-Dive (`/deep-dive/`)

Read-only accepted-analysis reader with module contents, provenance, cited-source
rail, and the visible-vs-latest switch.

**AC-DD-1** Renders only artifacts from the visible accepted snapshot — never the compile form or accept control.
**AC-DD-2** "Switch visible snapshot" appears only when `switch_required` is true and moves the visible authority on success.

### 4.5 RV Screener (`/rv-screener/`)

| Control | Kind | Acceptance criteria |
|---|---|---|
| Workbook upload | `type=file` `.xlsx` | invalid workbook → typed findings list, no active universe |
| Active authority panel | dl | version, digest, row count, source link |
| Issuer/ID search | search | filters across company/borrower/loan id/FIGI |
| Sector/Rating/Ranking/Loan type | 4 selects | options derived from the active universe |
| Maturity from/to | 2 date inputs | inclusive range |
| Margin/DM min-max | 4 number inputs | inclusive range; blank means unbounded |
| Column sort | 27 header buttons | toggles asc/desc; `aria-sort` matches |
| Pagination | Previous/Next | only when the filtered set exceeds one page; filters reset to page 1 |

**AC-RV-1** Values render in workbook units, never silently converted.
**AC-RV-2** A filter combination matching nothing says so rather than showing an empty table.
**AC-RV-3** Sorting is stable (ties break on `instrument_key`).

Edge cases: workbook with a bad sheet · non-numeric margin filter · maturity
range inverted (from > to) · sort on an all-null column.

### 4.6 Command Center (`/command-center/`)

**AC-CC-1** Lens and diff load independently; one failing does not blank the other.
**AC-CC-2** With no accepted snapshot the posture panel offers the route to Run Console instead of a false "no change".
**AC-CC-3** No system recommendation is rendered anywhere on this page.

### 4.7 Model Builder (`/model-builder/`)

| Control | Kind | Acceptance criteria |
|---|---|---|
| Build model / Retry build | button | 202 → queued; the worker moves it to READY |
| Refresh / Refresh authority | button | re-reads without losing the local draft |
| Assumption number inputs | `type=number` | non-finite and blank refused before submit |
| Preview Draft Revision | button | server-calculated; digest returned |
| Sign Off Revision + note | button + textarea | binds the exact preview digest; a stale digest is refused |
| Run Multi-Driver Scenario | button | server-calculated, never client-calculated |
| Run one-way | button + 3 numbers | route may be unserved → renders the unavailable block |
| Export XLSX / Retry export | button | queues; worker renders; download carries the sha256 header |
| Download exact XLSX | link | binary, `no-store` |
| Apply Rebase Candidate | button | only when a newer build exists |
| Views tablist | 4 buttons | Model / Assumptions / Sensitivities / History |

**AC-MB-1** An unsigned draft cannot be lost silently: leaving the page, switching case, or using browser history prompts first.
**AC-MB-2** Sign-off is a CAS: a second sign-off against a stale head is refused with a typed conflict.
**AC-MB-3** Every calculated number comes from the server response.
**AC-MB-4** READER sees no build, sign-off, scenario or export control.

Edge cases: build on a case with no accepted snapshot · sign off twice · sign
off with an empty note · scenario shock of `1e309` · export before build ·
download before export.

### 4.8 Report Studio (`/report-studio/`)

| Control | Kind | Acceptance criteria |
|---|---|---|
| Pathway template select | select | switching templates keeps or explicitly discards the draft |
| Section nav | button per block | `aria-current` on the selected block |
| Add optional block | buttons | disabled at the template's `max_items` |
| Narrative textarea | 20 000 chars | live counter; over-length refused |
| Claim authority radios | Evidence-bound / Analyst judgment | Evidence-bound with zero citations blocks freeze |
| Cite block / Remove citation | buttons | citations only from delivered evidence |
| Deliverable model radios | radio/checkbox | fallback to the Application Build requires an explicit acknowledgement |
| Scenario Exhibit form | 3 selects + value | server-calculated exhibit inserted verbatim |
| Freeze saved vN | primary button | requires a saved revision; revalidates server-side |
| File exact Frozen version | button | **APPROVER/ADMIN case standing only** |
| Request changes + comment | button + textarea | comment required; creates a new draft |
| Restore as new revision | button per revision | never overwrites history |
| Browser recovery | restore / retry / download / discard | scope- and template-bound; retry preserves the copy's original expected version so a newer shared draft conflicts instead of being overwritten |
| MD / PDF / XLSX download | links | only after filing |
| Conflict resolution | 2 buttons | "Retry over current vN" / "Use shared vN" |

**AC-RS-1** An unsaved draft prompts before navigation, case switch or unload.
**AC-RS-2** Freeze binds the exact draft digest; a concurrent save is refused, not merged.
**AC-RS-3** Filing is absent without a global APPROVER/ADMIN role; the server independently requires case approver standing and returns a typed refusal when it is absent.
**AC-RS-4** Export links are dead until the deliverable is FILED.

Edge cases: two tabs editing one draft · freeze a draft that another user just
superseded · file without approver standing · request changes with whitespace
only · 20 001-character narrative.

### 4.9 Admin Studio (`/admin-studio/`)

**AC-AS-1** Reachable by every role so capability status can be inspected without implying authority.
**AC-AS-2** No audit, membership, export or step-up control is rendered while those routes are absent.
**AC-AS-3** The route renders the unavailable contract and required backend capabilities, not simulated governance or a generic error.

## 5. Cross-cutting

**AC-X-1 Wire strictness.** Every JSON success matches its named response model; unknown fields are refused both ways.
**AC-X-2 Fail-closed refusals.** Every refusal is typed and carries no evidence text.
**AC-X-3 Security headers.** CSP, nosniff, referrer-policy, permissions-policy, COOP on every response; HSTS in production.
**AC-X-4 Admission ceilings.** Rate limit, stream and preview concurrency refuse rather than queue unboundedly.
**AC-X-5 Accessibility.** WCAG 2.1 AA: contrast, focus visibility, no status by colour alone, reduced-motion honoured.
**AC-X-6 Performance.** First contentful paint under the pinned budget on the seeded (48-case) dataset.
**AC-X-7 Boundary text.** Control bytes and bidi overrides are refused at every string that reaches pinned state.
