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
