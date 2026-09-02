from __future__ import annotations

import hashlib
import json

import pytest

from caos.config import Settings
from caos.contracts import digest
from caos.engine.provider import (
    AgentError,
    ProviderBlock,
    ProviderMessage,
    ProviderUsage,
    host_control_identity,
)
from caos.engine.runtime import Engine, _parse_calculation_input, _validate_calculation_refs
from caos.storage.store import DomainStore

from calculator_fixtures import VALID_CALCULATION_INPUTS

_VALID_CALCULATION_INPUTS = VALID_CALCULATION_INPUTS


@pytest.mark.parametrize(
    "input_json",
    ('{"x":1,"x":2}', '{"x":NaN}', "[]"),
)
def test_calculation_input_parser_rejects_non_strict_json(input_json: str):
    with pytest.raises(AgentError) as excinfo:
        _parse_calculation_input({"calculator_id": "credit_metrics", "input_json": input_json})

    assert excinfo.value.code == "METHODOLOGY_INPUT_INVALID"


def test_provider_cannot_claim_an_undelivered_or_duplicate_calculation():
    record = {
        "calculator_id": "credit_metrics",
        "script_digest": "a" * 64,
        "calculator_digest": "b" * 64,
        "input_digest": "c" * 64,
        "output_digest": "d" * 64,
    }

    with pytest.raises(ValueError, match="do not match"):
        _validate_calculation_refs(
            [{**record, "output_digest": "e" * 64}], [record], ("credit_metrics",),
        )
    with pytest.raises(ValueError, match="do not match"):
        _validate_calculation_refs([record, record], [record], ("credit_metrics",))
    second_input = {**record, "input_digest": "e" * 64, "output_digest": "f" * 64}
    with pytest.raises(ValueError, match="do not match"):
        _validate_calculation_refs(
            [record, second_input], [record, second_input], ("credit_metrics",),
        )
    with pytest.raises(ValueError, match="do not match"):
        _validate_calculation_refs([], [], ("credit_metrics",))


