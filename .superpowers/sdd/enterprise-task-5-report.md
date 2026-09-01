# Enterprise Task 5 report — provider authority and false-success removal

Implementation commit: `fe2fed45d0cfc14fc3ecc6ecdf4b5a61770dc3f6`.
Authority correction: `9b0f16d` (2026-09-01).

## Delivered

- Added frozen `ProviderIdentity`, its canonical self-digest/integrity check, strict v1 `ProviderQualification` parsing/loading/binding checks, safe host-only parameter/context metadata and digest, and explicit host-control identity.
- Anthropic and OpenRouter now expose one immutable identity with adapter-version constants. OpenRouter refuses qualification claims and remains explicitly unqualified/development-only.
- `ProviderMessage` now carries optional observed model/provider version. Both adapters use response-supplied values; OpenRouter never attributes to the Anthropic setting.
- Parsed `CAOS_PROVIDER_QUALIFICATION_PATH` and `CAOS_PROVIDER_QUALIFICATION_DIGEST`; removed the proven-unused `anthropic_timeout_seconds` setting.
- Added adapter/config/qualification tests. The existing dual-client lifecycle remains covered; a successful close now clears LangChain's closed shared-client cache so a later adapter cannot inherit it.

## Commands and results

```text
uv run --directory caos/server --extra dev pytest ../tests/test_provider_identity.py ../tests/test_anthropic_provider.py ../tests/test_openrouter_provider.py ../tests/test_config_and_vault.py
47 passed in 0.76s

uv run --directory caos/server --extra dev ruff check caos/engine/provider.py caos/engine/anthropic.py caos/engine/openrouter.py caos/config.py ../tests/test_provider_identity.py ../tests/test_anthropic_provider.py ../tests/test_openrouter_provider.py ../tests/test_config_and_vault.py
All checks passed!

git diff --check
passed

rg -n 'anthropic_timeout_seconds' caos
no matches
```

## Confidence review

1. Qualification JSON error classification — malformed or duplicate-key JSON originally shared the missing-file path. Reproduced with duplicate keys; changed it to `AGENT_PROVIDER_UNQUALIFIED` and retained `AGENT_QUALIFICATION_MISSING` only for unreadable files. Covered by `test_qualification_record_digest_and_binding_are_strict`.
2. Time-zone edge — a naive caller-supplied validation time would have adopted the host local zone. Reproduced with `datetime.now()`; it now fails closed. Future/expired UTC boundaries are covered.
3. Identity tampering, optional observed fields, and policy secrecy — verified the frozen identity's stored digest detects forced mutation, both response adapters preserve supplied values only, and the identity serialization contains no test API keys. The policy preimage has exactly `provider`, `adapter`, `transport`, `counting`, `loop`, `tool`, `schema`, and `modules`.
4. Constructor/lifecycle cleanup — qualification construction occurs before either SDK/HTTP client is created. Real dual-client closure is covered, including constructing a later adapter after a prior close; the SDK cache is cleared only after both closes succeed.
5. Independent review reproduced three authority gaps: provider-version binding was omitted, a forced mutation of the frozen qualification was not reverified, and stored identity reconstruction had no strict digest-aware path. The shared values now bind provider version, reverify the complete qualification preimage before use, and reconstruct only an exact ten-field identity whose claimed digest matches. Field-by-field adversarial mutation matrices passed for both values.
6. The corrected strict gate passed with `49 passed in 0.87s` under fatal `ResourceWarning`, `RuntimeWarning`, and `PytestUnraisableExceptionWarning`; Ruff and `git diff --check` passed. Two fresh interpreter processes produced the same host-control identity digest.

## NOT PROVED

- Runtime preflight, persistence, API projection, recovery comparison, response-substitution refusal, and deterministic false-success removal are 5B–5D and were not started.
- A live model has not been qualified. This packet builds only the fail-closed record primitive.

## BLOCKED EXTERNAL

- No genuine qualification record, protected Anthropic credentials, or live six-pathway qualification evidence was supplied. No external provider call was made.

## Risks / follow-up

- The parameter/context digest is intentionally sensitive to installed adapter/runtime versions and policy constants; a change requires a new qualification record.
- Task 5A's corrected authority boundary is accepted for local execution. User-controlled mode means no delegated reviewer is active; later Task 5 and final candidate gates still require the plan's independent enterprise evidence.

## Task 5B — durable authority and strict wire contract

Delivered:

- Added nullable JSON provider-identity columns to runs, artifacts, and snapshots. Fresh metadata creates them; existing SQLite databases evolve inside serialized `BEGIN IMMEDIATE` rechecks; PostgreSQL uses idempotent `ADD COLUMN IF NOT EXISTS`. Unsupported dialects abort startup.
- New runs validate and store one exact identity atomically with `run.created`; every subsequent run/node event carries its digest. Artifacts copy the run identity and reject divergent relinks. Snapshots copy the run identity, reject caller divergence, and require their digest to bind it.
- Legacy rows remain `null`; no environment or current provider backfill exists.
- Added strict provider identity and provider-attempt wire models. Run, generation, artifact, and snapshot responses project stored identity; generation model derives from stored identity, never Anthropic settings. Unknown attempt fields are dropped and a missing historical attempt identity remains `null` rather than being synthesized from its run.

