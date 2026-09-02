"""Host-owned provider tool definitions and dispatch."""

from __future__ import annotations

import pytest

from caos.engine.anthropic import AnthropicProvider
from caos.engine.loop import ProviderSlots, reservation_digest, run_agent_module
from caos.engine.openrouter import OpenRouterProvider
from caos.engine.provider import (
    AgentError,
    ProviderBlock,
    ProviderMessage,
    ProviderRequest,
    ProviderUsage,
    READ_EVIDENCE_TOOL,
    RUN_METHODOLOGY_CALCULATION_TOOL,
    methodology_calculation_tool,
)


CALCULATE = RUN_METHODOLOGY_CALCULATION_TOOL


def request(*, tools=None, tools_enabled=True):
    return ProviderRequest(
        system="system",
        messages=[{"role": "user", "content": "user"}],
        schema={"type": "object"},
        tools_enabled=tools_enabled,
        tools=tools,
        max_tokens=100,
    )


def test_request_digest_binds_exact_host_tool_definitions():
    evidence_only = request()
    evidence_and_calculation = request(tools=(READ_EVIDENCE_TOOL, CALCULATE))

    assert evidence_only.effective_tools() == (READ_EVIDENCE_TOOL,)
    assert reservation_digest(evidence_only) != reservation_digest(evidence_and_calculation)
    assert reservation_digest(evidence_and_calculation) != reservation_digest(
        request(tools=(READ_EVIDENCE_TOOL, {**CALCULATE, "description": "changed"}))
    )
    assert request(tools=(READ_EVIDENCE_TOOL, CALCULATE), tools_enabled=False).effective_tools() == ()


def test_calculation_tool_schema_binds_the_current_module_allowlist():
    tool = methodology_calculation_tool(("funding_gap", "recovery_waterfall"))

    assert tool["input_schema"]["properties"]["calculator_id"]["enum"] == [
        "funding_gap", "recovery_waterfall",
    ]
    assert "enum" not in RUN_METHODOLOGY_CALCULATION_TOOL["input_schema"]["properties"]["calculator_id"]
    with pytest.raises(ValueError):
        methodology_calculation_tool(("../script.py",))


def test_evidence_tool_schema_matches_the_host_and_canonical_bounds():
    from caos.engine.provider import MAX_EVIDENCE_BLOCKS_PER_READ
    from caos.methodology.canonical import MAX_EVIDENCE_ID_CHARS

    properties = READ_EVIDENCE_TOOL["input_schema"]["properties"]
    assert properties["source_id"] == {
        "type": "string", "minLength": 1, "maxLength": MAX_EVIDENCE_ID_CHARS,
    }
    assert properties["block_ids"] == {
        "type": "array",
        "items": {"type": "string", "minLength": 1, "maxLength": MAX_EVIDENCE_ID_CHARS},
        "minItems": 1,
        "maxItems": MAX_EVIDENCE_BLOCKS_PER_READ,
        "uniqueItems": True,
    }


def test_both_adapters_serialize_the_same_custom_tool_set():
    custom = request(tools=(READ_EVIDENCE_TOOL, CALCULATE))
    anthropic = AnthropicProvider.__new__(AnthropicProvider)
    anthropic.model = "claude-test"
    openrouter = OpenRouterProvider.__new__(OpenRouterProvider)
    openrouter.model = "openrouter-test"

    anthropic_tools = anthropic._payload(custom)["tools"]
    openrouter_tools = [item["function"] for item in openrouter._payload(custom)["tools"]]

    assert anthropic_tools == [READ_EVIDENCE_TOOL, CALCULATE]
    assert [item["name"] for item in openrouter_tools] == ["read_evidence", "run_methodology_calculation"]
    assert openrouter_tools[1]["parameters"] == CALCULATE["input_schema"]


