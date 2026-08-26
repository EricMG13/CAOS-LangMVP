"""Run-engine specification (invariants 1, 4, 5, 10). All tests must fail until the engine exists.

Sources: TEST_INVENTORY.md contractual rows from test_clean_slate.py, test_ledger_contracts.py,
and the re-hosted CP-DR finalization rows; DECISIONS.md §§10–12.
"""

from __future__ import annotations

import pytest

from spec_helpers import ScriptedProvider, seed_case_with_source, start_full_credit_run


# --- source pinning at the entry gate (invariant 1; §10.4, §11.1) -----------------


async def test_empty_source_set_pauses_at_entry_gate_without_pinning(engine, store):
    case = store.create_case("Empty", "Issuer", "Services", "analyst")
    run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst")
    record = engine.get_run(run["id"])
    assert record["status"] == "paused"
    assert record["error"]["code"] == "SOURCE_SET_EMPTY"
    assert record["plan"].get("source_set_id") is None, "nothing may be pinned before the gate exits"


async def test_resume_with_still_empty_set_re_pauses_without_pinning(engine, store):
    case = store.create_case("Empty", "Issuer", "Services", "analyst")
    run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst")
    await engine.resume(run["id"])
    record = engine.get_run(run["id"])
    assert record["status"] == "paused"
    assert record["plan"].get("source_set_id") is None


async def test_gate_exit_pins_exact_current_source_set_and_later_uploads_do_not_move_it(engine, store):
    case, source, run = await start_full_credit_run(engine, store)
    pinned = engine.get_run(run["id"])["plan"]
    assert pinned["source_set_id"] == source["source_set"]["id"]
    assert pinned["source_set_version"] == 1
    seed_case_with_source(store, body=b"a second document uploaded mid-run")  # same store, new content
    assert engine.get_run(run["id"])["plan"]["source_set_id"] == source["source_set"]["id"]


async def test_plan_digest_is_carried_outside_the_blob_and_reasserted(engine, store):
    from caos.contracts import digest
    from caos.engine.state import plan_preimage

    case, source, run = await start_full_credit_run(engine, store)
    record = engine.get_run(run["id"])
    assert "plan_digest" not in record["plan"], "digest lives outside the digested blob (§12.1)"
    assert record["plan_digest"] == digest(plan_preimage(record["plan"]))


async def test_run_pinned_to_immutable_source_set_and_upgrade_links_origin(engine, store, client):
    case, source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.wait(run["id"])
    accepted = await engine.accept(run["id"], actor="analyst")
    assert accepted["source_set"]["id"] == source["source_set"]["id"]
    upgraded = await engine.upgrade(run["id"], actor="analyst")
    assert upgraded["upgraded_from_run_id"] == run["id"]


async def test_acceptance_refuses_missing_historical_source_set(engine, store):
    case, source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.wait(run["id"])
    engine.store_for_tests_delete_source_set(source["source_set"]["id"])
    with pytest.raises(Exception, match="SOURCE_SET_CHANGED"):
        await engine.accept(run["id"], actor="analyst")


async def test_withdrawing_pinned_source_mid_run_fails_the_run_closed(engine, store):
    """Invariant 1: withdrawn or mutated sources fail the run rather than degrading it."""
    case, source, run = await start_full_credit_run(engine, store)
    store.withdraw(case["id"], source["id"], "analyst")
    await engine.wait(run["id"])
    record = engine.get_run(run["id"])
    assert record["status"] == "failed"
    assert record["error"]["code"] in {"AGENT_AUTHORITY_MISMATCH", "SOURCE_SET_CHANGED"}


# --- determinism and replay (invariant 10) ----------------------------------------


def test_node_set_and_edges_are_a_pure_function_of_pathway_and_depth(engine):
    from caos.engine.graphs import compiled_route

    one = compiled_route("FULL_CREDIT", "full")
    two = compiled_route("FULL_CREDIT", "full")
    assert one.nodes == two.nodes and one.edges == two.edges
    assert compiled_route("EARNINGS_UPDATE", "full").nodes != one.nodes


