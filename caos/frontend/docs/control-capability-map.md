# Approved design control-to-capability map

This map binds the approved screens (the Align destinations of `DESIGN.md`'s
2026-09-06 addendum) to the routes the server actually serves (`GET /openapi.json`
on the combined app; re-checked by FE-G4 on 2026-09-06). It is intentionally
conservative: an absent contract produces an unavailable state, never a
browser-derived substitute, and no control is drawn for a route the server does
not serve. "Served, not drawn" names a contract the server serves that no surface
renders yet; drawing it is an information-architecture decision, not a capability
gap. FE-G3 drew the two governance contracts the approved Align canvas and FE-A1 D7
assigned (member provisioning and the case audit package, both on Admin);
withdrawal and notes stay "served, not drawn" because no approved artboard draws
them.

| Surface | Control or data | Production source | Treatment |
|---|---|---|---|
| Portfolio | Case register and open-credit action | `GET /api/cases` | Served |
| Portfolio | Document-first intake (files only; issuer, label, types, periods, dispositions and the route come back as labelled machine suggestions) | `POST /api/intake`, `GET /api/cases/{case_id}/intake` | Served; the page's one primary action |
| Portfolio | Create a case by hand | `POST /api/cases` | Served as the advanced control beside intake; the ambiguous-issuer refusal links to it (FE-G3 D10) |
| Portfolio | Attention ordering, threshold distance, freshness score | No governed portfolio-summary route is served | Unavailable; no client ranking |
| Credit | Accepted and latest snapshot identity | `GET /api/cases/{case_id}/snapshot`, read once by the shell and rendered by every surface (one authority per screen) | Served |
| Credit | Issuer lens (issuer, sector, accepted snapshot, source set) | `GET /api/cases/{case_id}/lens` | Served; degrades to its own unavailable block |
| Credit | Accepted module conclusions and evidence counts | Snapshot artifact ids plus `GET /api/cases/{case_id}/artifacts/{artifact_id}` | Served as exact module output |
| Credit | Normalized binding metric, threshold, tolerance and gap summary | No normalized credit-summary route is served | Unavailable; no inferred values |
| Sources | Upload source objects | `POST /api/cases/{case_id}/sources` | Served; the upload form versions the supplied source |
| Sources | Paged metadata inventory and selected source detail | `GET …/source-summaries`, `GET …/sources/{source_id}` | Summary pages exclude block text; detail loads on selection; every block is reachable |
| Sources / Report | Complete active-case evidence search | `GET …/evidence-search?q=…&cursor=…` | Bounded server results search unopened sources; exact source/block links preserve context |
| Sources | Withdraw a source | `POST /api/cases/{case_id}/sources/{source_id}/withdraw` | Served, not drawn (D-G; no approved artboard draws it) |
| Sources | Analyst notes | `GET`/`POST /api/cases/{case_id}/notes`, `POST …/notes/{note_id}/promote` | Served, not drawn (D-G) |
| Sources | Claim-to-source coverage matrix | No normalized claim-map route is served | Unavailable |
| Run | Compile a route by hand | `POST /api/cases/{case_id}/runs` | Served; collapsed to "Advanced: compile a route" on an intake-created run (FE-G3 D11) |
| Run | Run stages, live progress, resume and exact artifact output | `GET /api/runs/{run_id}`, `GET /api/runs/{run_id}/events` (SSE; event names trigger a refetch, payloads are never read), `POST /api/runs/{run_id}/resume`, `GET /api/cases/{case_id}/artifacts/{artifact_id}` | Served |
| Run | Upgrade a run | `POST /api/runs/{run_id}/upgrade` | Served, not drawn (no approved artboard) |
| Run | Deep Research plan review and digest-bound approval | The persisted plan and its hash are read from the run record; `POST /api/runs/{run_id}/research-plan/approve` (`GET /api/runs/{run_id}/research-plan` is served and not called) | Served and drawn on Run (`/run/`) |
| Run | Accept the exact run snapshot | `POST /api/runs/{run_id}/accept` | Served; a completed intake run is opened for review and never accepted on the analyst's behalf |
| Analysis | Accepted artifacts, reader and evidence rail; switch the visible accepted snapshot | `GET /api/cases/{case_id}/artifacts/{artifact_id}`, `POST /api/cases/{case_id}/snapshot/switch` | Served |
| Market | Active loan universe, filters, values and source locators; workbook upload | `GET /api/cases/{case_id}/rv/loan-universes/active`, `POST /api/cases/{case_id}/rv/loan-universes` | Served |
| Market | Relative Value record | `GET`/`POST /api/cases/{case_id}/rv` | Served, not drawn (the Relative Value route runs through Run) |
| Market | Relative percentile | No deterministic percentile contract | Omitted; stated in words |
| Model | Build, worksheet, assumptions, preview, scenario, revisions, rebase preview and sign-off | `GET`/`POST /api/cases/{case_id}/models`, `GET …/models/{build_id}`, `GET …/models/{build_id}/worksheet`, `GET …/models/assumption-registry`, `POST …/models/previews`, `POST …/models/scenarios`, `GET …/model`, `GET …/model-revisions`, `POST …/model-revisions/rebase-preview`, `POST …/model-revisions/sign-off` | Served with existing guards |
| Model | Export and download | `POST …/model-revisions/{revision_id}/export`, `GET …/model-revisions/export-statuses`, `GET …/model-revisions/{revision_id}/download`, `GET …/models/{build_id}/download` (`POST …/models/{build_id}/export` is served and not called) | Served and drawn |
| Model | Tornado (four legacy drivers against the complete current forecast) | `POST /api/cases/{case_id}/models/tornado` | Served and drawn; the sensitivity control |
| Model | One-way sensitivity | `POST /api/cases/{case_id}/models/sensitivities/one-way` | Served, not drawn (D-F): the tornado is the sensitivity control and covers the same drivers |
| Report | Draft, autosave, scenario, freeze, filing and export | `GET`/`PUT …/deliverables/{pathway}/draft`, `POST …/deliverables/{pathway}/freeze`, `POST …/deliverables/by-id/{id}/approve`, `GET …/deliverables/by-id/{id}/export/{format}` (md, pdf, xlsx links unlock after filing) | Served; client and server require a current global writer plus stored case approver/admin standing; signer and freezer cannot file |
| Report | Opinion sign-off on the exact saved revision | `POST /api/cases/{case_id}/deliverables/{pathway}/opinion` | Served |
| Report | Freeze as a worker job, tracked to the frozen record | `POST …/freeze`, `GET …/deliverables/freeze-jobs/{job_id}` | Served |
| Report | Filing receipt and request-changes | `GET …/deliverables/by-id/{id}/receipt`, `POST …/by-id/{id}/request-changes` | Served |
| Report | Saved revision read by id | `GET …/deliverables/revisions/{revision_id}` | Served, not drawn |
| Report | Browser recovery copy | Browser `localStorage`, one slot per subject, case, pathway and browser tab | Served as recovery only; never authority; never offered to another subject |
| Admin | Member provisioning (a distinct APPROVER or ADMIN) | `POST /api/cases/{case_id}/members` | Served and drawn on Admin (FE-G3, D7); the control renders only for a current global writer role with stored APPROVER/ADMIN case standing, a reader sees the reason, and the filing gate stays on Report |
| Admin | Case audit package | `GET /api/cases/{case_id}/audit-package` | Served and drawn on Admin (FE-G3, D7): a download whose receipt names the `x-caos-sha256` digest; a 404 renders the unavailable state |
| Admin | Audit rows, bundle integrity, step-up operations | Routes absent in this deployment (the page probes `GET /api/admin/bundle` and renders its 404) | Unavailable; requirements only |

