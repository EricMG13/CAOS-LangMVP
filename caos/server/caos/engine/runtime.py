"""Run engine on LangGraph (DECISIONS §§2–4, 10–12).

One static StateGraph per (pathway, depth); thread = run; the source gate is a
real graph interrupt; the checkpointer is durable sqlite (postgres in prod).
No data-selected edges exist: nodes raise typed errors and the engine
finalizes failure at the graph boundary. Nothing here derives from LEGACY
workflows/domain.py or http.py.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from ..config import Settings
from ..contracts import Depth, digest
from ..methodology.bundle import DeployVBundle
from ..methodology.canonical import (
    CanonicalModuleOutput,
    canonicalize_for_tests,
    recompute_confidence,
    validate_citations,
    validate_model_sources,
)
from ..methodology.execution import (
    MAX_CALCULATION_INPUT_BYTES,
    MethodologyCalculationError,
    MethodologyCalculationRuntime,
    calculation_output_complete,
)
from ..observability import log_event, run_context
from ..storage.runs import (
    TERMINAL,
    RunStore,
    StoreConflict,
    artifact_input_fingerprint,
    verify_artifact_content,
)
from ..storage.store import DomainStore, now_iso, source_sets as domain_source_sets
from . import state as state_mod
from .authority import compile_module_prompts
from .budget import (
    DIMENSIONS,
    EVIDENCE_BYTES_PER_MODULE,
    EVIDENCE_READS_PER_MODULE,
    MAX_ACTIVE_JOBS,
    PROVIDER_CONCURRENCY_SLOTS,
    bound_manifest,
    route_envelope,
)
from .deterministic import build_deterministic_payload
from .evidence import EvidenceReader
from .loop import ProviderSlots, reject_duplicate_keys, run_agent_module
from .research import RESEARCH_HANDOFF_FIELDS, build_research_plan, research_handoff_fields, research_plan_hash, validate_brief
from .research import brief_digest as research_brief_digest
from .provider import (
    READ_EVIDENCE_TOOL,
    AgentError,
    ProviderIdentity,
    ProviderRequest,
    methodology_calculation_tool,
)


MVP_PATHWAYS = {
    "FULL_CREDIT",
    "EARNINGS_UPDATE",
    "COVENANT_REFINANCING",
    "RELATIVE_VALUE",
    "DISTRESSED_RESTRUCTURING",
    "DEEP_RESEARCH",
}

# Deep Research has no screen depth (DECISIONS §14.1): the catalog compiles a
# LITE route, the engine never starts it. Every other pathway runs at both.
_PATHWAY_DEPTHS = {"DEEP_RESEARCH": ("full",)}


def supported_depths(pathway: str) -> tuple[str, ...]:
    return _PATHWAY_DEPTHS.get(pathway, ("screen", "full"))


def startable_routes() -> list[tuple[str, str]]:
    """Every (pathway, depth) cell this engine will start — the one list the
    case wire, the corpus host control and the probes enumerate."""
    return [(pathway, depth) for pathway in sorted(MVP_PATHWAYS) for depth in supported_depths(pathway)]

PLAN_APPROVAL_REQUIRED = "PLAN_APPROVAL_REQUIRED"

_CALCULATION_REF_FIELDS = (
    "calculator_id",
    "script_digest",
    "calculator_digest",
    "input_digest",
    "output_digest",
)


def _is_placeholder_payload(payload: Any) -> bool:
    provenance = payload.get("provenance") if isinstance(payload, dict) else None
    return (
        isinstance(payload, dict)
        and payload.get("schema_version") == "caos.system_analysis.v1"
        and isinstance(provenance, dict)
        and provenance.get("executor") == "caos.engine.deterministic"
    )


def _agent_module_ids_for_plan(plan: dict[str, Any]) -> list[str]:
    from ..modules.registry import MODULES

    depth = plan["depth"]
    agent_modules = []
    for node in plan["nodes"]:
        spec = MODULES.get(node["module_id"])
        if spec is None:  # a route node without a registry entry is not budgeted
            continue
        if (spec.mode_full if depth == "full" else spec.mode_screen) == "agent":
            agent_modules.append(node["module_id"])
    return agent_modules


def _reject_nonfinite_json(_value: str) -> None:
    raise ValueError("non-finite number")


def _parse_calculation_input(arguments: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if set(arguments) != {"calculator_id", "input_json"}:
        raise AgentError("METHODOLOGY_INPUT_INVALID", "calculation arguments are not exact")
    calculator_id, input_json = arguments["calculator_id"], arguments["input_json"]
    if not isinstance(calculator_id, str) or not isinstance(input_json, str):
        raise AgentError("METHODOLOGY_INPUT_INVALID", "calculation arguments are malformed")
    try:
        if len(input_json.encode("utf-8")) > MAX_CALCULATION_INPUT_BYTES:
            raise ValueError("calculation input is too large")
        inputs = json.loads(
            input_json,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=_reject_nonfinite_json,
        )
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise AgentError("METHODOLOGY_INPUT_INVALID", "calculation input is not strict JSON") from exc
    if type(inputs) is not dict:
        raise AgentError("METHODOLOGY_INPUT_INVALID", "calculation input must be a JSON object")
    return calculator_id, inputs


def _calculation_ref(record: dict[str, Any]) -> dict[str, Any]:
    return {field: record[field] for field in _CALCULATION_REF_FIELDS}


CALCULATION_INCOMPLETE = "METHODOLOGY_CALCULATION_INCOMPLETE"

# The calculators whose incompleteness ends the run (DECISIONS §14 D6): the
# module's core numbers. Every other assigned calculator that stays incomplete
# after the single repair becomes a host-declared limitation on the artifact.
_CORE_CALCULATORS = frozenset({("CP-1", "credit_metrics"), ("CP-2G", "credit_metrics")})
_DISTRESSED_CORE_CALCULATORS = frozenset({("CP-4C", "funding_gap"), ("CP-4C", "recovery_waterfall")})


def _calculation_is_core(pathway: str, module_id: str, calculator_id: str) -> bool:
    key = (module_id, calculator_id)
    return key in _CORE_CALCULATORS or (
        pathway == "DISTRESSED_RESTRUCTURING" and key in _DISTRESSED_CORE_CALCULATORS
    )


def _validate_calculation_refs(
    declared: list[dict[str, Any]],
    delivered: list[dict[str, Any]],
    assigned_calculator_ids: tuple[str, ...],
    limited_calculator_ids: tuple[str, ...] = (),
) -> None:
    """Declared references must equal the host-pinned records exactly, and the
    records plus the host-declared limitations must cover every assigned
    calculator: a limitation is never a reference, and never a substitute."""
    declared_keys = [tuple(record[field] for field in _CALCULATION_REF_FIELDS) for record in declared]
    delivered_keys = [tuple(_calculation_ref(record)[field] for field in _CALCULATION_REF_FIELDS)
                      for record in delivered]
    delivered_ids = {key[0] for key in delivered_keys}
    limited_ids = set(limited_calculator_ids)
    if (
        len(assigned_calculator_ids) != len(set(assigned_calculator_ids))
        or len(limited_calculator_ids) != len(limited_ids)
        or len(declared_keys) != len(set(declared_keys))
        or len(delivered_keys) != len(set(delivered_keys))
        or len({key[0] for key in declared_keys}) != len(declared_keys)
        or len(delivered_ids) != len(delivered_keys)
        or delivered_ids & limited_ids
        or delivered_ids | limited_ids != set(assigned_calculator_ids)
        or set(declared_keys) != set(delivered_keys)
    ):
        raise ValueError("provider calculation references do not match host calculations")


# Shutdown must not wait forever for a task that ignores cancellation or a
# foreign loop that cannot finish its waiter. Failed work stays registered so a
# later close can retry once its owner can make progress.
CLOSE_DRAIN_TIMEOUT_SECONDS = 5.0

# /api/health is unauthenticated (oauth2-proxy `skip_auth_routes`) AND exempt
# from the per-subject rate ceiling, so its cost is an anonymous caller's to
# spend. Verifying the bundle hashes 307 files (~12 ms); this bounds that to
# once per window while still re-probing continuously — a readiness answer that
# is at most five seconds stale is still a readiness answer.
READINESS_TTL_SECONDS = 5.0


class EngineError(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {message}" if message else code)


class StateSchemaMismatch(RuntimeError):
    pass


class ModuleFailure(AgentError):
    def __init__(self, code: str, module_id: str | None, message: str = "") -> None:
        super().__init__(code, message)
        self.module_id = module_id


class SimulatedCrash(BaseException):
    """Test-only crash injection; BaseException so nothing 'handles' it."""


def _probe(check: Any) -> bool:
    """A readiness probe reports; it never raises. Why it failed belongs in the
    operator's logs, not on an unauthenticated wire (see api.health)."""
    try:
        check()
    except Exception:
        return False
    return True


