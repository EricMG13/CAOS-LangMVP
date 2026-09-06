# Approved design control-to-capability map

This map binds the approved desktop screens to the current production API. It
is intentionally conservative: an absent contract produces an unavailable
state, never a browser-derived substitute, and no control is drawn for a route
the server does not serve. "Served, not drawn" names a contract the server
serves that no surface renders yet; drawing it is an information-architecture
decision (FE-G3), not a capability gap.

| Surface | Control or data | Production source | Treatment |
|---|---|---|---|
| Portfolio | Case register and open-credit action | `GET /api/cases` | Served |
| Portfolio | Document-first intake (files only; issuer, label, types, periods, dispositions and the route come back as labelled machine suggestions) | `POST /api/intake`, `GET /api/cases/{case_id}/intake` | Served |
| Portfolio | Attention ordering, threshold distance, freshness score | No governed portfolio-summary response | Unavailable; no client ranking |
| Credit | Accepted and latest snapshot identity | `GET /api/cases/{case_id}/snapshot`, read once by the shell and rendered by every surface (one authority per screen) | Served |
| Credit | Issuer lens (issuer, sector, accepted snapshot, source set) | `GET /api/cases/{case_id}/lens` | Served; degrades to its own unavailable block |
| Credit | Accepted module conclusions and evidence counts | Snapshot artifact ids plus `GET /api/cases/{case_id}/artifacts/{artifact_id}` | Served as exact module output |
| Credit | Normalized binding metric, threshold, tolerance and gap summary | No normalized credit-summary response | Unavailable; no inferred values |
| Sources | List, read and upload source objects | Existing case source routes | Served |
| Sources | Withdraw a source | `POST /api/cases/{case_id}/sources/{source_id}/withdraw` | Served, not drawn (D-G; an IA decision for FE-G3) |
| Sources | Analyst notes | `GET`/`POST /api/cases/{case_id}/notes` | Served, not drawn (D-G) |
| Sources | Claim-to-source coverage matrix | No normalized claim-map response | Unavailable |
| Analysis | Run stages, live progress, resume and exact artifact output | Existing run, event and artifact routes | Served |
| Analysis | Deep Research plan review and digest-bound approval | `GET /api/runs/{run_id}/research-plan`, `POST /api/runs/{run_id}/research-plan/approve` | Served and drawn in the run console |
| Review | Accept exact run snapshot and switch visible accepted snapshot | Existing accept and snapshot-switch routes | Served |
| Market | Active loan universe, filters, values and source locators | Existing active-universe route | Served |
| Market | Relative percentile | No deterministic percentile contract | Omitted |
| Model | Build, worksheet, assumptions, preview, scenario and sign-off | Existing model routes | Served with existing guards |
| Model | Tornado (four legacy drivers against the complete current forecast) | `POST /api/cases/{case_id}/models/tornado` | Served and drawn; the sensitivity control |
| Model | One-way sensitivity | `POST /api/cases/{case_id}/models/sensitivities/one-way` | Served, not drawn (D-F): the tornado is the sensitivity control and covers the same drivers |
| Report | Draft, autosave, scenario, freeze, filing and export | Existing deliverable routes | Served; client gates global role and server enforces case approver standing |
| Report | Opinion sign-off on the exact saved revision | `POST /api/cases/{case_id}/deliverables/{pathway}/opinion` | Served |
| Report | Freeze as a worker job, tracked to the frozen record | `POST …/freeze`, `GET …/deliverables/freeze-jobs/{job_id}` | Served |
| Report | Filing receipt and request-changes | `GET …/deliverables/by-id/{id}/receipt`, `POST …/by-id/{id}/request-changes` | Served |
| Report | Approver provisioning | `POST /api/cases/{case_id}/members` | Served; drawn in Report Studio until FE-G3 moves it to Admin (D7) |
| Report | Browser recovery copy | Browser `localStorage`, one slot per subject, case, pathway and browser tab | Served as recovery only; never authority; never offered to another subject |
| Admin | Case audit package | `GET /api/cases/{case_id}/audit-package` | Served, not drawn (FE-G3 adds the download to Admin, D7) |
| Admin | Membership | `POST /api/cases/{case_id}/members` | Served; drawn in Report Studio (see above) |
| Admin | Audit rows, bundle integrity, step-up operations | Routes absent in this deployment | Unavailable; requirements only |

Unavailability is observed, not configured: a capability call that answers 404
(or 405 for a POST-only route behind the static catch-all) renders its
"Not available in this deployment." block. A 404 for a run-scoped route is
remembered for that run only, because the same 404 also means an unknown or
unauthorized run.

No mobile control, layout, breakpoint, fixture, snapshot or acceptance target is
part of this implementation. The narrow reflow is solely for desktop browser
zoom at 200%.
