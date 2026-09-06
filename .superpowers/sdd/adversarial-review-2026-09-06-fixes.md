# Adversarial review 2026-09-06 — fixes

Branch `worktree-fe-followup` from `main` at `18dccbb`; worktree `fe-followup`. Review:
`.superpowers/sdd/adversarial-review-2026-09-06.md` (34 findings: 2 CRITICAL, 19 WARNING, 13 NOTE).
The user said "Proceed": fix the criticals and every contained warning, record what stays open.

## Scope decision

Fixed in this pass: **C1, C2, W1–W8, W10–W13, W17–W19**, and the notes **S9, X3, X4, N12–N15**.
Left as recorded follow-ups, each a multi-hour refactor with a wide blast radius that deserves its
own reviewed change: **W9** (a `TypedRefusal` across 109 `ValueError` sites), **W14** (Credit wired
to the case record plus a lens key set), **W15** (rewriting the source-regex unit tests), **W16**
(relocating 76 `_for_tests` seams), **N16/N17** (naming and typing), **X5** (a Caddy rate limit needs
the `rate_limit` plugin), **X7** (a counting decompressor for archive admission), **X8**
(recovery-copy pruning policy).

## How the work ran

Four fix agents were dispatched in parallel on disjoint file sets. All four were killed mid-task by
the account's monthly spend limit (API 429 on `claude-fable-5-1`); the frontend agent had finished
and its work is green, the other three had written their test files but no implementation. This
session (Opus 5) finished the implementations against those tests, which made the whole remainder
genuinely test-first: every test below was written before the code that satisfies it existed.

## Dispositions