class CalculationRouteProvider:
    def __init__(
        self,
        source_id: str,
        block_id: str,
        *,
        model_source_id: str | None = None,
        omit_model_source: bool = False,
        source_gate: str = "pass",
        calculation_inputs: dict[str, dict] | None = None,
        retry_inputs: dict[str, dict] | None = None,
        limitation_flags: list[str] | None = None,
    ) -> None:
        self.limitation_flags = list(limitation_flags or [])
        self.identity = host_control_identity()
        self.source_id = source_id
        self.block_id = block_id
        self.model_source_id = model_source_id
        self.omit_model_source = omit_model_source
        self.source_gate = source_gate
        self.calculation_inputs = calculation_inputs or {}
        # After an incomplete result, retry the calculator once with these
        # inputs; without an entry the double finalizes with the gap declared.
        self.retry_inputs = retry_inputs or {}
        self.retried: list[str] = []
        self.incomplete_results: list[dict] = []
        self.create_requests = []

    def count_tokens(self, _request) -> int:
        return 1

    def create_message(self, request):
        self.create_requests.append(request)
        tool_results = [
            json.loads(block["content"])
            for message in request.messages
            if isinstance(message.get("content"), list)
            for block in message["content"]
            if isinstance(block, dict) and block.get("type") == "tool_result"
        ]
        calculation_tool = next(
            (tool for tool in request.effective_tools()
             if tool["name"] == "run_methodology_calculation"),
            None,
        )
        if not tool_results:
            return self._tool_call(
                "read_evidence",
                {"source_id": self.source_id, "block_ids": [self.block_id]},
            )
        results = [
            result for result in tool_results
            if isinstance(result, dict) and isinstance(result.get("calculator_id"), str)
        ]
        calculations = [record for record in results if "output_digest" in record]
        incomplete = [record for record in results if "output_digest" not in record]
        for record in incomplete:
            if record not in self.incomplete_results:
                self.incomplete_results.append(record)
        assigned = (
            calculation_tool["input_schema"]["properties"]["calculator_id"]["enum"]
            if calculation_tool is not None else []
        )
        attempted = {record["calculator_id"] for record in results}
        remaining = [calculator_id for calculator_id in assigned if calculator_id not in attempted]
        retry = next(
            (record["calculator_id"] for record in incomplete
             if record["calculator_id"] in self.retry_inputs
             and record["calculator_id"] not in self.retried),
            None,
        )
        if retry is not None:
            self.retried.append(retry)
            return self._tool_call(
                "run_methodology_calculation",
                {"calculator_id": retry, "input_json": json.dumps(self.retry_inputs[retry])},
            )
        if remaining:
            calculator_id = remaining[0]
            return self._tool_call(
                "run_methodology_calculation",
                {
                    "calculator_id": calculator_id,
                    "input_json": json.dumps(self.calculation_inputs.get(
                        calculator_id,
                        _VALID_CALCULATION_INPUTS[calculator_id],
                    )),
                },
            )

        refs = [
            {field: record[field] for field in (
                "calculator_id", "script_digest", "calculator_digest", "input_digest", "output_digest",
            )}
            for record in calculations
        ]
        sections = [
            f"## {heading}\n\nVerified"
            for heading in (
                "Audit Summary", "Analysis", "Evidence Trace", "Source Registry",
                "Gaps & Conflicts", "QA Validation",
            )
        ]
        if not self.omit_model_source:
            sections[1] += (
                "\n\n| source_id | value |\n| --- | --- |\n"
                f"| {self.model_source_id or self.source_id} | analysed |"
            )
        body = {
            "markdown": "\n\n".join(sections),
            "evidence_refs": [{"source_id": self.source_id, "block_id": self.block_id}],
            "calculation_refs": refs,
            "lineage_counts": {"directly_sourced": 1},
            "fields_present": 1,
            "fields_total": 1,
            "source_gate": self.source_gate,
            "limitation_flags": self.limitation_flags,
        }
        return ProviderMessage(
            content=[ProviderBlock(type="text", text=json.dumps(body))],
            stop_reason="end_turn",
            usage=ProviderUsage(input_tokens=1, output_tokens=1),
            request_id=f"final-{len(self.create_requests)}",
            observed_model="deterministic",
        )

    def _tool_call(self, name: str, arguments: dict[str, object]) -> ProviderMessage:
        return ProviderMessage(
            content=[ProviderBlock(
                type="tool_use",
                id=f"tool-{len(self.create_requests)}",
                name=name,
                input=arguments,
            )],
            stop_reason="tool_use",
            usage=ProviderUsage(input_tokens=1, output_tokens=1),
            request_id=f"tool-{len(self.create_requests)}",
            observed_model="deterministic",
        )


