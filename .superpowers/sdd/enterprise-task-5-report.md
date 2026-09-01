# Enterprise Task 5A report — identity contract and adapters

Implementation commit: `fe2fed45d0cfc14fc3ecc6ecdf4b5a61770dc3f6`.

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

## NOT PROVED

- Runtime preflight, persistence, API projection, recovery comparison, response-substitution refusal, and deterministic false-success removal are 5B–5D and were not started.
- A live model has not been qualified. This packet builds only the fail-closed record primitive.

## BLOCKED EXTERNAL

- No genuine qualification record, protected Anthropic credentials, or live six-pathway qualification evidence was supplied. No external provider call was made.

## Risks / follow-up

- The parameter/context digest is intentionally sensitive to installed adapter/runtime versions and policy constants; a change requires a new qualification record.
- Independent review remains pending before 5B.
