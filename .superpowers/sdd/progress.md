# Enterprise-testing readiness execution

Base: `ba97a89899440532686b08050127d48db9a509b9`
Plan: `docs/superpowers/plans/2026-09-01-enterprise-testing-readiness-execution.md`

| Task | Status | Implementer | Reviewer | Evidence |
| --- | --- | --- | --- | --- |
| 1. Truthful green development baseline | complete | Codex implementer | Codex reviewer: approved | Baseline 10+10 preserved; audit 0 failures; ledger complete; Ruff clean; backend 119 passed; frontend 113 passed; YAML loaded; independent re-review approved |
| 2. Remove external filing acquisition dependencies | complete | Codex implementer | Codex reviewer: approved | CP-4 and CP-1C acquisition lanes removed; prohibition scans every tracked CAOS file; build `1912cb0`; 26 tests pass; bundle current; 26 modules/0 drift; independent re-review approved; report: `enterprise-task-2-report.md` |
| 3. Remove external font dependency | complete | Codex implementer | Codex reviewer: approved | Native CSS font stacks; recursive shipped-file guard; all-context journey guard; restricted offline build passed; frontend 116 passed; workbench DCL 48.9 ms/FCP 124 ms with zero Google font requests; implementation `92626bf`; correction `3806c72`; report: `enterprise-task-3-report.md` |
| 4. Close resource leaks | complete | Codex implementer | Sol/XHigh phase gate: approved | Full strict backend: 687 passed, 2 PostgreSQL skips, one third-party Starlette deprecation; zero first-party ResourceWarning, RuntimeWarning, or unraisable-warning failures; focused lifecycle 65 passed; Ruff/diff clean; implementation through `24016e4`; proof `ceee0b1`; gate reviewed `d48c7d8`; report: `enterprise-task-4-report.md` |
| 5. Provider authority and false-success removal | complete | Codex implementer | Independent security + truth agents: approved | Full backend 766 passed; 2 PostgreSQL tests BLOCKED EXTERNAL; security audit 50/42 routes, 0 failures; Ruff/ledger/diff clean; qualified Anthropic-only production, guarded host control, same-loop lifecycle, minimal worker secrets; live qualification BLOCKED EXTERNAL; `enterprise-task-5-report.md` |
| 6. Semantic execution + Distressed pathway | complete (pending rebase gates) | Codex (WIP) + Claude Fable 5.1 (ER-G1) | adversarial review `enterprise-task-6-adversarial-review.md` (28 findings, decisions D1–D9 recorded) | Python 3.14.6; backend `945 passed, 2 skipped, 1 warning`; `run_sec_audit.py` 50/42 routes, 0 failures; ledger complete (45 routes, 232 files); `CORPUS_FULL=1` host control `34 passed` (every route, both depths, through ordinary `start_run`); Ruff clean; frontend lint/tsc/unit (116) /build pass; browser gates rerun after the rebase; report: `enterprise-task-6-report.md` |
| 7. Deep Research pathway | pending | — | — | — |
| 8. Documents-only journey | pending | — | — | — |
| 9. Source-complete modelling | pending | — | — | — |
| 10. Opinion, publication, reconstruction | pending | — | — | — |
| 11. Corpus and live matrix | pending | — | — | — |
| 12. Stress, recovery, security, capacity | pending | — | — | — |
| 13. Candidate qualification | pending | — | — | — |
