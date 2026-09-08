# Post-edit rewrite tournament — 2026-09-08

Scope: the two most material root-owned new boundaries, RequestBodyLimit and
source_manifest. Roles run inline sequentially because the session already
contains the complete 59-finding review and several implementation reports.
These are reasoned candidates, not independent-agent or benchmark results.
Other changed symbols (readiness, listings, parsing, renderer, SSE and typed
errors) are covered by confidence review and integration tests; no broader
rewrite sweep was requested. Frontend/startup tournaments are recorded in their
implementation reports. Docs, config, tests and deleted helpers are excluded.

Impact discovery: repository-wide `rg` found RequestBodyLimit installed only by
create_app, before GZip/routes and after authenticated admission; its transport
regression calls it directly. source_manifest has three production call sites:
Engine._start_run, the plan gate, and agent execution. No GitNexus index/tool was
available. Public signatures, return list, refusal codes and ordering must hold.
Request replay must preserve exact bytes, including empty and chunked bodies,
refuse before downstream parsing, close the spool and avoid blocking disk I/O
on the event loop. The spool's 1 MiB memory ceiling is intentional. Manifest row
refusal precedes digest work; full canonical array bounds remain inclusive;
source block order and digest inputs do not change.

## Transport

Read target: `/Users/ericguei/.codex/worktrees/e0aa/CAOS-LangMVP/caos/server/caos/api/__init__.py:268-307`.

Incumbent: retain the existing sequence and explicit state. The installed callers depend on its return/error and lifetime contracts; simplification has to preserve those contracts, not just the happy path.

### Speed challenger — full candidate

```python
class RequestBodyLimit:
    """Enforce the transport cap before form/JSON parsing, including chunked bodies."""

    def __init__(self, app: Any, *, max_bytes: int) -> None:
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH", "DELETE"}:
            await self.app(scope, receive, send)
            return
        # ponytail: spool at most one capped body per admitted request; streaming
        # parser integration if this extra local copy becomes measurable.
        with __import__("io").BytesIO() as body:
            size = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                size += len(chunk)
                if size > self.max_bytes:
                    await JSONResponse(status_code=413, content={"detail": "request exceeds upload limit"})(scope, receive, send)
                    return
                body.write(chunk)
                if not message.get("more_body", False):
                    break
            body.seek(0)
            remaining = size
            finished = False

            async def replay() -> Any:
                nonlocal remaining, finished
                if finished:
                    return await receive()
                chunk = body.read(64 * 1024)
                remaining -= len(chunk)
                finished = remaining == 0
                return {"type": "http.request", "body": chunk, "more_body": not finished}

            await self.app(scope, replay, send)
```

### Memory challenger — full candidate

```python
class RequestBodyLimit:
    """Enforce the transport cap before form/JSON parsing, including chunked bodies."""

    def __init__(self, app: Any, *, max_bytes: int) -> None:
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH", "DELETE"}:
            await self.app(scope, receive, send)
            return
        # ponytail: spool at most one capped body per admitted request; streaming
        # parser integration if this extra local copy becomes measurable.
        with __import__("tempfile").TemporaryFile() as body:
            size = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                size += len(chunk)
                if size > self.max_bytes:
                    await JSONResponse(status_code=413, content={"detail": "request exceeds upload limit"})(scope, receive, send)
                    return
                await asyncio.to_thread(body.write, chunk)
                if not message.get("more_body", False):
                    break
            await asyncio.to_thread(body.seek, 0)
            remaining = size
            finished = False

            async def replay() -> Any:
                nonlocal remaining, finished
                if finished:
                    return await receive()
                chunk = await asyncio.to_thread(body.read, 64 * 1024)
                remaining -= len(chunk)
                finished = remaining == 0
                return {"type": "http.request", "body": chunk, "more_body": not finished}

            await self.app(scope, replay, send)
```

### Readability challenger — full candidate