async def test_ordinary_earnings_path_persists_pinned_host_calculations(tmp_path):
    store = DomainStore.from_url(f"sqlite:///{tmp_path / 'caos.db'}")
    engine = None
    try:
        case = store.create_case("Earnings", "Issuer", "Services", "analyst")
        body = b"uploaded annual and quarterly evidence"
        source = store.ingest({
            "case_id": case["id"],
            "filename": "issuer-update.txt",
            "media_type": "text/plain",
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
            "vault_path": None,
            "blocks": [{
                "block_id": "b00001",
                "locator": {"line": 1},
                "text": body.decode(),
                "extractor_version": "builtin-v1",
                "confidence": "MEDIUM",
                "untrusted_data": True,
            }],
            "withdrawn": False,
        }, "analyst")
        provider = CalculationRouteProvider(source["id"], "b00001")
        engine = Engine.create(
            settings=Settings(storage_dir=tmp_path / "vault", agent_execution_enabled=True),
            store=store,
            checkpoint_path=tmp_path / "checkpoints.db",
            provider=provider,
        )

        started = await engine.start_run(
            case_id=case["id"],
            pathway="EARNINGS_UPDATE",
            depth="full",
            actor="analyst",
        )
        completed = await engine.wait(started["id"])

        assert completed["status"] == "succeeded", completed.get("error")
        artifacts = {row["module_id"]: row for row in engine.artifacts_for_run(started["id"])}
        assert set(artifacts) == {"CP-PARSE", "CP-0", "CP-1", "CP-1B", "CP-2", "CP-5"}
        for module_id in ("CP-1", "CP-1B"):
            calculations = artifacts[module_id]["payload"]["calculations"]
            assert [record["calculator_id"] for record in calculations] == ["credit_metrics"]
            assert calculations[0]["module_id"] == module_id
            assert calculations[0]["methodology_build_id"] == completed["plan"]["build_id"]
            assert calculations[0]["input_digest"] == digest(calculations[0]["canonical_input"])
            assert calculations[0]["output_digest"] == digest(calculations[0]["canonical_output"])
        assert all("calculations" in artifact["payload"] for artifact in artifacts.values())
        assert all(
            artifact["payload"]["host_confidence"] | {
                "basis": "provider_declared_bounded_counts",
                "arithmetic": "host_recomputed",
                "analyst_review_required": True,
            } == artifact["payload"]["host_confidence"]
            for artifact in artifacts.values()
        )
        calculation_attempts = [
            row for row in engine.runs.get_budget(started["id"])["attempts"]
            if row["kind"] == "calculation"
        ]
        assert {(row["module_id"], row["calculator_id"]) for row in calculation_attempts} == {
            ("CP-1", "credit_metrics"),
            ("CP-1B", "credit_metrics"),
        }
        assert all(len(row["output_digest"]) == 64 for row in calculation_attempts)
    finally:
        if engine is not None:
            await engine.aclose()
        store.close()


def _seed(store, name: str, body: bytes):
    case = store.create_case(name, "Issuer", "Services", "analyst")
    source = store.ingest({
        "case_id": case["id"], "filename": "issuer.txt", "media_type": "text/plain",
        "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "vault_path": None,
        "blocks": [{
            "block_id": "b00001", "locator": {"line": 1}, "text": body.decode(),
            "extractor_version": "builtin-v1", "confidence": "MEDIUM", "untrusted_data": True,
        }],
        "withdrawn": False,
    }, "analyst")
    return case, source


async def test_incomplete_non_core_calculation_completes_the_module_as_a_declared_limitation(tmp_path):
    """D6: CP-2E's rate/FX sensitivity cannot be computed from what the model
    extracted. That is a limitation on the artifact, not evidence insufficiency:
    the module completes, the incomplete calculator is absent from the pinned
    records and present in the host-derived limitations, and the run continues."""
    store = DomainStore.from_url(f"sqlite:///{tmp_path / 'caos.db'}")
    engine = None
    try:
        case, source = _seed(store, "Incomplete macro", b"uploaded annual quarterly forecast debt evidence")
        provider = CalculationRouteProvider(
            source["id"], "b00001", calculation_inputs={"rate_fx_sensitivity": {}},
        )
        engine = Engine.create(
            settings=Settings(storage_dir=tmp_path / "vault", agent_execution_enabled=True),
            store=store, checkpoint_path=tmp_path / "checkpoints.db", provider=provider,
        )

        started = await engine.start_run(
            case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst",
        )
        completed = await engine.wait(started["id"])

        assert completed["status"] == "succeeded", completed.get("error")
        artifact = next(a for a in engine.artifacts_for_run(started["id"]) if a["module_id"] == "CP-2E")
        assert [record["calculator_id"] for record in artifact["payload"]["calculations"]] == []
        assert artifact["payload"]["calculation_limitations"] == [{
            "calculator_id": "rate_fx_sensitivity",
            "code": "METHODOLOGY_CALCULATION_INCOMPLETE",
        }]
        assert "host:calculation_incomplete:rate_fx_sensitivity" in artifact["payload"]["handoff_metadata"]["limitation_flags"]
        assert "calculation_limitations" in artifact["payload"]["handoff_metadata_provenance"]["host_derived_fields"]
        # The model saw the gap as a typed tool result, never as a run failure.
        assert provider.incomplete_results and provider.incomplete_results[0]["complete"] is False
        assert provider.incomplete_results[0]["code"] == "METHODOLOGY_CALCULATION_INCOMPLETE"
        assert "SOURCE_EVIDENCE" not in json.dumps(provider.incomplete_results)
    finally:
        if engine is not None:
            await engine.aclose()
        store.close()