| Finding | Fix | Files | Test |
|---|---|---|---|
| **C1** startup recovery replayed every stranded run before the socket bound | Under the serving entrypoint (auto-continue on) a stranded run is re-driven as a background continuation, so the socket binds now and readiness answers while it executes; without auto-continue the drive stays inline, so `await engine.recover()` still leaves the run terminal for tests and tooling | `engine/runtime.py` (`recover`, `_recover_drive`, `_recover_run`) | `test_adversarial_fixes_spec.py`: recovery returns in <2 s with 0 provider calls and one scheduled continuation; the inline contract still holds without auto-continue |
| **C2** `MemberRequest.subject` was a bare `str` reaching the hash-chained audit row | The field is `NonBlankBoundaryText`; the identity edge recovers the edge's UTF-8 bytes from Starlette's latin-1 decode, refuses non-UTF-8 identity bytes with 401, and presents one NFC subject so stored standing and presented identity compare equal | `contracts.py`, `identity.py` | `test_membership_boundary_spec.py`: bidi override, control byte and lone surrogate each 422 with nothing echoed; an NFD subject stores and audits NFC and both spellings authenticate as the one member |
| **W1** admission ran the scan, extraction and vault fsync on the event loop | The synchronous half is `_admit_content`, run through `asyncio.to_thread` (DECISIONS §10.8) | `sources/domain.py` | `test_source_admission_fixes_spec.py`: the loop still turns ≥10 times during a 0.5 s admission, single-source and whole-pack |
| **W2** a refused intake pack left every prepared document orphaned in the vault | `prepare_upload` reports `published_now`; the intake collects what this submission published and discards it on any refusal, the single-source route the same, and bytes another case owns survive | `sources/domain.py` (`Vault.holds`, `Vault.discard`), `intake/service.py` | same spec: three refusal classes leave no unreferenced vault file; a shared document survives; a failed commit unpublishes only this pack's bytes |
| **W3** the visible-lens switch committed pointer and audit row separately | One `DomainStore.switch_visible_snapshot` doing both inside one transaction | `engine/runtime.py`, `storage/store.py` | `test_adversarial_fixes_spec.py`: with the audit insert failing the pointer does not move; the retry moves it with exactly one audit row |
| **W4** `pack_blocks` was not bounded by line shape (a ledger line was false) | A fragment that does not fit is split at the group's width instead of taking a block of its own; every block but the last is full to within `width/BLOCK_SLACK_DIVISOR` | `sources/domain.py` | same spec: eight line shapes bounded, evidence tiles the document, ids/locators/`builtin-v1` path unchanged, two and three worst-shape 12 MB documents pin one run |
| **W5** any non-`AgentError` stranded a run `running` forever | A dead continuation is retried on a bounded backoff and then failed closed as `RUN_EXECUTION_FAILED`, releasing the admission slot and emitting the terminal event | `engine/runtime.py` (`_schedule_continuation`) | `test_adversarial_fixes_spec.py`: a permanently locked store fails the run after its retries; a transient fault recovers on retry |
| **W6** `POST /resume` queued behind a held thread for the rest of the run | The resume refuses with `RESUME_NOT_APPLIED` when the run's thread lock is held; the route serves a typed 409 | `engine/runtime.py`, `api/__init__.py` | `test_adversarial_fixes_spec.py`: the refusal returns in <1 s while the run is executing, and maps to 409 |
| **W7** only `/models/previews` had a concurrency slot | Five synchronous calculation routes share the one ceiling; the misleading docstring corrected | `api/__init__.py` (`CALCULATION_PATHS`) | `test_limits_spec.py`: below/at/above per route, one shared counter, and only these five plus the events tail are slotted |
| **W8** an approver could self-promote or demote the last admin | `add_member` refuses a self role change and the demotion of the case's last ADMIN, typed, inside the transaction that would have written the audit row | `storage/store.py` | `test_membership_boundary_spec.py`: both refusals write nothing; an admin still demotes an approver and an approver still provisions one |
| **W10** the run failure shape was `Any` on the wire | A named `RunErrorResponse` (`code`, `module_id`, `message`) on the run and each node; `_finalize_node` keeps the blamed module; the client types it and renders the code, the module's registry name and the host's sentence only when sent | `responses.py`, `engine/runtime.py`, `src/lib/api.ts`, `src/components/Workspace.tsx` | `test_adversarial_fixes_spec.py` (the finalization refusal names CP-5; the wire model refuses undeclared keys) |
| **W11** a missing publication golden was created and compared with itself | A missing golden fails unless `CAOS_REGENERATE_GOLDENS=1`; the golden file set is pinned to `STATES × formats` | `test_publication_goldens_spec.py` | the two new module-level tests |
| **W12** the renderer version lived in the service, not the renderer | `RENDERER_VERSION` declared in `publishing/renderers.py` and imported by the service | `publishing/renderers.py`, `deliverables/service.py` | goldens spec: every Markdown and XLSX golden carries exactly that version |
| **W13** `_wire_case` spread the row, so a new column 500s every case route | An explicit projection of the nine `cases` columns plus `members` | `api/__init__.py` | `test_api_hardening_spec.py`: a case row carrying an extra column still wires to the pinned key set |
| **W17** every config default existed twice | `from_env` passes only the values a deployment set; the range checks run on the effective values; `ENV_NAMES` lists what it reads | `config.py` | `test_limits_spec.py`: `from_env() == Settings()` with nothing set, no `os.getenv` default anywhere, every range message preserved |
| **W18** client ceilings were bare literals; the drawer copy became wrong | Every cited block is shown and only the uncited remainder capped (`UNCITED_BLOCK_PREVIEW`), with truthful copy; `BRIEF_LIMITS` counts code points and names the server as its source; `EXPORT_POLL_MS`, `SOURCE_READER_BLOCK_PREVIEW`, `ARTIFACT_TABLE_MAX_ROWS` named | `WorkbenchShell.tsx`, `Workspace.tsx`, `ModelBuilder.tsx`, `lib/workbench.ts` | `workbench.test.ts` (`evidenceBlockPreview`, brief bounds), `ModelBuilder.test.ts` pin moved to the constant |
| **W19** README described four pathways and deterministic screen executors | Rewritten from `MVP_PATHWAYS` and DECISIONS §14.3/§14.12 | `README.md` | — (documentation) |
| **S9** an out-of-range `Last-Event-ID` raised inside the SSE generator | `_event_cursor` clamps to `[0, MAX_EVENT_CURSOR]` and treats anything else as the start | `api/__init__.py` | `test_api_hardening_spec.py`: five malformed cursors replay from the start, the ceiling closes the tail, an ordinary cursor still resumes |
| **X3** the offline verifier inflated every member before checking its size | A member is refused unread when its declared size exceeds the manifest's plus a margin, and every read is capped; refusals are findings, not exceptions, so a crafted package is reported rather than fatal | `audit/verify_package.py` | `test_verify_package_bounds.py` (4 tests); the six existing tamper classes still convict |
| **X4** two routes reflected `str(exc)` | Typed `{"code": …}` bodies (`SOURCE_CONTENT_ALREADY_ACTIVE`, `RUN_REQUEST_INVALID`) | `api/__init__.py` | `test_api_hardening_spec.py`: neither refusal carries the exception text |
| **N12/N13/N15** CLAUDE.md miscounted open envelopes, named registry fields the dataclass lacks, and said seven log points | Corrected to eleven `OpenWireModel` subclasses, the real `ModuleSpec` fields, and seven kinds of log point (seventeen names) | `CLAUDE.md` | — (documentation) |
| **N14** pre-Align vocabulary in analyst-facing copy | "Drop documents on Portfolio"; CP-PARSE and CP-DR named from the registry; the stale comment corrected | `Workspace.tsx`, `workbench-smoke.mjs`, `lib/workbench.ts` | the smoke's pinned sentence changed in the same commit |
| **W4 ledger** | The CLAUDE.md "three 12 MB credit agreements" line now records that it was false until this fix, with the measured figures (600 blocks for 10k-character lines, 625 for 1k, three per manifest) | `CLAUDE.md`, `sources/domain.py` | the spec above |

