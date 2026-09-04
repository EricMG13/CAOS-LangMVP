# Candidate 2026-09-04-b88c0f8 — evidence index

Frozen by ER-G9 on 2026-09-04 (00:26 BST) at `b88c0f8` (tag
`enterprise-candidate-2026-09-04`), the commit that repaired the capacity
harness after candidate `2026-09-03-c4f0270` (superseded; its own index says
why). Identity: `MANIFEST.json` (sha256 in `MANIFEST.sha256`). Narrative and
quoted results: `.superpowers/sdd/enterprise-task-13-report.md`, section
"Candidate 2026-09-04-b88c0f8". Nothing in this directory comes from another
commit, image, corpus version, binding or environment.

| Gate | Artifact(s) | Result |
| --- | --- | --- |
| Ruff | `gates/ruff.txt` | All checks passed |
| Route security audit | `gates/sec-audit.txt` | 59 routes, 507 cells, 20 cross-case probes, 0 failures |
| Quality ledger | `gates/quality-ledger.txt` | 54 routes, 354 product files, 134 features documented |
| Deploy assets | `gates/deploy-assets.txt` | shell syntax, Compose config (raw and filled example), secrets empty, 26 modules 0 drift |
| Backend suite with PostgreSQL | `gates/pytest-backend.txt`, `gates/pytest-backend-junit.xml` | 1242 passed, 1 skipped (nightly-only cell), 0 failures |
| Two-connection races, instance locks, harness tests | junit above | 27 + 49 + 6 passed, 0 skipped |
| SIM-001–030 | `gates/sim-evidence.json`, `gates/sim-evidence.csv`, `gates/sim-evidence-summary.txt` | 30/30 PASS, 67 tests, 0 missing |
| Corpus host control (all routes, both depths) | `gates/corpus-full.txt`, `gates/pytest-corpus-full-junit.xml` | 35 passed (orchestration proof) |
| Host-control qualification matrix | `gates/qualification/host-control-matrix.txt`, `host-control-verdict.txt`, `evidence/host_control/**` | 32 pass, 5 BLOCKED EXTERNAL (C20/C21/C22); ORCHESTRATION_PROOF_INCOMPLETE |
| Frontend lint/tsc/unit/build | `gates/frontend.txt`, `gates/frontend-unit.txt` | all exit 0; 123 unit tests |
| Image resources | `gates/scans/images.txt` | app and worker: 310 bundle files, 0 mismatches; `/app` carries only the tracked tree |
| Trivy, SBOM, fixable HIGH/CRITICAL gate | `gates/scans/trivy-*.json`, `sbom-*.cdx.json`, `trivy-*-fixable-gate.txt` | 181/324 packages, 182/325 components, gate exit 0 |
| pip-audit, bandit, npm audit | `gates/scans/pip-audit.json`, `bandit.json`, `npm-audit.json`, `dependency-and-sast.txt`, `npm-audit.txt` | 57 deps clean; 21 632 lines scanned; 409 deps 0 high/critical (first `npm audit` hit a registry timeout; the rerun is retained) |
| gitleaks (v8.18.4 by digest) | `gates/scans/gitleaks.log`, `gitleaks.txt` | 209 commits, no findings |
| Scan manifest | `gates/scans/scan-manifest.json` | 8 reports bound to 3 image ids at b88c0f8 |
| Accessibility | `gates/browser/a11y-rerun.txt` (the one run; stack empty, quiet machine) | 75 combinations, 0 violations |
| Three-engine journey | `gates/browser/browser-gates.txt`, `smoke-*.log`, `test-results/<engine>/workbench-report.json` | chromium, firefox, webkit passed; no console errors |
| Limits over HTTP | `gates/stack/capacity-limits.json`, `stack-gates.txt` | PASS ×7, NOT_EXERCISED ×1 (edge request bytes) |
| Backup and restore | `gates/stack/backup-manifest.txt`, `stack-gates.txt` | backup exit 0 in 1 s (paused writers); restore drill passed |
| Single instance, kill and recover, reset | `gates/stack/stack-gates.txt` | INSTANCE_ALREADY_RUNNING; health back 11 s, counts unchanged; reset to 31 empty tables |
| Post-reset golden journey = pre-soak journey | `soak/pre-soak-reset-and-journey.txt`, `soak/pre-soak-journey/chromium/` | chromium passed 140 161 ms |
| Soak attempt 1 at the declared 100 documents per case (stopped, retained) | `soak/attempt-1-manifest-ceiling/` | harness healthy (0 tracebacks, 10,000 distinct uploads admitted) but every run refused typed `AGENT_BUDGET_EXCEEDED` at CP-PARSE: 2,139 blocks + 100 source rows per case exceed the 2,000-row manifest ceiling; stopped at 9 min |
| Soak attempt 2 (COMPLETE, 8 h; `soak/profile/profile.json`) | `soak/soak-launch.txt`, `baseline-pre.json`, `pre-soak-authority.json`, `pre-soak-reset-and-journey.txt`, `pre-soak-journey/chromium/`, `profile.log`, `profile/samples.jsonl`, `profile.pid`, `started-at.txt`, `soak.sh`, `authority_snapshot.sh` | started 2026-09-04T00:19:33Z, pid 56830; 25 subjects / 20 jobs / 4 streams / 2 previews / 300 rpm, 100 cases × **80** documents (largest round count under the manifest ceiling), worker hard-restart every 2 h; finished 2026-09-04T08:20Z: leakage [], 3 restarts, 631 samples, 6,291 runs accepted, no driver_error, no traceback; finding: clamd OOM-killed at 03:31Z and never restarted (container up, unhealthy) — ER-L4 owes the post-soak comparison and journeys after logging that restart |
| Reviews | `reviews/REV-001.md` … `REV-015.md` | prepared, OUTSTANDING |
| Release evidence package (ER-G10, 2026-09-04) | `package/PACKAGE_MANIFEST.json`, `package/PACKAGE.sha256`, `package/checks.csv`, `package/loops/`, `package/ledgers/`, `package/corpus/`, `package/inventory/`, `package/assemble_package.py`, `package/verify_evidence_package.py` (the driver `qa/golden_journeys.py` is pinned by sha256 in the manifest) | 340 checks mapped (222 PASS, 29 PROVED HOST CONTROL, 17 BLOCKED EXTERNAL, 71 OPEN, 1 FAIL); every object hashed and re-verified on a separate copy; `signable: false` — see `.superpowers/sdd/enterprise-task-13b-report.md` |
