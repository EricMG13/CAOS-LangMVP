# CAOS — data handling, retention, and boundary audit

Audit performed 2026-08-31 against `claude/license-data-retention-audit-36ec68`
at `e224d9e`. The filename carries the date requested in the brief.

This is an engineering document. Every claim below is grounded in a file and
line that was read during the audit; anything unverified is marked as such in
§7 rather than asserted. It is not legal advice and not DPA prose — it is the
factual substrate a DPA would have to be drafted against, plus the list of
commitments the code cannot currently honour.

**Headline.** CAOS has no deletion capability of any kind. Not a partial one, not
a slow one — zero. There is no `DELETE` route on the API (43 routes, none),
no purge job, no TTL, no expiry, and no retention configuration anywhere in
`caos/server` or `caos/deploy`. Every uploaded document byte, every extracted
evidence block, every model-authored artifact, every audit row and every
container log line persists for the life of the volume. Source withdrawal
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
2. **Domain database** — SQLite in dev, PostgreSQL in production
   (`caos/server/run.py:44`), on the `postgres-data` named volume.

Run checkpoints ride the vault volume, not the database:
`caos/server/run.py:46-51` sets `checkpoint_path=data / "checkpoints.db"` and
`data` defaults to `settings.storage_dir` (`run.py:76`). This is deliberate and
noted in the code.

### 2.2 Inventory