async def test_incomplete_calculation_may_be_retried_once_as_the_module_repair(tmp_path):
    store = DomainStore.from_url(f"sqlite:///{tmp_path / 'caos.db'}")
    engine = None
    try:
        case, source = _seed(store, "Retry macro", b"uploaded annual quarterly forecast debt evidence")
        provider = CalculationRouteProvider(
            source["id"], "b00001",
            calculation_inputs={"rate_fx_sensitivity": {}},
            retry_inputs={"rate_fx_sensitivity": _VALID_CALCULATION_INPUTS["rate_fx_sensitivity"]},
        )
        engine = Engine.create(
            settings=Settings(storage_dir=tmp_path / "vault", agent_execution_enabled=True),
            store=store, checkpoint_path=tmp_path / "checkpoints.db", provider=provider,
        )

        started = await engine.start_run(
            case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst",
        )
        completed = await engine.wait(started["id"])

        assert completed["status"] == "succeeded", completed.get("error")
        artifact = next(a for a in engine.artifacts_for_run(started["id"]) if a["module_id"] == "CP-2E")
        assert [record["calculator_id"] for record in artifact["payload"]["calculations"]] == ["rate_fx_sensitivity"]
        assert artifact["payload"]["calculation_limitations"] == []
        assert provider.retried == ["rate_fx_sensitivity"]
        assert engine.runs.get_budget(started["id"])["used"]["repairs"] == 1, "the retry is the module's one repair"
    finally:
        if engine is not None:
            await engine.aclose()
        store.close()


async def test_incomplete_core_calculation_ends_the_run_as_a_model_failure_not_evidence_insufficiency(tmp_path):
    """CP-1's credit metrics are the module's core numbers: an incomplete result
    after the single repair ends the run with the calculation code, never with
    SOURCE_EVIDENCE_INSUFFICIENT, which is reserved for a declared source gate."""
    store = DomainStore.from_url(f"sqlite:///{tmp_path / 'caos.db'}")
    engine = None
    try:
        case, source = _seed(store, "Incomplete core", b"uploaded annual and quarterly evidence")
        provider = CalculationRouteProvider(
            source["id"], "b00001",
            calculation_inputs={"credit_metrics": {}},
            retry_inputs={"credit_metrics": {"periods": {}}},
        )
        engine = Engine.create(
            settings=Settings(storage_dir=tmp_path / "vault", agent_execution_enabled=True),
            store=store, checkpoint_path=tmp_path / "checkpoints.db", provider=provider,
        )

        started = await engine.start_run(
            case_id=case["id"], pathway="EARNINGS_UPDATE", depth="full", actor="analyst",
        )
        completed = await engine.wait(started["id"])

        assert completed["status"] == "failed"
        assert completed["error"] == {"code": "METHODOLOGY_CALCULATION_INCOMPLETE", "module_id": "CP-1"}
        assert provider.retried == ["credit_metrics"]
        assert "CP-1" not in {a["module_id"] for a in engine.artifacts_for_run(started["id"])}
        terminal = [row for row in engine.runs.get_budget(started["id"])["attempts"] if row["kind"] == "terminal"]
        assert terminal and terminal[-1]["terminal_code"] == "METHODOLOGY_CALCULATION_INCOMPLETE"
    finally:
        if engine is not None:
            await engine.aclose()
        store.close()


