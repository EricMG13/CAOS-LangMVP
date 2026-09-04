# Enterprise Task 13 report — assemble and verify the evidence package (second half, ER-G10)

**The candidate cannot be signed.** Candidate `2026-09-04-b88c0f8` (tag
`enterprise-candidate-2026-09-04`) has a hashed evidence package, every one of
the 340 checks and 30 simulations mapped, and every G0–G9 gate accounted for —
but 71 checks are OPEN, 17 are BLOCKED EXTERNAL, one (PERF-009) FAILS, no live
matrix cell exists, the post-soak comparison ER-L4 owes was never run, all
fifteen reviewer records are outstanding, and the six golden journeys did not
run on the frozen stack. `PACKAGE_MANIFEST.json::signable` is `false` and lists
every reason. The terminal claim stays: enterprise-testing candidate under
evaluation for one controlled environment, never production ready.

Executed as `ER-G10` on 2026-09-04 in a Claude Code remote session on branch
`claude/new-branch-from-main-aftkz1` from `main` `8a92f57` (the PR #56 squash).
`8a92f57` is one commit past the candidate tag: the diff outside
`.superpowers/` is the WebKit smoke follow-up (D-016: `webkit-teardown.mjs`,
its tests, `workbench-smoke.mjs` focus waits, `package.json`), the ledger scan
exclusion and the two ledgers — no server, methodology, corpus, image or
environment file. The package therefore binds to the tag `b88c0f8`, not to
`8a92f57`; the ledger updates this task makes are committed at the package
commit and copied into the package under `package/ledgers/`.

Inputs read before starting: the standing preamble; Task 13 and the finishing
sequence of `docs/superpowers/plans/2026-09-01-enterprise-testing-readiness-execution.md`;
Phase 7, the blocker closure map and the exclusions of `ENTERPRISE_READINESS_PLAN.md`;
"Define enterprise-testing readiness", "Keep production operations outside the
MVP gate", "Apply release gates", "Produce a release evidence package" and
"Enforce release exit criteria" of `ENTERPRISE_TESTING_READINESS.md`; the ER-G9
report (`enterprise-task-13-report.md`), `progress.md`, the four loop logs, the
candidate directory (`MANIFEST.json`, `EVIDENCE.md`, `gates/`, `reviews/`,
`soak/`).

## What the retained evidence said before this task touched anything

- **ER-L3 never ran.** `.superpowers/sdd/loops/live-matrix.md` carries the
  binding instructions and no tick; no live result exists under
  `gates/qualification/evidence/live/`. The credential, the analyst-approved
  keys and C20–C22 are still external.
- **ER-L4 stopped at the after-the-fact entry.** `soak-watch.md` records the
  soak finishing on its own (`profile.json` at 08:20Z, leakage `[]`, three
  worker restarts, 6,291 accepted runs, no driver error) and the clamd
  OOM-kill at 03:31Z, then lists what it still owes: the clamav restart logged
  as an operator action, `baseline`/`compare`, the authority diff, the three
  post-soak journeys and the PERF-014 leak check. None of that is in the log.
- **All fifteen reviewer records are OUTSTANDING** — prepared with this
  candidate's digests, none returned.
- **The session has no Docker daemon** (`docker info`: cannot connect to
  `/var/run/docker.sock`), and the two frozen images exist only on the machine
  that built them (local tags, no registry), so the frozen stack cannot be
  started here.

## What this task produced

Everything is under `.superpowers/sdd/candidates/2026-09-04-b88c0f8/package/`
and holds only retained candidate artifacts, the loop logs, the prepared
reviewer records, the ledgers at the package commit and the scripts:

| File | What it is |
| --- | --- |
| `PACKAGE_MANIFEST.json` | identity (commit, tag, both image ids, methodology build, corpus digest, candidate-manifest sha256, binding); the G0–G9 table with state, quoted result, artifacts and what closes each; the check summary by result and family with every OPEN/FAIL/BLOCKED EXTERNAL owner; the thirteen blockers with closing evidence; the thirteen excluded production requirements; eight test-only limitations with where each is recorded and who approves it; eight missing artifacts with owners; `signable: false` and `not_signable_because`; every object's sha256 and size |
| `checks.csv` | all 340 checks (`UX` 20, `SRC` 30, `EVD` 20, `RUN` 30, `MOD` 25, `ANA` 20, `CALC` 20, `PUB` 30, `AUD` 20, `IAM` 20, `SEC` 30, `SIM` 30, `WEB` 15, `PERF` 15, `REV` 15 — the 30 simulations are among the 340) with condition, result, evidence, owner and notes |
| `PACKAGE.sha256` | the package digest: sha256 over the manifest bytes followed by `path\0sha256\n` for every object in sorted order |
| `loops/` | `live-matrix.md`, `soak-watch.md`, `pr-babysit.md`, `focus-race-findings.md` verbatim |
| `ledgers/` | `QUALITY_LEDGER.csv`, `QUALITY_DEFECTS.csv`, `PERIMETER_LEDGER.csv`, `QUALITY_QUALIFICATION.csv`, `SIMULATION_LEDGER.csv`, `SPEC_RECONCILIATION.md`, `ENTERPRISE_TESTING_READINESS.md` at the package commit |
| `corpus/` | the 22 pack manifests (documents, dispositions, periods, provenance, digests) and `sources.txt`; answer keys stay in the tree at the tag (their digests ride each manifest) |
| `inventory/` | `openapi.json` (60 operations, 54 paths) and `route-inventory.json`, served by `dev.py` at the candidate commit (route registration is a pure function of the code; the serving environment was the rehearsal server, not the image) |
| `maps/` | the five family maps the check table was built from |
| `assemble_package.py` | builds all of the above from retained inputs; refuses a `junit:` citation that is not `passed` in the candidate's own junit, an `artifact:` path that does not exist, a PASS without evidence, an OPEN/FAIL/BLOCKED EXTERNAL without an owner |
| `verify_evidence_package.py` | standard library only; on a copy: every object digest, missing and extra objects, the package digest, every junit citation in `checks.csv`, every gate and blocker artifact, the signable flag |
| `golden_journeys.py` | the six-pathway HTTP driver (below) |

### The check map

| Result | Count | Meaning |
| --- | --- | --- |
| PASS | 222 | a retained passed test or retained artifact covers the whole condition |
| PROVED HOST CONTROL | 29 | only the answer-keyed orchestration binding proves it; the live half is external (owner: enterprise test owner / model risk) |
| BLOCKED EXTERNAL | 17 | an external input is missing (owner named per row) |
| OPEN | 71 | no retained result covers the whole condition; owner named per row |
| FAIL | 1 | PERF-009 — measured and not met |

By family (PASS / PROVED HOST CONTROL / BLOCKED EXTERNAL / OPEN / FAIL):
UX 16/1/0/3/0 · SRC 19/0/0/11/0 · EVD 11/4/0/5/0 · RUN 27/0/0/3/0 · MOD 7/16/2/0/0 ·
ANA 4/7/4/5/0 · CALC 20/0/0/0/0 · PUB 21/0/2/7/0 · AUD 7/0/2/11/0 · IAM 18/0/1/0/0 ·
SEC 25/0/5/0/0 · SIM 30/0/0/0/0 · WEB 10/0/1/4/0 · PERF 7/1/0/6/1 · REV 0/0/0/15/0.

How the rows were built, and what each source proves:

- `IAM/SEC/WEB/PERF` come from `docs/PERIMETER_LEDGER.csv`: every
  `retained-test` row's tests re-verified in the candidate junit; every
  `release-gate` row bound to the candidate's `sec-audit.txt`, scans, frontend
  and ledger artifacts; the `candidate-harness`, `structural` and
  `manual-checklist` rows judged one by one from `gates/stack/`, `soak/` and
  `gates/browser/` (the judgements are the `JUDGED` table in
  `assemble_package.py`, each with its artifact and reason).
- `MOD` from `docs/QUALITY_QUALIFICATION.csv` bound to the candidate's
  host-control verdict (`32 pass, 5 BLOCKED EXTERNAL`,
  `ORCHESTRATION_PROOF_INCOMPLETE`) and the runtime test modules.
- `SIM` from `docs/SIMULATION_LEDGER.csv`: every named test re-verified
  (`gates/sim-evidence.json`: 30/30, 67 tests, 0 missing).
- `CALC` verbatim from `SPEC_RECONCILIATION.md` "CALC-001–020 → retained tests",
  every cited test re-verified (parametrized cells included).
- `UX`, `SRC`, `EVD`, `RUN`, `ANA`, `PUB`, `AUD` were mapped by four
  fresh-context subagents reading each condition against the test sources and
  the candidate artifacts under binding rules (PASS only for a direct
  assertion; partial coverage is OPEN; nothing from prose), then every
  citation re-verified mechanically by the assembler. Their own weakest rows
  are recorded in the notes column.
- `REV-001–015`: OPEN, one owner per role, until each record is returned.

Notable rows the reader should not miss (all in `checks.csv` with their
evidence):

- **PERF-009 FAIL**: `list_cases` p95 1.28 s, `list_sources` p95 1.41 s,
  `case_detail` p95 1.20 s, `accept` p95 2.23 s at 76–97 % app CPU in the
  declared profile on one instance (`soak/profile/profile.json`).
- **PERF-013 OPEN**: the eight-hour soak ran (route-balanced, worker restarts
  every two hours, 6,291 accepted runs, no driver error) but its cycle stops
  at acceptance — previews were 422 because the served binding yields no
  READY model, so model, draft, freeze, approve, receipt, download and
  audit-export cycles were not exercised; and it ran 80 documents per case.
- **PERF-006 OPEN**: 100 documents per case exceed the 2,000-row manifest
  ceiling (attempt 1 retained: every run `AGENT_BUDGET_EXCEEDED`).
- **PERF-014/015 OPEN**: owed by ER-L4.
- **AUD-004/AUD-020, EVD-020 OPEN**: no per-read audit record exists (reads are
  budget charges); no release gate evaluates audit-path completeness.
- **SRC-002/008/009/010 OPEN**: media type is stored unverified; XLSX package
  screening (external links, macros, formulas, hidden sheets) is proven only for
  the loan-universe importer, not the general source path.
- **PUB-030, AUD-017 OPEN**: the offline verifier is proven in-suite; no
  on-image audit package was produced on this candidate.
- **ANA-003/004/008/013, PUB-018/026 BLOCKED EXTERNAL**: analyst blind review
  and the pinned benchmark (REV-001/006); the answer keys are implementer-attested
  at host-control scope only.

### G0–G9 on this candidate (from `PACKAGE_MANIFEST.json`)

| Gate | State | Closes with |
| --- | --- | --- |
| G0 scope and traceability | OPEN — every check mapped; 89 rows are not a retained pass | every OPEN/FAIL/BLOCKED EXTERNAL row resolved on this candidate |
| G1 deterministic automation | GREEN | — |
| G2 evidence integrity | OPEN (host-control half green) | ER-L3 |
| G3 model qualification | OPEN — no live cell | ER-L3, qualification record, C20–C22 |
| G4 analyst validation | OPEN | REV-001/002/005/006 |
| G5 security | OPEN (scanner, SAST, dependency, secret, workflow, authorization halves green) | penetration test, egress proof, provider policy, identity edge, REV-004/007/008/014 |
| G6 resilience | GREEN | — |
| G7 publishing | OPEN (contract half green) | the six golden journeys on the frozen stack with a binding that yields a READY model |
| G8 audit reconstruction | OPEN (verifier proven in-suite) | REV-012 on an on-image package |
| G9 enterprise test deployment | GREEN with findings (clamd OOM; identity edge external) | REV-014, OIDC inputs |

### Blockers (from `PACKAGE_MANIFEST.json`, mirrored into the blocker table)

Closed with retained candidate evidence: ETR-B02, B03 (excluded), B04, B06,
B07, B08, B09 (excluded), B10. Closed under host control with the live half
open: ETR-B01, B12. Open: ETR-B05 (no live cell), B11 (Distressed and Deep
Research not live-qualified), B13 (benchmark not pinned, REV-006 outstanding).

## The six golden journeys

**Not run on the frozen stack.** The stack needs the Docker daemon and the two
image ids that live only on the machine that built them; this session has
neither. What was done instead, so the run on the stack is one command:

`package/golden_journeys.py` drives, per pathway and over HTTP only: documents
in through `POST /api/intake` → the disposition review from
`GET /api/cases/{id}/intake` → execution (the Deep Research plan gate approved
on its exact proposed hash) → `POST /api/runs/{id}/accept` → model readiness,
`POST /models`, the worker build, assumption registry, preview and model
sign-off → deliverable workspace and draft → opinion sign-off on the exact
revision → freeze (worker-rendered md/pdf/xlsx) → the signer's own filing
attempt (must be refused) → a distinct approver's filing → the filing receipt →
exact download of every format, digest-checked against the frozen record and
the `x-caos-sha256` header → `GET /audit-package` → `verify_package.py` on the
zip. Every step records its HTTP status and typed code; a typed refusal is
recorded, never raised. The overlay pathways drop into the Full Credit case so
their model effect can find its base. No HTTP route grants the first case
membership, so the distinct approver is an operator action against the store
(`--database-url`, recorded as `operator_bootstrap`) — defect D-021.

**Rehearsal** (not candidate evidence; kept out of the package): a dev server
and worker (`dev.py`, `worker.py`, `ENVIRONMENT=development`,
`CAOS_PROVIDER=host_control`, `AGENT_EXECUTION_ENABLED=true`, SQLite, Python
3.13 from the hashed lock, `pango-view` installed) from a clean worktree at the
tag (`git status --porcelain` empty). Outcomes at the candidate commit:

| Pathway | Outcome |
| --- | --- |
| FULL_CREDIT | intake 201 → review 200 → run succeeded (17 nodes) → accept 200 → readiness `CANONICAL_MODEL_INPUTS_INVALID` → `POST /models` 422 `MODEL_BUILD_INVALID` → draft 422 `MODEL_REQUIRED` |
| EARNINGS_UPDATE, COVENANT_REFINANCING | … → accept 200 → `MODEL_NOT_READY` → draft 422 `DELIVERABLE_PATHWAY_AUTHORITY_MISMATCH` (no validated prior Full Credit model) |
| DISTRESSED_RESTRUCTURING | … → accept 200 → `DISTRESSED_BASE_MODEL_REQUIRED` → draft 422 `DELIVERABLE_PATHWAY_AUTHORITY_MISMATCH` |
| RELATIVE_VALUE | intake 201 (workbook imported) → run succeeded → accept 200 → `MODEL_NOT_READY` → draft 201 → opinion 201 → freeze 202 → job `PUBLISHED` → signer's filing 403 → approver provisioned → filing 200 `FILED` → receipt 200 → md/pdf/xlsx 200, each digest equal to the frozen record and the served header → audit package 200 (179 KB) → `verify_package.py` **VERIFIED** (objects 28, receipts 1, markdown reconstructed 1, findings []) |
| DEEP_RESEARCH | intake 201 → plan `PLAN_APPROVAL_REQUIRED` → approve 200 → run succeeded → accept 200 → `MODEL_NOT_READY` → draft 201 → … → filing 200 → receipt 200 → three exact downloads → audit package **VERIFIED** (objects 37, receipts 2, markdown reconstructed 2, findings []) |

The reading that matters for the decision owner: **on the served
`host_control` binding the journeys cannot reach model creation** — the
host-control provider emits the six section headings and no CP-MODEL tables,
so Full Credit is refused typed at the build and the four model-required
pathways stop at typed refusals. The journeys through freeze, filing, receipt
and offline verification are proven at the commit for the two model-optional
pathways; the whole chain for all six needs a binding that yields a READY Full
Credit model, which is the live binding ER-L3 is blocked on. On the frozen
stack, therefore, the same script will reproduce exactly these outcomes until
G3 closes. This is recorded on G7, PUB-030, AUD-017 and PERF-013, not inferred
into a pass.

## Ledger updates (only from retained candidate evidence)

- `docs/QUALITY_LEDGER.csv`: F-RUN-16 and F-RUN-18 were stale `FAIL` rows from
  2026-09-01; both now `PASS` on the candidate's `CORPUS_FULL=1` host-control run
  (`35 passed`, every route, both depths) with the live half named as BLOCKED
  EXTERNAL in the notes. F-QUAL-05's unquoted Test Cases field had split the
  row into 15 columns; rejoined (content unchanged). 134 rows, all PASS.
- `docs/QUALITY_DEFECTS.csv`: D-017 (clamd OOM, no restart-on-unhealthy —
  environment), D-018 (PERF-009 not met), D-019 (declared 100 documents per
  case vs the 2,000-row manifest ceiling), D-020 (no `.dockerignore`; build
  context), D-021 (no HTTP route grants the first case standing). All OPEN with
  their retained evidence paths; none patched.
- `SPEC_RECONCILIATION.md`: new section "Candidate 2026-09-04-b88c0f8 evidence
  package" — the ten invariants' 26 named tests all `passed` in the candidate
  junit (checked mechanically; two `…::` references cross modules), the check
  map, what the package lacks, and an anti-vacuity ledger.
- `ENTERPRISE_TESTING_READINESS.md` blocker table: every row now names its
  state on candidate `2026-09-04-b88c0f8` and the retained artifact (see
  Blockers above).
- `.superpowers/sdd/candidates/2026-09-04-b88c0f8/EVIDENCE.md`: one row for
  the package. The ER-G9 report gained a pointer to this file and is otherwise
  unchanged.

Gates rerun after the edits: `test_perimeter_ledger.py` + `test_simulation_ledger.py`
`8 passed`; `docs/quality_ledger_coverage.py` → `routes checked: 54  product
files: 356  features: 134 / the ledger documents every route and every product
file`. No product code changed (`git status`: the two ledgers, the two
documents, the ER-G9 report pointer, `EVIDENCE.md`, and the new `package/`).

## Exact commands

```bash
# candidate worktree and hashed dependencies (rehearsal only)
git worktree add --detach <scratch>/candidate enterprise-candidate-2026-09-04
uv venv --python 3.13 <scratch>/candidate/caos/server/.venv313
<venv>/bin/python -m pip install --require-hashes -r caos/server/requirements.txt -r caos/server/requirements-dev.txt

# rehearsal server and worker at the tag (not the image)
ENVIRONMENT=development CAOS_PROVIDER=host_control AGENT_EXECUTION_ENABLED=true PORT=18400 \
  CAOS_DATA_DIR=<scratch>/rehearsal/data CAOS_STORAGE_DIR=<scratch>/rehearsal/vault <venv>/bin/python dev.py
ENVIRONMENT=development CAOS_PROVIDER=host_control AGENT_EXECUTION_ENABLED=true \
  CAOS_DATA_DIR=<scratch>/rehearsal/data CAOS_STORAGE_DIR=<scratch>/rehearsal/vault <venv>/bin/python worker.py

# the six journeys (on the frozen stack: --base-url http://127.0.0.1:18300 and the stack's DATABASE_URL)
python .superpowers/sdd/candidates/2026-09-04-b88c0f8/package/golden_journeys.py \
  --base-url http://127.0.0.1:18400 --server-path caos/server \
  --database-url sqlite:///<scratch>/rehearsal/data/caos.db --out <scratch>/rehearsal/journeys
# → FULL_CREDIT/EARNINGS_UPDATE/COVENANT_REFINANCING/DISTRESSED_RESTRUCTURING: typed refusals at the model step
# → --pathways RELATIVE_VALUE,DEEP_RESEARCH --issuer "Polaris Holdings": 2/2 complete through offline verification

# the package
python .superpowers/sdd/candidates/2026-09-04-b88c0f8/package/assemble_package.py \
  .superpowers/sdd/candidates/2026-09-04-b88c0f8/package/maps
# → checks {"PASS": 222, "OPEN": 71, "PROVED HOST CONTROL": 29, "BLOCKED EXTERNAL": 17, "FAIL": 1}, objects 163, defects [], signable false
cp -R .superpowers/sdd/candidates/2026-09-04-b88c0f8 <scratch>/verify-copy
python3 -I <scratch>/verify-copy/package/verify_evidence_package.py <scratch>/verify-copy
# → candidate 2026-09-04-b88c0f8: VERIFIED · objects 163 · checks 340 · signable False · exit 1 (verified, not signable)
# tamper checks on the copy: one appended byte → OBJECT_DIGEST_MISMATCH; one removed file → OBJECT_MISSING

# ledger gates after the edits
<venv>/bin/python -m pytest caos/tests/test_perimeter_ledger.py caos/tests/test_simulation_ledger.py -q   # 8 passed
<venv>/bin/python docs/quality_ledger_coverage.py                                                       # complete
```

## The digest

```
c705d5a4cb69cd260d91787f3a34b62ad9f1655b6416167f8b2a151f12b67827  package/PACKAGE_MANIFEST.json+objects
```

163 objects; sha256 over `PACKAGE_MANIFEST.json` followed by `path\0sha256\n`
per object in sorted order (`assemble_package.py::package_digest`;
recomputed by `verify_evidence_package.py`). The candidate manifest inside
it is `35ef8ef8c0daeca1df3d34a7551f96e1834940080e94e2ce6db6b2779d8a9788`
(`MANIFEST.sha256`). The signature line is empty until the enterprise test
owner signs — and the owner should not sign this package: it says so itself.

## Open items with owners

| Item | Owner | What closes it |
| --- | --- | --- |
| Live qualification matrix (G3, MOD live halves, EVD/ANA/UX PROVED HOST CONTROL rows, ETR-B05/B11) | enterprise test owner (credential), model risk (qualification record), corpus owner and licence holder (C20/C21/C22), independent analysts (answer-key approvals) | ER-L3: three retained passes per required cell bound to `b88c0f8` and the app image id, copied under `gates/qualification/evidence/live/`; then `verdict --binding live` |
| Post-soak comparison, PERF-014 leak check, post-soak three-engine journeys (PERF-014/015) | ER-L4 operator on the stack machine | log the clamav restart as an operator action; `qa/capacity.py baseline` + `compare` against `soak/baseline-pre.json`; `authority_snapshot.sh` diffed against `soak/pre-soak-authority.json`; three engines against the post-soak stack |
| Six golden journeys on the frozen stack (G7, G8, PUB-030, AUD-017, PERF-013) | decision owner on the machine holding `sha256:10ec8aa0…`/`sha256:526c2d5f…` | `package/golden_journeys.py --base-url http://127.0.0.1:18300 --database-url <stack DATABASE_URL> --server-path caos/server --out <candidate>/package/journeys`; expect the typed model refusals until G3's binding is served; retain the output under the candidate |
| REV-001–REV-015 | the reviewer roster (external) | returned records with identity, date, result, findings and sign-off on this candidate's digests |
| PERF-009 FAIL; PERF-006 and D-019 (profile vs ceiling) | enterprise test owner / decision owner (REV-015) | a decision on the declared profile, the hardware or the ceiling; a code change is a new candidate |
| Environment: clamd memory and restart policy (D-017); `.dockerignore` (D-020); first-standing bootstrap (D-021) | operations (REV-014) / decision owner | Compose or build-context changes are a new candidate |
| Coverage reports (statement, branch, critical-path) | decision owner | a coverage run against the tag retained under the candidate, or a gate addition in a new candidate |
| Penetration test, egress allowlist proof, provider account policy, OIDC inputs (SEC-023/024/025/028, IAM-016, WEB-013) | security, network owner, provider account owner, identity owner | the external artifacts named in the ER-G9 BLOCKED EXTERNAL table |
| Benchmark set, approved screenshots, scorecards, adjudications (ETR-B13, WEB-015, PUB-018/026) | credit analysts / design owner | REV-001/002/006 |
| Package signature and the approved retention location | enterprise test owner | sign `PACKAGE.sha256` once `signable` is true; copy the candidate directory there |

## Confidence review

1. *Does the package mix candidates?* No: the object set is the
   `2026-09-04-b88c0f8` directory alone; the superseded candidate's directory
   is untouched and unreferenced; every `junit:` citation resolves against
   this candidate's two junit files only.
2. *Is any PASS inferred?* Every PASS row cites a test or artifact the
   assembler re-verified; a PASS without evidence is an assembly defect and
   the build ran with `defects: []`. The four subagent maps were read row by
   row for the non-PASS and flagged rows; their honest partial-coverage OPENs
   were kept as OPEN.
3. *Could the check count be wrong?* 340 extracted from the standard by id
   (15 families), asserted in the assembler, re-counted by the verifier; the
   30 SIMs are among them (the prompt's "340 checks and 30 simulations"
   double-counts).
4. *Does the package hold a secret, prompt, hidden reasoning, provider error
   body or unauthorized source text?* A scan of the candidate directory and
   the package for key prefixes, bearer tokens, `system_prompt` and the
   injection fixture's instruction text hits only the word `system_prompt`
   inside PUB-024's note (which says the export bytes were scanned for it).
   The answer keys were dropped from the package for that reason; the corpus
   manifests carry filenames, digests, dispositions and periods only. The
   rehearsal's filed exports and audit packages are not in the package.
5. *Is the journey driver evidence for anything?* Only that the script works
   at the commit and what the served binding does; the report says so and G7
   stays OPEN. The rehearsal ran Python 3.13 on SQLite with no image, so it is
   not the candidate's environment.
6. *Did the ledger edits change anything the candidate did not prove?*
   F-RUN-16/18 cite the candidate's corpus run; the five defects cite the
   candidate's retained files; the blocker rows cite candidate junit modules
   and artifacts that the assembler verified as `closing_evidence`.
7. *Does the verifier prove anything?* It convicted a one-byte change and a
   removed object on the copy; it re-resolves every citation from the copy's
   own junit, so a package cannot carry a citation its own evidence does not
   support.
8. *Is the OpenAPI inventory candidate evidence?* It was served by the
   candidate commit's code, not the image; the manifest and the inventory
   file say so. ETR-B08's closure rests on the audit's OpenAPI discovery on
   the candidate (`sec-audit.txt`), with the inventory as the retained
   document.
9. *Is anything left claimed that no tool result supports?* Every number in
   this report comes from a retained file or a command run in this session;
   the soak figures are quoted from `profile.json` via the ER-G9 record and
   the same file is in the package.
