# CAOS — data handling, retention, and boundary audit

Audit performed 2026-08-31 against `claude/license-data-retention-audit-36ec68`
at `e224d9e`. The filename carries the date requested in the brief.

Current-state correction, 2026-09-01: §2, §4, and §5 now reflect the Task 5
provider-authority, false-success, startup, and checkpoint-cleanup changes.
The original retention findings remain dated audit findings unless a correction
below says otherwise.

This is an engineering document. Every claim below is grounded in a file and
line that was read during the audit; anything unverified is marked as such in
§7 rather than asserted. It is not legal advice and not DPA prose — it is the
factual substrate a DPA would have to be drafted against, plus the list of
commitments the code cannot currently honour.

**Headline.** CAOS has no customer-data deletion or retention capability. There
is no customer-data `DELETE` route on the API,
no purge job, no TTL, no expiry, and no retention configuration anywhere in
`caos/server` or `caos/deploy`. Every uploaded document byte, every extracted
evidence block, every model-authored artifact, every audit row and every
container log line persists for the life of the volume. Terminal run
checkpoints are now deleted after the domain record becomes terminal, but they
hold references rather than customer content. Source withdrawal
(invariant 1) is a visibility and authority control; it deletes nothing. A DPA
clause promising erasure — Art. 17 or the Art. 28(3)(g) end-of-contract
deletion that is mandatory in every processor contract — cannot be satisfied
today by any code path in this repository.

---

## 1. Licence

### 1.1 Decision

`LICENSE` now exists at the repo root: a proprietary, all-rights-reserved
licence with copyright in **Eric Guei**, written to cover both a vendor-hosted
service and a customer-operated deployment.

The three inputs that decided this could not be read out of the repo and were
supplied by the decision owner during the audit:

| Input | Value | Why the repo could not answer it |
|---|---|---|
| Copyright holder | Eric Guei (individual) | No entity is named in `README.md`, `PRODUCT.md`, `caos/server/pyproject.toml`, or `caos/frontend/package.json`. Every non-bot commit is authored `Eric Guei <ericsea1990@googlemail.com>`. |
| Delivery model | Both hosted and customer-deployed | `caos/deploy/docker-compose.yml` and `caos/deploy/Dockerfile` build a self-contained stack, which is consistent with either. Inference, not evidence. |
| Openness | Fully proprietary | Nothing in the repo signals intent either way. |

Proprietary is also the only answer that is safe to be wrong about: it can be
loosened later, never tightened. For a product whose stated purpose is
ingesting "governed source documents" for institutional credit analysis
(`README.md:3-7`), and whose vendored methodology bundle is the substantive
asset (`CLAUDE.md`, invariant 4), a permissive or source-available licence
would hand a competitor the methodology.

### 1.2 What was true before

`ls | grep -i licen` returned nothing; `find` for `*licen*`, `NOTICE*`, and
`COPYING*` across the whole tree returned nothing. `caos/server/pyproject.toml`
has no `license` field (`[project]` block, lines 6-10). `caos/frontend/package.json`
is `"private": true` with no `license` field. The remote is
`https://github.com/EricMG13/CAOS-LangMVP.git`; whether it is public was not
checked. Absence of a licence file means default copyright — restrictive by
accident rather than by design, and in substance close to what the new file now
says, but unpleadable, invisible to a buyer's counsel, and read by many
engineers as an oversight rather than a position.

### 1.3 Open licensing item (not closed by this session)

**L1 — no third-party attribution notice.** The Docker image redistributes the
whole pinned Python and npm dependency tree. MIT, BSD, and Apache-2.0 all
require notice preservation on redistribution; Apache-2.0 additionally requires
a `NOTICE` file where upstream supplies one. `LICENSE` §5 records this as an
open prerequisite for distribution rather than papering over it. Closing it is
mechanical (`pip-licenses` / `license-checker` over the two lock files) but it
is a real blocker on shipping an image to a customer, and it was out of scope
here because it would mean generating a file this session was not asked for.

---

## 2. What actually persists, where, and for how long

Terms used below:

- **Content** — customer document text or bytes, or something derived from them
  that a reader could reconstruct meaning from.
- **Identifiers** — case/run/source/artifact ids, digests, versions. Pseudonymous
  but re-identifying against the same database.
- **Identity** — the OIDC subject or email of a human actor
  (`caos/server/caos/identity.py:52-55`).

Every row in the "lifetime" column is **indefinite** unless stated otherwise;
that is not a summary, it is the finding. "Deletable today" answers only:
*is there any code path, API or operational, that removes this?*

### 2.1 The two data planes

1. **Vault** — a content-addressed filesystem tree rooted at
   `Settings.storage_dir` (`caos/server/caos/config.py:24`), which is `/vault`
   in production (`caos/deploy/docker-compose.yml`, `CAOS_STORAGE_DIR: /vault`)
   on the `vault-data` named volume, and defaults to **`/tmp/caos-vault`** in
   development.
2. **Domain database** — SQLite in development and PostgreSQL in production;
   the environment contract is validated before the store opens
   (`caos/server/caos/config.py:123-140`; `caos/server/run.py:88-91`), and the
   production database lives on the `postgres-data` named volume.