Verification:

```text
python -m pytest caos/tests/spec/test_runs_spec.py caos/tests/spec/test_http_contracts_spec.py -q \
  -W error::ResourceWarning -W error::RuntimeWarning \
  -W error::pytest.PytestUnraisableExceptionWarning
113 passed, 1 third-party Starlette deprecation warning in 9.16s

python -m ruff check <Task 5B files>
All checks passed!

git diff --check
passed
```

Confidence review:

- Reproduced and fixed an attempted API backfill: a stored attempt lacking identity was initially projected with the run identity. It now remains honestly `null`, while the strict projection removes an injected `raw_body` field.
- Adversarial checks reject identity-divergent artifact relinks, snapshot identity substitution, and stale snapshot digests. Two concurrent SQLite initializers add each missing column once and preserve a legacy run as `provider_identity: null`.
- PostgreSQL schema-race execution remains `BLOCKED EXTERNAL` until `CAOS_TEST_POSTGRES_URL` is supplied. Runtime capture, attempt persistence, payload/plan binding, recovery checks, and false-success removal remain Task 5C rather than being claimed here.

## Task 5C — runtime enforcement, attempt audit, and false-success removal

Delivered:

- The engine captures provider identity once, preflights every agent route before creating a run, and binds the stored identity into the plan, input fingerprint, artifact row/payload, accepted snapshot, run events, acceptance audit, API generation state, and bounded provider-attempt ledger.
- Every provider response is usage-validated, spend-reconciled, and audit-digested before its observed model/version is compared with the run pin. A substituted response cannot execute a tool, validate output, or mint an artifact; billed usage and the bounded attempt remain durable.
- Qualified identities are rechecked for expiry at start, provider use, resume, wait, recovery, and new acceptance. Restart drift, legacy-null authority, malformed stored identities, and response substitution fail closed before provider contact or output use.
- The fixed deterministic `COMPLETE` payload is now host-control-only. Ordinary screen and deterministic-designated execution returns `DETERMINISTIC_EXECUTOR_UNAVAILABLE`; tests require an explicit per-run, memory-only capability that is absent from HTTP and must be deliberately restored after restart.
- Placeholder artifacts cannot be reused, finalized, or accepted after that memory-only capability disappears. Successful host-control runs keep it only until acceptance; failure and identity-quarantine paths clear it.
- Identity failures durably remove checkpoints, scripted/placeholder capabilities, and outstanding resume tickets. A malformed identity may omit its unverifiable digest only from the exact `run.failed / AGENT_IDENTITY_MISMATCH` event; every other event remains strict.
- Provider/qualification preflight refusals map to HTTP 503, admission remains 409, and user/path validation remains 422. Strict wire models normalize bounded scalar attempt metadata and never expose provider bodies, prompts, evidence text, or exceptions.

