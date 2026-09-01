"""OpenRouter binding for the provider port.

The port is Anthropic-shaped, so this adapter is almost entirely translation:
what the loop hands it, what it must hand back, and the one place where the
provider genuinely cannot do what Anthropic does — count tokens before the call.
These tests pin the translation in both directions against the exact message
shapes `loop.py` builds, because a silent mistranslation there does not raise;
it starves a module of evidence or loses a citation.

No network: `httpx.AsyncClient.post` is stubbed with recorded OpenRouter bodies.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SERVER = Path(__file__).resolve().parents[1] / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from caos.engine.openrouter import STOP_REASONS, OpenRouterProvider  # noqa: E402
from caos.engine.provider import AgentError, ProviderBlock, ProviderRequest  # noqa: E402

SCHEMA = {"type": "object", "properties": {"markdown": {"type": "string"}}, "required": ["markdown"]}


def make_request(messages, *, tools_enabled=True, max_tokens=1_000):
    return ProviderRequest(system="SYSTEM AUTHORITY", messages=messages, schema=SCHEMA,
                           tools_enabled=tools_enabled, max_tokens=max_tokens)


@pytest.fixture()
def provider():
    return OpenRouterProvider("sk-or-test", "z-ai/glm-5.3-flash")


class Recorder:
    """Stands in for httpx.AsyncClient.post; records the payload, replays a body."""

    def __init__(self, body, status=200):
        self.body, self.status, self.payload = body, status, None

    async def __call__(self, url, json=None, timeout=None):
        self.payload = json
        return Response(self.status, self.body)


class Response:
    def __init__(self, status_code, body):
        self.status_code, self._body = status_code, body

    @property
    def text(self):
        return json.dumps(self._body)

    def json(self):
        return self._body


def completion(message, *, finish_reason="stop", usage=None):
    return {
        "id": "gen-abc123",
        "choices": [{"finish_reason": finish_reason, "message": message}],
        "usage": usage if usage is not None else {"prompt_tokens": 1_200, "completion_tokens": 340},
    }


# -- request shaping -------------------------------------------------------


def test_system_authority_leads_and_tools_ride_the_openai_shape(provider):
    payload = provider._payload(make_request([{"role": "user", "content": "MODULE BRIEF"}]))

    assert payload["messages"][0] == {"role": "system", "content": "SYSTEM AUTHORITY"}
    assert payload["messages"][1] == {"role": "user", "content": "MODULE BRIEF"}
    assert payload["model"] == "z-ai/glm-5.3-flash"
    tool = payload["tools"][0]
    assert tool["type"] == "function" and tool["function"]["name"] == "read_evidence"
    assert tool["function"]["parameters"]["required"] == ["source_id", "block_ids"]
    assert payload["parallel_tool_calls"] is False, "the loop admits exactly one tool call per turn"


def test_schema_is_bound_only_when_the_turn_has_no_tools(provider):
    """Binding the envelope schema alongside the tool makes providers answer the
    schema instead of calling read_evidence, which starves the module of
    evidence rather than failing loudly."""
    with_tools = provider._payload(make_request([{"role": "user", "content": "x"}]))
    assert "response_format" not in with_tools

    repair = provider._payload(make_request([{"role": "user", "content": "x"}], tools_enabled=False))
    assert repair["response_format"]["json_schema"]["schema"] == SCHEMA
    assert repair["response_format"]["json_schema"]["strict"] is True
    assert "tools" not in repair


def test_the_assistant_tool_turn_and_its_result_survive_the_round_trip(provider):
    """The exact two messages loop.py appends after an evidence read."""
    call = ProviderBlock(type="tool_use", id="call_1", name="read_evidence",
                         input={"source_id": "src-1", "block_ids": ["b00001"]})
    rows = json.dumps([{"block_id": "b00001", "text": "Revenue rose 12%."}], sort_keys=True)
    payload = provider._payload(make_request([
        {"role": "user", "content": "MODULE BRIEF"},
        {"role": "assistant", "content": [call]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "call_1", "content": rows}]},
    ]))

    assistant = payload["messages"][2]
    assert assistant["role"] == "assistant" and assistant["content"] is None
    assert assistant["tool_calls"] == [{
        "id": "call_1", "type": "function",
        "function": {"name": "read_evidence",
                     "arguments": json.dumps({"block_ids": ["b00001"], "source_id": "src-1"}, sort_keys=True)},
    }]
    assert payload["messages"][3] == {"role": "tool", "tool_call_id": "call_1", "content": rows}


def test_an_assistant_text_turn_carries_its_text(provider):
    """The repair path echoes the model's own text back before asking again."""
    payload = provider._payload(make_request([
        {"role": "user", "content": "brief"},
        {"role": "assistant", "content": [ProviderBlock(type="text", text="{\"markdown\": 1}")]},
        {"role": "user", "content": "LOCAL VALIDATION FAILED — ..."},
    ], tools_enabled=False))
    assert payload["messages"][2] == {"role": "assistant", "content": "{\"markdown\": 1}"}


