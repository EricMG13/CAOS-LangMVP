# CAOS adversarial security audit — findings (Security Auditor persona; saved by the parent from the sub-agent's final message)

Scope: full app (FastAPI/LangGraph server, Next.js static export, Caddy + oauth2-proxy edge, worker, deploy), read-only worktree at `/Users/ericguei/Claude/Projects/CAOS-LangMVP/.claude/worktrees/fe-followup`.

**Counts: CRITICAL 0 · WARNING 2 · NOTE 6.**

The authorization perimeter is genuinely strong: the repo's own gate `run_sec_audit.py` passes here (`{'audited_routes': 59, 'matrix_cells': 507, 'cross_case_probes': 20, 'failures': 0}`, exit 0), and every case/run-scoped route enforces membership + write-standing through `require_case`/`visible_run`, with the run→case→member chain closing the "run id without a case id" IDOR. No CRITICAL survives the edge + matrix.

## X1 — Uncapped synchronous model computations exhaust the shared threadpool — WARNING · CONFIRMED (code) / PLAUSIBLE (magnitude)
- `caos/server/caos/api/__init__.py:181-187` (`RequestCeilings._slot`); endpoints `:1069` rebase-preview, `:1079` scenarios, `:1087` tornado, `:1095` one-way; deadline `caos/server/caos/models/service.py:138` (`MAX_CALCULATION_SECONDS = 30.0`).
- Claim: the per-subject concurrency ceiling covers only `/models/previews`, but `/models/scenarios`, `/models/tornado`, `/models/sensitivities/one-way`, `/model-revisions/rebase-preview` run the same 30 s-deadline model calculation synchronously with no concurrency ceiling — only the shared 300/min token bucket.
- Attack: an authenticated ANALYST in any one case with a READY build fires many concurrent `POST /models/tornado` (tornado runs ~1 + 2×drivers `_calculate` calls, up to 30 s CPU per request). FastAPI runs these `def` handlers on the anyio threadpool (default 40); the token bucket (300 burst) admits far more than 40 concurrent. ~40 in-flight computations starve the threadpool that every synchronous route across all cases/subjects shares → tenant-wide hang of model/deliverable/source reads.
- Reproduction: code inspection. `_slot` returns a counter only for `.../models/previews` and `.../events`; `caos/tests/spec/test_limits_spec.py` tests only preview (`:213`) and stream (`:218`) ceilings. The `RequestCeilings` docstring's "the one expensive computation outside the queued-job admission ceiling" (`api/__init__.py:138-141`) is therefore false. Not in CLAUDE.md known gaps (which records only the *preview* ceiling).
- OWASP API4:2023 Unrestricted Resource Consumption.
- Fix: extend `_slot` (or a semaphore) to cap in-flight scenarios/tornado/one-way/rebase-preview per subject, as previews already are.