async def test_runtime_rejects_model_facing_tables_with_undelivered_source_ids(tmp_path):
    store = DomainStore.from_url(f"sqlite:///{tmp_path / 'caos.db'}")
    engine = None
    try:
        case = store.create_case("Forged table", "Issuer", "Services", "analyst")
        body = b"uploaded issuer evidence"
        source = store.ingest({
            "case_id": case["id"], "filename": "issuer.txt", "media_type": "text/plain",
            "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "vault_path": None,
            "blocks": [{
                "block_id": "b00001", "locator": {"line": 1}, "text": body.decode(),
                "extractor_version": "builtin-v1", "confidence": "MEDIUM", "untrusted_data": True,
            }],
            "withdrawn": False,
        }, "analyst")
        provider = CalculationRouteProvider(
            source["id"], "b00001", model_source_id="source-not-returned",
        )
        engine = Engine.create(
            settings=Settings(storage_dir=tmp_path / "vault", agent_execution_enabled=True),
            store=store,
            checkpoint_path=tmp_path / "checkpoints.db",
            provider=provider,
        )

        started = await engine.start_run(
            case_id=case["id"], pathway="EARNINGS_UPDATE", depth="full", actor="analyst",
        )
        completed = await engine.wait(started["id"])

        assert completed["status"] == "failed"
        assert completed["error"]["code"] == "AGENT_OUTPUT_INVALID"
        assert engine.artifacts_for_run(started["id"]) == []
    finally:
        if engine is not None:
            await engine.aclose()
        store.close()


async def test_runtime_rejects_fixed_prose_without_model_facing_source_attribution(tmp_path):
    store = DomainStore.from_url(f"sqlite:///{tmp_path / 'caos.db'}")
    engine = None
    try:
        case = store.create_case("Fixed prose", "Issuer", "Services", "analyst")
        body = b"uploaded issuer evidence that generic boilerplate does not use"
        source = store.ingest({
            "case_id": case["id"], "filename": "issuer.txt", "media_type": "text/plain",
            "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "vault_path": None,
            "blocks": [{
                "block_id": "b00001", "locator": {"line": 1}, "text": body.decode(),
                "extractor_version": "builtin-v1", "confidence": "MEDIUM", "untrusted_data": True,
            }],
            "withdrawn": False,
        }, "analyst")
        provider = CalculationRouteProvider(
            source["id"],
            "b00001",
            omit_model_source=True,
        )
        engine = Engine.create(
            settings=Settings(storage_dir=tmp_path / "vault", agent_execution_enabled=True),
            store=store,
            checkpoint_path=tmp_path / "checkpoints.db",
            provider=provider,
        )

        started = await engine.start_run(
            case_id=case["id"], pathway="EARNINGS_UPDATE", depth="full", actor="analyst",
        )
        completed = await engine.wait(started["id"])

        assert completed["status"] == "failed"
        assert completed["error"]["code"] == "AGENT_OUTPUT_INVALID"
        assert engine.artifacts_for_run(started["id"]) == []
    finally:
        if engine is not None:
            await engine.aclose()
        store.close()