```python
class RequestBodyLimit:
    """Enforce the transport cap before form/JSON parsing, including chunked bodies."""

    def __init__(self, app: Any, *, max_bytes: int) -> None:
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH", "DELETE"}:
            await self.app(scope, receive, send)
            return
        # ponytail: spool at most one capped body per admitted request; streaming
        # parser integration if this extra local copy becomes measurable.
        with SpooledTemporaryFile(max_size=1024 * 1024) as body:
            size = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                size += len(chunk)
                if size > self.max_bytes:
                    await JSONResponse(status_code=413, content={"detail": "request exceeds upload limit"})(scope, receive, send)
                    return
                await asyncio.to_thread(body.write, chunk)
                if not message.get("more_body", False):
                    break
            await asyncio.to_thread(body.seek, 0)
            remaining = size

            async def replay() -> Any:
                nonlocal remaining
                if remaining < 0:
                    return await receive()
                chunk = await asyncio.to_thread(body.read, 64 * 1024)
                remaining -= len(chunk)
                more_body = remaining > 0
                if not more_body:
                    remaining = -1
                return {"type": "http.request", "body": chunk, "more_body": more_body}

            await self.app(scope, replay, send)
```

### Anonymous bracket adjudication

1. A (BytesIO) vs B (TemporaryFile): **B**. A drops the 1 MiB resident ceiling; B preserves byte replay and cleanup; B keeps disk operations off the event loop.
2. A (TemporaryFile) vs B (negative remaining sentinel): **A**. B saves one boolean but adds an implicit state; A has the same asymptotic space bound; A is easier to inspect for the empty-body case.
3. A (TemporaryFile) vs B (incumbent): **B**. Incumbent avoids disk I/O for small requests; its spool already bounds resident memory; both have the same bounded replay and closure contract.

**Winner**: Incumbent holds.

**Justification**:

- Dropping the memory ceiling disqualifies the fastest-looking candidate.
- Always writing to disk saves at most 1 MiB per request and penalizes every small body without workload evidence.
- Explicit finished state makes the empty-body and subsequent receive behavior easier to verify.

**Final code** (unchanged at `/Users/ericguei/.codex/worktrees/e0aa/CAOS-LangMVP/caos/server/caos/api/__init__.py:268-307`):

```python
class RequestBodyLimit:
    """Enforce the transport cap before form/JSON parsing, including chunked bodies."""

    def __init__(self, app: Any, *, max_bytes: int) -> None:
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH", "DELETE"}:
            await self.app(scope, receive, send)
            return
        # ponytail: spool at most one capped body per admitted request; streaming
        # parser integration if this extra local copy becomes measurable.
        with SpooledTemporaryFile(max_size=1024 * 1024) as body:
            size = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                size += len(chunk)
                if size > self.max_bytes:
                    await JSONResponse(status_code=413, content={"detail": "request exceeds upload limit"})(scope, receive, send)
                    return
                await asyncio.to_thread(body.write, chunk)
                if not message.get("more_body", False):
                    break
            await asyncio.to_thread(body.seek, 0)
            remaining = size
            finished = False

            async def replay() -> Any:
                nonlocal remaining, finished
                if finished:
                    return await receive()
                chunk = await asyncio.to_thread(body.read, 64 * 1024)
                remaining -= len(chunk)
                finished = remaining == 0
                return {"type": "http.request", "body": chunk, "more_body": not finished}

            await self.app(scope, replay, send)
```

## Manifest

Read target: `/Users/ericguei/.codex/worktrees/e0aa/CAOS-LangMVP/caos/server/caos/engine/budget.py:152-169`.

Incumbent: retain the existing sequence and explicit state. The installed callers depend on its return/error and lifetime contracts; simplification has to preserve those contracts, not just the happy path.

### Speed challenger — full candidate

