# Confidence review — validated audit fixes, 2026-09-08

Scope: working tree against f72e7bb8083548c77a85ac335adcc1b2ea6eca17.
This is a review of the actual diff and affected callers. Earlier observations
in audit-findings-validation.md remain the before-fix evidence. This record
separates reproduced bugs from retained policy and environment limits.

Least confident about, ranked:

1. Anonymous health requests still occupying shared request workers.
   Investigated: moving only the underlying probe leaves every synchronous HTTP
   caller waiting for it. Reproduced with one AnyIO worker: a stalled health
   request made /api/me time out. The engine/scanner probes are both synchronous.
   Verdict: CONFIRMED bug in the initial fix.
   Patch: async health shares one shielded background task across concurrent and
   cancelled callers, running both synchronous checks off the serving loop.
   The same one-worker test now passes and observes one health job.

2. Old successful readiness results becoming fresh when read later.
   Investigated: an initial timeout retained its Future; advancing the fake clock
   after completion returned stale success with a new timestamp. Reproduced.
   Verdict: CONFIRMED bug in the initial fix.
   Patch: timestamp/cache/reset pending at actual completion; timeout only caches
   failure while it still owns that pending probe. The fake-clock regression passes.

3. Source listing size check racing admission.
   Investigated: count/size and full SELECT are separate statements; PostgreSQL
   READ COMMITTED can see a source inserted between them. Traced all admission
   and withdrawal paths to the existing process authority lock and the supported
   one-app topology. A bounded read now holds that same lock across both queries.
   Verdict: CONFIRMED ordering defect by the executable transaction sequence.
   Patch: reuse the authority guard. SQL refusal regression proves an oversized
   listing executes only the aggregate query and never deserializes block arrays.
   A live cross-process PostgreSQL race was not exercised in this workspace.

4. Manifest preflight itself doing excessive text work before refusing.
   Investigated: a 2,000-block source plus its source row reached digest before
   bound_manifest. A digest sentinel failed before the patch.
   Verdict: CONFIRMED bug.
   Patch: count rows before constructing/hashing the provider manifest. The
   sentinel regression now refuses first; whole-array byte limits remain inclusive.

5. Concurrent run admission yielding between count and insert.
   Investigated: new async manifest preflight creates a yield point. The active
   count was moved to immediately before create_run, with no intervening await.
   Verdict: fine after ordering correction; the supported app owns one serving
   event loop and the unchanged runtime admission ceiling tests pass.

6. PDF work bounded inside a single page and cleanup on failure.
   Investigated: incremental text accounting cannot limit pypdf's internal page
   allocations. The parser now runs in a disposable process; timeout kills/waits
   for it, stderr is discarded, and output is bounded by text/page ceilings.
   Verdict: fine for the stated per-extraction limits; real PdfWriter fixtures
   cover ordinary, blank, invalid, aggregate-text and page-count paths.
   By-design limit: Linux enforces 512 MiB address space; macOS has CPU/wall/output
   bounds but no equivalent address-space guarantee. These are per child, not a
   host-wide memory quota. No production load/OOM claim is made.

7. ZIP/XML screens depending on whichever optional XML backend is installed.
   Investigated: every XML/rels part is streamed through the existing Expat
   DOCTYPE refusal before openpyxl. Prefixed valid ZIPs enter the same size and
   ratio screen. Direct historical loan-workbook import also screens all parts.
   Verdict: fine on real prefixed workbook and DTD regressions; no new dependency.
   No filesystem extraction was introduced; earlier Zip Slip claims were rejected.

8. Large JSON and intake failure leaving partial governed state or vault files.
   Investigated: recursion is caught, encoding accumulation stops at the text
   limit, transport/body and retained intake bytes are capped, aggregate extracted
   UTF-8 text is checked before admission. Existing all-or-none admission/cleanup
   tests and new over-cap tests passed with no case/source/vault delta.
   Verdict: fine. The transport test also verifies chunk boundaries, disconnect,
   exact-cap replay, refusal before downstream parsing and spool closure.

9. Derived names bypassing manual case validation.
   Investigated: issuer candidates and generated case data now use the actual
   CreateCaseRequest contract. Bidi/C1/oversized issuer probes leave no state;
   only the generated case label is abbreviated, preserving the governed issuer.
   Verdict: fine; boundary Cc handling retains CR/LF/TAB for ordinary narrative
   while upload metadata rejects them. NFC precedes metadata length limits.

10. Membership changes and malformed error fields returning 500/private text.
    Investigated: self-role and last-admin refusals are exact typed 409s; malformed
    validation locations are normalized/bounded or replaced with <field>.
    Deliverable exceptions expose only bounded code-shaped values. Pool timeout
    shares the existing safe STORE_UNAVAILABLE 503 handler.
    Verdict: fine on exact JSON/status and no-private-text regressions.

