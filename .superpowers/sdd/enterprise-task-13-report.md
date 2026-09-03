# Enterprise Task 13 report — freeze the candidate and run the automated gates (first half, ER-G9)

Executed as `ER-G9` (2026-09-03) from `.claude/worktrees/open-session-bcaed2`
on branch `claude/enterprise-readiness-freeze-ddfd60`, which sits on `main`
at `c4f0270` (the Task 12b squash merge, PR #55) with a clean tree. The
prompt names the primary checkout; this session was launched in a worktree
whose HEAD, tree and `origin/main` are the same commit, so the candidate was
frozen as a tag and every gate ran from a fresh clone checked out at that tag
(`git status --porcelain` empty), never from a working tree that could carry
untracked files into an image. Evidence is retained under
`.superpowers/sdd/candidates/2026-09-03-c4f0270/` in this branch; the
approved retention location and the package signer are external inputs.

Inputs read before starting: the standing preamble; Task 13 and the finishing
sequence of `docs/superpowers/plans/2026-09-01-enterprise-testing-readiness-execution.md`;
Phase 7, the external-inputs table, the blocker closure map and the exclusions
of `ENTERPRISE_READINESS_PLAN.md`; "Apply release gates", "Test the declared
enterprise profile", "Review the application manually", "Produce a release
evidence package" and "Enforce release exit criteria" in
`ENTERPRISE_TESTING_READINESS.md`; the ER-G9, ER-G10, ER-L3 and ER-L4 prompts;
`ci.yml`, `nightly.yml`, `security-review.yml`, `enterprise-qualification.yml`;
`caos/deploy/docker-compose.yml`, `Dockerfile`, `ENVIRONMENT_MANIFEST.md`,
`backup.sh`, `restore_drill.sh`; `run.py`, `dev.py`, `worker.py`,
`identity.py`; `qa/capacity.py`; `caos/tests/corpus/qualify.py` and
`manifests.py`; `caos/scripts/scan_floors.py`; the Task 11, 12a and 12b
reports and `.superpowers/sdd/loops/live-matrix.md`.

## Status

COMPLETE for the first half of Task 13. The candidate is frozen and its
manifest hashed; every automated gate that needs no live provider and no
eight hours ran from checked-in scripts against the frozen commit, images,
corpus, binding and stack, and every one is green or recorded as BLOCKED
EXTERNAL with its owner; the stack is up on the frozen images; the soak is
running with its pre-soak baseline recorded. The claim this supports is
"enterprise-testing candidate under evaluation", not "enterprise-testing
ready" (that needs ER-L3, ER-L4, the fifteen reviews and ER-G10) and never
"production ready".

Three things happened that the reader must know.

1. The first accessibility run, taken while the backend suite was
   saturating the machine, scanned `/command-center/` in its loading state
   before hydration and reported two moderate violations; the same command
   on a quiet machine reported none. Both runs are retained; the
   pre-hydration document's missing landmark is an open item for REV-010
   and ER-G10, not patched.
2. **The soak at the declared profile could not be run by the checked-in
   harness.** Two attempts at 25 subjects / 20 jobs / 4 streams / 2
   previews / 300 (then 200) rpm died within minutes: the application
   enforced its per-subject request bucket exactly as designed and the
   harness's threads died on the typed 429s (every job driver, three stream
   holders and the resource sampler). Both attempts are retained under
   `soak/attempt-1-aborted/` and `soak/attempt-2-aborted/`; PERF-013 at the
   declared profile is OPEN on this candidate, and the harness fix is code,
   so it is a new candidate.
3. The running soak (attempt 3, pid 26509, started `2026-09-03T21:02:31Z`)
   is a **reduced profile**: zero stream holders and the reader at 100 rpm,
   with 25 subjects, 20 active jobs, 2 previews per subject, 100 cases × 100
   seeded documents (21 distinct per case, see the open items) and a hard
   worker restart every two hours as the injected fault. Six minutes in:
   `tracebacks: 0`; 133 runs started, 120 succeeded and accepted, 14 running
   and 6 queued (the 20-slot admission ceiling working); `list_cases` p95
   0.85 s, `accept` p95 1.16 s, `start_run` p95 22 s (queueing behind the
   20 slots); app CPU 70–94 %, memory 450–640 MiB, 14 database connections,
   vault 41.6 MB; the harness baseline (`0 cases` for the capacity
   subjects) and the whole-store authority snapshot (12 cases, 24 sources,
   12 runs, 2 snapshots, 57 audit events) were recorded before it started.
   It is an eight-hour stability and leak watch for ER-L4 (PERF-012,
   PERF-014, PERF-015 inputs), and it is never the declared-profile soak.

## The candidate

