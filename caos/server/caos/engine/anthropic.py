"""Production Anthropic binding for the provider port (DECISIONS §12.16, §12.18).

ChatAnthropic is the pinned client factory, message formatter, and output
normalizer; the metered path goes directly to the adapter's async client
(`messages.count_tokens` / `messages.create`). `invoke()` / `bind_tools` /
`with_structured_output` are never on the metered path. read_evidence is the
raw Anthropic tool dict (strict); structured output uses the JSON-schema
output mode; the host owns retry policy (`max_retries=0`).
"""

from __future__ import annotations

from typing import Any

from .provider import AgentError, ProviderBlock, ProviderMessage, ProviderRequest, ProviderUsage
from .budget import PROVIDER_TIMEOUT_SECONDS


class AnthropicProvider:
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise AgentError("AGENT_PROVIDER_UNAVAILABLE", "ANTHROPIC_API_KEY is not configured")
        from langchain_anthropic import ChatAnthropic

        # §12.18 adapter pins: the host owns retries, streaming is disabled,
        # nothing is cached, and the SDK per-request timeout is an inner hint
        # (the outer asyncio.timeout in the loop is the enforcement).
        self.chat = ChatAnthropic(
            model=model,
            api_key=api_key,
            max_retries=0,
            disable_streaming=True,
            cache=False,
            default_request_timeout=PROVIDER_TIMEOUT_SECONDS,
        )
        self.model = model

    def _payload(self, request: ProviderRequest) -> dict[str, Any]:
        from .provider import READ_EVIDENCE_TOOL

        payload: dict[str, Any] = {
            "model": self.model,
            "system": request.system,
            "messages": [self._wire_message(message) for message in request.messages],
            "output_config": {"format": {"type": "json_schema", "schema": request.schema}},
        }
        if request.tools_enabled:
            payload["tools"] = [READ_EVIDENCE_TOOL]
            payload["tool_choice"] = {"type": "auto", "disable_parallel_tool_use": True}
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        return payload

    @staticmethod
    def _wire_message(message: dict[str, Any]) -> dict[str, Any]:
        content = message.get("content")
        if isinstance(content, list):
            content = [
                {key: value for key, value in vars(block).items() if value is not None}
                if isinstance(block, ProviderBlock)
                else block
                for block in content
            ]
        return {**message, "content": content}

    async def count_tokens(self, request: ProviderRequest) -> int:
        # The count body is the payload restricted to the endpoint's fields.
        payload = self._payload(request)
        payload.pop("max_tokens", None)
        payload.pop("output_config", None)
        response = await self.chat._async_client.messages.count_tokens(**payload)
        return getattr(response, "input_tokens", None)

    async def create_message(self, request: ProviderRequest) -> ProviderMessage:
        payload = self._payload(request)
        if request.timeout is not None:
            payload["timeout"] = request.timeout
        response = await self.chat._async_client.messages.create(**payload)
        usage = getattr(response, "usage", None)
        content = getattr(response, "content", None)
        blocks = [
            ProviderBlock(
                type=getattr(block, "type", None),
                id=getattr(block, "id", None),
                name=getattr(block, "name", None),
                input=getattr(block, "input", None),
                text=getattr(block, "text", None),
            )
            for block in content
        ] if isinstance(content, list) else content
        return ProviderMessage(
            content=blocks,  # type: ignore[arg-type]
            stop_reason=getattr(response, "stop_reason", None),
            usage=ProviderUsage(
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
            ),
            request_id=getattr(response, "_request_id", None),
        )