Run checkpoints ride the vault volume, not the database:
`caos/server/run.py:99-100` sets `checkpoint_path=data / "checkpoints.db"` and
`data` defaults to `settings.storage_dir` (`run.py:162`). This is deliberate and
noted in the code.

### 2.2 Inventory

| # | Data class | Where it lives | Content? | Lifetime | Deletable today |
|---|---|---|---|---|---|
| A | Uploaded document bytes | Vault: `<storage_dir>/sources/<sha[:2]>/<sha256>` (`sources/domain.py:57-75`) | Content (verbatim original) | Indefinite | **No.** `Vault` has `put` and nothing else. No delete method exists on the class. |
| B | Extracted text / evidence blocks | `sources.blocks` JSON column (`storage/store.py:63`), written at ingest (`sources/domain.py:387,396`) | Content (full extracted text, up to 12 MB per source) | Indefinite | **No.** No row is ever deleted; `withdraw` only sets a flag. |
| C | Source metadata | `sources` row: `filename`, `media_type`, `bytes`, `sha256`, `created_by`, `created_at` (`storage/store.py:54-78`) | Identifiers + Identity; filenames are often themselves signal ("Project X lender presentation") | Indefinite | **No.** |
| D | Analyst notes | `notes.body` TEXT (`storage/store.py:93`); a promoted note becomes a synthetic source row (`store.py:458`, `source_kind="analyst_note"`) | Content (analyst prose, which in a credit context is where MNPI is most likely to be written down verbatim) | Indefinite | **No.** No note delete or edit route. |
| E | Loan-universe rows | `loan_universes.rows` (`storage/store.py:125`), `rv_universes.rows` (`store.py:139`) | Content — includes `borrower_name` (`artifacts/loan_universe.py:66,469`) and position-level fields | Indefinite | **No.** Withdrawal flips `status` to `WITHDRAWN` (`store.py:344-349`); rows stay. |
| F | Prompts sent to the provider | Constructed in-memory in the node body (`engine/runtime.py:842-847`; `engine/loop.py:213-223`); the message list is a local variable | Content in transit | **Not persisted.** Ephemeral per node execution. | n/a — nothing to delete |
| G | Provider responses (agent modules) | `run_artifacts.payload` JSON + `run_artifacts.markdown` TEXT (`storage/runs.py:66-67`); the envelope permits up to 2 MiB of markdown (`methodology/canonical.py:48`) | Content — the model's analysis, including its Evidence Trace section, which is where verbatim document quotation lands | Indefinite | **No.** The `DELETE` on `run_artifacts` (`storage/runs.py:383`) is validate-then-replace arbitration inside `complete_node`, not a retention control. |
| H | Deterministic artifacts | Same table | The fixed `build_deterministic_payload` output is now a host-control fixture, not an ordinary successful analysis path. Its explicit test capability can still persist fixture output; CP-3 can include the pinned loan universe and borrower names. Ordinary execution without a source-computed executor fails with `DETERMINISTIC_EXECUTOR_UNAVAILABLE`. | Indefinite when a host control deliberately persists one | **No.** |
| I | Accepted snapshots | `run_snapshots.artifacts` (`storage/runs.py:86`) | Identifiers + digests | Indefinite | **No.** |
| J | Model builds and revisions | `model_builds.payload` (`storage/models.py:39`), `model_revisions.record` (`storage/models.py:59`); rendered workbooks are hash-addressed in the vault under `models/<case_id>/<target_id>` (`models/service.py:988-1001`) | Content — a credit model carries the issuer's figures | Indefinite | **No.** |
| K | Deliverable drafts, frozen versions, exports | `deliverable_revisions.content` (`storage/deliverables.py:31`), `deliverable_frozen.payload` (`deliverables.py:48`); export bytes at `<storage_dir>/deliverables/<thread_id>/<format>` (`deliverables/service.py:599-602`) | Content — the committee memo itself | Indefinite | **No.** The export `unlink` (`deliverables/service.py:812-814`) is `delete_export_for_tests`. |
| L | Audit events | `audit_events` table (`storage/store.py:144-152`), append-only, `data` JSON at `store.py:151` | Identifiers + **Identity** (`actor` on every row, `store.py:173-176`). One row carries free text: `deliverable.changes_requested` stores `comment[:300]` (`storage/deliverables.py:277-278`) | Indefinite | **No.** No delete, no archival, no rotation. `audit_trail` only reads (`store.py:182`). |
| M | Run events | `run_events` (`storage/runs.py:76-83`) | Identifiers + provider-identity digest. Normal events include `provider_identity_digest`; only the identity-quarantine failure omits the invalid digest (`storage/runs.py:177-193`). `run.failed` otherwise carries its bounded code and optional module ID (`storage/runs.py:415-441`). | Indefinite | **No.** |
| N | Run checkpoints | `checkpoints.db` on the vault volume, through LangGraph `AsyncSqliteSaver` | **No content.** `RunState` contains run authority and artifact references; the provider message list never enters state. | While the run is non-terminal. `_delete_terminal_thread` deletes the thread after terminalization, and recovery reaps terminal threads left by a crash. | **Yes, automatically at terminalization or recovery.** See G6. |
| O | Assumptions | `assumptions.data`, `assumptions.evidence_ids` (`storage/store.py:104-105`) | Content (analyst-entered figures) | Indefinite | **No.** Withdrawal marks them `STALE` (`store.py:338-341`); rows stay. |
| P | Identity and membership | `cases.created_by`, `case_members.subject` (`store.py:40,50`), plus `created_by` on sources, runs, artifacts, revisions, exports | **Identity** (OIDC subject or email) | Indefinite | **No.** There is no member-removal route (CLAUDE.md's known-gaps ledger records `/api/cases/{id}/members` as having no route at all; the route inventory confirms it). |
| Q | Backups | `caos.dump.age` + `vault.tgz.age` at an operator-chosen path (`caos/deploy/backup.sh:74-76`) | Content — "the complete confidential credit corpus" in the script's own words (`backup.sh:4`), age-encrypted | Indefinite, and *by design out of scope*: "Retention and destination ACLs belong to the storage layer" (`backup.sh:20`) | **No.** Each run overwrites the same two fixed filenames; there is no generation management and no expiry. |
| R | Container logs | Docker `json-file` driver (compose declares no `logging:` block, so the daemon default applies); uvicorn access log is on because `run.py:129` constructs `uvicorn.Config(app, host=host, port=port)` with defaults | Identifiers + **client IP** in every access line | Indefinite and unbounded — no `max-size`/`max-file` anywhere in `docker-compose.yml` | **No.** |
| S | Provider attempt metadata | `run_budgets.attempts` JSON | Identifiers and bounded execution metadata: provider identity, request/response digests, provider request ID, observed model/version, usage, stop reason, retry index, and terminal code. No prompt, evidence text, response body, hidden reasoning, error body, or secret is stored. | Indefinite | **No.** |

### 2.3 One structural fact that shapes any future deletion design

The vault is content-addressed **globally**, not per case:

```
directory = self.root / "sources" / sha256[:2]
target    = directory / sha256
if target.exists():
    return str(target)
```

`caos/server/caos/sources/domain.py:61-65`.

Two cases — potentially two different customers, or one customer's walled
deal teams — that upload byte-identical documents share one vault file, and
the second upload writes nothing. `sources.vault_path` therefore does not own
its bytes. Any deletion feature must be reference-counted across every
non-withdrawn `sources` row with that `sha256`, or it will silently break an
unrelated case's evidence. Deduplication is deliberate and defensible; the
point is only that it converts "delete this customer's file" from an `unlink`
into a graph problem, and that has to be designed rather than discovered.

Note that the DB-level uniqueness is scoped per case and only over active rows
(`ix_sources_active_content`, `store.py:70-76`), so the same content genuinely
can exist under multiple `sources` rows.

---

## 3. Withdrawal is not deletion

This distinction matters enough to state precisely, because invariant 1 makes
withdrawal sound stronger than it is.

`DomainStore.withdraw` (`caos/server/caos/storage/store.py:329-353`) does
exactly four things, in one transaction:

1. sets `withdrawn = True` and `withdrawn_at` on the `sources` row (`:335`);
2. mints a **new** immutable source-set version excluding that source
   (`:337`, via `_next_source_set`);
3. marks citing assumptions `STALE` (`:338-341`);
4. flips ACTIVE loan universes pinned to that source to `WITHDRAWN` (`:344-349`);
5. writes a `source.withdrawn` audit row (`:350`).

It issues no `DELETE`. What survives a withdrawal:

- **the document bytes**, untouched in the vault — nothing in the codebase ever
  removes a vault file;
- **the extracted text**, whole, in `sources.blocks` — the row is updated, never
  removed, and `blocks` is not cleared;
- **every prior source-set version** that included the source, because source
  sets are immutable history rows (`store.py:79-87`, unique on
  `(case_id, version)`);
- **every artifact** produced by a run pinned to those older sets, including
  any evidence text the model quoted into `run_artifacts.markdown`;
- **every snapshot, model build, revision, deliverable draft, frozen
  deliverable, and export** downstream of those artifacts;
- **the audit trail**, which by design records that the source existed, its
  `sha256`, who uploaded it, and when (`store.py:324`).

What withdrawal *does* guarantee, correctly and provably, is **prospective
unreadability through the agent boundary**. `EvidenceReader._authorized_source`
re-reads the store on **every** `read_evidence` call and refuses a withdrawn
source with `AGENT_AUTHORITY_MISMATCH`
(`caos/server/caos/engine/evidence.py:62-79`, specifically `:77-78`). This
holds after a resume, because the check is live and never served from the
checkpoint. That is a genuinely strong control and it is worth selling — it
just answers a different question than a DPA asks.

The one-line version for a buyer: **withdrawal stops future analysis from using
a document; it does not remove the document, its text, or anything already
derived from it.** Presenting withdrawal as an erasure control in a DPA would
be a misrepresentation.

---

## 4. Retention and deletion requirements a DPA would need

Requirements are numbered `R`; the original findings are numbered `G` for
audit traceability. Open findings describe missing behavior, while Task 5
closures are marked in place.

### 4.1 Requirements the code already satisfies

| Req | Requirement | Evidence |
|---|---|---|
| R1 | Customer content is never sent to an external service for discovery or enrichment; the analysis universe is the supplied set only | Invariant 1; web discovery is structurally banned, and `EvidenceReader` can only serve blocks of sources in the pinned set (`engine/evidence.py:69-79`) |
| R2 | Every read of customer content by the model is authorised at the host boundary and fails closed with a typed refusal that returns no text | Invariant 2; `engine/evidence.py:81-101`, and `caos/tests/spec/test_evidence_spec.py` enumerates 33 refusal shapes |
| R3 | Content at rest is integrity-verified on read | `atomic_files.py:88-158` (no-follow descriptor chain, size + SHA-256 + inode re-check); `Vault.put` verifies the digest before writing (`sources/domain.py:58-60`) |
| R4 | Uploads are malware-scanned before storage, and the scanner failing is a refusal rather than a bypass | `sources/domain.py:78-104`; production without `CLAMAV_HOST` returns 503 (`:83-84`) |
| R5 | Access is authenticated at a trusted edge, with role derived from OIDC groups in production and client headers unable to escalate | `identity.py:46-72`; unknown and unauthorised cases both return 404 (`identity.py:75-80`) |
| R6 | Backups are encrypted with an authenticated cipher, and the private key is required to live off the backup host | `caos/deploy/backup.sh:5-19,34,60,66` |
| R7 | The processing record — who did what to which case, when — is complete and tamper-evident | `audit_events` append-only, written in the same transaction as the governed write (`store.py:173-176` and every `_audit` call site) |
| R8 | No customer content is persisted client-side | `caos/frontend/src/components/model/ModelBuilder.test.ts:45` and `report/ReportStudio.test.ts:13,36` assert no `localStorage`/`sessionStorage` usage |
| R9 | Non-agent execution paths involve no external processor | `Engine._run_module` calls the provider only for a declared agent module with execution enabled. The former generic fixed payload is test-only; ordinary non-agent execution without a source-computed executor returns `DETERMINISTIC_EXECUTOR_UNAVAILABLE` rather than a synthetic success. |

### 4.2 Current gaps and closed findings

The original gap numbers remain stable for audit traceability. A finding closed
after the audit is marked closed instead of being silently removed.

---

**G1 — There is no end-of-contract deletion. (Blocking.)**

GDPR Art. 28(3)(g) requires the processor to delete or return all personal data
at the end of the service, at the controller's election. There is no code path
that does either.

- No customer-data `DELETE` route exists in the current route inventory.
- No case-deletion, source-deletion, run-deletion, or member-removal function
  exists on any store.
- Existing non-test deletions are correctness or lifecycle operations, not
  customer-retention controls: authority/artifact replacement
  (`storage/deliverables.py:295`; `storage/runs.py:383`), temporary-file cleanup
  (`sources/domain.py:74`; `atomic_files.py:84`), and automatic terminal
  checkpoint cleanup (`engine/runtime.py:471-474`). The deliverable export
  deletion at `deliverables/service.py:812-814` is explicitly test-only.

There is also no export path that could satisfy the "return" limb: the API can
download one model workbook and one deliverable export at a time, and there is
no case-level or tenant-level extract.

*Closing it requires:* a case-scoped cascade covering classes A–K and O–P in
§2.2, reference-counted against the shared vault (§2.3), transactionally paired
with an audit event, plus a decision (see G3) on what the audit trail retains.

---

**G2 — There is no data-subject erasure path. (Blocking, and narrower than G1.)**

Art. 17 erasure of one individual is not the same operation as G1. In CAOS,
personal data about an identifiable individual appears in two distinct places
and neither can be surgically removed:

1. **Actor identity**, denormalised across `cases.created_by`,
   `case_members.subject`, `sources.created_by`, `run_artifacts.created_by`,
   `model_revisions.created_by`, `deliverable_frozen.filed_by`, and
   `audit_events.actor`. An erasure request from a departed analyst touches
   every one of these.
2. **Content inside documents.** Credit documents routinely name directors,
   guarantors, and beneficial owners. That data lives inside opaque
   `sources.blocks` text and inside model-authored markdown; there is no index
   that could locate it, and no redaction primitive.

Note the tension worth stating in the DPA rather than hiding: the audit trail
exists precisely so a decision can be defended years later, and Art. 17(3)(b)/(e)
give real grounds for retaining it. That is a legitimate position — but it has
to be an argued, documented position, not the accidental consequence of there
being no delete statement.

---

**G3 — No retention period is defined for anything, so there is nothing to enforce.**

A DPA needs a period per category. `grep -riE 'ttl|expire|retention|cron|prune|purge|max_age'`
across `caos/server`, `caos/deploy`, and `.github/workflows` returns nothing
relevant: the only hits are a debt *schedule*, the run auto-continue
*scheduler*, the nightly CI cron, and `backup.sh:20` explicitly disclaiming
retention as somebody else's problem.

The minimum set to decide before a DPA can be signed:

| Category | Needs a period | Why it is not obvious |
|---|---|---|
| Document bytes + extracted text (A, B) | Yes | Shortest defensible period; highest MNPI exposure |
| Artifacts, snapshots, models, deliverables (G–K) | Yes | Committee decisions get challenged years later; the whole product premise is defensibility |
| Audit events (L) | Yes, and probably longest | Often driven by the customer's own regulatory record-keeping obligations, not by GDPR |
| Run events, checkpoints (M, N) | Yes, and probably shortest | No content; pure operational telemetry |
| Backups (Q) | Yes | See G7 |
| Container logs (R) | Yes | See G8 |

---

**G4 — Withdrawal is likely to be mistaken for deletion.**

Covered in full in §3. The gap is not the behaviour — the behaviour is correct
and well-tested. The gap is that `POST /api/cases/{case_id}/sources/{source_id}/withdraw`
is the only source-removal-shaped affordance in the product, it is the one an
analyst will reach for when someone says "get that document out of the system",
and neither the API surface nor any user-facing text distinguishes it from
deletion. If a DPA or a sales answer describes withdrawal as erasure, the
statement is false.

---

**G5 — Data is not encrypted at rest, and the DPA will be asked to say it is.**

`docker-compose.yml` mounts plain named volumes (`postgres-data`, `vault-data`)
with no encryption configuration; PostgreSQL is the stock
`postgres:17-alpine` image with no TDE, and the vault is ordinary files written
by `Vault.put` / `publish_hash_addressed_bytes`. Confidentiality at rest
therefore rests entirely on host-level disk encryption, which is an operator
property this repository neither configures nor verifies.

Backups *are* encrypted (`backup.sh`), which makes the live-volume gap easy to
overlook: the cold copy is protected and the hot copy is not.

---

**G6 — Terminal checkpoint cleanup is implemented. (Closed in Task 5.)**

`Engine._delete_terminal_thread` calls the checkpointer's native
`adelete_thread` only after the domain run is terminal. Every drive path invokes
that cleanup, identity-quarantine failures invoke it directly, and startup
recovery scans both checkpoint tables to reap a terminal thread left by a
crash. Paused and active threads remain because they are needed for resume.

`RunState` still holds no document text, and provider messages remain local to
the provider loop. The domain run, attempts, events, artifacts, and accepted
snapshot remain durable audit records; only the redundant execution checkpoint
is removed.

---

**G7 — Backups have no rotation, no expiry, and no way to be purged of deleted data.**

`backup.sh:74-76` moves the two artifacts to fixed names — `caos.dump.age` and
`vault.tgz.age` — so each run overwrites the previous one at that destination.
There are no generations, no timestamps, and no retention logic; the script
says so itself at `:20`.

The structural consequence matters more than the operational one. Even once G1
is closed, deletion will not reach backups. A DPA that promises erasure within
N days must either (a) state a backup-expiry window after which the last copy
provably ages out, or (b) commit to re-encrypting or re-taking backups after a
purge. Neither is possible against a single overwritten file with no lifecycle.

The encrypted Postgres and vault streams and their restore checks were exercised
with real `age`, PostgreSQL, and Docker-volume data on 2026-08-30. The
`backup.sh` Compose wrapper, lock directory, manifest bookkeeping, scheduled
off-host transfer, rotation, and retention were not exercised. Both the proven
cryptographic path and the missing lifecycle belong in the same DPA answer.

---

**G8 — Container logs are unbounded and contain personal data.**

`docker-compose.yml` declares no `logging:` block for any of the six services,
so the Docker daemon default applies — `json-file`, no `max-size`, no
`max-file`, no rotation. `run.py:129` builds `uvicorn.Config(app, host=host, port=port)`
without `access_log=False`, so uvicorn's access log is on, and each line carries
a client IP (personal data under GDPR) alongside a request path containing
case, run, and source identifiers.

Application logging is structured and bounded to identifiers, typed codes,
counts, timings, provider identity digests, and exception classes; its contract
and tests ban source text, prompts, model output, provider bodies, and secrets.
That reduces content exposure but does not bound Docker's retention or remove
the IP and path metadata in access logs. This remains an unbounded, unrotated,
unretained store of personal data outside the two data planes anyone would
think to purge.

---

**G9 — There is no record of where the data is, at a granularity that would survive a breach.**

Art. 33 breach notification requires scoping the blast radius within 72 hours.
Doing that today means a human reading the schema. This document is the first
artifact in the repository that enumerates the classes; there is no
machine-readable data map, no per-table classification, and no tenancy boundary
(a "tenant" is a set of cases, joined only through `case_members`). The
practical failure mode is not a missing document — it is that answering "whose
data was in this dump" requires a bespoke query written under time pressure.

---

**G10 — Runtime provider attribution is durable; contractual disclosure remains external.**

Task 5 replaced the settings-derived model claim with one immutable
`ProviderIdentity`. It records provider name, exact model, optional reported
provider version, adapter version, parameter/context digest, and the bound
qualification record ID, digest, status, and expiry. The engine captures that
identity once and persists it on the run, plan authority, attempts, artifacts,
accepted snapshot, run-event identity digest, acceptance audit event, and API
responses.

Each successfully usage-validated message-generation response records a bounded
request and response digest, provider request ID, observed model/version, usage,
stop reason, and retry index. Retry and terminal rows retain their applicable bounded subset; fields
that do not exist for that row class remain absent or null. Provider token-count
operations are bounded but are not logged or stored as durable attempt rows.
Raw prompts, evidence text, response bodies, hidden reasoning, provider error
bodies, and secrets are not retained. A usage-valid response that reports a
different model or provider version is charged and recorded, then fails with
`AGENT_IDENTITY_MISMATCH` before its tools or output can be used.

Enabled production agent execution now accepts only one qualified Anthropic
binding. It rejects multiple credentials, any OpenRouter credential, a missing
or malformed qualification record, an expired record, and a record bound to
another model, adapter, policy, or methodology build. Disabled execution with a
clean configuration constructs no provider. OpenRouter remains an explicitly
unqualified development-only adapter. An environment-variable edit can no
longer switch the production sub-processor.

Two limits remain. `/api/health` does not publish the active binding, although
every actual provider call is attached to a durable run identity. The identity
is carried through the accepted snapshot but has not yet been copied into every
model and deliverable publication record. A data processing agreement (DPA)
still needs externally verified processor terms and a change-notification
process; code cannot supply either.

---

**G11 — Deletion has no design, and the architecture makes it non-trivial.**

Flagged separately from G1 because it changes the estimate. Three properties
that are correct for defensibility all obstruct deletion:

1. **Content-addressed sharing.** Vault files are shared across cases (§2.3);
   deletion must be reference-counted.
2. **Immutable history.** Source sets are append-only versions
   (`store.py:79-87`); artifacts are keyed on
   `(run_id, module_id, input_fingerprint)` (`storage/runs.py:69`); model
   revisions and deliverable revisions are explicitly append-only. Removing a
   source's derivatives means removing rows the invariants describe as
   immutable, so it needs a stated exception, not a `DELETE`.
3. **Digest-bound identity.** Snapshots, frozen deliverables, and model builds
   carry digests over content that a purge would remove, so a partially purged
   case must either fail its own integrity checks or record a tombstone that
   satisfies them. That is a design decision with wire-visible consequences —
   the same shape of change CLAUDE.md flags for the loan-workbook
   `BoundaryText` gap.

None of this argues against building it. It argues that "add a delete endpoint"
is the wrong sizing, and a DPA should not be signed against that estimate.

---

### 4.3 Requirement summary

| Req | Requirement a DPA would carry | Status |
|---|---|---|
| R10 | Deletion or return of all customer data at end of contract | **G1 — cannot** |
| R11 | Erasure of an identified data subject on request | **G2 — cannot** |
| R12 | Documented retention period per data category | **G3 — none defined** |
| R13 | Erasure propagates to derived artifacts | **G1/G11 — cannot** |
| R14 | Erasure propagates to backups within a stated window | **G7 — cannot** |
| R15 | Encryption at rest for live data | **G5 — not configured** |
| R16 | Bounded, retained-for-N-days operational logs | **G8 — unbounded** |
| R17 | Named sub-processors, with change notification | **G10 — production processor and exact run identity are enforced and durable; contractual terms and notification remain external** |
| R18 | Ability to scope a breach to affected controllers | **G9 — manual** |
| R19 | Execution telemetry does not outlive its purpose | **G6 — terminal checkpoints are deleted; durable audit records remain subject to the undefined retention policy in G3** |

Of these ten standard processor requirements, eight remain wholly unmet. R17
now has the runtime control but still needs contractual governance, and R19 is
closed for checkpoints while durable audit retention remains governed by G3.

---

## 5. What leaves the boundary

This is the first question an enterprise buyer asks, so it is answered
exhaustively.

### 5.1 When anything leaves at all

Nothing leaves unless the route contains an agent module, agent execution is
enabled, and startup assembled a current provider identity. Agent-backed routes
are preflighted before a run is created.

- `AGENT_EXECUTION_ENABLED` defaults to `false` (`config.py:54`) and is strict —
  any value other than the literal `true`/`false` raises (`config.py:9-17`).
- Screen-depth modules are non-agent by catalog design. They never call a
  provider, but the application no longer treats the generic fixed payload as
  successful analysis. Until a source-computed deterministic executor exists,
  ordinary execution returns `DETERMINISTIC_EXECUTOR_UNAVAILABLE`.

So: **a screen-depth run, or any run with agent execution off, transmits
nothing to any third party.** That is a real and saleable property.

Only nine modules ever execute as agents (`DECISIONS.md §1`: CP-1, CP-1A,
CP-1B, CP-1C, CP-1D, CP-2, CP-2A, CP-2G, CP-5), at full depth only.

### 5.2 Exactly what is transmitted on an agent module

From `compile_module_prompts` (`caos/server/caos/engine/authority.py:71-100`):

**System prompt** — the host wrapper plus verified methodology bundle files
(`authority.py:25-34, 58-68`). Vendor IP; no customer data.

**User prompt** — `canonical_json` of four things, under an explicit untrusted
label (`authority.py:86-99`):

1. `host_identity` — `module_id`, `run_id`, `case_id`, an `issuer_id` derived
   mechanically from `case_id` by replacing underscores, and two dates sliced
   from the run's `created_at` (`runtime.py:825-837`). **The case name, issuer
   name and sector the analyst typed are *not* sent** — `issuer_id` is the
   opaque case id, not `cases.issuer`. Worth knowing; it is better than a buyer
   will assume.
2. `source_metadata_manifest` — for each live source: `source_id`, `sha256`,
   **`filename`**, `media_type`, and per-block `block_id`, `locator`,
   `extractor_version`, `confidence` (`runtime.py:810-823`). **No block text.**
3. `validated_upstream_artifacts` — the full `markdown` of every upstream
   module artifact (`runtime.py:844`, `authority.py:82-85`). This is
   customer-derived analytical content, up to 2 MiB per artifact.
4. A fixed confidence-input contract. No customer data.

**Tool results** — verbatim customer document text. When the model calls
`read_evidence`, the host returns the block `text` field itself
(`engine/evidence.py:113`) serialised into the next user turn
(`engine/loop.py:356-363`). This is the primary content egress.

**Two things worth naming explicitly for a buyer:**

- **Filenames leave the boundary.** In leveraged finance, a filename such as
  `Project-Falcon-Lender-Presentation-CONFIDENTIAL.pdf` is itself MNPI: it
  discloses that a deal exists and who is looking at it, before a single word of
  the document is read. The manifest bounds filenames to a length
  (`engine/budget.py:154`) but does not redact them, and it is sent to every
  agent module on every run.
- **Content egress is capped, per run.** The evidence envelope is
  `evidence_bytes = ⌈(5 MiB/6)·N⌉` where N is the agent-module count
  (`DECISIONS.md §12.20`), enforced by the ledger before each read
  (`engine/evidence.py:117-119`). A run cannot exfiltrate an unbounded corpus
  even under a fully adversarial model. That is a genuinely unusual control and
  it should be in the sales answer.

### 5.3 Anthropic

In development, Anthropic is selected only when agent execution is enabled and
it is the sole configured provider credential. In production, startup also
requires a digest-bound qualification record that matches the exact model,
adapter, parameter/context policy, and methodology build and has not expired.
Multiple credentials are rejected; Anthropic no longer wins by precedence.
When agent execution is disabled, no provider client is constructed.

Requests go directly to Anthropic's Messages API through the pinned
`langchain_anthropic` client. The configured default model is
`claude-sonnet-4-6`, but the qualification record and durable provider identity
bind the exact model used by a run.

**One named processor, one hop, one contractual counterparty.** The relevant
terms are Anthropic's commercial terms and DPA, which the buyer's counsel will
read directly — this repository is not the authority on them, and this document
deliberately does not paraphrase them (see §7).

`caos/deploy/docker-compose.yml` passes the Anthropic credential, model,
execution flag, and qualification path/digest only to `app`. The model/export
`worker` receives only its environment, database URL, and vault path; it does
not receive edge, session, ClamAV, or provider secrets. Qualified Anthropic is
the only provider the production app can assemble.

### 5.4 OpenRouter is development-only

OpenRouter can be selected only in development, with agent execution enabled,
no Anthropic credential, and no qualification claim. `run.py` rejects any
OpenRouter credential in production and rejects multiple provider credentials
in every environment. The default development model is
`z-ai/glm-5.3-flash`.

Four differences, all read off `caos/server/caos/engine/openrouter.py`:

1. **OpenRouter is a broker, not an inference provider.** The request goes to
   `https://openrouter.ai/api/v1/chat/completions` (`openrouter.py:64,242`),
   and OpenRouter forwards it to whichever upstream provider serves the named
   model. The buyer's data therefore reaches **at least two** organisations,
   the second of which is chosen by OpenRouter's routing rather than by CAOS.
   Anthropic is one hop; this is two or more.

2. **The upstream is not pinned and not disclosed.** `_payload`
   (`openrouter.py:204-224`) sends `model`, `messages`, `tools`, `tool_choice`,
   `parallel_tool_calls`, `response_format`, and `max_tokens`. It does **not**
   send OpenRouter's `provider` routing object, so there is no pinned upstream
   allowlist and no data-collection policy asserted on the request. Which
   organisation processes a given run's document text is therefore not
   determined by this codebase. CAOS records the OpenRouter provider and exact
   model, plus any provider version returned by the response, but OpenRouter's
   undisclosed upstream is not available for CAOS to record.

3. **The default model is third-party.** `z-ai/glm-5.3-flash` is not an
   Anthropic model. A buyer who has diligenced Anthropic and been told "we use
   Anthropic" would, on this path, be wrong about both the model vendor and the
   serving infrastructure.

4. **Production rejects it in code.** `docker-compose.yml` passes no
   `OPENROUTER_API_KEY`, and `build_provider` also refuses an OpenRouter
   credential whenever `ENVIRONMENT=production`. Adding one environment
   variable therefore stops startup instead of changing the sub-processor.

Two adjacent facts worth having in the same answer:

- **The budget guarantee is weaker on this path.** OpenRouter has no pre-call
  token-counting endpoint, so `count_tokens` estimates locally with tiktoken
  and a 1.5× margin (`openrouter.py:228-234`). Invariant 8's reservation is
  approximate here in a way it is not on Anthropic. `reconcile_provider` still
  corrects to actuals, so the aggregate ceiling holds — but the *pre-call*
  reservation can be wrong by the margin. This is documented honestly in the
  module docstring and in CLAUDE.md.
- **No model on this path currently completes an agent route.** The
  `openrouter.py` docstring (`:24-41`) records, from a live CP-1 run, four
  distinct ways `z-ai/glm-5.3-flash` fails the module contract, each of which
  the host correctly refuses. So the practical exposure today is low. The
  binding is groundwork; the disclosure obligation attaches the moment a model
  on it succeeds.

### 5.5 The answer to give a buyer

> With agent execution disabled, or on screen-depth routes, no customer data
> leaves the deployment. Screen-depth execution may currently refuse because
> fixed deterministic summaries are test-only; refusal does not transmit data.
> With production agent execution enabled, startup accepts only one exact,
> current, qualified Anthropic binding. Agent modules send document filenames,
> digests, a block index, validated upstream analysis, and only the evidence
> blocks requested through the audited `read_evidence` tool. The host enforces
> a per-run byte ceiling. Every successfully usage-validated message-generation response has a bounded
> attempt record, and every accepted output is bound to the durable provider
> identity. OpenRouter remains available only for development and is rejected
> by production startup.

That statement describes the enforced code path. It is not evidence that a
live Anthropic credential and qualification record have completed the protected
enterprise matrix, nor does it replace Anthropic's commercial terms or DPA.

---

## 6. Suggested order of work

Not a plan — a sequencing opinion, since the gaps have very different
cost-to-close ratios.

| Order | Gap | Why here |
|---|---|---|
| 1 | G3 (define periods) | Costs no code and is a prerequisite for G1's scope |
| 2 | G8 (log rotation), G5 (volume encryption) | Compose/ops changes measured in lines; both are pure risk reduction |
| 3 | G4 (name withdrawal honestly in the UI) | Copy change; prevents a misrepresentation |
| 4 | G1 + G11 + G2 (the cascade) | The real work. Needs design against §2.3 and §4.2-G11 before estimation |
| 5 | G7 (backup lifecycle) | Only meaningful once G1 exists |
| 6 | G9 (data map), L1 (attribution notice) | Documentation, but L1 blocks distribution |

Task 5 closed the former G6 checkpoint and G10 runtime-attribution defects.
Protected live qualification, processor contracts, and downstream publication
provenance remain candidate gates rather than completed audit evidence.

---

## 7. What was not verified

Stated so nothing above is read as stronger than it is.

- **The original audit executed nothing.** Its retention claims came from
  source inspection. The 2026-09-01 Task 5 correction reflects the current
  implementation and its recorded host-control tests; it does not claim a live
  provider, container, or enterprise qualification run.
- **Provider contract terms are out of scope.** This document says which
  organisation receives what data. It does not characterise Anthropic's or
  OpenRouter's terms, retention, or training policies — those are commercial
  documents, they change, and paraphrasing them from memory is exactly the kind
  of claim an enterprise buyer's counsel will check. Read them directly and
  attach them to the DPA.
- **Vendored methodology bundle not audited for embedded data.**
  `caos/server/caos/methodology/vendor/deploy_v/` was enumerated but its
  contents were not read. It is asserted to be methodology authority, is
  integrity-pinned, and is never edited (invariant 4). Whether it contains
  example issuer data was not checked.
- **`Modular OS/`, `notes/`, `qa/`, `.agent-reviews/`, `DESIGN-IS-2026-08-27/`**
  were not examined for customer or personal data. They are described as
  read-only reference material. A pre-distribution sweep should cover them.
- **The test corpus is real third-party documents.** `caos/tests/corpus/documents/`
  is gitignored (`caos/tests/corpus/.gitignore`) and acquired from the issuer's
  investor-relations site by `fetch.sh`, then uploaded through the public source
  route during tests. Not customer data, but it is real issuer material sitting
  on developer machines and CI runners, and it is outside every control
  described above.
- **Docker's default logging driver** is asserted from the absence of a
  `logging:` block in `docker-compose.yml` and the daemon's documented default,
  not from an inspected running daemon. If the deployment host sets a non-default
  driver in `daemon.json`, G8's shape changes.
- **PostgreSQL row-level behaviour under concurrency** was not exercised;
  CLAUDE.md already records that `_next_source_set`'s lock has never been run
  against a live PostgreSQL.
- **The enterprise-readiness documents postdate the original audit.**
  `ENTERPRISE_TESTING_READINESS.md` and `ENTERPRISE_READINESS_PLAN.md` are now
  tracked. Their provider requirements are reflected in this correction; their
  broader retention and deletion requirements still need reconciliation with
  §4.
