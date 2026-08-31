"""OpenRouter binding for the provider port (sibling of anthropic.py).

The port is Anthropic-shaped because the engine was built against it: content
is a list of typed blocks, a tool call arrives as `tool_use`, and the loop asks
for a token count *before* every create so the budget can be reserved first
(invariant 8; loop.py count -> reserve -> create). OpenRouter speaks the
OpenAI chat-completions dialect and has no pre-call counting endpoint, so this
adapter owns two translations and one honest approximation:

  * message and tool shapes, both directions, in `_wire_messages` and
    `_blocks`;
  * `count_tokens` measured locally with tiktoken over the exact serialized
    request. It is an estimate: tiktoken carries OpenAI's vocabularies, not
    GLM's or Llama's, so the number is off by a few percent either way. The
    reservation is therefore approximate on this provider in a way it is not on
    Anthropic, whose endpoint returns the real count. `TOKEN_ESTIMATE_MARGIN`
    biases it upward so the ceiling is approached early rather than overrun,
    which keeps the failure direction fail-closed.

Everything the host owns stays with the host: no client-side retry, no
streaming, no caching, and the outer asyncio.timeout in the loop remains the
enforcement.

Observed model behaviour, recorded from a live CP-1 run on z-ai/glm-5.3-flash
so the next reader does not rediscover it. None of it is worked around here —
each one is a model that does not meet the module contract, and the host
refusing it is the guardrail working:

  * binding a json_schema `response_format` alongside `tools` corrupts the tool
    call itself — `arguments` came back truncated to `{"block_ids": `. That is
    why the schema is bound only on the tool-less turn.
  * with no schema bound, it generates to the module's max_tokens ceiling
    (32,000 for CP-1) and the host refuses the turn as truncated.
  * it ignores `parallel_tool_calls: false` and returns several calls in one
    turn; loop.py admits exactly one evidence read per turn.
  * it cites blocks it never read, including malformed ids, which
    validate_citations refuses.

It also needs longer than PROVIDER_TIMEOUT_SECONDS (150s) for a 32k-token
module. Read: this binding is sound, but a model this size does not hold CP-1's
output contract. Smaller deterministic modules are unaffected.
"""

from __future__ import annotations

import json
from typing import Any

from .budget import PROVIDER_TIMEOUT_SECONDS
from .loop import reject_duplicate_keys
from .provider import AgentError, ProviderBlock, ProviderMessage, ProviderRequest, ProviderUsage

BASE_URL = "https://openrouter.ai/api/v1"
# A local tokenizer cannot know the served model's vocabulary, so the count is
# rounded up by this factor. Over-reserving is nearly free — reconcile_provider
# replaces the reservation with the actual usage once the call returns — while
# under-reserving lets a request through that the ceiling was meant to refuse.
# Bias generously. Measured against z-ai/glm-5.3-flash, actual prompt_tokens
# over raw tiktoken count of the serialized payload:
#     empty prompt   120 raw ->    32 actual   0.27x  (JSON envelope dominates)
#     ~1k tokens   1,140 raw -> 1,052 actual   0.92x
#     ~8k tokens   7,920 raw -> 9,032 actual   1.14x
#     tool turn      192 raw ->   230 actual   1.20x
# The ratio climbs with prompt size as the envelope amortises, so the margin is
# set above the worst observed case rather than at it.
TOKEN_ESTIMATE_MARGIN = 1.5
# tiktoken's newest published vocabulary. Not GLM's, which is the point of the
# margin above; it is a stable, offline stand-in rather than a claim of accuracy.
TOKENIZER_ENCODING = "o200k_base"

# finish_reason -> the port's stop_reason vocabulary. Anything absent stays
# verbatim so loop.py rejects it as an unexpected stop reason rather than this
# adapter quietly normalising a state the host has never seen.
STOP_REASONS = {"tool_calls": "tool_use", "stop": "end_turn", "length": "max_tokens"}


