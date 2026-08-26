"""read_evidence boundary specification (invariants 1, 2; §12.9–§12.11).

Re-hosts the contractual evidence rows from test_ledger_contracts.py and the CP-DR
runtime file onto the nine agent modules' shared evidence tool.
"""

from __future__ import annotations

import pytest

from spec_helpers import seed_case_with_source


@pytest.fixture()
def evidence_context(engine, store):
    """A pinned run context and the read_evidence host boundary under test."""
    import asyncio

    from caos.engine.evidence import EvidenceReader

    case, source = seed_case_with_source(store)
    run = asyncio.get_event_loop().run_until_complete(
        engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst")
    )
    pinned = engine.get_run(run["id"])["plan"]
    reader = EvidenceReader(store=store, case_id=case["id"], source_set_id=pinned["source_set_id"], run_id=run["id"])
    return case, source, run, reader


def test_read_outside_pinned_source_set_fails_closed(evidence_context, store):
    """Named scenario 2 (first half)."""
    case, source, run, reader = evidence_context
    foreign_case, foreign_source = seed_case_with_source(store, body=b"foreign case evidence")
    with pytest.raises(Exception, match="AGENT_AUTHORITY_MISMATCH"):
        reader.read(foreign_source["id"], ["b00001"])


def test_read_of_source_withdrawn_after_pin_fails_closed(evidence_context, store):
    """Named scenario 2 (second half): valid at pin time, withdrawn since — the check is live."""
    case, source, run, reader = evidence_context
    store.withdraw(case["id"], source["id"], "analyst")
    with pytest.raises(Exception, match="AGENT_AUTHORITY_MISMATCH"):
        reader.read(source["id"], ["b00001"])


async def test_withdrawal_while_parked_at_interrupt_is_banned_on_resume(engine, store):
    """§11.3/§12: no checkpointed value encodes withdrawal — every resume re-runs live checks."""
    import hashlib

    case = store.create_case("Gate", "Issuer", "Services", "analyst")
    run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst")
    assert engine.get_run(run["id"])["status"] == "paused"
    body = b"uploaded while the run waits at the gate"
    source = store.ingest({
        "case_id": case["id"], "filename": "late.txt", "media_type": "text/plain",
        "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "vault_path": None,
        "blocks": [{"block_id": "b00001", "locator": {"line": 1}, "text": body.decode(), "extractor_version": "builtin-v1", "confidence": "MEDIUM", "untrusted_data": True}],
        "withdrawn": False,
    }, "analyst")
    engine.hold_before_first_module_for_tests(run["id"])  # resume pins, then parks before module execution
    await engine.resume(run["id"])
    store.withdraw(case["id"], source["id"], "analyst")
    await engine.release_hold_for_tests(run["id"])
    await engine.wait(run["id"])
    record = engine.get_run(run["id"])
    assert record["status"] == "failed", "a source withdrawn after pinning must fail the run closed"
    assert record["error"]["code"] in {"AGENT_AUTHORITY_MISMATCH", "SOURCE_SET_CHANGED"}


def test_unknown_block_is_output_invalid_and_authority_precedes_existence(evidence_context, store):
    """§12.9: withdrawn/foreign source is never blamed on the model — code precedence is pinned."""
    case, source, run, reader = evidence_context
    with pytest.raises(Exception, match="AGENT_OUTPUT_INVALID"):
        reader.read(source["id"], ["no-such-block"])
    store.withdraw(case["id"], source["id"], "analyst")
    with pytest.raises(Exception, match="AGENT_AUTHORITY_MISMATCH"):
        reader.read(source["id"], ["no-such-block"])  # withdrawn + bogus block -> authority code wins


def test_duplicate_block_ids_are_rejected(evidence_context):
    case, source, run, reader = evidence_context
    with pytest.raises(Exception, match="AGENT_OUTPUT_INVALID"):
        reader.read(source["id"], ["b00001", "b00001"])


@pytest.mark.parametrize("block_ids", [[], [f"b{i:05d}" for i in range(1, 52)]])
def test_block_id_count_bounds_are_enforced(evidence_context, block_ids):
    case, source, run, reader = evidence_context
    with pytest.raises(Exception):
        reader.read(source["id"], block_ids)


def test_returned_rows_carry_provenance_and_the_delivered_set_is_the_citation_contract(evidence_context):
    """§12.10: ledger charge -> returned-set update -> return is one ordered unit."""
    case, source, run, reader = evidence_context
    rows = reader.read(source["id"], ["b00001"])
    assert rows[0]["source_id"] == source["id"]
    assert set(rows[0]) >= {"source_id", "source_digest", "block_id", "locator", "extractor_version", "confidence", "text"}
    assert reader.delivered() == {(source["id"], "b00001")}


def test_ceiling_rejected_read_leaves_no_citation_expectation(evidence_context):
    case, source, run, reader = evidence_context
    reader.exhaust_read_budget_for_tests()
    with pytest.raises(Exception, match="AGENT_BUDGET_EXCEEDED"):
        reader.read(source["id"], ["b00001"])
    assert reader.delivered() == set(), "rejected read must not create an expectation"


def test_evidence_bytes_measure_is_the_tool_result_serialization(evidence_context):
    """§12 Appendix A: the byte ceiling counts len(json.dumps(result, sort_keys=True)) —
    the identical serialization sent to the model as the tool_result."""
    import json

    from caos.engine.evidence import evidence_payload_bytes, render_tool_result

    case, source, run, reader = evidence_context
    rows = reader.read(source["id"], ["b00001"])
    assert evidence_payload_bytes(rows) == len(render_tool_result(rows))
    assert render_tool_result(rows) == json.dumps(rows, sort_keys=True)


def test_forged_citation_outside_delivered_set_is_rejected_at_canonicalization(engine, store):
    from caos.methodology.canonical import CanonicalValidationError, validate_citations

    with pytest.raises(CanonicalValidationError):
        validate_citations(
            declared=[{"source_id": "FORGED-SOURCE", "block_id": "b00001"}],
            delivered=set(),
        )