# -- response shaping ------------------------------------------------------


async def test_a_tool_call_comes_back_as_one_tool_use_block(provider):
    recorder = Recorder(completion(
        {"role": "assistant", "content": None, "tool_calls": [{
            "id": "call_9", "type": "function",
            "function": {"name": "read_evidence",
                         "arguments": '{"source_id": "src-1", "block_ids": ["b00007"]}'},
        }]},
        finish_reason="tool_calls",
    ))
    provider._client.post = recorder

    message = await provider.create_message(make_request([{"role": "user", "content": "brief"}]))

    assert message.stop_reason == "tool_use", "loop.py dispatches evidence reads on this exact string"
    assert len(message.content) == 1
    block = message.content[0]
    assert (block.type, block.id, block.name) == ("tool_use", "call_9", "read_evidence")
    assert block.input == {"source_id": "src-1", "block_ids": ["b00007"]}
    assert message.usage.input_tokens == 1_200 and message.usage.output_tokens == 340
    assert message.request_id == "gen-abc123"


async def test_a_final_answer_comes_back_as_one_text_block(provider):
    envelope = json.dumps({"markdown": "## Analysis"})
    provider._client.post = Recorder(completion({"role": "assistant", "content": envelope}))

    message = await provider.create_message(make_request([{"role": "user", "content": "brief"}]))

    assert message.stop_reason == "end_turn"
    assert [b.type for b in message.content] == ["text"]
    assert message.content[0].text == envelope


async def test_response_reports_the_observed_openrouter_model(provider):
    body = completion({"role": "assistant", "content": "{}"})
    body["model"] = "provider/actual-model"
    body["provider_version"] = "provider-build-7"
    provider._client.post = Recorder(body)

    message = await provider.create_message(make_request([{"role": "user", "content": "brief"}]))

    assert message.observed_model == "provider/actual-model"
    assert message.observed_provider_version == "provider-build-7"


@pytest.mark.parametrize("finish,expected", sorted(STOP_REASONS.items()))
async def test_finish_reasons_map_onto_the_port_vocabulary(provider, finish, expected):
    provider._client.post = Recorder(completion({"role": "assistant", "content": "{}"}, finish_reason=finish))
    message = await provider.create_message(make_request([{"role": "user", "content": "x"}]))
    assert message.stop_reason == expected


async def test_an_unknown_finish_reason_is_passed_through_for_the_host_to_refuse(provider):
    """Normalising an unseen state here would hide it from loop.py, which is the
    component that decides what a stop reason means."""
    provider._client.post = Recorder(completion({"role": "assistant", "content": "{}"},
                                                finish_reason="content_filter"))
    message = await provider.create_message(make_request([{"role": "user", "content": "x"}]))
    assert message.stop_reason == "content_filter"


async def test_a_refusal_is_typed_so_the_loop_can_see_it(provider):
    provider._client.post = Recorder(completion({"role": "assistant", "content": None, "refusal": "no"}))
    message = await provider.create_message(make_request([{"role": "user", "content": "x"}]))
    assert message.content[0].type == "refusal"


