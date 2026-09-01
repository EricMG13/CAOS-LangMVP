"""Anthropic adapter lifecycle stays at the adapter boundary."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SERVER = Path(__file__).resolve().parents[1] / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from caos.engine.anthropic import AnthropicProvider  # noqa: E402
from caos.engine.provider import ProviderRequest  # noqa: E402


async def test_anthropic_provider_closes_both_sdk_clients_once_and_retries_failure():
    class AsyncClient:
        attempts = 0

        async def close(self) -> None:
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("transient close failure")

    class SyncClient:
        attempts = 0

        def close(self) -> None:
            self.attempts += 1

    async_client = AsyncClient()
    sync_client = SyncClient()
    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider.chat = SimpleNamespace(_async_client=async_client, _client=sync_client)
    provider._closed = False

    with pytest.raises(RuntimeError, match="transient close failure"):
        await provider.aclose()
    await provider.aclose()
    await provider.aclose()

    assert async_client.attempts == 2
    assert sync_client.attempts == 2


async def test_anthropic_provider_closes_both_real_sdk_clients():
    provider = AnthropicProvider("inert-test-key", "claude-sonnet-4-6")

    assert provider.chat._async_client.is_closed() is False
    assert provider.chat._client.is_closed() is False
    await provider.aclose()

    assert provider.chat._async_client.is_closed() is True
    assert provider.chat._client.is_closed() is True


async def test_anthropic_response_reports_its_observed_model():
    class Messages:
        async def create(self, **_payload):
            return SimpleNamespace(
                content=[], stop_reason="end_turn",
                usage=SimpleNamespace(input_tokens=1, output_tokens=0),
                _request_id="req-1", model="claude-observed", provider_version="2026-09-01",
            )

    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider.model = "claude-configured"
    provider.chat = SimpleNamespace(_async_client=SimpleNamespace(messages=Messages()))
    message = await provider.create_message(ProviderRequest(
        system="system", messages=[], schema={}, tools_enabled=False,
    ))

    assert message.observed_model == "claude-observed"
    assert message.observed_provider_version == "2026-09-01"