11. Authorization audit passing an authorized request that crashes.
    Investigated: the matrix formerly accepted 500 after writer admission.
    Tightening it exposed upgrade's uncaught provider-identity EngineError.
    Verdict: CONFIRMED product and audit gaps.
    Patch: upgrade uses the existing typed provider-preflight status policy.
    The matrix permits only three exact offline-fixture 503 responses; arbitrary
    500/503 fails. It also tests refused membership transitions leave standing
    unchanged. 64 routes, 552 matrix cells and 20 cross-case probes pass.

12. Event tails keeping stale case standing or replaying unused histories.
    Investigated: membership checks run before every event and poll; five-minute
    stream lifetime forces edge reconnection. Revocation and expiry tests stop
    the existing iterator. Both ordinary UI reads omit embedded event history;
    explicit legacy GET behavior remains unchanged.
    Verdict: fine for application membership. Reference edge expiry is one hour;
    live IdP refresh/revocation and idle-timeout semantics remain external.

13. Weak lock bookkeeping losing synchronization while a run is active.
    Investigated: callers take a strong local reference while entering/holding
    each asyncio lock, and waiters retain it too. Weak dictionaries only remove
    entries without live owners. A completed real invocation plus GC empties both
    maps. Existing concurrency/durability tests remain the behavioral backstop.
    Verdict: fine within the supported one-serving-loop ownership model.

14. Queue diagnostics rolling back accepted state or leaking document text.
    Investigated: accept_snapshot commits before on_accepted. The catch logs
    run_id and exception class only; the queue-failure test now inspects the real
    log record and proves accepted pointer survives and manual retry succeeds.
    Verdict: fine. Worker database-finalization failures still intentionally
    escape for supervisor restart/recovery, rather than being suppressed.

15. Markdown hardening changing historical filed bytes.
    Investigated: v5 is selected for new freezes only; v3/v4 formatter branches
    stay byte-compatible. Metadata escaping is separate from authored narrative.
    Shared renderer copy and offline rerender are byte checked. 58 publication,
    audit-package and golden tests passed, including new CR/LF metadata fixtures.
    Verdict: fine. New v5 bytes intentionally differ; no historical mutation.

16. Startup ownership and shutdown behavior.
    Investigated: role ownership precedes schema DDL, lasts through serving, and
    exits before owned-engine disposal; schema interruption closes it. App owns
    checkpoint before build. Review then reproduced invalid config creating a
    lock sidecar before refusal.
    Verdict: CONFIRMED ordering corner, corrected by validating before flock.
    Constructor cleanup, nested ownership, session heartbeat and duplicate-process
    tests pass. Real PostgreSQL integration is opt-in and was not exercised here.

17. Password metacharacters and explicit development fallback.
    Investigated: SQLAlchemy URL.set/make_url round-trip @%/?#[] with fixed host
    and database; Compose passes password separately. An explicit blank URL plus
    password initially raised ArgumentError; a regression reproduced it.
    Verdict: CONFIRMED compatibility corner, fixed by only merging nonempty URLs.
    Explicit SQLite URLs render unchanged. No credential restriction introduced.

18. Pagination compatibility beyond the visible Workspace.
    Investigated: API case pages are bounded, stable by ID and use batch metadata;
    five-case/two-page tests prove completeness without N+1 reads, and 101 cases
    explicitly refuse the legacy unpaged request. Integration review found
    operational QA and browser consumers still assuming an unpaged list.
    Verdict: CONFIRMED caller gap, fixed in the operational QA tools and browser
    smoke. Seven capacity tests and 200/201-row plus refusal/cursor probes pass.

19. Browser cancellation reclassified as a malformed success response.
    Investigated: a ReadableStream that throws AbortError reproduced the changed
    error identity. The api helper now rethrows DOMException like networkFetch.
    Verdict: CONFIRMED regression, corrected. All 12 API unit tests pass.

20. Browser checks passing without useful observation or bounded completion.
    Investigated: frontend report traced positive anchors, nonempty collections,
    independent frozen objects, early page/dialog observers and final assertions.
    Empty browser selection and manual barriers are bounded; CI runs the four
    unique fixture scripts; axe records incomplete results and anchors destination
    headings. Agent's 193 Node tests and four Chromium fixtures passed.
    Verdict: fine on focused evidence; final full browser execution and any
    environmental limits are recorded separately, never inferred from test text.

21. Documentation and rejected findings becoming accidental scope expansion.
    Investigated: original findings kept untouched, 59 dispositions retained.
    No changes to allowed ADMIN provisioning, audited GET downloads, privileged
    database-owner threat model, intentional recovery drafts, inline Next bootstrap
    CSP, caller-selected provider credentials, or the incorrect semaphore fix.
    Verdict: by-design or not established, with reasons in the validation record.
    Health fields, membership predicate, session policy and live invariant proofs
    are corrected in current docs; old dated observations remain historical.

Fixed: the reproduced ordering, cancellation, stale-readiness, upgrade-error and
caller-compatibility issues above in addition to the validated audit findings.
Verified fine: bounded admission, exact typed refusals, live membership checks,
historical renderer compatibility, durable acceptance, active lock lifetime.
By-design: retained unsaved drafts, historical exports and supported authority
policy; per-child parser limits are not a total host-memory admission policy.
Still open: external/live IdP behavior and opt-in PostgreSQL evidence. Full suite
outcomes, browser checks and any environment exclusions belong to the final
status report; this document does not claim they passed before they complete.