Unavailability is observed, not configured: a capability call that answers 404
(or 405 for a POST-only route behind the static catch-all) renders its
"Not available in this deployment." block. A 404 for a run-scoped route is
remembered for that run only, because the same 404 also means an unknown or
unauthorized run.

No mobile control, layout, breakpoint, fixture, snapshot or acceptance target is
part of this implementation. The narrow reflow is solely for desktop browser
zoom at 200%.

Enterprise workflow update (2026-09-06):

| Surface | Control or data | Production source | Treatment |
|---|---|---|---|
| Admin | First independent approver for a known case ID | `POST /api/admin/cases/{case_id}/bootstrap-approver`; `/api/me.can_bootstrap_approver` | Operator-only one-shot grant; no case read access or membership is inferred |
| Admin | Default provider/model for new runs | `GET /api/admin/providers`, `POST /api/admin/provider-default`; `/api/me.can_manage_providers` | Safe qualified catalog IDs, policy-version CAS, change receipt; no browser credentials |
| Run | Pinned provider/model | `RunResponse.provider_identity` | Actual recorded binding; historical missing identity remains unavailable |
| Analysis / Sources | Accessible Markdown tables | Canonical artifact Markdown | Native table markup, escaped text, malformed-table fallback |
| Report | Initial pathway | Latest accepted snapshot `run_id`, then `GET /api/runs/{id}` | Initialized once from accepted authority; explicit template choices and dirty drafts are preserved |
| Sources | Withdrawn-source status | Selected source `withdrawn` field | Historical review only; never offered as current citation support |
