"""Metering-bracket coverage and the finalization deadline (DECISIONS §12.14;
TEST_INVENTORY D1/D2 deferrals). One test per re-hosted contractual row plus
the §12.14 wrapper-coverage test that enumerates the built loop's step table.
"""

from __future__ import annotations

import ast
import inspect
import re
import sys
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parents[1] / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from caos.config import Settings  # noqa: E402
from caos.storage.store import DomainStore  # noqa: E402

from test_module_wiring import ScriptedProvider, _agent_turns, _seed_case  # noqa: E402


async def _start_full_run(tmp_path: Path):
    """A FULL_CREDIT full-depth run parked after the gate, scripted to succeed."""
    from caos.engine.runtime import Engine

    settings = Settings(storage_dir=tmp_path / "vault", agent_execution_enabled=True)
    store = DomainStore.from_url(f"sqlite:///{tmp_path / 'caos.db'}")
    engine = None
    try:
        case, source = _seed_case(store)
        provider = ScriptedProvider(script=_agent_turns(source["id"], modules=10))
        engine = Engine.create(settings=settings, store=store,
                               checkpoint_path=tmp_path / "ck.db", provider=provider)
        run = await engine.start_run_for_tests(
            case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst",
            allow_placeholder_deterministic=True,
        )
        return engine, store, settings, provider, run
    except BaseException:
        try:
            if engine is not None:
                await engine.aclose()
        finally:
            store.close()
        raise


@pytest.fixture
async def full_run(tmp_path):
    resources = await _start_full_run(tmp_path)
    try:
        yield resources
    finally:
        try:
            await resources[0].aclose()
        finally:
            resources[1].close()


def _succeeded_events(engine, run_id: str) -> list[dict]:
    return [e for e in engine.events_after(run_id, 0) if e["event"] == "run.succeeded"]


# --- §12.14 coverage by construction ----------------------------------------------


def test_every_step_in_the_node_sequence_is_wrapped_by_the_timed_bracket():
    """§12.14: one timed() wrapper is the only call site and every step in the
    node sequence — count, create, evidence read, final parse/validate,
    reuse-validation, completion write, final verification — is bracketed."""
    from caos.engine import loop as loop_mod
    from caos.engine.runtime import Engine

    source = inspect.getsource(loop_mod.run_agent_module)
    tree = ast.parse(source)
    bracket_bodies = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and any(
            isinstance(candidate, ast.Call)
            and getattr(candidate.func, "id", None) == "timed"
            for stmt in node.finalbody for candidate in ast.walk(stmt)
        ):
            bracket_bodies.append("\n".join(
                ast.get_source_segment(source, stmt) or "" for stmt in node.body
            ))

    loop_steps = ("provider.count_tokens", "provider.create_message",
                  "read_evidence(", "parse_final_output(")
    for step in loop_steps:
        assert any(step in body for body in bracket_bodies), \
            f"loop step {step!r} is not inside a timed bracket"
    # every provider await goes through _call; none may sit outside a bracket
    assert source.count("await _call(") == sum(body.count("await _call(") for body in bracket_bodies)

    run_module = inspect.getsource(Engine._run_module)
    assert re.search(r"started = self\._clock\(\)\s*\n\s*existing = self\.runs\.find_valid_artifact", run_module) \
        and re.search(r"find_valid_artifact\([^\n]*\)\s*\n\s*self\._charge_active_if_metered", run_module), \
        "reuse-validation segment is not bracketed"
    assert re.search(r"started = self\._clock\(\)\s*\n\s*artifact = self\.runs\.complete_node", run_module) \
        and re.search(r"artifact = self\.runs\.complete_node[^\n]*\n\s*self\._charge_active_if_metered", run_module), \
        "completion-write segment is not bracketed"

    finalize = inspect.getsource(Engine._finalize_node)
    assert "_verify_run_artifacts" in finalize and "_charge_active_if_metered" in finalize \
        and finalize.index("_charge_active_if_metered") < finalize.index("finalize_success"), \
        "final verification is not metered before the success commit"


# --- D1: fake-clock behavior per re-hosted row ------------------------------------


async def test_slow_render_is_charged_before_artifact_completion(full_run, monkeypatch):
    """Re-hosts test_cpdr_slow_render_is_charged_before_artifact_completion:
    post-provider render/validation time crossing the ceiling fails the run
    with no artifact for the module."""
    import caos.engine.runtime as runtime_mod

    engine, store, settings, provider, run = full_run
    real = runtime_mod.canonicalize_for_tests
    with engine.fake_clock_for_tests() as clock:
        def slow_canonicalize(*args, **kwargs):
            clock.advance(16 * 60)  # crosses the 15-minute active ceiling
            return real(*args, **kwargs)

        monkeypatch.setattr(runtime_mod, "canonicalize_for_tests", slow_canonicalize)
        await engine.wait(run["id"])

    record = engine.get_run(run["id"])
    assert record["status"] == "failed"
    assert record["error"]["code"] == "AGENT_BUDGET_EXCEEDED"
    module_id = record["error"]["module_id"]
    assert [a for a in engine.artifacts_for_run(run["id"]) if a["module_id"] == module_id] == [], \
        "an over-ceiling render must never commit its artifact"


