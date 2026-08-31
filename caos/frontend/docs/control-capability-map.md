# Approved design control-to-capability map

This map binds the approved desktop screens to the current production API. It
is intentionally conservative: an absent contract produces an unavailable
state, never a browser-derived substitute.

| Surface | Control or data | Production source | Treatment |
|---|---|---|---|
| Portfolio | Case register and open-credit action | `GET /api/cases` | Served |
| Portfolio | Attention ordering, threshold distance, freshness score | No governed portfolio-summary response | Unavailable; no client ranking |
| Credit | Accepted and latest snapshot identity | `GET /api/cases/{case_id}/snapshot` | Served |
| Credit | Accepted module conclusions and evidence counts | Snapshot artifact ids plus `GET /api/cases/{case_id}/artifacts/{artifact_id}` | Served as exact module output |
| Credit | Normalized binding metric, threshold, tolerance and gap summary | No normalized credit-summary response | Unavailable; no inferred values |
| Sources | List, read and upload source objects | Existing case source routes | Served |
| Sources | Claim-to-source coverage matrix | No normalized claim-map response | Unavailable |
| Analysis | Run stages, live progress, resume and exact artifact output | Existing run, event and artifact routes | Served |
| Review | Accept exact run snapshot and switch visible accepted snapshot | Existing accept and snapshot-switch routes | Served |
| Market | Active loan universe, filters, values and source locators | Existing active-universe route | Served |
| Market | Relative percentile | No deterministic percentile contract | Omitted |
| Model | Build, worksheet, assumptions, preview, scenario and sign-off | Existing model routes | Served with existing guards |
| Model | One-way sensitivity | Route absent in this deployment | Unavailable |
| Report | Draft, autosave, scenario, freeze, filing and export | Existing deliverable routes | Served; client gates global role and server enforces case approver standing |
| Report | Browser recovery copy | Browser `localStorage`, scoped to case and pathway | Served as recovery only; never authority |
| Admin | Audit, membership, export and step-up operations | Routes absent in this deployment | Unavailable; requirements only |

No mobile control, layout, breakpoint, fixture, snapshot or acceptance target is
part of this implementation. The narrow reflow is solely for desktop browser
zoom at 200%.