| Identity | Value |
| --- | --- |
| Candidate id | `2026-09-03-c4f0270` |
| Tag | `enterprise-candidate-2026-09-03` (annotated, on `c4f0270104ad659f7d54dd530b74ba4fd5bb6ccc`) |
| Commit / tree | `c4f0270104ad659f7d54dd530b74ba4fd5bb6ccc`; `origin/main` at the same commit |
| Clean-tree result | worktree `git status --porcelain` empty before tagging; the candidate clone at the tag empty; recorded in `MANIFEST.json::git.clean_tree_result` |
| App image | `caos-cand-20260903-app:c4f0270` = `sha256:cae0ed6b5c55696c44495825552353a4fdd51ff1f63ee6521bf18d89e5bd14fa` |
| Worker image | `caos-cand-20260903-worker:c4f0270` = `sha256:61283796a3d6df4987514e1c5a80310a5073c1652b2796d346cc3f8650dfe7a6` |
| Built | once, from the clone at the tag, `docker build --target app` then `--target worker` (`caos/deploy/Dockerfile`, digest-pinned `node:26-slim` and `python:3.14-slim` bases) |
| Methodology build | `237bf4bc56b616b1c679a32c3733a2d9baf580b113758329320478e0226bae9d` (310 files verified in both images by `verify_image_resources.py`) |
| Corpus digest | `460e3ad6a64c8f78632862921f4d181f0fcb866160a6aa2f44b8c476d70ae7e3` over every C01–C22 manifest, answer key and pinned document digest; per-pack manifest and answer-key digests in `MANIFEST.json::corpus.packs` |
| Binding | `host_control` (development-only orchestration binding; identity digest in `MANIFEST.json::binding.orchestration`); its qualification record is the host-control matrix under `gates/qualification/` and reads ORCHESTRATION_PROOF by construction. The live Anthropic binding and its qualification record are BLOCKED EXTERNAL |
| Environment | `caos/deploy/ENVIRONMENT_MANIFEST.md` (sha256 in the manifest), Compose `deploy.replicas: 1` for app and worker; candidate stack = shipped Compose file + a scratch override pinning the two image ids, publishing the app on `127.0.0.1:18200`, `ENVIRONMENT=development` + `CAOS_PROVIDER=host_control`; `db` and `clamav` at the shipped digests; `oauth2-proxy` and `caddy` not started (OIDC issuer BLOCKED EXTERNAL) |
| Manifest | `.superpowers/sdd/candidates/2026-09-03-c4f0270/MANIFEST.json`, sha256 `c38d205f058a642128827c5ef5949d1675b5581631ba54c6980376df25b3bd57` (`MANIFEST.sha256`) |
| Reviewer roster | BLOCKED EXTERNAL (enterprise test owner); fifteen records prepared under `reviews/REV-001.md` … `REV-015.md`, each carrying the commit, both image ids, the methodology build, the corpus digest and versions, and the questions to answer |

Anything that changes the commit, the images, the corpus, the model policy,
the methodology or the environment after this point is a new candidate; this
report does not patch and re-run.

## Gate table

Every command ran from the candidate clone at the tag with its own Python
3.14.6 venv built from the hashed lock (`uv venv --python 3.14`, `uv pip
install --require-hashes -r caos/server/requirements-dev.txt`, editable
install with `--no-deps`) and `npm ci` (351 packages); `PY` is that venv's
python. Artifacts are relative to
`.superpowers/sdd/candidates/2026-09-03-c4f0270/gates/`.