async def test_throwing_host_operations_charge_active_time(full_run, monkeypatch):
    """Re-hosts test_cpdr_throwing_host_operations_charge_active_time: a host
    op that throws still charges its elapsed time before the sanitized terminal."""
    import caos.engine.runtime as runtime_mod

    engine, store, settings, provider, run = full_run
    with engine.fake_clock_for_tests() as clock:
        def exploding_confidence(decoded):
            clock.advance(30)
            raise RuntimeError("scorer exploded")

        monkeypatch.setattr(runtime_mod, "recompute_confidence", exploding_confidence)
        await engine.wait(run["id"])

    record = engine.get_run(run["id"])
    assert record["status"] == "failed"
    assert record["error"]["code"] == "CANONICAL_GENERATION_FAILED", "§12.9 collapse rule"
    assert engine.budget_used(run["id"])["active_minutes"] >= 0.5, \
        "the throwing bracket's elapsed time must be charged"


async def test_slow_atomic_completion_crosses_ceiling_and_cannot_succeed(full_run, monkeypatch):
    """Re-hosts test_cpdr_slow_atomic_completion_crosses_ceiling_and_cannot_succeed:
    metered persistence crossing the ceiling ends run and node failed."""
    engine, store, settings, provider, run = full_run
    real_complete = engine.runs.complete_node
    with engine.fake_clock_for_tests() as clock:
        def slow_complete(*args, **kwargs):
            artifact = real_complete(*args, **kwargs)
            clock.advance(16 * 60)
            return artifact

        monkeypatch.setattr(engine.runs, "complete_node", slow_complete)
        await engine.wait(run["id"])

    record = engine.get_run(run["id"])
    assert record["status"] == "failed"
    assert record["error"]["code"] == "AGENT_BUDGET_EXCEEDED"
    module_id = record["error"]["module_id"]
    node = next(n for n in record["nodes"] if n["module_id"] == module_id)
    assert node["status"] == "failed", "an over-ceiling completion must not stand as succeeded"
    assert _succeeded_events(engine, run["id"]) == []


async def test_final_validation_is_charged_before_run_success(full_run, monkeypatch):
    """Re-hosts test_cpdr_no_pending_final_validation_is_charged_before_run_success:
    the pre-success verification segment is metered."""
    engine, store, settings, provider, run = full_run
    real_verify = engine._verify_run_artifacts
    with engine.fake_clock_for_tests() as clock:
        def slow_verify(run_id, plan):
            clock.advance(60)
            return real_verify(run_id, plan)

        monkeypatch.setattr(engine, "_verify_run_artifacts", slow_verify)
        await engine.wait(run["id"])

    record = engine.get_run(run["id"])
    assert record["status"] == "succeeded", record.get("error")
    assert engine.budget_used(run["id"])["active_minutes"] >= 1.0, \
        "final validation before run.succeeded must be charged"


# --- D2: the finalization deadline under a fake clock -----------------------------


async def test_success_commit_that_would_breach_the_ceiling_never_lands(tmp_path, full_run, monkeypatch):
    """Re-hosts test_cpdr_174_plus_ten_second_finalization_never_commits_success:
    durable failed state, no success event, snapshot acceptance refused."""
    from caos.engine.runtime import Engine

    engine, store, settings, provider, run = full_run
    real_verify = engine._verify_run_artifacts
    with engine.fake_clock_for_tests() as clock:
        def breaching_verify(run_id, plan):
            clock.advance(3_600)
            return real_verify(run_id, plan)

        monkeypatch.setattr(engine, "_verify_run_artifacts", breaching_verify)
        await engine.wait(run["id"])

    record = engine.get_run(run["id"])
    assert record["status"] == "failed"
    assert record["error"]["code"] == "AGENT_BUDGET_EXCEEDED"
    assert _succeeded_events(engine, run["id"]) == [], "success must never be emitted"
    with pytest.raises(Exception, match="RUN_NOT_READY"):
        await engine.accept(run["id"], actor="analyst")
    revived = Engine.create(settings=settings, store=store,
                            checkpoint_path=tmp_path / "ck.db", provider=provider)
    try:
        assert revived.get_run(run["id"])["status"] == "failed", "the terminal state is durable"
    finally:
        await revived.aclose()


async def test_within_budget_success_commit_lands_once_inside_the_deadline(tmp_path, full_run, monkeypatch):
    """Re-hosts test_cpdr_two_second_finalization_commits_inside_absolute_deadline:
    a within-budget success commit persists succeeded with exactly one event."""
    from caos.engine.runtime import Engine

    engine, store, settings, provider, run = full_run
    real_verify = engine._verify_run_artifacts
    with engine.fake_clock_for_tests() as clock:
        def two_second_verify(run_id, plan):
            clock.advance(2)
            return real_verify(run_id, plan)

        monkeypatch.setattr(engine, "_verify_run_artifacts", two_second_verify)
        await engine.wait(run["id"])

    assert engine.get_run(run["id"])["status"] == "succeeded"
    revived = Engine.create(settings=settings, store=store,
                            checkpoint_path=tmp_path / "ck.db", provider=provider)
    try:
        assert revived.get_run(run["id"])["status"] == "succeeded"
        assert len(_succeeded_events(revived, run["id"])) == 1, "run.succeeded exactly once"
    finally:
        await revived.aclose()