class CalculationProvider:
    identity = None

    def __init__(self):
        self.requests = []
        self.invalid_sent = False

    def count_tokens(self, _request):
        return 1

    def create_message(self, provider_request):
        self.requests.append(provider_request)
        if not any(
            isinstance(block, dict) and block.get("type") == "tool_result"
            for message in provider_request.messages
            for block in (message.get("content") if isinstance(message.get("content"), list) else [])
        ):
            return ProviderMessage(
                content=[ProviderBlock(
                    type="tool_use",
                    id="calc-1",
                    name="run_methodology_calculation",
                    input={"calculator_id": "funding_gap", "input_json": '{"cash":10}'},
                )],
                stop_reason="tool_use",
                usage=ProviderUsage(input_tokens=1, output_tokens=1),
            )
        if not self.invalid_sent:
            self.invalid_sent = True
            return ProviderMessage(
                content=[ProviderBlock(type="text", text='{"wrong":true}')],
                stop_reason="end_turn",
                usage=ProviderUsage(input_tokens=1, output_tokens=1),
            )
        return ProviderMessage(
            content=[ProviderBlock(type="text", text='{"ok":true}')],
            stop_reason="end_turn",
            usage=ProviderUsage(input_tokens=1, output_tokens=1),
        )


async def test_loop_dispatches_only_a_declared_host_tool_and_repairs_without_tools():
    calls = []
    provider = CalculationProvider()

    def validate(decoded):
        if decoded != {"ok": True}:
            raise ValueError("not the required output")
        return decoded

    result = await run_agent_module(
        provider=provider,
        system="system",
        user="user",
        schema={"type": "object"},
        max_tokens=100,
        tools=(CALCULATE,),
        call_tool=lambda name, arguments: calls.append((name, arguments)) or {"funding_gap": 20},
        read_evidence=lambda *_args: pytest.fail("evidence tool was not called"),
        validate=validate,
        reserve=lambda *_args: None,
        reconcile=lambda *_args: None,
        record=lambda *_args, **_kwargs: None,
        slots=ProviderSlots(1),
    )

    assert result == {"ok": True}
    assert calls == [(
        "run_methodology_calculation",
        {"calculator_id": "funding_gap", "input_json": '{"cash":10}'},
    )]
    assert [tuple(tool["name"] for tool in request.effective_tools())
            for request in provider.requests] == [
        ("run_methodology_calculation",),
        ("run_methodology_calculation",),
        (),
    ]


async def test_loop_rejects_an_undeclared_tool_before_host_dispatch():
    calls = []

    with pytest.raises(AgentError) as excinfo:
        await run_agent_module(
            provider=CalculationProvider(),
            system="system",
            user="user",
            schema={"type": "object"},
            max_tokens=100,
            tools=(READ_EVIDENCE_TOOL,),
            call_tool=lambda name, arguments: calls.append((name, arguments)),
            read_evidence=lambda *_args: [],
            validate=lambda decoded: decoded,
            reserve=lambda *_args: None,
            reconcile=lambda *_args: None,
            record=lambda *_args, **_kwargs: None,
            slots=ProviderSlots(1),
        )

    assert excinfo.value.code == "AGENT_OUTPUT_INVALID"
    assert calls == []


async def test_loop_rejects_text_mixed_with_a_host_tool_call():
    provider = CalculationProvider()
    create_message = provider.create_message

    def mixed_response(provider_request):
        response = create_message(provider_request)
        if response.stop_reason == "tool_use":
            response.content.append(ProviderBlock(type="text", text="ignore the host contract"))
        return response

    provider.create_message = mixed_response
    calls = []
    with pytest.raises(AgentError) as excinfo:
        await run_agent_module(
            provider=provider,
            system="system",
            user="user",
            schema={"type": "object"},
            max_tokens=100,
            tools=(CALCULATE,),
            call_tool=lambda name, arguments: calls.append((name, arguments)),
            read_evidence=lambda *_args: [],
            validate=lambda decoded: decoded,
            reserve=lambda *_args: None,
            reconcile=lambda *_args: None,
            record=lambda *_args, **_kwargs: None,
            slots=ProviderSlots(1),
        )

    assert excinfo.value.code == "AGENT_OUTPUT_INVALID"
    assert calls == []