```python
def source_manifest(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The exact provider manifest, shared by admission, gate and execution."""
    if len(sources) + sum(len(source.get("blocks") or []) for source in sources) > MAX_MANIFEST_BLOCKS:
        raise AgentError("AGENT_BUDGET_EXCEEDED", "source manifest block ceiling exceeded")
    return bound_manifest([{
        "source_id": source["id"], "sha256": source["sha256"],
        "filename": source.get("filename", source["id"]),
        "media_type": source.get("media_type", "application/octet-stream"),
        "preparation": {
            "representation": "pinned_blocks", "block_count": len(source.get("blocks") or []),
            "content_digest": digest(source.get("blocks") or []),
        },
        "blocks": [{key: block.get(key) for key in ("block_id", "locator", "extractor_version", "confidence")}
                   for block in source.get("blocks") or []],
    } for source in sources])
```

### Memory challenger — full candidate

```python
def source_manifest(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The exact provider manifest, shared by admission, gate and execution."""
    rows = len(sources)
    for source in sources:
        rows += len(source.get("blocks") or [])
        if rows > MAX_MANIFEST_BLOCKS:
            raise AgentError("AGENT_BUDGET_EXCEEDED", "source manifest block ceiling exceeded")
    entries = ({
        "source_id": source["id"], "sha256": source["sha256"],
        "filename": source.get("filename", source["id"]),
        "media_type": source.get("media_type", "application/octet-stream"),
        "preparation": {
            "representation": "pinned_blocks", "block_count": len(source.get("blocks") or []),
            "content_digest": digest(source.get("blocks") or []),
        },
        "blocks": [{key: block.get(key) for key in ("block_id", "locator", "extractor_version", "confidence")}
                   for block in source.get("blocks") or []],
    } for source in sources)
    return bound_manifest(list(entries))
```

### Readability challenger — full candidate

```python
def source_manifest(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The exact provider manifest, shared by admission, gate and execution."""
    rows = len(sources)
    for source in sources:
        rows += len(source.get("blocks") or [])
        if rows > MAX_MANIFEST_BLOCKS:
            raise AgentError("AGENT_BUDGET_EXCEEDED", "source manifest block ceiling exceeded")
    entries = []
    for source in sources:
        blocks = source.get("blocks") or []
        entries.append({
            "source_id": source["id"], "sha256": source["sha256"],
            "filename": source.get("filename", source["id"]),
            "media_type": source.get("media_type", "application/octet-stream"),
            "preparation": {
                "representation": "pinned_blocks", "block_count": len(blocks),
                "content_digest": digest(blocks),
            },
            "blocks": [{key: block.get(key) for key in
                        ("block_id", "locator", "extractor_version", "confidence")}
                       for block in blocks],
        })
    return bound_manifest(entries)
```

### Anonymous bracket adjudication

1. A (sum prepass) vs B (generator then list): **A**. A is shorter; B still materializes the same list; B adds an iterator without reducing asymptotic allocation.
2. A (sum prepass) vs B (explicit append): **B**. B retains early refusal during the count pass; B names the reused block collection; B keeps provider field construction together.
3. A (explicit append) vs B (incumbent): **B**. Both retain the required list; the repeated dict lookups are bounded by 2,000 rows; the incumbent has fewer moving parts and the same digest/field order.

**Winner**: Incumbent holds.

**Justification**:

- The early row ceiling prevents unneeded text hashing before any provider manifest is allocated.
- The output must remain a list; a lazy return would change the provider contract.
- None of the alternatives establishes a material cost reduction for at most 2,000 rows.

**Final code** (unchanged at `/Users/ericguei/.codex/worktrees/e0aa/CAOS-LangMVP/caos/server/caos/engine/budget.py:152-169`):

```python
def source_manifest(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The exact provider manifest, shared by admission, gate and execution."""
    rows = len(sources)
    for source in sources:
        rows += len(source.get("blocks") or [])
        if rows > MAX_MANIFEST_BLOCKS:
            raise AgentError("AGENT_BUDGET_EXCEEDED", "source manifest block ceiling exceeded")
    return bound_manifest([{
        "source_id": source["id"], "sha256": source["sha256"],
        "filename": source.get("filename", source["id"]),
        "media_type": source.get("media_type", "application/octet-stream"),
        "preparation": {
            "representation": "pinned_blocks", "block_count": len(source.get("blocks") or []),
            "content_digest": digest(source.get("blocks") or []),
        },
        "blocks": [{key: block.get(key) for key in ("block_id", "locator", "extractor_version", "confidence")}
                   for block in source.get("blocks") or []],
    } for source in sources])
```