## Gates

All on the final tree, quoted from this session:

| Gate | Result |
|---|---|
| Backend suite (`pytest caos/tests -q -p no:cacheprovider`) | `1247 passed, 33 skipped, 1 warning in 1245.63s` (1,215 before this pass; 32 new tests) |
| Ruff (`ruff check --config ruff.toml caos/server caos/tests --exclude …/vendor`) | `All checks passed!` |
| Perimeter gate (`python run_sec_audit.py`) | `{'audited_routes': 59, 'matrix_cells': 507, 'cross_case_probes': 20, 'failures': 0}` |
| Quality ledger (`python docs/quality_ledger_coverage.py`) | `routes checked: 54   product files: 375   features: 134` — the ledger documents every route and product file |
| Frontend (`npm run lint`, `npx tsc --noEmit`, `npm run test:unit`, `npm run build`) | ESLint no issues; TypeScript no errors; 144 tests, 144 pass (141 before); 20/20 static pages |
| Accessibility sweep (`npm run a11y`, fresh host-control server on `:8794`) | `{"routes":17,"forwarders":8,"viewports":6,"combinations":125, … "violations":0}` |
| Workbench smoke, three engines (`npm run test:workbench`) | chromium 151.0.7922.34 passed 140,760 ms · firefox 153.0 passed 152,669 ms · webkit 26.5 passed 150,706 ms |

Two failures surfaced on the first full-suite run and were fixed as the paired updates the changes
require, not by weakening them: `test_distinct_duplicate_note_promotion_is_a_structured_source_conflict`
pinned the old untyped `detail` string (X4 makes it a typed code, which is what the test's own name
asks for), and `docs/PERIMETER_LEDGER.csv` named `test_preview_ceiling_at_and_above_is_per_subject_and_returned`,
which W7 replaced with the parametrized `test_calculation_ceiling_at_and_above_is_per_subject_and_returned`
(3 references updated). The rerun after both was clean.

## Confidence review

Points investigated after the code was written, each to its root cause:

1. **A continuation retry timer firing after `aclose()`** — `_schedule_continuation` read the run's
   status before checking the lifecycle, so a `call_later` retry landing after shutdown would touch a
   closed store. Fixed: the closing check runs first, before any store read.
2. **A manifest too large to read** — `Package.json` returns `None` for a refused member, and
   `verify()` called `.get` on it, so a >64 MiB manifest raised `AttributeError` instead of reporting.
   Fixed: `package.json("manifest.json") or {}`.
3. **The size margin** — refusing every member larger than declared broke two existing tamper classes
   (`export_bytes`, `frozen_payload` grow a member by a few bytes and must still be convicted by
   digest). Root cause understood rather than patched around: a bomb is orders of magnitude larger, so
   `MEMBER_SIZE_MARGIN` separates the two and both behaviours hold.
4. **Every `resume` caller** — the API route plus five spec tests, all resuming a paused run whose
   thread is free; the refusal only fires when the lock is held. Confirmed by the full suite.
5. **Duplicate bytes inside one intake pack** — the second document sees `Vault.holds` true, so
   `published_now` is False and a refusal discards the digest once. Covered by the shared-document test.
6. **`finalize_failure` on a run that does not exist** — the conditional update matches nothing and
   returns False, so the existing continuation-failure test still sees exactly one log line.

Not done, and why: the four large refactors listed under "Scope decision" — each would touch far more
than the finding it closes, and mixing them into this change would make it unreviewable.

## Commands
