# Enterprise-testing readiness execution

Base: `ba97a89899440532686b08050127d48db9a509b9`
Plan: `docs/superpowers/plans/2026-09-01-enterprise-testing-readiness-execution.md`

| Task | Status | Implementer | Reviewer | Evidence |
| --- | --- | --- | --- | --- |
| 1. Truthful green development baseline | complete | Codex implementer | Codex reviewer: approved | Baseline 10+10 preserved; audit 0 failures; ledger complete; Ruff clean; backend 119 passed; frontend 113 passed; YAML loaded; independent re-review approved |
| 2. Remove external filing acquisition dependencies | complete | Codex implementer | Codex reviewer: approved | CP-4 and CP-1C acquisition lanes removed; prohibition scans every tracked CAOS file; build `1912cb0`; 26 tests pass; bundle current; 26 modules/0 drift; independent re-review approved; report: `enterprise-task-2-report.md` |
| 3. Remove external font dependency | complete | Codex implementer | Codex reviewer: approved | Native CSS font stacks; recursive shipped-file guard; all-context journey guard; restricted offline build passed; frontend 116 passed; workbench DCL 48.9 ms/FCP 124 ms with zero Google font requests; implementation `92626bf`; correction `3806c72`; report: `enterprise-task-3-report.md` |
| 4. Close resource leaks | complete | Codex implementer | confidence review complete; independent review pending | Zero first-party ResourceWarnings; full strict backend 666 passed/2 skipped; lifecycle hardening `209b2df` verified by 61 strict focused passes (2 PostgreSQL skips; one third-party Starlette deprecation), including real Anthropic close, error precedence, and bounded foreign-loop drain; Ruff/diff clean; prior entrypoint/cross-loop correction `6550449`; implementation `0cfcc64`; scheduling correction `c506808`; report: `enterprise-task-4-report.md` |
| 5. Provider authority and false-success removal | pending | — | — | — |
| 6. Distressed pathway | pending | — | — | — |
| 7. Deep Research pathway | pending | — | — | — |
| 8. Documents-only journey | pending | — | — | — |
| 9. Source-complete modelling | pending | — | — | — |
| 10. Opinion, publication, reconstruction | pending | — | — | — |
| 11. Corpus and live matrix | pending | — | — | — |
| 12. Stress, recovery, security, capacity | pending | — | — | — |
| 13. Candidate qualification | pending | — | — | — |
