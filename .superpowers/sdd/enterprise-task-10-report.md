# Enterprise Task 10 report — opinion ownership, institutional publication, and reconstruction

Executed as `ER-G5` (started 2026-09-03) in
`.claude/worktrees/target-consolidation-checklist-b86b72` on branch
`claude/enterprise-report-signing-filing-e14fb4`, cut from `main` at `eea2b29`
(the Task 9 squash merge, PR #44). Local interpreter: Python 3.14.6 in a
dedicated venv built from the hashed lock (`uv venv --python 3.14
caos/server/.venv314`, `uv pip install --python caos/server/.venv314/bin/python
--require-hashes -r caos/server/requirements-dev.txt`, then a dependency-less
editable install of `caos/server`; no `uv run`, no `uv.lock`). The worktree's
pre-existing `caos/server/.venv` is Python 3.13.15 and was left untouched; every
command below names `.venv314` explicitly (decision D3, DECISIONS §14.15). The
30-document Carnival corpus is present (gitignored). Frontend dependencies were
already installed.

Inputs read before starting: Task 10 of
`docs/superpowers/plans/2026-09-01-enterprise-testing-readiness-execution.md`,
Phase 4 of `ENTERPRISE_READINESS_PLAN.md` (objective, minimum pathway output
contract table, implement items 1–18, verify list, anti-pattern guards),
`ENTERPRISE_TESTING_READINESS.md` ANA-017–020, PUB-001–030, AUD-001–020,
`CONTEXT.md` deliverable and sign-off vocabulary, `docs/DECISIONS.md` §14
(§14.15 authority locking, §14.16–18), `SPEC_RECONCILIATION.md` invariant-5
rows, the deliverables service/store/graph/document/renderers, the API
deliverable routes and wire models, the model service export path, the worker,
the domain store audit table, the model store's append-only trigger pattern,
`identity.py`, the frontend Report Studio, `DeliverableDocument.tsx`,
`documentTypes.ts`, the workbench smoke's Report Studio section, the a11y
script, `DESIGN.md`/`.impeccable.md` paper rules, and the benchmark repository
at commit `e566c1b` (DESIGN.md, ReportDoc.tsx, builders.ts, report_exports.py,
globals.css) via a read-only survey.

## Status

Complete on the branch: every gate in "Commands and results" is green on the
final code (the "full suite, final" row carries its own result), and a draft
pull request to `main` is open (the URL is recorded in
`.superpowers/sdd/progress.md` and at the end of this report). The blind
rubric review, live-model qualification and the PostgreSQL exercise of the
new DDL stay BLOCKED EXTERNAL or open (Open items).

## Design (decided before the first test)

Findings that shaped it:

- Freeze and filing are already digest-bound store CAS transactions
  (`deliverables/service.py::freeze`, `approve_filing`; `storage/deliverables.py::
  file_record`). There is no opinion record anywhere: the frozen payload binds
  the draft revision, model identity, snapshot, source set and methodology, but
  nothing states who owns the opinion or what it is.
- `approve_filing` only checks case standing (`require_case_approver`: current
  global writer role AND stored case APPROVER/ADMIN). The freeze actor or a
  future opinion signer with APPROVER standing can file their own output.
- No route provisions a case member. `MemberRequest` exists in `contracts.py`
  and `DomainStore.add_member` enforces the actor rule (case ADMIN/APPROVER or
  global ADMIN), but the API never exposes it; every test seeds approvers via
  `store.add_member` directly.
- `freeze` renders md, pdf and xlsx **in the API process** with openpyxl and a
  hand-written PDF writer (pango-view for Unicode), then inserts the frozen
  record. `worker.py` states "the API image never renders XLSX", and
  `verify_image_resources.py` forbids LibreOffice in the app image, but the
  deliverable XLSX path contradicts the stated boundary.
- The PDF is a single 10pt Helvetica text column (`render_frozen_pdf`) with no
  masthead, page numbers, tables or hierarchy; Unicode falls to a second path
  (`_unicode_pdf`, 80-column wrap) whose layout differs from the Latin path.
  The XLSX is a flat `Record / Section ID / Title / Content / Authority` dump.
- `audit_events` is a plain table: `_audit` inserts `{id, action, actor, at,
  data}`; nothing prevents UPDATE/DELETE and no digest links rows. The model
  store already has the append-only pattern to copy (`storage/models.py`:
  SQLite `RAISE(ABORT, 'APPEND_ONLY…')` triggers and a plpgsql trigger).
- The wire pins the representative audit key set to exactly
  `{id, actor, at, action, case_id}` (`test_http_contracts_spec.py`), and
  several deliverable tests pin "no audit residue" after refused approvals and
  failed exports, so chain fields must not leak into `audit_trail()` and
  refusals must stay unaudited (they are logged through `observability`).
- The benchmark (`e566c1b`) renders PDFs with reportlab base-14 fonts (no
  Unicode), XLSX with a cover/control sheet, frozen panes, one filtered table,
  `#,##0.00` numerics, formula rejection; its browser composition and fixture
  content are explicitly out of bounds.
- `pango-view` on this machine and in the image supports `--markup`,
  `--background=transparent`, `--rotate`, and, without `--height`, sizes the
  page to the laid-out content (measured: 106 pt for a six-line sample). That
  makes measurement-based pagination and a rotated transparent watermark
  possible with the tool the image already ships, and keeps one Unicode-safe
  PDF path.
- `dev.py`/`run.py` never run worker jobs; model builds and exports already
  require `worker.py`. Moving freeze rendering into the worker therefore
  matches the existing operational model rather than inventing a new one.

Decisions:

1. **Opinion sign-off is an append-only, digest-bound store record.**
   `deliverable_opinions` (new table, append-only triggers) holds, per signing:
   the exact draft revision (`draft_id`, `version`, `digest`), the accepted
   snapshot id, source-set id and version, the digest of the revision's
   `model_identity`, the methodology build id, four BoundaryText fields
   (`opinion`, `limitations`, `material_overrides`, `rationale`; all non-blank —
   "None" is written explicitly), the signer and time, and `opinion_digest`
   over the whole preimage. `sign_opinion` is an expected-head CAS
   (`expected_head_opinion_id`) on the (case, pathway) opinion head and audits
   `deliverable.opinion.signed` in the same transaction (invariant 5, single
   actor → store CAS, not an interrupt). Freeze requires the head opinion to
   bind exactly the revision, snapshot, source set, model identity and
   methodology being frozen (`OPINION_SIGNOFF_REQUIRED` / `OPINION_SIGNOFF_STALE`).
   Editing the draft, changing evidence or model authority, or superseding the
   snapshot therefore invalidates the sign-off by construction.
2. **ANALYST_JUDGMENT cannot carry an uncited quantitative fact.** A
   mechanical rule at draft save: any sentence of an `ANALYST_JUDGMENT`
   narrative that contains a numeric figure (currency, percent, multiple,
   thousands-separated number, or a fiscal-period token) is a documentary claim
   and is refused as `ANALYST_JUDGMENT_UNCITED_FACT` unless the block carries a
   citation or the sentence opens with an explicit judgment framing from a
   closed vocabulary ("We assume", "We estimate", "In our judgment", "We
   expect", "We believe", "Our view", "Assumption:", "Judgment:"). The rule is
   a bound, not natural-language understanding; its ceiling is recorded in the
   code comment.
3. **Approver provisioning is one authenticated mutation.**
   `POST /api/cases/{case_id}/members` (`MemberRequest`) → `store.add_member`
   with the existing actor rule; response is the strict case wire. No admin
   subsystem.
4. **Separation of duties is enforced at the filing CAS.** The filing actor
   must differ from the opinion signer and the freeze actor
   (`APPROVER_NOT_INDEPENDENT`, HTTP 403) in addition to case approver
   standing. The frozen record stores `opinion_id` and `signed_by`.
5. **Freeze becomes a worker job; the frozen record exists only after
   publication and verified reads.** `POST …/freeze` validates everything it
   validates today plus the opinion binding, composes the frozen payload and
   the publication document, and CAS-inserts a `deliverable_freeze_jobs` row
   keyed by the freeze thread identity (idempotent under race and retry;
   `202 FreezeJobResponse`). `worker.py` drains jobs: claim QUEUED→RENDERING,
   render md/pdf/xlsx from the job payload, publish hash-addressed, read every
   export back verified, then in one transaction insert the FROZEN record, park
   the filing thread, audit `deliverable.frozen`, and mark the job PUBLISHED.
   Any failure marks the job FAILED with a typed code and audits
   `deliverable.freeze_failed`; no frozen record exists. Startup recovery
   requeues RENDERING jobs under the worker's single-instance lock (renders are
   deterministic and publication is idempotent). A re-render for an identity
   that already has a frozen record with a different approval digest is
   `DELIVERABLE_FREEZE_CONFLICT`. XLSX rendering therefore lives only in the
   worker process; the API renders nothing.
6. **One publication document feeds four renderers.** At freeze the server
   builds `payload.publication`: masthead (issuer, report type, as-of date,
   run/version identifiers, authority, approval state `PENDING APPROVAL`,
   opinion owner), the opinion as the first Decision-page sections, the
   pathway's canonical `document_sections` grouped by page, an
   Evidence & QA Control Sheet page (source register with dispositions and
   digests, evidence inventory, limitations, model identity, machine
   assistance, approval state, digests), and disclosures. Sections reuse the
   `CanonicalDocumentSection` schema so the browser renderer already draws them.
   Markdown, PDF and XLSX walk `payload.publication` only; a parity test
   extracts headings, numbers, citations, origin labels, limitations, model
   identity and opinion from all three and compares them.
7. **PDF: pango-view everywhere, laid out by measurement.** One Unicode-safe
   path. Each page is a Pango-markup document (masthead, sections with sized
   bold headings, monospace tabular numerics right-aligned by padding, rules,
   footer with page numbers); pagination measures candidate pages by rendering
   them unconstrained and reading the mediabox height, moving overflowing
   elements to the next page and repeating table headers across the split. A
   rotated transparent `PENDING APPROVAL` (or `CHANGES REQUESTED`) watermark is
   rendered once and merged under the content with pypdf. Bytes are
   deterministic (`SOURCE_DATE_EPOCH=0`, no clock reads).
8. **XLSX: worker-rendered openpyxl workbook** with Cover & Control, Report,
   Opinion, Model, Evidence Register, Source Audit, Gaps & Limitations sheets;
   bold frozen header rows, auto-filters on register/audit sheets, typed numeric
   cells with `#,##0.00;[Red](#,##0.00);-` where the origin is MODEL, formula
   prefixes neutralised, no formulas, the existing deterministic zip re-pack.
9. **Filing receipt is a detached immutable record.** `file_record` inserts a
   `deliverable_filing_receipts` row (append-only) in the filing transaction:
   approver, time, opinion id and signer, frozen approval digest, input
   fingerprint, export digests, approval hash, `receipt_digest`. Served by
   `GET …/by-id/{id}/receipt` (`FilingReceiptResponse`, strict JSON). The
   approved bytes are never touched; export media types are unchanged
   (`application/octet-stream`), so no gzip or response-model change is needed.
10. **Audit is append-only with a head-locked hash chain.** `audit_events`
    gains `prev_digest` and `digest`; `seq` is assigned explicitly as
    `head.seq + 1` under a row lock on a one-row `audit_head` table (Postgres
    `SELECT … FOR UPDATE`; SQLite acquires the writer lock with an `UPDATE` of
    the head row before reading it), so links are contiguous and forks are
    impossible; `UNIQUE(prev_digest)` is the belt-and-braces. UPDATE/DELETE
    triggers refuse mutation on both dialects. Existing rows are backfilled
    once (renumbered contiguously, chained) before the triggers are created.
    `audit_trail()` output is unchanged; `audit_chain()` serves the chain to
    the package and the verifier. Typed refusals stay unaudited (existing spec
    pins "no residue"); successful downloads audit `deliverable.exported`.
11. **Audit package and offline verifier.** `caos/audit/package.py` builds a
    case-scoped zip: manifest with per-file digests, case/sources (metadata,
    block ids and digests, never block text), source sets, intakes
    (dispositions), runs with nodes, events, snapshots and validated artifacts,
    provider identities, model builds and revisions, deliverable revisions,
    opinions, frozen records, receipts, filed export bytes, the audit chain and
    head, methodology and runtime identity. `GET /api/cases/{case_id}/audit-package`
    serves it (binary, OpenAPI-exempt like the other downloads).
    `caos/server/caos/audit/verify_package.py` is a single-file, stdlib-only
    script: it recomputes every manifest digest, the audit chain, the frozen
    payload and approval digests, the receipt digest and its cross-references,
    signer ≠ filer, export digests against the packaged bytes, and
    re-renders the Markdown export from the frozen payload with an inline copy
    of the Markdown renderer whose byte-equality with the application renderer
    is pinned by a test.
12. **Goldens** for normal, dense, long-text, multilingual, held and filed
    states under `caos/tests/fixtures/deliverables/publication/`: exact
    Markdown bytes, an XLSX cell dump, and a PDF structural expectation
    (headings in order, every table value present, page count ≥ 1; PDF text
    wrapping is font-metric dependent and is not byte-goldened).

## Delivered

Server (all under `caos/server/caos/`):

- `audit/chain.py` (new): the per-case hash chain algorithm (`event_digest`,
  `verify_chain`, `GENESIS`, `GLOBAL_CHAIN`), standard library only.
- `storage/store.py`: `audit_events` gains `chain_key`, `chain_seq`,
  `prev_digest`, `digest` and a unique `(chain_key, chain_seq)` index;
  `audit_chain_heads` (one row per chain plus the `__lock__` row); `_audit`
  locks the head row, assigns `chain_seq = head + 1`, digests the row over its
  predecessor and moves the head in the caller's transaction; UPDATE/DELETE
  triggers on both dialects; `_ensure_audit_schema` migrates and backfills a
  legacy table once; `audit_chain`, `audit_chain_head`, `verify_audit_chain`,
  `disarm_audit_triggers_for_tests`; `audit_trail` unchanged.
- `contracts.py`: `SignOpinionRequest` (four required BoundaryText
  statements, expected-head CAS field).
- `storage/deliverables.py`: `deliverable_opinions`,
  `deliverable_freeze_jobs`, `deliverable_filing_receipts` (the first and last
  append-only by trigger); `deliverable_frozen` gains `opinion_id` and
  `signed_by`; opinion head/history/sign CAS; freeze-job request (idempotent
  by thread identity, FAILED requeues), claim CAS, fail, recover, and
  `publish_frozen` (frozen record + parked thread + audit + job PUBLISHED in
  one transaction, divergent digest → `DELIVERABLE_FREEZE_CONFLICT`);
  `file_record` writes the receipt in the filing transaction and audits its
  digest; `OpinionHeadConflict`.
- `deliverables/service.py`: `_validate_judgment_facts`
  (`ANALYST_JUDGMENT_UNCITED_FACT`), `sign_opinion`, `opinion_state`,
  `_opinion_staleness`, `_require_current_opinion`; `freeze` validates as
  before plus the opinion binding, composes `payload.opinion` and
  `payload.publication`, and queues the job; `run_pending_freezes`,
  `_publish_freeze_job` (render → publish → verified read → record),
  `recover_freeze_jobs`, `freeze_job`, `frozen_record_for_job`,
  `rerender_freeze_job_for_tests`; `approve_filing` refuses
  `APPROVER_NOT_INDEPENDENT`; `filing_receipt`, `record_export_download`,
  `filing_receipts_for_tests`.
- `publishing/document.py` (new): `build_publication` — masthead, opinion-first
  pages, canonical sections, Evidence & QA Control Sheet (control status,
  source document register with dispositions, registered evidence inventory,
  limitations and open QA, content origin), disclosures.
- `publishing/markdown.py` (new, stdlib-only, copied verbatim into the
  verifier) and `publishing/renderers.py` (rewritten): one
  `publication_view`; Markdown; PDF via pango-view markup with measured,
  estimate-first pagination, repeated table headers, record layout for wide
  tables, pinned footer with page numbers, white paper layer and a
  transparent rotated `PENDING APPROVAL` watermark, ASCII separators in
  monospace lines; XLSX with Cover & Control, Report, one typed and filtered
  sheet per table, Revision Record, formula rejection, deterministic zip.
- `audit/package.py` (new): `build_case_package`; `audit/verify_package.py`
  (new): the stdlib-only offline verifier.
- `api/__init__.py`: `POST /api/cases/{case_id}/members`,
  `POST …/deliverables/{pathway}/opinion`, `POST …/freeze` → 202
  `FreezeJobResponse`, `GET …/deliverables/freeze-jobs/{job_id}`,
  `GET …/by-id/{deliverable_id}/receipt`, `GET /api/cases/{case_id}/audit-package`;
  the workspace serves `opinion` and `pending_freezes`; served downloads audit
  `deliverable.exported`; superseded-but-filed records stay downloadable;
  `NOT_INDEPENDENT` → 403, `SIGNOFF` → 409.
- `responses.py`: `OpinionBindingResponse`, `OpinionResponse`,
  `OpinionStateResponse`, `FreezeJobResponse`, `FilingReceiptResponse`;
  `DeliverableWorkspaceResponse` and `FrozenDeliverableResponse` extended;
  `AuditEventResponse` gains `opinion_id` and `format`.
- `worker.py`: drains freeze jobs after builds and exports; requeues
  RENDERING jobs at start under the single-instance lock.
- `run_sec_audit.py`: body probes for the two new POST routes (the audit
  itself caught the first draft of the members route escalating a stored
  reader; fixed to require stored approver/admin standing).

Frontend (`caos/frontend/`):

- `src/components/report/reportStudioState.ts`: fifth checklist item
  (opinion sign-off), `freezeJobIsPending`, `canFileFrozen`.
- `src/components/report/DeliverableDocument.tsx`: draws
  `payload.publication` for frozen and filed records (masthead facts, page
  bands, watermark, approval state) and the draft's canonical sections
  otherwise; `Publication` and `FrozenOpinion` types.
- `src/components/report/ReportStudio.tsx`: opinion sign-off form with
  expected-head CAS, freeze → job → polling → server-served frozen record,
  pending/failed freeze status, separation-of-duties gate on File
  (`canFileFrozen(role, subject, …)`), filing receipt display, approver
  provisioning form for case approvers/admins.
- `src/components/Workspace.tsx` passes the identity subject;
  `src/lib/workbench.ts` types `members` on the case record;
  `app/globals.css` adds the sign-off form, watermark, page band and masthead
  fact styles and the `--caos-paper-watermark` token.
- `scripts/workbench-smoke.mjs`: fixtures and journey for sign-off, the 202
  job and its publication, separation of duties, the filing receipt.
- Unit tests updated (`ReportStudio.test.ts`, `reportStudioState.test.ts`).

Tests: `caos/tests/spec/test_audit_chain_spec.py` (11),
`test_publication_spec.py` (30), `test_audit_package_spec.py` (10),
`test_publication_goldens_spec.py` (7) and the goldens under
`caos/tests/fixtures/deliverables/publication/`; the existing deliverable,
research, Distressed and audit-regression tests moved to the sign-then-freeze
flow through shared helpers (`sign_min`, `freeze_now`).

Docs: `docs/DECISIONS.md` §14.19, `CLAUDE.md` (publication model, four new
known gaps), `SPEC_RECONCILIATION.md` invariant-5 row, six
`docs/QUALITY_LEDGER.csv` rows (F-DELIV-13..16, F-AUD-01..02) and the
coverage file map, `.claude/launch.json` `caos-gates` (host-control server on
8766 with a fresh data directory for the browser gates).

Phase 4 verify items → retained tests:

| Verify item | Test |
| --- | --- |
| Machine interpretation, fact, calculation, judgment, assumption, limitation distinguishable in storage, API, UI, exports | origin labels in every format: `test_publication_goldens_spec.py::test_every_format_carries_the_same_facts_and_matches_its_golden`; `ANALYST_JUDGMENT_UNCITED_FACT`: `test_publication_spec.py::test_analyst_judgment_cannot_carry_an_uncited_quantitative_fact` |
| Stale or mismatched sign-off cannot freeze | `test_freeze_requires_a_current_opinion_and_refuses_a_stale_one`, `test_superseded_upstream_authority_invalidates_the_signoff` |
| Signer cannot approve/file | `test_the_opinion_signer_and_the_freeze_actor_cannot_file_their_own_output` |
| Distinct approver provisioned without DB seeding | `test_approver_is_provisioned_through_the_members_route_without_database_seeding` |
| Exactly one concurrent filer wins, loser typed | `test_concurrent_filers_yield_one_receipt_and_one_typed_loser` (+ the existing `test_deliverables_spec.py::test_concurrent_filers_yield_exactly_one_filed_with_payload_equal_to_frozen`) |
| Filed downloads equal approved bytes, fail on tamper | `test_filed_download_is_audited_and_tampering_is_detected_on_download`, existing `test_filed_exports_are_byte_exact_sha_verified_and_never_rerendered` |
| Approver verifies in the detached receipt, bytes unchanged | `test_filing_writes_an_immutable_detached_receipt_and_leaves_the_approved_bytes_untouched` |
| Every pathway: decision report, model appendix/workbook, Evidence & QA Control Sheet from one frozen payload | `test_deliverables_spec.py::test_each_pathway_frozen_payload_renders_substantive_md_pdf_xlsx` (six pathways, control sheets in every format) |
| Browser, Markdown, PDF, XLSX semantically equivalent; no filler, truncation, missing glyphs | goldens spec (six states incl. long-text and multilingual) |
| One numeric/null/estimate convention | `Unavailable` convention pinned in the Content Origin profile and the goldens; typed numerics `test_xlsx_export_neutralizes_formula_text_and_preserves_typed_model_values` |
| Visual regression and blind rubric review | goldens + this report's inspection record; blind review BLOCKED EXTERNAL |
| Editing any bound authority invalidates downstream sign-off/approval | opinion staleness tests above; existing `FROZEN_AUTHORITY_STALE` / `FROZEN_MODEL_AUTHORITY_STALE` tests |
| Audit insertion, update, deletion, reordering detected | `test_audit_chain_spec.py::test_tampering_under_disarmed_triggers_is_detected[…]`, `::test_audit_rows_refuse_update_and_delete_at_the_database_boundary` |
| Offline verifier reconstructs sampled claims and bytes | `test_audit_package_spec.py::test_package_is_case_authorized_audited_and_offline_verifiable_in_a_clean_directory`, `::test_offline_verifier_convicts_every_tamper_class[…]` |
| Package holds no secret, hidden reasoning, unauthorized source, provider error body | `::test_package_holds_no_source_text_vault_path_secret_or_provider_body` |
| Independent analyst and auditor can follow the result | the package README plus the verifier's human summary; the blind review is the external half |

Inspection record (every affected PDF page and XLSX sheet): the six golden
states were rendered to `scratchpad/goldens/` (54 PDF pages rasterised with
`sips`; normal 3 pages, dense 8, long-text 33, multilingual 4, held 3, filed
3) and inspected page by page in this session: masthead, opinion-first
decision page, title-case section headings with origin labels, monospace
grids with right-aligned numerics and repeated headers across the split
(dense p.3), record layout for the seven-column source register with whole
digests (normal p.3), CJK/Greek/Turkish/ligature glyphs (multilingual p.1),
pinned footer with page numbers, transparent watermark on every page, no
orphan headings, no clipping. Defects found and fixed during inspection:
letter-spacing broke text extraction (removed); a transparent page
background rasterised black in thumbnailers (white paper layer added); the
64-character deliverable id wrapped the masthead line (short id in running
lines, full id in the Control Status and Revision Record); the estimate-first
packer stranded a heading at a page foot (keep-with-next carry); a table
continuation lost its header (repeat at page finalisation); "Disposition"
wrapped mid-word (record layout for wide tables, header-word floors); the
content page was anchored at the page bottom and overprinted the footer
(anchored to the top, footer as its own layer). XLSX sheets inspected via
`openpyxl` dumps: Cover & Control, Report, one sheet per table (frozen header
row, auto-filter, typed model numerics with `#,##0.00;[Red](#,##0.00);0.00`),
Evidence Register, Source Document Register, Registered Evidence Inventory,
Revision Record; no formulas anywhere.

## Assumptions stated

- "Held" means a frozen record on which changes were requested
  (`CHANGES_REQUESTED`): its bytes are the frozen bytes, unchanged, and the
  golden pins that. A frozen-and-waiting record is the "normal" state.
- The blind rubric review cannot be run in a repository session; its inputs
  are the six golden states and the `scratchpad/goldens/` renders, and its
  result is BLOCKED EXTERNAL.
- The judgment-fact rule is a regex bound (figures, currencies, percentages,
  multiples, basis points, years and fiscal-period tokens; framing phrases
  "We assume/estimate/expect/believe/judge/think/project/forecast", "In our
  judgment/view/opinion/estimate", "Our view/estimate/assumption/judgment",
  "Assumption:", "Judgment:", "Estimate:"); it is documented as a bound in the
  code and in §14.19.
- Typed refusals stay unaudited because existing specs pin "no audit residue"
  after refused approvals and failed downloads; they are logged.
- The export route's media types are left as `application/octet-stream` by
  the task's own constraint; the audit package is `application/zip`.
- Earnings Update and Covenant & Refinancing deliverables keep binding the
  prior Full Credit base build (§14.18); rendering their pathway effects in
  the published deliverable needs a model-authority change pinned by existing
  tests and is recorded as an open item rather than done quietly.
- Local development needs `python caos/server/worker.py` beside `dev.py` for
  a freeze to complete; the browser gates use route fixtures for the
  deliverable surface, as before, so they do not need a worker.

## Commands and results

Every line below is a command run in this session with its verbatim summary.

| When | Command | Result |
| --- | --- | --- |
| baseline, before any change | `uv venv --python 3.14 caos/server/.venv314 && uv pip install --python caos/server/.venv314/bin/python --require-hashes -r caos/server/requirements-dev.txt && uv pip install --python caos/server/.venv314/bin/python --no-deps -e caos/server` | exit 0; `Python 3.14.6` |
| baseline, before any change | `caos/server/.venv314/bin/python -m pytest caos/tests -q -p no:cacheprovider -x --deselect caos/tests/test_corpus_pathways.py` | `1005 passed, 2 skipped, 26 deselected, 1 warning in 938.49s (0:15:38)` (the one warning is Starlette's third-party `TestClient` deprecation) |
| after the audit chain | `caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_audit_chain_spec.py -q -p no:cacheprovider` | `11 passed in 0.83s` |
| after the audit chain | `… -m pytest caos/tests/test_store.py caos/tests/test_audit_regressions.py caos/tests/test_source_ingestion.py caos/tests/spec/test_http_contracts_spec.py caos/tests/spec/test_intake_spec.py -q` | `163 passed, 1 warning in 20.24s` |
| after the sign-off, jobs, receipt and renderers | `… -m pytest caos/tests/spec/test_deliverables_spec.py caos/tests/spec/test_publication_spec.py caos/tests/spec/test_audit_chain_spec.py -q` | `134 passed, 1 warning in 447.19s (0:07:27)` |
| after the layout changes | `… -m pytest caos/tests/spec/test_deliverables_spec.py caos/tests/spec/test_publication_spec.py caos/tests/spec/test_audit_package_spec.py -q` | `133 passed, 1 warning in 318.15s (0:05:18)` |
| research, Distressed, audit regressions, worker | `… -m pytest caos/tests/spec/test_research_spec.py caos/tests/spec/test_ordinary_distressed_e2e.py caos/tests/test_audit_regressions.py caos/tests/test_worker.py -q` | `31 passed, 1 warning in 181.08s` |
| source-complete spec in isolation | `… -m pytest caos/tests/spec/test_source_complete_modelling_spec.py -q` | `27 passed, 1 warning in 125.96s` (an earlier mixed run with `test_worker.py` in the same session showed 18 order-dependent `AGENT_EXECUTION_DISABLED` failures in this file; it is green alone and in the baseline order — see Confidence review) |
| audit package and verifier | `… -m pytest caos/tests/spec/test_audit_package_spec.py -q` | `10 passed, 1 warning in 19.57s` |
| cross-format goldens | `… -m pytest caos/tests/spec/test_publication_goldens_spec.py -q` (first with `CAOS_REGENERATE_GOLDENS=1` after the inspection) | `7 passed in 42.89s` |
| full suite, first run | `caos/server/.venv314/bin/python -m pytest caos/tests -q -p no:cacheprovider` (corpus smoke subset included; documents present) | `4 failed, 1092 passed, 2 skipped, 1 warning in 1340.49s (0:22:20)` — the four failures were the worker-entrypoint tests in `test_single_instance.py` (`'Store' object has no attribute 'engine'`): `worker.main` now constructs the deliverable service and passes it to `run_pending`, and those tests stub the store and the poll with one-argument fakes. Fixed by stubbing `worker.DeliverableService` and widening the poll stubs in the three affected tests; `test_single_instance.py` + `test_worker.py` then `50 passed, 2 skipped in 8.59s` |
| corpus host control | `CORPUS_FULL=1 caos/server/.venv314/bin/python -m pytest caos/tests/test_corpus_pathways.py -q -p no:cacheprovider` (orchestration proof only, scripted provider; never live qualification) | `34 passed, 1 warning in 208.78s (0:03:28)` |
| full suite, final | `caos/server/.venv314/bin/python -m pytest caos/tests -q -p no:cacheprovider` on the final code | `1096 passed, 2 skipped, 1 warning in 1344.24s (0:22:24)` (the two skips are the PostgreSQL tests; the warning is Starlette's `TestClient` deprecation) |
| lint | `caos/server/.venv314/bin/python -m ruff check --config ruff.toml caos/server caos/tests --exclude caos/server/caos/methodology/vendor` | `All checks passed!` |
| security audit | `caos/server/.venv314/bin/python run_sec_audit.py` | first run: `FAIL POST /api/cases/{case_id}/members: stored reader write -> 201 (expected 403)` (a real escalation in the first draft of the route, fixed by requiring stored approver/admin standing); then `{'audited_routes': 59, 'case_boundary_routes': 48, 'failures': 0}` |
| quality ledger | `caos/server/.venv314/bin/python docs/quality_ledger_coverage.py` | `routes checked: 54   product files: 250   features: 128` / `the ledger documents every route and every product file` |
| frontend | `npx tsc --noEmit` · `npm run lint` · `npm run test:unit` · `npm run build` (from `caos/frontend`) | tsc clean; lint clean; `tests 123 pass 123 fail 0`; build exit 0 |
| accessibility, final | same command on the final build against a recycled fresh-data `caos-gates` server (the smoke had populated the first one) | `{"routes":9,"viewports":6,"combinations":70,"pendingPlanFixture":true,"readyModelFixture":true,"readyReportFixture":true,"modelBuilderAxeChecks":12,"modelBuilderKeyboardTabChecks":3,"reportStudioAxeChecks":3,"reportStudioKeyboardTabChecks":3,"violations":0}` |
| workbench smoke | `CAOS_URL=http://127.0.0.1:8766 npm run test:workbench` against the same server (the Report Studio journey now signs the opinion, watches the 202 freeze job publish, proves the signer sees no File control, files as a third subject and reads the receipt) | exit 0; `{"timing":{"domContentLoaded":48.1,"firstContentfulPaint":120},"caseRequests":1}` |
| anti-vacuity mutations (each reverted from a byte copy) | M1 drop the `APPROVER_NOT_INDEPENDENT` check → `test_the_opinion_signer_and_the_freeze_actor_cannot_file_their_own_output`; M2 freeze ignores a stale sign-off → `test_freeze_requires_a_current_opinion_and_refuses_a_stale_one` (`DID NOT RAISE`); M3 chain link not verified → `test_tampering_under_disarmed_triggers_is_detected[delete]`; M4 a failed render is replaced by placeholder bytes → `test_a_rendering_failure_leaves_a_typed_failed_job_and_no_frozen_record` (`'PUBLISHED' == 'FAILED'`); M5 receipt names a constant approver → `test_filing_writes_an_immutable_detached_receipt_and_leaves_the_approved_bytes_untouched` | every mutation: `1 failed` |
| accessibility | `CAOS_URL=http://127.0.0.1:8766 npm run a11y` against the `caos-gates` host-control server (fresh data dir) | first run failed on the Report Studio fixture (`Deliverable paper preview` never rendered: the fixture workspace lacked the two new fields and the studio dereferenced them; both fixed); then `{"routes":9,"viewports":6,"combinations":70,…,"violations":0}` |

## Confidence review

Each doubt below was investigated to its cause in this session; the verdict
is what the evidence supports, nothing more.

1. **Could a stored reader or analyst mint an approver?** Yes, in the first
   draft: `run_sec_audit.py` reported `POST /api/cases/{case_id}/members:
   stored reader write -> 201`, because `store.add_member` accepts a current
   global ADMIN regardless of case standing. Fixed: the route now goes through
   `require_case_approver` (stored APPROVER/ADMIN standing AND a current
   global writer role) and passes `actor_role=None` to the store; the audit is
   back to `failures: 0` and the spec covers analyst 403, reader 403,
   outsider 404, invalid role 422. The frontend gate mirrors the rule from the
   case's `members` map.
2. **Is the audit chain vacuous?** No: M3 (skip the link check) turns the
   deletion test red; the update/delete triggers are asserted through raw
   SQLAlchemy statements; a rolled-back governed write leaves no gap; twelve
   concurrent writers never fork. Not exercised: the PostgreSQL branch
   (`SELECT … FOR UPDATE`, plpgsql trigger, `ADD COLUMN IF NOT EXISTS`) — the
   emitted DDL is pinned by reading, not by a live PostgreSQL, like the
   source-set lock before it. Ceiling recorded in `CLAUDE.md`: no external
   anchor beyond a retained package's head.
3. **Does freeze ever leave a frozen record on a render failure?** M4 (swap a
   crashed render for placeholder bytes) turns the failure test red, so the
   test really depends on the worker writing the record only after every
   export exists; `publish_frozen` is one transaction; the conflict path
   raises inside it so the job stays RENDERING and is finalised FAILED by the
   pass. The vault does keep any exports published before a later format
   crashed (hash-addressed files are inert without a record); a retry reuses
   them by digest.
4. **Is the sign-off binding real?** M2 (ignore staleness) fails `DID NOT
   RAISE`; the composition check fires first when the snapshot is superseded,
   which is why that test accepts either typed code. The model-identity part
   of the binding compares the digest pinned in the revision content; a model
   that moves after the sign-off without a new draft save is caught by the
   freeze's own model re-resolution (`MODEL_REVISION_STALE`), not by the
   opinion binding, and both are refusals.
5. **Separation of duties**: M1 turns the HTTP 403 test red; M5 turns the
   receipt test red. Request-changes deliberately keeps the existing approver
   rule (it is not an approval); noted, not changed.
6. **The judgment-fact rule**: it is a bound. It refuses figures, currencies,
   percentages, multiples, basis points, years and period tokens in an uncited
   `ANALYST_JUDGMENT` narrative unless the sentence opens with a framing
   phrase; it does not understand prose. Two existing tests and one smoke
   fixture had to add a citation or a framing, which is the rule working.
   `LIMITATIONS` blocks are exempt on purpose (a limitation is not a
   documentary claim).
7. **PDF fidelity**: eight defects were found by inspecting the renders and
   fixed (tracking, transparent background, wrapped masthead, orphan heading,
   lost table header, mid-word wrap, content anchored at the page bottom,
   masthead line wrap). Remaining known limits: fonts come from the host
   (`fonts-noto-cjk` in the image; Homebrew fonts here), so a script no
   installed font covers would draw notdef boxes — the multilingual golden
   asserts CJK, Greek, Turkish and ligatures extract intact in this
   environment and CI installs the same font package; a filed PDF is 90–150 KB
   per page; decimal alignment is right-alignment, not decimal-point
   alignment.
8. **Suite time**: the deliverable spec files now take about seven minutes
   because every freeze renders a real PDF through pango-view (2–10 s). Kept:
   the constraint is that the frozen record exists only after real exports,
   and a stub renderer would make the publication tests vacuous; the
   `renderer_for_tests` seam remains for tests that need speed.
9. **Order-dependent failures seen once**: a mixed invocation that ran
   `test_worker.py` before `test_source_complete_modelling_spec.py` showed 18
   `AGENT_EXECUTION_DISABLED` failures in the latter; alone and in the
   suite's own collection order (spec/ before the root files) the file is
   green (27 passed) and the full suite below is the authority. Not
   attributed to this change and not fixed here; recorded as a follow-up.
10. **Wire strictness**: every new JSON success serves a named strict model;
    the audit-package and export routes are the OpenAPI-exempt binaries; the
    contract spec's audit-action enumeration carries the five new actions and
    `AuditEventResponse` the two new optional keys. `test_representative_response_payloads_preserve_exact_key_sets`
    still pins the audit family to `{id, actor, at, action, case_id}` because
    chain fields never reach `audit_trail()`.
11. **Frontend robustness**: the first accessibility run failed because the
    a11y fixture predates the two new workspace fields and the studio
    dereferenced them; both were fixed, and the studio now tolerates a
    workspace without them (a server predating the field shows "no signed
    opinion"). The lifecycle stays held while the worker renders so a
    concurrent action cannot orphan the poll; a record filed before receipts
    existed reads as "no receipt", not as an error.
12. **What was not built, on purpose**: overlay-bound deliverables for
    Earnings Update and Covenant & Refinancing (model-authority change pinned
    by existing tests; §14.19 and `CLAUDE.md` record it); export media types;
    a general administration surface; a PostgreSQL run of the new DDL; the
    blind rubric review (external).

## Open items

- **Blind rubric review** by two credit analysts and one external-stakeholder
  reviewer: BLOCKED EXTERNAL (candidate-only work, run once on the frozen
  Phase 7 candidate). Inputs prepared: the six golden states under
  `caos/tests/fixtures/deliverables/publication/` (normal, dense, long-text,
  multilingual, held, filed) and the rendering recipe in
  `test_publication_goldens_spec.py::_build`, which produces the same PDF,
  XLSX and Markdown for any reviewer; the rubric criteria are Phase 4 item 13
  (hierarchy, legibility, print fidelity, evidence clarity, decision
  usefulness) against the `e566c1b` benchmark. Owner: the decision owner
  names the reviewers; artifact needed: their scored rubric; where it goes:
  this report and `.superpowers/sdd/progress.md`.
- **Live-model qualification** of any published opinion: BLOCKED EXTERNAL
  (Task 11's matrix).
- **Overlay-bound deliverables for Earnings Update and Covenant &
  Refinancing** (their pathway effects in the published deliverable, not only
  in the overlay build and model export): a model-authority change under
  `models/service.py::validated_publication_build` and
  `deliverables/service.py::_validate_pathway_authority`, pinned by
  `test_live_incremental_pathway_publishes_against_a_validated_prior_full_credit_model`;
  recorded in §14.19 and `CLAUDE.md`; needs the decision owner's call.
- **PostgreSQL exercise** of the new DDL (`audit_chain_heads` lock,
  append-only triggers on `audit_events`, `deliverable_opinions`,
  `deliverable_filing_receipts`, `ADD COLUMN IF NOT EXISTS` migrations): Task
  12's PostgreSQL simulations are the place.
- **Order-dependent failures** in `test_source_complete_modelling_spec.py`
  when `test_worker.py` runs before it in one invocation (18
  `AGENT_EXECUTION_DISABLED` failures; green alone and in collection order):
  not attributed, not fixed here.
- **CI browser job**: `workbench-smoke.mjs:1251` (focus return after a
  cancelled browser-history traversal in the model editor) times out in CI
  on this branch, twice, while passing locally and on `main`'s CI. The step
  is not touched by this branch; the instrumented failure message on the next
  run is the next input. Not attributed yet.
- **Scripts beyond DejaVu's coverage** (CJK, Arabic, Indic) are shaped by the
  host's fallback fonts; pagination is pinned by absolute line heights but
  glyph shapes follow the host (`fonts-noto-cjk` in the image). Vendoring a
  CJK face is the upgrade path if those scripts become routine.
- **Export media types** remain `application/octet-stream` (wire-visible;
  unchanged by the task's own constraint).
- **PDF cost**: 90–150 KB per page and 2–10 s per freeze in the worker; a
  single multi-page pango render or shared font subsets would cut both.
- Frontend follow-ups: the populated-page `<aside>` nesting noted in Task 9
  is unchanged; the deliverable smoke and the a11y fixture mock the
  deliverable routes, so a live freeze journey through a running worker is
  not part of the browser gates.

## CI follow-up (2026-09-03): the font pin and the paragraph split

The first CI run of the draft PR (run 33704148181) failed three server tests
on both interpreters and the browser job.

**What failed and why.**
`test_publication_goldens_spec[dense]` and `[multilingual]` reported 8 and 4
PDF pages against goldens of 7 and 3, and
`test_frozen_pdf_is_structurally_complete_under_optimized_python` could not
find `Pinned narrative body.` because the PDF extracted as `body .`. The
renderer asked pango-view for `sans` and `monospace` and each host answered
differently: Verdana and Andale Mono on the developer Mac (where the goldens
were generated), DejaVu on Ubuntu, and Noto CJK's Latin glyphs in the image,
which installs no DejaVu at all. One frozen payload therefore had three
renderings, and the goldens pinned the Mac's. Regenerating them in CI would
have been exactly the silent drift the test forbids; the fix is a font pin.

**The pin.** `caos/server/caos/publishing/fonts/` now vendors DejaVu Sans and
DejaVu Sans Mono (regular and bold, release 2.37, 2.1 MB, Bitstream Vera
licence in `fonts/LICENSE`). `renderers.FONT_BUNDLE` holds their SHA-256
digests; `_font_environment` verifies the bytes before a render and refuses
with `PDF_FONT_BUNDLE_INVALID`, writes a hermetic `fonts.conf` into the render
workspace (the bundle directory first, the host's fontconfig after it for
scripts the bundle lacks, Debian's DejaVu package rejected by path), and sets
`PANGOCAIRO_BACKEND=fontconfig` because Homebrew pango on macOS otherwise
answers font requests through CoreText and ignores fontconfig entirely — the
first hermetic experiment rendered Helvetica until that variable was set.
Every pango-view call now runs `--hinting=none --hint-metrics=off
--subpixel-positions`: unhinted design advances are identical on every host,
and subpixel positioning is what turned `body .` back into `body.` (the
kerned pair `y.` was being rounded into a gap that pypdf read as a space;
kerning off would also have fixed it, at the cost of the kerning). Every span
carries an absolute `line_height` (1.2 × size, in Pango units), so a
fallback face — Noto CJK in the image, Hiragino on the Mac — never moves a
page break; multilingual paginates identically on both. Masthead metadata is
wrapped at spaces before pango sees it (`_meta_lines`), because pango's
word-char wrapping split a build id at its hyphen and the raw hex leaked past
the golden's identifier normalisation. The renderer version is
`caos.deliverable-renderer.v3`. `pyproject.toml` declares the bundle as
package data.

**The paragraph split, found by the inspection.** Rasterising every page of
the regenerated long-text state showed the narrative overprinting the footer
and running off the page, followed by blank and heading-only pages. The Task
10 renderer handed each paragraph to pango as one line, so the paginator —
which divides an overflowing block by its lines — had nothing to divide, and
its split step also took the first carried block (the heading) instead of the
one that overflowed. The committed 33-page golden was that broken render;
the whole-narrative assertion passed because pypdf extracts glyphs drawn
below the page edge. Both are fixed: `_prose_lines` pre-wraps paragraphs and
bullets at 94 columns (main's renderer did the same; the rewrite dropped
it), and the split step keeps the keep-with-next chain, bisects the
overflowing block to the largest prefix that measures in, and breaks out when
a block is indivisible. The long-text golden test now bounds every page to
between 400 and 8,000 extracted characters, which an overprinted, blank or
heading-only page cannot satisfy.

**The browser job.** `workbench-smoke.mjs:1251` timed out waiting for focus
to return to the dirty model editor after a cancelled browser-history
traversal — on both the original run and a re-run, while the same smoke
passes locally against a fresh `caos-gates` server and passed in CI on
`main`. The step is unchanged by this branch and precedes the Report Studio
journey. The failing wait now reports the active element, any open dialog,
the URL and the history state instead of a bare timeout, so the next CI run
says which restoration path ran; the cause is open below.

**Tests added.** `test_pdf_glyphs_come_from_the_vendored_font_bundle_alone`
(every embedded font is one of the four vendored faces and the kerned
sentence extracts exactly) and
`test_a_font_bundle_that_fails_verification_refuses_to_render`, both in
`test_publication_spec.py`; the long-text per-page bound in the goldens spec.

**Inspection and results.** Every page of every regenerated state was
rasterised and inspected (see the table below for the counts); every XLSX
sheet was listed and its only change is the renderer version on the cover.

| Gate | Command | Result |
| --- | --- | --- |
| cross-format goldens, regenerated | `CAOS_REGENERATE_GOLDENS=1 caos/server/.venv314/bin/python -m pytest caos/tests/spec/test_publication_goldens_spec.py -q -p no:cacheprovider` | `7 passed in 56.09s`; PDF pages normal 3, dense 8, long_text 39, multilingual 4, held 3, filed 3 (dense and multilingual now equal what CI rendered; long_text was 33 broken pages); every page rasterised with `sips` and read (60 pages); every XLSX sheet listed, the only cell change is `Renderer caos.deliverable-renderer.v3` on the cover |
| font-pin tests | `… -m pytest caos/tests/spec/test_publication_spec.py -k font_bundle -q` | `2 passed in 0.42s` |
| full suite | `caos/server/.venv314/bin/python -m pytest caos/tests -q -p no:cacheprovider -W always` | `1098 passed, 2 skipped, 217 warnings in 1343.64s (0:22:23)` (two more tests than the final Task 10 run; `-W always` surfaces the ResourceWarnings CI also lists) |
| lint | `… -m ruff check --config ruff.toml caos/server caos/tests --exclude caos/server/caos/methodology/vendor` | `All checks passed!` |
| security audit | `… run_sec_audit.py` | `{'audited_routes': 59, 'case_boundary_routes': 48, 'failures': 0}` |
| quality ledger | `… docs/quality_ledger_coverage.py` | `routes checked: 54   product files: 278   features: 128` / `the ledger documents every route and every product file` |
| dependency pins (pyproject changed) | `… -m pytest caos/tests/test_dependency_pins.py -q` | `4 passed` |
| frontend | `npm run lint` · `npx tsc --noEmit` · `npm run test:unit` · `npm run build` | `ESLint: No issues found`; `TypeScript: No errors found`; `tests 123 pass 123 fail 0`; build exit 0 |
| workbench smoke, local | `CAOS_URL=http://127.0.0.1:8766 node scripts/workbench-smoke.mjs` against a fresh `caos-gates` host-control server, before and after the instrumented wait | exit 0 both times; `{"timing":{"domContentLoaded":64.1,"firstContentfulPaint":152},"caseRequests":1}` and `{…"domContentLoaded":67.5,"firstContentfulPaint":160…}` |
| render cost | `--durations` on the golden dump | long_text 39.7 s, dense 3.7 s, multilingual 2.2 s, normal 1.6 s: the bisection measures about eight candidate pages per split, so a 39-page narrative costs about a second a page |

## Pull request

Draft PR to `main`: https://github.com/EricMG13/CAOS-LangMVP/pull/51 (commit `e770a65`, branch `claude/enterprise-report-signing-filing-e14fb4`, base `eea2b29` = current `origin/main`; no rebase was needed).