Verification (separate pytest processes avoid the repository's root/spec fixture-discovery collision):

```text
Task 5C core runtime/spec gate
228 passed, 1 third-party Starlette deprecation warning in 10.25s

HTTP and injection contracts
95 passed, 1 third-party Starlette deprecation warning in 11.81s

Model-builder compatibility
93 passed, 1 third-party Starlette deprecation warning in 101.72s

Provider identity, module wiring, and finalization metering
27 passed in 2.66s

State/replay contracts
16 passed, 1 third-party Starlette deprecation warning in 0.69s

20–30-document corpus host-control pathways
26 passed, 1 third-party Starlette deprecation warning in 122.33s

Ruff over every changed Task 5C file
All checks passed!

git diff --check
passed
```

Confidence review:

1. **Identity currency and error taxonomy.** Reproduced expiry at start, resume, wait, recovery, and acceptance. Expiry now fails durably with `AGENT_QUALIFICATION_EXPIRED`; provider/qualification preflight is 503 rather than being misclassified as user validation.
2. **Substitution plus overspend ordering.** Reproduced a response whose model mismatched while actual usage exceeded the reservation. Reconciliation and the bounded generation attempt commit first; identity mismatch wins before tool/output processing, while spend and in-flight truth remain correct.
3. **Malformed provider metadata and privacy.** Reproduced non-JSON/cyclic response values and non-string request/model/version/stop metadata. Digests remain deterministic and privacy-safe; served attempts contain only allowlisted, bounded scalar fields plus the strict host identity.
4. **Test capability escape and restart.** Reproduced ordinary API execution, restart without capability, artifact relink, finalization, and acceptance. No ordinary path can persist or accept placeholder success; only explicit host-control methods can restore the known run ID.
5. **Malformed artifact shape.** Independent review reproduced digest-valid list/scalar artifact payloads causing `AttributeError`. Both finalization and acceptance now require a mapping and return typed `RUN_NOT_READY`; list and scalar regressions pass.
6. **Malformed stored identity transaction.** Independent review reproduced `run.failed` rollback when its audit event reparsed the same invalid identity. The exact mismatch terminal event can now omit the unverifiable digest, and the run, checkpoint, capability, and ticket cleanup commits atomically with zero provider calls.
7. **Terminal ticket leak.** Independent review found paused identity failures left one-shot resume tickets live. `finalize_failure` now consumes every outstanding ticket in its existing transaction; malformed and expired recovery cases prove no live ticket remains.
8. **Replay equivalence.** The broader state gate caught that the direct replay helper omitted the newly bound provider identity (and CP-3 universe input). It now mirrors the ordinary deterministic artifact preimage; the day-boundary digest invariant passes.

By design / deferred:

- Host-control placeholder outputs are not candidate evidence and cannot establish enterprise readiness.
- PostgreSQL schema-race execution remains `BLOCKED EXTERNAL` without `CAOS_TEST_POSTGRES_URL`.
- Live qualified Anthropic execution remains `BLOCKED EXTERNAL` until a genuine protected qualification record and credential are supplied in Tasks 11/13.
- Source-computed deterministic executors are required before ordinary pathway success; that work is pulled forward into the pathway/model packets rather than restoring false success.
- No rewrite tournament was run because the user explicitly prohibited rewrite tournaments for this session.

## Task 5D — enterprise startup and final phase gate

Delivered:

- Production startup now accepts only one enabled, current, digest-bound qualified Anthropic identity. It refuses ambiguous credentials, OpenRouter, incomplete qualification configuration, missing credentials, and mismatched or expired authority without fallback.
- `run.py` is production-only and `dev.py` is development-only. Shared runtime validation runs before files, logging, stores, providers, or network listeners are owned.
- The app and worker share the PostgreSQL/password gate, including blank and percent-encoded placeholder refusal. Only the HTTP app receives edge/session, ClamAV, provider, and qualification settings; the export worker receives database and vault settings only.
- Direct production `Engine` construction rejects every non-Anthropic or unqualified provider identity. Placeholder/scripted test capabilities additionally require a verified development `host_control` identity, so an in-process caller cannot turn production or a real development provider into fixture success.
- Normal and failed server shutdown closes the engine and async provider on the same event loop that served requests. A lock-acquisition failure before serving closes unused async resources separately; the synchronous store always closes while the originating failure is preserved.
- Deployment examples, buyer-facing data handling, threat model, README, CLAUDE guidance, and the quality ledger now state the enabled/disabled qualification boundary, provider-attempt limitations, checkpoint backend, worker secret boundary, placeholder refusal, and remaining external evidence honestly.

Verification:

```text
Focused startup/lifecycle gate
44 passed, 2 PostgreSQL-dependent tests skipped

Independent settled Task 5D gate
373 passed, 2 PostgreSQL-dependent tests skipped, 1 third-party Starlette deprecation warning

Full backend regression after the final code change
766 passed, 2 PostgreSQL-dependent tests skipped, 1 third-party Starlette deprecation warning in 283.91s

run_sec_audit.py
50 routes, 42 case-boundary routes, 0 failures

ruff check caos
All checks passed!

quality_ledger_coverage.py
45 routes, 232 product files, 120 features; complete

git diff --check
passed
```

Final confidence review:

1. **Startup ordering and rollback.** Invalid environment, database, secret, provider, and qualification states are refused before progressively owned resources; construction and lock-acquisition failures close everything already owned.
2. **Async lifecycle affinity.** Independent review reproduced provider close on a second loop. Cleanup now runs inside the serving loop on both normal and exceptional exits, with a regression asserting identical loop identity for service, engine close, and provider close.
3. **Provider ambiguity and disabled behavior.** Empty/whitespace credentials, dual keys, partial qualification pairs, OpenRouter in production, and clean disabled configurations were adversarially exercised. Disabled execution creates no provider; it does not silently validate or claim a live qualification.
4. **Test-capability escape.** All three fixture-success entry points refuse production engines and real development providers; only a verified development `host_control` identity can use them.
5. **Database credential parsing.** Blank and percent-encoded documented placeholders are decoded and refused at the shared app/worker gate.
6. **Truth and privacy.** Two independent read-only reviews traced documentation claims to current code. Usage-invalid responses are described as terminal-code-only; token-count calls are bounded but not falsely described as durable attempts or logs; full identities and digest-only events are distinguished.

`BLOCKED EXTERNAL`:

- The two live-PostgreSQL tests require `CAOS_TEST_POSTGRES_URL`; their skips are not counted as passes.
- No genuine protected Anthropic credential and qualification record are available, so live qualified execution remains blocked until Tasks 11 and 13.
- Host-control and corpus fixture runs are not candidate qualification evidence.

No rewrite tournament was run because the user explicitly prohibited rewrite tournaments for this session.
