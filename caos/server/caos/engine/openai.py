"""Direct, stateless OpenAI Responses transport for the existing metered port.

Only host-supplied function tools are exposed. Encrypted continuation stays in
the current module's messages; the adapter has no conversation or response cache.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from ..config import Settings
from .budget import PROVIDER_TIMEOUT_SECONDS
from .loop import reject_duplicate_keys
from .provider import (
    AgentError, ProviderBlock, ProviderIdentity, ProviderMessage, ProviderQualification,
    ProviderRequest, ProviderUsage, installed_dependencies, methodology_binding,
    parameter_context_digest,
)

BASE_URL = "https://api.openai.com/v1"
ADAPTER_VERSION = "caos.openai.v2"
MAX_CONTINUATION_BYTES = 256 * 1024
MAX_CONTINUATION_ITEMS = 40
_LINEAGE_CLASSES = ("directly_sourced", "calculated", "assumption_based", "analyst_inference",
                    "weak_lineage", "untraced", "conflicting", "insufficient_information")


def strict_output_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Narrow the canonical envelope to OpenAI's strict object subset, without changing host validation."""
    result = json.loads(json.dumps(schema))
    properties = result.get("properties", {})
    for name, keys in (("lineage_counts", _LINEAGE_CLASSES), ("findings", ("CRITICAL", "MATERIAL", "MINOR"))):
        node = properties.get(name)
        if isinstance(node, dict) and isinstance(node.get("additionalProperties"), dict):
            value_schema = node["additionalProperties"]
            node["properties"] = {key: dict(value_schema) for key in keys}
            node.pop("propertyNames", None)

    def close_objects(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "array":
                # Responses rejects this keyword; uniqueness remains a host validation rule.
                node.pop("uniqueItems", None)
            if node.get("type") == "object":
                if "properties" not in node and node.get("additionalProperties"):
                    raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "OpenAI cannot represent an unbounded object schema")
                node["additionalProperties"] = False
                node["required"] = list(node.get("properties", {}))
            for value in node.values():
                close_objects(value)
        elif isinstance(node, list):
            for value in node:
                close_objects(value)

    close_objects(result)
    return result


