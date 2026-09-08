# Validated audit fixes implementation plan

> For agentic workers: use subagent-driven-development for delegated tasks and execute the validated remediation task by task. The user authorized applying fixes; no additional execution-choice prompt is needed.

Goal: repair the supported defects in audit-findings-validation.md at f72e7bb without implementing rejected findings or speculative architecture.
Architecture: preserve the existing service, storage and wire boundaries; add early bounds and typed refusals, keep transactional authority and immutable evidence, repair actual test coverage.
Tech stack: Python 3.14, FastAPI/SQLAlchemy/LangGraph, Next.js static export, existing pytest and Node/Playwright checks.

## Global constraints

- Every read_evidence fails closed without evidence on refusal.
- Preserve source-set pins, commit-time standing, exactly-once transitions, pure finite calculations and provider reservations.
- Preserve existing APIs where possible; record intentional wire changes and update named response models/spec expectations together.
- Keep Markdown renderer and offline verifier renderer synchronized.
- Preserve legitimate multiline narrative and meaningful Unicode format characters; reject invalid metadata at admission.
- Generated dependency locks come from pyproject.toml; no runtime dependency is added unless existing/platform facilities cannot cover the required behavior.
- No code or input-report edits outside this worktree, no commits/push/merge/deploy required by the user. Do not change live cases, services or credentials.
- TDD for behavioral fixes; run focused checks, then integrated checks once. Run rewrite-tournament post-edit on material changed functions and confidence-review before completion.
- The root owns CLAUDE.md, SPEC_RECONCILIATION.md and docs/DECISIONS.md updates; delegate reports proposed documentation changes to avoid overlapping edits.

## Task 1: Frontend, browser checks, quality ledger, workflow hygiene

Owner: one fresh implementer subagent. Files: caos/frontend/**, docs/quality_ledger_coverage.py, docs/PERIMETER_LEDGER.csv, .github/workflows/**, tests specifically covering these scripts/workflows.
- [x] Fix D43 six unmapped scripts with truthful existing feature mappings.
- [x] Fix D35 misleading authorization-404 wording while preserving uniform server 404 privacy; D37 wrap malformed successful responses as a safe unexpected-response failure.
- [x] Fix D45 true fixture/self-comparison and missing-positive-anchor issues, preserving valid response-contract/DOM/hash assertions and NOT_READY preconditions.
- [x] Fix D46 early observation/final assertions; D47 assert intended axe scan states and retain incomplete results; D48 empty engine input and bounded child/waiter lifetimes.
- [x] Address D44 actual unique unenforced regression coverage using the existing runner/gates. Unsupported deployment inventory/live qualification stays explicitly manual; do not blindly wire unusable or redundant scripts or delete retained evidence.
- [x] Fix D49 stale script/ledger claims in owned files and D58 credential persistence configuration. Report CLAUDE corrections to root.
- [x] Test with existing Node units, type/lint/build and relevant scripts; perform rewrite-tournament and confidence-review; write /tmp/audit-fixes-frontend-report.md. Leave full browser execution to root unless coordinated.

## Task 2: Intake, extraction and source metadata

Owner: root. Files: sources/domain.py, intake/service.py, contracts.py and existing ingestion/intake specs.
- [x] D1: ZIP detection must match zipfile acceptance for prepended data while malformed PK archives still refuse.
- [x] D2: enforce the intended safe XML behavior on workbook ingestion using a verified parser boundary; correct the backend comment.
- [x] D3/D4: bound PDF accumulation/pages and parser work; turn nested JSON errors into typed refusal, preserve no-text-layer fallback only for intended extraction failures.
- [x] D6: bound aggregate HTTP body and intake retained content without leaking partial admission.
- [x] D12/D13/D14/D50: bounded normalized filename/media metadata and derived case fields; retain intentional CR/LF/TAB semantics in general text; reject DEL/C1, no blanket Cf ban.
- [x] Add exact regression cases from the validation report, assert rollback/byte/field bounds, run focused suites.

## Task 3: Engine, APIs, authorization, storage and operation

Owner: root, later bounded implementation/review delegations may assist after Task 1.
- [x] D5/D54: share truthful full-manifest accounting at gate/admission and pre-provider checks; no small-document locator rewrite or increased arbitrary limits.
- [x] D7/D36: remove avoidable full evidence/event transfer from normal UI paths and bound supported listing contracts explicitly; avoid silent truncation.
- [x] D8/D9/D10/D28: bound health probing occupancy, cover actual synchronous model paths, safely reclaim lock bookkeeping.
- [x] D15/D16/D17/D31: deliberate safe validation/code mapping for known refusals and fallback, add authorized-negative perimeter cases.
- [x] D19/D21: stream revocation and empty-secret defense at its own boundary.
- [x] D23: bound reference session staleness without claiming unverified live IdP behavior.
- [x] D30/D33/D56: validated worker polling, observable post-accept queue failure, acquire process ownership before avoidable schema work.
- [x] D38/D49/D59: correct stale contract comments; preserve the passing image integrity gate.
- [x] Keep D18/D20/D22/D27/D29/D34/D39/D42/D51/D52/D53/D55/D57 and speculative S changes at their validated scope, without applying rejected fixes.

## Task 4: Publication and invariant proof

Owner: root or one later fresh implementer.
- [x] D11: escape plain Markdown metadata including CR/LF, keep offline verifier exact and existing narrative semantics/old package verification.
- [x] D25/D26: re-host named proofs onto production paths and remove dead permissive helpers when callers permit it.
- [x] D40/D41: apply only concrete configuration/retention corrections justified by existing behavior; no secret-format or same-origin encryption theater.
- [x] Record wire/policy changes and tests in docs/DECISIONS.md and update current contract documentation.

## Task 5: Integrated review and validation

- [x] Review each task diff against the validated requirement; repair confirmed issues.
- [x] Run post-edit rewrite-tournament (2 material symbols per pass; name skips), final broad independent code review, and confidence-review of boundaries/concurrency/rollback/error paths.
- [x] Run appropriate backend suite, frontend checks/browser journeys, security audit, quality ledger and diff checks, without simultaneous full ecosystems.
- [x] Write concise audit-fixes-status.md mapping every finding to fixed, retained by design, or externally unverifiable, with actual tests.


Completed: see audit-fixes-status.md for all 59 dispositions, exact verification
results, the untouched-base backend failure and retained axe incomplete records.
No commit, push or deployment was performed.