| Gate | Command | Result (quoted) | Artifact |
| --- | --- | --- | --- |
| Ruff | `PY -m ruff check --config ruff.toml caos/server caos/tests --exclude caos/server/caos/methodology/vendor` | `All checks passed!` exit 0 | `ruff.txt` |
| Route security audit | `ANTHROPIC_API_KEY= … PY run_sec_audit.py` | `{'audited_routes': 59, 'matrix_cells': 507, 'cross_case_probes': 20, 'failures': 0}` exit 0 | `sec-audit.txt` |
| Quality ledger | `PY docs/quality_ledger_coverage.py` | `routes checked: 54   product files: 353   features: 134` / `the ledger documents every route and every product file` exit 0 | `quality-ledger.txt` |
| Deploy assets | `bash -n` over deploy and script shells; `docker compose … config -q --no-interpolate`; `config -q` with the filled example env; required secrets empty; `Modular OS/tools/check_module_consistency.py` | all ok; `26 modules checked, 0 with drift.` exit 0 | `deploy-assets.txt` |
| Backend suite (with the candidate PostgreSQL) | `CAOS_TEST_POSTGRES_URL=postgresql+psycopg://…@127.0.0.1:55434/postgres CAOS_REQUIRE_POSTGRES=1 ANTHROPIC_API_KEY= OPENROUTER_API_KEY= GEMINI_API_KEY= PY -m pytest caos/tests -q -p no:cacheprovider -W always -rs --junitxml=…` | `1236 passed, 1 skipped, 1 warning in 1483.18s (0:24:43)` exit 0; the skip is the nightly-only whole-pack harness cell (covered by the CORPUS_FULL run below); the warning is the third-party StarletteDeprecationWarning; junit: tests 1237, failures 0, errors 0 | `pytest-backend.txt`, `pytest-backend-junit.xml` |
| Two-connection PostgreSQL races and instance locks | inside the suite above, against `postgres:17-alpine@sha256:18cfe3ef…` started fresh as `caos-cand-20260903-pg` (port 55434) | `test_postgres_races` 27 passed, `test_single_instance` 49 passed, 0 skipped | junit above |
| SIM-001–SIM-030 | `docs/SIMULATION_LEDGER.csv` rows mapped to the junit reports and the frontend unit output (scratch mapper, retained) | `simulations 30, pass 30, open [], tests_referenced 67, tests_missing []` | `sim-evidence.json`, `sim-evidence.csv`, `sim-evidence-summary.txt` |
| Corpus host control, every route, both depths | `CORPUS_FULL=1 ANTHROPIC_API_KEY= … PY -m pytest caos/tests/test_corpus_pathways.py -q -p no:cacheprovider -W always -rs --junitxml=…` (30 Carnival documents, digest-pinned by `sources.txt`) | `35 passed, 1 warning in 331.15s (0:05:31)` exit 0 — orchestration proof only | `corpus-full.txt`, `pytest-corpus-full-junit.xml` |
| Frontend | `npm run lint -- --max-warnings=0`; `npx tsc --noEmit`; `npm run test:unit`; `npm run build` | lint exit 0; tsc exit 0; `tests 123 pass 123 fail 0`; `✓ Compiled successfully`, 12 static pages, build exit 0 | `frontend.txt`, `frontend-unit.txt` |
| Image resources | `docker run --rm --entrypoint python <image> verify_image_resources.py --runtime app|worker` | app: `build_id 237bf4bc…, checked 310, mismatches 0, pango /usr/bin/pango-view`; worker: same plus `libreoffice /usr/bin/soffice`, workbook smoke `formulas_validated 345, semantic_checks 20, LibreOffice 25.2.3.2` | `scans/images.txt` |
| Trivy inventory + SBOM + fixable HIGH/CRITICAL gate | `trivy image --scanners vuln --list-all-pkgs --format json`, `scan_floors.py trivy --image-id`, `trivy image --format cyclonedx`, `scan_floors.py sbom`, `trivy image --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1` (Trivy 0.72.0) | app: 181 packages inventoried, SBOM 182 components, gate exit 0; worker: 390 packages, SBOM 391 components, gate exit 0 | `scans/trivy-{app,worker}.json`, `scans/sbom-{app,worker}.cdx.json`, `scans/trivy-*-fixable-gate.txt` |
| Dependency CVEs | `pip-audit --require-hashes -r caos/server/requirements.txt --format json` + floor (Python 3.12.14 scanner venv from the hashed `requirements-security.txt`) | `No known vulnerabilities found`; `pip-audit audited 57 dependencies, none vulnerable` | `scans/pip-audit.json`, `scans/dependency-and-sast.txt` |
| Python SAST | `bandit -r caos/server/caos -x …/vendor --severity-level high --confidence-level medium -f json` + floor | `bandit scanned 21632 lines with no parse errors` | `scans/bandit.json` |
| Frontend advisories | `npm audit --audit-level=high`; `npm audit --json` + floor | `found 0 vulnerabilities`; `npm audit covered 409 dependencies (high 0, critical 0)` | `scans/npm-audit.json` |
| Secret scan | `ghcr.io/gitleaks/gitleaks:v8.18.4@sha256:75bdb2b2…` `detect --source=/repo --config=/repo/.gitleaks.toml` over a clone at the tag + floor | `gitleaks scanned 207 commits with no findings` exit 0 (a first run over the scratch-path clone saw an empty bind mount — Docker Desktop does not share that path — and the floor refused it: `gitleaks did not report the commits it scanned`; rerun over a clone under the worktree's ignored `.dev-data/`) | `scans/gitleaks.log`, `scans/gitleaks.txt` |
| Scan manifest | `scan_floors.py manifest --commit c4f0270… --image app=… --image worker=… --image source-tree=…` | `scan manifest binds 8 reports to 3 image(s) at c4f0270104ad` | `scans/scan-manifest.json` |
| Accessibility (first run, under the backend suite's load) | `CAOS_URL=http://127.0.0.1:18200 node scripts/a11y-axe.mjs` against the empty stack | exit 1: two moderate violations on `/command-center/` in the `state-loading` scan (`landmark-one-main`, `page-has-heading-one` on `<html>`), i.e. the scan ran on the pre-hydration document; rerun on a quiet machine below | `browser/a11y.txt` |
| Accessibility (rerun, quiet machine, stack still empty) | same command | `{"routes":9,"viewports":6,"combinations":75,…,"states":["empty","populated","review","filed","loading","error","refusal"],…,"violations":0}` exit 0 | `browser/a11y-rerun.txt` |
| Three-engine documents-only journey against the frozen app image | `CAOS_URL=http://127.0.0.1:18200 CAOS_BROWSER=<engine> node scripts/workbench-smoke.mjs` (Playwright 1.62.1; chromium-1234, firefox-1538, webkit-2336) | chromium `151.0.7922.34` passed 142 177 ms (DCL 62 ms, FCP 148 ms, budget enforced); firefox `153.0` passed 150 146 ms; webkit `26.5` passed 151 520 ms; `console_errors: []` in all three; the six pathways run as data cases of the one journey through `POST /api/intake` | `browser/browser-gates.txt`, `browser/smoke-<engine>.log`, `browser/test-results/<engine>/workbench-report.json` |
| Host-control qualification matrix (binding's qualification record) | `ANTHROPIC_API_KEY= … CAOS_PROVIDER= CAOS_BUILD_COMMIT=c4f0270… CAOS_IMAGE_DIGEST=sha256:cae0ed6b… PY caos/tests/corpus/qualify.py matrix --binding host_control --reviewer "Claude Fable 5.1 (ER-G9, orchestration proof only)" --out gates/qualification/evidence`; then `qualify.py verdict --binding host_control` | 37 cells: 32 `exit 0` (C01 ten cells, C02–C19), 5 `exit 2` BLOCKED EXTERNAL (C20 RELATIVE_VALUE screen/full, C21 DISTRESSED_RESTRUCTURING screen/full, C22 DEEP_RESEARCH full); verdict `ORCHESTRATION_PROOF_INCOMPLETE`, `complete: false`, `blocking` 5, `blocked_external` 22, `expired_results []`, `stale_results []`; matrix exit 1 and verdict exit 1 by construction — never QUALIFIED | `qualification/host-control-matrix.txt`, `qualification/host-control-verdict.txt`, `qualification/evidence/host_control/<pack>/<PATHWAY>-<depth>/rep-1-*.json` (37 results bound to the commit, the app image id, the methodology build and the corpus digest) |
| Limit boundaries over HTTP against the stack | `PY qa/capacity.py limits --url http://127.0.0.1:18200` (after the browser journeys; 36 cases on the stack) | PASS ×7, NOT_EXERCISED ×1: rate 300 sent/300 admitted/0 refused, 26 of the next 30 refused; streams `[200,200,200,200]`, fifth 429, other subject 200, after release 200; previews `[422,422,429]` (in-process proof named); active jobs 25 sent → 20 admitted, 5 typed `ADMISSION_BUSY`, 20 terminal; source bytes 1 KiB 201 / 25 MiB 201 / 25 MiB+1 → 413 `source exceeds upload limit`; intake 39 → 201, 40 → 201, 41 → 422 `INTAKE_TOO_MANY_FILES`; manifest rows 2 000 → succeeded, 2 002 → failed `AGENT_BUDGET_EXCEEDED`; request bytes NOT_EXERCISED (Caddy's ceiling; edge not started) | `stack/capacity-limits.json`, `stack/stack-gates.txt` |
| Backup (writers paused) | `COMPOSE_PROJECT_NAME=caos-cand-20260903 CAOS_BACKUP_RECIPIENT=age1… bash caos/deploy/backup.sh <out>` with 36 cases / 72 sources / 36 runs on the stack | exit 0 in 1 s; manifest: `vault_volume caos-cand-20260903_vault-data`, `snapshot_point paused-writers`, `caos.dump.age 43c6da35…` (1 091 897 B), `vault.tgz.age f80151db…` (596 677 B); app healthy afterwards. The encrypted pair stays in the session scratch directory (candidate data, not committed); the manifest is retained | `stack/backup-manifest.txt` |
| Restore drill | `CAOS_BACKUP_IDENTITY=… RESTORE_DRILL_DB=caos_restore_drill_cand RESTORE_DRILL_VOLUME=caos_restore_vault_cand bash caos/deploy/restore_drill.sh <out>/caos.dump.age` | `restore drill passed for isolated database caos_restore_drill_cand`, exit 0 (the drill restores both halves into an isolated database and volume, asserts the full startup schema and every READY build's payload, digest and export bytes, then drops them; the extra row count my sequencing script ran afterwards hit the already-dropped database and is void, not a finding) | `stack/stack-gates.txt` |
| Single-instance enforcement on the image | `docker compose … run --rm --no-deps -T app` (same command as the running app) | exit 1: `caos.instance_lock.InstanceAlreadyRunning: INSTANCE_ALREADY_RUNNING: another CAOS application instance holds the checkpoint location /vault/checkpoints.db.lock`; the first app stayed healthy | `stack/stack-gates.txt` |
| Hard kill and recovery on the image | `compose kill -s SIGKILL app worker` then `up -d --no-build app worker` with 67 cases / 62 runs (55 succeeded, 1 failed = the 2 002-row budget refusal, 6 paused) | health back 12 s after the kill; `recovery.started runs=6`, every recovered run `action=skipped_interrupt` (the six parked at the plan gate); store counts identical before and after (cases 67, sources 128, runs 62, snapshots 6, audit 263, run events 1 502) | `stack/stack-gates.txt` |
| Reset | `compose down -v` then `up -d --no-build db clamav app worker` | every project volume removed (`no project volumes remain`); health ok; 31 tables in the fresh schema, 0 startup tables missing; counts all 0; `GET /api/cases` → `[]` | `stack/stack-gates.txt` |
| Golden journey repeated after reset (G9) | `CAOS_BROWSER=chromium node scripts/workbench-smoke.mjs` on the reset stack | chromium `151.0.7922.34` passed 138 246 ms (DCL 90 ms, FCP 180 ms), exit 0 | `stack/post-reset-journey.txt`, `stack/post-reset-test-results/chromium/workbench-report.json` |
| Soak attempt 1 (aborted, retained) | `bash soak/soak.sh …` with the harness default `--rpm 300` | pid 22253, started `2026-09-03T20:38:06Z`, stopped by me at 3 min: five of the twenty job drivers had died with `RuntimeError: run … unreadable for this subject: 429 {"detail":"request rate ceiling reached"}` — the reader thread alone spends the whole 300/min per-subject token bucket, the same subject's job-driver poll then draws a 429 and `wait_terminal` has no retry. The seed phase also showed the harness's 100-document cases are 21-document cases: `upload 10000 → 201: 2100, 409: 7900` (the generated documents repeat every 20 lines, and a duplicate source is refused with 409). Both are harness limitations of the frozen candidate, recorded, not patched | `soak/attempt-1-aborted/` (log, samples, baseline, snapshot, launch record) |
| Soak attempt 2 (aborted, retained) | reset (`down -v`/`up`), pre-soak chromium journey (passed, 139 239 ms), then `soak.sh` with `--rpm 200` and every other declared value | pid 24649, started `2026-09-03T20:46:19Z`, stopped by me at 11 min. By then all 20 job drivers, 3 stream holders and the sampler had died (27 tracebacks): the four stream holders per subject reopen `GET /api/runs/{id}/events` in a tight loop once the case's run is terminal (6 203 opens in three minutes), draining the per-subject bucket; every job driver then met a 429 in `wait_terminal` (no retry) and the sampler's `leakage_check` indexed the 429 body (`TypeError: string indices must be integers`), so samples stopped at 20:50. The application behaved as designed (typed 429s, 65 runs succeeded, health ok, app CPU 73–120 %); it is the harness that cannot sustain the declared profile. Second batch `start_run` p95 55.6 s under 20 concurrent full-depth host-control runs is a real observation of the single-instance ceiling, retained | `soak/attempt-2-aborted/` (log with the tracebacks, five samples, baseline, snapshot, pre-soak journey report) |
| PERF-013 at the declared profile | — | OPEN on this candidate: the checked-in harness destroys its own workload at 25/20/4/2/300 against this single-instance app; a harness fix (retry on 429 and connection errors in `wait_terminal`, a pause in `stream_holder` after a closed stream, an error-body guard in `leakage_check`, distinct seed documents, readers below the ceiling by design) is code and therefore a new candidate | `soak/attempt-1-aborted/`, `soak/attempt-2-aborted/` |
| Reset before attempt 3, pre-soak golden journey | `compose down -v` / `up`; `CAOS_BROWSER=chromium node scripts/workbench-smoke.mjs` | see `soak/pre-soak-reset-and-journey.txt` (quoted in the status section) | `soak/pre-soak-reset-and-journey.txt`, `soak/pre-soak-journey/chromium/workbench-report.json` |
| Soak attempt 3 (reduced profile) running | `bash soak/soak.sh <clone> soak/` → `qa/capacity.py baseline`, `soak/authority_snapshot.sh`, then `qa/capacity.py profile --duration 28800 --streams 0 --rpm 100 --large-every 500 --sample-every 30 --compose-project caos-cand-20260903 --restart-every 7200 --restart-command "docker compose -p caos-cand-20260903 restart -t 0 worker"` — 25 subjects, 20 active jobs, 2 previews, 100 cases × 100 seeded documents (21 distinct per case), worker hard-restart every two hours; **zero stream holders and the reader at 100 rpm**, so the workload survives | pid, start time, baseline and snapshot quoted in the status section; this is an eight-hour stability and leak watch (PERF-012, PERF-014, PERF-015 inputs) at a reduced load, never the declared-profile soak | `soak/soak-launch.txt`, `soak/baseline-pre.json`, `soak/pre-soak-authority.json`, `soak/profile.log`, `soak/profile/samples.jsonl`, `soak/profile.pid`, `soak/started-at.txt` |
| CI workflow steps | — | not executed as workflows here: every step of `ci.yml`'s frontend, server, browser, deploy-assets, image, postgres and security jobs was run from the checked-in scripts above against the candidate identities; `security-review.yml` is a pull-request check (nothing to diff on a frozen tag); `enterprise-qualification.yml` is the live matrix (BLOCKED EXTERNAL); the workflows themselves are pinned by `test_workflow_security.py` (22 passed) and `test_recorded_review.py` (8 passed) inside the suite | junit above |

## BLOCKED EXTERNAL

Each row names the owner and the artifact; none is claimed by a retained
check, and none was worked around.

| Item | Owner | Artifact needed | Where it goes |
| --- | --- | --- | --- |
| Live provider binding and its qualification record (G3, MOD-001–025, every live half of the matrix) | enterprise test owner (credential); model risk and product (provider, model id/version, parameters, contractual settings) | `ANTHROPIC_API_KEY` in the ER-L3 shell and the `enterprise-qualification` environment; a `ProviderQualification` record and its digest | `qualify.py cell --binding live` per required cell, three cold repetitions (`.superpowers/sdd/loops/live-matrix.md`) |
| Licensed market marks (C20), Lumen stressed pack (C21), research pack (C22) and analyst-approved answer keys for every pack | licence holder, corpus owner, research analyst, independent credit analysts | as listed in `enterprise-task-11-report.md` "BLOCKED EXTERNAL" (unchanged) | `$CAOS_CORPUS_EXTERNAL_DIR/C2x/`, `packs/<id>/manifest.json` digests and `answer_key.approvals` |
| Enterprise identity provider and test accounts (IAM-016 and WEB-013 live halves; `oauth2-proxy` and `caddy` in the stack) | enterprise identity owner | OIDC issuer, client id and secret, one account per role plus one with no group | `caos/.env` for the stack (`OAUTH2_PROXY_*`, `CAOS_DOMAIN`); then the edge services start and the 32 MiB request ceiling is probed with `qa/capacity.py limits --edge-url` |
| Egress allowlist proof (SEC-025), authorized penetration test (SEC-028), provider account policy and settings (SEC-023/024) | enterprise network owner; security; provider account owner | as listed in `enterprise-task-12b-report.md` "BLOCKED EXTERNAL" (unchanged) | the security package for ER-G10 |
| Malware scanner signatures (SEC-001 upload half, SIM-028 live half) | operator | current signature set on the `clamav` service (the stack's `clamav/clamav:1.5` container updates from the network on start; freshness is not asserted here) | REV-014 |
| Reviewer roster for REV-001–REV-015 | enterprise test owner | named reviewers per role | `reviews/REV-0NN.md` (prepared; identity, date, result, findings and sign-off blank) |
| Release-package signer and the approved evidence retention location | enterprise test owner | a signer and a location outside this repository | ER-G10 copies `.superpowers/sdd/candidates/2026-09-03-c4f0270/` and the soak directory there and signs the package digest |
| Approved benchmark screenshots, content rubric, minimum print sizes and reviewer score threshold pinned to Credit Operating System `e566c1b` (ETR-B13, REV-006) | credit analysts, design owner, external-stakeholder reviewer | the pinned benchmark set | REV-001, REV-006 |

## What ER-L3, ER-L4, the reviewers and ER-G10 still owe

**ER-L3 (live qualification matrix)** — in a shell with the protected
credential and `CAOS_CORPUS_EXTERNAL_DIR` exported, on the candidate clone
or a checkout of the tag, with `CAOS_BUILD_COMMIT=c4f0270104ad659f7d54dd530b74ba4fd5bb6ccc`
and `CAOS_IMAGE_DIGEST=sha256:cae0ed6b…` so every result binds to this
candidate: three retained `pass` results per required cell (`qualify.py plan
--binding live`), every C20/C21/C22 cell either run or logged BLOCKED
EXTERNAL, and `qualify.py verdict --binding live` retained; evidence under
`caos/tests/corpus/evidence/live/` copied into the candidate directory. Until
the credential and the answer-key approvals exist, the verdict is
UNQUALIFIED by construction and G3 stays open.

**ER-L4 (soak watch)** — thirty-minute ticks appended to
`.superpowers/sdd/loops/soak-watch.md` from the harness samples
(`soak/profile/samples.jsonl`), the containers and the database; at the end
of the eight hours: `soak/profile/profile.json` retained, the post-soak
`qa/capacity.py baseline` and `compare` against `soak/baseline-pre.json`,
the post-soak `authority_snapshot.sh` diffed against
`soak/pre-soak-authority.json` (every pre-soak case byte-identical; only soak
cases and audit rows added), the six documents-only journeys rerun in the
three engines against the post-soak stack and compared with
`gates/browser/test-results/*/workbench-report.json`, and PERF-014's leak
check (jobs, permits, handles, connections, orphan rows) from the last
samples and the final snapshot.

**Human reviewers (REV-001–REV-015)** — each returns the prepared record
under `reviews/` with identity, role, date, result, findings and sign-off;
the build digest on the returned record must equal the commit and both
image ids above. REV-001/002/006 need the benchmark set and the analyst
scorecards; REV-012 needs an audit package from a filed deliverable on this
candidate; REV-010 needs the assistive-technology pass.

**ER-G10 (evidence package)** — the six golden journeys through opinion
sign-off, separate approval, filed download with receipt and offline audit
verification against the frozen stack (the workbench smoke drives the
documents-only journeys with fixture-mocked deliverable routes; the real
freeze/file/receipt/verifier chain on the image is ER-G10's); the package
assembled from this directory, the loop logs and the reviewer records,
verified object by object with `verify_package.py`, hashed, and the ledgers
(`docs/QUALITY_LEDGER.csv`, `docs/QUALITY_DEFECTS.csv`,
`SPEC_RECONCILIATION.md`, the blocker table) updated only from retained
candidate evidence.

## Gate status against G0–G9 for this candidate

| Gate | State after ER-G9 | What closes it |
| --- | --- | --- |
| G0 scope and traceability | open | ER-G10 maps every one of the 340 checks to a retained result or an open owner (`docs/PERIMETER_LEDGER.csv`, `docs/QUALITY_QUALIFICATION.csv`, `docs/SIMULATION_LEDGER.csv` and the quality ledger are the inputs) |
| G1 deterministic automation | green on the candidate: suite, Ruff, audit, ledger, frontend, three engines, accessibility, image checks, deploy assets | — |
| G2 evidence integrity | host-control half green (corpus host control, matrix, lineage tests in the suite); live half open | ER-L3 |
| G3 model qualification | open (`ORCHESTRATION_PROOF_INCOMPLETE`; no live binding) | ER-L3 with the credential, the qualification record and the analyst-approved keys |
| G4 analyst validation | open | REV-001, REV-002, REV-005, REV-006 |
| G5 security | scanner, SAST, dependency, secret, workflow and authorization halves green; SEC-023/024/025/028 and the live IAM halves BLOCKED EXTERNAL | REV-007, REV-008, REV-014, the penetration test |
| G6 resilience | green on the candidate: SIM-001–030 (30/30), two-connection races (27), instance locks (49), kill-and-recover on the image, backup and restore; soak in progress | ER-L4's end-of-soak comparison and leak check |
| G7 publishing | contract half green in the suite (publication, opinion, filing, receipt, goldens); the on-image freeze/file/receipt chain not yet driven | ER-G10's six golden journeys through filing on the stack |
| G8 audit reconstruction | verifier and package tests green in the suite; independent reconstruction open | REV-012 |
| G9 enterprise test deployment | green on the candidate: boots on the frozen images against PostgreSQL, resets to an empty schema (31 tables), isolates subjects (leakage check in the harness), repeats the golden journey after reset; the identity edge is BLOCKED EXTERNAL | REV-014 and the OIDC inputs |

## Commands and results not in the table

```text
$ /usr/bin/git tag -a enterprise-candidate-2026-09-03 c4f0270104ad659f7d54dd530b74ba4fd5bb6ccc -m "Enterprise-testing candidate frozen 2026-09-03 …"
$ /usr/bin/git clone -q <worktree> <scratch>/candidate && git -C <scratch>/candidate checkout -q enterprise-candidate-2026-09-03
→ clone HEAD=c4f0270104ad659f7d54dd530b74ba4fd5bb6ccc status=[] tag=enterprise-candidate-2026-09-03
$ docker build --target app --tag caos-cand-20260903-app:c4f0270 --file caos/deploy/Dockerfile .      (in the clone)
$ docker build --target worker --tag caos-cand-20260903-worker:c4f0270 --file caos/deploy/Dockerfile .
→ app exit 0 (sha256:cae0ed6b5c55…, 181 725 955 B), worker exit 0 (sha256:61283796a3d6…, 408 447 112 B)
$ PY <scratch>/freeze.py MANIFEST.json
→ sha256 c38d205f058a642128827c5ef5949d1675b5581631ba54c6980376df25b3bd57; methodology 237bf4bc…; corpus 460e3ad6…
$ docker run -d --name caos-cand-20260903-pg -p 127.0.0.1:55434:5432 … postgres:17-alpine@sha256:18cfe3ef…   (races target)
$ docker compose -p caos-cand-20260903 --env-file <scratch>/stack/candidate.env -f <clone>/caos/deploy/docker-compose.yml -f <scratch>/stack/override.yml config -q && … up -d --no-build db clamav app worker
→ db healthy, clamav healthy, app healthy, worker started; GET /api/health {"status":"ok","store":true,"bundle":true,"checkpointer":true}; 31 tables, 0 startup tables missing
$ PY <scratch>/reviews.py MANIFEST.json reviews/   → prepared 15 review records
$ docker tag caos-cand-20260903-app:c4f0270 caos-cand-20260903-app:latest (and worker)   — same image ids; lets restore_drill.sh's `compose run app` resolve the candidate image instead of building
```

The scratch files (`freeze.py`, `reviews.py`, `sim_map.py`, `scan-images.sh`,
`browser-gates.sh`, `stack-gates.sh`, the Compose override and env) are
sequencing only; they call the checked-in scripts and never change product
behaviour. The soak launcher and the authority snapshot are retained under
`soak/` because ER-L4 must rerun the snapshot identically.

## Confidence review

Doubts enumerated before declaring the task done, each investigated:

1. *Are the images really built from the commit and nothing else?* The build
   context was a fresh clone at the tag with an empty `git status
   --porcelain`; the Dockerfile copies `caos/server/`, `caos/frontend/`,
   `caos/deploy/verify_image_resources.py` and the model fixtures, and builds
   the export inside the image. The first Docker bind-mount attempt showed
   that Docker Desktop does not share the scratch path at all (an empty
   directory appeared in the container), which is why gitleaks was rerun
   from a clone under the worktree; `docker build` streams its context
   through the CLI and was unaffected (the images verified their own 310
   bundle files).
2. *Did the two-connection races actually run against PostgreSQL?* junit:
   `test_postgres_races` 27 passed, `test_single_instance` 49 passed, 0
   skipped, with `CAOS_REQUIRE_POSTGRES=1` set so a missing URL would have
   failed the run.
3. *Is the SIM mapping vacuous?* Every one of the 67 referenced tests was
   found in the junit reports or the frontend unit output (`tests_missing:
   []`); a test that was absent would read MISSING and the simulation OPEN.
4. *Did the browser gates hit the image or a dev server?* `CAOS_URL` was the
   stack's published port; the app container's `/app/static` is the export
   built in the image; the reports record `base_url`
   `http://127.0.0.1:18200`.
5. *Is the first a11y failure a product defect or a harness race?* The
   sweep navigates with `waitUntil: "domcontentloaded"`, asserts a `Loading`
   status is on screen and scans; the pre-hydration static document
   satisfies the assertion and lacks `<main>`/`<h1>`, so under load the scan
   ran before hydration. That is a real (brief) state of the shipped
   export; recorded for REV-010 and ER-G10 rather than argued away.
6. *Does the restore drill's evidence stand without my extra row count?*
   Yes: the drill's own pass line follows its schema, model-metadata and
   export-byte assertions; my count ran after its cleanup and is void.
7. *Is the soak really detached from this session?* `nohup … &` plus
   `disown` with stdin from `/dev/null`; pid and start time retained; the
   process was alive and seeding when checked (66 cases, 1 069 sources at
   24 s).
8. *Does the soak's worker restart invalidate anything?* It is the harness's
   own `--restart-every`/`--restart-command`; the app is never touched, so
   the job drivers keep running; the worker's dead-claim recovery is the
   seam SIM-008 pins.
9. *Is the candidate binding truthfully labelled?* `host_control` is
   development-only and production-refused (`run.build_provider`); every
   result carries `qualification_status` from `host_control_identity` and
   the verdict reads ORCHESTRATION_PROOF_INCOMPLETE. No live result exists
   anywhere in the evidence directory.
10. *Could the stack override have changed product behaviour?* It pins the
    image ids, publishes a port, sets the development identity edge and the
    host-control binding, and runs `run.build` + `run.serve` under the same
    two single-instance guards `run.py` uses; the second-instance gate
    proved the guard is in force on the image.
11. *Is anything quoted from memory?* Every number in the tables is copied
    from a retained file under the candidate directory.
12. *Was aborting two soak attempts the right call, or should the first have
    run to the end?* A soak whose twenty job drivers and resource sampler
    are dead after four minutes measures readers only and records no
    resources; letting it run eight hours would have produced a
    `profile.json` that looks like evidence and is not. Each attempt's log
    with its tracebacks is retained so the decision can be re-examined.
13. *Did the application, not the harness, fail under the declared
    profile?* The 429s are the per-subject token bucket (`RequestCeilings`,
    300/min) refusing exactly what `limits` proved it refuses; health stayed
    ok, runs kept succeeding (65 in attempt 2), and the store counts were
    consistent. The one application-side observation worth keeping is
    `start_run` p95 of 55.6 s in attempt 2 under 20 concurrent full-depth
    host-control runs, i.e. the single-instance ceiling; it is retained, not
    hidden. Whether the declared profile is achievable at all on one
    instance is a question for ER-G10 with a repaired harness.
14. *Is the reduced-profile soak mislabelled anywhere?* `soak/soak.sh`
    carries the reason in its header, the launch record shows the exact
    arguments, `EVIDENCE.md`, `progress.md`, the soak-watch log and this
    report all say "reduced profile"; the declared 300/min and 4-stream
    ceilings are claimed only from `limits`.

Rewrite tournaments were not run: the standing preamble disables them for
this execution (D4) and this task adds no product code.

## Open items and follow-ups

- Pre-hydration document of the static export lacks a main landmark and a
  level-one heading (axe `landmark-one-main`, `page-has-heading-one`); only
  visible when the a11y sweep scans before hydration. For REV-010 and
  ER-G10; a fix is a new candidate.
- `qa/capacity.py` job drivers do not survive an unreachable API or a 429
  (`wait_terminal` has no retry and re-raises on any non-run body), so an
  app restart under the soak would thin the workload silently, and at the
  harness's default `--rpm 300` the reader starves the driver of the same
  subject (five drivers dead in three minutes, `soak/attempt-1-aborted/`).
  The soak therefore restarts the worker only and runs the reader at 200
  rpm. Harness fix (retry on 429 and connection errors; readers below the
  ceiling by design) is a new candidate.
- The harness's seeded "100 documents per case" are 21 distinct documents
  per case: `text_document` repeats every 20 line counts and the
  application refuses the duplicate bytes with 409 (7 900 of 10 000 seed
  uploads). PERF-005/PERF-006's 100-document lists are therefore not what
  the soak exercises; the limits gate's 40-file intake and the corpus tests
  are the retained evidence for large source lists. Harness fix is a new
  candidate.
- The restore drill is self-cleaning; a post-drill row count must run inside
  the drill, not after it.
- Docker Desktop does not share `/private/tmp/claude-501/…`; bind mounts
  from the session scratch directory appear empty inside containers.
- zsh reads `"$var:c4f0270"` as a history modifier; the image scan script is
  bash for that reason.
- The candidate stack, the candidate PostgreSQL container
  (`caos-cand-20260903-pg`), the two images and the `.dev-data/candidate`
  clone stay on the machine for ER-L3/ER-L4/ER-G10; the scratch clone
  carries the venv the soak runs from and must not be deleted before the
  soak ends (`soak/started-at.txt` + 8 h).
- The tag is local; push it (`git push origin enterprise-candidate-2026-09-03`)
  when the branch is pushed so CI and other clones see the same identity.