class OpenAIProvider:
    def __init__(self, api_key: str, model: str, *, qualification: ProviderQualification | None = None,
                 methodology_root: Path | None = None, account_policy: str = "",
                 parameters: dict[str, Any] | None = None) -> None:
        if not api_key.strip() or not model.strip():
            raise AgentError("AGENT_PROVIDER_UNAVAILABLE", "OpenAI credential and model must be configured")
        self.model = model
        self.account_policy = account_policy
        self.parameters = dict(parameters or {})
        effort = self.parameters.get("reasoning_effort", "low")
        if set(self.parameters) - {"reasoning_effort"} or not isinstance(effort, str) or effort not in {
            "none", "minimal", "low", "medium", "high", "xhigh",
        }:
            raise AgentError("AGENT_PROVIDER_UNQUALIFIED", "unsupported OpenAI execution parameters")
        context = parameter_context_digest(
            provider_name="openai", model=model, provider_version=None, adapter_version=ADAPTER_VERSION,
            runtime_dependencies=installed_dependencies("httpx"),
            transport={"mode": "openai-responses", "base_url": BASE_URL, "store": False,
                       "account_policy": account_policy, "parameters": self.parameters,
                       "schema_mode": "strict-canonical-and-tool-schemas-v2",
                       "continuation_bytes": MAX_CONTINUATION_BYTES,
                       "continuation_items": MAX_CONTINUATION_ITEMS},
            counting={"mode": "provider-input-tokens", "output_includes_reasoning": True},
        )
        self.qualification = qualification
        if qualification is not None:
            build, manifest = methodology_binding(methodology_root or Settings().deploy_v_root)
            qualification.validate_binding(
                provider_name="openai", model=model, provider_version=None, adapter_version=ADAPTER_VERSION,
                parameter_context_digest=context, methodology_build_id=build, methodology_manifest_digest=manifest,
            )
        self.identity = ProviderIdentity(
            provider_name="openai", model=model, provider_version=None, adapter_version=ADAPTER_VERSION,
            parameter_context_digest=context,
            qualification_record_id=qualification.record_id if qualification else None,
            qualification_record_digest=qualification.record_digest if qualification else None,
            qualification_status="qualified" if qualification else "unqualified",
            qualification_expires_at=qualification.expires_at if qualification else None,
        )
        from ..observability import register_secrets

        register_secrets(api_key)
        self._client = httpx.AsyncClient(base_url=BASE_URL, headers={"Authorization": f"Bearer {api_key}"},
                                         timeout=PROVIDER_TIMEOUT_SECONDS, follow_redirects=False)

    async def aclose(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _wire_input(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for message in messages:
            content = message.get("content")
            if message.get("role") == "assistant" and message.get("continuation"):
                result.extend(message["continuation"])
            elif isinstance(content, str):
                result.append({"role": message["role"], "content": content})
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        result.append({"type": "function_call_output", "call_id": block["tool_use_id"],
                                       "output": block["content"]})
                    elif isinstance(block, ProviderBlock) and block.type == "tool_use":
                        result.append({"type": "function_call", "call_id": block.id, "name": block.name,
                                       "arguments": json.dumps(block.input, sort_keys=True)})
                    elif isinstance(block, ProviderBlock) and block.type == "text":
                        result.append({"role": message["role"], "content": block.text})
                    else:
                        raise AgentError("AGENT_OUTPUT_INVALID", "unroutable OpenAI message block")
            else:
                raise AgentError("AGENT_OUTPUT_INVALID", "unroutable OpenAI message")
        return result

    def _payload(self, request: ProviderRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model, "instructions": request.system, "input": self._wire_input(request.messages),
            "store": False, "stream": False, "truncation": "disabled", "parallel_tool_calls": False,
            "include": ["reasoning.encrypted_content"],
            "text": {"format": {"type": "json_schema", "name": "CanonicalModuleOutput",
                                "strict": True, "schema": strict_output_schema(request.schema)}},
        }
        if "reasoning_effort" in self.parameters:
            payload["reasoning"] = {"effort": self.parameters["reasoning_effort"]}
        tools = request.effective_tools()
        if tools:
            payload["tools"] = [{"type": "function", "name": tool["name"],
                                 "description": tool["description"], "parameters": strict_output_schema(tool["input_schema"]),
                                 "strict": tool["strict"]} for tool in tools]
            payload["tool_choice"] = "auto"
        if request.max_tokens is not None:
            # Responses counts reasoning within this ceiling and output_tokens usage.
            payload["max_output_tokens"] = request.max_tokens
        return payload

    async def _post(self, path: str, payload: dict[str, Any], timeout: float | None) -> dict[str, Any]:
        try:
            response = await self._client.post(path, json=payload, timeout=timeout or PROVIDER_TIMEOUT_SECONDS)
        except httpx.TimeoutException as exc:
            raise AgentError("AGENT_PROVIDER_TIMEOUT", "OpenAI request timed out") from exc
        except httpx.HTTPError as exc:
            raise AgentError("AGENT_PROVIDER_UNAVAILABLE", "OpenAI transport failed") from exc
        if response.status_code >= 400:
            # Provider bodies can echo input or credentials: only the status crosses this boundary.
            raise AgentError("AGENT_PROVIDER_UNAVAILABLE", f"OpenAI returned HTTP {response.status_code}")
        try:
            body = response.json()
        except (ValueError, UnicodeError) as exc:
            raise AgentError("AGENT_OUTPUT_INVALID", "OpenAI returned malformed JSON") from exc
        if not isinstance(body, dict):
            raise AgentError("AGENT_OUTPUT_INVALID", "OpenAI returned an invalid response")
        return body

    async def count_tokens(self, request: ProviderRequest) -> int:
        payload = self._payload(request)
        # Exact input-token endpoint projection; generation controls are not accepted there.
        for key in ("store", "stream", "include", "max_output_tokens"):
            payload.pop(key, None)
        body = await self._post("/responses/input_tokens", payload, request.timeout)
        count = body.get("input_tokens")
        if body.get("object") != "response.input_tokens" or type(count) is not int or count < 0:
            raise AgentError("AGENT_OUTPUT_INVALID", "OpenAI returned an invalid input-token count")
        return count

    async def create_message(self, request: ProviderRequest) -> ProviderMessage:
        body = await self._post("/responses", self._payload(request), request.timeout)
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        blocks: list[ProviderBlock] = []
        continuation: tuple[dict[str, Any], ...] = ()
        stop = "invalid_response"
        try:
            blocks, continuation = self._output(body.get("output"))
            if body.get("status") == "completed" and not body.get("error"):
                stop = "tool_use" if any(block.type == "tool_use" for block in blocks) else "end_turn"
            elif body.get("status") == "incomplete":
                details = body.get("incomplete_details")
                stop = "max_tokens" if isinstance(details, dict) and details.get("reason") == "max_output_tokens" else "incomplete"
        except (AgentError, KeyError, TypeError, ValueError):
            # Return known spend even when output is malformed; the shared loop reconciles first.
            blocks, continuation = [], ()
        return ProviderMessage(
            content=blocks, stop_reason=stop,
            usage=ProviderUsage(input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens")),
            request_id=body.get("id"), observed_model=body.get("model"),
            observed_provider_version=body.get("provider_version"), continuation=continuation,
        )

    @staticmethod
    def _output(output: Any) -> tuple[list[ProviderBlock], tuple[dict[str, Any], ...]]:
        if not isinstance(output, list) or len(output) > MAX_CONTINUATION_ITEMS:
            raise AgentError("AGENT_OUTPUT_INVALID", "invalid OpenAI output items")
        blocks: list[ProviderBlock] = []
        continuation: list[dict[str, Any]] = []
        for item in output:
            if not isinstance(item, dict):
                raise AgentError("AGENT_OUTPUT_INVALID", "invalid OpenAI output item")
            kind = item.get("type")
            if kind == "reasoning":
                encrypted, item_id = item.get("encrypted_content"), item.get("id")
                if not isinstance(encrypted, str) or not encrypted or not isinstance(item_id, str):
                    raise AgentError("AGENT_OUTPUT_INVALID", "missing encrypted reasoning continuation")
                # No summary or raw reasoning content is retained, even if supplied by the vendor.
                continuation.append({"type": "reasoning", "id": item_id, "summary": [], "encrypted_content": encrypted})
            elif kind == "function_call":
                if not all(isinstance(item.get(key), str) and item[key] for key in ("call_id", "name", "arguments")):
                    raise AgentError("AGENT_OUTPUT_INVALID", "malformed OpenAI function call")
                arguments = json.loads(item["arguments"], object_pairs_hook=reject_duplicate_keys)
                if not isinstance(arguments, dict):
                    raise AgentError("AGENT_OUTPUT_INVALID", "malformed OpenAI function arguments")
                blocks.append(ProviderBlock(type="tool_use", id=item["call_id"], name=item["name"], input=arguments))
                continuation.append({key: item[key] for key in ("type", "id", "call_id", "name", "arguments") if key in item})
            elif kind == "message" and item.get("role") == "assistant":
                for content in item["content"]:
                    if not isinstance(content, dict):
                        raise AgentError("AGENT_OUTPUT_INVALID", "invalid OpenAI message content")
                    if content.get("type") == "refusal":
                        blocks.append(ProviderBlock(type="refusal"))
                    elif content.get("type") == "output_text" and isinstance(content.get("text"), str):
                        blocks.append(ProviderBlock(type="text", text=content["text"]))
                    else:
                        raise AgentError("AGENT_OUTPUT_INVALID", "unsupported OpenAI message content")
                continuation.append({"role": "assistant", "content": "".join(block.text or "" for block in blocks if block.type == "text")})
            else:
                raise AgentError("AGENT_OUTPUT_INVALID", "unsupported OpenAI output item")
        # ponytail: bound invocation continuation to 256 KiB; qualify a larger policy before widening.
        if len(json.dumps(continuation, ensure_ascii=False).encode()) > MAX_CONTINUATION_BYTES:
            raise AgentError("AGENT_OUTPUT_INVALID", "OpenAI continuation exceeds the qualified bound")
        return blocks, tuple(continuation)
