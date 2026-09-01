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
