"""read_evidence boundary specification (invariants 1, 2; §12.9–§12.11).

Re-hosts the contractual evidence rows from test_ledger_contracts.py and the CP-DR
runtime file onto the nine agent modules' shared evidence tool.
"""

from __future__ import annotations

import json

import pytest

from spec_helpers import seed_case_with_source


@pytest.fixture()
def evidence_context(engine, store):
    """A pinned run context and the read_evidence host boundary under test."""
    import asyncio

    from caos.engine.evidence import EvidenceReader

    case, source = seed_case_with_source(store)
    run = asyncio.run(
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


# --- the argument-shape matrix (invariant 2) --------------------------------------
#
# read_evidence is the only tool a module can call, so every shape a module can
# put on the wire is enumerated here and proved to fail closed with a typed
# refusal that returns no text — not in the rows, not in the exception, not in
# the delivered set.

# Each marker leads its body on purpose: a leak that truncates (the codebase
# bounds diagnostic text at 200 chars in several places) still carries the head
# of the text, so a substring search for the marker still trips. Moving a marker
# to the tail of a longer body would silently weaken every scenario below.
PINNED_TEXT = "PINNED-EVIDENCE-MARKER-9f3a net leverage 3.4x"
FOREIGN_TEXT = "FOREIGN-EVIDENCE-MARKER-71bd restricted payments basket"
OUT_OF_SET_TEXT = "OUTOFSET-EVIDENCE-MARKER-c204 restated covenant pack"
MARKERS = ("PINNED-EVIDENCE-MARKER-9f3a", "FOREIGN-EVIDENCE-MARKER-71bd",
           "OUTOFSET-EVIDENCE-MARKER-c204")


def _ingest_text(store, case_id: str, text: str, *, filename: str = "later.txt",
                 source_id: str | None = None):
    import hashlib

    body = text.encode("utf-8")
    payload = {
        "case_id": case_id, "filename": filename, "media_type": "text/plain",
        "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "vault_path": None,
        "blocks": [{"block_id": "b00001", "locator": {"line": 1}, "text": text,
                    "extractor_version": "builtin-v1", "confidence": "MEDIUM", "untrusted_data": True},
                   {"block_id": "b00002", "locator": {"line": 2}, "text": text,
                    "extractor_version": "builtin-v1", "confidence": "MEDIUM", "untrusted_data": True}],
        "withdrawn": False,
    }
    if source_id is not None:
        payload["id"] = source_id
    return store.ingest(payload, "analyst")


@pytest.fixture()
def evidence_lab(engine, store):
    """A pinned run whose evidence carries a unique marker, plus a reader factory."""
    import asyncio
    from types import SimpleNamespace

    from caos.engine.evidence import EvidenceReader

    case, source = seed_case_with_source(store, body=PINNED_TEXT.encode())
    run = asyncio.run(
        engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst")
    )
    plan = engine.get_run(run["id"])["plan"]

    def make_reader(**overrides):
        return EvidenceReader(store=store, case_id=case["id"], source_set_id=plan["source_set_id"],
                              run_id=run["id"], **overrides)

    return SimpleNamespace(case=case, source=source, run=run, plan=plan,
                           make_reader=make_reader, store=store)


def _refusal(lab, scenario: str):
    """One refusal class: (reader, (source_id, block_ids), expected code)."""
    source_id = lab.source["id"]
    reader = lab.make_reader()
    match scenario:
        case "read_ceiling":
            reader.exhaust_read_budget_for_tests()
            return reader, (source_id, ["b00001"]), "AGENT_BUDGET_EXCEEDED"
        case "byte_ceiling":
            return lab.make_reader(byte_limit=1), (source_id, ["b00001"]), "AGENT_BUDGET_EXCEEDED"
        case "absent_block":
            return reader, (source_id, ["b99999"]), "AGENT_OUTPUT_INVALID"
        case "duplicate_blocks":
            return reader, (source_id, ["b00001", "b00001"]), "AGENT_OUTPUT_INVALID"
        case "empty_block_list":
            return reader, (source_id, []), "AGENT_OUTPUT_INVALID"
        case "too_many_blocks":
            return reader, (source_id, [f"b{i:05d}" for i in range(1, 52)]), "AGENT_OUTPUT_INVALID"
        case "block_ids_not_a_list":
            return reader, (source_id, "b00001"), "AGENT_OUTPUT_INVALID"
        case "block_ids_is_a_dict":
            return reader, (source_id, {"block_id": "b00001"}), "AGENT_OUTPUT_INVALID"
        case "block_ids_is_null":
            return reader, (source_id, None), "AGENT_OUTPUT_INVALID"
        case "block_id_is_an_int":
            return reader, (source_id, [1]), "AGENT_OUTPUT_INVALID"
        case "block_id_is_a_float":
            return reader, (source_id, [1.0]), "AGENT_OUTPUT_INVALID"
        case "block_id_is_null":
            return reader, (source_id, [None]), "AGENT_OUTPUT_INVALID"
        case "block_id_is_a_bool":
            return reader, (source_id, [True]), "AGENT_OUTPUT_INVALID"
        case "block_id_is_an_array":
            return reader, (source_id, [["b00001"]]), "AGENT_OUTPUT_INVALID"
        case "block_id_is_bytes":
            return reader, (source_id, [b"b00001"]), "AGENT_OUTPUT_INVALID"
        case "source_id_is_an_int":
            return reader, (1, ["b00001"]), "AGENT_OUTPUT_INVALID"
        case "source_id_is_a_float":
            return reader, (1.5, ["b00001"]), "AGENT_OUTPUT_INVALID"
        case "source_id_is_null":
            return reader, (None, ["b00001"]), "AGENT_OUTPUT_INVALID"
        case "source_id_is_an_array":
            return reader, ([source_id], ["b00001"]), "AGENT_OUTPUT_INVALID"
        case "source_id_is_a_dict":
            return reader, ({"id": source_id}, ["b00001"]), "AGENT_OUTPUT_INVALID"
        case "source_id_is_a_bool":
            return reader, (True, ["b00001"]), "AGENT_OUTPUT_INVALID"
        case "source_id_is_bytes":
            return reader, (source_id.encode(), ["b00001"]), "AGENT_OUTPUT_INVALID"
        case "foreign_case":
            _, foreign = seed_case_with_source(lab.store, body=FOREIGN_TEXT.encode())
            return reader, (foreign["id"], ["b00001"]), "AGENT_AUTHORITY_MISMATCH"
        case "withdrawn":
            lab.store.withdraw(lab.case["id"], lab.source["id"], "analyst")
            return reader, (source_id, ["b00001"]), "AGENT_AUTHORITY_MISMATCH"
        case "outside_pinned_set":
            later = _ingest_text(lab.store, lab.case["id"], OUT_OF_SET_TEXT)
            return reader, (later["id"], ["b00001"]), "AGENT_AUTHORITY_MISMATCH"
        case "block_id_of_another_source":
            # b00002 exists in the later source, never in the pinned one; block
            # ids are per-source counters (`b00001`…) and collide across sources,
            # so identity is the (source_id, block_id) PAIR or nothing.
            _ingest_text(lab.store, lab.case["id"], OUT_OF_SET_TEXT)
            return reader, (source_id, ["b00002"]), "AGENT_OUTPUT_INVALID"
        case "empty_source_id":
            return reader, ("", ["b00001"]), "AGENT_AUTHORITY_MISMATCH"
        case "empty_block_id":
            return reader, (source_id, [""]), "AGENT_OUTPUT_INVALID"
        case "unknown_source_id":
            return reader, ("src-doesnotexist00000", ["b00001"]), "AGENT_AUTHORITY_MISMATCH"
        case "lone_surrogate_source_id":
            return reader, ("\ud800" + source_id, ["b00001"]), "AGENT_AUTHORITY_MISMATCH"
        case "lone_surrogate_block_id":
            return reader, (source_id, ["\ud800b00001"]), "AGENT_OUTPUT_INVALID"
        case "oversized_source_id":
            return reader, ("s" * 1_000_000, ["b00001"]), "AGENT_AUTHORITY_MISMATCH"
        case "oversized_block_id":
            return reader, (source_id, ["b" * 1_000_000]), "AGENT_OUTPUT_INVALID"
    raise AssertionError(f"unknown scenario: {scenario}")


REFUSAL_SCENARIOS = [
    "read_ceiling", "byte_ceiling", "absent_block", "duplicate_blocks", "empty_block_list",
    "too_many_blocks", "block_ids_not_a_list", "block_ids_is_a_dict", "block_ids_is_null",
    "block_id_is_an_int", "block_id_is_a_float", "block_id_is_null", "block_id_is_a_bool",
    "block_id_is_an_array", "block_id_is_bytes", "source_id_is_an_int", "source_id_is_a_float",
    "source_id_is_null", "source_id_is_an_array", "source_id_is_a_dict", "source_id_is_a_bool",
    "source_id_is_bytes", "foreign_case", "withdrawn", "outside_pinned_set",
    "block_id_of_another_source", "empty_source_id", "empty_block_id",
    "unknown_source_id", "lone_surrogate_source_id",
    "lone_surrogate_block_id", "oversized_source_id", "oversized_block_id",
]


def test_the_scenario_list_covers_every_shape_the_helper_knows():
    """The parametrize list and `_refusal`'s arms are parallel structures; a
    `case` added to one and forgotten in the other is a shape that silently
    stops being tested. This is the only thing keeping them honest."""
    import inspect
    import re

    arms = set(re.findall(r'case "([a-z_]+)"', inspect.getsource(_refusal)))
    assert arms == set(REFUSAL_SCENARIOS)


@pytest.mark.parametrize("scenario", REFUSAL_SCENARIOS)
def test_every_argument_shape_fails_closed_with_a_typed_refusal(evidence_lab, scenario):
    """§12.9: every refusal carries the pinned taxonomy code — never an untyped
    escape, never a partial delivery."""
    from caos.engine.provider import AgentError

    reader, (source_id, block_ids), expected = _refusal(evidence_lab, scenario)
    with pytest.raises(AgentError) as caught:
        reader.read(source_id, block_ids)
    assert caught.value.code == expected


@pytest.mark.parametrize("scenario", REFUSAL_SCENARIOS)
def test_no_refusal_leaks_evidence_text_or_leaves_a_citation_expectation(evidence_lab, scenario):
    """Invariant 2, read literally: on refusal NO text comes back — not as rows,
    not in the exception message, not in its args, not through a chained cause's
    string, and not as a delivered-set expectation a later citation could claim."""
    import traceback

    from caos.engine.provider import AgentError

    reader, (source_id, block_ids), _ = _refusal(evidence_lab, scenario)
    charged = (reader.reads_used, reader.bytes_used)
    with pytest.raises(AgentError) as caught:
        reader.read(source_id, block_ids)

    rendered = "".join(traceback.format_exception(caught.value)) + repr(caught.value.args)
    for marker in MARKERS:
        assert marker not in rendered, f"{scenario}: refusal leaked source text"
    assert reader.delivered() == set(), f"{scenario}: refused read left a citation expectation"
    assert reader.delivered_rows() == {}
    assert (reader.reads_used, reader.bytes_used) == charged, f"{scenario}: refused read charged the ledger"


def test_a_block_id_that_collides_across_sources_reads_only_the_named_source(evidence_lab):
    """Block ids are per-source counters, so `b00001` exists in every source.
    Identity is the (source_id, block_id) pair: naming the pinned source can
    never reach another source's block of the same name."""
    later = _ingest_text(evidence_lab.store, evidence_lab.case["id"], OUT_OF_SET_TEXT)
    assert later["blocks"][0]["block_id"] == "b00001", "the collision this test guards must exist"

    rows = evidence_lab.make_reader().read(evidence_lab.source["id"], ["b00001"])
    assert rows[0]["text"] == PINNED_TEXT
    assert OUT_OF_SET_TEXT not in rows[0]["text"]
    assert rows[0]["source_id"] == evidence_lab.source["id"]


# --- the tool-argument gate ahead of the reader (loop._evidence_call) -------------


@pytest.mark.parametrize("arguments", [
    {"source_id": "src-pinned000000001"},                                      # block_ids absent
    {"block_ids": ["b00001"]},                                                 # source_id absent
    {"source_id": "src-pinned000000001", "block_ids": ["b00001"], "limit": 5},  # undeclared field
    {"source_id": "src-pinned000000001", "block_ids": ["b00001"], "web": "https://x"},
    {},
    {"source_id": 1, "block_ids": ["b00001"]},
    {"source_id": None, "block_ids": ["b00001"]},
    {"source_id": "src-pinned000000001", "block_ids": "b00001"},
    {"source_id": "src-pinned000000001", "block_ids": None},
    {"source_id": "src-pinned000000001", "block_ids": [1]},
    {"source_id": "src-pinned000000001", "block_ids": [None]},
    "not-a-dict",
    None,
    ["src-pinned000000001", ["b00001"]],
])
def test_tool_arguments_off_the_declared_two_field_shape_are_refused(arguments):
    """The loop gate is the first boundary a tool call meets; anything off the
    strict {source_id, block_ids} shape never reaches the reader."""
    from caos.engine.loop import _evidence_call
    from caos.engine.provider import AgentError, ProviderBlock

    block = ProviderBlock(type="tool_use", id="tool-1", name="read_evidence", input=arguments)
    with pytest.raises(AgentError) as caught:
        _evidence_call(block)
    assert caught.value.code == "AGENT_OUTPUT_INVALID"


def test_duplicate_tool_argument_keys_are_refused_not_collapsed():
    """A tool-call argument object is host-parsed on the OpenRouter binding, so
    the §12.9 duplicate-key rule that governs the final output governs it too:
    `{"source_id": A, ..., "source_id": B}` must be refused, never silently
    last-wins into a read the model's own first claim did not ask for."""
    from caos.engine.openrouter import OpenRouterProvider
    from caos.engine.provider import AgentError

    duplicated = ('{"source_id": "src-pinned000000001", "block_ids": ["b00001"], '
                  '"source_id": "src-foreign00000001"}')
    message = {"tool_calls": [{"id": "call-1", "function": {"name": "read_evidence",
                                                            "arguments": duplicated}}]}
    with pytest.raises(AgentError) as caught:
        OpenRouterProvider._blocks(message)
    assert caught.value.code == "AGENT_OUTPUT_INVALID"


# --- the other side of the read path: bounding the call count --------------------


class LoopingReadProvider:
    """Never volunteers a final answer — reads evidence for as long as it is let."""

    def __init__(self, source_id: str, block_id: str = "b00001", count: int = 1_000) -> None:
        self.source_id = source_id
        self.block_id = block_id
        self.count = count
        self.turns = 0

    def count_tokens(self, request) -> int:
        return self.count

    def create_message(self, request):
        from spec_helpers import tool_call_message

        self.turns += 1
        return tool_call_message(self.source_id, [self.block_id])


async def test_an_unbounded_read_loop_is_stopped_by_the_run_evidence_read_ceiling(
    tmp_path, settings, store,
):
    """A module cannot stall the run by reading forever: the run-wide
    evidence_reads ceiling refuses read N+1 and the run fails closed."""
    from caos.engine.runtime import Engine

    case, source = seed_case_with_source(store, body=PINNED_TEXT.encode())
    provider = LoopingReadProvider(source["id"])
    engine = Engine.create(settings=settings, store=store,
                           checkpoint_path=tmp_path / "checkpoints.db", provider=provider)
    run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst")
    await engine.wait(run["id"])

    record = engine.get_run(run["id"])
    assert record["status"] == "failed"
    # The blamed module is derived, not named: which node holds the looping
    # provider is a property of the compiled route, and pinning it here would
    # turn a catalog change into a failure of this boundary test.
    assert set(record["error"]) == {"code", "module_id"}
    assert record["error"]["code"] == "AGENT_BUDGET_EXCEEDED"
    blamed = record["error"]["module_id"]
    failed = {node["module_id"]: node for node in record["nodes"] if node.get("status") == "failed"}
    assert blamed in failed, "a module is blamed, not the graph boundary"
    assert failed[blamed]["error"]["code"] == "AGENT_BUDGET_EXCEEDED"

    # The bound is run-wide, not per-node: the reader a node is handed is sized
    # `limits - used`, so the looping module drinks the whole run's allowance and
    # is refused at read N+1. Nothing per-node caps it short of that.
    budget = engine.runs.get_budget(run["id"])
    ceiling = budget["limits"]["evidence_reads"]
    assert ceiling > 0
    assert provider.turns > ceiling, "the module really did loop"
    assert budget["used"]["evidence_reads"] == ceiling, "the ceiling is exact, never overspent"
    assert budget["used"]["turns"] <= budget["limits"]["turns"]


class OneBadReadProvider:
    """Reads one source the host must refuse, then would keep going forever."""

    def __init__(self, source_id: str) -> None:
        self.source_id = source_id
        self.create_requests: list = []

    def count_tokens(self, request) -> int:
        return 1_000

    def create_message(self, request):
        from spec_helpers import tool_call_message

        self.create_requests.append(request)
        return tool_call_message(self.source_id, ["b00001"])


async def test_a_refused_read_ends_the_module_instead_of_returning_a_reason_to_the_model(
    tmp_path, settings, store,
):
    """The structural half of invariant 2: a refusal is not a tool_result. The
    model is never handed the refusal — not the code, not a reason, not text —
    so a failing read cannot be retried in a loop either."""
    from caos.engine.runtime import Engine

    case, _ = seed_case_with_source(store, body=PINNED_TEXT.encode())
    outsider_id = "src-postpinoutsider01"
    provider = OneBadReadProvider(outsider_id)
    engine = Engine.create(settings=settings, store=store,
                           checkpoint_path=tmp_path / "checkpoints.db", provider=provider)
    run = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst")
    # Ingested after gate exit: live, same case, outside the pinned set.
    _ingest_text(store, case["id"], OUT_OF_SET_TEXT, source_id=outsider_id)
    await engine.wait(run["id"])

    record = engine.get_run(run["id"])
    assert record["status"] == "failed"
    assert record["error"]["code"] == "AGENT_AUTHORITY_MISMATCH"

    # Nothing the host ever put on the wire is a tool_result: a refused read is
    # not answered, it ends the module. That is what makes "no text" total —
    # there is no channel left to carry text, a code, or a reason — and it is
    # also why a failing read cannot be looped.
    for request in provider.create_requests:
        for message in request.messages:
            content = message.get("content")
            blocks = content if isinstance(content, list) else []
            assert not [b for b in blocks if isinstance(b, dict) and b.get("type") == "tool_result"]

    sent = json.dumps([request.messages for request in provider.create_requests], default=str)
    assert "OUTOFSET-EVIDENCE-MARKER-c204" not in sent
    assert "AGENT_AUTHORITY_MISMATCH" not in sent, "the refusal reason never reaches the model"
    assert engine.runs.get_budget(run["id"])["used"]["evidence_reads"] == 0


def test_the_run_error_surface_carries_a_code_and_never_a_message(evidence_lab, engine):
    """A refusal's reason must not reach an operator surface carrying content
    either: the persisted run error is {code, module_id} and nothing else."""
    engine.runs.finalize_failure(evidence_lab.run["id"], "AGENT_AUTHORITY_MISMATCH", "CP-1")
    error = engine.get_run(evidence_lab.run["id"])["error"]
    assert set(error) == {"code", "module_id"}
    assert error["code"] == "AGENT_AUTHORITY_MISMATCH"


def test_a_ledger_refused_read_leaves_no_expectation_even_though_rows_were_built(evidence_lab):
    """§12.10 ordered unit — the half the in-process guard hides.

    The per-node reader is sized `limits - used` at node entry, so sibling agent
    nodes in one superstep each believe the whole remaining allowance is theirs.
    Whichever loses the race passes its local guard and is refused by the
    run-wide ledger instead, with the rows already materialized. That refusal
    must still deliver nothing and expect nothing.
    """
    from caos.engine.provider import AgentError

    def ledger_full(source_id, block_ids, returned_bytes):
        raise AgentError("AGENT_BUDGET_EXCEEDED", "evidence_reads budget exhausted")

    reader = evidence_lab.make_reader(on_read=ledger_full)
    with pytest.raises(AgentError) as caught:
        reader.read(evidence_lab.source["id"], ["b00001"])

    assert caught.value.code == "AGENT_BUDGET_EXCEEDED"
    assert reader.delivered() == set(), "a ledger-refused read left a citation expectation"
    assert reader.delivered_rows() == {}
