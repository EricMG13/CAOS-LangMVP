# Candidate 2026-09-03-c4f0270 — evidence index

> **SUPERSEDED** on 2026-09-03T23:20Z by the next candidate: the decision owner chose to repair the capacity
> harness (`qa/capacity.py`) now, which is a code change and therefore a new candidate. Soak attempt 3 was
> stopped at 2 h 18 m (200 samples, retained under `soak/attempt-3-superseded/`); its stack and volumes were
> removed. Nothing here is combined with the next candidate's evidence.

Frozen by ER-G9 on 2026-09-03. Identity: `MANIFEST.json` (sha256 in
`MANIFEST.sha256`). Narrative and quoted results:
`.superpowers/sdd/enterprise-task-13-report.md`. Nothing in this directory
comes from another commit, image, corpus version, binding or environment.

| Gate | Artifact(s) | Result |
| --- | --- | --- |
| Ruff | `gates/ruff.txt` | All checks passed |
| Route security audit | `gates/sec-audit.txt` | 59 routes, 507 cells, 20 cross-case probes, 0 failures |
| Quality ledger | `gates/quality-ledger.txt` | 54 routes, 353 product files, 134 features documented |
| Deploy assets | `gates/deploy-assets.txt` | shell syntax, Compose config (raw and filled example), secrets empty, 26 modules 0 drift |
| Backend suite with PostgreSQL | `gates/pytest-backend.txt`, `gates/pytest-backend-junit.xml` | 1236 passed, 1 skipped (nightly-only cell), 0 failures |
| Two-connection races, instance locks | junit above | 27 + 49 passed, 0 skipped |
| SIM-001–030 | `gates/sim-evidence.json`, `gates/sim-evidence.csv`, `gates/sim-evidence-summary.txt` | 30/30 PASS, 67 tests, 0 missing |
| Corpus host control (all routes, both depths) | `gates/corpus-full.txt`, `gates/pytest-corpus-full-junit.xml` | 35 passed (orchestration proof) |
| Host-control qualification matrix | `gates/qualification/host-control-matrix.txt`, `host-control-verdict.txt`, `evidence/host_control/**` | 32 pass, 5 BLOCKED EXTERNAL; ORCHESTRATION_PROOF_INCOMPLETE |
| Frontend lint/tsc/unit/build | `gates/frontend.txt`, `gates/frontend-unit.txt` | all exit 0; 123 unit tests |
| Image resources | `gates/scans/images.txt` | app and worker: 310 bundle files, 0 mismatches |
| Trivy, SBOM, fixable HIGH/CRITICAL gate | `gates/scans/trivy-*.json`, `sbom-*.cdx.json`, `trivy-*-fixable-gate.txt` | 181/390 packages, 182/391 components, gate exit 0 |
| pip-audit, bandit, npm audit | `gates/scans/pip-audit.json`, `bandit.json`, `npm-audit.json`, `dependency-and-sast.txt` | 57 deps clean; 21 632 lines scanned; 409 deps 0 high/critical |
| gitleaks (v8.18.4 by digest) | `gates/scans/gitleaks.log`, `gitleaks.txt` | 207 commits, no findings |
| Scan manifest | `gates/scans/scan-manifest.json` | 8 reports bound to 3 image ids at c4f0270 |
| Accessibility | `gates/browser/a11y.txt` (first run, under load: 2 moderate), `a11y-rerun.txt` (quiet: 0) | 75 combinations, 0 violations on the retained rerun |
| Three-engine journey | `gates/browser/browser-gates.txt`, `smoke-*.log`, `test-results/<engine>/workbench-report.json` | chromium, firefox, webkit passed; no console errors |
| Limits over HTTP | `gates/stack/capacity-limits.json`, `stack-gates.txt` | PASS ×7, NOT_EXERCISED ×1 (edge request bytes) |
| Backup and restore | `gates/stack/backup-manifest.txt`, `stack-gates.txt` | backup exit 0 (paused writers); restore drill passed |
| Single instance, kill and recover, reset | `gates/stack/stack-gates.txt` | INSTANCE_ALREADY_RUNNING; health back 12 s, counts unchanged; reset to 31 empty tables |
| Post-reset golden journey | `gates/stack/post-reset-journey.txt`, `post-reset-test-results/chromium/` | chromium passed |
| Soak attempt 1 (aborted) | `soak/attempt-1-aborted/` | reader at 300 rpm starved the job drivers (5 of 20 dead in 3 min); stopped, retained |
| Pre-soak reset and golden journey (before attempt 3) | `soak/pre-soak-reset-and-journey.txt`, `soak/pre-soak-journey/chromium/` | reset to empty; chromium passed 138 156 ms |
| Soak attempt 2 (aborted) | `soak/attempt-2-aborted/` | `--rpm 200`: all 20 drivers, 3 stream holders and the sampler dead on 429s within 11 min; stopped, retained; PERF-013 at the declared profile OPEN |
| Soak attempt 3 (in progress, reduced profile) | `soak/soak-launch.txt`, `baseline-pre.json`, `pre-soak-authority.json`, `profile.log`, `profile/samples.jsonl`, `profile.pid`, `started-at.txt` | started 2026-09-03T21:02:31Z, pid 26509, `--streams 0 --rpm 100`, everything else declared; ER-L4 watches and closes it |
| Reviews | `reviews/REV-001.md` … `REV-015.md` | prepared, OUTSTANDING |
