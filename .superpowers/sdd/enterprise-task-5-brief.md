# Enterprise Task 5 — truthful provider authority

Architecture source: independent Sol/XHigh planner at baseline `bc76936`.

## Objective

Pin one truthful machine-generation authority to every new run and carry it through attempts, artifacts, accepted snapshots, durable events, and strict API responses. Remove settings-derived Anthropic attribution and prevent fixed deterministic `COMPLETE` / `Passed` prose from reaching an ordinary run.

Task 5 does not qualify a live model. It builds and proves the fail-closed authority mechanism. The real qualification record, credentials, and six-pathway live evidence remain Tasks 11/13 and must be reported `BLOCKED EXTERNAL` or `NOT PROVED`, never passed.

## Binding decisions

1. Enterprise mode is the existing `Settings.environment == "production"`; do not add another profile flag.
2. `agent_execution_enabled` is a capability switch. A full run refuses before row creation when it is disabled or its provider authority is unavailable.
3. Production permits only one explicit Anthropic binding. OpenRouter is development-only; ambiguous dual credentials are refused. There is no fallback or picker.
4. Worker startup remains provider-independent because it does not drive run graphs.
5. Qualification is a strict read-only JSON record selected by `CAOS_PROVIDER_QUALIFICATION_PATH` and pinned by `CAOS_PROVIDER_QUALIFICATION_DIGEST`. Do not add a database, catalog, UI, signing service, or pretend checked-in qualified record.
6. Fixed `build_deterministic_payload()` output is host-control-only globally. Ordinary screen/full execution typed-refuses until a real source-computed deterministic executor exists.
7. Existing financial-model/scenario/revision controls are unrelated to LLM selection and remain unchanged.

## Qualification record v1

Strict allowlisted fields:

- `schema_version = "caos.provider-qualification.v1"`
- `record_id`
- `status = "qualified"`
- `provider_name`
- `model`
- nullable provider-reported `provider_version`
- `adapter_version`
- `parameter_context_digest`
- `methodology_build_id`
- `methodology_manifest_digest`
- `qualified_at`
- `expires_at`
- `evidence_digest`

Use the existing canonical `contracts.digest()` over parsed JSON. Validate the configured digest, bounded scalar formats, exact Anthropic/model/adapter/context/build/manifest agreement, `qualified_at <= now < expires_at`, and a SHA-256 evidence digest. Missing, malformed, future, expired, mismatched, or unqualified records fail closed. Installed dependency versions belong in the parameter/context digest, not a falsely provider-reported field.

## Provider identity

Add one frozen `ProviderIdentity` value on the existing `Provider` port:

- provider name
- exact model
- nullable provider-reported version
- adapter version
- parameter/context digest
- qualification record ID/digest
- qualification status: `qualified`, `unqualified`, or `host_control`
- qualification expiry
- self-digest over every prior field, including explicit nulls

Anthropic and OpenRouter construct this value once. `Engine` caches the adapter identity once; `start_run()` copies and validates that frozen value. Existing runs are always described from storage, never current settings. Recovery verifies the cached current binding against the stored run authority before provider contact.

The safe parameter/context preimage contains only host-owned policy metadata: provider/model/version, adapter and installed runtime versions, transport/counting mode, retry/repair/timeout/cache/stream/tool-parallelism policy, evidence-tool digest, canonical-output schema digest, module modes/token caps/authority digests, and OpenRouter tokenizer/margin/base URL policy. It contains no prompts, source text, hidden reasoning, keys, headers, provider bodies, or errors.

## Response substitution and spend order

Extend `ProviderMessage` with observed model and nullable provider version. Both adapters return actual observed values when available.

After every provider response:

1. validate usage;
2. reconcile billed spend and clear the in-flight request;
3. persist a bounded attempt with request/response digests and observed identity;
4. compare observed model/version with the run pin;
5. on mismatch, raise `AGENT_IDENTITY_MISMATCH` before parsing output, executing a tool, or writing an artifact.

The response digest may cover normalized blocks, stop reason, usage, bounded request ID, and observed identity, but only the digest is durable.

## Persistence and schema evolution

Add nullable JSON `provider_identity` columns to `runs`, `run_artifacts`, and `run_snapshots`.

- Fresh schemas use existing SQLAlchemy metadata.
- Existing SQLite schemas evolve inside a serialized `BEGIN IMMEDIATE` re-check.
- Existing PostgreSQL schemas use `ADD COLUMN IF NOT EXISTS`.
- App/worker concurrent construction must not race an inspector-only check.
- Unsupported dialect or failed evolution aborts startup.
- Do not add Alembic or a migration framework.

