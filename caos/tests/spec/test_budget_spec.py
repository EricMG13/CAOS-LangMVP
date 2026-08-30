"""Budget-ceiling specification (invariant 8; DECISIONS §12.D, Appendix A).

Re-hosts the contractual CP-DR budget rows onto the shared agent loop and ledger.
Every ceiling is host-enforced and fails BEFORE overspend; nothing is model-reported.
"""

from __future__ import annotations

import pytest

from spec_helpers import text_message, start_full_credit_run


# --- literal constants (Appendix A: transcription is the only carrier) ------------


def test_manifest_caps_literal():
    from caos.engine import budget

    assert budget.MAX_MANIFEST_BLOCKS == 2_000
    assert budget.MAX_MANIFEST_BYTES == 256 * 1_024
    assert budget.MAX_MANIFEST_FILENAME_CHARS == 255
    assert budget.MAX_MANIFEST_MEDIA_TYPE_CHARS == 160
    assert budget.MAX_MANIFEST_FIELD_CHARS == 160
    assert budget.MAX_MANIFEST_LOCATOR_CHARS == 500
    assert budget.MAX_MANIFEST_LOCATOR_ITEMS == 100
    assert budget.MAX_MANIFEST_LOCATOR_DEPTH == 8
    assert budget.MAX_MANIFEST_LOCATOR_NODES == 500


def test_finalization_allowance_and_provider_constants():
    from caos.engine import budget

    assert budget.FINALIZATION_ALLOWANCE_SECONDS == 5.0
    assert budget.PROVIDER_TIMEOUT_SECONDS == 150.0
    assert budget.PROVIDER_CONCURRENCY_SLOTS == 2
    assert budget.MAX_ACTIVE_JOBS == 20
    assert budget.REPAIR_TEXT_LIMIT == 1_500


def test_registry_output_caps_literal():
    from caos.modules.registry import MODULES

    caps = {m: MODULES[m].max_output_tokens for m in MODULES if MODULES[m].mode_full == "agent"}
    assert caps == {
        "CP-1": 32_000, "CP-1A": 12_000, "CP-1B": 12_000, "CP-2": 16_000,
        "CP-2A": 16_000, "CP-2G": 24_000, "CP-1C": 12_000, "CP-1D": 12_000, "CP-5": 24_000,
    }


# --- the envelope is a pure function of (route, registry) (§12.20) ----------------


def test_route_envelopes_scale_per_module_and_reproduce_legacy_at_n6():
    from caos.engine.budget import route_envelope
    from caos.modules.registry import MODULES

    legacy_six = ["CP-1", "CP-1A", "CP-1B", "CP-2", "CP-2A", "CP-2G"]
    env = route_envelope(legacy_six, MODULES)
    assert env["evidence_reads"] == 60
    assert env["evidence_bytes"] == 5 * 1024 * 1024
    assert env["input_tokens"] == 500_000
    assert env["output_tokens"] == (32_000 + 12_000 + 12_000 + 16_000 + 16_000 + 24_000) + 32_000, "Σ caps + max (repair headroom)"
    assert env["turns"] == 60 + 6 + 1
    assert env["active_minutes"] == 15 and env["provider_retries"] == 1 and env["repairs"] == 1

    earnings = ["CP-1", "CP-1B", "CP-2", "CP-5"]
    env4 = route_envelope(earnings, MODULES)
    assert env4["evidence_reads"] == 40
    assert env4["turns"] == 40 + 4 + 1
    assert env4["output_tokens"] == (32_000 + 12_000 + 16_000 + 24_000) + 32_000


# --- reservation protocol (§12.12) ------------------------------------------------


async def test_no_provider_call_without_a_successful_reservation(engine, store, provider):
    """Rejected reservation is terminal budget failure with ZERO model calls."""
    engine.set_budget_limit_for_tests("input_tokens", 1)  # any counted request over-reserves
    case, source, run = await start_full_credit_run(engine, store)
    await engine.wait(run["id"])
    record = engine.get_run(run["id"])
    assert record["status"] == "failed"
    assert record["error"]["code"] == "AGENT_BUDGET_EXCEEDED"
    assert provider.create_requests == [], "reservation failure must precede any provider call"