# -- failure paths ---------------------------------------------------------


async def test_an_http_error_is_a_typed_provider_failure(provider):
    provider._client.post = Recorder({"error": {"message": "no credit"}}, status=402)
    with pytest.raises(AgentError) as excinfo:
        await provider.create_message(make_request([{"role": "user", "content": "x"}]))
    assert excinfo.value.code == "AGENT_PROVIDER_UNAVAILABLE"


async def test_an_upstream_error_inside_a_200_body_is_not_read_as_success(provider):
    """OpenRouter reports upstream provider failures in a 200 response."""
    provider._client.post = Recorder({"error": {"message": "upstream timeout"}, "choices": []})
    with pytest.raises(AgentError) as excinfo:
        await provider.create_message(make_request([{"role": "user", "content": "x"}]))
    assert excinfo.value.code == "AGENT_PROVIDER_UNAVAILABLE"


async def test_unparseable_tool_arguments_are_typed_not_swallowed(provider):
    provider._client.post = Recorder(completion(
        {"role": "assistant", "tool_calls": [
            {"id": "c", "type": "function", "function": {"name": "read_evidence", "arguments": "{not json"}}]},
        finish_reason="tool_calls",
    ))
    with pytest.raises(AgentError) as excinfo:
        await provider.create_message(make_request([{"role": "user", "content": "x"}]))
    assert excinfo.value.code == "AGENT_OUTPUT_INVALID"


def test_a_missing_key_refuses_at_construction():
    with pytest.raises(AgentError) as excinfo:
        OpenRouterProvider("", "z-ai/glm-5.3-flash")
    assert excinfo.value.code == "AGENT_PROVIDER_UNAVAILABLE"


# -- metering --------------------------------------------------------------


async def test_the_token_estimate_grows_with_the_request_and_is_never_zero(provider):
    """Invariant 8 reserves against this number before the call. It is a local
    estimate on this provider, so what it must be is monotonic and positive —
    never a zero that would reserve nothing."""
    small = await provider.count_tokens(make_request([{"role": "user", "content": "brief"}]))
    large = await provider.count_tokens(make_request([{"role": "user", "content": "brief " * 5_000}]))

    assert small > 0
    assert large > small * 10, "a far larger prompt must reserve a far larger count"


async def test_the_estimate_is_biased_upward_so_the_ceiling_is_hit_early(provider):
    """Under-reserving would let a request through that the ceiling was meant to
    refuse; over-reserving only spends budget sooner."""
    import tiktoken

    request = make_request([{"role": "user", "content": "the borrower shall not permit " * 200}])
    payload = provider._payload(request)
    payload.pop("max_tokens", None)
    exact = len(tiktoken.get_encoding("o200k_base").encode(json.dumps(payload, sort_keys=True)))

    assert await provider.count_tokens(request) > exact


async def test_counting_never_reaches_the_network(provider):
    """The count runs before the reservation, so it must not be a billable call
    or a second failure surface."""
    def explode(*args, **kwargs):
        raise AssertionError("count_tokens contacted the network")

    provider._client.post = explode
    assert await provider.count_tokens(make_request([{"role": "user", "content": "x"}])) > 0


async def test_only_a_real_timeout_claims_the_timeout_code(provider):
    """loop.py answers AGENT_PROVIDER_TIMEOUT with a byte-identical retry. A
    connect error or a broken pipe will not resolve by being repeated, so it
    must not borrow the code that buys one."""
    import httpx

    async def refuse_connect(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    async def time_out(*args, **kwargs):
        raise httpx.ReadTimeout("read timed out")

    provider._client.post = refuse_connect
    with pytest.raises(AgentError) as connect_failure:
        await provider.create_message(make_request([{"role": "user", "content": "x"}]))
    assert connect_failure.value.code == "AGENT_PROVIDER_UNAVAILABLE"

    provider._client.post = time_out
    with pytest.raises(AgentError) as timeout_failure:
        await provider.create_message(make_request([{"role": "user", "content": "x"}]))
    assert timeout_failure.value.code == "AGENT_PROVIDER_TIMEOUT"
