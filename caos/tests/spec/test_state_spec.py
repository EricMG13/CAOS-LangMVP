"""Checkpoint-state discipline specification (invariants 3, 6, 10; DECISIONS §12.A, §12.E)."""

from __future__ import annotations

import pytest


def test_run_state_fields_are_json_native_and_round_trip_identically():
    """§12.2: channel values are plain data; serde round-trip preserves equality AND type."""
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    from caos.engine.state import example_state_for_tests

    serde = JsonPlusSerializer()
    state = example_state_for_tests()

    def assert_plain(value, path="state"):
        assert not isinstance(value, tuple), f"{path}: tuples do not survive the serde"
        if isinstance(value, dict):
            for key, item in value.items():
                assert_plain(item, f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                assert_plain(item, f"{path}[{index}]")
        else:
            assert value is None or isinstance(value, (str, int, float, bool)), f"{path}: {type(value)} is not JSON-native"

    assert_plain(state)
    revived = serde.loads_typed(serde.dumps_typed(state))
    assert revived == state
    assert type(revived) is type(state)


def test_plan_blob_is_frozen_and_digest_reassertion_catches_mutation():
    from caos.engine.state import assert_plan_integrity, pin_plan

    pinned = pin_plan({"build_id": "b", "nodes": [], "pathway": "FULL_CREDIT", "depth": "full",
                       "source_set_id": "set-1", "source_set_version": 1})
    assert_plan_integrity(pinned["plan"], pinned["plan_digest"])  # passes untouched
    tampered = dict(pinned["plan"])
    tampered["source_set_id"] = "set-2"
    with pytest.raises(Exception, match="AGENT_AUTHORITY_MISMATCH|plan"):
        assert_plan_integrity(tampered, pinned["plan_digest"])


@pytest.mark.parametrize("bad", ["issuer \ud800 name", "nul\x00byte"])
def test_unicode_boundary_rejects_unencodable_pinned_strings(bad):
    """§12.3: serde replaces surrogates and Postgres jsonb rejects them — ban at the boundary."""
    from caos.engine.state import validate_boundary_text

    with pytest.raises(Exception):
        validate_boundary_text(bad)


def test_focus_questions_reject_surrogates_at_the_api_contract(client, store):
    from spec_helpers import seed_case_with_source

    case, _ = seed_case_with_source(store)
    response = client.post(
        f"/api/cases/{case['id']}/runs",
        json={"pathway": "FULL_CREDIT", "depth": "full", "focus_questions": ["what about \ud800?"]},
    )
    assert response.status_code == 422


def test_checkpointed_digests_are_expectations_not_authority(engine, store):
    """§11.2: consumers re-read the store record by id and recompute; mismatch is typed failure."""
    from caos.engine.state import verify_source_set_expectation

    from spec_helpers import seed_case_with_source

    case, source = seed_case_with_source(store)
    pinned_digest = engine.digest_source_set_for_tests(source["source_set"]["id"])
    verify_source_set_expectation(store, source["source_set"]["id"], pinned_digest)  # live record matches
    with pytest.raises(Exception, match="AGENT_AUTHORITY_MISMATCH|SOURCE_SET"):
        verify_source_set_expectation(store, source["source_set"]["id"], "0" * 64)


def test_schema_version_is_checked_at_the_raw_layer_before_coercion(tmp_path, settings, store, provider):
    """§12.24: a mismatched stamp fails closed before Pydantic fills defaults or drops fields."""
    from caos.engine.runtime import Engine, StateSchemaMismatch

    engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "ck.db", provider=provider)
    thread_id = engine.write_legacy_schema_checkpoint_for_tests(schema_version="caos-state-v0")
    with pytest.raises(StateSchemaMismatch):
        engine.resume_thread_for_tests(thread_id)


def test_single_time_authority_survives_a_day_boundary(engine, store):
    """§12.4: all artifact dates are slices of the pinned created_at; a resume across midnight
    reproduces identical digests."""
    import asyncio

    from spec_helpers import start_full_credit_run

    async def scenario():
        case, source, run = await start_full_credit_run(engine, store, depth="screen")
        await engine.wait(run["id"])
        first = {a["module_id"]: a["digest"] for a in engine.artifacts_for_run(run["id"])}
        with engine.fake_clock_for_tests() as clock:
            clock.advance(86_400 + 3_600)
            replay = await engine.rerun_module_for_tests(run["id"], "CP-0")
        assert replay["digest"] == first["CP-0"], "artifact content never reads the wall clock"

    asyncio.run(scenario())


def test_resume_ticket_makes_racing_resumes_single_effect(tmp_path, settings, store, provider):
    """§12.21: langgraph 1.2.11 executes BOTH racing resumes (proven empirically) — the
    store-side one-shot ticket must make the second a no-op."""
    import asyncio

    from caos.engine.runtime import Engine

    engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "ck.db", provider=provider)
    case = store.create_case("Gate", "Issuer", "Services", "analyst")

    async def scenario():
        run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst")
        ticket = engine.pending_interrupt_for_tests(run["id"])
        first, second = await asyncio.gather(
            engine.consume_resume_ticket_for_tests(run["id"], ticket),
            engine.consume_resume_ticket_for_tests(run["id"], ticket),
            return_exceptions=True,
        )
        outcomes = {bool(first is True), bool(second is True)}
        assert outcomes == {True, False}, "exactly one racer consumes the ticket"

    asyncio.run(scenario())


def test_stale_or_late_resume_returns_typed_not_applied(client, engine, store):
    """§12.22: a silent no-op resume must never surface as success."""
    from spec_helpers import seed_case_with_source

    case, source = seed_case_with_source(store)
    response = client.post("/api/runs/run-never-existed/resume", json={})
    assert response.status_code in {404, 409}
    if response.status_code == 409:
        assert response.json()["detail"]["code"] == "RESUME_NOT_APPLIED"