Post-suite refinement: three v5 tests found unnecessary escaping of decimal
points, internal underscores and hyphens. Metadata is always inline, so the
formatter now leaves those literal and escapes underscore emphasis only at word
boundaries. The four affected focused publication checks and the ordinary
distressed export E2E pass, preserving all original assertions. The lone research
publication failure was reproduced in an isolated untouched-base export.

Browser follow-up: the newly input-derived model-signoff fixture computed
4.1000000000000005. A comparison tolerance hid the numeric assertion failure but
the frozen report correctly exposed the same unrounded value. The root fix rounds
the fixture output to two decimal places before serialization, retaining the
submitted-assumption dependency. Both the strict 4.1 assertion and the frozen
report text assertion remain intact. No product calculation or renderer changed.
Full browser rerun results are recorded in the status report.

Browser-runner follow-up: an explicitly empty environment value previously fell
back to the default engine list through `||`. Nullish fallback now distinguishes
unset from empty. The executable runner check rejects empty, comma-only and
whitespace-only selections before spawning a browser; all five harness unit
checks pass.

The WebKit CSP warning was isolated to Playwright screenshot preparation: the
installed runtime inserts a `body {}` stylesheet for animation synchronization.
Changing caret capture did not remove it. The main-page observer already had
provenance-based handling for that exact automation insertion; the new auxiliary
observers lacked it. The follow-up reuses that handling rather than changing
application CSP or broadly suppressing stylesheet errors. Final evidence is in
the status report and browser reports.

Final configuration cross-check: setting POSTGRES_PASSWORD alongside an explicit
SQLite URL does not add credentials to that URL; SQLAlchemy renders the original
SQLite URL unchanged. A real in-memory connection and SELECT 1 passed. This
suspected compatibility issue was refuted, so no extra guard was added.

Firefox final-assertion follow-up: Firefox emits no console line for an HTTP
error, which the existing authority-503 check already handled using a response
listener. Newly added refusal assertions incorrectly depended on consumption of
Chromium-style console allowances. The common response observer now records
exact expected URL/status pairs, including repeated refusals; the final assertion
compares the expected and observed multisets. Optional console filtering remains
separate, and all page/runtime errors remain failures. Both registrations precede
the two real intake submissions; route fixtures register before fulfilling their
404/409/422 responses. Missing and duplicate responses now fail independently of
engine console behavior. This is a test-only follow-up, so no rewrite tournament
is needed. The final Firefox rerun and shared browser evidence are in the status
report.

Axe follow-up: strengthening the Report Studio focus check accidentally assumed
the section navigator was a DIV. The full sweep returned NAV; both production
section navigators are semantic nav elements. The assertion now requires NAV,
so an absent focus target still fails instead of passing through undefined/null
coercion. Both component call sites and all sibling test references were checked;
no product element or keyboard behavior changed. This one-word test correction
is excluded from rewrite-tournament. The full axe rerun is recorded in the status
report.

Incomplete-result triage: six repeated aria-valid-attr-value findings all named
one real empty-state defect: .source-reader referenced source-reader-title even
when no source was selected and the heading did not exist. The section now uses
the source filename as its direct accessible name, falling back to Source
document for empty/loading/error states. Loaded-source naming and visible heading
content are preserved; repository-wide references show no other caller of the
label relationship. The central axe recorder now rejects unresolved ARIA values;
replaying the actual failing scan verified that the new assertion fails. Full
build and axe verification follow in the status report. This is a single ARIA
attribute correction with the existing selected-source fallback; no component
rewrite or new helper is warranted. Eleven other incomplete records concern
partially obscured text at the 200% viewport; those are recorded for manual
contrast assessment, not labelled as passes or assumed contrast failures.

Final verification: rebuilt axe passed 122 combinations with no violations or
unresolved ARIA values. Its fresh empty database adds 12 empty-table incomplete
records; 11 obscured-element contrast records remain, for 23 retained records.
These are not asserted defects or silently counted as passes. Full results and
manual-review limits are in audit-fixes-status.md. All three full browser journeys
passed; the final ARIA-only correction was then covered by the rebuilt sweep,
195 Node tests, lint and TypeScript. The disposable server is stopped.

Commit/CI confidence pass: the first GitHub run exposed two confirmed integration
issues: the newly tracked audit harness lacked a FILE_MAP entry, and the browser
fixture's intentional scanner-unavailable health response was rejected by
curl -f. The ledger now maps the harness and passes with 433 tracked product
files. The browser readiness probe accepts only HTTP 200 or 503 and validates
store, bundle, checkpointer and scanner fields; it does not change application
health semantics. YAML structure, shell syntax, route coverage and JavaScript
syntax were checked. The local fixture previously returned the documented 503
with ready core fields; no production endpoint was weakened. CI must be rerun
on the pushed correction before merge.