## Orchestrator verification

No candidate replaced the incumbent, so no restoration or mutation was needed.
The exact focused verification command and outcome are appended after execution.
Concrete probes: a two-chunk five-byte body reaches downstream byte-for-byte;
a six-byte body and disconnect do not reach the parser and close the spool.
An over-row manifest refuses before the digest function is called; exact
canonical byte limits are tested inclusively. Call-site review retained all
three runtime uses and the single middleware installation; signatures unchanged.

Focused orchestrator verification completed after the final transport/manifest changes:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=caos/server /Users/ericguei/Claude/Projects/CAOS-LangMVP/caos/server/.venv314/bin/python -m pytest -q -p no:cacheprovider --tb=short caos/tests/test_single_instance.py caos/tests/spec/test_budget_spec.py caos/tests/spec/test_audit_boundaries_spec.py -k 'not second_dev_server'
```

Result: **115 passed, 2 PostgreSQL skips, 1 socket test deselected**. The deselected
duplicate-process socket check subsequently passed outside the sandbox. Root
re-read the actual diff; no candidate changed a caller, field or error contract.

## Follow-up pass: health route

Target: the new `health` async endpoint in `caos/server/caos/api/__init__.py`.
Impact: FastAPI registration and HTTP clients only; health_checks delegates to
existing synchronous Engine.readiness and ScannerReadiness.status. Keep the
strict five-field response, shared cancellation-safe task and degraded 503.

Incumbent: one shielded task owns the combined check; awaiting clients neither
block the event loop nor consume Starlette request worker tokens.

Speed challenger (full endpoint):
```python
async def health(response: Response) -> dict[str, Any]:
    result = health_checks()
    if result["status"] != "ok":
        response.status_code = 503
    return result
```
Memory challenger (full endpoint; `health_lock = asyncio.Lock()` at app assembly):
```python
async def health(response: Response) -> dict[str, Any]:
    async with health_lock:
        result = await asyncio.to_thread(health_checks)
    if result["status"] != "ok":
        response.status_code = 503
    return result
```
Readability challenger (full endpoint):
```python
async def health(response: Response) -> dict[str, Any]:
    result = await asyncio.to_thread(health_checks)
    if result["status"] != "ok":
        response.status_code = 503
    return result
```
Anonymous bracket: A (direct) vs B (lock): B, because A blocks the event loop, B
offloads checks, and B otherwise preserves the wire response. A (lock) vs B
(per-call thread): A, because it limits concurrent checks, preserves responses,
and avoids one worker per anonymous request. A (lock) vs B (incumbent): B,
because a cancelled lock waiter releases its lock while its thread can keep
running, shielding retains one owner, and the incumbent avoids an extra lock.

**Winner**: Incumbent holds.

**Justification**:

- Direct checking blocks the event loop and fails the free-request-pool invariant.
- One thread per caller recreates the original capacity problem.
- Shared shielded ownership survives caller cancellation with minimal state.

**Final code**:
```python
    async def health(response: Response) -> dict[str, Any]:
        nonlocal health_task
        # One background task serves the whole burst, including cancelled
        # callers. Neither probe waits on the event loop or HTTP worker pool.
        if health_task is None or health_task.done():
            health_task = asyncio.create_task(asyncio.to_thread(health_checks))
        result = await asyncio.shield(health_task)
        if result["status"] != "ok":
            response.status_code = 503
        return result

