"""Direct OpenAI contract: stateless continuation, exact counting, metered refusals."""

from __future__ import annotations

import json
from dataclasses import replace

import httpx
import pytest

from caos.engine.loop import ProviderSlots, provider_response_digest, reservation_digest, run_agent_module
from caos.engine.openai import MAX_CONTINUATION_BYTES, OpenAIProvider, strict_output_schema
from caos.engine.provider import AgentError, ProviderMessage, ProviderRequest, ProviderUsage


def request(messages=None):
    return ProviderRequest(system="host authority", messages=messages or [{"role": "user", "content": "evidence"}],
                           schema={"type": "object", "properties": {"ok": {"type": "boolean"}},
                                   "required": ["ok"], "additionalProperties": False},
                           tools_enabled=True, max_tokens=1000)


def response(output, **changes):
    return {"id": "resp-test", "model": "configured-model", "status": "completed", "output": output,
            "usage": {"input_tokens": 100, "output_tokens": 80, "output_tokens_details": {"reasoning_tokens": 70}},
            **changes}


def final():
    return {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": '{"ok":true}'}]}


@pytest.mark.parametrize("effort", [[], {}, None, 2, True, "unsupported"])
def test_invalid_reasoning_parameters_are_typed_refusals(effort):
    with pytest.raises(AgentError, match="AGENT_PROVIDER_UNQUALIFIED"):
        OpenAIProvider("inert-key", "configured-model", parameters={"reasoning_effort": effort})


def test_a_malformed_continuation_cannot_prevent_a_generation_receipt():
    message = ProviderMessage(content=[], stop_reason="end_turn", usage=ProviderUsage(1, 1), continuation=({"bad": {1}},))
    assert len(provider_response_digest(message, {"input_tokens": 1, "output_tokens": 1})) == 64


async def test_invalid_incomplete_details_preserve_known_usage(provider, monkeypatch):
    async def post(*args):
        return response([final()], status="incomplete", incomplete_details="invalid")
    monkeypatch.setattr(provider, "_post", post)
    result = await provider.create_message(request())
    assert result.stop_reason == "incomplete" and result.usage.output_tokens == 80


@pytest.fixture
async def provider():
    value = OpenAIProvider("inert-key", "configured-model", parameters={"reasoning_effort": "low"})
    try:
        yield value
    finally:
        await value.aclose()


async def test_count_and_create_share_all_input_fields_and_reasoning_cap(provider, monkeypatch):
    calls = []

    async def post(path, *, json, timeout):
        calls.append((path, json))
        return httpx.Response(200, json={"object": "response.input_tokens", "input_tokens": 100}
                              if path.endswith("input_tokens") else response([final()]))

    monkeypatch.setattr(provider._client, "post", post)
    assert await provider.count_tokens(request()) == 100
    result = await provider.create_message(request())
    count, create = calls[0][1], calls[1][1]
    assert calls[0][0] == "/responses/input_tokens" and calls[1][0] == "/responses"
    assert count == {k: v for k, v in create.items() if k not in {"store", "stream", "include", "max_output_tokens"}}
    assert create["store"] is False and create["stream"] is False and create["truncation"] == "disabled"
    assert create["max_output_tokens"] == 1000 and result.usage.output_tokens == 80
    assert create["parallel_tool_calls"] is False and create["tools"][0]["strict"] is True
    assert "uniqueItems" not in create["tools"][0]["parameters"]["properties"]["block_ids"]
    assert create["tools"][0]["parameters"]["properties"]["block_ids"]["maxItems"] == 50
    assert create["text"]["format"]["strict"] is True


async def test_encrypted_continuation_round_trips_in_order_without_reasoning_text(provider, monkeypatch):
    reason = {"type": "reasoning", "id": "rs-1", "encrypted_content": "opaque-encrypted",
              "summary": [{"type": "summary_text", "text": "private reasoning must not survive"}]}
    call = {"type": "function_call", "id": "fc-1", "call_id": "call-1", "name": "read_evidence",
            "arguments": '{"source_id":"s","block_ids":["b"]}'}
    calls = []

    async def post(path, *, json, timeout):
        calls.append((path, json))
        if path.endswith("input_tokens"):
            return httpx.Response(200, json={"object": "response.input_tokens", "input_tokens": 100})
        generations = sum(p == "/responses" for p, _ in calls)
        return httpx.Response(200, json=response([reason, call] if generations == 1 else [final()]))

    monkeypatch.setattr(provider._client, "post", post)
    records, reservations = [], []
    result = await run_agent_module(
        provider=provider, system="host authority", user="evidence", schema=request().schema, max_tokens=1000,
        read_evidence=lambda *_: [{"text": "supplied document"}], validate=lambda output: output,
        reserve=lambda *args: reservations.append(args), reconcile=lambda *_: None,
        record=lambda *args, **kwargs: records.append((args, kwargs)), slots=ProviderSlots(2),
        expected_identity=provider.identity,
    )
    assert result == {"ok": True}
    second = [body for path, body in calls if path == "/responses"][1]
    assert [item.get("type") for item in second["input"]] == [None, "reasoning", "function_call", "function_call_output"]
    assert second["input"][1] == {**reason, "summary": []}
    assert second["input"][3]["call_id"] == "call-1"
    assert "private reasoning" not in json.dumps(second)
    assert "opaque-encrypted" not in json.dumps(records)
    assert reservations[0][0] != reservations[1][0]


@pytest.mark.parametrize("output", [
    [{"type": "function_call", "call_id": "c", "name": "read_evidence", "arguments": '{"x":1,"x":2}'}],
    [{"type": "reasoning", "id": "r", "encrypted_content": "x" * (MAX_CONTINUATION_BYTES + 1)}],
    [{"type": "reasoning", "id": "r", "summary": []}],
    [None],
    [{"type": "web_search_call"}],
])
async def test_bad_output_returns_known_usage_for_reconciliation(provider, monkeypatch, output):
    async def post(*args, **kwargs):
        return httpx.Response(200, json=response(output))

    monkeypatch.setattr(provider._client, "post", post)
    result = await provider.create_message(request())
    assert result.stop_reason == "invalid_response"
    assert result.usage.input_tokens == 100 and result.usage.output_tokens == 80
    assert not result.continuation


@pytest.mark.parametrize("body", [
    response([final()], status="incomplete", incomplete_details={"reason": "max_output_tokens"}),
    response([{"type": "message", "role": "assistant", "content": [{"type": "refusal", "refusal": "denied"}]}]),
    response([final()], model="substituted-model"),
])
async def test_truncation_refusal_and_model_substitution_are_billed_before_rejection(provider, monkeypatch, body):
    async def post(path, **kwargs):
        return httpx.Response(200, json={"object": "response.input_tokens", "input_tokens": 100}
                              if path.endswith("input_tokens") else body)

    monkeypatch.setattr(provider._client, "post", post)
    billed = []
    with pytest.raises(AgentError):
        await run_agent_module(provider=provider, system="authority", user="evidence", schema={}, max_tokens=1000,
                               read_evidence=lambda *_: [], validate=lambda value: value,
                               reserve=lambda *_: None, reconcile=lambda *args: billed.append(args),
                               record=lambda *_args, **_kwargs: None, slots=ProviderSlots(2), expected_identity=provider.identity)
    assert len(billed) == 1 and billed[0][-2:] == (100, 80)


async def test_http_failure_never_exposes_provider_echoed_secrets(provider, monkeypatch):
    async def post(*args, **kwargs):
        return httpx.Response(401, json={"error": "secret document text and API credential"})

    monkeypatch.setattr(provider._client, "post", post)
    with pytest.raises(AgentError) as exc:
        await provider.create_message(request())
    assert exc.value.code == "AGENT_PROVIDER_UNAVAILABLE" and "secret document" not in str(exc.value)


def test_reservation_identity_includes_opaque_continuation():
    first = request([{"role": "assistant", "content": [], "continuation": [{"encrypted_content": "one"}]}])
    second = replace(first, messages=[{"role": "assistant", "content": [], "continuation": [{"encrypted_content": "two"}]}])
    assert reservation_digest(first) != reservation_digest(second)


def test_real_canonical_schema_is_closed_required_and_still_host_valid():
    from caos.methodology.canonical import CanonicalModuleOutput

    original = CanonicalModuleOutput.model_json_schema()
    projected = strict_output_schema(original)

    def check(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node.get("properties", {}))
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)

    check(projected)
    assert isinstance(original["properties"]["lineage_counts"]["additionalProperties"], dict)
    result = CanonicalModuleOutput.model_validate({
        "markdown": "Supplied source", "evidence_refs": [{"source_id": "s", "block_id": "b"}],
        "calculation_refs": [], "lineage_counts": {key: 0 for key in projected["properties"]["lineage_counts"]["properties"]},
        "fields_present": 1, "fields_total": 1, "source_gate": "pass",
        "findings": {"CRITICAL": 0, "MATERIAL": 0, "MINOR": 0}, "limitation_flags": [], "validation_warnings": [],
    })
    assert len(result.lineage_counts) == 8
