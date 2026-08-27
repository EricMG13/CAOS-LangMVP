"""Provider port: the legacy transport shape survives; the gateway does not.

The engine talks to this port only. Production binds it to an adapter built on
langchain-anthropic's pinned client (see anthropic.AnthropicProvider); tests
bind a scripted double. Nothing here is copied from LEGACY workflows/provider.py — the
dataclass port shape is the recorded surviving contract (DECISIONS §5).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


READ_EVIDENCE_TOOL = {
    "name": "read_evidence",
    "description": "Read exact blocks from the run's pinned supplied evidence set.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "source_id": {"type": "string"},
            "block_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["source_id", "block_ids"],
        "additionalProperties": False,
    },
}


class AgentError(RuntimeError):
    """Typed agent failure; .code carries the legacy taxonomy string verbatim."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {message}" if message else code)


@dataclass(frozen=True)
class ProviderBlock:
    type: str
    id: str | None = None
    name: str | None = None
    input: dict[str, Any] | None = None
    text: str | None = None


@dataclass(frozen=True)
class ProviderUsage:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class ProviderMessage:
    content: list[ProviderBlock]
    stop_reason: str
    usage: ProviderUsage
    request_id: str | None = None


@dataclass(frozen=True)
class ProviderRequest:
    system: str
    messages: list[dict[str, Any]]
    schema: dict[str, Any]
    tools_enabled: bool
    max_tokens: int | None = None
    timeout: float | None = None


class Provider(Protocol):
    def count_tokens(self, request: ProviderRequest) -> int: ...

    def create_message(self, request: ProviderRequest) -> ProviderMessage: ...