async def test_unresolved_inflight_reservation_fails_closed_on_resume_without_respend(tmp_path, settings, store, provider):
    from caos.engine.runtime import Engine

    engine = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "ck.db", provider=provider)
    case, source, run = await start_full_credit_run(engine, store)
    await engine.crash_mid_provider_call_for_tests(run["id"])  # inflight digest persisted, never reconciled
    calls_before = len(provider.create_requests)

    revived = Engine.create(settings=settings, store=store, checkpoint_path=tmp_path / "ck.db", provider=provider)
    await revived.recover()
    await revived.wait(run["id"])
    record = revived.get_run(run["id"])
    assert record["status"] == "failed" and record["error"]["code"] == "AGENT_BUDGET_EXCEEDED"
    assert len(provider.create_requests) == calls_before, "no re-spend after crash with unknown spend"


async def test_timeout_retry_must_be_byte_identical_and_single(engine, store, provider):
    from caos.engine.loop import reservation_digest

    one = engine.build_request_for_tests("CP-1")
    again = engine.build_request_for_tests("CP-1")
    assert reservation_digest(one) == reservation_digest(again), "two builds of one turn are byte-identical"
    assert reservation_digest(one) == reservation_digest(engine.with_timeout_for_tests(one, 10.0)), "timeout is outside the digest"


def test_count_tokens_never_charges_a_turn():
    from caos.engine.budget import BudgetLedger

    ledger = BudgetLedger.for_tests(turns=3)
    ledger.note_count_tokens()
    ledger.note_count_tokens()
    assert ledger.used("turns") == 0, "turns charge on create only (legacy provider.py:326 vs :344)"


# --- ceilings fail before overspend (re-hosted CP-DR rows) ------------------------


@pytest.mark.parametrize("dimension", ["turns", "evidence_reads", "evidence_bytes", "input_tokens", "output_tokens", "active_minutes"])
def test_each_ceiling_refuses_the_next_operation_before_overspend(dimension):
    from caos.engine.budget import BudgetLedger

    ledger = BudgetLedger.for_tests(**{dimension: 1})
    ledger.exhaust_for_tests(dimension)
    with pytest.raises(Exception, match="AGENT_BUDGET_EXCEEDED"):
        ledger.reserve_next_operation(dimension)
    assert ledger.used(dimension) <= ledger.limit(dimension), "refusal must precede spend, never after"


def test_manifest_bounding_fails_closed_before_provider_contact(store, provider):
    from caos.engine.budget import bound_manifest

    oversized = [{"source_id": f"s{i}", "filename": "f.txt", "media_type": "text/plain",
                  "sha256": "a" * 64, "blocks": []} for i in range(2_001)]
    with pytest.raises(Exception, match="AGENT_BUDGET_EXCEEDED"):
        bound_manifest(oversized)
    assert provider.create_requests == []


def test_manifest_exact_boundaries_are_allowed_inclusive():
    from caos.engine import budget
    from caos.engine.budget import bound_manifest

    at_cap = [{"source_id": f"s{i}", "filename": "f.txt", "media_type": "text/plain",
               "sha256": "a" * 64, "blocks": []} for i in range(budget.MAX_MANIFEST_BLOCKS)]
    bound_manifest(at_cap)  # must not raise: ceilings are inclusive


def test_locator_bounding_rejects_structural_bombs_and_nonfinite_floats():
    from caos.engine.budget import locator_is_bounded

    assert locator_is_bounded({"line": 1})
    assert not locator_is_bounded({"a": [["x"] * 101]})
    deep = value = {}
    for _ in range(9):
        value["k"] = {}
        value = value["k"]
    assert not locator_is_bounded(deep)
    assert not locator_is_bounded({"f": float("nan")})


# --- usage integrity (§12.17) -----------------------------------------------------


@pytest.mark.parametrize("usage", [None, {"input_tokens": 0, "output_tokens": 0}, {"input_tokens": -1, "output_tokens": 5}, {"input_tokens": 2.5, "output_tokens": 5}])
def test_malformed_or_zero_usage_is_output_invalid_with_reservation_unresolved(usage):
    from caos.engine.loop import validate_usage

    with pytest.raises(Exception, match="AGENT_OUTPUT_INVALID"):
        validate_usage(usage)


# --- active time (§12.14) ---------------------------------------------------------