## X2 — `MemberRequest.subject` is a bare `str` reaching a hash-chained audit event — WARNING · CONFIRMED
- `caos/server/caos/contracts.py:156-158` (`MemberRequest.subject: str`); route `caos/server/caos/api/__init__.py:1135-1146`; audit write `caos/server/caos/storage/store.py:637` (`self._audit(conn, "case.member_added", actor, …, member=member, role=role)`).
- Claim: CLAUDE.md's standing "Boundary text" rule requires every string that enters pinned state or an event to be `BoundaryText`, "never a bare `str` … Bare `str` on a field that reaches … an audit event is a defect: it lets a control byte through … and it lets two spellings of one string mint two lineages." `MemberRequest.subject` is bare `str` and flows verbatim into the per-case hash-chained `case.member_added` event and `case_members.subject`.
- Attack: a case APPROVER/ADMIN provisions a member subject carrying U+202E RIGHT-TO-LEFT OVERRIDE (CVE-2021-42574 "Trojan Source", the exact class `BIDI_CONTROLS` blocks everywhere else) or a raw control byte; it is written unmodified into the append-only audit chain and the offline audit package, misrepresenting member/actor identity to a reviewer, and two non-NFC spellings mint two lineages.
- Reproduction (this tree's venv):
  ```
  MemberRequest ACCEPTED  subject='approver‮evil' role=ADMIN
  MemberRequest ACCEPTED  subject='line\x07bell' role=ADMIN
  CreateCaseRequest rejected issuer -> ValidationError   # BoundaryText
  NoteRequest       rejected body   -> ValidationError   # BoundaryText
  ```
  The same two payloads every BoundaryText field rejects are accepted on `subject`. (Related, lower risk: prod identity `subject`/`email`/`groups` at `identity.py:60-84` are also raw but come from the trusted OIDC edge.)
- Invariant: CLAUDE.md "Boundary text"; touches audit integrity (inv. 3/5). Not in known gaps; not covered by `run_sec_audit` (authz, not boundary text).
- Fix: type `MemberRequest.subject` as `BoundaryText` and NFC-normalize before the membership/audit write.

## X3 — Offline audit-package verifier has no decompression bound (zip-bomb) — NOTE · PLAUSIBLE
- `caos/server/caos/audit/verify_package.py:293-354` — `Package.bytes`→`archive.read(name)`; the verify loop reads `content = package.bytes(name)` *before* checking `len(content)` against the manifest size.
- Claim: the verifier runs on arbitrary packages a reviewer receives ("copy this file next to the zip on any review machine"), but fully decompresses every member into memory with no per-entry/total cap and checks size only after the read.
- Attack: an attacker hands a reviewer a file posing as a CAOS audit package with one highly-compressed member; `zipfile.read` inflates it and OOMs/kills the verifier before any digest/size check. Self-DoS of the defensive tool (does not touch the server).
- Reproduction: not reproduced (no crafted package built); the read-then-check ordering at `:343-349` is the gap.
- OWASP A05:2021 / decompression bomb.
- Fix: cap each `archive.read` at the manifest-declared size (+margin) and refuse an entry whose `file_size` exceeds a hard ceiling before reading.

## X4 — Exception strings reflected to the wire — NOTE · CONFIRMED
- `caos/server/caos/api/__init__.py:548` (`promote_note`: `detail=str(exc)`) and `:677` (`start_run`: `detail=str(exc)`).
- Claim: two routes return `str(exc)` in JSON `detail`, against the otherwise-consistent typed-code discipline (the validation handler at `:319-327` deliberately never echoes rejected input).
- Attack: today both carry host-owned messages, so nothing sensitive leaks; the risk is regression — a future `ValueError` on these paths quoting user/document input would be reflected verbatim.
- Reproduction: code inspection; no exploit today.
- OWASP A09:2021 / defense-in-depth.
- Fix: map to typed codes like every neighbouring handler.

## X5 — `/api/health` is unthrottled end to end — NOTE · CONFIRMED
- `caos/deploy/Caddyfile` (no `rate_limit`), `caos/deploy/oauth2-proxy.cfg:15` (`skip_auth_routes`), `caos/server/caos/identity.py:122` (`PUBLIC_PATHS`), skips at `api/__init__.py:130,191`, handler `:344-356`.
- Claim: `/api/health` is anonymous (oauth2-proxy skip + gate public) *and* exempt from the app rate ceiling, and Caddy has no edge rate limit, so an anonymous client can flood it unthrottled.
- Attack: sustained anonymous GET `/api/health` — each is a Caddy→app round-trip + JSON serialize + `_readiness_lock` acquisition. The *expensive* probes are TTL-capped to once per 5 s (`runtime.py:214`), which is recorded ("anonymous caller's to spend"); the incremental point is that the *request rate* itself is capped nowhere.
- Reproduction: config inspection; not load-tested.
- OWASP API4:2023.
- Fix: add a Caddy `rate_limit` on `/api/health`.

## X6 — Approver can provision an arbitrary, unverified subject at any case role — NOTE · CONFIRMED
- `caos/server/caos/contracts.py:156-158` (`MemberRequest`: free-form `subject`, `role` accepts READER/ANALYST/APPROVER/ADMIN); `storage/store.py:616-638` (`add_member`); route `api/__init__.py:1135-1146`.
- Claim: `add_member` never checks that `subject` maps to a real IdP identity and accepts any of the four case roles. The frontend offers only APPROVER/ADMIN (`Workspace.tsx:1976`), but the server accepts any `Role` and any string.
- Attack: a case APPROVER can provision a guessed/not-yet-existing OIDC `sub` as case ADMIN (latent standing that activates the instant that identity authenticates), and can set their own subject to `role=ADMIN`, self-promoting APPROVER→ADMIN. Global role still gates writes, so impact is case-scoped, but the surface is wider than the UI implies. Compounds X2 (same field is boundary-unchecked).
- Reproduction: code inspection + the X2 repro.
- OWASP API3:2023 / A01:2021.
- Fix: constrain `role` to the intended provisioning set at the model; treat provisioning of a never-authenticated subject as reviewable, or validate against the directory.

## X7 — Archive admission trusts the zip's own declared sizes — NOTE · PLAUSIBLE (mitigated downstream)
- `caos/server/caos/sources/domain.py:150-185` (`validate_archive`).
- Claim: the bomb guard sums `info.file_size` and divides by `info.compress_size` from the central directory — author-controlled values. An archive understating `file_size` passes both the ratio and the 100 MB total checks while decompressing to more.
- Attack: an authenticated writer uploads such a PK file. Mitigations are real and bound actual damage: `extract_blocks` caps XLSX at 25 000 rows / 64 cols and text at 12 MB (`:255-318`), openpyxl reads `read_only`, the loan importer re-screens (`artifacts/loan_universe.py:211-262`), and Caddy caps the request at 32 MB. The guard is advisory rather than authoritative.
- Reproduction: not reproduced; trust-declared-size logic at `:160-183`.
- OWASP A05:2021.
- Fix: bound actual inflation with a counting/limited decompressor rather than `file_size`.

## X8 — Report/opinion draft text persists in `localStorage` on shared workstations — NOTE · CONFIRMED
- `caos/frontend/src/components/report/reportRecovery.ts:80-103` (key scheme, `reportRecoveryKey` `:88-90`).
- Claim: crash-recovery copies of unsaved deliverable/opinion drafts are written to `localStorage`. Cross-subject *loading* is correctly isolated (key includes `subject`, `parseReportRecovery` re-checks it), but `localStorage` is per-origin: the blob (an analyst's unsaved credit opinion) stays readable via devtools by any co-user of the browser profile, and the code comment states abandoned copies are never pruned.
- Attack: on a shared institutional workstation, user B reads user A's prior unsaved opinion/rationale text from `localStorage`.
- Reproduction: code inspection; WEB-014 covers isolation of *loading*, not persistence at rest.
- OWASP A01:2021 client data-at-rest exposure.
- Fix: prune a subject's recovery entries on sign-out / successful save; consider `sessionStorage` for the sensitive text.

## Boundaries audited and found sound (coverage)
- Identity edge/header trust: prod role from OIDC groups only; `x-caos-role` ignored in prod and its use outside `identity.py` blocked by `recorded_review.py:75`; edge secret via `hmac.compare_digest`; duplicate trusted headers 401; Caddy strips inbound identity headers + injects secret; confusable/zero-width groups fall to READER; `EdgeIdentityGate` refuses unauth `/api/*` before body validation.
- AuthZ matrix / IDOR: `run_sec_audit.py` passes (59 routes / 507 cells / 20 cross-case, 0 failures). Every nested id re-checked against path `case_id`; `visible_run` gives the uniform 404; mass assignment refused (`StrictModel` extra=forbid).
- SQL injection: SQLAlchemy Core bound params throughout; f-string DDL uses only hardcoded column/table names.
- Path traversal / vault: `read_verified_vault_bytes` rejects `..`/absolute, `O_NOFOLLOW`+`dir_fd`, verifies dev/ino/size/sha; publish enforces `SAFE_ID_CHARACTERS`; export/download keys are server-minted ids.
- Subprocess (pango-view): fixed argv, no shell, hermetic fontconfig, `timeout=60`; all dynamic text `html.escape`d into Pango markup; XLSX refuses formula cells. Methodology `exec()` runs only the sha256-verified vendored bundle (inv. 4).
- Audit package/verifier: fixed object paths (no traversal), `_scrub` digests every `text` and drops `vault_path`; verifier never extracts to disk, recomputes chain/plan/snapshot/opinion/receipt digests, re-renders Markdown, enforces approver≠signer≠freeze-actor (decompression bound is X3).
- Prompt-injection/evidence: `engine/evidence.py` re-checks live authority every read, typed refusals with no text; pinned source set only; no web/acquisition lane.
- Observability: single `log_event`, host-owned scalars only, secrets registered + regex backstop, `MAX_STRING` truncation; worker logs exception class only.
- CSP/headers/CSRF: `SecurityHeaders` (outermost) on every response incl. refusals/downloads; `script-src 'unsafe-inline'` residual not reachable (no `innerHTML`/`dangerouslySetInnerHTML` sink; React escapes; exports render from frozen payload not HTML); no CORS; state-changing routes are POST/PUT JSON behind a SameSite=lax cookie.
- BREACH: authenticated JSON is gzipped and reflects attacker-influenced fields, but no secret is in any response body (httpOnly cookie, no CSRF token/API key echoed), so no secret to leak.
- Frontend routing: `RouteForwarder`/`withQuery` build only same-origin targets from fixed `forwardedRoutes`; role is display-only; browser never sends `x-caos-role`.
- Uploads: suffix allowlist, empty/oversize refusal, EICAR + prod clamav, OOXML external-rel/macro/DTD screening (expat, DOCTYPE refused), bounded extraction, content-addressed atomic write.
- Single-instance/audit chain: `flock` sidecar + PG advisory locks; append-only per-case hash chain with CAS head.

## Commands run
- CSV summary of `docs/PERIMETER_LEDGER.csv` (all rows read).
- grep sweeps: secrets, subprocess, `zipfile`/`exec`/`eval`, `tempfile`, raw-SQL f-strings, `str(exc)`, parsers, HTML sinks, download/link/role handling.
- `run_sec_audit.py` (this tree's `.venv314`) → 59/507/20/0 failures, exit 0.
- `MemberRequest(subject=…)` repro: accepts U+202E and BEL; `CreateCaseRequest.issuer`/`NoteRequest.body` reject both.
- Read `MAX_CALCULATION_SECONDS=30.0`, confirmed `_slot` covers only previews + event streams, cross-checked `test_limits_spec.py`.