class Engine:
    def __init__(self, settings: Settings, store: DomainStore, checkpoint_path: Path, provider: Any) -> None:
        self.settings = settings
        self.store = store
        self.provider = provider
        self._provider_identity = self._capture_provider_identity(provider)
        if settings.environment == "production" and self._provider_identity is not None:
            identity = self._provider_identity
            if identity.provider_name != "anthropic" or identity.qualification_status != "qualified":
                raise EngineError("AGENT_PROVIDER_UNQUALIFIED", "production requires qualified Anthropic")
            try:
                identity.ensure_current()
            except AgentError as exc:
                raise EngineError(exc.code, "production provider identity is not current") from exc
        self.checkpoint_path = Path(checkpoint_path)
        self.runs = RunStore(store.engine)
        self.bundle = DeployVBundle(settings.deploy_v_root)
        self._calculation_runtime = MethodologyCalculationRuntime(
            settings.deploy_v_root,
            self.bundle.integrity,
        )
        self._calculation_bindings_cache: dict[str, list[dict[str, Any]]] | None = None
        self._savers: dict[int, Any] = {}
        self._graphs: dict[tuple[int, str, str], Any] = {}
        self._clock = time.monotonic
        self._active_invocations = 0
        self._admission_offset = 0
        self._budget_overrides: dict[str, int | float] = {}
        self._build_override: str | None = None
        self._crash_gap: dict[str, str] = {}
        self._crash_before_create: set[str] = set()
        self._agent_locks: dict[tuple[int, str], asyncio.Lock] = {}
        self._thread_locks: dict[tuple[int, str], asyncio.Lock] = {}
        self._auto_continue = False
        self._continuations: set[asyncio.Task[Any]] = set()
        self._slots = ProviderSlots(PROVIDER_CONCURRENCY_SLOTS)
        self._model_service: Any = None
        self._scripted_runs: set[str] = set()
        self._placeholder_deterministic_runs: set[str] = set()
        self._readiness: tuple[float, dict[str, bool]] | None = None
        self._readiness_lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        self._saver_initializations: set[asyncio.Task[Any]] = set()
        self._close_in_progress = False
        self._close_waiters: list[tuple[asyncio.AbstractEventLoop, asyncio.Future[None]]] = []
        self._closing = False
        self._closed = False

    def enable_auto_continue(self) -> None:
        """The serving entrypoint owns execution: start/resume stop at the plan
        gate so the immutable plan returns immediately, and this schedules the
        rest of the run on the serving loop. Tests never enable it — they keep
        explicit wait()/resume() control, and a second loop driving the same
        thread would break the one-loop-per-thread assumption (_loop_key)."""
        self._auto_continue = True

    def _schedule_continuation(self, run_id: str) -> None:
        if not self._auto_continue or self.runs.get_run(run_id)["status"] != "running":
            return
        with self._lifecycle_lock:
            if self._closing or self._closed:
                return
            task = asyncio.get_running_loop().create_task(self.wait(run_id))
            self._continuations.add(task)

        def finish(done: asyncio.Task[Any]) -> None:
            with self._lifecycle_lock:
                self._continuations.discard(done)
            try:
                error = done.exception()
            except asyncio.CancelledError:
                return
            if error is not None:
                log_event("engine.continuation_failed", level=logging.ERROR, run_id=run_id,
                          detail=type(error).__name__)

        task.add_done_callback(finish)

    def register_model_service(self, service: Any) -> None:
        """The Model Builder shares this engine's admission budget and receives
        the accept-time auto-queue hook. Registration is the seam — the engine
        never imports the model service."""
        self._model_service = service

    @classmethod
    def create(cls, *, settings: Settings, store: DomainStore, checkpoint_path: Path, provider: Any = None) -> "Engine":
        return cls(settings, store, checkpoint_path, provider)

    @staticmethod
    def _capture_provider_identity(provider: Any) -> ProviderIdentity | None:
        if provider is None:
            return None
        try:
            raw = provider.identity
        except AttributeError:
            return None
        try:
            identity = raw if isinstance(raw, ProviderIdentity) else ProviderIdentity.from_dict(raw)
            identity.verify()
        except (AgentError, TypeError, ValueError) as exc:
            raise EngineError("AGENT_IDENTITY_MISMATCH", "provider identity is invalid") from exc
        return identity

    def _route_requires_agent(self, pathway: str, depth: str) -> bool:
        from ..modules.registry import MODULES
        from .graphs import compiled_route

        route = compiled_route(pathway, depth, self.settings.deploy_v_root)
        return any(
            (MODULES[module_id].mode_full if depth == "full" else MODULES[module_id].mode_screen) == "agent"
            for module_id in route.nodes
        )

    def _assert_run_provider_identity(self, run: dict[str, Any]) -> ProviderIdentity | None:
        raw = run.get("provider_identity")
        identity = ProviderIdentity.from_dict(raw) if raw is not None else None
        if not self._route_requires_agent(run["pathway"], run["depth"]):
            return identity
        if identity is None or self._provider_identity is None:
            raise AgentError("AGENT_IDENTITY_MISMATCH", "agent run has no current provider identity")
        self._provider_identity.ensure_current()
        if identity != self._provider_identity:
            raise AgentError("AGENT_IDENTITY_MISMATCH", "stored provider identity differs from current binding")
        return identity

    async def _finalize_identity_failure(self, run_id: str, exc: AgentError) -> dict[str, Any]:
        self.runs.finalize_failure(run_id, exc.code, None)
        await self._delete_terminal_thread(run_id)
        self._placeholder_deterministic_runs.discard(run_id)
        self._scripted_runs.discard(run_id)
        return self.get_run(run_id)

    # -- infrastructure ----------------------------------------------------

    def _loop_key(self) -> int:
        # Savers, compiled graphs, and asyncio locks are event-loop-bound.
        # Production runs one loop; a second key only appears at the test-client
        # boundary, where the HTTP portal loop and the test loop never drive the
        # same thread concurrently.
        return id(asyncio.get_running_loop())

    async def _ensure_saver(self):
        key = self._loop_key()
        current = asyncio.current_task()
        with self._lifecycle_lock:
            if self._closing or self._closed:
                raise RuntimeError("engine is closed")
            saver = self._savers.get(key)
            if saver is not None:
                return saver
            if current is not None:
                self._saver_initializations.add(current)

        import aiosqlite
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        conn = None
        try:
            connector = aiosqlite.connect(str(self.checkpoint_path))
            # The worker thread must not block interpreter shutdown (tests and
            # scripts would otherwise hang at exit joining it).
            connector.daemon = True
            conn = await connector
            saver = AsyncSqliteSaver(conn)
            await saver.setup()
            with self._lifecycle_lock:
                rejected = self._closing or self._closed
                existing = self._savers.get(key)
                if not rejected and existing is None:
                    self._savers[key] = saver
                    return saver
            await conn.close()
            conn = None
            if rejected:
                raise RuntimeError("engine is closed")
            return existing
        except BaseException:
            if conn is not None:
                await conn.close()
            raise
        finally:
            if current is not None:
                with self._lifecycle_lock:
                    self._saver_initializations.discard(current)

    async def aclose(self) -> None:
        """Stop owned work and close owned checkpointers, but not borrowed ports."""
        loop = asyncio.get_running_loop()
        with self._lifecycle_lock:
            if self._closed:
                return
            if self._close_in_progress:
                waiter = loop.create_future()
                self._close_waiters.append((loop, waiter))
            else:
                self._close_in_progress = True
                waiter = None
            self._closing = True
            current = asyncio.current_task()
            initializations = tuple(task for task in self._saver_initializations if task is not current)
        if waiter is not None:
            await waiter
            return

        error: BaseException | None = None
        try:
            if initializations:
                await self._drain_tasks(initializations)

            continuations = tuple(task for task in self._continuations if task is not current)
            if continuations:
                await self._drain_tasks(continuations, cancel=True)
            with self._lifecycle_lock:
                for task in continuations:
                    if task.done():
                        self._continuations.discard(task)

            with self._lifecycle_lock:
                savers = tuple(self._savers.items())
            self._graphs.clear()
            first_error: Exception | None = None
            for key, saver in savers:
                try:
                    await saver.conn.close()
                except Exception as exc:
                    if first_error is None:
                        first_error = exc
                else:
                    with self._lifecycle_lock:
                        if self._savers.get(key) is saver:
                            del self._savers[key]
            if first_error is not None:
                raise first_error
            with self._lifecycle_lock:
                self._closed = True
        except BaseException as exc:
            error = exc
            raise
        finally:
            with self._lifecycle_lock:
                self._close_in_progress = False
                waiters = tuple(self._close_waiters)
                self._close_waiters.clear()
            for waiter_loop, close_waiter in waiters:
                try:
                    if error is None:
                        waiter_loop.call_soon_threadsafe(self._finish_close_waiter, close_waiter, None)
                    else:
                        waiter_loop.call_soon_threadsafe(self._finish_close_waiter, close_waiter, error)
                except RuntimeError:
                    pass

    async def _drain_tasks(self, tasks: tuple[asyncio.Task[Any], ...], *, cancel: bool = False) -> None:
        """Wait for tasks on the loop that owns each task, cancelling when asked."""
        loop = asyncio.get_running_loop()
        local: list[asyncio.Task[Any]] = []
        foreign: list[tuple[asyncio.AbstractEventLoop, concurrent.futures.Future[None],
                            concurrent.futures.Future[asyncio.Task[None]]]] = []
        for task in tasks:
            if task.done():
                continue
            owner = task.get_loop()
            if owner is loop:
                if cancel:
                    task.cancel()
                local.append(task)
                continue
            if not self._owner_loop_runnable(owner, loop) and not task.done():
                raise RuntimeError("cannot close a task without a runnable owner loop")
            if task.done():
                continue
            if cancel:
                try:
                    owner.call_soon_threadsafe(task.cancel)
                except RuntimeError:
                    # The owner loop closed underneath us. That is only a failure
                    # if the task is still pending; a finished task is drained.
                    if task.done():
                        continue
                    raise
            bridge: concurrent.futures.Future[None] = concurrent.futures.Future()
            waiter_ref: concurrent.futures.Future[asyncio.Task[None]] = concurrent.futures.Future()

            def wait_on_owner(task: asyncio.Task[Any] = task, owner: asyncio.AbstractEventLoop = owner,
                              bridge: concurrent.futures.Future[None] = bridge,
                              waiter_ref: concurrent.futures.Future[asyncio.Task[None]] = waiter_ref) -> None:
                if bridge.done():
                    return
                waiter_coro = self._wait_for_task(task)
                try:
                    waiter = owner.create_task(waiter_coro)
                except BaseException as exc:
                    waiter_coro.close()
                    waiter_ref.set_exception(exc)
                    bridge.set_exception(exc)
                    return
                waiter_ref.set_result(waiter)

                def finish_waiter(done: asyncio.Task[None], bridge: concurrent.futures.Future[None] = bridge) -> None:
                    if bridge.done():
                        return
                    try:
                        done.result()
                    except BaseException as exc:
                        bridge.set_exception(exc)
                    else:
                        bridge.set_result(None)

                waiter.add_done_callback(finish_waiter)

            # Cancelling above is frequently what ends the owner loop, so from here
            # on "the loop is gone" and "the task finished" are the same event seen
            # from two threads. A finished task is a drained task: reporting that as
            # a failure aborts aclose() before it closes the savers, which strands
            # aiosqlite's non-daemon threads and leaves the process unable to exit.
            try:
                owner.call_soon_threadsafe(wait_on_owner)
            except RuntimeError:
                if task.done():
                    continue
                raise
            if not self._owner_loop_runnable(owner, loop):
                if task.done():
                    if waiter_ref.done() and not waiter_ref.cancelled():
                        try:
                            owner.call_soon_threadsafe(waiter_ref.result().cancel)
                        except BaseException:
                            pass
                    continue
                if waiter_ref.done() and not waiter_ref.cancelled():
                    try:
                        owner.call_soon_threadsafe(waiter_ref.result().cancel)
                    except BaseException:
                        pass
                raise RuntimeError("cannot close a task without a runnable owner loop")
            foreign.append((owner, bridge, waiter_ref))
        bridges = [asyncio.wrap_future(bridge) for _owner, bridge, _waiter in foreign]
        if local or bridges:
            try:
                async with asyncio.timeout(CLOSE_DRAIN_TIMEOUT_SECONDS):
                    await asyncio.wait([*local, *bridges])
            except TimeoutError as exc:
                for owner, bridge, waiter_ref in foreign:
                    bridge.cancel()
                    try:
                        if waiter_ref.done() and not waiter_ref.cancelled():
                            owner.call_soon_threadsafe(waiter_ref.result().cancel)
                    except BaseException:
                        pass
                raise RuntimeError("engine close timed out draining tasks") from exc
        for task in local:
            try:
                task.result()
            except BaseException:
                pass
        first_error = next((bridge.exception() for bridge in bridges if bridge.exception() is not None), None)
        if first_error is not None:
            raise first_error

    @staticmethod
    async def _wait_for_task(task: asyncio.Task[Any]) -> None:
        await asyncio.gather(task, return_exceptions=True)

    @staticmethod
    def _owner_loop_runnable(owner: asyncio.AbstractEventLoop, caller: asyncio.AbstractEventLoop) -> bool:
        return not (
            owner.is_closed()
            or not owner.is_running()
            or getattr(owner, "_thread_id", None) == threading.get_ident()
            or getattr(owner, "_stopping", False)
        )

    @staticmethod
    def _finish_close_waiter(waiter: asyncio.Future[None], error: BaseException | None) -> None:
        if waiter.done():
            return
        if error is None:
            waiter.set_result(None)
        elif isinstance(error, asyncio.CancelledError):
            waiter.cancel()
        else:
            waiter.set_exception(error)

    def _sync_saver(self):
        from langgraph.checkpoint.sqlite import SqliteSaver

        conn = sqlite3.connect(str(self.checkpoint_path), check_same_thread=False)
        return SqliteSaver(conn)

    def _config(self, run_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": run_id}}

    def _current_build_id(self) -> str:
        return self._build_override or self.bundle.build_id

    async def _delete_terminal_thread(self, run_id: str) -> None:
        run = self.runs.get_run(run_id)
        if run is not None and run["status"] in TERMINAL:
            await (await self._ensure_saver()).adelete_thread(run_id)

    async def _reap_terminal_threads(self) -> None:
        saver = await self._ensure_saver()
        # Intermediate writes commit independently, so a crash can leave a
        # thread in either table; the native deletion API clears both.
        async with saver.lock, saver.conn.execute(
            "SELECT thread_id FROM checkpoints UNION SELECT thread_id FROM writes"
        ) as cursor:
            thread_ids = [thread_id async for thread_id, in cursor]
        for thread_id in thread_ids:
            await self._delete_terminal_thread(thread_id)

    async def _graph(self, pathway: str, depth: str):
        key = (self._loop_key(), pathway, depth)
        if key not in self._graphs:
            from langgraph.graph import END, START, StateGraph

            from .graphs import compiled_route

            route = compiled_route(pathway, depth, self.settings.deploy_v_root)
            builder = StateGraph(state_mod.RunState)
            builder.add_node("gate", self._gate_node)
            for module_id in route.nodes:
                builder.add_node(module_id, self._make_module_node(module_id))
            builder.add_node("finalize", self._finalize_node)
            builder.add_edge(START, "gate")
            dependencies: dict[str, list[str]] = {}
            for source, target in sorted(route.edges):
                dependencies.setdefault(target, []).append(source)
            sources = {source for source, _ in route.edges}
            sinks = sorted(module_id for module_id in route.nodes if module_id not in sources)
            for module_id in route.nodes:
                if module_id not in dependencies:
                    builder.add_edge("gate", module_id)
            for target, deps in sorted(dependencies.items()):
                # List-form edges compile to an ALL-join barrier; separate
                # string edges would fire the target on ANY predecessor.
                builder.add_edge(deps if len(deps) > 1 else deps[0], target)
            builder.add_edge(sinks if len(sinks) > 1 else sinks[0], "finalize")
            builder.add_edge("finalize", END)
            saver = await self._ensure_saver()
            self._graphs[key] = builder.compile(checkpointer=saver)
        return self._graphs[key]

    def _raw_schema_check(self, run_id: str) -> None:
        """§12.24: the stamp is read from the raw checkpoint channel values and
        checked before any coercion."""
        saver = self._sync_saver()
        try:
            tup = saver.get_tuple({"configurable": {"thread_id": run_id, "checkpoint_ns": ""}})
        finally:
            saver.conn.close()
        if tup is None:
            return
        values = tup.checkpoint.get("channel_values") or {}
        if values.get("schema_version") != state_mod.SCHEMA_VERSION:
            raise StateSchemaMismatch(
                f"checkpoint schema {values.get('schema_version')!r} != {state_mod.SCHEMA_VERSION!r}"
            )

    async def _drive(self, run_id: str, input_value: Any, **kwargs: Any) -> Any:
        run = self.runs.get_run(run_id)
        graph = await self._graph(run["pathway"], run["depth"])
        # §10.3: single writer per thread, enforced on every drive entry point
        # (start, resume, wait, recovery, test hooks) — never assumed.
        async with self._thread_locks.setdefault((self._loop_key(), run_id), asyncio.Lock()):
            if self.runs.get_run(run_id)["status"] in TERMINAL:
                await self._delete_terminal_thread(run_id)
                return None
            self._active_invocations += 1
            try:
                return await graph.ainvoke(input_value, self._config(run_id), durability="sync", **kwargs)
            except AgentError as exc:
                module_id = exc.module_id if isinstance(exc, ModuleFailure) else None
                self.runs.finalize_failure(run_id, exc.code, module_id)
                return None
            finally:
                self._active_invocations -= 1
                await self._delete_terminal_thread(run_id)
                if self.runs.get_run(run_id)["status"] == "failed":
                    self._placeholder_deterministic_runs.discard(run_id)
                if self.runs.get_run(run_id)["status"] in TERMINAL:
                    self._scripted_runs.discard(run_id)

    # -- graph nodes -------------------------------------------------------

    def _gate_node(self, state: dict[str, Any]) -> dict[str, Any]:
        from langgraph.types import interrupt

        run_id = state["run_id"]
        run = self.runs.get_run(run_id)
        if run["plan_digest"]:
            # Crash between pin commit and checkpoint: the pin is already
            # written exactly once; re-emit state from the store copy.
            return {"plan": run["plan"], "plan_digest": run["plan_digest"]}
        current = self.store.current_source_set(run["case_id"])
        while not current or not current.get("source_ids"):
            ticket = self.runs.pause_run(run_id, "SOURCE_SET_EMPTY")
            log_event("gate.interrupt", run_id=run_id, reason="SOURCE_SET_EMPTY", interrupt_id=ticket)
            interrupt({"reason": "SOURCE_SET_EMPTY", "ticket": ticket})
            current = self.store.current_source_set(run["case_id"])
        live_sources = self.store.sources_for_live_set(
            run["case_id"],
            current["id"],
            current["version"],
        )
        if live_sources is None:
            raise AgentError("AGENT_AUTHORITY_MISMATCH", "source authority changed at the gate")
        self._verify_source_vault(live_sources)
        if run["status"] == "paused":
            # The node re-runs from the top on resume, so a run that entered
            # this invocation paused is a run whose gate has just cleared.
            log_event("gate.resolved", run_id=run_id, reason="SOURCE_SET_EMPTY")
        plan = self.bundle.compile(
            run["pathway"], Depth(run["depth"]), current["id"],
            focus_questions=run.get("focus_questions") or [],
            source_set_version=current["version"],
        )
        plan.pop("plan_digest", None)
        plan["source_set_digest"] = state_mod.source_set_digest(current)
        plan["source_authority"] = state_mod.source_authority(live_sources)
        if run.get("research") is not None:
            # The brief is bound into run authority through the plan digest; it
            # selects nothing about the node set (invariant 10). Absent, never
            # null, on every other pathway (§12.1).
            plan["research_brief_digest"] = run["research"]["brief_digest"]
        # §12.6: the plan pins the integrity-manifest digest at gate exit.
        plan["manifest_digest"] = digest(self.bundle.integrity)
        plan["provider_identity"] = run.get("provider_identity")
        # Invariant 1: a loan universe is workbook-derived analysis the host
        # lifts into CP-3's artifact without any evidence read, so it binds like
        # every other input — pinned here, once, and only when its own source is
        # in the set this run just pinned. A workbook imported after gate exit is
        # outside the pin and stays outside it; the key is absent, never null
        # (§12.1), so no other route's plan digest moves.
        universe = self.store.active_loan_universe(run["case_id"])
        if universe is not None and universe["source_id"] in current["source_ids"]:
            plan["loan_universe"] = {
                "id": universe["id"],
                "universe_digest": universe["universe_digest"],
                "source_id": universe["source_id"],
            }
        pinned = state_mod.pin_plan(plan)
        self.runs.pin_plan(run_id, pinned["plan"], pinned["plan_digest"])
        return {"plan": pinned["plan"], "plan_digest": pinned["plan_digest"], "error": None}

    def _make_module_node(self, module_id: str):
        async def node(state: dict[str, Any]) -> dict[str, Any]:
            return await self._run_module(state, module_id)

        node.__name__ = f"module_{module_id}"
        return node

    def _charge_active_if_metered(self, run_id: str, seconds: float) -> None:
        """Bracketed active-time charge; a run with no budget ledger (screen /
        pre-agent) accrues nothing. Over-budget raises and fails the module."""
        if self.runs.get_budget(run_id) is not None:
            self.runs.charge_budget(run_id, "active_minutes", max(0.0, seconds) / 60)

    def _plan_node(self, plan: dict[str, Any], module_id: str) -> dict[str, Any]:
        return next(node for node in plan["nodes"] if node["module_id"] == module_id)

    def _input_fingerprint(self, plan: dict[str, Any], plan_digest: str, module_id: str, upstream_digests: list[str]) -> str:
        return artifact_input_fingerprint(plan, plan_digest, module_id, upstream_digests)

    def _pinned_loan_universe(self, plan: dict[str, Any], case_id: str) -> dict[str, Any] | None:
        """The universe CP-3 binds, re-derived from the store on every attempt.

        §11.2: the plan carries an expectation, not authority — the record is
        re-read by id and its digest recomputed from the stored fields, so a
        tampered row or a swapped record fails closed. Case binding is re-checked
        here for the same reason `_live_sources` re-checks it on a digest-verified
        source set: the pin is only as good as the record it names. No pin means
        this run has no loan universe, which is the artifact a case without one
        already produces.
        """
        from ..artifacts.loan_universe import universe_digest

        pinned = plan.get("loan_universe")
        if pinned is None:
            return None
        record = self.store.loan_universe(pinned["id"])
        if (
            record is None
            or record["case_id"] != case_id
            or record["source_id"] != pinned["source_id"]
            or universe_digest(record) != pinned["universe_digest"]
        ):
            raise AgentError("AGENT_AUTHORITY_MISMATCH", "pinned loan universe does not match the store record")
        return record

    def _live_sources(self, case_id: str, source_set: dict[str, Any]) -> list[dict[str, Any]]:
        """Invariant 1, on EVERY path: the pinned set's digest cannot see a
        withdrawal — `store.withdraw` mints a NEW set version and leaves the
        pinned record byte-identical, so `verify_source_set_expectation` passes.
        The live rows are the only authority, and reuse-relink and deterministic
        execution need this check exactly as much as the agent path does."""
        live = self.store.sources_for_live_set(
            case_id,
            source_set.get("id"),
            source_set.get("version"),
        )
        if live is None:
            raise AgentError("AGENT_AUTHORITY_MISMATCH", "pinned source is unavailable")
        return live

    def _live_plan_sources(self, run: dict[str, Any], plan: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        source_set = state_mod.verify_source_set_expectation(
            self.store, plan["source_set_id"], plan["source_set_digest"],
        )
        live_sources = self._live_sources(run["case_id"], source_set)
        if plan.get("source_authority") != state_mod.source_authority(live_sources):
            raise AgentError("AGENT_AUTHORITY_MISMATCH", "pinned source content changed")
        return source_set, live_sources

    def _verify_source_vault(self, sources: list[dict[str, Any]]) -> None:
        from ..sources.domain import Vault

        vault = Vault(self.settings)
        for source in sources:
            private = self.store.get_source_private(source.get("id"))
            if (
                private is None
                or state_mod.source_authority([private])
                != state_mod.source_authority([source])
            ):
                raise AgentError(
                    "AGENT_AUTHORITY_MISMATCH",
                    "pinned source storage identity changed",
                )
            if private.get("vault_path") is None:
                if private.get("source_kind") == "analyst_note" or self.settings.environment == "development":
                    continue
                raise AgentError(
                    "AGENT_AUTHORITY_MISMATCH",
                    "pinned source bytes are unavailable",
                )
            try:
                vault.verify(private)
            except ValueError as exc:
                raise AgentError(
                    "AGENT_AUTHORITY_MISMATCH",
                    "pinned source bytes failed integrity verification",
                ) from exc

    def _calculation_bindings_by_module(self, *, fresh: bool = False) -> dict[str, list[dict[str, Any]]]:
        if self._calculation_bindings_cache is None or fresh:
            try:
                manifest = self._calculation_runtime.binding_manifest()
            except (KeyError, OSError, TypeError, ValueError) as exc:
                raise AgentError(
                    "METHODOLOGY_AUTHORITY_MISMATCH",
                    "calculation bindings are unavailable",
                ) from exc
            grouped: dict[str, list[dict[str, Any]]] = {}
            for binding in manifest:
                grouped.setdefault(binding["module_id"], []).append(binding)
            self._calculation_bindings_cache = grouped
        return self._calculation_bindings_cache

    def _replay_artifact_calculations(
        self,
        artifact: dict[str, Any],
        module_id: str,
    ) -> None:
        """Require persisted deterministic results to equal a fresh pinned run."""
        for record in artifact["payload"].get("calculations", []):
            try:
                reconstructed = self._calculation_runtime.execute(
                    module_id,
                    record["calculator_id"],
                    record["canonical_input"],
                )
            except (KeyError, OSError, TypeError, ValueError) as exc:
                raise ModuleFailure(
                    "RUN_NOT_READY",
                    module_id,
                    "calculation record cannot be reconstructed",
                ) from exc
            if reconstructed != record:
                raise ModuleFailure(
                    "RUN_NOT_READY",
                    module_id,
                    "calculation record differs from the pinned calculator",
                )

    def _artifact_rows_by_module(self, run: dict[str, Any]) -> dict[str, dict[str, Any]]:
        artifacts: dict[str, dict[str, Any]] = {}
        for node in run["nodes"]:
            if not node.get("artifact_id"):
                continue
            artifact = self.runs.get_artifact(node["artifact_id"])
            if artifact is not None:
                artifacts[node["module_id"]] = artifact
        return artifacts

    def _expected_host_identity(
        self,
        run: dict[str, Any],
        plan: dict[str, Any],
        module_id: str,
        source_set: dict[str, Any],
        upstream: list[dict[str, Any]],
        calculator_bindings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        case = self.store.get_case(run["case_id"])
        if case is None:
            raise AgentError("AGENT_AUTHORITY_MISMATCH", "run case is unavailable")
        identity = {
            "module_id": module_id,
            "module_name": self._plan_node(plan, module_id)["module_name"],
            "run_id": run["id"],
            "case_id": run["case_id"],
            "issuer_name": case["issuer"],
            "issuer_id": run["case_id"].replace("_", "-"),
            "reporting_period": run["created_at"][:10],
            "analysis_date": run["created_at"][:10],
            "profile_id": plan["profile_id"],
            "selection_id": plan["selection_id"],
            "source_set_id": source_set["id"],
            "source_set_version": source_set["version"],
            "calculator_ids": [binding["calculator_id"] for binding in calculator_bindings],
            "upstream_digests": [artifact["digest"] for artifact in upstream],
        }
        research_identity = self._research_identity(run, module_id)
        if research_identity is not None:
            identity["research"] = research_identity
        return identity

    def _research_identity(self, run: dict[str, Any], module_id: str) -> dict[str, Any] | None:
        """The approved research scope a plan-approval module executes under:
        host-owned, carried in the artifact's host identity and re-derived by
        the verifier from the run's research row (Task 7)."""
        from ..modules.registry import MODULES

        research = run.get("research")
        if not MODULES[module_id].plan_approval or research is None:
            return None
        plan = research.get("proposed_plan") or {}
        return {
            "brief": research["brief"],
            "brief_digest": research["brief_digest"],
            "approved_plan_hash": research["approved_plan_hash"],
            "workstreams": plan.get("workstreams") or [],
        }

    def _await_research_approval(
        self, run: dict[str, Any], plan: dict[str, Any], module_id: str, upstream: list[dict[str, Any]],
    ) -> str:
        """Propose the host-built plan and park the run until the exact hash is
        approved (invariant 5). The node re-runs from the top on every resume,
        so the loop re-reads the store rather than trusting a resume value; an
        approval that no longer matches the plan that would execute is refused."""
        from langgraph.types import interrupt

        run_id = run["id"]
        research = run.get("research")
        if research is None or plan.get("research_brief_digest") != research["brief_digest"]:
            raise AgentError("AGENT_AUTHORITY_MISMATCH", "research brief is not bound to the pinned plan")
        proposed = build_research_plan(
            build_id=plan["build_id"],
            run_plan_digest=run["plan_digest"],
            brief=research["brief"],
            source_set_id=plan["source_set_id"],
            source_set_version=plan["source_set_version"],
            upstream_artifacts=[
                {"module_id": a["module_id"], "artifact_id": a["id"], "digest": a["digest"]} for a in upstream
            ],
            scope_key=run["case_id"].replace("_", "-"),
        )
        plan_hash = research_plan_hash(proposed)
        while research["phase"] != "approved":
            ticket = self.runs.propose_research_plan(run_id, proposed, plan_hash)
            log_event("gate.interrupt", run_id=run_id, module_id=module_id,
                      reason=PLAN_APPROVAL_REQUIRED, interrupt_id=ticket)
            interrupt({"reason": PLAN_APPROVAL_REQUIRED, "ticket": ticket})
            research = self.runs.get_run(run_id)["research"]
        if research["approved_plan_hash"] != plan_hash:
            raise AgentError("RESEARCH_PLAN_MISMATCH", "the approved plan is not the plan that would execute")
        log_event("gate.resolved", run_id=run_id, module_id=module_id, reason=PLAN_APPROVAL_REQUIRED)
        return plan_hash

    def _artifact_content_expectations(
        self,
        run: dict[str, Any],
        plan: dict[str, Any],
        module_id: str,
        source_set: dict[str, Any],
        live_sources: list[dict[str, Any]],
        artifacts: dict[str, dict[str, Any]],
        *,
        payload: dict[str, Any] | None = None,
        bindings_by_module: dict[str, list[dict[str, Any]]] | None = None,
    ) -> dict[str, Any]:
        plan_node = self._plan_node(plan, module_id)
        try:
            immediate = [artifacts[dependency] for dependency in plan_node["dependencies"]]
        except KeyError as exc:
            raise AgentError("AGENT_AUTHORITY_MISMATCH", "upstream artifact is unavailable") from exc
        handoff = immediate
        if module_id not in {"CP-PARSE", "CP-0"} and not any(
            artifact["module_id"] == "CP-0" for artifact in immediate
        ):
            cp0 = artifacts.get("CP-0")
            if cp0 is None:
                raise AgentError("AGENT_AUTHORITY_MISMATCH", "CP-0 handoff anchor is unavailable")
            handoff = [cp0, *immediate]
        identity = run.get("provider_identity") or {}
        host_control_without_calculations = (
            identity.get("provider_name") == "host_control"
            and not (
                isinstance(payload, dict)
                and (payload.get("calculations") or payload.get("calculation_limitations"))
            )
        )
        available_bindings = (
            self._calculation_bindings_by_module()
            if bindings_by_module is None
            else bindings_by_module
        )
        bindings = [] if host_control_without_calculations else available_bindings.get(module_id, [])
        upstream_digests = [artifact["digest"] for artifact in immediate]
        input_fingerprint = self._input_fingerprint(
            plan,
            run["plan_digest"],
            module_id,
            upstream_digests,
        )
        loan_universe = (
            self._pinned_loan_universe(plan, run["case_id"])
            if module_id == "CP-3"
            else None
        )
        return {
            "source_set": {**source_set, "digest": plan["source_set_digest"]},
            "upstream_artifacts": immediate,
            "handoff_artifacts": handoff,
            "calculator_bindings": bindings,
            "expected_system_payload": build_deterministic_payload(
                module_id,
                plan,
                input_fingerprint=input_fingerprint,
                upstream_digests=upstream_digests,
                source_ids=source_set["source_ids"],
                loan_universe=loan_universe,
            ),
            "expected_host_identity": self._expected_host_identity(
                run,
                plan,
                module_id,
                source_set,
                immediate,
                bindings,
            ),
            "evidence_blocks": {
                (source["id"], block["block_id"])
                for source in live_sources
                for block in source.get("blocks") or []
                if isinstance(block, dict) and isinstance(block.get("block_id"), str)
            },
            "downstream_consumers": self._downstream_consumers(plan, module_id),
        }

    def _upstream_digests(self, run_id: str, plan: dict[str, Any], module_id: str) -> list[dict[str, Any]]:
        """Upstream artifact refs in the pinned plan's dependency order (§12.5)."""
        run = self.runs.get_run(run_id)
        source_set, live_sources = self._live_plan_sources(run, plan)
        nodes = {node["module_id"]: node for node in run["nodes"]}
        artifacts = self._artifact_rows_by_module(run)
        upstream = []
        for dependency in self._plan_node(plan, module_id)["dependencies"]:
            node = nodes.get(dependency)
            artifact = self.runs.get_artifact(node["artifact_id"]) if node and node["artifact_id"] else None
            if artifact is None or not verify_artifact_content(
                artifact,
                run_id=run_id,
                case_id=run["case_id"],
                module_id=dependency,
                input_fingerprint=self._input_fingerprint(
                    plan,
                    run["plan_digest"],
                    dependency,
                    [
                        artifacts[parent]["digest"]
                        for parent in self._plan_node(plan, dependency)["dependencies"]
                    ],
                ),
                methodology_build_id=plan["build_id"],
                provider_identity=run.get("provider_identity"),
                **self._artifact_content_expectations(
                    run,
                    plan,
                    dependency,
                    source_set,
                    live_sources,
                    artifacts,
                    payload=artifact.get("payload"),
                ),
            ):
                raise ModuleFailure("AGENT_AUTHORITY_MISMATCH", module_id, "validated upstream artifact is unavailable")
            upstream.append(artifact)
        return upstream

    def _handoff_lineage(
        self,
        run_id: str,
        module_id: str,
        immediate: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Retain the accepted CP-0 anchor as well as immediate dependencies."""
        if module_id in {"CP-PARSE", "CP-0"} or any(
            artifact["module_id"] == "CP-0" for artifact in immediate
        ):
            return immediate
        run = self.runs.get_run(run_id)
        nodes = {node["module_id"]: node for node in run["nodes"]}
        cp0_node = nodes.get("CP-0")
        cp0 = self.runs.get_artifact(cp0_node["artifact_id"]) if cp0_node and cp0_node["artifact_id"] else None
        source_set, live_sources = self._live_plan_sources(run, run["plan"])
        if cp0 is None or not verify_artifact_content(
            cp0,
            run_id=run_id,
            case_id=run["case_id"],
            module_id="CP-0",
            input_fingerprint=self._input_fingerprint(
                run["plan"],
                run["plan_digest"],
                "CP-0",
                [
                    self._artifact_rows_by_module(run)[parent]["digest"]
                    for parent in self._plan_node(run["plan"], "CP-0")["dependencies"]
                ],
            ),
            methodology_build_id=run["plan"]["build_id"],
            provider_identity=run.get("provider_identity"),
            **self._artifact_content_expectations(
                run,
                run["plan"],
                "CP-0",
                source_set,
                live_sources,
                self._artifact_rows_by_module(run),
                payload=cp0.get("payload"),
            ),
        ):
            raise AgentError("AGENT_AUTHORITY_MISMATCH", "accepted CP-0 lineage is unavailable")
        return [cp0, *immediate]

    @staticmethod
    def _downstream_consumers(plan: dict[str, Any], module_id: str) -> list[str]:
        from ..modules.registry import CP_MODEL_INPUT_MODULES

        consumers = [
            node["module_id"]
            for node in plan["nodes"]
            if module_id in node["dependencies"]
        ]
        if module_id in CP_MODEL_INPUT_MODULES and "CP-MODEL" not in consumers:
            consumers.append("CP-MODEL")
        return consumers

    async def _run_module(self, state: dict[str, Any], module_id: str) -> dict[str, Any]:
        from ..modules.registry import MODULES

        run_id = state["run_id"]
        plan, plan_digest = state["plan"], state["plan_digest"]
        try:
            state_mod.assert_plan_integrity(plan, plan_digest)
            run = self.runs.get_run(run_id)
            if plan.get("provider_identity") != run.get("provider_identity"):
                raise AgentError("AGENT_IDENTITY_MISMATCH", "plan identity differs from run")
            if plan["build_id"] != self._current_build_id():
                raise AgentError("AGENT_AUTHORITY_MISMATCH", "pinned methodology build is not the active bundle")
            source_set, live_sources = self._live_plan_sources(run, plan)
            upstream = self._upstream_digests(run_id, plan, module_id)
            fingerprint = self._input_fingerprint(plan, plan_digest, module_id, [a["digest"] for a in upstream])
            if MODULES[module_id].plan_approval:
                # Digest-bound human gate (invariant 5) before reuse or
                # execution; the wait sits outside every metered bracket.
                self._await_research_approval(run, plan, module_id, upstream)
                run = self.runs.get_run(run_id)

            # §12.14: the reuse-validation segment is a bracketed charge on
            # metered (agent-budgeted) runs; gate/interrupt waits accrue nothing.
            started = self._clock()
            artifacts = self._artifact_rows_by_module(run)
            content_expectations = self._artifact_content_expectations(
                run,
                plan,
                module_id,
                source_set,
                live_sources,
                artifacts,
                payload=(artifacts.get(module_id) or {}).get("payload"),
            )
            existing = self.runs.find_valid_artifact(
                run_id,
                module_id,
                fingerprint,
                content_expectations=content_expectations,
            )
            self._charge_active_if_metered(run_id, self._clock() - started)
            if existing is not None:
                if _is_placeholder_payload(existing.get("payload")) and run_id not in self._placeholder_deterministic_runs:
                    raise AgentError(
                        "DETERMINISTIC_EXECUTOR_UNAVAILABLE",
                        "a placeholder artifact cannot be reused without its test capability",
                    )
                # Reuse-first relink (§10.1): zero provider calls, byte-identical link.
                self.runs.complete_node(run_id, existing["case_id"], module_id, fingerprint,
                                        existing["payload"], existing["markdown"], existing["qa_status"], "system",
                                        content_expectations=content_expectations)
                return {"artifacts": {module_id: {"artifact_id": existing["id"], "digest": existing["digest"]}},
                        "node_status": {module_id: "succeeded"}}

            self.runs.node_running(run_id, module_id)
            spec = MODULES[module_id]
            mode = spec.mode_full if plan["depth"] == "full" else spec.mode_screen
            if run_id in self._scripted_runs and module_id in self._SCRIPTED_FIXTURES:
                # Canonical modules take the golden fixtures; every other node
                # (CP-3's universe binding included) runs its real
                # deterministic path.
                payload, markdown, qa_status = self._scripted_output(
                    run_id,
                    plan,
                    module_id,
                    fingerprint,
                    upstream,
                    source_set,
                    live_sources,
                )
            elif (
                run_id in self._placeholder_deterministic_runs
                and (
                    run_id in self._scripted_runs
                    or plan["depth"] == "screen"
                    or module_id in self._PLACEHOLDER_FULL_MODULES
                )
            ):
                universe = (self._pinned_loan_universe(plan, run["case_id"])
                            if module_id == "CP-3" else None)
                payload = build_deterministic_payload(
                    module_id, plan, input_fingerprint=fingerprint,
                    upstream_digests=[a["digest"] for a in upstream],
                    source_ids=source_set["source_ids"],
                    loan_universe=universe,
                )
                if run_id in self._scripted_runs and module_id == "CP-4C":
                    payload["calculations"] = [
                        self._calculation_runtime.execute("CP-4C", "funding_gap", {
                            "horizon_years": 2,
                            "cash": 100,
                            "currency": "USD",
                            "forecast_fcf": 50,
                            "instruments": [{
                                "instrument": "Near-term notes",
                                "amount": 300,
                                "years_to_maturity": 1,
                                "currency": "USD",
                            }],
                        }),
                        self._calculation_runtime.execute("CP-4C", "recovery_waterfall", {
                            "enterprise_value": 130,
                            "claims": [
                                *[{
                                    "claim_id": f"FILLER-{index:03d}",
                                    "class": "Senior Secured",
                                    "amount": 1,
                                } for index in range(80)],
                                {"claim_id": "SUN", "class": "Senior Unsecured", "amount": 200},
                            ],
                        }),
                    ]
                markdown, qa_status = None, "Passed"
            elif mode == "agent" and run_id not in self._scripted_runs:
                if not self.settings.agent_execution_enabled:
                    raise AgentError("AGENT_EXECUTION_DISABLED", "agent execution is disabled")
                # The provider loop reports its own calls but is handed no
                # identity at all, and the ledger knows the run without the
                # module. Both get the pair from a ContextVar scoped to this
                # node, rather than threading arguments through either.
                with run_context(run_id=run_id, module_id=module_id):
                    result = await self._execute_agent(run_id, plan, module_id, source_set, live_sources, fingerprint, upstream)
                payload, markdown, qa_status = result["payload"], result["markdown"], result["qa_status"]
            else:
                raise AgentError(
                    "DETERMINISTIC_EXECUTOR_UNAVAILABLE",
                    "the fixed deterministic payload is a host-control fixture only",
                )
            run = self.runs.get_run(run_id)
            payload = {**payload, "provider_identity": run.get("provider_identity")}
            content_expectations = self._artifact_content_expectations(
                run,
                plan,
                module_id,
                source_set,
                live_sources,
                self._artifact_rows_by_module(run),
                payload=payload,
            )
            started = self._clock()
            artifact = self.runs.complete_node(
                run_id,
                run["case_id"],
                module_id,
                fingerprint,
                payload,
                markdown,
                qa_status,
                run["created_by"],
                content_expectations=content_expectations,
            )
            self._charge_active_if_metered(run_id, self._clock() - started)
            if self._crash_gap.get(run_id) == module_id:
                raise SimulatedCrash(f"injected crash in commit gap for {module_id}")
            return {"artifacts": {module_id: {"artifact_id": artifact["id"], "digest": artifact["digest"]}},
                    "node_status": {module_id: "succeeded"}}
        except SimulatedCrash:
            raise
        except ModuleFailure as exc:
            # First terminal failure wins the run error (CAS in the store);
            # racing sibling failures in the same superstep no-op (§12.9) — so
            # the log, unlike run.failed, carries every module's refusal, not
            # only the one that won the CAS.
            log_event("refusal", run_id=run_id, module_id=exc.module_id, code=exc.code)
            self.runs.finalize_failure(run_id, exc.code, exc.module_id)
            raise
        except (AgentError, StoreConflict) as exc:
            # The code only. Never str(exc): a validation failure quotes the
            # model's own output, which is document-derived.
            log_event("refusal", run_id=run_id, module_id=module_id, code=exc.code)
            self.runs.finalize_failure(run_id, exc.code, module_id)
            raise ModuleFailure(exc.code, module_id) from exc

    async def _execute_agent(
        self,
        run_id: str,
        plan: dict[str, Any],
        module_id: str,
        source_set: dict[str, Any],
        live_sources: list[dict[str, Any]],
        fingerprint: str,
        upstream: list[dict[str, Any]],
    ) -> dict[str, Any]:
        from ..modules.registry import MODULES

        if self.provider is None:
            raise AgentError("AGENT_PROVIDER_UNAVAILABLE", "no provider is configured")
        lock = self._agent_locks.setdefault((self._loop_key(), run_id), asyncio.Lock())
        async with lock:  # §10.2: agent execution serialises per run
            run = self.runs.get_run(run_id)
            if run["status"] in TERMINAL:
                raise AgentError((run.get("error") or {}).get("code", "RUN_NOT_READY"))
            identity = self._assert_run_provider_identity(run)
            if identity is None:  # guarded above for every agent route
                raise AgentError("AGENT_IDENTITY_MISMATCH", "agent run identity is absent")
            spec = MODULES[module_id]
            if spec.calculators != self._calculation_runtime.calculator_ids(module_id):
                raise AgentError(
                    "AGENT_AUTHORITY_MISMATCH",
                    "module calculator registry differs from the pinned execution runtime",
                )
            agent_modules = _agent_module_ids_for_plan(plan)
            limits = dict(route_envelope(agent_modules, MODULES))
            limits.update(self._budget_overrides)
            self.runs.init_budget(run_id, limits)
            budget = self.runs.get_budget(run_id)
            if budget["inflight_request_digest"]:
                raise AgentError("AGENT_BUDGET_EXCEEDED", "unresolved provider request from a prior execution")

            manifest = []
            for source in live_sources:  # validated live in _run_module, before reuse or mode dispatch
                manifest.append({
                    "source_id": source["id"],
                    "sha256": source["sha256"],
                    "filename": source.get("filename", source["id"]),
                    "media_type": source.get("media_type", "application/octet-stream"),
                    "blocks": [
                        {"block_id": block.get("block_id"), "locator": block.get("locator"),
                         "extractor_version": block.get("extractor_version"), "confidence": block.get("confidence")}
                        for block in source.get("blocks") or []
                    ],
                })
            bound_manifest(manifest)

            case = self.store.get_case(run["case_id"])
            if case is None:
                raise AgentError("AGENT_AUTHORITY_MISMATCH", "run case is unavailable")
            plan_node = self._plan_node(plan, module_id)
            host_identity = {
                "module_id": module_id,
                "module_name": plan_node["module_name"],
                "run_id": run_id,
                "case_id": run["case_id"],
                "issuer_name": case["issuer"],
                "issuer_id": run["case_id"].replace("_", "-"),
                "reporting_period": run["created_at"][:10],
                "analysis_date": run["created_at"][:10],
                "profile_id": plan["profile_id"],
                "selection_id": plan["selection_id"],
                "source_set_id": source_set["id"],
                "source_set_version": source_set["version"],
                "calculator_ids": list(spec.calculators),
                "upstream_digests": [a["digest"] for a in upstream],
            }
            research_identity = self._research_identity(run, module_id)
            if research_identity is not None:
                host_identity["research"] = research_identity
            # §12.6 verify-at-use: prompt bytes are hashed against the PINNED
            # build's manifest, whose digest the plan carries from gate exit.
            if plan.get("manifest_digest") != digest(self.bundle.integrity):
                raise AgentError("AGENT_AUTHORITY_MISMATCH", "pinned integrity manifest is not the active bundle")
            system, user = compile_module_prompts(
                module_id, host_identity, manifest,
                [{"module_id": a["module_id"], "digest": a["digest"], "markdown": a["markdown"] or ""} for a in upstream],
                root=self.settings.deploy_v_root,
                pinned_manifest=self.bundle.integrity,
            )

            used = budget["used"]
            reader = EvidenceReader(
                self.store, run["case_id"], source_set["id"], run_id,
                read_limit=min(
                    EVIDENCE_READS_PER_MODULE,
                    limits["evidence_reads"] - used.get("evidence_reads", 0),
                ),
                byte_limit=min(
                    EVIDENCE_BYTES_PER_MODULE,
                    limits["evidence_bytes"] - used.get("evidence_bytes", 0),
                ),
                on_read=lambda source_id, block_ids, returned_bytes: (
                    self.runs.charge_budget(run_id, "evidence_reads", 1),
                    self.runs.charge_budget(run_id, "evidence_bytes", returned_bytes),
                ),
            )
            calculation_records: list[dict[str, Any]] = []
            incomplete_calculators: dict[str, int] = {}
            repair_state = {"used": False}
            tools = (READ_EVIDENCE_TOOL,)
            if spec.calculators:
                tools += (methodology_calculation_tool(spec.calculators),)

            attempt_base = {
                "run_id": run_id,
                "module_id": module_id,
                "provider_identity": identity.as_dict(),
            }
            provider_interacted = False

            def record(kind: str, **details: Any) -> None:
                nonlocal provider_interacted
                if kind in {"generation", "provider_retry"}:
                    provider_interacted = True
                if kind == "provider_retry":
                    self.runs.charge_budget(run_id, "provider_retries", 1)
                if kind == "repair_reserve":
                    self.runs.charge_budget(run_id, "repairs", 1)
                from .budget import AttemptRecorder

                row = {**attempt_base, "kind": kind[:40], **AttemptRecorder._allow(details)}
                self.runs.record_attempt(run_id, row, terminal=kind == "terminal")

            def reserve(request_digest: str, input_tokens: int, output_tokens: int, retry: bool) -> None:
                self.runs.reserve_provider(run_id, request_digest, input_tokens, output_tokens, retry)

            def reconcile(
                request_digest: str, reserved_in: int, reserved_out: int,
                actual_in: int, actual_out: int,
            ) -> str | None:
                try:
                    self.runs.reconcile_provider(
                        run_id, request_digest, reserved_in, reserved_out, actual_in, actual_out,
                    )
                except StoreConflict as exc:
                    return exc.code
                return None

            def before_create() -> None:
                nonlocal provider_interacted
                provider_interacted = True
                if run_id in self._crash_before_create:
                    raise SimulatedCrash("injected crash mid provider call")

            def charge_time(seconds: float) -> None:
                self.runs.charge_budget(run_id, "active_minutes", seconds / 60)

            def remaining_seconds() -> float:
                budget_now = self.runs.get_budget(run_id)
                remaining = (budget_now["limits"]["active_minutes"] - budget_now["used"].get("active_minutes", 0)) * 60
                if remaining <= 0:
                    raise AgentError("AGENT_BUDGET_EXCEEDED", "active worker time exhausted")
                return remaining

            async def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
                if name != "run_methodology_calculation":
                    raise AgentError("AGENT_OUTPUT_INVALID", "unknown host tool")
                calculator_id, inputs = _parse_calculation_input(arguments)
                if any(record["calculator_id"] == calculator_id for record in calculation_records):
                    raise AgentError(
                        "METHODOLOGY_CALCULATOR_NOT_ALLOWED",
                        "each assigned calculator may run once per module",
                    )
                if calculator_id in incomplete_calculators:
                    # A retry after an incomplete result is the module's one
                    # repair; a second retry has nothing left to spend.
                    if repair_state["used"]:
                        raise AgentError(
                            "METHODOLOGY_CALCULATOR_NOT_ALLOWED",
                            "the calculator retry allowance is spent",
                        )
                    repair_state["used"] = True
                    record("repair_reserve", calculator_id=calculator_id)
                try:
                    calculation = await asyncio.to_thread(
                        self._calculation_runtime.execute,
                        module_id,
                        calculator_id,
                        inputs,
                    )
                except MethodologyCalculationError as exc:
                    raise AgentError(exc.code) from exc
                if not calculation_output_complete(
                    module_id,
                    calculator_id,
                    calculation["canonical_output"],
                ):
                    # The pinned calculator ran and produced nothing usable for
                    # these inputs. That is the model's extraction, not the
                    # evidence, so it is never an evidence refusal: the core
                    # numbers end the run once the repair is spent, everything
                    # else becomes a host-declared limitation on the artifact.
                    incomplete_calculators[calculator_id] = incomplete_calculators.get(calculator_id, 0) + 1
                    record(
                        "calculation_incomplete",
                        module_id=module_id,
                        calculator_id=calculator_id,
                        input_digest=calculation["input_digest"],
                    )
                    if repair_state["used"] and _calculation_is_core(plan["pathway"], module_id, calculator_id):
                        raise AgentError(
                            CALCULATION_INCOMPLETE,
                            "a core methodology calculation is incomplete after its repair",
                        )
                    return {
                        "calculator_id": calculator_id,
                        "complete": False,
                        "code": CALCULATION_INCOMPLETE,
                        "input_digest": calculation["input_digest"],
                        "retry_available": not repair_state["used"],
                        "reason": "the pinned calculator returned no usable result for these inputs",
                    }
                incomplete_calculators.pop(calculator_id, None)
                calculation_records.append(calculation)
                record_attempt = _calculation_ref(calculation)
                record(
                    "calculation",
                    module_id=module_id,
                    **record_attempt,
                )
                return calculation

            def validate(decoded: dict[str, Any]) -> dict[str, Any]:
                output = CanonicalModuleOutput.model_validate(decoded)
                if any(flag.startswith("host:") for flag in output.limitation_flags):
                    # `host:` flags are host-derived provenance; a provider may
                    # not label its own text as a host finding.
                    raise ValueError("provider limitation flags may not carry the host prefix")
                validate_citations([ref.model_dump() for ref in output.evidence_refs], reader.delivered())
                limited = tuple(
                    calculator_id for calculator_id in spec.calculators
                    if calculator_id in incomplete_calculators
                    and not any(record["calculator_id"] == calculator_id for record in calculation_records)
                )
                if any(_calculation_is_core(plan["pathway"], module_id, calculator_id) for calculator_id in limited):
                    raise AgentError(
                        CALCULATION_INCOMPLETE,
                        "a core methodology calculation is incomplete",
                    )
                _validate_calculation_refs(
                    [ref.model_dump() for ref in output.calculation_refs],
                    calculation_records,
                    spec.calculators,
                    limited,
                )
                validate_model_sources(
                    output.markdown,
                    {source_id for source_id, _block_id in reader.delivered()},
                    module_id=module_id,
                )
                confidence = recompute_confidence(decoded)
                if confidence["qa_status"] != "Passed":
                    gate = decoded["source_gate"]
                    code = (
                        "SOURCE_EVIDENCE_INSUFFICIENT" if gate == "fail"
                        else "SOURCE_EVIDENCE_RESTRICTED" if gate == "partial"
                        else "ANALYSIS_QA_BLOCKED" if confidence["qa_status"] == "Blocked"
                        else "ANALYSIS_QA_RESTRICTED"
                    )
                    raise AgentError(code)
                reporting_period = host_identity["reporting_period"]
                handoff_lineage = self._handoff_lineage(run_id, module_id, upstream)
                handoff_metadata = {
                    "module_id": module_id,
                    "module_name": host_identity["module_name"],
                    "run_id": run_id,
                    "reporting_period": reporting_period,
                    "analysis_date": host_identity["analysis_date"],
                    "confidence_score": confidence["confidence_score"],
                    "confidence_band": confidence["confidence_band"].title(),
                    "qa_status": confidence["qa_status"],
                    "committee_status": "Draft Only",
                    "limitation_flags": [
                        *output.limitation_flags,
                        *(f"host:calculation_incomplete:{calculator_id}" for calculator_id in limited),
                    ],
                    "validation_warnings": output.validation_warnings,
                    "upstream_artifacts_used": [
                        {
                            "module_id": artifact["module_id"],
                            "run_id": artifact["run_id"],
                            "period": (
                                (artifact.get("payload") or {}).get("handoff_metadata") or {}
                            ).get("reporting_period", reporting_period),
                            "artifact_digest": artifact["digest"],
                        }
                        for artifact in handoff_lineage
                    ],
                    "downstream_consumers": self._downstream_consumers(plan, module_id),
                    "issuer_name": host_identity["issuer_name"],
                    "issuer_id": host_identity["issuer_id"],
                }
                host_derived = [
                    "module_id", "module_name", "run_id", "analysis_date",
                    "confidence_score", "confidence_band", "qa_status",
                    "committee_status", "upstream_artifacts_used",
                    "downstream_consumers", "issuer_name", "issuer_id",
                    "calculation_limitations",
                ]
                if research_identity is not None:
                    # The CP-DR envelope is stamped by the host from the approved
                    # plan and the validated contract, never from provider prose.
                    handoff_metadata.update(research_handoff_fields(
                        brief=research_identity["brief"],
                        approved_plan_hash=research_identity["approved_plan_hash"],
                        subject_name=host_identity["issuer_name"],
                        scope_key=host_identity["issuer_id"],
                        fields_present=output.fields_present,
                        fields_total=output.fields_total,
                    ))
                    host_derived.extend(RESEARCH_HANDOFF_FIELDS)
                envelope = canonicalize_for_tests(
                    module_id=module_id,
                    provider_markdown=output.markdown,
                    run_identity=host_identity,
                    delivered=reader.delivered(),
                    build_id=plan["build_id"],
                    handoff_metadata=handoff_metadata,
                )
                self.bundle.validate_handoff(
                    envelope["canonical_output"]["markdown"],
                    module_id=module_id,
                    run_id=run_id,
                    reporting_period=reporting_period,
                )
                envelope["host_confidence"] = confidence
                envelope["handoff_metadata_provenance"] = {
                    "host_derived_fields": host_derived,
                    "provider_declared_bounded_fields": [
                        "limitation_flags", "validation_warnings",
                    ],
                    "reporting_period_basis": "host_pinned_run_date",
                }
                envelope["calculations"] = list(calculation_records)
                envelope["calculation_limitations"] = [
                    {"calculator_id": calculator_id, "code": CALCULATION_INCOMPLETE}
                    for calculator_id in limited
                ]
                envelope["lineage"] = {
                    "input_fingerprint": fingerprint,
                    "upstream_digests": [artifact["digest"] for artifact in upstream],
                }
                envelope["source_set"] = {"id": source_set["id"], "version": source_set["version"], "digest": plan["source_set_digest"]}
                envelope["upstream_artifacts"] = [
                    {"module_id": a["module_id"], "artifact_id": a["id"], "digest": a["digest"]} for a in upstream
                ]
                return {"payload": envelope, "markdown": envelope["canonical_output"]["markdown"], "qa_status": confidence["qa_status"]}

            try:
                return await run_agent_module(
                    provider=self.provider,
                    system=system,
                    user=user,
                    schema=CanonicalModuleOutput.model_json_schema(),
                    max_tokens=spec.max_output_tokens,
                    read_evidence=reader.read,
                    tools=tools,
                    call_tool=call_tool,
                    validate=validate,
                    reserve=reserve,
                    reconcile=reconcile,
                    record=record,
                    slots=self._slots,
                    charge_time=charge_time,
                    remaining_seconds=remaining_seconds,
                    before_create=before_create,
                    clock=self._clock,
                    expected_identity=identity,
                    repair_state=repair_state,
                )
            except SimulatedCrash:
                raise
            except (AgentError, StoreConflict) as exc:
                code = exc.code
                if provider_interacted:
                    with contextlib.suppress(Exception):
                        record("terminal", terminal_code=code)
                raise AgentError(code) from exc
            except Exception as exc:
                # §12.9 collapse rule: never persist provider error bodies.
                if provider_interacted:
                    with contextlib.suppress(Exception):
                        record("terminal", terminal_code="CANONICAL_GENERATION_FAILED")
                raise AgentError("CANONICAL_GENERATION_FAILED", "agent module execution failed") from exc

    def _finalize_node(self, state: dict[str, Any]) -> dict[str, Any]:
        run_id = state["run_id"]
        plan = state["plan"]
        state_mod.assert_plan_integrity(plan, state["plan_digest"])
        # §12.14: the final re-validation before success is a metered bracket,
        # charged even when verification throws; an over-ceiling charge fails
        # the run closed HERE, so a success commit never lands past the budget
        # ceiling (the re-hosted 174+10 finalization-deadline contract).
        try:
            # Linearize source authority and terminal success: a withdrawal is
            # either visible to the last verification or happens after a run
            # that was validly terminalized.
            with self.store.authority_guard():
                started = self._clock()
                try:
                    self._verify_run_artifacts(run_id, plan)
                finally:
                    self._charge_active_if_metered(run_id, self._clock() - started)
                self.runs.finalize_success(run_id)
        except (AgentError, StoreConflict) as exc:
            log_event("refusal", run_id=run_id, module_id=None, code=exc.code)
            self.runs.finalize_failure(run_id, exc.code, None)
            raise ModuleFailure(exc.code, None) from exc
        return {"error": None}

    def _verify_run_artifacts(self, run_id: str, plan: dict[str, Any]) -> None:
        """Finalization gate over the exact plan artifact graph."""
        run = self.runs.get_run(run_id)
        self._validated_plan_artifacts(run, plan)

    def _validated_plan_artifacts(
        self,
        run: dict[str, Any],
        plan: dict[str, Any],
        references: list[dict[str, Any]] | None = None,
        *,
        accepted_snapshot_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if (
            not isinstance(run, dict)
            or plan != run.get("plan")
            or digest(plan) != run.get("plan_digest")
            or plan.get("pathway") != run.get("pathway")
            or plan.get("depth") != run.get("depth")
            or plan.get("provider_identity") != run.get("provider_identity")
        ):
            raise AgentError("AGENT_AUTHORITY_MISMATCH", "run differs from its pinned plan")
        plan_nodes = plan.get("nodes")
        run_nodes = run.get("nodes")
        if not isinstance(plan_nodes, list) or not isinstance(run_nodes, list):
            raise AgentError("AGENT_AUTHORITY_MISMATCH", "run artifact plan is unavailable")
        expected_modules = [node.get("module_id") for node in plan_nodes]
        nodes = {node.get("module_id"): node for node in run_nodes if isinstance(node, dict)}
        if (
            any(not isinstance(module_id, str) or not module_id for module_id in expected_modules)
            or len(expected_modules) != len(set(expected_modules))
            or set(nodes) != set(expected_modules)
        ):
            raise AgentError("AGENT_AUTHORITY_MISMATCH", "run artifact plan is invalid")
        if references is not None and (
            not isinstance(references, list)
            or [reference.get("module_id") if isinstance(reference, dict) else None
                for reference in references] != expected_modules
            or any(not isinstance(reference, dict) or set(reference) != {"id", "module_id", "digest"}
                   for reference in references)
        ):
            raise AgentError("AGENT_AUTHORITY_MISMATCH", "snapshot artifact set is incomplete")
        source_set, live_sources = self._live_plan_sources(run, plan)
        self._verify_source_vault(live_sources)
        bindings_by_module = self._calculation_bindings_by_module(fresh=True)
        artifacts: list[dict[str, Any]] = []
        ids: set[str] = set()
        for index, module_id in enumerate(expected_modules):
            node = nodes[module_id]
            reference = references[index] if references is not None else None
            artifact_id = reference["id"] if reference is not None else node.get("artifact_id")
            artifact = self.runs.get_artifact(artifact_id) if isinstance(artifact_id, str) else None
            if (
                node.get("status") != "succeeded"
                or node.get("artifact_id") != artifact_id
                or artifact_id in ids
                or artifact is None
                or (reference is not None and artifact.get("digest") != reference["digest"])
            ):
                raise ModuleFailure("RUN_NOT_READY", module_id, "module artifact reference is invalid")
            ids.add(artifact_id)
            artifacts.append(artifact)
        by_module = {artifact["module_id"]: artifact for artifact in artifacts}
        persisted_test_authority = (
            accepted_snapshot_id is not None
            and self.settings.environment == "development"
            and (run.get("provider_identity") or {}).get("provider_name") == "host_control"
            and run.get("status") == "succeeded"
            and run.get("accepted_snapshot_id") == accepted_snapshot_id
        )
        for module_id, artifact in zip(expected_modules, artifacts, strict=True):
            if (
                _is_placeholder_payload(artifact.get("payload"))
                and run["id"] not in self._placeholder_deterministic_runs
                and not persisted_test_authority
            ):
                raise AgentError(
                    "DETERMINISTIC_EXECUTOR_UNAVAILABLE",
                    f"placeholder artifact cannot authorize {module_id}",
                )
            if artifact.get("qa_status") != "Passed":
                raise ModuleFailure("QA_BLOCKED", module_id, "module QA is not Passed")
            if not verify_artifact_content(
                artifact,
                run_id=run["id"],
                case_id=run["case_id"],
                module_id=module_id,
                input_fingerprint=self._input_fingerprint(
                    plan,
                    run["plan_digest"],
                    module_id,
                    [by_module[parent]["digest"]
                     for parent in self._plan_node(plan, module_id)["dependencies"]],
                ),
                methodology_build_id=plan["build_id"],
                provider_identity=run.get("provider_identity"),
                **self._artifact_content_expectations(
                    run,
                    plan,
                    module_id,
                    source_set,
                    live_sources,
                    by_module,
                    payload=artifact.get("payload"),
                    bindings_by_module=bindings_by_module,
                ),
            ):
                raise ModuleFailure("RUN_NOT_READY", module_id, "module artifact failed verification")
            self._replay_artifact_calculations(artifact, module_id)
        return artifacts

    def validated_snapshot_artifacts(
        self,
        snapshot: dict[str, Any],
        run: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Resolve an accepted snapshot's exact, ordered plan artifact graph."""
        if snapshot.get("run_id") != run.get("id") or snapshot.get("case_id") != run.get("case_id"):
            raise AgentError("AGENT_AUTHORITY_MISMATCH", "snapshot differs from its run")
        return self._validated_plan_artifacts(
            run,
            run.get("plan") or {},
            snapshot.get("artifacts"),
            accepted_snapshot_id=snapshot.get("id"),
        )

    def validated_run_artifact(
        self,
        artifact: dict[str, Any],
        run: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate one linked artifact while a run may still be in progress."""
        plan = run.get("plan") or {}
        module_id = artifact.get("module_id")
        node = next(
            (candidate for candidate in run.get("nodes") or []
             if candidate.get("module_id") == module_id),
            None,
        )
        if (
            not isinstance(module_id, str)
            or node is None
            or node.get("artifact_id") != artifact.get("id")
            or node.get("status") != "succeeded"
        ):
            raise AgentError("AGENT_AUTHORITY_MISMATCH", "artifact is not linked to the run")
        persisted_test_authority = (
            self.settings.environment == "development"
            and (run.get("provider_identity") or {}).get("provider_name") == "host_control"
            and run.get("status") == "succeeded"
            and isinstance(run.get("accepted_snapshot_id"), str)
            and (self.store.get_case(run["case_id"]) or {}).get("accepted_snapshot_id")
            == run["accepted_snapshot_id"]
        )
        if (
            _is_placeholder_payload(artifact.get("payload"))
            and run["id"] not in self._placeholder_deterministic_runs
            and not persisted_test_authority
        ):
            raise AgentError(
                "DETERMINISTIC_EXECUTOR_UNAVAILABLE",
                "placeholder artifact has no current test authority",
            )
        source_set, live_sources = self._live_plan_sources(run, plan)
        if not verify_artifact_content(
            artifact,
            run_id=run["id"],
            case_id=run["case_id"],
            module_id=module_id,
            input_fingerprint=self._input_fingerprint(
                plan,
                run["plan_digest"],
                module_id,
                [
                    self._artifact_rows_by_module(run)[parent]["digest"]
                    for parent in self._plan_node(plan, module_id)["dependencies"]
                ],
            ),
            methodology_build_id=plan.get("build_id"),
            provider_identity=run.get("provider_identity"),
            **self._artifact_content_expectations(
                run,
                plan,
                module_id,
                source_set,
                live_sources,
                self._artifact_rows_by_module(run),
                payload=artifact.get("payload"),
                bindings_by_module=self._calculation_bindings_by_module(fresh=True),
            ),
        ):
            raise AgentError("AGENT_AUTHORITY_MISMATCH", "artifact content is invalid")
        self._replay_artifact_calculations(artifact, module_id)
        return artifact

    # -- public API --------------------------------------------------------

    async def start_run(self, *, case_id: str, pathway: str, depth: str, actor: str,
                        focus_questions: list[str] | None = None,
                        upgraded_from_run_id: str | None = None,
                        research_brief: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._start_run(
            case_id=case_id, pathway=pathway, depth=depth, actor=actor,
            focus_questions=focus_questions, upgraded_from_run_id=upgraded_from_run_id,
            research_brief=research_brief,
            allow_placeholder_deterministic=False, scripted=False,
        )

    async def start_run_for_tests(
        self, *, case_id: str, pathway: str, depth: str, actor: str,
        focus_questions: list[str] | None = None,
        upgraded_from_run_id: str | None = None,
        allow_placeholder_deterministic: bool = False,
        research_brief: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._require_host_control_for_tests()
        return await self._start_run(
            case_id=case_id, pathway=pathway, depth=depth, actor=actor,
            focus_questions=focus_questions, upgraded_from_run_id=upgraded_from_run_id,
            research_brief=research_brief,
            allow_placeholder_deterministic=allow_placeholder_deterministic, scripted=False,
        )

    async def _start_run(
        self, *, case_id: str, pathway: str, depth: str, actor: str,
        focus_questions: list[str] | None,
        upgraded_from_run_id: str | None,
        allow_placeholder_deterministic: bool,
        scripted: bool,
        research_brief: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if pathway not in MVP_PATHWAYS:
            raise EngineError("PATHWAY_NOT_AVAILABLE", f"{pathway} is outside the MVP cut")
        depth = Depth(depth).value
        if depth not in supported_depths(pathway):
            raise EngineError("DEPTH_NOT_SUPPORTED", f"{pathway} does not run at {depth} depth")
        research: dict[str, Any] | None = None
        if pathway == "DEEP_RESEARCH":
            # The brief is refused before any row exists: no run, no pin, no
            # pointer for a brief the contract or the boundary rules reject.
            if research_brief is None:
                raise EngineError("RESEARCH_BRIEF_REQUIRED", "DEEP_RESEARCH requires a research brief")
            try:
                brief = validate_brief(research_brief)
            except AgentError as exc:
                raise EngineError(exc.code, "research brief refused") from exc
            research = {"brief": brief, "brief_digest": research_brief_digest(brief)}
        elif research_brief is not None:
            raise EngineError("RESEARCH_BRIEF_NOT_APPLICABLE", "research_brief is only valid for DEEP_RESEARCH")
        if self.store.get_case(case_id) is None:
            raise EngineError("CASE_NOT_FOUND", case_id)
        model_jobs = self._model_service.active_job_count() if self._model_service is not None else 0
        if self.runs.active_admission_count() + self._admission_offset + model_jobs >= MAX_ACTIVE_JOBS:
            raise EngineError("ADMISSION_BUSY", "active job ceiling reached")
        for question in focus_questions or []:
            state_mod.validate_boundary_text(question)
        if self._route_requires_agent(pathway, depth):
            if not self.settings.agent_execution_enabled:
                raise EngineError("AGENT_EXECUTION_DISABLED", "agent execution is disabled")
            if self.provider is None or self._provider_identity is None:
                raise EngineError("AGENT_PROVIDER_UNAVAILABLE", "no provider identity is configured")
            try:
                self._provider_identity.ensure_current()
            except AgentError as exc:
                raise EngineError(exc.code, "provider identity is not current") from exc
        run = self.runs.create_run(case_id, pathway, depth, actor,
                                   focus_questions=focus_questions,
                                   upgraded_from_run_id=upgraded_from_run_id,
                                   provider_identity=self._provider_identity,
                                   schema_version=state_mod.SCHEMA_VERSION,
                                   research_brief=research["brief"] if research else None,
                                   research_brief_digest=research["brief_digest"] if research else None)
        if allow_placeholder_deterministic:
            self._placeholder_deterministic_runs.add(run["id"])
        if scripted:
            self._scripted_runs.add(run["id"])
        # The case's workspace attaches to its latest execution; success does not
        # clear this — only a newer run moves it.
        self.store.update_case(case_id, current_execution_id=run["id"])
        await self._drive(run["id"], self._initial_state(run), interrupt_after=["gate"])
        self._schedule_continuation(run["id"])
        return self.get_run(run["id"])

    def _initial_state(self, run: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": state_mod.SCHEMA_VERSION,
            "run_id": run["id"],
            "case_id": run["case_id"],
            "plan": None,
            "plan_digest": None,
            "artifacts": {},
            "node_status": {},
            "error": None,
        }

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self.runs.get_run(run_id)

    async def resume(self, run_id: str) -> dict[str, Any]:
        from langgraph.types import Command

        run = self.runs.get_run(run_id)
        if run is None:
            raise EngineError("RESUME_NOT_APPLIED", "run does not exist")
        try:
            self._assert_run_provider_identity(run)
        except AgentError as exc:
            return await self._finalize_identity_failure(run_id, exc)
        self._raw_schema_check(run_id)
        ticket = self.runs.latest_ticket(run_id)
        if ticket is not None:
            # §12.21: consume the one-shot ticket before acting on the resume.
            if not self.runs.consume_ticket(run_id, ticket):
                return self.get_run(run_id)
        await self._drive(run_id, Command(resume=True), interrupt_after=["gate"])
        self._schedule_continuation(run_id)
        return self.get_run(run_id)

    async def approve_research_plan(self, run_id: str, *, plan_hash: str, actor: str) -> dict[str, Any]:
        """Approve the exact proposed plan (invariant 5). The store does the
        compare-and-swap; this re-checks identity and pinned-source liveness
        first and schedules the continuation afterwards — approval never drives
        the graph inline, so the serving loop keeps answering."""
        run = self.runs.get_run(run_id)
        if run is None:
            raise EngineError("RUN_NOT_FOUND", run_id)
        if run.get("research") is None:
            raise EngineError("RESEARCH_PLAN_NOT_PENDING", "run has no research plan")
        try:
            self._assert_run_provider_identity(run)
        except AgentError as exc:
            raise EngineError(exc.code, "provider identity is not current") from exc
        if run.get("plan_digest"):
            try:
                self._live_plan_sources(run, run["plan"])
            except AgentError as exc:
                raise EngineError("SOURCE_SET_CHANGED", "one or more pinned sources are unavailable") from exc
        try:
            self.runs.approve_research_plan(run_id, plan_hash, actor, audit=self.store._audit)
        except StoreConflict as exc:
            raise EngineError(exc.code, "research plan approval refused") from exc
        self._schedule_continuation(run_id)
        return self.get_run(run_id)

    def deep_research_availability(self) -> tuple[bool, str | None]:
        """Runtime truth for the case wire's `deep_research_available`: the cut,
        the compiled route, the registry and the provider binding — never a
        literal (Task 7)."""
        from ..methodology.bundle import MethodologyError
        from ..modules.registry import MODULES
        from .graphs import compiled_route

        if "DEEP_RESEARCH" not in MVP_PATHWAYS:
            return False, "Deep Research is outside this deployment's route cut."
        try:
            route = compiled_route("DEEP_RESEARCH", "full", self.settings.deploy_v_root)
        except MethodologyError:
            return False, "The Deep Research route does not compile from the verified bundle."
        missing = [module_id for module_id in route.nodes if module_id not in MODULES]
        if missing:
            return False, f"Deep Research route nodes are not registered: {', '.join(missing)}."
        if not self.settings.agent_execution_enabled:
            return False, "Deep Research requires agent execution, which is disabled for this deployment."
        if self.provider is None or self._provider_identity is None:
            return False, "Deep Research requires a qualified provider binding, which is not configured."
        try:
            self._provider_identity.ensure_current()
        except AgentError as exc:
            return False, f"Deep Research requires a current provider qualification ({exc.code})."
        return True, None

    async def wait(self, run_id: str) -> dict[str, Any]:
        run = self.runs.get_run(run_id)
        if run is None:
            raise EngineError("RUN_NOT_FOUND", run_id)
        if run["status"] in {"succeeded", "failed"}:
            return run
        try:
            self._assert_run_provider_identity(run)
        except AgentError as exc:
            return await self._finalize_identity_failure(run_id, exc)
        self._raw_schema_check(run_id)
        await self._drive(run_id, None)
        return self.get_run(run_id)

    async def recover(self) -> None:
        """Startup recovery (§10.5): skip threads parked at an interrupt,
        re-admit crashed mid-run threads."""
        await self._reap_terminal_threads()
        pending = self.runs.non_terminal_runs()
        log_event("recovery.started", runs=len(pending))
        for run in pending:
            try:
                self._assert_run_provider_identity(run)
            except AgentError as exc:
                await self._finalize_identity_failure(run["id"], exc)
                log_event("recovery.run", run_id=run["id"], action="failed_identity", code=exc.code)
                continue
            graph = await self._graph(run["pathway"], run["depth"])
            graph_state = await graph.aget_state(self._config(run["id"]))
            if any(task.interrupts for task in graph_state.tasks):
                if run["status"] != "running":
                    log_event("recovery.run", run_id=run["id"], action="skipped_interrupt")
                    continue
                # The gate was cleared out of band (a research plan approved,
                # status already `running`) and the process died before the
                # continuation ran: the checkpointed interrupt waits on nobody,
                # so re-enter the node from the last checkpoint (invariant 6).
                self._raw_schema_check(run["id"])
                log_event("recovery.run", run_id=run["id"], action="resumed_after_gate")
                await self._drive(run["id"], None)
                continue
            self._raw_schema_check(run["id"])
            if graph_state.created_at is None:
                # Crashed between create_run and the first checkpoint: re-admit
                # through the graph from a fresh initial state (§10.5/§10.9 —
                # capacity self-heals, no orphaned queued slots).
                log_event("recovery.run", run_id=run["id"], action="readmitted")
                await self._drive(run["id"], self._initial_state(run))
            else:
                log_event("recovery.run", run_id=run["id"], action="resumed")
                await self._drive(run["id"], None)

    def readiness(self) -> dict[str, bool]:
        """What has to hold before this instance should take traffic: the domain
        store answers, the vendored bundle still hashes to its own manifest
        (invariant 4), and the checkpoint database can take a write lock
        (invariant 6's durability). Every probe really runs — a readiness answer
        assembled from startup state is a decoration — but at most once per
        READINESS_TTL_SECONDS, because this route answers anonymous callers."""
        with self._readiness_lock:
            now = self._clock()
            if self._readiness is not None and now - self._readiness[0] < READINESS_TTL_SECONDS:
                return dict(self._readiness[1])
            checks = {
                "store": _probe(self._probe_store),
                "bundle": _probe(self.bundle.verify),
                "checkpointer": _probe(self._probe_checkpointer),
            }
            self._readiness = (now, checks)
            return dict(checks)

    def _probe_store(self) -> None:
        with self.store.engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")

    def _probe_checkpointer(self) -> None:
        # Use the real saver setup for an empty database, then prove both its
        # schema and its ability to acquire a write lock. A short-lived writer
        # gets 250 ms to finish; a lock held longer fails readiness closed.
        from langgraph.checkpoint.sqlite import SqliteSaver

        conn = sqlite3.connect(str(self.checkpoint_path), timeout=0.25)
        try:
            tables = {
                row[0]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
            if not {"checkpoints", "writes"} <= tables:
                SqliteSaver(conn).setup()
            conn.execute(
                "SELECT thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, "
                "type, checkpoint, metadata FROM checkpoints LIMIT 0"
            )
            conn.execute(
                "SELECT thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, "
                "type, value FROM writes LIMIT 0"
            )
            conn.execute("BEGIN IMMEDIATE")
            conn.rollback()
        finally:
            conn.close()

    def active_execution_count(self) -> int:
        return self._active_invocations

    def events_after(self, run_id: str, after_seq: int) -> list[dict[str, Any]]:
        return self.runs.events_after(run_id, after_seq)

    def artifacts_for_run(self, run_id: str) -> list[dict[str, Any]]:
        return self.runs.artifacts_for_run(run_id)

    def budget_used(self, run_id: str) -> dict[str, Any]:
        budget = self.runs.get_budget(run_id)
        if budget is None:
            return {key: 0 for key in DIMENSIONS}
        return {key: budget["used"].get(key, 0) for key in DIMENSIONS}

    async def accept(self, run_id: str, *, actor: str) -> dict[str, Any]:
        # The authority lock linearizes acceptance against ingest, withdrawal
        # and finalization; waiting for it on the loop thread would freeze
        # every other coroutine (SSE tails, readiness), so wait in a worker.
        def accept_under_lock() -> dict[str, Any]:
            with self.store.authority_guard():
                return self._accept_locked(run_id, actor=actor)

        return await asyncio.to_thread(accept_under_lock)

    def _accept_locked(self, run_id: str, *, actor: str) -> dict[str, Any]:
        run = self.runs.get_run(run_id)
        if run is None:
            raise EngineError("RUN_NOT_FOUND", run_id)
        if run["accepted_snapshot_id"]:
            snapshot = self.runs.get_snapshot(run["accepted_snapshot_id"])
            return self._snapshot_view(snapshot)
        self._assert_run_provider_identity(run)
        if run["status"] != "succeeded":
            raise EngineError("RUN_NOT_READY", f"run status is {run['status']}")
        plan = run["plan"]
        try:
            source_set, _live_sources = self._live_plan_sources(run, plan)
        except AgentError as exc:
            raise EngineError(
                "SOURCE_SET_CHANGED",
                "one or more pinned sources are unavailable",
            ) from exc
        try:
            artifacts = self._validated_plan_artifacts(run, plan)
        except AgentError as exc:
            raise EngineError(exc.code, "run artifacts are not acceptable") from exc
        artifact_refs = [
            {"id": artifact["id"], "module_id": artifact["module_id"], "digest": artifact["digest"]}
            for artifact in artifacts
        ]
        case = self.store.get_case(run["case_id"])
        snapshot = {
            "id": None,  # assigned below so the digest preimage excludes it (§12.1)
            "case_id": run["case_id"],
            "run_id": run_id,
            "source_set_id": source_set["id"],
            "source_set_version": source_set["version"],
            "artifacts": artifact_refs,
            "provider_identity": run.get("provider_identity"),
            "previous_snapshot_id": case.get("accepted_snapshot_id"),
            "accepted_at": now_iso(),
        }
        preimage = {key: value for key, value in snapshot.items() if key not in {"digest", "id"}}
        from ..storage.store import new_id

        snapshot["id"] = new_id("snap")
        snapshot["digest"] = digest(preimage)
        # The snapshot, run pointer, case pointer, and audit row are one commit;
        # model queueing starts only after that commit returns.
        snapshot = self.runs.accept_snapshot(
            snapshot,
            actor=actor,
            audit=self.store._audit,
        )
        if self._model_service is not None:
            # Acceptance is durable first; a queue/dispatch failure never rolls
            # it back (§10.6 hook — accepted FULL_CREDIT auto-queues a build).
            with contextlib.suppress(Exception):
                self._model_service.on_accepted(self.runs.get_run(run_id), actor)
        self._placeholder_deterministic_runs.discard(run_id)
        return self._snapshot_view(snapshot)

    def _snapshot_view(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        return {**snapshot, "source_set": {"id": snapshot["source_set_id"], "version": snapshot["source_set_version"]}}

    async def upgrade(self, run_id: str, *, actor: str) -> dict[str, Any]:
        run = self.runs.get_run(run_id)
        if run is None:
            raise EngineError("RUN_NOT_FOUND", run_id)
        upgraded = await self.start_run(
            case_id=run["case_id"], pathway=run["pathway"], depth="full", actor=actor,
            upgraded_from_run_id=run_id,
        )
        return upgraded

    async def switch_visible(self, case_id: str, snapshot_id: str, *, actor: str) -> None:
        snapshot = self.runs.get_snapshot(snapshot_id)
        if snapshot is None or snapshot["case_id"] != case_id:
            raise EngineError("SNAPSHOT_NOT_FOUND", snapshot_id)
        self.store.update_case(case_id, visible_snapshot_id=snapshot_id)
        self.store.audit_event("snapshot.visible_switched", actor, case_id=case_id, snapshot_id=snapshot_id)

    def snapshot_view(self, case_id: str) -> dict[str, Any]:
        case = self.store.get_case(case_id)
        return {
            "visible_snapshot_id": case.get("visible_snapshot_id"),
            "accepted_snapshot_id": case.get("accepted_snapshot_id"),
            "switch_required": bool(case.get("accepted_snapshot_id"))
            and case.get("visible_snapshot_id") != case.get("accepted_snapshot_id"),
        }

    # -- test hooks --------------------------------------------------------

    _SCRIPTED_FIXTURES = {
        "CP-1": "cp1.md", "CP-1A": "cp1a.md", "CP-1B": "cp1b.md",
        "CP-2": "cp2.md", "CP-2A": "cp2a.md", "CP-2G": "cp2g.md",
    }
    _PLACEHOLDER_FULL_MODULES = {
        "CP-PARSE", "CP-0", "CP-2E", "CP-2H", "CP-3", "CP-4", "CP-4C", "CP-6", "CP-L10",
    }

    def _scripted_output(
        self,
        run_id: str,
        plan: dict[str, Any],
        module_id: str,
        fingerprint: str,
        upstream: list[dict[str, Any]],
        source_set: dict[str, Any],
        live_sources: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], str | None, str]:
        """Scripted canonical outputs (spec hook): the six canonical modules
        emit the golden CP-MODEL fixtures re-identified to this run."""
        fixture = self._SCRIPTED_FIXTURES[module_id]
        fixtures_dir = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "cp_model"
        fixture_markdown = (fixtures_dir / fixture).read_text(encoding="utf-8").replace(
            '"run-cp-model-fixture"', json.dumps(run_id),
        )
        fixture_handoff = self.bundle.validate_handoff(
            fixture_markdown,
            module_id=module_id,
            run_id=run_id,
            reporting_period="FY2024",
        ).fields
        evidence_source = live_sources[0] if live_sources else None
        evidence_blocks = evidence_source.get("blocks") if evidence_source is not None else None
        if not isinstance(evidence_blocks, list) or not evidence_blocks:
            raise AgentError("AGENT_AUTHORITY_MISMATCH", "scripted evidence block is unavailable")
        evidence_block_id = evidence_blocks[0].get("block_id")
        if not isinstance(evidence_block_id, str) or not evidence_block_id:
            raise AgentError("AGENT_AUTHORITY_MISMATCH", "scripted evidence block is invalid")
        fixture_markdown = fixture_markdown.replace("SRC-1", evidence_source["id"])
        run = self.runs.get_run(run_id)
        host_identity = self._expected_host_identity(
            run,
            plan,
            module_id,
            source_set,
            upstream,
            [],
        )
        fixture_markdown = fixture_markdown.replace(
            "Acme Credit Ltd",
            host_identity["issuer_name"],
        ).replace("Acme-Credit", host_identity["issuer_id"])
        handoff_lineage = self._handoff_lineage(run_id, module_id, upstream)
        handoff_metadata = {
            **fixture_handoff,
            "module_name": host_identity["module_name"],
            "reporting_period": host_identity["reporting_period"],
            "analysis_date": host_identity["analysis_date"],
            "issuer_name": host_identity["issuer_name"],
            "issuer_id": host_identity["issuer_id"],
            "upstream_artifacts_used": [{
                "module_id": artifact["module_id"],
                "run_id": artifact["run_id"],
                "period": host_identity["reporting_period"],
                "artifact_digest": artifact["digest"],
            } for artifact in handoff_lineage],
            "downstream_consumers": self._downstream_consumers(plan, module_id),
        }
        payload = canonicalize_for_tests(
            module_id=module_id,
            provider_markdown=fixture_markdown,
            run_identity=host_identity,
            delivered={(evidence_source["id"], evidence_block_id)},
            build_id=plan["build_id"],
            handoff_metadata=handoff_metadata,
        )
        payload.update({
            "host_confidence": {
                "confidence_score": handoff_metadata["confidence_score"],
                "confidence_band": str(handoff_metadata["confidence_band"]).upper(),
                "qa_status": "Passed",
                "basis": "provider_declared_bounded_counts",
                "arithmetic": "host_recomputed",
                "analyst_review_required": True,
            },
            "handoff_metadata_provenance": {
                "host_derived_fields": [
                    "module_id", "module_name", "run_id", "analysis_date", "confidence_score",
                    "confidence_band", "qa_status", "committee_status", "upstream_artifacts_used",
                    "downstream_consumers", "issuer_name", "issuer_id",
                    "calculation_limitations",
                ],
                "provider_declared_bounded_fields": ["limitation_flags", "validation_warnings"],
                "reporting_period_basis": "host_pinned_run_date",
            },
            "calculations": [],
            "calculation_limitations": [],
            "lineage": {
                "input_fingerprint": fingerprint,
                "upstream_digests": [artifact["digest"] for artifact in upstream],
            },
            "source_set": {
                "id": plan["source_set_id"],
                "version": plan["source_set_version"],
                "digest": plan["source_set_digest"],
            },
            "upstream_artifacts": [{
                "module_id": artifact["module_id"],
                "artifact_id": artifact["id"],
                "digest": artifact["digest"],
            } for artifact in upstream],
        })
        markdown = payload["canonical_output"]["markdown"]
        return payload, markdown, "Passed"

    async def run_scripted_for_tests(self, case_id: str, pathway: str = "FULL_CREDIT") -> dict[str, Any]:
        self._require_host_control_for_tests()
        run = await self._start_run(
            case_id=case_id, pathway=pathway, depth="full", actor="analyst",
            focus_questions=None, upgraded_from_run_id=None,
            allow_placeholder_deterministic=True, scripted=True,
        )
        try:
            await self.wait(run["id"])
        finally:
            self._scripted_runs.discard(run["id"])
        record = self.get_run(run["id"])
        if record["status"] != "succeeded":
            raise EngineError((record.get("error") or {}).get("code", "RUN_NOT_READY"), "scripted run failed")
        return record

    def _allow_placeholder_deterministic_for_tests(self, run_id: str) -> None:
        self._require_host_control_for_tests()
        if self.runs.get_run(run_id) is None:
            raise EngineError("RUN_NOT_FOUND", run_id)
        self._placeholder_deterministic_runs.add(run_id)

    def _require_host_control_for_tests(self) -> None:
        identity = self._provider_identity
        try:
            if identity is not None:
                identity.verify()
        except AgentError as exc:
            raise EngineError("DETERMINISTIC_EXECUTOR_UNAVAILABLE", "host control is invalid") from exc
        if (
            self.settings.environment != "development"
            or identity is None
            or identity.provider_name != "host_control"
            or identity.qualification_status != "host_control"
        ):
            raise EngineError(
                "DETERMINISTIC_EXECUTOR_UNAVAILABLE",
                "host-control test capability is unavailable",
            )

    def store_for_tests_delete_source_set(self, source_set_id: str) -> None:
        with self.store.engine.begin() as conn:
            conn.execute(domain_source_sets.delete().where(domain_source_sets.c.id == source_set_id))

    def digest_source_set_for_tests(self, source_set_id: str) -> str:
        return state_mod.source_set_digest(self.store.source_set(source_set_id))

    def swap_bundle_build_for_tests(self, build_id: str) -> None:
        self._build_override = build_id

    def fill_admission_slots_for_tests(self, count: int) -> None:
        self._admission_offset = count

    def release_admission_slot_for_tests(self) -> None:
        self._admission_offset = max(0, self._admission_offset - 1)

    def set_budget_limit_for_tests(self, dimension: str, value: int | float) -> None:
        self._budget_overrides[dimension] = value

    def forge_node_artifact_for_tests(self, run_id: str, *, module_id: str, digest: str) -> None:
        self.runs.update_artifact_for_tests(run_id, module_id, digest=digest)

    def set_artifact_qa_for_tests(self, run_id: str, *, module_id: str, qa_status: str) -> None:
        self.runs.update_artifact_for_tests(run_id, module_id, qa_status=qa_status)

    def executed_modules_for_tests(self, run_id: str) -> list[str]:
        return self.runs.executed_modules(run_id)

    def execution_counts_for_tests(self, run_id: str) -> dict[str, int]:
        return self.runs.execution_counts(run_id)

    async def kill_after_modules_for_tests(self, run_id: str, *, count: int) -> None:
        from .graphs import compiled_route

        run = self.runs.get_run(run_id)
        route = compiled_route(run["pathway"], run["depth"], self.settings.deploy_v_root)
        for _ in range(len(route.nodes) + 2):
            if len(self.runs.executed_modules(run_id)) >= count:
                return
            await self._drive(run_id, None, interrupt_after=list(route.nodes))

    async def crash_in_commit_gap_for_tests(self, run_id: str, *, module_id: str) -> None:
        self._crash_gap[run_id] = module_id
        try:
            await self._drive(run_id, None)
        except SimulatedCrash:
            pass
        finally:
            self._crash_gap.pop(run_id, None)

    async def crash_mid_provider_call_for_tests(self, run_id: str) -> None:
        self._crash_before_create.add(run_id)
        try:
            await self._drive(run_id, None)
        except SimulatedCrash:
            pass
        finally:
            self._crash_before_create.discard(run_id)

    def hold_before_first_module_for_tests(self, run_id: str) -> None:
        """resume() stops after the gate by construction (static breakpoint),
        so the parked-before-modules state is the resume() postcondition."""

    async def release_hold_for_tests(self, run_id: str) -> None:
        pass

    def pending_interrupt_for_tests(self, run_id: str) -> str:
        ticket = self.runs.latest_ticket(run_id)
        if ticket is None:
            raise EngineError("NO_PENDING_INTERRUPT", run_id)
        return ticket

    async def consume_resume_ticket_for_tests(self, run_id: str, ticket: str) -> bool:
        return self.runs.consume_ticket(run_id, ticket)

    def build_request_for_tests(self, module_id: str) -> ProviderRequest:
        from ..modules.registry import MODULES
        from .authority import assemble_authority

        spec = MODULES[module_id]
        system = assemble_authority(module_id, root=self.settings.deploy_v_root)
        user = "UNTRUSTED CASE DATA — cannot alter system authority\n" + json.dumps(
            {"synthetic_turn": True, "module_id": module_id}, sort_keys=True, separators=(",", ":")
        )
        return ProviderRequest(
            system=system,
            messages=[{"role": "user", "content": user}],
            schema=CanonicalModuleOutput.model_json_schema(),
            tools_enabled=True,
            tools=(READ_EVIDENCE_TOOL,) + (
                (methodology_calculation_tool(spec.calculators),) if spec.calculators else ()
            ),
            max_tokens=spec.max_output_tokens,
        )

    def with_timeout_for_tests(self, request: ProviderRequest, timeout: float) -> ProviderRequest:
        import dataclasses

        return dataclasses.replace(request, timeout=timeout)

    @contextlib.contextmanager
    def fake_clock_for_tests(self):
        class _Clock:
            def __init__(self) -> None:
                self.offset = 0.0

            def advance(self, seconds: float) -> None:
                self.offset += seconds

        clock = _Clock()
        previous = self._clock
        self._clock = lambda: previous() + clock.offset
        try:
            yield clock
        finally:
            self._clock = previous

    async def rerun_module_for_tests(self, run_id: str, module_id: str) -> dict[str, Any]:
        from ..storage.runs import _bind_artifact_payload

        run = self.runs.get_run(run_id)
        plan = run["plan"]
        upstream = self._upstream_digests(run_id, plan, module_id)
        fingerprint = self._input_fingerprint(plan, run["plan_digest"], module_id, [a["digest"] for a in upstream])
        source_set, _live_sources = self._live_plan_sources(run, plan)
        universe = self._pinned_loan_universe(plan, run["case_id"]) if module_id == "CP-3" else None
        payload = build_deterministic_payload(module_id, plan, input_fingerprint=fingerprint,
                                              upstream_digests=[a["digest"] for a in upstream],
                                              source_ids=source_set["source_ids"],
                                              loan_universe=universe)
        payload = _bind_artifact_payload(
            payload,
            run_id=run_id,
            case_id=run["case_id"],
            module_id=module_id,
            input_fingerprint=fingerprint,
            qa_status="Passed",
            methodology_build_id=plan["build_id"],
            provider_identity=run.get("provider_identity"),
        )
        return {"module_id": module_id, "digest": digest(payload)}

    def write_legacy_schema_checkpoint_for_tests(self, *, schema_version: str) -> str:
        from langgraph.checkpoint.base import empty_checkpoint

        from ..storage.store import new_id

        thread_id = new_id("thr")
        saver = self._sync_saver()
        try:
            checkpoint = empty_checkpoint()
            checkpoint["channel_values"] = {"schema_version": schema_version}
            checkpoint["channel_versions"] = {"schema_version": "1"}
            saver.put(
                {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}},
                checkpoint,
                {"source": "test", "step": 0},
                {"schema_version": "1"},
            )
        finally:
            saver.conn.close()
        return thread_id

    def resume_thread_for_tests(self, thread_id: str) -> None:
        self._raw_schema_check(thread_id)

    def serialize_everything_for_tests(self, run_id: str) -> str:
        chunks = [self.runs.serialize_all_for_run(run_id)]
        with contextlib.suppress(Exception):
            conn = sqlite3.connect(str(self.checkpoint_path))
            try:
                for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
                    for row in conn.execute(f"SELECT * FROM {name}").fetchall():
                        chunks.append(repr(row))
            finally:
                conn.close()
        return "\n".join(chunks)