| # | Data class | Where it lives | Content? | Lifetime | Deletable today |
|---|---|---|---|---|---|
| A | Uploaded document bytes | Vault: `<storage_dir>/sources/<sha[:2]>/<sha256>` (`sources/domain.py:57-75`) | Content (verbatim original) | Indefinite | **No.** `Vault` has `put` and nothing else. No delete method exists on the class. |
| B | Extracted text / evidence blocks | `sources.blocks` JSON column (`storage/store.py:63`), written at ingest (`sources/domain.py:387,396`) | Content (full extracted text, up to 12 MB per source) | Indefinite | **No.** No row is ever deleted; `withdraw` only sets a flag. |
| C | Source metadata | `sources` row: `filename`, `media_type`, `bytes`, `sha256`, `created_by`, `created_at` (`storage/store.py:54-78`) | Identifiers + Identity; filenames are often themselves signal ("Project X lender presentation") | Indefinite | **No.** |
| D | Analyst notes | `notes.body` TEXT (`storage/store.py:93`); a promoted note becomes a synthetic source row (`store.py:458`, `source_kind="analyst_note"`) | Content (analyst prose, which in a credit context is where MNPI is most likely to be written down verbatim) | Indefinite | **No.** No note delete or edit route. |
| E | Loan-universe rows | `loan_universes.rows` (`storage/store.py:125`), `rv_universes.rows` (`store.py:139`) | Content — includes `borrower_name` (`artifacts/loan_universe.py:66,469`) and position-level fields | Indefinite | **No.** Withdrawal flips `status` to `WITHDRAWN` (`store.py:344-349`); rows stay. |
| F | Prompts sent to the provider | Constructed in-memory in the node body (`engine/loop.py:146`, `engine/authority.py:86-99`); the message list is a local variable | Content in transit | **Not persisted.** Ephemeral per node execution. | n/a — nothing to delete |
| G | Provider responses (agent modules) | `run_artifacts.payload` JSON + `run_artifacts.markdown` TEXT (`storage/runs.py:63-64`); the envelope permits up to 2 MiB of markdown (`methodology/canonical.py:48`) | Content — the model's analysis, including its Evidence Trace section, which is where verbatim document quotation lands | Indefinite | **No.** The only `DELETE` on `run_artifacts` (`storage/runs.py:311`) is the validate-then-replace arbitration inside `complete_node`, not a retention control. |
| H | Deterministic artifacts | Same table | Mostly Identifiers — `build_deterministic_payload` is a pure function of ids (`engine/deterministic.py:73-81`). **Exception:** CP-3 embeds the full pinned loan universe, borrower names included, at `engine/deterministic.py:71` | Indefinite | **No.** |
| I | Accepted snapshots | `run_snapshots.artifacts` (`storage/runs.py:86`) | Identifiers + digests | Indefinite | **No.** |
| J | Model builds and revisions | `model_builds.payload` (`storage/models.py:39`), `model_revisions.record` (`storage/models.py:59`); rendered workbooks in the vault at `models/<case_id>/<target_id>/<sha256>.xlsx` (`models/service.py:910-913`) | Content — a credit model carries the issuer's figures | Indefinite | **No.** |
| K | Deliverable drafts, frozen versions, exports | `deliverable_revisions.content` (`storage/deliverables.py:31`), `deliverable_frozen.payload` (`deliverables.py:48`); export bytes at `<storage_dir>/deliverables/<thread_id>/<format>` (`deliverables/service.py:553-556`) | Content — the committee memo itself | Indefinite | **No.** The one `unlink` (`deliverables/service.py:768`) is `delete_export_for_tests`. |
| L | Audit events | `audit_events` table (`storage/store.py:144-152`), append-only, `data` JSON at `store.py:151` | Identifiers + **Identity** (`actor` on every row, `store.py:173-176`). One row carries free text: `deliverable.changes_requested` stores `comment[:300]` (`storage/deliverables.py:277-278`) | Indefinite | **No.** No delete, no archival, no rotation. `audit_trail` only reads (`store.py:182`). |
| M | Run events | `run_events` (`storage/runs.py:71-79`) | Identifiers only. `run.failed` carries `{code, module_id}` and nothing else (`storage/runs.py:340-342,363`) | Indefinite | **No.** |
| N | Run checkpoints | `checkpoints.db` on the vault volume (`run.py:50`), LangGraph `AsyncSqliteSaver` (`engine/runtime.py:134-144`) | **No content.** `RunState` is `run_id`, `case_id`, `plan`, `plan_digest`, artifact *refs*, `node_status`, `error` (`engine/state.py:23-31`). The provider message list never enters state. | Indefinite | **No** — see G-6 below; the decision record requires a `delete_thread` that was never implemented. |
| O | Assumptions | `assumptions.data`, `assumptions.evidence_ids` (`storage/store.py:104-105`) | Content (analyst-entered figures) | Indefinite | **No.** Withdrawal marks them `STALE` (`store.py:338-341`); rows stay. |
| P | Identity and membership | `cases.created_by`, `case_members.subject` (`store.py:40,50`), plus `created_by` on sources, runs, artifacts, revisions, exports | **Identity** (OIDC subject or email) | Indefinite | **No.** There is no member-removal route (CLAUDE.md's known-gaps ledger records `/api/cases/{id}/members` as having no route at all; the route inventory confirms it). |
| Q | Backups | `caos.dump.age` + `vault.tgz.age` at an operator-chosen path (`caos/deploy/backup.sh:74-76`) | Content — "the complete confidential credit corpus" in the script's own words (`backup.sh:4`), age-encrypted | Indefinite, and *by design out of scope*: "Retention and destination ACLs belong to the storage layer" (`backup.sh:20`) | **No.** Each run overwrites the same two fixed filenames; there is no generation management and no expiry. |
| R | Container logs | Docker `json-file` driver (compose declares no `logging:` block, so the daemon default applies); uvicorn access log is on because `run.py:68` constructs `uvicorn.Config(app, host=host, port=port)` with defaults | Identifiers + **client IP** in every access line | Indefinite and unbounded — no `max-size`/`max-file` anywhere in `docker-compose.yml` | **No.** |

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

Requirements are numbered `R`; the gaps are numbered `G` and are the
deliverable. Every gap is a thing the code cannot do today, not a thing that is
merely undocumented.

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
| R9 | Deterministic execution paths involve no external processor at all | `engine/runtime.py:372-386`: agent dispatch requires `mode == "agent"` **and** `settings.agent_execution_enabled`; everything else takes `build_deterministic_payload` |

### 4.2 Requirements the code cannot satisfy — the gap list

---

**G1 — There is no end-of-contract deletion. (Blocking.)**

GDPR Art. 28(3)(g) requires the processor to delete or return all personal data
at the end of the service, at the controller's election. There is no code path
that does either.

- No `DELETE` route exists: 43 registered `/api` routes, zero of them `DELETE`
  (`grep -c '@app.delete' caos/server/caos/api/__init__.py` → 0).
- No case-deletion, source-deletion, run-deletion, or member-removal function
  exists on any store.
- The only four non-test `DELETE`/`unlink` statements in the entire server are
  integrity operations, not retention ones: `storage/deliverables.py:295`
  (delete-then-insert while replacing a case's single deliverable-authority
  row in `set_authority`), `storage/runs.py:311` (validate-then-replace inside
  `complete_node`, DECISIONS §12.8), and `sources/domain.py:74` plus
  `atomic_files.py:84` (removing the temp file after an atomic rename). Two
  further `unlink`/`delete` call sites exist and are both `*_for_tests`
  helpers: `deliverables/service.py:768` and `engine/runtime.py:851`.

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

**G6 — Run checkpoints accumulate forever, against an explicit decision that says they should not.**

`docs/DECISIONS.md` §12.E item 25 is binding and unambiguous: "Terminalized
threads are deleted (`delete_thread`) once the domain store holds the full
audit trail." `grep -rn 'delete_thread\|adelete_thread' caos/` returns nothing.
It was never implemented.

Severity is genuinely low on the content axis — `RunState`
(`engine/state.py:23-31`) holds no document text, and the provider message list
lives in a node-body local (`engine/loop.py:146`), never in a channel. It is
listed because it is an unmet binding decision and because `checkpoints.db`
grows without bound on the same volume as the vault, which is a durability
problem before it is a privacy one.

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

CLAUDE.md's known-gaps ledger already records that backup encryption is
untested here — `age` and a running Compose stack do not exist in this
worktree, so only the scripts' syntax has been checked. Both facts belong in
the same DPA answer.

---

**G8 — Container logs are unbounded and contain personal data.**

`docker-compose.yml` declares no `logging:` block for any of the six services,
so the Docker daemon default applies — `json-file`, no `max-size`, no
`max-file`, no rotation. `run.py:68` builds `uvicorn.Config(app, host=host, port=port)`
without `access_log=False`, so uvicorn's access log is on, and each line carries
a client IP (personal data under GDPR) alongside a request path containing
case, run, and source identifiers.

No application logger writes content. The non-vendored server code contains
zero occurrences of `import logging`, `logging.`, or `logger`, and exactly one
`print` — `caos/server/worker.py:76`, which emits `{"processed": <count>}`. So
this is a metadata-and-IP exposure, not a content one. It is still an unbounded, unrotated, unretained store of
personal data outside the two data planes anyone would think to purge.

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

**G10 — Sub-processor disclosure is not derivable from configuration, and the one ledger that records a model records the wrong one.**

Which external processor sees customer content depends on which of two
environment variables is set, resolved at process start with no record of the
outcome (`caos/server/run.py:24-36`). There is no startup log line, no field on
`/api/health`, and no audit event naming the active provider.

The single place a model is persisted is the attempt ledger, and on the
OpenRouter path it is **wrong**, not merely incomplete:

```python
attempt_base = {"run_id": run_id, "module_id": module_id, "model": self.settings.anthropic_model}
```

`caos/server/caos/engine/runtime.py:488`. This is unconditional — it reads
`anthropic_model` regardless of which provider `build_provider` actually
selected. On the OpenRouter path `ANTHROPIC_API_KEY` is by definition unset
(`run.py:32`), so `anthropic_model` holds its default `"claude-sonnet-4-6"`
(`config.py:45`), and every row `record()` writes into `run_budgets.attempts`
(`runtime.py:491-502`, stored in `run_budgets.attempts`, `storage/runs.py:100`) claims a run served by
`z-ai/glm-5.3-flash` was served by Claude Sonnet.

This is worse than a missing field. A missing field is an unanswerable
question; a wrong field is an audit record that would be produced in good faith
to a regulator or a buyer and would be false. It also defeats the only forensic
route to reconstructing which sub-processor handled a past run.

A DPA lists sub-processors and commits to notifying the controller before they
change. Today, changing the sub-processor is an env-var edit that leaves no
evidence — and leaves positively misleading evidence. See §5 for why the two
answers are materially different.

*Closing it:* select the model string from the active provider rather than from
settings, and emit the resolved provider identity as a startup audit event.
Small change, but it touches `caos/`, so it is out of scope for this session.

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
| R17 | Named sub-processors, with change notification | **G10 — not observable; attempt ledger actively misattributes** |
| R18 | Ability to scope a breach to affected controllers | **G9 — manual** |
| R19 | Execution telemetry does not outlive its purpose | **G6 — unmet decision** |

Ten requirements a standard processor DPA carries; **ten the code cannot
currently satisfy.** No partial credit is claimed anywhere in that table.

---

## 5. What leaves the boundary

This is the first question an enterprise buyer asks, so it is answered
exhaustively.

### 5.1 When anything leaves at all

Nothing leaves unless **both** conditions hold
(`caos/server/caos/engine/runtime.py:378`):

```python
elif mode == "agent" and self.settings.agent_execution_enabled and run_id not in self._scripted_runs:
```

- `AGENT_EXECUTION_ENABLED` defaults to `false` (`config.py:54`) and is strict —
  any value other than the literal `true`/`false` raises (`config.py:9-17`).
- Screen-depth routes are deterministic end to end by catalog design
  (`DECISIONS.md §1`), and the dispatch takes `spec.mode_screen` at that depth
  (`runtime.py:372`).

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
   from the run's `created_at` (`runtime.py:452-465`). **The case name, issuer
   name and sector the analyst typed are *not* sent** — `issuer_id` is the
   opaque case id, not `cases.issuer`. Worth knowing; it is better than a buyer
   will assume.
2. `source_metadata_manifest` — for each live source: `source_id`, `sha256`,
   **`filename`**, `media_type`, and per-block `block_id`, `locator`,
   `extractor_version`, `confidence` (`runtime.py:438-450`). **No block text.**
3. `validated_upstream_artifacts` — the full `markdown` of every upstream
   module artifact (`runtime.py:471`, `authority.py:82-85`). This is
   customer-derived analytical content, up to 2 MiB per artifact.
4. A fixed confidence-input contract. No customer data.

**Tool results** — verbatim customer document text. When the model calls
`read_evidence`, the host returns the block `text` field itself
(`engine/evidence.py:113`) serialised into the next user turn
(`engine/loop.py:241`). This is the primary content egress.

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

Selected when `ANTHROPIC_API_KEY` is set; it wins whenever both keys are
present (`caos/server/run.py:28-31`). Requests go directly to Anthropic's
Messages API via `langchain_anthropic`'s pinned async client
(`engine/anthropic.py:71,78`). Default model `claude-sonnet-4-6`
(`config.py:45`).

**One named processor, one hop, one contractual counterparty.** The relevant
terms are Anthropic's commercial terms and DPA, which the buyer's counsel will
read directly — this repository is not the authority on them, and this document
deliberately does not paraphrase them (see §7).

`caos/deploy/docker-compose.yml` passes `ANTHROPIC_API_KEY` and
`ANTHROPIC_MODEL` to both the `app` and `worker` services. Anthropic is
therefore the *only* provider reachable from the shipped production stack.

### 5.4 OpenRouter — yes, this changes the answer materially

Selected only when `OPENROUTER_API_KEY` is set and `ANTHROPIC_API_KEY` is not
(`run.py:32-35`). Default model `z-ai/glm-5.3-flash` (`config.py:52`).

Four differences, all read off `caos/server/caos/engine/openrouter.py`:

1. **OpenRouter is a broker, not an inference provider.** The request goes to
   `https://openrouter.ai/api/v1/chat/completions` (`openrouter.py:53,198`),
   and OpenRouter forwards it to whichever upstream provider serves the named
   model. The buyer's data therefore reaches **at least two** organisations,
   the second of which is chosen by OpenRouter's routing rather than by CAOS.
   Anthropic is one hop; this is two or more.

2. **The upstream is not pinned and not disclosed.** `_payload`
   (`openrouter.py:160-180`) sends `model`, `messages`, `tools`, `tool_choice`,
   `parallel_tool_calls`, `response_format`, and `max_tokens`. It does **not**
   send OpenRouter's `provider` routing object, so there is no pinned upstream
   allowlist and no data-collection policy asserted on the request. Which
   organisation processes a given run's document text is therefore not
   determined by this codebase, and is not recorded anywhere afterwards. For a
   sub-processor list (G10), that is not a gap in the disclosure — it is an
   answer that cannot be given.

3. **The default model is third-party.** `z-ai/glm-5.3-flash` is not an
   Anthropic model. A buyer who has diligenced Anthropic and been told "we use
   Anthropic" would, on this path, be wrong about both the model vendor and the
   serving infrastructure.

4. **It is not reachable from the shipped stack — today.**
   `docker-compose.yml` passes no `OPENROUTER_API_KEY` to `app` or `worker`, so
   the production Compose deployment cannot select it. That is a fact about the
   current compose file, not an enforced invariant: nothing in the code refuses
   the OpenRouter binding in production, and adding one environment variable
   silently changes the sub-processor with no audit event and no health-endpoint
   signal. Treat it as a configuration property, not a control.

Two adjacent facts worth having in the same answer:

- **The budget guarantee is weaker on this path.** OpenRouter has no pre-call
  token-counting endpoint, so `count_tokens` estimates locally with tiktoken
  and a 1.5× margin (`openrouter.py:184-190`). Invariant 8's reservation is
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
> leaves the deployment. With it enabled on a full-depth route, nine analytical
> modules send Anthropic the document filenames, their digests, a block index,
> the analysis produced by upstream modules, and — only when the model requests
> a specific block through the audited `read_evidence` tool — the verbatim text
> of that block, under a per-run byte ceiling the host enforces before each
> read. Anthropic is the single sub-processor in the shipped configuration.
> An alternative OpenRouter binding exists in the codebase; it is not reachable
> from the shipped stack, and if it were enabled it would introduce a broker
> plus an undisclosed upstream provider. We would notify before enabling it.

That statement is accurate as of this audit. It stops being accurate the moment
someone sets `OPENROUTER_API_KEY` in production, which is why G10 matters.

---

## 6. Suggested order of work

Not a plan — a sequencing opinion, since the gaps have very different
cost-to-close ratios.

| Order | Gap | Why here |
|---|---|---|
| 1 | G3 (define periods) | Costs no code and is a prerequisite for G1's scope |
| 2 | G8 (log rotation), G5 (volume encryption) | Compose/ops changes measured in lines; both are pure risk reduction |
| 3 | G10 (record the active provider) | Two small changes — take the model string from the live provider, emit a startup audit event. Converts an unanswerable DPA question into an answerable one and removes a false audit record |
| 4 | G4 (name withdrawal honestly in the UI) | Copy change; prevents a misrepresentation |
| 5 | G6 (`delete_thread`) | Discharges a binding decision; small, and exercises the deletion-with-audit pattern before the hard one |
| 6 | G1 + G11 + G2 (the cascade) | The real work. Needs design against §2.3 and §4.2-G11 before estimation |
| 7 | G7 (backup lifecycle) | Only meaningful once G1 exists |
| 8 | G9 (data map), L1 (attribution notice) | Documentation, but L1 blocks distribution |

---

## 7. What was not verified

Stated so nothing above is read as stronger than it is.

- **Nothing was executed.** No test suite, no server, no container. Every claim
  is from reading source. Behavioural claims about withdrawal, evidence
  refusal, and dispatch are read off the code paths cited, not observed at
  runtime.
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
  is gitignored (`caos/tests/corpus/.gitignore`) and fetched from EDGAR by
  `fetch.sh`. Not customer data, but it is real issuer material sitting on
  developer machines and CI runners, and it is outside every control described
  above.
- **Docker's default logging driver** is asserted from the absence of a
  `logging:` block in `docker-compose.yml` and the daemon's documented default,
  not from an inspected running daemon. If the deployment host sets a non-default
  driver in `daemon.json`, G8's shape changes.
- **PostgreSQL row-level behaviour under concurrency** was not exercised;
  CLAUDE.md already records that `_next_source_set`'s lock has never been run
  against a live PostgreSQL.
- **Two documents referenced by `README.md` were not read.**
  `ENTERPRISE_TESTING_READINESS.md` and `ENTERPRISE_READINESS_PLAN.md` are not
  tracked in git and are absent from this worktree; they exist as untracked
  files in the primary checkout, i.e. as somebody's uncommitted work in
  progress. `README.md` calls the first of them "the binding gate". If either
  carries retention or data-handling commitments, this audit has not seen them
  and they must be reconciled against §4 — and committed, since a binding gate
  that lives only on one machine is not a gate.