async def test_gate_wait_accrues_zero_active_time_while_compute_is_charged(engine, store):
    """Re-hosts test_cpdr_approval_wait_is_excluded_while_planning_time_is_charged onto the entry gate."""
    case = store.create_case("Gate", "Issuer", "Services", "analyst")
    with engine.fake_clock_for_tests() as clock:
        run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst")
        clock.advance(3_600)  # an hour parked at the interrupt
        used = engine.budget_used(run["id"])
        assert used["active_minutes"] == 0, "wall-clock at a human gate must accrue nothing"


async def test_max_tokens_truncation_fails_module_immediately_without_consuming_repair(engine, store, provider):
    provider.script = [text_message("truncated…", stop_reason="max_tokens")]
    case, source, run = await start_full_credit_run(engine, store)
    await engine.wait(run["id"])
    record = engine.get_run(run["id"])
    assert record["status"] == "failed"
    assert engine.budget_used(run["id"])["repairs"] == 0, "truncation must not consume the shared repair (§10.11)"


def test_provider_concurrency_denial_is_typed_and_reserves_nothing():
    from caos.engine.loop import ProviderSlots

    slots = ProviderSlots(2)
    assert slots.try_acquire() and slots.try_acquire()
    with pytest.raises(Exception, match="AGENT_BUDGET_EXCEEDED"):
        slots.acquire_or_deny()


# --- attempt recorder (§12.11, Appendix A) ---------------------------------------


def test_attempt_recorder_allowlist_truncation_and_asymmetric_caps():
    from caos.engine.budget import AttemptRecorder

    recorder = AttemptRecorder.for_tests()
    recorder.record("generation", note="x" * 500, structured={"not": "allowed"}, ok=True)
    row = recorder.rows()[-1]
    assert row["note"] == "x" * 200, "strings truncate to 200"
    assert "structured" not in row, "non-scalar values are dropped"
    for _ in range(99):
        recorder.record("generation")
    with pytest.raises(Exception, match="AGENT_BUDGET_EXCEEDED"):
        recorder.record("generation")  # non-terminal fails closed at 100
    recorder.record("terminal", terminal_code="AGENT_BUDGET_EXCEEDED")  # terminal is cap-exempt
    assert recorder.rows()[-1]["terminal_code"] == "AGENT_BUDGET_EXCEEDED"
    assert len(recorder.rows()) == 100, "terminal appends into the [-100:] ring"


async def test_secret_bearing_provider_failure_never_persists_secret_or_evidence_text(engine, store, provider):
    """Re-hosts test_cpdr_failure_metadata_does_not_persist_secret_body_prompt_or_evidence."""
    secret = "sk-ant-SECRET-VALUE-99"

    def explode(request):
        raise RuntimeError(f"provider error body containing {secret}")

    provider.script = [explode]
    case, source, run = await start_full_credit_run(engine, store)
    await engine.wait(run["id"])
    serialized = engine.serialize_everything_for_tests(run["id"])
    assert secret not in serialized
    assert "pinned evidence line" not in serialized, "evidence text never persists in failure metadata"
    record = engine.get_run(run["id"])
    assert record["error"]["code"] == "CANONICAL_GENERATION_FAILED", "run-level collapse rule (§12.9)"


def test_reconcile_commits_the_actual_usage_before_it_refuses_the_overage(tmp_path):
    """§12.12: the true-up is the ledger's record of what the provider actually
    billed. Raising inside the store transaction rolled it back on exactly the
    path where it matters, leaving the reservation on the books and the request
    in flight forever."""
    import sqlalchemy as sa

    from caos.storage.runs import RunStore, StoreConflict

    store = RunStore(sa.create_engine(f"sqlite:///{tmp_path / 'runs.db'}"))
    run_id = store.create_run("case-1", "FULL_CREDIT", "full", "analyst")["id"]
    store.init_budget(run_id, {"turns": 10, "input_tokens": 1_000, "output_tokens": 1_000})
    store.reserve_provider(run_id, "digest-1", 100, 100, retry=False)

    with pytest.raises(StoreConflict, match="AGENT_BUDGET_EXCEEDED"):
        store.reconcile_provider(run_id, "digest-1", 100, 100, 100, 5_000)

    budget = store.get_budget(run_id)
    assert budget["used"]["output_tokens"] == 5_000, "the ledger records what was actually spent"
    assert budget["inflight_request_digest"] is None, "the request is resolved, not stranded in flight"
    with pytest.raises(StoreConflict, match="AGENT_BUDGET_EXCEEDED"):
        store.reserve_provider(run_id, "digest-2", 1, 1, retry=False)