class OpenRouterProvider:
    def __init__(self, api_key: str, model: str, *, referer: str = "", title: str = "CAOS") -> None:
        if not api_key:
            raise AgentError("AGENT_PROVIDER_UNAVAILABLE", "OPENROUTER_API_KEY is not configured")
        import httpx
        import tiktoken

        self.model = model
        self._encoding = tiktoken.get_encoding(TOKENIZER_ENCODING)
        headers = {"Authorization": f"Bearer {api_key}", "X-Title": title}
        if referer:
            headers["HTTP-Referer"] = referer
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers=headers,
            timeout=PROVIDER_TIMEOUT_SECONDS,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # -- request shaping ---------------------------------------------------

    @staticmethod
    def _tool_definition() -> dict[str, Any]:
        from .provider import READ_EVIDENCE_TOOL

        return {
            "type": "function",
            "function": {
                "name": READ_EVIDENCE_TOOL["name"],
                "description": READ_EVIDENCE_TOOL["description"],
                "parameters": READ_EVIDENCE_TOOL["input_schema"],
                "strict": READ_EVIDENCE_TOOL["strict"],
            },
        }

    @staticmethod
    def _wire_messages(system: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Port messages -> OpenAI chat messages.

        Three shapes reach this adapter, all built by loop.py: a plain string
        user turn, an assistant turn echoing the blocks we returned, and a user
        turn carrying one tool_result.
        """
        wired: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for message in messages:
            role, content = message["role"], message.get("content")
            if isinstance(content, str):
                wired.append({"role": role, "content": content})
                continue
            if not isinstance(content, list):
                raise AgentError("AGENT_OUTPUT_INVALID", "unroutable message content")

            tool_results = [
                block for block in content
                if isinstance(block, dict) and block.get("type") == "tool_result"
            ]
            if tool_results:
                # OpenAI splits a tool result into its own message per call id.
                wired.extend(
                    {"role": "tool", "tool_call_id": block["tool_use_id"], "content": block["content"]}
                    for block in tool_results
                )
                continue

            text = "".join(
                block.text or "" for block in content if getattr(block, "type", None) == "text"
            )
            calls = [
                {
                    "id": block.id,
                    "type": "function",
                    "function": {"name": block.name, "arguments": json.dumps(block.input or {}, sort_keys=True)},
                }
                for block in content if getattr(block, "type", None) == "tool_use"
            ]
            turn: dict[str, Any] = {"role": role, "content": text or None}
            if calls:
                turn["tool_calls"] = calls
            wired.append(turn)
        return wired

    def _payload(self, request: ProviderRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._wire_messages(request.system, request.messages),
        }
        if request.tools_enabled:
            payload["tools"] = [self._tool_definition()]
            payload["tool_choice"] = "auto"
            payload["parallel_tool_calls"] = False
        else:
            # The schema is only bound on the turn that must produce the final
            # envelope. Binding it alongside tools makes providers answer the
            # schema instead of calling the tool, which would starve the module
            # of evidence rather than fail loudly.
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "CanonicalModuleOutput", "strict": True, "schema": request.schema},
            }
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        return payload

    # -- port --------------------------------------------------------------

    async def count_tokens(self, request: ProviderRequest) -> int:
        """Local estimate. See the module docstring: OpenRouter has no pre-call
        counting endpoint, and the host reserves before it calls."""
        payload = self._payload(request)
        payload.pop("max_tokens", None)
        measured = len(self._encoding.encode(json.dumps(payload, sort_keys=True), disallowed_special=()))
        return int(measured * TOKEN_ESTIMATE_MARGIN) + 1

    async def create_message(self, request: ProviderRequest) -> ProviderMessage:
        payload = self._payload(request)
        timeout = request.timeout if request.timeout is not None else PROVIDER_TIMEOUT_SECONDS
        import httpx

        try:
            response = await self._client.post("/chat/completions", json=payload, timeout=timeout)
        except httpx.TimeoutException as exc:
            # Only a real timeout may claim this code: loop.py answers it with a
            # byte-identical retry, which is wasted on a failure that will not
            # resolve by being repeated.
            raise AgentError("AGENT_PROVIDER_TIMEOUT", f"openrouter timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise AgentError("AGENT_PROVIDER_UNAVAILABLE", f"openrouter transport failure: {exc}") from exc
        if response.status_code >= 400:
            raise AgentError(
                "AGENT_PROVIDER_UNAVAILABLE",
                f"openrouter returned {response.status_code}: {response.text[:200]}",
            )
        body = response.json()
        if body.get("error"):
            # OpenRouter reports upstream failures in a 200 body.
            raise AgentError("AGENT_PROVIDER_UNAVAILABLE", f"openrouter error: {str(body['error'])[:200]}")
        try:
            choice = body["choices"][0]
        except (KeyError, IndexError, TypeError) as exc:
            raise AgentError("AGENT_OUTPUT_INVALID", "openrouter response carried no choice") from exc

        usage = body.get("usage") or {}
        return ProviderMessage(
            content=self._blocks(choice.get("message") or {}),
            stop_reason=STOP_REASONS.get(choice.get("finish_reason"), choice.get("finish_reason")),
            usage=ProviderUsage(
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
            ),
            request_id=body.get("id"),
        )

    @staticmethod
    def _blocks(message: dict[str, Any]) -> list[ProviderBlock]:
        """OpenAI message -> port blocks. Tool calls win: the loop requires
        exactly one tool_use block on a tool turn, and a provider that also
        emits chatter alongside the call must not turn that into two blocks."""
        calls = message.get("tool_calls") or []
        if calls:
            blocks = []
            for call in calls:
                function = call.get("function") or {}
                try:
                    # The MODEL authors this string and the host parses it, so
                    # §12.9's duplicate-key rule governs it exactly as it
                    # governs the final output: a repeated key is refused, never
                    # last-wins into a read the model's own first claim did not
                    # make. The enclosing response body is deliberately NOT
                    # parsed this way — its shape is the gateway's, not the
                    # model's, and `_blocks` trusts that shape throughout.
                    arguments = json.loads(function.get("arguments") or "{}",
                                           object_pairs_hook=reject_duplicate_keys)
                except ValueError as exc:  # JSONDecodeError included
                    raise AgentError("AGENT_OUTPUT_INVALID", "malformed tool arguments") from exc
                blocks.append(ProviderBlock(
                    type="tool_use", id=call.get("id"), name=function.get("name"), input=arguments,
                ))
            return blocks
        if message.get("refusal"):
            return [ProviderBlock(type="refusal", text=str(message["refusal"])[:500])]
        return [ProviderBlock(type="text", text=message.get("content") or "")]