Legacy rows stay null; never infer history from current environment. Terminal history remains readable as identity unavailable. Legacy non-terminal agent recovery and new acceptance of an identity-less agent result fail closed.

New writes copy the exact run identity into plan, artifact row and payload, snapshot row and digest preimage. Attempts carry the full bounded identity. Durable run/node events and `snapshot.accepted` audit data carry its digest. Artifact reuse, finalization, recovery, and acceptance revalidate equality.

## Strict wire authority

Add strict identity and attempt response models. Serve stored identity on:

- run;
- canonical generation state;
- artifact;
- accepted snapshot;
- attempts;
- durable run/SSE events by digest.

Remove `_generation_state()` use of `settings.anthropic_model`. Historical null identity must round-trip honestly. Provider/qualification preflight refusals map to HTTP 503; admission remains 409; user contract validation remains 422; a post-start mismatch is a code-only failed run.

## False-success boundary

Ordinary runtime may not call the fixed deterministic builder. It raises `DETERMINISTIC_EXECUTOR_UNAVAILABLE` without an artifact.

Keep two distinct test-only mechanisms:

- existing `_scripted_runs` replaces canonical agent modules with fixtures;
- new in-memory `_placeholder_deterministic_runs` permits placeholder deterministic nodes while real host-control provider nodes still execute.

The shared private start path must register the test flag before auto-continuation can be scheduled. Expose only named `_for_tests` entry points. Do not persist, configure, infer from provider type, or route this flag through HTTP. Restart controls explicitly re-register a known run ID.

## Typed failures

- `AGENT_EXECUTION_DISABLED`
- `AGENT_PROVIDER_UNAVAILABLE`
- `AGENT_QUALIFICATION_MISSING`
- `AGENT_QUALIFICATION_EXPIRED`
- `AGENT_PROVIDER_UNQUALIFIED`
- `AGENT_IDENTITY_MISMATCH`
- `DETERMINISTIC_EXECUTOR_UNAVAILABLE`

Persist only codes and bounded host-owned classifications.

## Ordered implementation

### 5A — identity contract and adapters

Provider/qualification dataclasses and canonical digests; Anthropic/OpenRouter immutable identity; observed model/version; config parsing; host-control identity helper; adapter/config tests.

### 5B — durable authority and wire contract

Concurrent-safe additive columns; atomic run identity; artifact/snapshot/event propagation; strict response/API projection; legacy-null behavior and digest-tamper tests.

### 5C — runtime enforcement and false-success removal

One-time capture/preflight; plan/fingerprint/recovery/finalization checks; reconcile-before-substitution refusal; response digest and attempts; deterministic refusal; explicit per-run host-control seam; mechanical shared-test conversion.

### 5D — enterprise startup and task gate

Anthropic-only production assembly; ambiguous credential refusal; qualification startup validation; dev/worker boundaries; empty environment examples; security audit; strict focused and full backend suites.

Implementation is sequential. Review each subpacket before starting the next. Core work stays Terra/High; only bounded mechanical test-double conversions may use Luna/Medium.

## Minimum proof

- Exact provider/model/adapter/policy/qualification self-digest and immutability.
- OpenRouter attribution never mentions the Anthropic setting.
- Response substitution reconciles spend before failure and creates no artifact/tool execution.
- Environment/provider mutation cannot alter an existing run.
- Plan/artifact/snapshot/API identities equal the stored run pin.
- Missing/expired/wrong qualification refuses production startup/new full runs.
- OpenRouter and dual credentials refuse production startup.
- Legacy null rows are not backfilled and cannot acquire new authority.
- Ordinary deterministic execution refuses; the test-only seam cannot escape.
- Attempt/event/log data contain no prompt, source text, provider error/body, secrets, or qualification body.
- Schema evolution survives simultaneous app/worker initialization.
- Provider, runtime, budget, evidence, observability, HTTP, security-audit, Ruff, diff, and full backend gates pass.

## Forbidden shortcuts

No picker/catalog/fallback, qualification boolean, fake record, environment backfill, raw prompt/response persistence, model-authored identity, OpenRouter qualification claim, configurable placeholder flag, new provider/migration/test framework, or rewrite tournament.

## Classification

- Host authority, persistence, strict API, false-success, security, and regression gates must PASS.
- Real PostgreSQL tests without the configured service are BLOCKED EXTERNAL.
- Live Anthropic execution and a real qualification record are BLOCKED EXTERNAL until supplied.
- Enterprise model qualification remains NOT PROVED until Tasks 11/13.