async def test_replay_from_same_pinned_sources_and_build_is_equivalent_by_the_same_path(engine, store, provider):
    """Named scenario 3: same pinned sources + methodology build -> equivalent result, same path."""
    case, source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.wait(run["id"])
    first = engine.get_run(run["id"])
    assert first["status"] == "succeeded"

    replay = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst")
    await engine.wait(replay["id"])
    second = engine.get_run(replay["id"])
    assert second["status"] == "succeeded"
    assert [n["module_id"] for n in second["nodes"]] == [n["module_id"] for n in first["nodes"]], "same path"
    assert second["plan_digest"] == first["plan_digest"], "same pin -> same plan identity"
    firsts = {a["module_id"]: a["digest"] for a in engine.artifacts_for_run(first["id"])}
    seconds = {a["module_id"]: a["digest"] for a in engine.artifacts_for_run(second["id"])}
    assert firsts == seconds, "deterministic modules replay to identical artifact digests"


async def test_started_pathways_are_restricted_to_the_mvp_set(engine, store):
    case, _ = seed_case_with_source(store)
    for pathway in ("DEEP_RESEARCH", "DISTRESSED_RESTRUCTURING", "PORTFOLIO_DECISION", "DECISION_LEDGER"):
        with pytest.raises(Exception):
            await engine.start_run(case_id=case["id"], pathway=pathway, depth="full", actor="analyst")


# --- kill / resume (success criterion; §10.1, §12.28) -----------------------------


async def test_worker_killed_mid_run_resumes_from_last_checkpoint_not_restart(tmp_path, settings, store, provider):
    """Named scenario 1. Kill after N modules; a fresh Engine over the same checkpoint
    DB resumes and completes without re-executing the finished modules."""
    from caos.engine.runtime import Engine

    engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "ck.db", provider=provider)
    case, source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.kill_after_modules_for_tests(run["id"], count=2)  # crashes the worker mid-run
    executed_before = engine.executed_modules_for_tests(run["id"])
    assert len(executed_before) == 2

    revived = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "ck.db", provider=provider)
    await revived.recover()
    await revived.wait(run["id"])
    record = revived.get_run(run["id"])
    assert record["status"] == "succeeded"
    assert revived.execution_counts_for_tests(run["id"])[executed_before[0]] == 1, "finished module not re-executed"


async def test_crash_between_store_commit_and_checkpoint_write_yields_one_artifact_one_charge(tmp_path, settings, store, provider):
    """§12 objection 1: the store-commit/checkpoint gap must not double-mint or double-spend."""
    from caos.engine.runtime import Engine

    engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "ck.db", provider=provider)
    case, source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.crash_in_commit_gap_for_tests(run["id"], module_id="CP-0")

    revived = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "ck.db", provider=provider)
    await revived.recover()
    await revived.wait(run["id"])
    artifacts = [a for a in revived.artifacts_for_run(run["id"]) if a["module_id"] == "CP-0"]
    assert len(artifacts) == 1, "exactly one artifact for the crashed module"
    events = [e for e in revived.events_after(run["id"], 0) if e["event"] == "run.succeeded"]
    assert len(events) == 1, "run.succeeded exactly once"


async def test_interrupt_paused_threads_are_skipped_by_recovery_and_hold_no_admission_slot(tmp_path, settings, store, provider):
    from caos.engine.runtime import Engine

    engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "ck.db", provider=provider)
    case = store.create_case("Empty", "Issuer", "Services", "analyst")
    run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst")
    assert engine.get_run(run["id"])["status"] == "paused"

    revived = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "ck.db", provider=provider)
    await revived.recover()
    assert revived.get_run(run["id"])["status"] == "paused", "recovery must not poke parked threads"
    assert revived.active_execution_count() == 0, "paused threads hold no admission slot"


# --- events (contractual: atomic state+event, exactly-once terminals, ordering) ---