@pytest.mark.parametrize(("source_gate", "expected_code"), [
    ("fail", "SOURCE_EVIDENCE_INSUFFICIENT"),
    ("partial", "SOURCE_EVIDENCE_RESTRICTED"),
])
async def test_sparse_or_legally_incomplete_pack_returns_a_typed_refusal(
    tmp_path,
    source_gate,
    expected_code,
):
    store = DomainStore.from_url(f"sqlite:///{tmp_path / 'caos.db'}")
    engine = None
    try:
        case = store.create_case("Incomplete pack", "Issuer", "Services", "analyst")
        body = b"sparse uploaded source pack with missing legal support"
        source = store.ingest({
            "case_id": case["id"], "filename": "sparse.txt", "media_type": "text/plain",
            "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "vault_path": None,
            "blocks": [{
                "block_id": "b00001", "locator": {"line": 1}, "text": body.decode(),
                "extractor_version": "builtin-v1", "confidence": "MEDIUM", "untrusted_data": True,
            }],
            "withdrawn": False,
        }, "analyst")
        provider = CalculationRouteProvider(
            source["id"], "b00001", source_gate=source_gate,
        )
        engine = Engine.create(
            settings=Settings(storage_dir=tmp_path / "vault", agent_execution_enabled=True),
            store=store,
            checkpoint_path=tmp_path / "checkpoints.db",
            provider=provider,
        )

        started = await engine.start_run(
            case_id=case["id"], pathway="EARNINGS_UPDATE", depth="full", actor="analyst",
        )
        completed = await engine.wait(started["id"])

        assert completed["status"] == "failed"
        assert completed["error"]["code"] == expected_code
        assert engine.runs.get_budget(started["id"])["used"]["repairs"] == 0
    finally:
        if engine is not None:
            await engine.aclose()
        store.close()


async def test_incomplete_tool_result_reports_whether_a_retry_is_still_available(tmp_path):
    """The typed result tells the model whether the module's repair allowance is
    still available, so a real model can choose to declare the gap instead of
    spending a retry it no longer has."""
    store = DomainStore.from_url(f"sqlite:///{tmp_path / 'caos.db'}")
    engine = None
    try:
        case, source = _seed(store, "Retry twice", b"uploaded annual quarterly forecast debt evidence")
        provider = CalculationRouteProvider(
            source["id"], "b00001",
            calculation_inputs={"rate_fx_sensitivity": {}},
            retry_inputs={"rate_fx_sensitivity": {}},
        )
        engine = Engine.create(
            settings=Settings(storage_dir=tmp_path / "vault", agent_execution_enabled=True),
            store=store, checkpoint_path=tmp_path / "checkpoints.db", provider=provider,
        )

        started = await engine.start_run(case_id=case["id"], pathway="FULL_CREDIT", depth="full", actor="analyst")
        completed = await engine.wait(started["id"])

        assert completed["status"] == "succeeded", completed.get("error")
        assert [record["retry_available"] for record in provider.incomplete_results] == [True, False]
        artifact = next(a for a in engine.artifacts_for_run(started["id"]) if a["module_id"] == "CP-2E")
        assert artifact["payload"]["calculation_limitations"] == [{
            "calculator_id": "rate_fx_sensitivity", "code": "METHODOLOGY_CALCULATION_INCOMPLETE",
        }]
    finally:
        if engine is not None:
            await engine.aclose()
        store.close()


async def test_provider_cannot_forge_a_host_limitation_flag(tmp_path):
    """`host:` limitation flags are host-derived provenance; a provider that
    emits one is refused as invalid output, never recorded as a host finding."""
    store = DomainStore.from_url(f"sqlite:///{tmp_path / 'caos.db'}")
    engine = None
    try:
        case, source = _seed(store, "Forged flag", b"uploaded annual and quarterly evidence")
        provider = CalculationRouteProvider(
            source["id"], "b00001",
            limitation_flags=["host:calculation_incomplete:credit_metrics"],
        )
        engine = Engine.create(
            settings=Settings(storage_dir=tmp_path / "vault", agent_execution_enabled=True),
            store=store, checkpoint_path=tmp_path / "checkpoints.db", provider=provider,
        )

        started = await engine.start_run(case_id=case["id"], pathway="EARNINGS_UPDATE", depth="full", actor="analyst")
        completed = await engine.wait(started["id"])

        assert completed["status"] == "failed"
        assert completed["error"]["code"] == "AGENT_OUTPUT_INVALID"
        assert engine.artifacts_for_run(started["id"]) == []
    finally:
        if engine is not None:
            await engine.aclose()
        store.close()