```

**Verification**: the 115-test command above passed, including the one-token
HTTP worker-pool probe and cancelled/concurrent health callers. The separate
readiness completion-time fake-clock regression passed in the 30-test focused
health/config command (recorded in the status report).

Final axe follow-up: skipped the single source-reader ARIA attribute correction
and test-only gate changes; no material function rewrite is justified. The
existing source selection and rendering branches are unchanged. Confidence
review and the rebuilt axe sweep cover the correction.

Post-edit CI check: Incumbent holds for the browser startup probe. The smallest
correct seam is the workflow's readiness command because the fixture intentionally
reports scanner=unavailable while its store, bundle and checkpointer are ready.
A broader app-health change would weaken the production contract. The only other
edit is a declarative FILE_MAP entry for the new harness test, so no rewrite is
warranted. Local quality coverage and shell/syntax checks pass.

## Follow-up pass: ReportStudio identity/autosave race

Target: `caos/frontend/src/components/report/ReportStudio.tsx`, the `load`,
`retainRecovery`, and `enqueueSave` paths around lines 272-390. Impact callers
are the Report editor mount/pathway effect, every draft mutation, autosave,
conflict recovery, and browser recovery actions. Invariants are unchanged
signatures, case/pathway generation fencing, subject-scoped recovery, and a
pending autosave surviving identity resolution.

Incumbent: defend the smallest ref-based fix. It keeps the existing sequential
tab claim and workspace request, removes only `subject` from the workspace load
dependencies, and adds one subject-arrival recovery read. The editor still
restarts for case/pathway changes, while dirty content is never replaced by the
late recovery read.

Speed challenger: remove the initial recovery read from `load`, overlap tab
claim and workspace fetch with `Promise.all`, and key one recovery effect on a
`workspaceLoaded` boolean. This avoids parsing the same localStorage slot after
every `workspace` replacement, but changes the request ordering and broadens the
post-edit diff without fixing a measured bottleneck.

Readability challenger: use a single `subjectRef` update effect and a dedicated
`readRecovery` callback called by `load` and the subject effect. This names the
operation clearly, but adds an abstraction with two call sites and a callback
dependency solely to avoid two short existing lines.

Memory challenger: same semantic shape as the speed candidate, with one bounded
recovery parse per subject/case/pathway scope. Its allocation reduction is
negligible beside the browser document and it still needs a workspace-loaded
guard for late identity.

Arbiter: the incumbent beats speed on change surface and preserves the current
claim-before-load order; speed beats readability and memory only on repeated
localStorage work. The incumbent therefore wins the bracket: the race is fixed
at the load-effect dependency, with no new helper or API contract.

**Winner**: Incumbent holds, replacing the subject-dependent load lifecycle and
rendered-subject recovery accesses in `ReportStudio.tsx` lines 219-390.

**Justification**:

- It prevents `/api/me` subject resolution from clearing the pending autosave
  timer and resetting draft generations.
- A ref supplies the current subject to save/conflict/clear paths without
  recreating the workspace load callback.
- The separate subject/workspace recovery effect handles either arrival order
  and refuses to overwrite an unsaved draft.

**Verification**: `npm run test:unit -- --test-name-pattern='report|workbench'`
passed 195 tests; `node --test scripts/audit-fixes.test.mjs`, ESLint with
`--max-warnings=0`, TypeScript `--noEmit`, quality-ledger coverage, and
`git diff --check` passed. Every `load`, `retainRecovery`, and `enqueueSave`
caller was re-read; their signatures and case/pathway fences remain unchanged.

## Follow-up pass: bounded PDF extraction fixture ceiling

The follow-up changes only the existing subprocess CPU and parent wall
ceilings in `caos/server/caos/sources/pdf.py` and
`caos/server/caos/sources/domain.py`; the parser, page cap, text cap, and error
contract are unchanged. This is a four-line limit adjustment with no new
branching, so the tournament is skipped as a trivial configuration edit.
The existing subprocess isolation and incremental extraction remain the
load-bearing design; a direct in-process parser or an unbounded timeout would
weaken the trust boundary. The 81 focused source/admission tests passed after
the adjustment. The hosted runner's corpus log then showed the 45-second
ceiling was still too low for its 579-page fixture; increasing the same bounded
ceiling to 120 seconds changes no parser semantics or error contract.

The CP-DR fixture change is test-only and adds no production branching, so the
rewrite tournament is skipped for that edit.