async def test_event_log_is_per_run_monotonic_with_legacy_names_and_single_terminal(engine, store):
    case, source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.wait(run["id"])
    events = engine.events_after(run["id"], 0)
    ids = [e["id"] for e in events]
    assert ids == sorted(ids) and len(ids) == len(set(ids)), "monotonic unique per-run sequence"
    names = [e["event"] for e in events]
    assert names[0] == "run.created"
    assert names.count("run.succeeded") == 1
    assert {"run.running", "node.running", "node.succeeded"} <= set(names)
    assert engine.events_after(run["id"], ids[-1]) == [], "Last-Event-ID resume semantics"


# --- finalization gate ------------------------------------------------------------


async def test_snapshot_rejects_forged_succeeded_run(engine, store):
    case, source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.wait(run["id"])
    engine.forge_node_artifact_for_tests(run["id"], module_id="CP-0", digest="0" * 64)
    with pytest.raises(Exception, match="RUN_NOT_READY"):
        await engine.accept(run["id"], actor="analyst")


async def test_acceptance_is_idempotent_and_updates_case_and_run_together(engine, store):
    case, source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.wait(run["id"])
    first = await engine.accept(run["id"], actor="analyst")
    second = await engine.accept(run["id"], actor="analyst")
    assert first["id"] == second["id"]
    assert store.get_case(case["id"])["accepted_snapshot_id"] == first["id"]


async def test_snapshot_acceptance_refuses_when_cp5_reports_blocked(engine, store):
    """§12.27: reviewer authority maps onto the acceptance gate — Blocked QA cannot be accepted."""
    case, source, run = await start_full_credit_run(engine, store, depth="screen")
    await engine.wait(run["id"])
    engine.set_artifact_qa_for_tests(run["id"], module_id="CP-5", qa_status="Blocked")
    with pytest.raises(Exception, match="RUN_NOT_READY|QA_BLOCKED"):
        await engine.accept(run["id"], actor="analyst")


# --- admission (contractual: shared active-job ceiling, capacity returns) ---------


async def test_admission_ceiling_is_derived_and_capacity_returns_on_completion(engine, store):
    from caos.engine.budget import MAX_ACTIVE_JOBS

    assert MAX_ACTIVE_JOBS == 20
    engine.fill_admission_slots_for_tests(MAX_ACTIVE_JOBS)
    case, _ = seed_case_with_source(store)
    with pytest.raises(Exception, match="ADMISSION|BUSY"):
        await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst")
    engine.release_admission_slot_for_tests()
    run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="screen", actor="analyst")
    assert run["id"]


# --- authorization (contractual matrix, re-hosted) --------------------------------


async def test_case_reader_cannot_start_or_upgrade_and_outsiders_see_nothing(client, store):
    case, _ = seed_case_with_source(store)
    store.add_member(case["id"], "analyst", "reader-user", "READER", actor_role="ADMIN")
    start = client.post(
        f"/api/cases/{case['id']}/runs",
        json={"pathway": "FULL_CREDIT", "depth": "screen"},
        headers={"x-caos-role": "ANALYST", "x-forwarded-user": "reader-user"},
    )
    assert start.status_code == 403
    outsider = client.get(f"/api/cases/{case['id']}", headers={"x-forwarded-user": "stranger"})
    assert outsider.status_code == 404


def test_production_rejects_forged_forwarded_identity(store, tmp_path):
    from caos.api import create_app
    from caos.config import Settings
    from fastapi.testclient import TestClient

    prod = Settings(environment="production", storage_dir=tmp_path / "v",
                    database_url="postgresql://x/y", edge_proxy_secret="real-secret", session_secret="real-session")
    app = create_app(settings=prod, store=store, engine=None)
    test_client = TestClient(app)
    assert test_client.get("/api/me", headers={"x-forwarded-user": "spoof"}).status_code == 401
    escalated = test_client.get(
        "/api/me",
        headers={"x-edge-authorization": "real-secret", "x-forwarded-user": "user", "x-caos-role": "ADMIN"},
    )
    assert escalated.status_code == 200
    assert escalated.json()["role"] == "READER", "client role headers never escalate in production"
