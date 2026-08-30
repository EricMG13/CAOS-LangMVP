"""Checkpoint-state discipline specification (invariants 3, 6, 10; DECISIONS §12.A, §12.E)."""

from __future__ import annotations

import unicodedata

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


def test_case_and_note_text_is_boundary_validated_at_the_api_contract(client):
    """§12.3 applies to every string that reaches pinned state, not only focus
    questions: case identity and a promotable note body are both pinned and both
    ride into audit events. A control byte is refused and NFC folding happens
    before the row is written, so one issuer cannot mint two lineages."""
    control = client.post("/api/cases", content=r'{"name":"a\u0007b","issuer":"I","sector":"S"}',
                          headers={"content-type": "application/json"})
    assert control.status_code == 422

    case = client.post("/api/cases", json={"name": "N", "issuer": "I", "sector": "S"})
    assert case.status_code == 201
    note = client.post(f"/api/cases/{case.json()['id']}/notes",
                       content=r'{"body":"a\u0007b"}',
                       headers={"content-type": "application/json"})
    assert note.status_code == 422

    decomposed = client.post("/api/cases", json={"name": "N", "issuer": "Cafe\u0301", "sector": "S"})
    composed = client.post("/api/cases", json={"name": "N", "issuer": "Caf\u00e9", "sector": "S"})
    assert decomposed.json()["issuer"] == composed.json()["issuer"]

    # Normalization runs BEFORE the length bound. U+0958 is a composition
    # exclusion that folds to two code points, so folding after max_length would
    # store 320 characters in a field declared at 160.
    expanding = "\u0958"
    assert len(unicodedata.normalize("NFC", expanding)) == 2, "fixture no longer expands under NFC"
    # The validator runs BEFORE coercion, so it must cover every shape pydantic
    # will turn into a string. bytes is one: guarding on isinstance(str) alone let
    # a control byte and an unnormalized form in through a door the after-form shut.
    from caos.contracts import CreateCaseRequest

    with pytest.raises(Exception):
        CreateCaseRequest(name=b"a\x07b", issuer="I")
    assert CreateCaseRequest(name="Cafe\u0301".encode(), issuer="I").name == "Caf\u00e9"

    over = client.post("/api/cases", json={"name": expanding * 160, "issuer": "I", "sector": "S"})
    assert over.status_code == 422
    under = client.post("/api/cases", json={"name": expanding * 80, "issuer": "I", "sector": "S"})
    assert under.status_code == 201 and len(under.json()["name"]) == 160


def test_focus_questions_reject_surrogates_at_the_api_contract(client, store):
    import json

    from spec_helpers import seed_case_with_source

    case, _ = seed_case_with_source(store)
    # Pre-encoded body: httpx cannot UTF-8-encode a raw lone surrogate, so the
    # character rides the wire as the JSON escape \ud800 — valid ASCII JSON that
    # the server decodes back into the lone surrogate before the boundary check,
    # which is the contract under test. (Repaired 2026-08-27, user-approved; the
    # original `json=` form failed client-side in httpx and never reached the API.)
    body = json.dumps(
        {"pathway": "FULL_CREDIT", "depth": "full", "focus_questions": ["what about \ud800?"]},
        ensure_ascii=True,
    ).encode("ascii")
    response = client.post(
        f"/api/cases/{case['id']}/runs", content=body,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
    assert "\ud800" not in response.text and "\\ud800" not in response.text, \
        "rejected input must not be echoed back through the response encoder"


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


# --- boundary text on every string that enters pinned state (§12.3) ----------------


@pytest.mark.parametrize("field,payload", [
    ("narrative text", "control \x00 byte"),
    ("heading text", "control \x0b byte"),
    ("citation claim", "control \x1f byte"),
])
def test_deliverable_block_text_is_boundary_validated(field, payload):
    """A control byte in draft text used to reach the append-only revision and only
    fail later, inside the XLSX render — a 500 on a freeze that can never succeed."""
    import pydantic

    from caos.contracts import EvidenceCitation, HeadingBlock, NarrativeBlock

    with pytest.raises(pydantic.ValidationError):
        if field == "narrative text":
            NarrativeBlock(block_id="b", slot_id="section.01", kind="NARRATIVE",
                           text=payload, content_mode="ANALYST_JUDGMENT", citations=[])
        elif field == "heading text":
            HeadingBlock(block_id="b", slot_id="section.01", kind="HEADING", text=payload)
        else:
            EvidenceCitation(source_id="src-1", block_ids=["b00001"], claim=payload)


def test_deliverable_narrative_text_is_nfc_normalized_before_it_is_digested():
    """Two spellings of one string must not mint two lineages: the revision digest
    is taken over this text, so normalization has to happen at the boundary."""
    import unicodedata

    from caos.contracts import NarrativeBlock

    nfc = unicodedata.normalize("NFC", "Café exposure")
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfc != nfd, "premise: the two spellings differ before validation"
    block = NarrativeBlock(block_id="b", slot_id="section.01", kind="NARRATIVE",
                           text=nfd, content_mode="ANALYST_JUDGMENT", citations=[])
    assert block.text == nfc


def test_bidi_override_characters_are_refused_but_rtl_text_is_not():
    """CVE-2021-42574: an embedding/override/isolate control reorders how text
    DISPLAYS without changing a byte, so a narrative can render one way to the
    approver binding its preview digest and another to whoever reads the filed
    PDF. Directional marks stay legal — Arabic and Hebrew issuer names need them."""
    from caos.contracts import validate_boundary_text

    for legitimate in ("Northstar Holdings", "شركة النور",
                       "בנק ‎2026"):
        assert validate_boundary_text(legitimate) == legitimate
    for override in ("‪", "‫", "‬", "‭", "‮",
                     "⁦", "⁧", "⁨", "⁩"):
        with pytest.raises(ValueError, match="bidirectional"):
            validate_boundary_text(f"leverage 3.0x{override}")
